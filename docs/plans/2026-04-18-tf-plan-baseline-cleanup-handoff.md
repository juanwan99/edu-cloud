<!-- legacy-format -->
# T-F Plan Baseline 全局清洗 · 2026-04-18 10:41:24

> 类型：Executor session（批量 docs 编辑 + frontmatter migration）
> 创建：Planner (Opus 4.7 1M)
> 工作目录：`/home/ops/projects/edu-cloud-t2`（master @ T-G 收尾后 HEAD）
> 优先级：P2（继 T-G）
> 估时：3-5h（单 session 串行 3 phase）

---

## §1. 任务背景（基于 T-G 实测）

T-G hook 落地后 dry-run 318 文件 → **clean 89 / block 59 / skip 170**：

| Block 类型 | 命中 | 处置 |
|---|---|---|
| Block 1 Windows 路径 | 30 | 替换 `cd C:/Users/Administrator/edu-cloud` → `cd /home/ops/projects/edu-cloud-t2` |
| Block 2 baseline 数字缺 verified_at | 37 | 加 frontmatter 5 字段 |
| Block 3 *-plan.md 缺 frontmatter | 33 | 加 frontmatter 5 字段 |

（59 总数小于分项之和，因部分文件多重命中）

**A2 决策约束**（`docs/plans/2026-04-18-planner-decisions-v3.md` §1）：
- conduct 数字 118 / 120 / 108 → **68**（A2 ECS 权威）
- alembic 数字 2 → **3**（T-H 实测）
- frontend conduct 3 件套 13 → **6**（T-E §3.2 grep 实测，前端 vitest 待 T-H 后续验证）
- CLAUDE.md 「1896 tests / 120 conduct tests」→ 「1958 collected / 1934 passed / 68 conduct」

---

## §2. 范围

**In scope**：
- 批 1：35 `*-plan.md`（含 W4 R8 plan 12 锚点正文订正；frontmatter 已由 T-G 收尾）
- 批 2：19 `*-review/report.md`（含 codex review reports，按文件历史性判断是否需订正数字）
- 批 3：5 其他（design.md / 杂项）
- CLAUDE.md 顶部加 frontmatter（baseline_command + verified_at + count，对接 T-H）

**Out of scope**（移交后续任务）：
- 修业务代码（src/ frontend/ alembic/ tests/）
- 修 hook 本身（T-G 已落地）
- W4-R8 整合的 plan **正文重写**（T-F 只改 frontmatter + 数字漂移；正文重写是后续任务）
- FAIL fixture 修复（独立 ticket）

---

## §3. 红线

- **A2 ECS 权威**：所有 plan 中 conduct 数字 118/120/108 订正为 68
- **历史时序段保留**：如 R3 handoff §"Windows R3 baseline 是 118"段属历史快照，**不订正**仅加 `<!-- historical -->` 注释
- **codex review reports 慎修**：含 codex GPT 历史输出原文，**默认不动数字**，仅加 frontmatter
- **每批 commit 前必须 dry-run 验该批 0 block**（hook 自检，exit 0）
- **禁动业务代码**（src/ frontend/ alembic/ tests/）
- **禁碰 W4 worktree** `feat/conduct-roadmap-batch1` 分支上 plan（W4 已关闭，本任务在 master）
- **完成声明前必须 dry-run 全 docs/plans/ exit 0 + 0 block**

---

## §4. 关键证据起点

| 项 | 命令 / 路径 |
|---|---|
| T-G hook 文件 | `~/.claude/hooks/plan_baseline_guard.py` 339 行 |
| dry-run 命令 | `python3 ~/.claude/hooks/plan_baseline_guard.py --scan docs/plans/` |
| W4 R8 plan frontmatter 范本 | `docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md` 顶部 5 字段 |
| A2 决策 | `docs/plans/2026-04-18-planner-decisions-v3.md` §1 |
| T-H baseline 真值 | `docs/plans/2026-04-18-ecs-pytest-baseline-report.md` §3 |
| T-E audit 归类 | `docs/plans/2026-04-18-takeover-impact-audit-report.md` §5 |

---

## §5. 步骤

### Phase 1：35 *-plan.md（2-3h）

