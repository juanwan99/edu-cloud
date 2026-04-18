<!-- legacy-format -->
# W2 KG-phase1 Phase 1 收尾合并交接卡 · 2026-04-18 10:45:01

> 类型：Executor session（前端实施 + 测试 + 收尾）
> 创建：Planner (Opus 4.7 1M)
> 工作目录：`/home/ops/projects/edu-cloud-w2` 分支 `feat/kg-batch3b` @ `80b57fb`
> 优先级：**P0 业务推进**（合并 B1 + B2）
> 估时：3-5h（Phase A 1h + Phase B 2-4h）

---

## §1. 任务背景（基于事实）

KG-phase1 state.json 实查：T0-T10 已完成 / **T11-T14 pending**（4 task）。

| Task | 描述 | 当前状态 |
|---|---|---|
| T11 | NodeDetailDrawer 高考真题 + 学习单元 tab | batch 3.b 实施中，**R2 FAIL** → 拆 3.b.iii |
| T12 | 教材章节导航模式 | 同 T11 batch 3.b |
| T13 | ModuleOverviewPanel 统计增强 + 集成验证 | 待启 (batch 3.c) |
| T14 | 收尾 — design.md 标记 + 审查交接单 | 待启 (batch 3.c) |

**本任务**：W2 worktree 上串行做完 batch 3.b.iii (race test 补丁) + batch 3.c (T13-T14 + Phase 1 收尾)。

---

## §2. 范围

**In scope**：
- **Phase A** — batch 3.b.iii race mutant test（按 existing handoff `2026-04-18-w2-batch3b-iii-handoff.md`）
- **Phase B** — batch 3.c：实施 T13 ModuleOverviewPanel + T14 收尾
- 完成后 codex-review code_review_batch3b_iii + code_review_batch3c
- merge 由 T2-补遗 session 处理（**不在本任务**）

**Out of scope**：
- 修后端 `src/edu_cloud/*`（Phase 1 仅前端）
- 修 W4 / master 上的 plan baseline 数字（T-F 范围）
- merge feat/kg-batch3b 到 master（T2-补遗）
- T-F plan 清洗（独立任务）

---

## §3. 红线

- **Phase A**：禁动 `frontend/src/components/knowledge-tree/ExamItemsTab.vue`（仅补 race test）
- **Phase B**：仅动 `frontend/src/components/knowledge-tree/ModuleOverviewPanel.vue` + 关联测试
- **禁动后端** `src/edu_cloud/*`、`tests/test_*`（Phase 1 收尾仅前端）
- **禁动 master 上 plan baseline 数字**（T-F 任务）
- **禁动 W4 worktree 上文件**（不同分支）
- 完成声明前必须 vitest + codex-review PASS

---

## §4. 关键证据起点

| 项 | 命令 / 路径 |
|---|---|
| W2 worktree HEAD | `cd /home/ops/projects/edu-cloud-w2 && git log --oneline -3` 应见 `80b57fb` |
| Phase A handoff | `docs/plans/2026-04-18-w2-batch3b-iii-handoff.md`（同一仓 docs/plans/）|
| Phase B plan 引用 | `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md` T13/T14 段 |
| Phase 1 design 收尾 | `docs/plans/2026-04-12-knowledge-graph-optimization-design.md`（结尾标记"[实现完成]"）|

---

## §5. 步骤

### Phase A：batch 3.b.iii race mutant test（1h）

1. `cd /home/ops/projects/edu-cloud-w2`，verify HEAD = `80b57fb`
2. 读 `docs/plans/2026-04-18-w2-batch3b-iii-handoff.md` Step 0-7 全文
3. 按 handoff 补 `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js` +2 it (resolve/reject race)
4. 红线：**ExamItemsTab.vue 零改动**
5. 强制：粘贴反证 1+2 实测 fail 输出到 review-handoff-batch3biii
6. `cd frontend && npx vitest run src/__tests__/knowledge-tree/ExamItemsTab.test.js`
7. commit + `codex-review code_review_batch3b_iii round=1`
8. R1 PASS 才进 Phase B

### Phase B：batch 3.c T13-T14 + Phase 1 收尾（2-4h）

1. 读 `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md` T13/T14 段
2. **T13 ModuleOverviewPanel 统计增强 + 集成验证**：
   - 按 plan T13 实施（含 testable slices）
   - 跑 `cd frontend && npx vitest run src/components/knowledge-tree/`
   - commit
3. **T14 收尾**：
   - design.md 顶部标"[实现完成]"
   - 写 `2026-04-18-w2-kg-phase1-finish-review-handoff.md`（codex-review 入参）
   - state.json T11-T14 标 completed
   - commit
4. `codex-review code_review_batch3c round=1`
5. R1 PASS 才完成；R2+ 走 fix
6. **完成 SendMessage 通知 Planner**：触发 T2-补遗 merge feat/kg-batch3b 到 master

---

## §6. 完成定义 (DoD)

- Phase A: batch3b.iii vitest PASS + codex-review PASS（commit + review report）
- Phase B: T13-T14 实施完成 + vitest PASS + codex-review PASS
- design.md 标"[实现完成]" + state.json T11-T14=completed
- 通知 Planner Phase 1 全收尾，触发 T2-补遗 merge

---

## §7. 启动 prompt（直接复制）

```
[edu-cloud] Executor | 2026-04-18 10:45:01 | W2 KG-phase1 Phase 1 收尾合并
工作目录: /home/ops/projects/edu-cloud-w2 (feat/kg-batch3b @ 80b57fb)

读取交接卡: docs/plans/2026-04-18-w2-kg-phase1-finish-handoff.md
按 §5 Phase A → Phase B 串行：
- Phase A: 按 docs/plans/2026-04-18-w2-batch3b-iii-handoff.md Step 0-7
- Phase B: 按 docs/plans/2026-04-13-knowledge-graph-phase1-plan.md T13/T14

红线 §3:
- Phase A: ExamItemsTab.vue 零改动（仅补 race test）
- Phase B: 仅动 ModuleOverviewPanel.vue + 关联测试
- 禁动后端 src/edu_cloud/*
- 禁动 master/W4 上 plan baseline 数字（T-F 任务）
- 完成必须 vitest + codex-review PASS

每 Phase 完成 codex-review；R1 PASS 才进下一 Phase。
完成后用 SendMessage 通知 Planner，触发 T2-补遗 merge feat/kg-batch3b 到 master。
基于事实 + vitest 输出 + GPT review，禁猜测。L013/L015 严守。
```

---

## §8. 后续触发（不在本 scope）

- **T2-补遗 merge** feat/kg-batch3b 到 master（W2 收尾后）
- **KG-phase2 设计**（Phase 1 完成后启动 design plan）
- **T-F plan 清洗** 独立处理 W2 plan baseline 数字
