# Claude×GPT 审计修复共识方案

> 基于: 2026-05-04 行为质量审计报告（2.7/5）
> 辩论轮次: 3 轮（GPT 发散→Claude 挑战→GPT 收敛）
> GPT threadId: 019df2e9-70f9-7c01-abc3-b9d5fb5966ab
> 产出日期: 2026-05-04

---

## 总根因（双模型共识）

五个硬伤（完成诚实度、规划归档、Git 体系、Commit 质量、打地鼠）不是五个孤立问题，指向同一个结构性缺陷：

1. **检测多，收口少** — Hook/Guardian/Truthline 都能发现问题，但多数只是 warn/additionalContext
2. **状态分散，没有单一完成裁判** — session state、gates.json、git、dist、backend、Guardian 各管各的，Stop hook 没有统一消费
3. **例外路径比主路径便宜** — `# skip-code-review` 比补 gates 更便宜；untracked 比归档更便宜
4. **个人开发场景下，提醒不够** — 没有 CI/CD 兜底时，本地 hook 就是最后防线

**指导原则**：Stop/commit 只 block 本地可判定、漏过代价高、触发频率低的红灯。远程依赖和历史债进入 ledger/基线，不制造 ask 疲劳。

---

## P0 — 立即止血

### P0-0: 治理文件一次性 sweep（前置依赖）

**问题**：23 个 untracked plan/gates/review 文件，证据链断裂
**动作**：
- 正式治理产物（plan/gates/review report）→ `git add` + commit
- 已完成任务 handoff → 移到 `docs/plans/archived/`
- 临时产物（startup prompt、raw codex log）→ `.gitignore`
**修改对象**：`git add docs/plans/*.md docs/superpowers/plans/*.md docs/meta-reviews/*.md`
**依赖**：无，先做

### P0-A: 本地 truth hard gate（最大 delta）

**问题**：completion_guard 只检查"跑没跑 build"，不检查 build 是否对齐 HEAD
**证据**：`completion_guard.py:97-128` prove_gate 只看 `vite build` 命令是否执行成功
**方案**：
- 新增 `truthline_local_check()` 函数
- 读 `frontend/dist/version.json` 的 `git_hash` + `git rev-parse --short HEAD` 对比
- 纯本地操作，0 网络依赖，<100ms
- 不一致时 block + 提示 `cd frontend && npm run build`
- 插入位置：`completion_guard.py` Stop handler，Phase 1 之前
**分层**：
- **Hard block**（本地）：source hash ≠ build hash（且本会话 touched frontend）
- **Soft warn**（远程）：mcu.asia/nginx/backend 不一致，只在声称"已上线/用户可见"时 block
**预期**：完成诚实度 2→3.8，整体 2.7→3.1
**修改对象**：`~/.claude/hooks/completion_guard.py`

### P0-C: Review waiver 风险分类

**问题**：`code_review_gate_guard.py:35` 裸 `skip-code-review` 无条件放行
**方案**：三档分类

| 档位 | 条件 | 行为 |
|------|------|------|
| 绿色 | 纯 docs/md + 纯 CSS/style + <5 files | 允许 `# skip-code-review` |
| 黄色 | 5-15 files 且全部 `.vue/.css/.scss` | 必须 `# review-waiver: {reason}` |
| 红色 | 含 router/models/migration/permissions/service + >15 files + T3/T4 | 禁止 skip，必须 gates pass |

**修改对象**：`~/.claude/hooks/code_review_gate_guard.py:35` 附近
**预期**：Commit 质量 2→3.5，自审 2→3.3

### P0-D: code_review_gate 降噪

**问题**：83/84 block 是"T3+ 无 gates_file"假阳性——规划态 commit 被误拦
**方案**：
- docs/plan/design/handoff 类 commit（commit message 含 `docs:/plan:/design:/handoff:`）不因 T3 无 gates_file block
- 只对执行态 commit（`feat:/fix:/refactor:`）+ 高风险路径 block
**修改对象**：`~/.claude/hooks/code_review_gate_guard.py:42-55`
**预期**：假阳性率从 >98% 降到 <20%

---

## P1 — 短期加固（Week 1）

### P1-A: pytest no-new-failures 基线

**问题**：27 个历史失败使 pytest 全绿作为完成条件不可行
**方案**：
- 新建 `.quality/known-pytest-failures.txt`（当前 27 个失败）
- 新建 `scripts/pytest_delta.py`：跑 pytest → 对比基线 → 新增失败 block
- 已知失败消失（修好了）→ 自动移除
- 每周 review known failures，逐步清零
**修改对象**：新建 2 文件 + 改 `verification_recorder.py`
**预期**：回归控制 2→3.5

