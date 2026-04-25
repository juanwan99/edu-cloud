<!-- legacy-format -->
# T-Wipe ECS 单一环境彻底切断 Windows · 2026-04-18 11:16:57

> 类型：Executor session（架构边界声明 + 全文清洗 + hook 升级 + LESSON 落档）
> 创建：Planner (Opus 4.7 1M)（用户 2026-04-18 11:15 严令"必须彻底解决"后）
> 工作目录：`/home/ops/projects/edu-cloud-t2` master + `~/.claude/`
> 优先级：**P0 紧急**（取代 T-F + W4-R8 整合 + A2 决策三个任务）
> 估时：4-6h

---

## §1. 用户铁律（架构边界声明）

> "ECS 是独立环境，跟原 Windows 已经完全没有任何关系了！"
> — 用户 2026-04-18 11:15

**含义**（Planner 解读，待 Executor 严守）：
- takeover commit `00cfc3d` 的 `sync ECS worktree as authoritative` = **单一权威边界声明**
- ECS = 唯一权威环境，Windows = **不再存在的历史，无任何参考价值**
- 所有规格/plan/handoff/CLAUDE.md/baseline-evidence/LESSONS 中**禁止**：
  - cd C:/Users/Administrator 路径
  - Windows-era 数字（118/120/108 等已知 + 任何"Windows 实测/handoff 写"等表述）
  - R1-R3 handoff 时序追溯段（"R3 是 118"/"R2 是 108"等）
  - "Windows-era 历史扩展"、"Windows worktree 仍可达"等表述
- 替代：所有 baseline 用 ECS pytest 实测数字，**不需要解释来源对比 Windows**

**类比**：从美元结算转人民币 → 不是"建汇率表订正报价"，是"从此没有美元价"。

---

## §2. 范围（彻底清洗，不留死角）

**In scope**：

### 2.1 CLAUDE.md（核心权威文档）
- 顶部加架构边界声明（"ECS 单一环境，Windows 已断"）
- 删除 "1896 tests, 含 conduct 106" → 写 "1958 collected / 1934 passed / 68 conduct (ECS pytest 实测 @ 2026-04-18)"
- 删除任何 cd Windows 路径示例
- 删除 conduct 模块描述里"R2 基线 108 + 12 新增"等历史追溯

### 2.2 docs/plans/*.md 全文清洗（除 codex raw log）
- **删除 cd C:/Users/Administrator/edu-cloud**（不替换，删除整段——除非段含独立信息可改 ECS path）
- **删除 Windows 数字 + 历史追溯**：
  - "Windows R3 baseline 是 118" → 删整段
  - "118 passed (R3 收尾)" → 改 ECS 实测数字
  - "108 + 10/12 = 118/120" → 删数字算式
- **删除 R1-R3 handoff 时序段**（如 conduct-roadmap-design §0.1 "测试基线（2026-04-14 verified）" 写 118 → 改 ECS 68）
- **takeover 之前的 plan**（pre-takeover, 即 2026-04-16 之前）：加 `<!-- pre-takeover: archived for history, not active spec -->` 顶部 marker，hook 跳过

### 2.3 baseline-evidence.md（W4 worktree）
- 删除 §"Windows 时序" / §"R3 handoff 真伪追溯" / §"40/50 测试遗失" 全部 Windows 比对段
- 重写为"ECS 真实 baseline 文档"，只含 ECS 实测数字 + 来源命令
- 写在最顶部："ECS 单一环境，本文档不引 Windows 历史"

### 2.4 W4 R8 plan（conduct-roadmap-batch1-plan.md）
- **不是"订正 17 锚点"，是按 ECS 上下文重写**：
  - 数字、命令、路径、测试基线 — 全部 ECS 视角
  - 删除"plan 写 118 / 实跑 68 / 差额 50" 等 Windows 对比
  - frontmatter `baseline_count: 118` → `68`；`baseline_note` 删 Windows 引用
  - 创建 `state.json`（executing-plans skill 硬依赖）
  - W4 R8 整合任务并入本任务（不另开 session）

