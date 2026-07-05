"""Agent 模块 — ReAct Agent + Planner + 结构化状态 + 可插拔工具注册

主要导出:
    ReActAgent      — 思考→行动→观察 循环（单步决策）
    PlannerExecutor — 计划→执行→汇总（先规划再执行）
    AgentState      — 执行状态容器（可序列化）
    StepRecord      — 单步记录
    BaseTool        — 工具基类
    TOOL_CLASSES    — 工具注册表
"""

from app.agent.agent_state import AgentState, StepRecord
from app.agent.agent_tools import BaseTool, TOOL_CLASSES
from app.agent.react_agent import ReActAgent
from app.agent.planner import PlannerExecutor, PlannedTask, PlannedStep, StepResult, DAGDeadlockError

__all__ = [
    "ReActAgent",
    "PlannerExecutor",
    "PlannedTask",
    "PlannedStep",
    "StepResult",
    "DAGDeadlockError",
    "AgentState",
    "StepRecord",
    "BaseTool",
    "TOOL_CLASSES",
]
