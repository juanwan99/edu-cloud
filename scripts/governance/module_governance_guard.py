#!/usr/bin/env python3
"""module_governance_guard — edu-cloud 模块治理（MODULE.md / owns 冲突检测）。"""
from __future__ import annotations

ENFORCES = ["WF-016", "WF-018"]

import argparse
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

MODULES_DIR = "src/edu_cloud/modules"
SERVICES_DIR = "src/edu_cloud/services"
OWNS_SERVICES_FIELD = "owns_services"
LARGE_MODIFY_THRESHOLD = 50
EDU_CLOUD_MARKER = "edu-cloud"


def _kill_switch() -> bool:
    return os.environ.get("EDU_GOVERNANCE_GUARD_DISABLED") == "1"


def _is_edu_cloud(cwd: str | Path) -> bool:
    p = Path(cwd)
    return p.name == EDU_CLOUD_MARKER or (p / "src" / "edu_cloud").exists()


def _module_name_from_path(path: str) -> str | None:
    normalized = Path(path).as_posix().split("/")
    if len(normalized) < 5:
        return None
    if "/".join(normalized[:3]) != MODULES_DIR:
        return None
    return normalized[3]


def _dir_exists_in_head(repo: Path, rel_dir: str) -> bool:
    """git ls-tree -d HEAD <rel_dir>：HEAD 含该目录返回 True。"""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "ls-tree", "-d", "HEAD", rel_dir],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False  # 无 HEAD（首次 commit）→ 按"新建"保守判定


def _is_git_worktree(repo: Path) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _checkout_staged_index(repo: Path, tmp_path: Path) -> bool:
    """将 staged index 导出到 tmp_path；失败必须由调用方阻断。"""
    try:
        # R2-NEW-01: 非 git 工作树先显式 fail；兼容 .git 为文件的 worktree。
        if not _is_git_worktree(repo):
            return False

        prefix = str(tmp_path).replace(os.sep, "/")
        if not prefix.endswith("/"):
            prefix += "/"
        subprocess.run(
            ["git", "-C", str(repo), "checkout-index", "--all", "--prefix", prefix],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def parse_diff_line_counts(diff: str) -> dict[str, dict[str, int]]:
    """解析 unified diff，返回 {path: {"added": n, "deleted": n}}。"""
    result: dict[str, dict[str, int]] = {}
    current: str | None = None
    DIFF_HEADER_RE = re.compile(r"^diff --git a/(.*?) b/(.*)$")
    for line in diff.splitlines():
        m = DIFF_HEADER_RE.match(line)
        if m:
            current = m.group(2).strip()
            result.setdefault(current, {"added": 0, "deleted": 0})
            continue
        if current is None:
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            result[current]["added"] += 1
        elif line.startswith("-"):
            result[current]["deleted"] += 1
    return result


def _import_aggregate_module(repo: Path):
    """导入 aggregate_modules（共享 parse_module_md 契约）。失败 raise。"""
    candidates = [
        repo / "scripts" / "governance" / "aggregate_modules.py",
        Path(__file__).resolve().parent / "aggregate_modules.py",
    ]
    for path in candidates:
        if not path.exists():
            continue
        module_name = f"_edu_cloud_aggregate_modules_{abs(hash(path.resolve()))}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    raise ModuleNotFoundError(
        "aggregate_modules.py not found in repo or scripts/governance"
    )


