<!-- legacy-format -->
# W2 · knowledge-graph Phase 1 Batch 3b · 执行窗口交接卡

> 类型：T1 并行执行窗口（4 窗口之一）
> 前序 handoff（必读）：`docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3b.md`
> 起点 git HEAD：`6f3dc81`（commit 拆分后）
> 工作分支：**`feat/kg-batch3b`**（独立分支）

## 1. 与前序 handoff 的关系
- **前序 handoff 是任务详情来源**（T11 NodeDetailDrawer 高考真题/学习单元 tab + T12 章节导航 buildChapterTree + TreeNavPanel 双模式）
- **本卡仅追加并行执行硬约束**，不重复任务内容

## 2. 范围定义

### 2.1 可改文件（白名单）
- `frontend/src/components/knowledge-tree/NodeDetailDrawer.vue`（T11）
- `frontend/src/components/knowledge-tree/TreeNavPanel.vue`（T12，双模式）
- `frontend/src/components/knowledge-tree/buildChapterTree.js`（T12 新建 helper）
- `frontend/src/pages/KnowledgeTreePage.vue`（如需引入新 tab/导航）
- `frontend/src/api/knowledgeTree.js`（如需新 API 调用方法）
- 对应测试：`frontend/src/components/knowledge-tree/__tests__/*`

### 2.2 红线禁区
- `src/edu_cloud/modules/card/*` — W1 范围
- `src/edu_cloud/modules/conduct/*` — W4 范围
- `src/edu_cloud/modules/knowledge_tree/*` 后端 — Batch 1-3a 已 PASS，本卡前端范围
- `frontend-nuxt/*` — W3 范围
- `frontend/src/components/{shell,ai,context,workspace,studio,calendar}/*` — 与 kg 无关
- `CLAUDE.md` — 不动（前端 KG 改动不需同步项目级 CLAUDE.md，Batch 3 完整收口时再说）

## 3. 实施步骤
按前序 handoff §"实施步骤"执行。本卡不重复。

```bash
# Step 0: 起分支
cd /home/ops/projects/edu-cloud
git checkout -b feat/kg-batch3b
```

## 4. 测试隔离

```bash
# 仅跑 knowledge-tree 前端测试
cd /home/ops/projects/edu-cloud/frontend
npx vitest run src/components/knowledge-tree/__tests__/
# 预期 ~30+ 测试 PASS（按前序 handoff 基线）
```

**禁止**：跑后端 pytest 全量（与 W1/W4 争抢资源）；跑 frontend 全量 vitest 也不必（精准跑 kg 子集即可）。

## 5. 验收契约
按前序 handoff "验收契约" + 追加：
- 不动红线文件
- vitest knowledge-tree 子集 100% PASS
- 不引入新前端依赖（不改 frontend/package.json）

## 6. checkpoint 输出格式

```
【W2 kg Batch 3b · 待汇总】
- 工作分支：feat/kg-batch3b
- 最终 commit hash：<sha>
- T11 NodeDetailDrawer：完成/未完成（差异说明）
- T12 TreeNavPanel + buildChapterTree：完成/未完成
- vitest 子集：N passed / 0 failed
- 异常/已知问题：<列出>
- 等 T2 汇总窗口 merge
```

## 7. 与其他窗口同步
- **零文件冲突**（W1/W3/W4 红线均互斥）
- **不直接 commit master** — 完成在 feat/kg-batch3b
- **不 push origin** — T2 统一处理

## 8. 第一步指令

```bash
cd /home/ops/projects/edu-cloud
cat docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3b.md  # 必读前序
cat docs/plans/2026-04-17-w2-kg-batch3b-exec-handoff.md              # 必读本卡
git log --oneline -5
git status                                                            # 应空
git checkout -b feat/kg-batch3b
# 报告："已起 feat/kg-batch3b 分支，前序 handoff 任务理解 = T11+T12，准备 Step 1"
```

等用户确认进入实施。

## 9. 兜底
- 前序 handoff 信息缺失 → 立即报告，不擅自推断
- vitest 失败定位不到 → 按 bug-fix-discipline 输出根因声明
- 同子项被纠正 ≥3 次 → 主动放弃
