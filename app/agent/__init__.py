"""Agent 模块 — LangGraph ReAct Agent + Planner DAG + @tool 工具

主要导出:
    LangGraphReActAgent    — LangGraph create_react_agent (替代旧 ReActAgent)
    LangGraphPlannerAgent  — LangGraph DAG StateGraph (替代旧 PlannerExecutor)
    AGENT_TOOLS            — LangChain @tool 工具列表
    set_tool_dependencies  — 注入 retriever/llm 到工具模块
"""

from app.agent.langgraph_agent import LangGraphReActAgent, LangGraphPlannerAgent
from app.agent.agent_tools import AGENT_TOOLS, set_tool_dependencies

__all__ = [
    "LangGraphReActAgent",
    "LangGraphPlannerAgent",
    "AGENT_TOOLS",
    "set_tool_dependencies",
]
