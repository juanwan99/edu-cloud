<!-- legacy-format -->
# Planner Session 交接卡 V2 · 2026-04-18 10:45:01

> 类型：Planner 跨 session 接替（**取代** V1 `2026-04-18-planner-session-handoff.md` §3 任务表）
> 创建：Planner (Opus 4.7 1M) 本 session 完成 T-E + T-H + T-G 派发 + 收 audit 报告 + V3 决策落档 + T-F 派发后
> 接替者：新规划窗口（Planner，不是执行窗口）

## 1. 我的角色 + 范围

- **规划窗口（Planner）**：调研事实 + 写交接卡 + 派发任务 + 监控 W/T 结果 + 决策响应
- **不动业务代码**：Executor 各自跑独立 session
- **本 session 已派 4 任务 + 收 2 完成报告 + 落 1 决策档**（详 §3）

## 2. 当前真实状态（实查 2026-04-18 10:45）

### 2.1 worktree HEAD
```
edu-cloud (W4)     793eaf2 [feat/conduct-roadmap-batch1]   ← W4-R8 已关闭，evidence 落 batch1-baseline-evidence.md
edu-cloud-t2       63d4bf3 [master]                         ← Planner 主场，T-F 待启
edu-cloud-w1       6c1ee0e [feat/card-subdir]               ← ✅ merge 完成
edu-cloud-w2       80b57fb [feat/kg-batch3b]                ← T-D 已关闭，仅派发文档落地
edu-cloud-w3       1439904 [feat/haofenshu-batch3]          ← ✅ merge 完成
```

### 2.2 master commit 链（本 session 产出）
```
63d4bf3 docs: 派发 T-F plan baseline 全局清洗交接卡（继 T-G）⭐ 本 session HEAD
5657f82 chore(T-G): 收尾 W4 R8 plan frontmatter 5 字段（Executor 漏 commit）
f614d88 docs: Planner V3 决策落档 (A2 ECS-authority + T-G 优先启动序)
15be600 docs: ECS pytest baseline 实跑报告（T-H Executor）
52bb198 chore: ECS pytest 环境装配 (uv venv + setup script + doc)
d806661 docs: 派发 T-H ECS pytest 环境装配交接卡（P0）
d9a842e docs: T-E Takeover Audit Report 落地（Researcher 产出）
5ec30de docs: 派发 T-E + T-G 交接卡
6490dea docs: V1 Planner session 跨 session 交接卡（旧）
```

### 2.3 关键基础设施变更
- **ECS pytest 已装好**：`.venv/bin/python` = 3.11.15 / pytest 9.0.3 via `uv`，`uv.lock` 已对齐
- **plan_baseline_guard hook 已注册**：`~/.claude/hooks/plan_baseline_guard.py` 339 行 + `~/.claude/settings.json` PreToolUse(Write,Edit)
- **dry-run 当前实测**：total=319 / clean=89 / block=59 / skip=171

## 3. 任务清单 V3（取代 V1 §3）

