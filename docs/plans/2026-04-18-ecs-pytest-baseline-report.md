<!-- legacy-format -->
# ECS pytest baseline 实跑报告 · 2026-04-18

> 产出：T-H Executor session（Opus 4.7 1M）
> 环境：`/home/ops/projects/edu-cloud-t2` master @ `d806661` (HEAD 含 T-H 派发 commit)
> 任务：`docs/plans/2026-04-18-ecs-pytest-setup-handoff.md`
> 上游：`docs/plans/2026-04-18-takeover-impact-audit-report.md` §3.2 + §4
> 口径：本报告所有 "passed" 数字均为 ECS 本地 `python -m pytest` 实跑结果。

---

## §1. 环境指纹

| 项 | 值 |
|---|---|
| OS | Linux 5.15.0-173-generic（ECS Ubuntu 22.04 风格） |
| 系统 python3 | `/usr/bin/python3` → 3.10.12（未用） |
| uv | 0.11.6（`/home/ops/.local/bin/uv`） |
| uv-managed Python | cpython-3.11.15-linux-x86_64-gnu |
| .venv path | `/home/ops/projects/edu-cloud-t2/.venv` |
| pytest | 9.0.3 |
| pytest-asyncio | 1.3.0 |
| ruff | 0.15.10 |
| 工作目录 git HEAD | `d806661` |
| 装配脚本 | `scripts/setup_ecs_dev.sh`（可复现） |
| 文档 | `docs/dev/ecs-pytest-setup.md` |

装配总耗时（sync 含全部 wheel 下载）：约 3 分钟。

---

## §2. 全量跑结果

命令：
```
source .venv/bin/activate
python -m pytest -q --tb=no
```

结果：**1934 passed, 1 failed, 23 skipped, 32 warnings in 692.35s (0:11:32)**

| 指标 | 数值 |
|---|---|
| collect（由 `--collect-only` 独立确认） | **1958** |
| pass | 1934 |
| fail | 1 |
| skip | 23 |
| 1958 = pass + fail + skip | ✅ 对账 |
| 总耗时 | 692.35s |
| 主体通过率（pass/collected） | 98.78% |

**与 CLAUDE.md "后端 1896 tests, 含 conduct 106" 的差异**：ECS 实测 collect 1958（多 62），conduct 68（少 38）。CLAUDE.md 数字是**陈旧 snapshot**，建议 T-F plan 清洗任务统一订正为 ECS 实测。

---

## §3. T-E audit §3.2 六项 plan baseline 重跑（pytest 实测列）

audit §3.2 原表缺 ECS pytest 列（因 `No module named pytest`）。本节补齐。

| # | plan 来源 | plan 写 | grep 函数 | **ECS pytest passed** | 结论 |
|---|---|---:|---:|---:|---|
| 1 | `2026-04-14-conduct-roadmap-batch1-plan.md` L23 | 118 | 68 | **68** | grep = pytest；plan 118 多出的 50 是 **Windows-only 历史扩展**（W4-R8 "50 测试遗失"假设被**订正为 "50 函数从未进 git"**） |
| 2 | `2026-04-14-conduct-roadmap-batch1-plan.md` L24 | 15 | 15 | **15**（school_settings 11 + homework_permissions 4） | 三者一致 ✓ |
| 3 | `2026-04-12-haofenshu-phase1-plan.md` L489 | 9 | 9 | **9**（`tests/test_menu/`） | 三者一致 ✓ |
| 4 | `2026-04-13-migration-gate-repair-design.md` L180 | 2 | 3 | **3**（`tests/test_alembic_migration.py`） | pytest = grep = 3；plan 2 **过时+1** |
| 5 | `2026-04-12-grading-dispatch-plan.md` L181 | 10 | 10 | **10**（`tests/test_services_exam/test_objective_grading.py`） | 三者一致 ✓ |
| 6 | `2026-04-12-conduct-roadmap-batch1-plan.md` frontend 13 | 6 | N/A（vitest） | 前端 vitest，本次 scope 外 |

**关键发现**：所有 5 项 Python 测试模块 **grep 函数数 = pytest passed 数**（无 parametrize 膨胀、无 class-based 额外 case）。这与 audit §3.1 "无 parametrize 时两者 1:1" 预判一致，意味着在 edu-cloud 当前代码库**L1 grep 可作为 L2 pytest 的保守下界**（差值来自 skip，不会虚高）。

---

## §4. W4-R8 "50 测试遗失"假设订正

W4-R8 Planner 原提法（`docs/plans/2026-04-18-w4-r8-planner-handoff.md` 引）："40 测试遗失" / "约 50 测试遗失"。

