"""LLM生成器"""

from typing import List, Dict
import httpx

from config import settings


class LLMGenerator:
    """LLM生成器"""
    
    def __init__(self):
        self.api_key = settings.llm_api_key
        self.api_url = settings.llm_api_url
        self.model = settings.llm_model
    
    async def generate_with_history(
        self, query: str, context: List[Dict], collection: str, history: List[Dict] = None
    ) -> str:
        """生成答案（带历史）"""
        if not context:
            return "抱歉，没有找到相关信息。"
        
        prompt = self._build_prompt(query, context, collection, history)
        
        if self.api_key and self.api_url:
            return await self._call_llm(prompt)
        else:
            return self._fallback_answer(context, collection)
    
    async def _call_llm(self, prompt=None, messages=None, temperature=None) -> str:
        """调用 LLM API。

        支持两种调用方式：
        - _call_llm(prompt="...")            Agent/RAG 路径，自动拼接 system prompt
        - _call_llm(messages=[{...}], temperature=0)  Router 路径，直接传入消息列表
        """
        try:
            print(f"DEBUG: 正在请求的 URL -> {self.api_url}")
            print(f"DEBUG: 使用的模型名称 -> {self.model}")

            if messages is not None:
                msg_list = messages
            elif prompt is not None:
                msg_list = [
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt}
                ]
            else:
                return "LLM调用失败: 未提供 prompt 或 messages"

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": msg_list,
                        "temperature": temperature if temperature is not None else settings.llm_temperature,
                        "max_tokens": settings.llm_max_tokens
                    },
                    timeout=settings.llm_timeout
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                return f"LLM API错误: {resp.status_code}"
        except Exception as e:
            return f"LLM调用失败: {str(e)}"
    
    def _system_prompt(self) -> str:
        return (
            "你是招投标智能问答助手，请根据提供的参考信息准确回答问题。"
            "重要规则：\n"
            "1. 如果问题涉及多个法条或需要综合多条参考信息才能完整回答，请务必整合所有相关片段，不要只依赖单一来源。\n"
            "2. 如果参考信息不足以回答问题，请如实告知，不要编造信息。\n"
            "3. 引用法规时请注明出处（法律名称+条款号），引用项目数据时请注明项目和金额。"
        )
    
    def _build_prompt(self, query: str, context: List[Dict], collection: str, history: List[Dict] = None) -> str:
        history_text = ""
        if history:
            history_parts = []
            for h in history[-3:]:
                history_parts.append(f"用户：{h['question']}\n助手：{h['answer']}")
            if history_parts:
                history_text = "【对话历史】\n" + "\n\n".join(history_parts) + "\n\n"
        
        # 优先使用 parent_content（完整法条），其次 text（embedding 文本）
        # 取 top-5 片段，每条最多 1500 字符，确保长法条和多片段场景不被截断
        max_per_fragment = 1500
        max_fragments = min(len(context), 5)
        context_text = "\n\n".join([
            f"【参考信息{i+1}】\n{(c.get('parent_content') or c.get('text', ''))[:max_per_fragment]}"
            for i, c in enumerate(context[:max_fragments])
        ])
        
        return f"{history_text}【参考信息】\n{context_text}\n\n【当前问题】\n{query}\n\n【回答】"
    
    def _fallback_answer(self, context: List[Dict], collection: str) -> str:
        best = context[0].get("data", {})
        if collection == "bids":
            return f"找到相关招标项目：{best.get('project_name', '未知')}，中标人：{best.get('winner', '未知')}，中标金额：{best.get('winner_amount', '未知')}元"
        elif collection == "regulations":
            return f"找到相关法规内容：{best.get('text', '')[:300]}"
        else:
            return f"找到相关信息：{best}"