def check_new_module(
    files: list[str], repo: Path, real_repo: Path | None = None
) -> dict | None:
    """新建模块必须附合法 MODULE.md（staged 证据），否则 block。"""
    if _kill_switch():
        return None
    real_repo = real_repo or repo
    touched: dict[str, str | None] = {}  # module_name -> staged MODULE.md 路径 or None
    for p in files:
        mod = _module_name_from_path(p)
        if mod is None:
            continue
        touched.setdefault(mod, None)
        if p.replace("\\", "/").endswith(f"modules/{mod}/MODULE.md"):
            touched[mod] = p
    blocking_missing: list[str] = []
    blocking_invalid: list[str] = []
    # F008: MODULE.md frontmatter 校验需要 aggregate 模块（工具从 real_repo 导入）
    try:
        agg = _import_aggregate_module(real_repo)
    except Exception as e:
        if any(touched.get(m) for m in touched):
            return {
                "decision": "block",
                "reason": f"无法加载 aggregate_modules 校验 MODULE.md frontmatter: {e}",
            }
        agg = None
    for mod, md_rel in touched.items():
        if _dir_exists_in_head(real_repo, f"{MODULES_DIR}/{mod}"):
            continue  # 存量模块走 check_touched_legacy
        if md_rel is None:
            blocking_missing.append(mod)
            continue
        # F008 + G2-01: 校验 staged MODULE.md 内容合法（从 snapshot 读 staged 副本）
        if agg is not None:
            md_abs = repo / md_rel
            if not md_abs.exists():
                # staged 声明含该 MODULE.md 但 snapshot 未包含 → missing（异常边界）
                blocking_missing.append(mod)
                continue
            try:
                agg.parse_module_md(md_abs)
            except Exception as e:
                blocking_invalid.append(f"{mod}: {e}")
    if blocking_missing or blocking_invalid:
        parts: list[str] = []
        if blocking_missing:
            parts.append(
                f"新建模块缺 MODULE.md (staged 未包含): {blocking_missing}。"
                "请按 docs/governance/MODULE-template.md 创建并 `git add`。"
            )
        if blocking_invalid:
            parts.append(
                "新建模块 MODULE.md frontmatter 非法:\n  - "
                + "\n  - ".join(blocking_invalid)
            )
        return {"decision": "block", "reason": "\n".join(parts)}
    return None


def check_ownership_conflicts(modules: list[dict[str, Any]]) -> dict | None:
    if _kill_switch():
        return None
    table_owner: dict[str, str] = {}
    route_owner: dict[str, str] = {}
    service_owner: dict[str, str] = {}
    conflicts: list[str] = []
    for m in modules:
        name = m.get("name", "?")
        for t in m.get("owns_tables") or []:
            prev = table_owner.get(t)
            if prev is not None and prev != name:
                conflicts.append(f"table '{t}': {prev} vs {name}")
            else:
                table_owner[t] = name
        for r in m.get("owns_routes") or []:
            prev = route_owner.get(r)
            if prev is not None and prev != name:
                conflicts.append(f"route '{r}': {prev} vs {name}")
            else:
                route_owner[r] = name
        for raw_service in m.get(OWNS_SERVICES_FIELD) or []:
            service = _normalize_owned_service_path(raw_service) or str(raw_service)
            prev = service_owner.get(service)
            if prev is not None and prev != name:
                conflicts.append(f"service '{service}': {prev} vs {name}")
            else:
                service_owner[service] = name
    if conflicts:
        return {
            "decision": "block",
            "reason": "owns_* 跨模块冲突（违反 L015 单一所有权）:\n  - "
            + "\n  - ".join(conflicts),
        }
    return None


def _normalize_owned_service_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    service = value.strip().replace("\\", "/")
    while service.startswith("./"):
        service = service[2:]
    if service.startswith("edu_cloud/services/"):
        service = f"src/{service}"
    elif service.startswith("services/"):
        service = f"{SERVICES_DIR}/{service[len('services/'):]}"
    elif "/" not in service:
        if service.startswith("edu_cloud.services."):
            service = service[len("edu_cloud.services.") :]
        elif service.startswith("services."):
            service = service[len("services.") :]
        service = service.replace(".", "/")
        if not service.endswith(".py"):
            service = f"{service}.py"
        service = f"{SERVICES_DIR}/{service}"
    elif not service.endswith(".py"):
        service = f"{service}.py"
    if not service.startswith(f"{SERVICES_DIR}/"):
        return None
    return service


def _workflow_service_files(repo: Path) -> list[str]:
    services_dir = repo / SERVICES_DIR
    if not services_dir.exists():
        return []
    return sorted(
        path.relative_to(repo).as_posix()
        for path in services_dir.rglob("*_workflow.py")
        if path.is_file()
    )