### 2.5 plan_baseline_guard.py hook 升级
- 现有 block 1（cd Windows 路径）保留
- **新增 block 4**：内容含 `Windows`、`Windows-era`、`Windows 历史`、`Windows worktree`、`R3 handoff 是 X passed` 等字样
- **新增 block 5**：plan 中 conduct 数字白名单 = `{68, 后续 task 加测试增量}`，引 118/120/108 必须在 archived 标记的 pre-takeover 文件内才允许
- 更新 `~/.claude/hooks/README-plan-baseline-guard.md`

### 2.6 LESSON L018 + 决策档清洗
- `~/.claude/LESSONS.md` 新增：
  ```
  L018 ECS 单一环境铁律 (2026-04-18)
  takeover (00cfc3d, 2026-04-16) 是边界声明事件：ECS 单一权威，Windows 完全断开。
  规格/plan/handoff/CLAUDE.md 禁引 Windows 数字、路径、时序追溯。
  "修正 Windows 数字" 是错误思维，"清除 Windows 引用"才是答案。
  类比：美元转人民币不是建汇率表，是废除美元报价系统。
  ```
- `~/.claude/CLAUDE.md` L34-40 教训段加 L018 一行
- `docs/plans/2026-04-18-planner-decisions-v3.md` A2 决策段升级：从"接受 ECS 为权威"改为"Windows 完全切断"
- `docs/plans/2026-04-18-takeover-impact-audit-report.md` §3-4 删除 Windows 数字对比，简化为"ECS baseline 表"

**Out of scope**：
- 修业务代码（src/ frontend/ alembic/ tests/）
- W2 KG-phase1 任务（独立 worktree，不受影响）
- W4 T1-T5 实施（本任务完成后启）
- codex raw log (`.codex-raw-*`) — GPT 原文不动

---

## §3. 红线

- **彻底清除而非订正**：禁留"Windows 118 → ECS 68"对比表/注释/时序段
- **pre-takeover plan 标 archived**：不删除文件（保留历史证据），但用 marker 隔离不再作活规格
- **hook 升级先 dry-run**：现存 plan 多少触发新 block 规则要心里有数
- 禁动业务代码（src/ frontend/ alembic/ tests/）
- 禁动 W2 worktree 上文件（W2 独立业务）
- 完成声明前必须 dry-run 全 docs/plans/ block=0 + pytest conduct PASS

---

## §4. 关键证据起点

| 项 | 命令 / 路径 |
|---|---|
| takeover commit message | `git log --no-patch 00cfc3d` → "sync ECS worktree as authoritative; retire legacy ai/* modules" |
| ECS pytest baseline | `.venv/bin/python -m pytest tests/test_conduct/ -q` → 68 passed |
| 全量 ECS pytest | `.venv/bin/python -m pytest -q` → 1934 passed / 1 fail / 23 skip / 1958 collect |
| 现有 hook | `~/.claude/hooks/plan_baseline_guard.py` 339 行 |
| pre-takeover plan 识别 | `git log --diff-filter=A -- 'docs/plans/<file>'` 早于 00cfc3d (2026-04-16) 即归档 |

---

## §5. 步骤

### Phase 1：架构边界声明（30min）
1. CLAUDE.md 顶部加 "ECS 单一环境铁律" 段
2. ~/.claude/LESSONS.md 加 L018
3. ~/.claude/CLAUDE.md L34-40 加 L018 一行
4. commit `docs+chore: ECS 单一环境铁律 + LESSON L018`

### Phase 2：hook 升级 + dry-run（1h）
1. `~/.claude/hooks/plan_baseline_guard.py` 加 Block 4/5 规则
2. dry-run 看冲击面（现存多少 plan 触发新规则）
3. 更新 README-plan-baseline-guard.md
4. commit `chore(hook): plan_baseline_guard 升级 Block 4/5 (Windows 残影禁引)`

