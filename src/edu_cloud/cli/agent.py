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
    """Execute Agent and print JSON lines to stdout.

    TODO: Phase C — wire DB connection + slot lookup.
    Currently a placeholder that requires DB to actually run.
    """
    # Deferred import to avoid loading full app on parse_args tests
    from edu_cloud.ai.runtime import AgentRuntime, AgentContext
    from edu_cloud.database import async_session

    async with async_session() as db:
        ctx = AgentContext(
            db=db,
            user_id="cli",
            school_id=args.school,
            role=args.role,
            data_scope=None,
            session_id="cli-session",
            user_slots=[],  # TODO: Phase C — lookup from DB
            system_slots=[],
            enhanced_enabled=False,
        )

        runtime = AgentRuntime()
        async for event in runtime.run(args.message, ctx):
            print(json.dumps(event.to_dict(), ensure_ascii=False))


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
