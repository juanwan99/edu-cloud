"""CLI entry point for Agent — single-shot execution."""
import argparse
import asyncio
import json
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="edu-agent",
        description="edu-cloud Agent CLI — single-shot execution",
    )
    parser.add_argument("--school", required=True, help="School code (e.g. YCSY2026)")
    parser.add_argument("--role", default="principal", help="Role (default: principal)")
    parser.add_argument("message", help="Message to send to Agent")
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> None:
    """Execute Agent and print JSON lines to stdout."""
    from datetime import datetime

    from edu_cloud.ai.data_scope import DataScope
    from edu_cloud.ai.engine.edu_runtime import EduAgentRuntime
    from edu_cloud.ai.engine.tools import collect_all_tools, filter_tools_for_role
    from edu_cloud.ai.engine.tool_wrapper import TOOL_META_REGISTRY
    from edu_cloud.ai.memory_store import MemoryStore
    from edu_cloud.ai.anonymizer import Anonymizer
    from edu_cloud.ai.prompts import build_teacher_prompt
    from edu_cloud.database import async_session

    all_tools = collect_all_tools()
    enabled_modules = frozenset({"exam", "grading", "homework", "calendar", "studio", "conduct"})
    allowed = filter_tools_for_role(all_tools, role=args.role, enabled_modules=enabled_modules)
    tool_names = [getattr(fn, "_edu_meta", None).name for fn in allowed if getattr(fn, "_edu_meta", None)]

    scope = DataScope(
        user_id="cli", school_id=args.school, role=args.role,
        visible_class_ids=None, visible_subject_codes=None,
        visible_grade_ids=None, visible_student_ids=None, district_ids=None,
        can_write=True, can_see_rankings=True, can_cross_school=args.role == "platform_admin",
        persona="teacher_assistant", version=1, computed_at=datetime.now(),
    )

    prompt = build_teacher_prompt(
        role=args.role, display_name="CLI", school_name=args.school,
        tool_names=tool_names, tier=3,
    )

    runtime = EduAgentRuntime(
        db_sessionmaker=async_session,
        user_id="cli", school_id=args.school, role=args.role,
        data_scope=scope, enabled_modules=enabled_modules, capabilities={},
        anonymizer=Anonymizer(), memory=MemoryStore(),
        system_prompt=prompt, tool_meta_registry=TOOL_META_REGISTRY,
        tool_functions=allowed,
    )
    runtime.build_agent()

    async for event in runtime.run(args.message):
        print(json.dumps({"type": event.type, "data": event.data}, ensure_ascii=False))


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