audit 已订正为：Windows 118 − ECS 68 = **50 函数从未进 git**（A 类 Windows-only 扩展）。

本次 ECS pytest 实跑 conduct 模块 **68 passed**，全部进入 git 的测试函数**100% 跑通**，没有"本地存在但 pytest 跑挂"的隐藏情况。订正结论：

> **Windows 118 baseline 与 ECS 68 的差值（50）不是"pytest 选择性失败"，是"50 个测试函数从未被 commit 进 git"**。
>
> 处置决策（A1 同步 / A2 视为遗弃 / A3 订正 Windows→ECS）留给用户，建议 T-F plan 清洗任务前确认。

---

## §5. 唯一 FAIL 记录（非 ECS 环境问题，scope 外）

```
FAILED tests/test_workers/test_grading_worker.py::test_run_post_exam_pipeline_stub
```

**根因**（完整 traceback 经 `--tb=long` 复现）：

```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: subjects
[SQL: SELECT subjects.exam_id, ... FROM subjects WHERE subjects.exam_id = ? AND subjects.school_id = ?]
[parameters: ('test-exam', 'test-school')]
```

stub 测试 `test_run_post_exam_pipeline_stub` 调用 `run_post_exam_pipeline` 时连接的 SQLite 未建表。同文件其他 7 个测试（`test_process_grading_task_*` / `test_worker_settings_*`）**全绿**，所以不是 worker/模块问题而是**该 stub 测试自身 fixture 缺少 `create_all` 初始化**。

**处置**（**不在本任务 scope，仅记录**）：
- 归类：既有测试缺陷（C 类 per audit 分类）
- Windows 侧是否也 FAIL：未验证；CLAUDE.md 声称 1896 tests 但未声明全绿，不排除 Windows 侧也 FAIL 或被 skip
- 后续：留给 W4-R8 后续 plan 或 test-fixture fix ticket 处理
- 本次不动 `tests/` 任何文件（红线 §3）

---

## §6. 可复现性

任意后续 session 在 ECS 上重现本报告所有数字的命令链：

```
cd /home/ops/projects/edu-cloud-t2
bash scripts/setup_ecs_dev.sh
source .venv/bin/activate

# 全量
python -m pytest -q --tb=no   # 期望 1934 passed, 1 failed, 23 skipped

# conduct baseline
python -m pytest tests/test_conduct/ -q   # 期望 68 passed

# audit §3.2 五项复测
python -m pytest tests/test_menu/ tests/test_alembic_migration.py \
  tests/test_services_exam/test_objective_grading.py \
  tests/test_services/test_school_settings_service.py \
  tests/test_services/test_homework_permissions.py -q
# 期望 37 passed（9 + 3 + 10 + 11 + 4）
```

---

## §7. 附：uv.lock drift 修复记录

`uv sync --extra dev` 过程中检测到 `uv.lock` 与 `pyproject.toml` drift，**uv 自动补齐**：

| 变更 | 说明 |
|---|---|
| 新增 runtime `python-docx` 到 locked deps | `pyproject.toml` L28 已列 `python-docx>=1.1.0`，但旧 lockfile 未锁 |
| 新增 dev extra `playwright` 到 locked deps | `pyproject.toml` L35 已列 `playwright>=1.40`，旧 lockfile 未锁 |
| 移除 dev extra 冗余项（`aiosqlite` `httpx`）| 这两个已在 runtime deps，dev extras 多余记录 |

这是装配期**合理副产物**（lockfile 与 pyproject 对齐），与 src/ 业务代码无关。

---

## §8. 后续任务触发

完成本报告后建议 Planner 触发：

| 任务 | 依据 |
|---|---|
| **T-G hook 启动**（plan_baseline_guard）| 有 ECS pytest 验证基础后，hook 的"X passed"机器校验可本地复测 |
| **T-F plan 清洗启动** | 用本报告 §3 数字订正 6 plan + CLAUDE.md "1896 tests / 120 conduct tests" 条目 |
| **W4-R8 重启/整合** | 用 §4 结论订正 "50 测试遗失" → "50 函数从未进 git" |
| **A 类处置决策** | A1 同步 Windows 50 函数 / A2 标注遗弃 / A3 订正 Windows baseline 为 68 — 交用户 |
| **FAIL fixture 修复** | §5 `test_run_post_exam_pipeline_stub` 独立 ticket |

---

**报告基于事实 + pytest 输出，L013/L015 严守：所有"passed"数字有命令 + exit code 实证；任何未实证的估计明确标注。**