### Phase 3：CLAUDE.md 数字清洗（30min）
1. 全文搜 "1896" / "120 conduct" / "108 + 12" 等 Windows-era 数字
2. 改为 ECS 实测（1958/1934/68）
3. 删除 cd Windows 路径示例
4. commit

### Phase 4：W4 R8 plan ECS-rewrite（1.5h）
1. `docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md` 全文按 ECS 视角重写
2. 创建 `docs/plans/2026-04-14-conduct-roadmap-batch1-state.json`
3. 同步到 W4 worktree（cherry-pick 或 merge master HEAD）
4. commit

### Phase 5：baseline-evidence + audit-report 重写（30min）
1. W4 worktree `docs/plans/2026-04-18-batch1-baseline-evidence.md` 删 Windows 段
2. master `docs/plans/2026-04-18-takeover-impact-audit-report.md` §3-4 简化
3. commit

### Phase 6：剩余 plan 全文清洗（1-2h）
1. dry-run 看 hook 升级后 block 清单
2. 逐文件 Edit：删 cd Windows / 删 Windows 数字时序 / pre-takeover 文件加 archived marker
3. commit 分批

### Phase 7：终验（10min）
1. `python3 ~/.claude/hooks/plan_baseline_guard.py --scan docs/plans/` → block 0
2. `grep -ri "Windows\|C:/Users/Administrator" docs/plans/ CLAUDE.md` → 仅 pre-takeover archived 文件命中
3. `pytest tests/test_alembic_migration.py -q` → 3 passed exit 0
4. SendMessage 通知 Planner T-Wipe 完成

---

## §6. 完成定义 (DoD)

- CLAUDE.md 顶部含"ECS 单一环境铁律"段
- LESSONS.md 含 L018
- plan_baseline_guard hook Block 4/5 上线 + dry-run 验
- 全 docs/plans/ + CLAUDE.md "Windows" 字样 = 0（除 archived pre-takeover 文件）
- W4 R8 plan ECS-rewrite + state.json 创建
- baseline-evidence + audit-report Windows 段删除
- pytest + dry-run 全绿

---

## §7. 启动 prompt（直接复制到新 Claude Code 窗口）

```
[edu-cloud] Executor | 2026-04-18 11:16:57 | T-Wipe ECS 单一环境彻底切断
工作目录: /home/ops/projects/edu-cloud-t2 (master) + ~/.claude/

读取交接卡: docs/plans/2026-04-18-windows-wipe-handoff.md
全文阅读 §1 用户铁律 + §2 范围 + §3 红线 后按 §5 Phase 1-7 串行推进。

红线 §3:
- 彻底清除 Windows 引用，禁"修正"思维（删 Windows 数字而非改写为"118→68"对比）
- pre-takeover plan 加 <!-- pre-takeover: archived --> marker 隔离不删文件
- 禁动业务代码 (src/ frontend/ alembic/ tests/)
- 禁动 W2 worktree 文件
- hook 升级前先 dry-run 看冲击面
- 完成必须全 grep "Windows" 仅 archived 文件命中 + pytest exit 0

完成后用 SendMessage 通知 Planner，触发 W4 T1-T5 实施 + W2 后续。
基于事实 + 实跑 grep + dry-run 数字，禁猜测。L013/L015/L017/L018 严守。
```

---

## §8. 后续触发（不在本 scope）

- **W4 T1-T5 实施**（W4 worktree 上做，按 ECS-rewrite 后的 plan + state.json）
- **W2 KG-phase1 收尾** 不受影响（独立业务）
- **T-F 任务作废**（被本任务覆盖）
- **W4-R8 整合任务作废**（被本任务 Phase 4 覆盖）
- **A2 决策升级为 L018**（决策档保留作历史，但活规格用 L018）
