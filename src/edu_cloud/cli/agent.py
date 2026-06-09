"""CLI entry point for Agent — single-shot execution."""
import argparse
import asyncio
import json
import sys
import uuid


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="edu-agent",
        description="edu-cloud Agent CLI — single-shot execution",
    )
    parser.add_argument("--provider-status", action="store_true", help="Print provider readiness and exit")
    parser.add_argument("--coze-live-smoke", action="store_true", help="Run a live Coze provider smoke test")
    parser.add_argument("--school", help="School code (e.g. YCSY2026)")
    parser.add_argument("--role", default="principal", help="Role (default: principal)")
    parser.add_argument("message", nargs="?", help="Message to send to Agent")
    args = parser.parse_args(argv)
    if not args.provider_status and not args.coze_live_smoke:
        if not args.school:
            parser.error("--school is required unless --provider-status or --coze-live-smoke is set")
        if not args.message:
            parser.error("message is required unless --provider-status or --coze-live-smoke is set")
    return args


async def _run(args: argparse.Namespace) -> None:
    """Execute Agent and print JSON lines to stdout."""
    from datetime import datetime

    from edu_cloud.ai.data_scope import DataScope
    from edu_cloud.ai.engine.tools import collect_all_tools, filter_tools_for_role
    from edu_cloud.ai.engine.tool_wrapper import TOOL_META_REGISTRY
    from edu_cloud.ai.providers import AgentProviderContext, create_agent_run
    from edu_cloud.ai.memory_store import MemoryStore
    from edu_cloud.ai.anonymizer import Anonymizer
    from edu_cloud.ai.prompts import build_teacher_prompt
    from edu_cloud.config import settings
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

    provider_context = AgentProviderContext(
        db_sessionmaker=async_session,
        user_id="cli", school_id=args.school, role=args.role,
        data_scope=scope, enabled_modules=enabled_modules, capabilities={},
        anonymizer=Anonymizer(), memory=MemoryStore(),
        session_id=f"cli-{uuid.uuid4().hex[:12]}",
        system_prompt=prompt, tool_meta_registry=TOOL_META_REGISTRY,
        tool_functions=allowed, tool_names=tool_names, provider_state={},
    )
    runtime = await create_agent_run(settings, provider_context)

    async for event in runtime.run(args.message):
        print(json.dumps({"type": event.type, "data": event.data}, ensure_ascii=False))


class _NoopDb:
    def add(self, obj):
        return None

    async def commit(self):
        return None


class _NoopSessionmaker:
    def __call__(self):
        return self

    async def __aenter__(self):
        return _NoopDb()

    async def __aexit__(self, exc_type, exc, tb):
        return None


async def _coze_live_smoke(message: str | None = None) -> int:
    from edu_cloud.ai.providers import AgentProviderContext, provider_status
    from edu_cloud.ai.providers.coze import CozeProvider
    from edu_cloud.config import settings

    provider = CozeProvider(settings)
    if not provider.is_available():
        print(json.dumps({
            "type": "error",
            "data": {
                "message": "Coze provider is not configured",
                "provider": provider_status(settings),
            },
        }, ensure_ascii=False))
        return 2

    ctx = AgentProviderContext(
        db_sessionmaker=_NoopSessionmaker(),
        user_id="coze-live-smoke",
        school_id="coze-live-smoke",
        role="subject_teacher",
        data_scope=None,
        enabled_modules=frozenset(),
        capabilities={},
        anonymizer=None,
        memory=None,
        session_id=f"coze-live-smoke-{uuid.uuid4().hex[:12]}",
        system_prompt="",
        tool_meta_registry={},
        tool_functions=[],
        tool_names=[],
        provider_state={},
    )
    runtime = await provider.create_run(ctx)
    prompt = message or "请用一句中文回复：Coze live smoke OK"
    got_answer = False
    got_done = False
    got_error = False
    async for event in runtime.run(prompt):
        if event.type == "answer":
            got_answer = True
        if event.type == "done":
            got_done = True
        if event.type == "error":
            got_error = True
        print(json.dumps(event.to_dict(), ensure_ascii=False))
    return 0 if got_answer and got_done and not got_error else 1


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.provider_status:
        from edu_cloud.ai.providers import provider_status
        from edu_cloud.config import settings

        print(json.dumps(provider_status(settings), ensure_ascii=False))
        return
    if args.coze_live_smoke:
        code = asyncio.run(_coze_live_smoke(args.message))
        if code:
            raise SystemExit(code)
        return
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