| # | 任务 | 角色 | 状态 | 产出 / 交接卡 |
|---|---|---|---|---|
| **T-E** | Takeover 影响面 audit | 研究员（只读）| ✅ 完成 | `takeover-impact-audit-report.md`（commit `d9a842e`）|
| **T-H** | ECS pytest 环境装配 | 执行员 | ✅ 完成 | `ecs-pytest-baseline-report.md` + `setup_ecs_dev.sh` + `docs/dev/ecs-pytest-setup.md`（commit `52bb198`/`15be600`）|
| **T-G** | plan_baseline_guard hook | 架构+执行 | ✅ 完成（Planner 收尾 frontmatter）| `~/.claude/hooks/plan_baseline_guard.py` + `README` + W4 R8 plan frontmatter 5 字段（commit `5657f82`）|
| **T-F** | plan baseline 全局清洗 | 执行员 | 🟡 **待启动**（启动 prompt 见 handoff §7）| `tf-plan-baseline-cleanup-handoff.md`（commit `63d4bf3`）|
| **W4-R8 整合** | W4 plan 12 锚点正文订正 | 规划+执行 | ⏳ 排队（继 T-F）| W4 worktree `feat/conduct-roadmap-batch1` 上做 |
| **FAIL fixture** | `test_run_post_exam_pipeline_stub` 缺 subjects 表 | 执行员 | ⏳ 排队（独立小修复）| baseline-report §5 |
| **T-B W4 T1-T5** | conduct-roadmap 批次 1 实施 | 执行员 | ⏳ 阻塞（等 W4-R8 PASS）| `w4-exec-T1-T5-handoff.md` |
| ~~T-D W2 race test~~ | ⏸️ 已关闭未启动 | — | 派发文档落 W2 worktree `80b57fb`，决策保留：A2 决策后 KG-phase1 收尾时再判断启动 | `w2-batch3b-iii-handoff.md` |
| ~~W4-R8 Planner~~ | ⏸️ 已关闭，evidence 已落地 | — | `batch1-baseline-evidence.md`（W4 worktree `793eaf2`），订正动作整合入 T-F |

## 4. V3 决策记录（用户 2026-04-18 10:25 拍板）

详见 `docs/plans/2026-04-18-planner-decisions-v3.md`：
- **决策 1 [1b] A2**：接受 ECS 68 为 conduct 权威 baseline，Windows 118 视遗弃；所有 plan/CLAUDE.md 数字订正为 ECS 实测
- **决策 2 [2b]**：T-G 优先 → T-F → W4-R8 整合 → FAIL fixture → T-B

## 5. 待用户操作

- **B1** W3 视觉验收 http://localhost:3100 → admin_principal_1 / 123456（W3 已 merge，视觉验收未确认）
- **启 T-F Executor session**（启动 prompt 见 `2026-04-18-tf-plan-baseline-cleanup-handoff.md` §7）

## 6. 用户偏好（V1 §6 沿用 + 本 session 强化）

| 偏好 | 应用 |
|---|---|
| 基于事实，禁猜测/印象 | 任何状态判定用 git/grep/pytest/dry-run 实证 |
| 不打补丁，底层修复 | T-H 修 reviewer 没实跑根因（装 pytest）；T-G 建 hook 防未来漂移 |
| 按建议执行 | 给推荐 + 理由，"按推荐"=接受 |
| checkpoint 式推进 | 不自标 ✓ / 不输出全绿表 / 等用户拍板才进下一项 |
| 务实统一中线 | A2 单一权威（ECS）vs A3 双轨 |

## 7. LESSONS 触发记录（本 session）

- **L013 自审盲区**：本 session 标注依据类型严守——T-H 完成时 second-source verify 跑 conduct 68 PASS，没套用 Executor 自述
- **L015 虚假完成声明**：commit 5657f82 是 T-G Executor 漏 commit 的兜底，Planner 主动 verify 发现
- **L017 局部最优**：Researcher T-E 报告倒置 Planner V2 优先级（T-H P0 而非 T-E→T-F→T-B），Planner 接受（不是机械同步，是逻辑成立）

## 8. 工具/环境约束（实查 2026-04-18）

