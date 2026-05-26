"""ReAct Agent — Thought → Action → Observation 循环"""
import json
import re
from typing import Dict, Optional, List
from app.agent.agent_tools import TOOL_CLASSES, BaseTool
from config import settings


REACT_PROMPT = """你是一个招投标法规专家助手。可以使用工具检索信息，基于检索结果回答问题。

## 历史对话记录（最近 5 轮）
{history}

## 当前用户问题
{question}

## 可用工具
{tools_description}

## 工具调用格式
**Action Input 必须是 JSON 格式**

示例：
Thought: 需要查询围标的定义
Action: search_regulations
Action Input: {{"query": "串通投标的定义"}}

示例：
Thought: 需要查第33条
Action: get_article
Action Input: {{"article_num": "33"}}

示例：
Thought: 需要统计去年项目数量
Action: sql_query
Action Input: {{"query": "去年有多少个招标项目"}}

## 重要规则
1. 每轮只能调用一个工具
2. Action Input 必须使用双花括号 {{{{}}}} 包裹的 JSON 格式
3. 信息足够时输出 Final Answer
4. 如果用户使用了指代词，请结合历史对话理解问题
5. 比较类问题先分别检索再比较
6. 如果没有找到相关信息，请如实告知

请继续输出（必须包含 Thought 和 Action，或 Final Answer）：
"""


class ReActAgent:
    """ReAct Agent — 思考→行动→观察 循环"""

    def __init__(self, retriever, llm, max_steps: int = 5, session_manager=None):
        self.retriever = retriever
        self.llm = llm
        self.max_steps = max_steps
        self.session_manager = session_manager
        self.tools: Dict[str, BaseTool] = {}

        for tool_name, tool_class in TOOL_CLASSES.items():
            self.tools[tool_name] = tool_class(retriever, llm)

    def _get_tools_description(self) -> str:
        lines = []
        for name, tool in self.tools.items():
            lines.append(f"- {name}: {tool.description}")
        return "\n".join(lines)

    def _get_history_context(self, session_id: str, max_messages: int = 10) -> str:
        if not self.session_manager or not session_id:
            return "（无历史记录）"

        try:
            history = self.session_manager.get_chat_history(session_id)
            messages = history.messages[-max_messages:] if max_messages > 0 else history.messages
            if not messages:
                return "（无历史记录）"

            lines = ["以下是最近的对话历史："]
            for msg in messages:
                role = "用户" if msg.type == "human" else "助手"
                lines.append(f"[{role}]: {msg.content[:800]}")
            return "\n".join(lines)
        except Exception:
            return "（无历史记录）"

    def _parse_action(self, text: str) -> Optional[Dict]:
        action_match = re.search(r'Action:\s*(\w+)', text)
        if not action_match:
            return None

        action = action_match.group(1)

        # JSON 格式
        json_match = re.search(r'Action Input:\s*(\{[\s\S]+?\})', text)
        if json_match:
            try:
                action_input = json.loads(json_match.group(1))
                return {"action": action, "action_input": action_input}
            except json.JSONDecodeError:
                pass

        # 双引号字符串
        quoted = re.search(r'Action Input:\s*"([^"]+)"', text)
        if quoted:
            query = quoted.group(1).strip()
            if action == "get_article":
                return {"action": action, "action_input": {"article_num": query} if query.isdigit() else {"query": query}}
            return {"action": action, "action_input": {"query": query}}

        # 降级：从文本中提取 query 参数
        qm = re.search(r'"query"\s*:\s*"([^"]+)"', text)
        if qm:
            return {"action": action, "action_input": {"query": qm.group(1)}}

        am = re.search(r'"article_num"\s*:\s*"(\d+)"', text)
        if am:
            return {"action": action, "action_input": {"article_num": am.group(1)}}

        return {"action": action, "action_input": {}}

    def _extract_final_answer(self, text: str) -> Optional[str]:
        match = re.search(r'Final Answer:\s*(.+)', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        if not re.search(r'Action:', text) and len(text) > 100:
            return text.strip()
        return None

    async def run(self, question: str, session_id: str = "") -> str:
        print(f"\n[Agent] 处理: {question}")

        base_history = self._get_history_context(session_id, max_messages=10)
        step_records: List[str] = []

        for step in range(self.max_steps):
            print(f"   Step {step + 1}/{self.max_steps}...")

            history_context = base_history
            if step_records:
                history_context += "\n\n## 检索过程\n" + "\n\n".join(step_records[-3:])

            prompt = REACT_PROMPT.format(
                history=history_context,
                question=question,
                tools_description=self._get_tools_description(),
            )

            try:
                temp = getattr(settings, 'agent_temperature', 0.3)
                response = await self.llm._call_llm([
                    {"role": "user", "content": prompt}
                ], temperature=temp)
                print(f"   [LLM] {response[:300]}...")

                final_answer = self._extract_final_answer(response)
                if final_answer:
                    print(f"   [Final Answer]")
                    return final_answer

                action_info = self._parse_action(response)
                if not action_info:
                    print(f"   [WARN] 无法解析 Action，用默认检索")
                    action_info = {"action": "search_regulations", "action_input": {"query": question}}

                tool_name = action_info["action"]
                tool_input = action_info.get("action_input", {})

                if tool_name not in self.tools:
                    print(f"   [ERROR] 未知工具: {tool_name}")
                    continue

                print(f"   [Tool] {tool_name}({tool_input})")
                observation = await self.tools[tool_name].run(**tool_input)
                print(f"   [Obs] 结果: {observation[:200]}...")

                step_records.append(f"Action: {tool_name}\nObservation: {observation[:500]}")

            except Exception as e:
                print(f"   [ERROR] Agent错误: {e}")
                # 降级到直接 RAG
                results = self.retriever.search(question, "regulations", top_k=5)
                if results and self.llm:
                    context = "\n\n".join([r.get("text", "")[:500] for r in results[:3]])
                    try:
                        return await self.llm._call_llm([
                            {"role": "user", "content": f"基于以下信息回答问题：\n{context}\n\n问题：{question}"}
                        ])
                    except Exception:
                        pass
                return f"处理失败: {str(e)}"

        # 达到最大步数，强制总结
        print(f"   [MAX_STEPS] 达到最大步数，强制总结")
        all_obs = []
        for rec in step_records:
            m = re.search(r'Observation: (.+)', rec, re.DOTALL)
            if m:
                all_obs.append(m.group(1).strip())

        if all_obs and self.llm:
            context = "\n\n".join(all_obs[:5])
            try:
                return await self.llm._call_llm([
                    {"role": "user", "content": f"基于以下信息回答问题：\n{context[:3000]}\n\n问题：{question}"}
                ])
            except Exception:
                pass

        return f"经过 {self.max_steps} 步检索，未能得到完整答案。请尝试更具体的问题。"
