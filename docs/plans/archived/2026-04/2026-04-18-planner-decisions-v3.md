<!-- legacy-format -->
# Planner V3 决策记录 · 2026-04-18 10:25:04

> 类型：决策落档（不是任务交接卡，是 Planner 决议日志）
> 上游：`2026-04-18-takeover-impact-audit-report.md`（T-E）+ `2026-04-18-ecs-pytest-baseline-report.md`（T-H）
> 下游：T-G / T-F / W4-R8 整合 / FAIL-fixture ticket

---

## §1. 决策 1：A 类 50 conduct 测试处置 → **A2 接受 ECS 为权威**

**裁定**：用户 2026-04-18 10:25 拍板 [1b]。

**含义**：
- ECS conduct 实测 **68 passed** 即权威 baseline
- Windows 历史 118 baseline 视为遗弃（不再追求"补回 50 函数"）
- 所有 plan / CLAUDE.md 中的 conduct 数字（118/120/108）订正为 **68**
- 不再追查 Windows worktree 状态（Windows 仓可达性不再是决策变量）

**理由**：
- A1（同步 Windows）受 Windows 仓可达性约束，不可控
- A3（双轨）增加纪律负担，长期偏离 takeover "ECS-as-authority" 决议
- A2 与 takeover 00cfc3d 决议对齐，单一权威最简

**影响 scope（待 T-F 落地）**：
- `CLAUDE.md` 「1896 tests / 120 conduct tests (108+12)」→ 「1958 collected, 1934 passed / 68 conduct」
- `docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md` 12 锚点 118→68
- `docs/plans/2026-04-13-conduct-next-phase-handoff.md` L151 120→68
- `docs/plans/2026-04-13-migration-gate-repair-design.md` L180 alembic 2→3
- 其他 100+ plan 含 `cd C:/Users/Administrator` 路径 → ECS path

---

## §2. 决策 2：下一任务启动顺序 → **T-G 优先**

**裁定**：用户 2026-04-18 10:25 拍板 [2b]。

**启动序**：
```
T-G (hook 防漂移, 2h)
   ↓
T-F (plan + CLAUDE.md 大批量清洗, 2-4h)
   ↓
W4-R8 整合（订正措辞 + 触发 T-B W4 T1-T5）
   ↓
FAIL-fixture ticket（独立小修复）
```

**理由**：
- T-G 先建护栏，T-F 清洗时新增 plan 自动被守护
- 不返工：先清洗再建 hook 会有窗口期 plan 仍可漂移

---

## §3. T-G Executor 增量输入清单（启动时必读）

**主交接卡**：`docs/plans/2026-04-18-plan-baseline-guard-handoff.md`（commit `5ec30de`，已落地）

**新增上下文（本决策记录之后产生）**：
1. **本文件**（A2 决策 + 启动序）
2. `docs/plans/2026-04-18-takeover-impact-audit-report.md`（T-E audit，C 类/A 类/D 类归类）
3. `docs/plans/2026-04-18-ecs-pytest-baseline-report.md`（T-H baseline，5/5 模块 grep=pytest 实证 → hook 可信用 grep 验证）

**hook 设计调整（基于决策上下文）**：
- A2 决策意味着 hook **block 条件 1**（含 `cd C:/Users/Administrator`）**无任何例外**
- T-H §3 表 5/5 模块 `grep "def test_" = pytest passed` → hook 可用 grep 作为 baseline 验证手段（不必依赖 pytest 实跑）
- block 条件 3（plan frontmatter 三字段）→ 增加可选字段 `baseline_method: grep|pytest`，默认 grep（轻量）

---

## §4. 跨 session 接替注释

下次 Planner 接替时（如本 session 被关闭/压缩），从此文件可恢复决策状态：
- A 类 50 测试已决：A2（不要再询问用户）
- T-G 已派发待启动（启动 prompt 见 §5）
- T-F 队列中，等 T-G 完成
- W4-R8 整合 + FAIL-fixture 在 T-F 之后

---

## §5. T-G 启动 prompt（直接复制到新 Claude Code 窗口）

```
[meta-config] Executor | 2026-04-18 10:25:04 | T-G plan_baseline_guard hook
工作目录: ~/.claude/hooks/ + /home/ops/projects/edu-cloud-t2

读取主交接卡: /home/ops/projects/edu-cloud-t2/docs/plans/2026-04-18-plan-baseline-guard-handoff.md
增量上下文必读:
- /home/ops/projects/edu-cloud-t2/docs/plans/2026-04-18-planner-decisions-v3.md (A2 决策 + hook 调整 §3)
- /home/ops/projects/edu-cloud-t2/docs/plans/2026-04-18-takeover-impact-audit-report.md (归类矩阵 §5)
- /home/ops/projects/edu-cloud-t2/docs/plans/2026-04-18-ecs-pytest-baseline-report.md (5/5 grep=pytest 实证)

按主交接卡 §6 步骤 1-7 推进，达成 §7 DoD。

红线 (主卡 §3):
- hook fail-open，禁打补丁式临时方案（用户偏好底层修复）
- update-config skill 走 ~/.claude/settings.json，禁动 local
- 不动业务代码 (src/ frontend/) 与 plan baseline 数字（T-F 的事，不是 T-G）
- A2 已定：Windows 路径无例外 block

完成后用 SendMessage 通知 Planner dry-run 冲击面（多少 plan 触发）+ 是否需立即派 T-F。
基于事实 + 实跑 dry-run 数字，禁猜测。L013/L015 严守。
```
