<!-- legacy-format -->
# W4-R8 · conduct-roadmap Batch 1 · Plan Review R8 订正 · Planner 交接卡

> 类型：T3 plan 订正窗口（Gate 1 退回 under_review_r8）
> 创建：2026-04-18 规划窗口（Opus 4.7）
> 工作分支：`feat/conduct-roadmap-batch1`
> 工作 worktree：**`/home/ops/projects/edu-cloud`**（主仓）
> 起点 HEAD：commit 证据文档之后（见 §1 verify）
> 用户决策：§5 [a] Gate 1 退回 R8 重审（2026-04-18）

## 1. 第一步 verify
```bash
cd /home/ops/projects/edu-cloud
git log --oneline -3   # 应见 docs(evidence) 在 637ce2f 之上
cat docs/plans/2026-04-18-batch1-baseline-evidence.md | head -50  # 必读全文
cat docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md | head -25  # 看 frontmatter status
```

## 2. R8 任务清单（按优先级）

### 2.1 必做 · 核心订正
- **核 R3 handoff L171 真伪**（依据：证据文档 §7）：读 `docs/plans/2026-04-12-conduct-module-review-handoff-batch1-r3.md` L171，verify "原本就是 118" 是否真实
  - 如真：源头漂移在更早时间点，需追溯到 conduct-module-design
  - 如假：源头从 conduct-roadmap-batch1-plan 创建时就编造，污染面更窄
- **订正 plan 12 锚点**（依据：证据文档 §3 表）：L24/L82/L88/L94/L101-102/L111/L149-153/L166/L441/L842 全部按实测 68 重算
- **CLAUDE.md "120 conduct tests" 描述**（证据文档 §3 L94）：同步订正

### 2.2 必做 · gate 状态
- 改 plan frontmatter `gate_1_result: PASS @ 2026-04-18 (R7...)` → `under_review_r8`
- 改 `gates.json` (`docs/plans/2026-04-14-conduct-roadmap-batch1-gates.json`) plan_review.status PASS → fail / under_review

### 2.3 必做 · 触发 R8 审查
```bash
# AIPROXY key 已 verify 路径
export AIPROXY_OAI_KEY="$(cat ~/.secrets/aiproxy.key)"
export PLAN_FILE="/home/ops/projects/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md"
# 调 codex-review plan R8
```

### 2.4 选做 · 横向核查
- 其他在飞 plan 是否有类似"基线 + N = M"伪计算式？（W1 / W2 / W3 plan 都查一遍）
- 同模式风险：handoff_format_guard 检查 review report 必需 section，但**不检查基线数字真实性** —— 这是个治理 gap

## 3. 范围定义

### 3.1 可改文件（白名单）
- `docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md`（订正 12 锚点 + frontmatter gate）
- `docs/plans/2026-04-14-conduct-roadmap-batch1-gates.json`（status 改）
- `CLAUDE.md`（参考文档条目"120 conduct tests" 描述）
- `docs/plans/2026-04-18-batch1-baseline-evidence.md`（如需补 R8 调查结论）
- 新建：R8 review report + raw log（codex 自动写）

### 3.2 红线禁区
- **禁动 T1-T5 实施代码**（permissions.py / conduct/ / sidebarConfig.js / MODULE.md / 测试文件）—— R8 PASS 后另起 session 才能实施
- 禁动 W1/W2/W3 范围
- 禁 push origin

## 4. R8 PASS 后下一步
- R8 PASS → plan frontmatter `gate_1_result: PASS @ 2026-04-18 (R8)`
- gates.json plan_review status pass
- 用户决策启动 T1-T5 实施 session（**仍需新 session**，T3 硬约束）
- 实施 session 用本卡引用的 plan **R8 订正版**作为依据

## 5. checkpoint 输出格式

```
【W4-R8 Planner · 待汇总】
- 工作分支：feat/conduct-roadmap-batch1
- R3 handoff L171 核验结果：真 / 假 + 证据
- plan 锚点订正：N 处（commits <sha list>）
- gates.json status：under_review_r8 / pass-after-R8
- codex-review R8 task ID：<id>，结果：PASS/FAIL
- 横向核查：W1/W2/W3 plan 是否同类型伪基线？是 / 否 / 部分
- 异常：<列出>
- 等用户确认进 T1-T5 实施 session
```

## 6. 启动 prompt（新 Planner session 用）

```
继续 conduct-roadmap-batch1 Gate 1 R8 订正。

工作目录：/home/ops/projects/edu-cloud
工作分支：feat/conduct-roadmap-batch1
依据交接卡：/home/ops/projects/edu-cloud-t2/docs/plans/2026-04-18-w4-r8-planner-handoff.md
依据证据：docs/plans/2026-04-18-batch1-baseline-evidence.md（已 commit）

T3 Planner session（不实施 T1-T5）。第一步：
1. verify HEAD 含 docs(evidence) commit
2. 读证据文档 + 本交接卡 + plan
3. 先核 R3 handoff L171 真伪报告等用户确认
4. 再开 12 锚点订正
```

## 7. 兜底
- L171 核验出更深源头漂移 → 报告，不擅自扩大订正范围
- codex-review R8 卡 AIPROXY key → 检查 ~/.secrets/aiproxy.key 存在性
- R8 又 FAIL → 再 R9，不接受"补丁绕过"