- **projectctl 缺失**：`~/.claude/scripts/projectctl.py` 不存在 → 全部 legacy-format
- **ECS python**：`.venv/bin/python` 3.11.15（uv-managed）；系统 `/usr/bin/python3` 3.10.12（不要用）
- **pytest 命令**：必须 `source .venv/bin/activate` 后 `python -m pytest`
- **plan_baseline_guard hook**：所有 docs/plans/*.md 写入触发；A2 已定 → Windows 路径无例外 block；handoff 文件 + legacy-format marker + codex raw log 自动 skip
- **doc_sync_guard hook**：commit 含"关键变更"时强制 CLAUDE.md staged
- **handoff_format_guard hook**：legacy-format 标记可绕过 30 行硬限；启动 prompt 必须含 `YYYY-MM-DD HH:MM:SS`
- **stop hook**：完成声明前必须有本地测试 exit 0；推荐快测 `pytest tests/test_alembic_migration.py -q`（3 函数 5s）

## 9. 已知陷阱（V1 §9 沿用 + 本 session 新增）

- **W4 R8 plan frontmatter `baseline_count: 118`**：T-G 收尾时填的是 Windows-era 值（已带 baseline_note 记录 ECS=68 + A2 决策），T-F 同步正文订正为 68
- **历史时序段保留**：plan 中如有 R3 handoff "Windows R3 baseline 是 118" 段属历史快照，T-F 不订正，加 `<!-- historical -->` 注释
- **codex raw log (`.codex-raw-*`) 跳过**：T-F 不动 GPT 原文
- **`tests/test_workers/test_grading_worker.py::test_run_post_exam_pipeline_stub` FAIL**：fixture 缺 `create_all`（既有缺陷，FAIL fixture ticket 处理）
- **W4 worktree 上 plan**：T-F 在 master，**禁碰 W4 worktree feat/conduct-roadmap-batch1 上的 plan**（W4-R8 整合时再说）
- **test_output/tql_yuwen_a3.pdf 飘动**：3 worktree 都有，gitignored 但 tracked，可忽略

## 10. 跨 session 接替 prompt（直接复制）

```
继续 edu-cloud 规划窗口（Planner）工作。

工作目录：/home/ops/projects/edu-cloud-t2（master @ 63d4bf3）
依据交接卡：docs/plans/2026-04-18-planner-session-handoff-v2.md
取代旧卡：docs/plans/2026-04-18-planner-session-handoff.md §3 任务表已过时

第一步：
1. cd /home/ops/projects/edu-cloud-t2
2. git log --oneline -10 verify HEAD = 63d4bf3
3. git worktree list verify 5 worktree
4. 读 V2 §2 真实状态 + §3 任务清单 V3 + §4 V3 决策 + §6 用户偏好 + §9 已知陷阱
5. 询问用户：T-F 是否已启动 Executor session？或有新输入？

不擅自跑 executor 工作。基于事实禁猜测。L013/L015/L017 严守。
```

## 11. 文件索引（本 session 产出 + 引用）

本 session 产出（master 上）：
| 文件 | 用途 | commit |
|---|---|---|
| `2026-04-18-takeover-audit-handoff.md` | T-E 派发 | `5ec30de` |
| `2026-04-18-takeover-impact-audit-report.md` | T-E 完成报告 | `d9a842e` |
| `2026-04-18-ecs-pytest-setup-handoff.md` | T-H 派发 | `d806661` |
| `2026-04-18-ecs-pytest-baseline-report.md` | T-H 完成报告 | `15be600` |
| `2026-04-18-plan-baseline-guard-handoff.md` | T-G 派发 | `5ec30de` |
| `2026-04-18-planner-decisions-v3.md` | A2 + 启动序决策档 | `f614d88` |
| `2026-04-18-tf-plan-baseline-cleanup-handoff.md` | T-F 派发 | `63d4bf3` |
| `2026-04-18-planner-session-handoff-v2.md` | **本卡（V2 跨 session 交接）** | 待 commit |

非交接卡产出（外部位置）：
| 文件 | 位置 | 用途 |
|---|---|---|
| `plan_baseline_guard.py` | `~/.claude/hooks/` | T-G hook 文件（339 行）|
| `README-plan-baseline-guard.md` | `~/.claude/hooks/` | T-G 文档（143 行）|
| `setup_ecs_dev.sh` | `scripts/` | T-H 装配脚本 |
| `ecs-pytest-setup.md` | `docs/dev/` | T-H 文档 |
| `.venv/` | 项目根 | T-H ECS pytest 虚拟环境（gitignored）|
