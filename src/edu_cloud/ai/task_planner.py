"""Task decomposition and scheduling for complex goals (Design §7)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Generator

from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest
from edu_cloud.ai.registry import ToolSpec
from edu_cloud.ai.schemas import Message

logger = logging.getLogger(__name__)


@dataclass
class Task:
    id: str
    description: str
    status: str = "pending"
    tools_hint: list[str] | None = None
    depends_on: list[str] | None = None
    result_summary: str | None = None
    verify: str | None = None


@dataclass
class Plan:
    goal: str
    tasks: list[Task]
    current_task_index: int = 0


class TaskPlanner:
    async def maybe_plan(
        self,
        goal: str,
        tier: int,
        adapter: LLMProxyAdapter,
        available_tools: list[ToolSpec],
    ) -> Plan | None:
        if tier == 3:
            return None

        tool_desc = "\n".join(f"- {t.name}: {t.description}" for t in available_tools)
        prompt = (
            "你是任务规划器。用户给你一个目标，你判断：\n"
            '- 如果一步就能完成，回复 {"plan": null}\n'
            "- 如果需要多步，回复：\n"
            '{"plan": [{"description": "...", "tools_hint": ["..."], "depends_on": ["task_id"], "verify": "..."}]}\n\n'
            f"可用工具：\n{tool_desc}\n\n"
            "规划原则：每个任务是一个可独立验证的步骤；无依赖关系的任务可并行。"
        )

        try:
            resp = await adapter.chat(LLMRequest(
                messages=[Message(role="system", content=prompt), Message(role="user", content=goal)],
                max_tokens=1500,
                stream=False,
            ))
            data = json.loads(resp.content)
            if data.get("plan") is None:
                return None

            tasks = [
                Task(
                    id=str(i),
                    description=t["description"],
                    tools_hint=t.get("tools_hint"),
                    depends_on=t.get("depends_on", []),
                    verify=t.get("verify") if tier == 1 else None,
                )
                for i, t in enumerate(data["plan"])
            ]
            return Plan(goal=goal, tasks=tasks)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Plan parsing failed: %s", exc)
            return None

    def schedule(self, plan: Plan) -> Generator[Task, None, None]:
        completed: set[str] = set()
        remaining = list(plan.tasks)

        while remaining:
            ready = [t for t in remaining if all(d in completed for d in (t.depends_on or []))]
            if not ready:
                logger.error("Task dependency deadlock: %s", [t.id for t in remaining])
                yield from remaining
                return
            for task in ready:
                yield task
                completed.add(task.id)
                remaining.remove(task)
