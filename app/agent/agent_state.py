"""Agent 状态容器 — 结构化记录每一步的 Thought/Action/Observation

设计要点:
1. StepRecord 是每一步的"施工日志"，字段固定，方便序列化和调试
2. AgentState 是全局状态单例，Agent 只负责写，外部只读
3. 工具调用统计让调用方知道"用了哪些工具、各几次"
4. to_dict() 支持序列化，方便存日志或前端展示
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json
import os
import time


# ---------------------------------------------------------------------------
# 单步记录
# ---------------------------------------------------------------------------
@dataclass
class StepRecord:
    """ReAct 循环中一个 step 的完整记录

    一次标准的 ReAct step：
        Thought → Action → Action Input → 工具执行 → Observation
    """

    step_num: int
    task_id: str = ""                       # 关联的 task_id（Planner 模式使用）
    thought: str = ""                       # LLM 输出的 Thought 部分
    action: str = ""                        # 工具名称, e.g. "search_regulations"
    action_input: Dict[str, Any] = field(default_factory=dict)  # 传给工具的 kwarg
    observation: str = ""                   # 工具返回结果（截断前800字）
    tool_name: str = ""                     # 实际执行的工具名（回填用）
    tool_duration_ms: float = 0.0           # 工具耗时（毫秒）
    error: Optional[str] = None             # 如果这步出错，这里记录异常信息

    def is_error_step(self) -> bool:
        return self.error is not None

    def summary(self) -> str:
        """单行摘要，方便日志输出"""
        if self.error:
            return f"Step{self.step_num} ERROR: {self.error[:100]}"
        obs_preview = self.observation[:60].replace("\n", " ")
        return f"Step{self.step_num} {self.action}({self._inputs_short()}) → {obs_preview}..."

    def _inputs_short(self) -> str:
        if not self.action_input:
            return ""
        items = [f"{k}={str(v)[:30]}" for k, v in self.action_input.items()]
        return ", ".join(items)


# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------
class AgentState:
    """一次问答的完整执行状态

    生命周期：
        AgentState(question)  →  每步 add_step()  →  finish(answer)  →  to_dict()

    用法示例:
        state = AgentState("围标怎么罚")
        agent.run_with_state(state)
        print(state.tool_call_count)  # {"search_regulations": 2}
        print(state.to_dict())        # 序列化整个执行轨迹
    """

    def __init__(self, question: str):
        # ── 输入 ──
        self.question: str = question

        # ── 执行轨迹 ──
        self.steps: List[StepRecord] = []
        self.current_step: int = 0                     # 当前步数（从0开始，跟循环变量对齐）

        # ── 结果 ──
        self.final_answer: Optional[str] = None
        self.finished: bool = False
        self.errors: List[Dict[str, Any]] = []           # 非致命错误（如 dag_deadlock）

        # ── 统计 ──
        self.tool_call_count: Dict[str, int] = {}       # tool_name → 调用次数
        self.total_llm_calls: int = 0                   # LLM 被调用了多少次
        self.total_tool_calls: int = 0                  # 工具总共执行了多少次

        # ── 元信息 ──
        self.created_at: float = time.time()
        self.finished_at: Optional[float] = None

    # ── 写入接口（Agent 使用） ─────────────────────────────

    def begin_step(self) -> int:
        """开始新的一步，返回步号"""
        self.current_step += 1
        return self.current_step

    def add_step(self, record: StepRecord):
        """记录一个完整的执行步"""
        self.steps.append(record)

        # 更新工具调用统计
        tool = record.tool_name or record.action
        if tool:
            self.tool_call_count[tool] = self.tool_call_count.get(tool, 0) + 1
            self.total_tool_calls += 1

    def finish(self, answer: str):
        """标记任务完成"""
        self.final_answer = answer
        self.finished = True
        self.finished_at = time.time()

    # ── 断点续跑 ─────────────────────────────────────

    def save_checkpoint(self, checkpoint_dir: str, session_id: str = "default"):
        """保存当前状态到本地文件（每步覆盖，保持最新）"""
        os.makedirs(checkpoint_dir, exist_ok=True)
        path = os.path.join(checkpoint_dir, f"{session_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_checkpoint(cls, checkpoint_dir: str, session_id: str = "default") -> "AgentState":
        """从本地文件恢复状态（用于崩溃后续跑）"""
        path = os.path.join(checkpoint_dir, f"{session_id}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Checkpoint not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        state = cls(data.get("question", ""))
        state.final_answer = data.get("final_answer")
        state.finished = data.get("finished", False)
        state.errors = data.get("errors", [])

        stats = data.get("stats", {})
        state.tool_call_count = stats.get("tool_call_count", {})
        state.total_llm_calls = stats.get("total_llm_calls", 0)
        state.total_tool_calls = stats.get("total_tool_calls", 0)

        for s in data.get("steps", []):
            record = StepRecord(
                step_num=s.get("step_num", 0),
                thought=s.get("thought", ""),
                action=s.get("action", ""),
                action_input=s.get("action_input", {}),
                observation=s.get("observation", ""),
                tool_name=s.get("tool_name", ""),
                tool_duration_ms=s.get("tool_duration_ms", 0.0),
                error=s.get("error"),
            )
            state.steps.append(record)
            state.current_step = max(state.current_step, record.step_num)

        return state

    @staticmethod
    def delete_checkpoint(checkpoint_dir: str, session_id: str = "default"):
        """任务完成/异常时清理断点文件"""
        path = os.path.join(checkpoint_dir, f"{session_id}.json")
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    # ── 读取接口（外部观察者使用） ─────────────────────────

    def get_observations_context(self, last_n: int = 3) -> str:
        """取最近 N 步的 Action+Observation 文本，注入 LLM prompt"""
        if not self.steps:
            return "（尚未执行任何检索）"

        recent = self.steps[-last_n:]
        lines = []
        for r in recent:
            action_str = f"Action: {r.action}"
            if r.action_input:
                action_str += f"\nAction Input: {r.action_input}"
            lines.append(f"{action_str}\nObservation: {r.observation}")
        return "\n\n".join(lines)

    def get_tool_result(self, tool_name: str) -> Optional[str]:
        """获取指定工具最后一次执行的 observation"""
        for step in reversed(self.steps):
            if step.tool_name == tool_name:
                return step.observation
        return None

    def elapsed_seconds(self) -> float:
        """从创建到现在（或完成时刻）的耗时"""
        end = self.finished_at or time.time()
        return end - self.created_at

    def step_count(self) -> int:
        return len(self.steps)

    # ── 序列化 ─────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """完整序列化，方便存日志 / 前端展示"""
        return {
            "question": self.question,
            "steps": [
                {
                    "step_num": s.step_num,
                    "thought": s.thought,
                    "action": s.action,
                    "action_input": s.action_input,
                    "observation": s.observation[:500],  # 截断避免过大
                    "tool_name": s.tool_name,
                    "tool_duration_ms": s.tool_duration_ms,
                    "error": s.error,
                }
                for s in self.steps
            ],
            "final_answer": self.final_answer,
            "finished": self.finished,
            "errors": self.errors,
            "stats": {
                "tool_call_count": self.tool_call_count,
                "total_llm_calls": self.total_llm_calls,
                "total_tool_calls": self.total_tool_calls,
                "step_count": self.step_count(),
                "elapsed_seconds": round(self.elapsed_seconds(), 2),
            },
        }

    def print_trace(self):
        """打印完整执行轨迹，调试用"""
        print(f"\n{'='*60}")
        print(f"Agent 执行轨迹 | 问题: {self.question}")
        print(f"耗时: {self.elapsed_seconds():.1f}s | 步数: {self.step_count()} | LLM调用: {self.total_llm_calls}")
        print(f"{'='*60}")
        for s in self.steps:
            print(f"\n── Step {s.step_num} ──")
            if s.thought:
                print(f"  Thought: {s.thought[:200]}")
            print(f"  Action:  {s.action}")
            print(f"  Input:   {s.action_input}")
            print(f"  Result:  {s.observation[:200]}")
            if s.error:
                print(f"  [ERROR] {s.error}")
        if self.final_answer:
            print(f"\n[Final Answer] ({len(self.final_answer)} chars):")
            print(self.final_answer[:500])
        print(f"{'='*60}\n")
