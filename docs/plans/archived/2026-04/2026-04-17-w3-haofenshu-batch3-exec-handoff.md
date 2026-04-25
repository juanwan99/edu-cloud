<!-- legacy-format -->
# W3 · haofenshu Phase 1 Batch 3 · 执行窗口交接卡

> 类型：T1 并行执行窗口（4 窗口之一）
> 前序 handoff（必读）：`docs/plans/2026-04-14-haofenshu-phase1-batch3-handoff.md`
> 设计文档：`docs/plans/2026-04-12-haofenshu-biz-replication-design.md`
> 起点 git HEAD：`6f3dc81`（commit 拆分后）
> 工作分支：**`feat/haofenshu-batch3`**（独立分支）

## 1. 与前序 handoff 的关系
- **前序 handoff 是任务详情来源**（Task 10-12: PowerFilter + 45 页面 stub + 端到端启动脚本化 + R4 useMenus startsWith 分隔符）
- **本卡仅追加并行执行硬约束**

## 2. 范围定义

### 2.1 可改文件（白名单）
- `frontend-nuxt/*` — 完整目录，独立前端
- 涉及子目录：components/ / composables/ / layouts/ / middleware/ / pages/ / plugins/ / public/ / stores/ / tests/ / assets/ / package.json / nuxt.config.ts / vitest.config.ts / .nvmrc

### 2.2 红线禁区
- `frontend/*` — W2 范围（生产主前端）
- `src/edu_cloud/modules/card/*` — W1 范围
- `src/edu_cloud/modules/conduct/*` — W4 范围
- `src/edu_cloud/*` 全部后端 — Batch 1 backend Schema/Menu API 已落，Batch 3 不应再改后端（如发现 menu API 漏字段需新增端点，**必须先 STOP 报告**）
- `CLAUDE.md` — 不动（Batch 3 完整收口由 Batch 4 / 单独 doc-sync session 处理）

## 3. Node 环境硬约束（Batch 2 R3 已锁）
- `node ≥22.12.0`（`.nvmrc` 锁定 22.12.0）
- 用法：`nvm use` 或确保 PATH 含 portable Node 22.22.2（`~/bin/node-v22.22.2-win-x64/`）
- 禁止：`--legacy-peer-deps` / 降 nitropack 等核心依赖

## 4. 实施步骤
按前序 handoff §"实施步骤"执行。

```bash
# Step 0: 起分支 + Node 版本 verify
cd /home/ops/projects/edu-cloud
git checkout -b feat/haofenshu-batch3
node --version  # 必须 v22.12+
cd frontend-nuxt
npm ci --ignore-scripts  # 应 0 EBADENGINE 警告
```

## 5. 测试隔离

```bash
# 仅跑 frontend-nuxt vitest（独立目录，与所有其他窗口零冲突）
cd /home/ops/projects/edu-cloud/frontend-nuxt
npx vitest run
# 预期 ≥24 PASS（Batch 2 基线 + Batch 3 新增）
```

**禁止**：跑 `frontend/` vitest（W2 范围）或后端 pytest（W1/W4 范围）。

## 6. 验收契约
按前序 handoff "验收契约" + 追加：
- 不动红线文件
- frontend-nuxt vitest 100% PASS
- npm ci EBADENGINE 0 警告
- 不引入新核心依赖（不改 nitropack/nuxt 等）

## 7. checkpoint 输出格式

```
【W3 haofenshu Batch 3 · 待汇总】
- 工作分支：feat/haofenshu-batch3
- 最终 commit hash：<sha>
- T10 PowerFilter：完成/未完成
- T11 45 页面 stub：完成/未完成（实际 N 个）
- T12 端到端：完成/未完成
- vitest：N passed / 0 failed
- npm ci EBADENGINE 警告：0
- 异常/已知问题：<列出>
- 等 T2 汇总窗口 merge
```

## 8. 与其他窗口同步
- **零文件冲突**（独立目录 frontend-nuxt/）
- **不直接 commit master** — 完成在 feat/haofenshu-batch3
- **不 push origin** — T2 统一处理

## 9. 第一步指令

```bash
cd /home/ops/projects/edu-cloud
cat docs/plans/2026-04-14-haofenshu-phase1-batch3-handoff.md  # 必读前序
cat docs/plans/2026-04-17-w3-haofenshu-batch3-exec-handoff.md # 必读本卡
git log --oneline -5
git status                                                     # 应空
node --version                                                 # ≥22.12 verify
git checkout -b feat/haofenshu-batch3
# 报告："已起 feat/haofenshu-batch3 分支，Node 版本 X，前序任务 = T10+T11+T12+R4，准备 Step 1"
```

等用户确认进入实施。

## 10. 兜底
- Node 版本 <22.12 → 立即报告，不强行 npm ci
- npm ci 出 EBADENGINE → 不绕过，按 Batch 2 R3 方案 A 处理
- 同子项被纠正 ≥3 次 → 主动放弃
