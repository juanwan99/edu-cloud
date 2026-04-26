<!-- legacy-format -->
# T-H ECS pytest 环境装配 · 2026-04-18

> 类型：Executor session（环境装配 + 验证 + 文档）
> 创建：2026-04-18 09:57:00 由 Planner (Opus 4.7 1M)
> 工作目录：`/home/ops/projects/edu-cloud-t2`（master @ `d9a842e`）
> 优先级：**P0**（T-E audit 报告 §6 论证 — T-G/T-F 价值依赖能跑 pytest 验证）
> 估时：1-3h（核心 1h + 排查 + 文档 1-2h）

---

## §1. 任务背景（基于事实）

| 现象 | 证据 | 影响 |
|---|---|---|
| ECS python3 无 pytest | `/usr/bin/python3 --version` = 3.10.12；`python3 -m pytest` = `No module named pytest` | 7 轮 reviewer 没在 ECS 实跑的根因 |
| 系统 python 版本不够 | 系统 3.10 vs `pyproject.toml requires-python = ">=3.11"` | 必须 uv 自己装 Python 3.11+ |
| uv 已装 + uv.lock 存在 | `which uv` = `/home/ops/.local/bin/uv 0.11.6`；`ls uv.lock` 存在 | **可走 `uv sync` lockfile 一键复现** |
| audit 数字漂移悬而未决 | T-E §3.2：grep 68 函数 vs Windows plan 118 passed | 真伪需 pytest 实跑（含 parametrize 展开后真实 case 数） |

**任务目标**：让 ECS 上能 `python3 -m pytest`（含 conduct/menu/alembic/grading 全模块），跑出 baseline 真实 passed 数，为 T-G hook + T-F plan 清洗 + 后续所有 reviewer 实跑提供基础设施。

---

## §2. 范围

**In scope**：
- 在 `/home/ops/projects/edu-cloud-t2`（master）下用 `uv` 装 venv + 全部依赖（含 dev）
- 验证至少 **5 个测试模块**能 collect + run（conduct / menu / alembic / grading / services）
- 实跑 conduct 模块得真实 passed 数（验证 grep 68 与 pytest passed 的差异）
- 写 setup script `scripts/setup_ecs_dev.sh`（可复现，未来跨机器一键）
- 写 `docs/dev/ecs-pytest-setup.md` 文档（含已知坑位 + 排查指南）
- 输出 baseline 实跑报告 `docs/plans/2026-04-18-ecs-pytest-baseline-report.md`

**Out of scope**（移交后续任务）：
- 修业务代码（src/ frontend/）→ 不涉及
- 修 plan baseline 数字 → T-F 任务
- 写 plan_baseline_guard hook → T-G 任务
- 跑前端 vitest（前端已有 node_modules 可跑，不属本任务）
- 装 playwright Chromium 浏览器（>500MB，按需后置）

---

## §3. 红线

- **不污染系统 python**：禁 `sudo apt install python3-*`，全走 uv venv
- **不 commit `.venv/` 或 `uv` 缓存**：检查 `.gitignore` 已含 `.venv`，未含则补
- **不动 `src/` `frontend/` `alembic/` `tests/` 业务代码**
- **不动 `docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md`** 等 baseline 数字（T-F 的事）
- **不动 W4-R8 / T-D handoff**（同 T-E 红线）
- **playwright Chromium 装载阻塞**：若 `uv sync` 失败仅因 playwright，可 `--no-extra dev` 装核心，dev deps 单独排查
- **pyzbar/lxml/opencv 系统库依赖**：若 import 失败，**先记录到 setup script 的 `apt install` 段**给用户审批，不擅自 sudo
- **完成声明前必须有测试输出**（Stop hook 强制）

---

## §4. 关键证据起点

| 项 | 命令 / 路径 |
|---|---|
| pyproject.toml | `/home/ops/projects/edu-cloud-t2/pyproject.toml`（核心 23 deps + dev 4 deps） |
| uv.lock | `/home/ops/projects/edu-cloud-t2/uv.lock`（lockfile） |
| 当前 master HEAD | `d9a842e docs: T-E Takeover Audit Report 落地` |
| audit 报告 | `docs/plans/2026-04-18-takeover-impact-audit-report.md` |
| 重点测试模块 | `tests/test_conduct/`（68 grep）/ `tests/test_menu/`（9 grep）/ `tests/test_alembic_migration.py`（3 grep）/ `tests/test_services_exam/test_objective_grading.py`（10 grep） |

---

## §5. 步骤

### Phase 1：核心装配（30-60min）

1. **侦查**
   ```
   ls .gitignore | xargs grep -E "^\.venv|^venv" || echo "需补 .venv"
   uv --version
   cat pyproject.toml | head -50
   ```
2. **装 Python 3.11 via uv**
   ```
   uv python install 3.11
   uv python list | grep 3.11
   ```