def _service_ownership_map(
    modules: list[dict[str, Any]],
) -> tuple[dict[str, list[str]], list[str]]:
    owners: dict[str, list[str]] = {}
    invalid: list[str] = []
    for module in modules:
        module_name = str(module.get("name") or "?")
        raw_services = module.get(OWNS_SERVICES_FIELD) or []
        if not isinstance(raw_services, list):
            invalid.append(f"{module_name}: {OWNS_SERVICES_FIELD} must be a list")
            continue
        for raw_service in raw_services:
            service = _normalize_owned_service_path(raw_service)
            if service is None:
                invalid.append(
                    f"{module_name}: invalid {OWNS_SERVICES_FIELD} entry {raw_service!r}"
                )
                continue
            owners.setdefault(service, []).append(module_name)
    return owners, invalid


def check_workflow_service_ownership(
    repo: Path, modules: list[dict[str, Any]] | None = None
) -> dict | None:
    if _kill_switch():
        return None
    workflow_files = _workflow_service_files(repo)
    if not workflow_files:
        return None
    if modules is None:
        try:
            modules = _load_all_module_frontmatters(repo)
        except _LoaderError as e:
            return {
                "decision": "block",
                "reason": (
                    "MODULE.md 解析失败，无法执行 workflow ownership 检测: "
                    f"{e}"
                ),
            }

    owners, invalid = _service_ownership_map(modules)
    missing = [path for path in workflow_files if len(owners.get(path, [])) == 0]
    duplicate = [
        f"{path}: {', '.join(owner_names)}"
        for path, owner_names in sorted(owners.items())
        if path in workflow_files and len(owner_names) > 1
    ]
    stale = [
        path
        for path in sorted(owners)
        if path.endswith("_workflow.py") and path not in workflow_files
    ]
    if not (invalid or missing or duplicate or stale):
        return None

    sections: list[str] = []
    if invalid:
        sections.append("invalid owns_services:\n  - " + "\n  - ".join(invalid))
    if missing:
        sections.append("missing workflow owner:\n  - " + "\n  - ".join(missing))
    if duplicate:
        sections.append("duplicate workflow owner:\n  - " + "\n  - ".join(duplicate))
    if stale:
        sections.append(
            "stale workflow owner declaration:\n  - " + "\n  - ".join(stale)
        )
    return {
        "decision": "block",
        "reason": (
            "workflow service ownership must be exactly one module owner per "
            "*_workflow.py\n"
            + "\n".join(sections)
        ),
    }


def check_touched_legacy(
    files: list[str], diff: str, repo: Path, real_repo: Path | None = None
) -> dict | None:
    """存量模块大幅改动（>=50 行）缺 MODULE.md 时 block。"""
    if _kill_switch():
        return None
    real_repo = real_repo or repo
    line_counts = parse_diff_line_counts(diff)
    per_module: dict[str, int] = {}
    for p in files:
        mod = _module_name_from_path(p)
        if mod is None:
            continue
        counts = line_counts.get(p, {"added": 0, "deleted": 0})
        per_module[mod] = per_module.get(mod, 0) + counts["added"] + counts["deleted"]
    asks: list[str] = []
    for mod, lines in per_module.items():
        if lines < LARGE_MODIFY_THRESHOLD:
            continue
        rel = f"{MODULES_DIR}/{mod}"
        if not _dir_exists_in_head(real_repo, rel):
            continue  # 新模块走 check_new_module
        # F007 + G2-01: 存量模块 MODULE.md 存在性以 staged snapshot 为准
        if not (repo / rel / "MODULE.md").exists():
            asks.append(f"{mod} ({lines} 行触碰)")
    if asks:
        return {
            "decision": "block",
            "reason": (
                f"触碰存量模块 ≥{LARGE_MODIFY_THRESHOLD} 行但缺 MODULE.md:\n  - "
                + "\n  - ".join(asks)
                + "\n请先补齐 MODULE.md 再 commit。(Boy Scout 自愈式收敛)"
            ),
        }
    return None