1. **列文件**
   ```
   python3 ~/.claude/hooks/plan_baseline_guard.py --scan docs/plans/ 2>&1 \
     | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print('\n'.join(f for f in d.get('block_files',[]) if f.endswith('-plan.md')))"
   ```
2. **逐文件 Edit**：
   - 顶部加 frontmatter 5 字段（按 W4 R8 plan 范本）
   - Grep 替换 `cd C:/Users/Administrator/edu-cloud` → `cd /home/ops/projects/edu-cloud-t2`
   - 数字订正：conduct 118/120/108 → 68；alembic 2 → 3；frontend conduct 13 → 6
   - 历史时序段加 `<!-- historical -->` 注释保留原数字
3. **每 5-10 文件 commit 一次**（避免单 commit 太大）
4. **每 commit 前 dry-run 验该批文件 0 block**

### Phase 2：19 *-review/report.md（1-2h）

1. **列文件**（同上 pattern 改 `*-review/report.md`）
2. **加 frontmatter**（type: review/report；不动正文数字）
3. **codex raw log** (`.codex-raw-*`) **跳过**（GPT 原文不能改）
4. **commit + dry-run**

### Phase 3：5 其他文件（30min）

1. design.md / 杂项
2. 视情况加 frontmatter 或 legacy-format
3. **commit + dry-run**

### Phase 4：CLAUDE.md 顶部 frontmatter（10min）

1. 加 frontmatter（baseline_command: 全量 pytest / verified_at: 2026-04-18 / count: 1958）
2. 正文 L?? 「1896 tests, 含 conduct 106」→ 「1958 collected, 1934 passed / 68 conduct」（看实际行号）
3. **commit**

### Phase 5：终验（5min）

1. `python3 ~/.claude/hooks/plan_baseline_guard.py --scan docs/plans/` → block 0
2. `pytest tests/test_conduct/ -q` → 68 passed
3. `git log --oneline -10` → 3-4 个 chore(docs)/docs commit

---

## §6. 完成定义 (DoD)

- `python3 hook --scan docs/plans/` → **block 0**
- A2 决策落地：所有 plan/CLAUDE.md 中 conduct 主体数字订正为 68
- 历史时序段保留原数字 + `<!-- historical -->` 注释
- 3-4 commit 落地（chore(docs): T-F batch X plan baseline cleanup）
- pytest 实跑 conduct PASS 兜底（Stop hook 通过）

---

## §7. 启动 prompt（直接复制）

```
[edu-cloud] Executor | 2026-04-18 10:41:24 | T-F plan baseline 全局清洗
工作目录: /home/ops/projects/edu-cloud-t2 (master)

读取交接卡: docs/plans/2026-04-18-tf-plan-baseline-cleanup-handoff.md
增量上下文必读:
- docs/plans/2026-04-18-planner-decisions-v3.md (A2 决策 §1)
- docs/plans/2026-04-18-ecs-pytest-baseline-report.md (T-H 数字真值 §3)
- docs/plans/2026-04-18-takeover-impact-audit-report.md (T-E 归类 §5)
- ~/.claude/hooks/README-plan-baseline-guard.md (hook 规则)

按交接卡 §5 Phase 1-5 串行推进，每批 commit 前 dry-run 验该批 0 block。

红线 §3:
- A2 ECS 权威：conduct 118/120/108 → 68
- 历史时序段保留 + <!-- historical --> 注释（如 R3 handoff "Windows R3 是 118"段）
- codex raw log (.codex-raw-*) 跳过
- 禁动业务代码 (src/ frontend/ alembic/ tests/)
- 禁碰 W4 worktree feat/conduct-roadmap-batch1 上 plan
- 完成必须 dry-run 全 docs/plans/ block=0 + pytest conduct PASS

完成后用 SendMessage 通知 Planner 实测 block 数 + commit 列表。
基于事实 + dry-run 实跑数字，禁猜测。L013/L015 严守。
```

---

## §8. 后续任务触发（不在本 scope）

- **W4-R8 plan 正文整合**：T-F 后启动 W4 R8 plan 12 锚点的真正订正（Plan Review R8 重启）
- **FAIL fixture 修复**：`test_run_post_exam_pipeline_stub` 独立 ticket
- **T-B W4 T1-T5 实施**：W4 R8 PASS 后启