3. **创建 venv + sync 依赖**（用 lockfile 保证复现）
   ```
   uv venv --python 3.11
   uv sync --extra dev   # 含 pytest + pytest-asyncio + ruff（playwright 可能需 --no-extra dev 二次试）
   source .venv/bin/activate
   python -m pytest --version
   ```
4. **首次 collect-only 验证**
   ```
   python -m pytest --collect-only -q 2>&1 | tail -20
   # 期望：报告 "X tests collected"，无 ImportError
   ```
5. **若 pyzbar/lxml ImportError**：在 setup script 中记录所需 `apt install` 包（libzbar0 / libxml2 / libxslt1.1 / libjpeg62 等），**不擅自 sudo**，给用户审批

### Phase 2：baseline 实跑（30-60min）

6. **跑 conduct 模块**（解决 T-E §3.2 的 grep 68 vs plan 118 真伪）
   ```
   python -m pytest tests/test_conduct/ -q --tb=short 2>&1 | tail -30
   # 期望：得到真实 "X passed"，对账 grep 函数数 + parametrize 展开
   ```
7. **跑其他 5 个 audit 表中的模块**
   ```
   python -m pytest tests/test_menu/ tests/test_alembic_migration.py tests/test_services_exam/test_objective_grading.py tests/test_services/test_school_settings_service.py tests/test_services/test_homework_permissions.py -q 2>&1 | tail -30
   ```
8. **跑全量**（容许部分 fail，目标是 collect 数 + 主体 pass 数）
   ```
   python -m pytest -q --tb=no 2>&1 | tail -10
   ```

### Phase 3：交付物（30min）

9. **写 setup script** `scripts/setup_ecs_dev.sh`
   - shebang + set -euo pipefail
   - 检查 uv / Python 3.11 / sync / 验证 pytest --version
   - apt install 段（如 Phase 1 step 5 触发）注释化，require user audit
10. **写文档** `docs/dev/ecs-pytest-setup.md`
    - 前置依赖（uv 已装）
    - 一键命令
    - 常见坑位（pyzbar/lxml/playwright Chromium）
    - 与 Windows 环境的差异点
11. **写 baseline report** `docs/plans/2026-04-18-ecs-pytest-baseline-report.md`
    - audit 表 §3.2 重跑：grep 函数数 vs pytest passed 数对账
    - conduct 模块真实 passed 数（订正 W4-R8 「50 测试遗失」假设的最终数字）
    - 全量 collect 数 + 主体 pass/fail/skip 分布
12. **commit**（拆 2 commit）
    - `chore: ECS pytest 环境装配 (uv venv + setup script + doc)`
    - `docs: ECS pytest baseline 实跑报告（订正 grep 函数数 → pytest passed 数）`

---

## §6. 完成定义 (DoD)

- `.venv/` 装好，`source .venv/bin/activate && python -m pytest --version` 输出版本号
- `python -m pytest --collect-only -q` 报告 collected 数无 ImportError
- conduct 模块跑出真实 passed 数（精确数字，不是估计）
- `scripts/setup_ecs_dev.sh` 可执行，含必要 apt 包审批段
- `docs/dev/ecs-pytest-setup.md` 落地（≥ 5 段：前置/一键/坑位/差异/排查）
- `docs/plans/2026-04-18-ecs-pytest-baseline-report.md` 落地（含 §3.2 重跑表 + W4-R8 数字订正）
- `.gitignore` 含 `.venv`（如缺则补）
- 2 commit 落地（`chore:` + `docs:`），Stop hook 通过

---

## §7. Followup 触发（不在本任务 scope）

完成后通知 Planner，预期触发：
- **T-G hook 启动**（plan_baseline_guard）：现在有 pytest 验证基础，hook 的"X passed"机器校验有意义
- **T-F plan 清洗 启动**：用本任务 baseline report 数字订正 6 plan + CLAUDE.md
- **W4-R8 重启 / 整合**：用真实 conduct passed 数订正 "50 测试遗失"假设
- **A 类 50 测试处置决策**（A1/A2/A3）：用户基于 pytest 实测后再定

---

## §8. 启动 prompt（直接复制）

```
[edu-cloud] Executor | 2026-04-18 09:57:00 | T-H ECS pytest 环境装配
工作目录: /home/ops/projects/edu-cloud-t2 (master @ d9a842e)

读取交接卡: docs/plans/2026-04-18-ecs-pytest-setup-handoff.md
全文阅读后按 §5 Phase 1-3 步骤推进，达成 §6 DoD。

红线 (§3):
- 禁 sudo / 禁污染系统 python，全走 uv venv
- 禁动业务代码 (src/ frontend/) 与 plan baseline 数字
- 禁动 W4-R8 / T-D handoff
- 装包失败先记 apt 包到 setup script 给用户审批，不擅自 sudo
- 完成声明前必须有 pytest 实跑输出

完成后用 SendMessage 通知 Planner 实测 conduct passed 数 + baseline report 路径。
基于事实 + pytest 输出，禁猜测。L013/L015 严守。
```