### P1-B: Closeout ledger

**问题**：Stop 时信息分散，没有一页状态
**方案**：
- 扩展 `completion_guard.py` Stop handler
- 输出 truth/git/tests/gates/artifacts 汇总状态
- Hard block 项：本地 truth red（P0-A）+ 当前会话 dirty edited files + 新增 pytest failure
- 披露项（不 block）：unpushed commits、hanging branches、远程 truth yellow
**修改对象**：`~/.claude/hooks/completion_guard.py:645+`
**预期**：Git 体系 2→3.5，完成诚实度再提升
**依赖**：P0-A 稳定后

### P1-C: Trajectory completion gate

**问题**：打地鼠模式无阻断
**方案**：
- 保留 30min/6次 warn 阈值（不改）
- 新增：同会话高频修改文件 + 声称完成时 → 要求 root-cause note
- 不惩罚跨天合理迭代（只看 session 内）
**修改对象**：`~/.claude/hooks/trajectory_collector.py` + `trajectory_analysis.py`
**预期**：能力边界 2→3

---

## P2 — 长期架构（Week 2-3）

### P2-A: Closeout State Machine

**问题**："检测多收口少"的根治
**方案**：
- 新建 `~/.claude/contracts/closeout-state.schema.json`
- completion_guard、change_auth、guardian/collector 消费同一状态
- 定义状态机：`working → ready_to_close → close_blocked → closed`
**时间表**：
- Week 1: P0/P1 shadow + hard gate 稳定
- Week 2: 定义 schema，让各组件写同一状态
- Week 3: completion_guard 从散装判断迁到 state machine 消费

### P2-B: Guardian local/remote 分层

**问题**：远程依赖（curl mcu.asia）不应污染本地完成裁判
**方案**：
- guardian/collector.py 的 `all_aligned` 拆成 `local_aligned` / `remote_aligned`
- completion 只消费 `local_aligned`
- 显式"已上线"声明时才要求 `remote_aligned`

### P2-C: Gates/Plan manifest 化

**问题**：gates.json 散落各处，格式不统一
**方案**：
- gates_lib.py 创建 gates 时写 manifest
- receipt 绑定 commit/range hash
- 旧 gates 兼容读，新 manifest 只对新任务强制

---

## 依赖图

```
P0-0 sweep ──→ P0-B tracked gate
                    ↓
P0-A truth gate ──→ P1-B closeout ledger ──→ P2-A state machine
                                                    ↑
P0-C waiver ──→ (独立)                    P2-B guardian 分层
P0-D 降噪  ──→ P2-C manifest
P1-A pytest delta ──→ P1-B closeout ledger
P1-C trajectory ──→ (独立，可并行)
```

## 实施路线图

| 时间 | 方案 | 核心交付 |
|------|------|---------|
| Day 0 | P0-0 | 治理文件 sweep commit |
| Day 1 | P0-A | 本地 truth hard gate 上线 |
| Day 2 | P0-D + P0-C | code review gate 降噪 + waiver 分类 |
| Day 3 | P0-B | 治理产物 tracked gate |
| Week 1 | P1-A + P1-B | pytest delta + closeout ledger |
| Week 1 | P1-C | trajectory completion gate |
| Week 2-3 | P2-A | closeout state machine shadow→hard |
| Week 2-3 | P2-B + P2-C | guardian 分层 + manifest |

## 预期评分提升

| 维度 | 当前 | P0 后 | P1 后 | P2 后 |
|------|------|-------|-------|-------|
| D1 宏观决策 | 3.5 | 3.5 | 3.5 | 3.5 |
| D2 微观执行 | 2.5 | 3.2 | 3.5 | 4.0 |
| D3 工程纪律 | 2.4 | 3.0 | 3.5 | 4.0 |
| D4 行为模式 | 2.5 | 2.8 | 3.2 | 3.5 |
| **整体** | **2.7** | **3.1** | **3.4** | **3.8** |

## 个人开发者 DX 评估

**日常增加的摩擦**：
- commit 时如果含高风险文件不能裸 skip（P0-C）→ 必须有 gates 或写 reason
- Stop 时如果 truth 红灯要先 build（P0-A）→ 但这本来就是应该做的事
- 新增 pytest 失败会 block（P1-A）→ 不影响历史失败

**日常减少的摩擦**：
- code_review_gate 假阳性降 80%+（P0-D）
- prove_gate 噪音降低（P0-A 精准检测替代笼统 block）
- Stop 时一页状态一目了然（P1-B）

**净效果**：高成本低频动作（T3 skip、truth 断裂）变贵；低成本高频动作（plan commit、日常编码）不受影响。符合用户偏好。
