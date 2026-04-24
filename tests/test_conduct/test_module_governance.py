"""conduct MODULE.md 治理契约测试。"""
from pathlib import Path

import yaml


MODULE_MD = (
    Path(__file__).resolve().parents[2]
    / "src" / "edu_cloud" / "modules" / "conduct" / "MODULE.md"
)


def _load_frontmatter() -> dict:
    text = MODULE_MD.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "MODULE.md must start with YAML frontmatter"
    _, fm, _ = text.split("---\n", 2)
    return yaml.safe_load(fm)


def test_module_md_exists():
    assert MODULE_MD.exists(), f"MODULE.md missing: {MODULE_MD}"


def test_owns_tables_matches_orm_definitions():
    from edu_cloud.modules.conduct import models

    orm_tables = {
        cls.__tablename__
        for cls in vars(models).values()
        if isinstance(cls, type) and hasattr(cls, "__tablename__")
    }
    fm = _load_frontmatter()
    declared = set(fm.get("owns_tables") or [])
    assert declared == orm_tables, (
        f"owns_tables drift: declared={declared} actual={orm_tables}"
    )


def test_exposes_ai_tools_matches_registry():
    import edu_cloud.ai.tools  # noqa: F401
    from edu_cloud.ai.registry import tools

    actual = {
        spec.name for spec in tools.get_all_specs()
        if spec.module_code == "conduct"
    }
    fm = _load_frontmatter()
    declared = set((fm.get("depends_on") or {}).get("ai_tools") or [])
    assert declared == actual, (
        f"ai_tools drift: declared={declared} actual={actual}"
    )