class _LoaderError(RuntimeError):
    """F008: aggregate loader 失败必须向上抛，不得静默。"""


def _load_all_module_frontmatters(repo: Path) -> list[dict[str, Any]]:
    """读所有 MODULE.md frontmatter。任一失败 → raise _LoaderError。"""
    modules_dir = repo / MODULES_DIR
    if not modules_dir.exists():
        return []
    md_files = [
        child / "MODULE.md"
        for child in sorted(modules_dir.iterdir())
        if child.is_dir()
        and not child.name.startswith("_")
        and child.name != "__pycache__"
        and (child / "MODULE.md").exists()
    ]
    if not md_files:
        return []
    try:
        agg = _import_aggregate_module(repo)
    except Exception as e:
        raise _LoaderError(f"aggregate_modules 不可导入: {e}") from e
    result: list[dict[str, Any]] = []
    for md in md_files:
        try:
            result.append(agg.parse_module_md(md))
        except Exception as e:
            raise _LoaderError(f"{md.relative_to(repo)}: {e}") from e
    return result


def check_derived_products_fresh(
    repo: Path, files: list[str], real_repo: Path | None = None
) -> dict | None:
    """派生产物（modules.yaml 等）与 MODULE.md 不同步时 block。"""
    if _kill_switch():
        return None
    real_repo = real_repo or repo
    trigger = any(
        p.replace("\\", "/").startswith(MODULES_DIR + "/")
        or p.replace("\\", "/").endswith("MODULE.md")
        for p in files
    )
    if not trigger:
        return None
    try:
        agg = _import_aggregate_module(real_repo)
    except Exception as e:
        return {
            "decision": "block",
            "reason": f"aggregate_modules 不可用，无法校验派生产物 freshness: {e}",
        }
    out_dir = repo / "docs" / "governance"
    if not out_dir.exists():
        return {
            "decision": "block",
            "reason": "docs/governance 不存在，无法校验派生产物 freshness。",
        }
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            agg.aggregate_all(repo / MODULES_DIR, tmp_path)
        except Exception as e:
            return {
                "decision": "block",
                "reason": f"派生产物重算失败，无法证明 freshness: {e}",
            }
        stale: list[str] = []
        for name in ("modules.yaml", "dependency-graph.md", "debt-report.md"):
            fresh = (
                (tmp_path / name).read_text(encoding="utf-8")
                if (tmp_path / name).exists()
                else ""
            )
            ondisk = (
                (out_dir / name).read_text(encoding="utf-8")
                if (out_dir / name).exists()
                else ""
            )
            if fresh != ondisk:
                stale.append(name)
        if stale:
            return {
                "decision": "block",
                "reason": (
                    f"派生产物过期 (违反设计 §3.1 单一真源): {stale}\n"
                    "请执行:\n"
                    "  python scripts/governance/aggregate_modules.py\n"
                    f"  git add docs/governance/{{{','.join(stale)}}}\n"
                    "然后重试 commit。"
                ),
            }
    return None


