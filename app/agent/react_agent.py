"""ReAct Agent — Thought → Action → Observation 循环

核心流程:
    用户问题 → AgentState 初始化
    → [循环] LLM 输出 Thought + Action → 执行工具 → 记录 Observation → 更新 State
    → 输出 Final Answer → State.finish()

State 和 Agent 的关系:
    - AgentState 是"施工档案"，Agent 是"施工队"
    - Agent 只负责控制流（解析→执行→回写 State）
    - State 是纯数据结构，可序列化、可调试、可给前端展示
    - 这种分离让你以后可以轻松加: 中断恢复、人工审批节点、多 Agent 编排
"""

import json
import re
import time
from typing import Dict, Optional, List

from app.agent.agent_tools import TOOL_CLASSES, BaseTool
from app.agent.agent_state import AgentState, StepRecord
from config import settings

CHECKPOINT_DIR = settings.checkpoint_dir
CHECKPOINT_ENABLED = settings.checkpoint_enabled


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
    """ReAct Agent — 思考→行动→观察 循环

    用法:
        agent = ReActAgent(retriever, llm, max_steps=5)
        answer = await agent.run("围标怎么处罚")
        # answer 是最终答案字符串
        # agent.last_state 里有完整的执行轨迹（AgentState 对象）
        agent.last_state.print_trace()  # 打印执行过程
        print(agent.last_state.to_dict())  # 序列化
    """

    def __init__(
        self,
        retriever,
        llm,
        max_steps: int = 5,
        session_manager=None,
    ):
        self.retriever = retriever
        self.llm = llm
        self.max_steps = max_steps
        self.session_manager = session_manager

        # 按 TOOL_CLASSES 注册表实例化所有工具
        self.tools: Dict[str, BaseTool] = {}
        for tool_name, tool_class in TOOL_CLASSES.items():
            self.tools[tool_name] = tool_class(retriever, llm)

        # 最后一次运行的完整状态（外部只读）
        self.last_state: Optional[AgentState] = None

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _save_checkpoint(self, state: AgentState, session_id: str):
        """每步保存状态快照（单文件覆盖，不累积）"""
        if CHECKPOINT_ENABLED:
            try:
                state.save_checkpoint(CHECKPOINT_DIR, session_id or "default")
            except Exception:
                pass  # 断点保存失败不阻断主流程

    def _delete_checkpoint(self, session_id: str):
        """任务完成时清理断点文件"""
        if CHECKPOINT_ENABLED:
            try:
                AgentState.delete_checkpoint(CHECKPOINT_DIR, session_id or "default")
            except Exception:
                pass

    def _get_tools_description(self) -> str:
        """生成工具列表描述文本，注入 prompt"""
        lines = []
        for name, tool in self.tools.items():
            lines.append(f"- {name}: {tool.description}")
        return "\n".join(lines)

    def _get_history_context(self, session_id: str, max_messages: int = 10) -> str:
        """从 Redis session 拉取最近几轮对话"""
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
        """从 LLM 原始输出中提取 Action 和 Action Input

        支持的格式（按优先级）:
        1. Action Input: {json}
        2. Action Input: "string"
        3. 降级: 从文本中正则提取 "query" 或 "article_num"
        """
        # 1. 提取 Action
        action_match = re.search(r'Action:\s*(\w+)', text)
        action = action_match.group(1) if action_match else None

        # 2. 提取 Action Input (JSON 格式优先)
        json_match = re.search(r'Action Input:\s*(\{[\s\S]+?\})', text)
        if json_match:
            try:
                action_input = json.loads(json_match.group(1))
                return {"action": action or "search_regulations", "action_input": action_input}
            except json.JSONDecodeError:
                pass

        # 3. 双引号字符串格式
        quoted = re.search(r'Action Input:\s*"([^"]+)"', text)
        if quoted:
            query = quoted.group(1).strip()
            if action == "get_article":
                return {
                    "action": action,
                    "action_input": {"article_num": query} if query.isdigit() else {"query": query},
                }
            return {"action": action or "search_regulations", "action_input": {"query": query}}

        # 4. 降级: 从 JSON 体里提取字段
        qm = re.search(r'"query"\s*:\s*"([^"]+)"', text)
        if qm:
            return {"action": action or "search_regulations", "action_input": {"query": qm.group(1)}}

        am = re.search(r'"article_num"\s*:\s*"(\d+)"', text)
        if am:
            return {"action": action or "get_article", "action_input": {"article_num": am.group(1)}}

        # 5. 完全无法解析 — 但有 Action 名
        if action:
            return {"action": action, "action_input": {}}

        return None

    def _extract_thought(self, text: str) -> str:
        """提取 Thought 部分（用于记录，不影响逻辑）"""
        m = re.search(r'Thought:\s*(.+?)(?:\n\s*(?:Action|Final))', text, re.DOTALL)
        return m.group(1).strip() if m else ""

    def _extract_final_answer(self, text: str) -> Optional[str]:
        """检测 LLM 是否给出了最终答案"""
        match = re.search(r'Final Answer:\s*(.+)', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # 没有 Action 标记且文本够长 → 可能是裸答案
        if not re.search(r'Action:', text) and len(text) > 100:
            return text.strip()
        return None

    # ------------------------------------------------------------------
    # 核心执行循环
    # ------------------------------------------------------------------

    async def run(self, question: str, session_id: str = "") -> str:
        """执行 ReAct 循环，返回最终答案

        Args:
            question: 用户问题
            session_id: 可选，多轮对话的 session ID

        Returns:
            最终答案字符串。完整执行轨迹在 self.last_state
        """

        # ── 初始化状态 ──
        state = AgentState(question)
        print(f"\n[Agent] 处理: {question}")

        # ── 获取历史对话 ──
        base_history = self._get_history_context(session_id, max_messages=10)

        # ── ReAct 循环 ──
        for step_idx in range(self.max_steps):
            step_num = state.begin_step()
            print(f"   Step {step_num}/{self.max_steps}...")

            # --- 拼 prompt（含之前步骤的 Observation） ---
            history_context = base_history
            obs_context = state.get_observations_context(last_n=3)
            if obs_context and obs_context != "（尚未执行任何检索）":
                history_context += "\n\n## 检索过程\n" + obs_context

            prompt = REACT_PROMPT.format(
                history=history_context,
                question=question,
                tools_description=self._get_tools_description(),
            )

            # --- 调用 LLM ---
            try:
                state.total_llm_calls += 1
                response = await self.llm._call_llm(prompt)
                print(f"   [LLM] {response[:300]}...")
            except Exception as e:
                # LLM 调用失败 → 记录并中止
                record = StepRecord(
                    step_num=step_num,
                    error=f"LLM调用失败: {e}",
                )
                state.add_step(record)
                self._save_checkpoint(state, session_id)
                print(f"   [ERROR] LLM调用失败: {e}")
                break

            # --- 检查是否 Final Answer ---
            final_answer = self._extract_final_answer(response)
            if final_answer:
                state.finish(final_answer)
                self._delete_checkpoint(session_id)
                self.last_state = state
                print(f"   [Final Answer] {len(final_answer)} 字符")
                return final_answer

            # --- 解析 Action ---
            thought = self._extract_thought(response)
            action_info = self._parse_action(response)

            if not action_info:
                # 无法解析 → 默认用 search_regulations
                print(f"   [WARN] 无法解析 Action，降级为 search_regulations")
                action_info = {"action": "search_regulations", "action_input": {"query": question}}

            tool_name = action_info["action"]
            tool_input = action_info.get("action_input", {})

            # --- 执行工具 ---
            record = StepRecord(
                step_num=step_num,
                thought=thought,
                action=tool_name,
                action_input=tool_input,
                tool_name=tool_name,
            )

            if tool_name not in self.tools:
                record.error = f"未知工具: {tool_name}"
                state.add_step(record)
                self._save_checkpoint(state, session_id)
                print(f"   [ERROR] 未知工具: {tool_name}")
                # 不 break，下一轮 LLM 会看到错误并调整
                continue

            try:
                print(f"   [Tool] {tool_name}({tool_input})")
                t_start = time.time()
                observation = await self.tools[tool_name].run(**tool_input)
                record.tool_duration_ms = (time.time() - t_start) * 1000
                record.observation = observation[:800]   # 截断，避免 prompt 过长
                print(f"   [Obs] {observation[:200]}...")
            except Exception as e:
                record.error = str(e)
                record.observation = f"工具执行失败: {e}"
                print(f"   [ERROR] 工具执行失败: {e}")

            state.add_step(record)
            self._save_checkpoint(state, session_id)

        # ── 达到最大步数 → 强制总结 ──
        print(f"   [MAX_STEPS] 达到最大步数 {self.max_steps}，强制总结")
        all_obs = [s.observation for s in state.steps if s.observation and not s.error]
        if all_obs and self.llm:
            try:
                context = "\n\n".join(all_obs[-5:])
                state.total_llm_calls += 1
                answer = await self.llm._call_llm(
                    f"基于以下检索结果，简洁回答用户问题：\n\n{context[:3000]}\n\n问题：{question}"
                )
                state.finish(answer)
                self._delete_checkpoint(session_id)
                self.last_state = state
                return answer
            except Exception:
                pass

        fallback = f"经过 {state.step_count()} 步检索，未能得到完整答案。请尝试更具体的问题。"
        state.finish(fallback)
        self._delete_checkpoint(session_id)
        self.last_state = state
        return fallback
