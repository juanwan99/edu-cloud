#!/usr/bin/env python3
"""edu-cloud 模块治理聚合脚本。

读取 `src/edu_cloud/modules/*/MODULE.md` 的 YAML frontmatter，
产出 `docs/governance/{modules.yaml, dependency-graph.md, debt-report.md}`。

**禁止手写 modules.yaml / dependency-graph.md / debt-report.md —— 单一真源在 MODULE.md。**

CLI 退出码：
- 0: 聚合成功且无冲突
- 1: 聚合成功但发现 owns_tables/owns_routes 跨模块冲突（治理违规）
- 2: 解析失败（MODULE.md frontmatter 非法）

被 `~/.claude/hooks/module_governance_guard.py` 通过 `parse_module_md` 共享契约使用。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

REQUIRED_FIELDS = [
    "name",
    "status",
    "owner",
    "layer",
    "owns_tables",
    "owns_routes",
    "exposes",
    "depends_on",
]
NESTED_REQUIRED: dict[str, list[str]] = {
    "exposes": ["services"],
    "depends_on": ["modules", "services", "ai_tools"],
}
VALID_STATUS = {"active", "deprecated", "experimental"}
VALID_LAYER = {"business", "infrastructure", "cross-cutting"}
VALID_STRUCTURE_PATTERN = {"standard", "multi-router", "service-only"}


class ModuleGovernanceError(ValueError):
    """MODULE.md 格式或内容违反纲领。"""


def parse_module_md(md_path: Path) -> dict[str, Any]:
    """解析 MODULE.md frontmatter。缺必填字段 / 枚举非法 → 抛错。"""
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ModuleGovernanceError(f"{md_path}: missing frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ModuleGovernanceError(f"{md_path}: frontmatter not closed")
    try:
        meta = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError as e:
        raise ModuleGovernanceError(f"{md_path}: YAML parse error: {e}") from e

    for field in REQUIRED_FIELDS:
        if field not in meta:
            raise ModuleGovernanceError(
                f"{md_path}: missing required field '{field}'"
            )
    if meta["status"] not in VALID_STATUS:
        raise ModuleGovernanceError(
            f"{md_path}: invalid status '{meta['status']}' (expected one of {VALID_STATUS})"
        )
    if meta["layer"] not in VALID_LAYER:
        raise ModuleGovernanceError(
            f"{md_path}: invalid layer '{meta['layer']}' (expected one of {VALID_LAYER})"
        )
    # G2-02 修复：嵌套必填 schema 校验（模板 MODULE-template.md:76-80 声明必填）
    for parent, subs in NESTED_REQUIRED.items():
        section = meta.get(parent)
        if not isinstance(section, dict):
            raise ModuleGovernanceError(
                f"{md_path}: '{parent}' must be a mapping (got {type(section).__name__})"
            )
        for sub in subs:
            if sub not in section:
                raise ModuleGovernanceError(
                    f"{md_path}: missing required nested field '{parent}.{sub}'"
                )
    # ── 结构治理字段（可选，向后兼容） ──
    if "structure_pattern" in meta:
        if meta["structure_pattern"] not in VALID_STRUCTURE_PATTERN:
            raise ModuleGovernanceError(
                f"{md_path}: invalid structure_pattern '{meta['structure_pattern']}' "
                f"(expected one of {VALID_STRUCTURE_PATTERN})"
            )
    if "max_router_loc" in meta:
        if isinstance(meta["max_router_loc"], bool) or not isinstance(meta["max_router_loc"], int) or meta["max_router_loc"] < 0:
            raise ModuleGovernanceError(
                f"{md_path}: max_router_loc must be a non-negative integer"
            )
    if "routers" in meta:
        if not isinstance(meta["routers"], list):
            raise ModuleGovernanceError(
                f"{md_path}: routers must be a list"
            )
    return meta


def detect_conflicts(modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """返回跨模块 owns_tables / owns_routes 冲突列表。

    同模块内部重复（`[t, t]`）不算冲突。
    """
    table_owner: dict[str, str] = {}
    route_owner: dict[str, str] = {}
    conflicts: list[dict[str, Any]] = []
    for m in modules:
        name = m["name"]
        for t in m.get("owns_tables") or []:
            if t in table_owner and table_owner[t] != name:
                conflicts.append(
                    {
                        "kind": "duplicate_table",
                        "value": t,
                        "owners": [table_owner[t], name],
                    }
                )
            else:
                table_owner[t] = name
        for r in m.get("owns_routes") or []:
            if r in route_owner and route_owner[r] != name:
                conflicts.append(
                    {
                        "kind": "duplicate_route",
                        "value": r,
                        "owners": [route_owner[r], name],
                    }
                )
            else:
                route_owner[r] = name
    return conflicts


def _render_dep_graph(modules: list[dict[str, Any]]) -> str:
    """Mermaid flowchart TD。"""
    lines = [
        "# edu-cloud 模块依赖图\n",
        "> 自动生成，禁止手写。源：各模块 MODULE.md frontmatter。\n",
        "```mermaid",
        "flowchart TD",
    ]
    for m in modules:
        for dep in (m.get("depends_on") or {}).get("modules") or []:
            lines.append(f"  {m['name']} --> {dep}")
    lines.append("```\n")
    return "\n".join(lines)


def _render_debt(modules_dir: Path, covered: set[str]) -> str:
    """列出 modules/ 下缺 MODULE.md 的子目录。"""
    debt: list[str] = []
    for child in sorted(modules_dir.iterdir()):
        if (
            child.is_dir()
            and child.name != "__pycache__"
            and not child.name.startswith("_")
            and child.name not in covered
        ):
            debt.append(child.name)
    lines = [
        "# MODULE.md 债务清单\n",
        "> 自动生成。以下模块缺 MODULE.md，下次触碰时 hook 会 ask。\n",
    ]
    if not debt:
        lines.append("_无债务——所有模块已合规。_\n")
    else:
        for name in debt:
            lines.append(f"- `src/edu_cloud/modules/{name}/`")
    return "\n".join(lines) + "\n"


def aggregate_all(modules_dir: Path, out_dir: Path) -> dict[str, Any]:
    """主入口。返回统计信息 {modules, conflicts, debt}。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    modules: list[dict[str, Any]] = []
    covered: set[str] = set()
    for child in sorted(modules_dir.iterdir()):
        if (
            not child.is_dir()
            or child.name.startswith("_")
            or child.name == "__pycache__"
        ):
            continue
        md = child / "MODULE.md"
        if md.exists():
            meta = parse_module_md(md)
            modules.append(meta)
            covered.add(meta["name"])
    conflicts = detect_conflicts(modules)

    (out_dir / "modules.yaml").write_text(
        yaml.safe_dump(
            {"modules": modules, "conflicts": conflicts},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (out_dir / "dependency-graph.md").write_text(
        _render_dep_graph(modules), encoding="utf-8"
    )
    (out_dir / "debt-report.md").write_text(
        _render_debt(modules_dir, covered), encoding="utf-8"
    )
    total = len([c for c in modules_dir.iterdir() if c.is_dir() and c.name != "__pycache__" and not c.name.startswith("_")])
    return {
        "modules": len(modules),
        "conflicts": len(conflicts),
        "debt": total - len(covered),
    }


def _main() -> int:
    """CLI 入口。"""
    repo = Path(__file__).resolve().parents[2]
    try:
        cwd = Path.cwd()
        candidate_modules = cwd / "src" / "edu_cloud" / "modules"
        candidate_out = cwd / "docs" / "governance"
        if candidate_modules.exists() and candidate_out.exists():
            modules_dir = candidate_modules
            out_dir = candidate_out
        else:
            modules_dir = repo / "src" / "edu_cloud" / "modules"
            out_dir = repo / "docs" / "governance"
        stats = aggregate_all(modules_dir, out_dir)
    except ModuleGovernanceError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(f"Aggregated: {stats}")
    return 1 if stats["conflicts"] > 0 else 0


if __name__ == "__main__":
    sys.exit(_main())
