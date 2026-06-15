"""Agent 模块 — LangGraph ReAct Agent + Planner DAG + @tool 工具

主要导出:
    LangGraphReActAgent    — LangGraph create_react_agent (替代旧 ReActAgent)
    LangGraphPlannerAgent  — LangGraph DAG StateGraph (替代旧 PlannerExecutor)
    create_agent_tools     — 闭包工厂，创建注入依赖的工具列表（消除全局变量）
"""

from app.agent.langgraph_agent import LangGraphReActAgent, LangGraphPlannerAgent
from app.agent.agent_tools import create_agent_tools, AGENT_TOOLS, set_tool_dependencies

__all__ = [
    "LangGraphReActAgent",
    "LangGraphPlannerAgent",
    "create_agent_tools",
    "AGENT_TOOLS",
    "set_tool_dependencies",
]
