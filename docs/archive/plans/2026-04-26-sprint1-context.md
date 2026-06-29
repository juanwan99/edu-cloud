# Sprint 1 新会话详细上下文

本文档为新会话启动 Sprint 1 提供完整上下文，无需回溯前一会话历史。

---

## 一、你在哪里

**项目**: edu-cloud 教育云平台（FastAPI + Vue 3 + Naive UI）
**分支**: master（统一分支，无其他活跃分支）
**目录**: `/home/ops/projects/edu-cloud`

**当前基线**:
```
后端 pytest: 2199 passed / 23 skipped / 21 failed（既有债，非本轮引入）
前端 vitest: 373 passed / 0 failed
前端 build: vite build 成功（14s）
服务: uvicorn pid 运行中，port 9000，health OK
```

---

## 二、全局规划概览

edu 项目群经过全面审查后，制定了 6 Sprint 系统性开发规划：

| Sprint | 主题 | 状态 |
|--------|------|------|
| S0 | 清场（分支合并+安全+测试+文档） | **已完成 + GPT 审查 PASS** |
| **S1** | **基线加固 + Dashboard 实现** | **← 你从这里开始** |
| S2 | 教务教学链路（作业/学期/课表/校历） | 待执行 |
| S3 | 管理与分析链路（联考/学校/分析/数据层） | 待执行 |
| S4 | 德育与家长链路（12 页面增强） | 待执行 |
| S5 | 收尾与运维（质量/HTTPS/备份/ace 合入） | 待执行 |

**设计文档**: `docs/plans/2026-04-26-systematic-dev-plan-design.md`

---

## 三、Sprint 1 修正版（你要做的）

**Plan 文件**: `docs/plans/2026-04-26-sprint1-revised-plan.md`（详细步骤在里面）

### 为什么叫"修正版"

原 Sprint 1 计划估 25h 新建 3 个前端页面（ErrorBookPage/QuestionBankPage/DashboardPage）。
Sprint 1 调研发现这 3 个页面**全部已存在且相当成熟**（316/345/596 行），原计划基于错误假设。
修正为 8h 基线加固 + 增强。

### 4 个 Task

**T1: 修复 Alembic 多 head（最优先，~2h）**
- 症状：`alembic heads` 返回多个 revision，6 个 migration 测试 FAIL
- 根因：feat/kg-batch3b 合并时引入了分叉的 migration 链
- 修复：`alembic merge heads` 或手动调整 down_revision
- 验证：`alembic heads` 返回 1 个 + migration 测试恢复

**T2: Dashboard 后端 3 字段实现（~3h）**
- `src/edu_cloud/api/dashboard.py` 当前返回 3 个假值：
  - `total_staff: null` → 查 PlatformUser 表 COUNT
  - `pending_subjects: null` → 查 grading dispatch stage != 'done'
  - `pending_grading: 0` → 查 GradingTask status='pending'
- TDD：先写测试再实现
- 现有 4 个 pytest 测试在 `tests/test_api/test_dashboard.py`

**T3: 前端 Dashboard 测试补全（~2h）**
- `frontend/src/pages/__tests__/DashboardPage.test.js` 现有 19 测试
- 缺失：fetchCharts / fetchActivity / 网络错误处理
- 补 3-5 个测试用例

**T4: Sprint 2 提前调研（~1h）**
- 对 homework/academic/calendar 模块做调研
- **关键**：验证前端页面是否也已存在（Sprint 1 的教训：审查说"零覆盖"但实际已有）
- 输出结构化调研文档到 `docs/plans/2026-04-26-sprint2-investigation.md`

---

## 四、两条硬纪律（Sprint 1-5 全适用）

### 纪律 1：调研硬门控

每个 Sprint 执行前必须产出结构化调研文档，包含：
1. 资产盘点表（file:line 证据）
2. 端点实测（curl 响应）
3. 调用方清单（grep 结果）
4. 测试基线（pytest 输出）
5. 文件操作清单：[M] 修改 / [N] 新建 + 理由

Sprint 1 的调研已在前一会话完成，结论在 plan 文件开头。

### 纪律 2：Agent 全局注入协议

每个 Agent 子代理 prompt 必须包含三段：
1. **全局上下文**：CLAUDE.md 项目结构 + 前端 serving 架构 + 已有 API client 列表
2. **调研产物**：资产盘点 + 端点实测 + [M]/[N] 清单
3. **禁令**：增强已有文件不新建平行模块 / 先 grep 再新建 / 不改 prompt 未提及的文件 / 改完 vite build

---

## 五、关键教训（前一会话踩过的坑）

1. **Agent 测试修复变回归**：Sprint 0 派 Agent 修复 4 个 vitest 失败，Agent 在不了解源代码的情况下错误修改了测试（把 41 改成 44 但实际就是 41）。GPT 审查拦住了这个问题并自动回退。**教训：Agent 必须先读源代码确认事实再改测试。**

2. **审查结论可能过时**：全面审查说"9 个模块前端零覆盖"，但合并分支后 3 个模块已有页面。**教训：执行前必须重新验证审查假设。**

3. **出口标准必须诚实**：Sprint 0 design 写"pytest 0 failed"但实际 21 failed 既有债。GPT 审查标记为矛盾。**教训：出口标准写实际可达的值。**

---

## 六、文件索引

| 文件 | 用途 |
|------|------|
| `docs/plans/2026-04-26-systematic-dev-plan-design.md` | S0-S5 总设计（含纪律 1/2 定义） |
| `docs/plans/2026-04-26-sprint1-revised-plan.md` | Sprint 1 详细步骤（**你的执行依据**） |
| `docs/plans/2026-04-26-sprint0-cleanup-plan.md` | Sprint 0 计划（已完成，参考用） |
| `docs/plans/2026-04-26-edu-systematic-dev-handoff.md` | 本交接卡 |
| `src/edu_cloud/api/dashboard.py` | T2 要改的后端文件（56 行） |
| `tests/test_api/test_dashboard.py` | T2 要改的测试（116 行，4 tests） |
| `frontend/src/pages/DashboardPage.vue` | T3 参考（596 行，不改代码只补测试） |
| `frontend/src/pages/__tests__/DashboardPage.test.js` | T3 要改的测试（133 行，19 tests） |
| `alembic/versions/` | T1 要修复的 migration 链 |

---

## 七、启动 prompt（复制到新窗口）

```
你是 edu-cloud 项目 Sprint 1 的执行者。

读取以下文件获取完整上下文：
1. docs/plans/2026-04-26-sprint1-revised-plan.md — 你的执行计划（4 Task）
2. docs/plans/2026-04-26-sprint1-context.md — 详细上下文
3. docs/plans/2026-04-26-systematic-dev-plan-design.md — 总设计（含纪律 1/2）

当前基线：vitest 373/0 + pytest 2199/21(既有债) + vite build OK

按 plan 中的 Task 1-4 顺序执行。每个 Task 完成后附 git log + test output。
T1（Alembic 多 head）最优先。T4（Sprint 2 调研）验证前端页面是否已存在。

纪律：调研清楚再动手 + Agent 必须注入全局上下文。
Sprint 1 全部完成后，使用 codex-review skill 做 GPT 独立审查。
```
