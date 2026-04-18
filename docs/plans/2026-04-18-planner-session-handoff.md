<!-- legacy-format -->
# Planner Session 交接卡 · 2026-04-18

> 类型：规划窗口（Planner）跨 session 交接
> 创建：2026-04-18 由 Opus 4.7 (1M) Planner session 写
> 接替者：新规划窗口（不是执行窗口！4 W executor session 都在独立 worktree 跑）
> 工具约束：projectctl 缺失（`~/.claude/scripts/projectctl.py` 不存在），所有 handoff 用 `<!-- legacy-format -->` 合规路径

## 1. 我的角色 + 范围
- **规划窗口（Planner）**：调研事实 + 写交接卡 + 派发任务 + 监控 W 结果 + 决策响应
- **不动业务代码**：4 W 各自在独立 worktree 跑 executor session，本 session 仅写 docs/plans/* 交接卡
- **本 session 已派 5 个任务**（详 §3）

## 2. 当前真实状态（实查 2026-04-18，依据：git worktree list + git log）

### 2.1 worktree 与 HEAD
```
edu-cloud (主)     793eaf2 [feat/conduct-roadmap-batch1]   ← W4 (R7 PASS 是伪基线，已派 R8 Planner)
edu-cloud-t2       b0e951c [master]                         ← Planner 写 docs 用
edu-cloud-w1       6c1ee0e [feat/card-subdir]               ← W1 ✅ 完成且已 merge master
edu-cloud-w2       fc4da5f [feat/kg-batch3b]                ← W2 R2 FAIL，已派 batch 3.b.iii
edu-cloud-w3       1439904 [feat/haofenshu-batch3]          ← W3 ✅ 完成且已 merge master
```

### 2.2 master commit 链（本 Planner session 产出 + T-C 执行产出）
```
b0e951c docs: T-D W2 batch 3.b.iii 交接卡 ⭐本 session 最后 commit
459592e merge: W1 Phase 4 card 子目录化 [partial T2 2/2] ← T-C executor 产出
eb594b4 merge: W3 haofenshu Phase 1 Batch 3 [partial T2 1/2] ← T-C executor 产出
8150219 docs: W4-R8 Planner 交接卡（Gate 1 退回 under_review_r8）
8437597 docs: T2 handoff 补 Partial 模式段
fc3f0e0 docs: 2026-04-18 派发 W2-R2 + W4-Exec + T2-Partial 交接卡
29dfb8a docs: 5-window 并行执行规划交接卡（W1-W4 + T2 汇总）
6f3dc81 feat: Phase 5 首动作 — compat_router 注入 DeprecationWarning
55f9d9a docs: Phase 2 Task 1-4 + Phase 4 方案 + 交接卡
848cbae refactor: ORM 等级 2 搬迁
2e0f05f fix: Phase 1 测试修复 + card 字体 + 文档归档
bcf4b97 chore: vite ECS 远程开发 + 前序 session 交接卡
```

### 2.3 W4 worktree feat/conduct-roadmap-batch1 commit 链
- `793eaf2 docs(evidence): R7 PASS 基于伪基线 — 实测 68 vs plan 声称 118` ⭐ 本 session 最后 commit
- `637ce2f review(conduct-roadmap): Gate 1 Plan Review R7 PASS ✅` ← W4 plan session 产出（被证实伪 PASS）

## 3. 已派发任务（5 个，3 在跑 + 2 已完成）

| # | 任务 | worktree / 分支 | 交接卡 | 状态 |
|---|---|---|---|---|
| **T-A** | W2-R2 修复（5 findings） | edu-cloud-w2 / feat/kg-batch3b | `2026-04-18-w2-r2-repair-handoff.md` | ✅ 完成（4 resolved + 1 衍生 R2-F001 → 触发 T-D）|
| **T-B** | W4 实施 T1-T5 | edu-cloud / feat/conduct-roadmap-batch1 | `2026-04-18-w4-exec-T1-T5-handoff.md` | ⛔ **冻结**（plan 基线伪数 → 改派 R8 Planner，T1-T5 必须等 R8 PASS）|
| **T-C** | T2-Partial merge W1+W3 | edu-cloud-t2 / master | `2026-04-17-t2-merge-summary-handoff.md` §1.2/§2.3.B | ✅ **已完成**（master 459592e + eb594b4）|
| **W4-R8** | Planner 订正 plan + 重审 | edu-cloud / feat/conduct-roadmap-batch1 | `2026-04-18-w4-r8-planner-handoff.md` | 🟡 在跑（等 executor session）|
| **T-D** | W2 batch 3.b.iii race mutant test | edu-cloud-w2 / feat/kg-batch3b | `2026-04-18-w2-batch3b-iii-handoff.md` | 🟡 在跑（等 executor session）|

## 4. 待用户操作（不能派 Claude）
- **B1** W3 视觉验收 http://localhost:3100 → admin_principal_1 / 123456（W3 已 merge master 但视觉验收未确认）
- 启动 W4-R8 Planner 新 session（话术见 `2026-04-18-w4-r8-planner-handoff.md` §6）
- 启动 T-D W2 batch 3.b.iii 新 session（话术见 `2026-04-18-w2-batch3b-iii-handoff.md` §8）

## 5. 后续 T2-补遗（待触发）
- **T2-补遗-1**：W2 batch 3.b.iii PASS → merge feat/kg-batch3b 到 master
- **T2-补遗-2**：W4 R8 PASS + T1-T5 完成 + code_review_batch1 PASS → merge feat/conduct-roadmap-batch1 到 master

## 6. 用户偏好（多次纠正后固化）

| 偏好 | 触发场景 | 应用 |
|---|---|---|
| 基于事实，禁止猜测/印象 | "你为什么说它们没启动" 严厉质疑后 | 任何状态判定都用 git status / ls / grep / process / commit message 实证，不凭 commit 数 |
| 基于实际代码，绝对禁止基于 commit 数 | 同上 | commit 数 ≠ 进度（in-flight 工作可能未 commit）|
| 不打补丁，底层修复 | hook 拦截 commit 拆分时 | 不为过 hook 妥协 commit 语义；问题源头修 |
| 按建议执行 | 给选项 A/B/C 时 | 给推荐 + 理由，用户多说"全 A"或"按你建议" |
| 务实统一中线 | 整体技术债清理 | Q1-Q4 = B 方向，不激进推倒不局部最优 |
| checkpoint 式推进 | 多任务规划 | 不自标 ✓ / 不输出全绿表 / 等用户拍板才进下一项 |

## 7. LESSONS 触发记录（本 session 多次自审）

- **L013 自审盲区**：标注依据类型——本 session 至少 3 次拍脑袋（W2 buildChapterTree 不存在 → 实际嵌入 useKnowledgeTree.js / W3 "未启动" → 实际大量 in-flight / T-C 已完成我不知道）
- **L015 虚假完成声明**：禁自标 ✓，本 session 严格遵守"待汇总"语义
- **L017 局部最优**：W2 R2 FAIL 4 选项分析时拒绝选项 4（推后 3.c）= 范围蔓延的局部最优

## 8. 工具/环境约束（实查）

- **projectctl 缺失**：`~/.claude/scripts/projectctl.py` 全系统不存在 → 标准两段式 handoff 不可用 → 全部 legacy-format（合规路径，SKILL.md §"例外/Legacy" 明文允许）
- **AIPROXY_OAI_KEY**：`~/.secrets/aiproxy.key` 路径已 verify（W4 用过）
- **stop hook**：完成声明前必须跑测试 + exit=0；推荐快测 `tests/test_api/test_compat_deprecation.py + tests/test_api/test_compat.py`（19 PASS / 19s）
- **doc_sync_guard hook**：commit 含"关键变更"（route/port/structure/config/deps/entry）时强制 CLAUDE.md staged
- **module_governance_guard hook**：modules.yaml 派生产物过期会拦 commit，跑 `python scripts/governance/aggregate_modules.py` 重生成
- **handoff_format_guard hook**：handoff.md 文件检查格式，legacy-format 标记可绕过 30 行硬限

## 9. 已知陷阱

- **W4 R7 PASS 是伪基线事故**：R1-R7 reviewer 从未实跑基线命令；plan 12 处数字锚点污染（详证据文档 `docs/plans/2026-04-18-batch1-baseline-evidence.md`）
- **W4 worktree 当前 HEAD = 793eaf2**：含证据文档 commit；R8 Planner session 必须从此 HEAD 开始
- **W2 R2 FAIL 后拆 batch 3.b.iii**：gates_lib 硬约束 R2 FAIL → 拒 R3，拆新 batch 是合规路径
- **W2/W3 worktree node_modules 各自一份**：vitest 跑必须 cd 到 worktree 内（cwd 在不同 bash 调用间不持久，每次 `cd /path && cmd`）
- **test_output/tql_yuwen_a3.pdf 飘动**：3 个 worktree (edu-cloud / edu-cloud-t2 / edu-cloud-w1) 都有，gitignored 但 tracked，可忽略
- **CLAUDE.md "120 conduct tests" 描述**：基于伪基线，W4-R8 任务清单 §2.1 含订正

## 10. 新规划窗口第一步

```bash
# Step 1：verify 接替起点
cd /home/ops/projects/edu-cloud-t2
git log --oneline -5      # 应见 b0e951c 在最顶
git worktree list          # 应见 5 worktree

# Step 2：读本卡 + 当前 4 W 状态（合计 ≤5 min）
cat /home/ops/projects/edu-cloud-t2/docs/plans/2026-04-18-planner-session-handoff.md
ls /home/ops/projects/edu-cloud-t2/docs/plans/2026-04-18-*.md  # 列本 session 产出

# Step 3：监控在跑任务（询问用户哪个 W session 出新结果）
# - W4-R8 Planner: 等订正 + R8 review 结果
# - T-D W2 batch 3.b.iii: 等 mini plan + race test + R1 review 结果

# Step 4：响应新结果时遵循
# - 基于事实（grep/ls/git status，禁止凭 commit 数判进度）
# - LESSONS L013/L015/L017
# - 用户偏好（§6）+ 工具约束（§8）
# - 不擅自跑 executor 工作（不动 src/ frontend/ 业务代码）
```

## 11. 文件索引

本 Planner session 产出（master 上）：
| 文件 | 用途 |
|---|---|
| `docs/plans/2026-04-17-tech-debt-cleanup-handoff.md` | 前序 4 phase 技术债清理交接卡 |
| `docs/plans/2026-04-17-tech-debt-cleanup-exec-handoff.md` | 5-window 并行执行规划 |
| `docs/plans/2026-04-17-w1-card-subdir-exec-handoff.md` | W1 card 子目录化（已完成 ✅）|
| `docs/plans/2026-04-17-w2-kg-batch3b-exec-handoff.md` | W2 kg Batch 3b（R2 FAIL → T-D 接力）|
| `docs/plans/2026-04-17-w3-haofenshu-batch3-exec-handoff.md` | W3 haofenshu Batch 3（已完成 ✅）|
| `docs/plans/2026-04-17-w4-conduct-batch1-exec-handoff.md` | W4 conduct Batch 1（R7 PASS 伪基线 → R8 接力）|
| `docs/plans/2026-04-17-t2-merge-summary-handoff.md` | T2 汇总（含 partial mode §1.2/§2.3.B）|
| `docs/plans/2026-04-18-w2-r2-repair-handoff.md` | W2 R2 修复（已完成 ✅，衍生 T-D）|
| `docs/plans/2026-04-18-w4-exec-T1-T5-handoff.md` | W4 T1-T5 实施（冻结，等 R8 PASS）|
| `docs/plans/2026-04-18-w4-r8-planner-handoff.md` | W4 R8 Planner 订正 plan |
| `docs/plans/2026-04-18-w2-batch3b-iii-handoff.md` | T-D W2 batch 3.b.iii race mutant test |
| `docs/plans/2026-04-18-planner-session-handoff.md` | **本卡（Planner 跨 session 交接）** |

W4 worktree feat/conduct-roadmap-batch1 上：
| 文件 | 用途 |
|---|---|
| `docs/plans/2026-04-18-batch1-baseline-evidence.md` | W4 实测偏差证据（R7 PASS 是伪）|

## 12. 启动 prompt（新规划窗口接替）

```
继续 edu-cloud 规划窗口（Planner）工作。

工作目录：/home/ops/projects/edu-cloud-t2（master）
依据交接卡：/home/ops/projects/edu-cloud-t2/docs/plans/2026-04-18-planner-session-handoff.md

第一步：
1. cd /home/ops/projects/edu-cloud-t2
2. git log --oneline -5 verify HEAD = b0e951c
3. git worktree list verify 5 worktree
4. 读本卡 §2 真实状态 + §3 已派任务 + §6 用户偏好 + §9 已知陷阱
5. 询问用户：哪个 W session 有新结果待规划响应？

不擅自跑 executor 工作。基于事实禁止猜测。L013/L015/L017 严守。
```