def check_parallel_dir(files: list[str], cwd: str) -> dict | None:
    """平行目录检测（原 parallel_dir_guard.py 合并）。
    staged files 新建顶层目录且目录名与已有目录共享词根时 block。
    """
    if not files:
        return None
    try:
        result = subprocess.run(
            ["git", "ls-tree", "--name-only", "-d", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        existing_dirs = set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()
    except Exception:
        return None
    if not existing_dirs:
        return None

    existing_roots: dict[str, list[str]] = {}
    for d in existing_dirs:
        root = d.split("-")[0].split("_")[0].lower()
        existing_roots.setdefault(root, []).append(d)

    for f in files:
        parts = f.split("/")
        if len(parts) >= 2:
            top = parts[0]
            if top not in existing_dirs:
                root = top.split("-")[0].split("_")[0].lower()
                if root in existing_roots:
                    matches = existing_roots[root]
                    return {
                        "decision": "block",
                        "reason": (
                            f"🚨 PARALLEL DIRECTORY DETECTED\n\n"
                            f"新建目录 `{top}/` 与已有 `{matches[0]}/` 共享词根。\n"
                            f"这可能是创建平行系统 — 多版本并存严令禁止（frontend-nuxt 教训: -15035 行）。\n\n"
                            f"📋 如果确实需要创建此目录，告知用户并获取确认。"
                        ),
                    }
    return None


def check(data: dict, session_state, staged_info: dict | None = None) -> dict | None:
    """hook 入口：基于 staged snapshot 执行模块治理检查。"""
    if _kill_switch():
        return None
    cwd = data.get("cwd", ".")
    command = (data.get("tool_input") or {}).get("command", "")
    if "git commit" not in command:
        return None

    staged_info = staged_info or {}
    files: list[str] = [f for f in (staged_info.get("files") or []) if f]
    diff: str = staged_info.get("diff") or ""

    # 平行目录检测（对所有项目生效，不限 edu-cloud）
    parallel_result = check_parallel_dir(files, cwd)
    if parallel_result is not None:
        return parallel_result

    if not _is_edu_cloud(cwd):
        return None

    real_repo = Path(cwd)

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp)
        if not _checkout_staged_index(real_repo, snap):
            return {
                "decision": "block",
                "reason": "无法导出 staged index，拒绝改用工作区证据执行模块治理检查。",
            }

        try:
            all_modules = _load_all_module_frontmatters(snap)
        except _LoaderError as e:
            return {
                "decision": "block",
                "reason": f"MODULE.md 解析失败，无法执行 owns 冲突检测: {e}",
            }

        for check_fn in (
            lambda: check_new_module(files, snap, real_repo=real_repo),
            lambda: check_ownership_conflicts(all_modules),
            lambda: check_workflow_service_ownership(snap, all_modules),
            lambda: check_derived_products_fresh(snap, files, real_repo=real_repo),
            lambda: check_touched_legacy(files, diff, snap, real_repo=real_repo),
        ):
            result = check_fn()
            if result is not None:
                return result
    return None


def _resolve_repo(path: str) -> Path:
    repo = Path(path).resolve()
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip()).resolve()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return repo
    return repo


def _git_text(repo: Path, args: list[str]) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        if r.returncode != 0:
            return ""
        return r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _staged_info_from_git(repo: Path) -> dict[str, Any]:
    names = _git_text(
        repo, ["diff", "--cached", "--name-only", "--diff-filter=ACMRT"]
    )
    diff = _git_text(repo, ["diff", "--cached", "-U0", "--no-ext-diff"])
    return {
        "files": [line.strip() for line in names.splitlines() if line.strip()],
        "diff": diff,
    }


def _run_git_hook_mode(repo: Path) -> int:
    staged_info = _staged_info_from_git(repo)
    data = {"cwd": str(repo), "tool_input": {"command": "git commit"}}
    result = check(data, session_state=None, staged_info=staged_info)
    if result is None:
        return 0
    print(result.get("reason") or "module governance guard blocked commit", file=sys.stderr)
    return 1


def _run_repo_mode(repo: Path) -> int:
    try:
        all_modules = _load_all_module_frontmatters(repo)
    except _LoaderError as e:
        print(f"MODULE.md parse failed: {e}", file=sys.stderr)
        return 1
    for check_fn in (
        lambda: check_ownership_conflicts(all_modules),
        lambda: check_workflow_service_ownership(repo, all_modules),
    ):
        result = check_fn()
        if result is not None:
            print(
                result.get("reason") or "module governance guard blocked repository",
                file=sys.stderr,
            )
            return 1
    print("module governance guard: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run edu-cloud module governance checks against staged files."
    )
    parser.add_argument("--repo", default=".", help="Repository path.")
    parser.add_argument(
        "--git-hook-mode",
        action="store_true",
        help="Read staged files from git and return non-zero when blocked.",
    )
    args = parser.parse_args(argv)

    repo = _resolve_repo(args.repo)
    if args.git_hook_mode:
        return _run_git_hook_mode(repo)

    return _run_repo_mode(repo)


if __name__ == "__main__":
    raise SystemExit(main())
