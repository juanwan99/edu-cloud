---
topic: systematic-dev-plan
tier: T3
type: design
created: "2026-04-26"
status: approved
scope: edu-cloud / paper-seg / answer-card-editor
estimated_hours: 118
sprints: 6 (S0-S5)
baseline_command: "cd ~/projects/edu-cloud && .venv/bin/python -m pytest --tb=no -q"
baseline_verified_at: "2026-04-26T21:11:19+08:00"
baseline_count: "2219 passed / 23 skipped / 2 failed"
---

# edu 项目群系统性开发规划设计

## 现有资产盘点

### 后端（edu-cloud）

| 层 | 已有 | 位置 | 证据 |
|----|------|------|------|
| API 路由 | 276 端点（21 模块） | `src/edu_cloud/modules/` + `src/edu_cloud/api/` | CLAUDE.md 端点清单 |
| Models | 88 表 | `src/edu_cloud/models/` + `modules/*/models.py` | Alembic 36 migrations |
| Services | 15+ service 类 | `src/edu_cloud/services/` + `modules/*/service.py` | CLAUDE.md 实现状态 |
| AI Agent | 62 tools / 23 模块 | `src/edu_cloud/ai/tools/` | `ai/tools/__init__.py` 注册 |
| Tests | 2219 passed / 23 skip / 2 fail | `tests/` 300 文件 | ECS pytest 实测 |
| Workers | grading + pipeline | `src/edu_cloud/workers/` | arq WorkerSettings |

### 前端（edu-cloud/frontend/）

| 层 | 已有 | 位置 | 证据 |
|----|------|------|------|
| 页面 | 49 个（44 成熟 + 3 中等 + 2 骨架） | `frontend/src/pages/` | wc -l 统计 20226 行 |
| API client | 16 模块 + client.js | `frontend/src/api/` | auth/schools/exams/grading/analytics/conduct 等 |
| 组件 | shell(4) + ai(2) + analytics(9) + card-editor(5) + 通用(4) | `frontend/src/components/` | CLAUDE.md 项目结构 |
| 路由 | 44 活跃 + 8 家长端 | `frontend/src/router/index.js` | router.test.js |
| 测试 | 342 passed / 6 failed | `frontend/src/__tests__/` 36 文件 | vitest run 实测 |
| 构建 | dist/ 已就绪 | `frontend/dist/` | vite build 6252 modules |

### 子项目

| 项目 | 后端 | 前端 | 测试 | 位置 |
|------|------|------|------|------|
| paper-seg | 7 router 完整 | app.js 986 行 SPA | 17 文件 | `~/projects/paper-seg/` |
| answer-card-editor | 11 端点完整 | SvgCardStage 391 行（缺 patch 编辑 UI） | 3 文件 | `~/projects/answer-card-editor/` |

### 后端 API 就绪但前端零覆盖的模块

| 模块 | 后端端点数 | 数据量 | 前端 API client | 前端页面 |
|------|-----------|--------|----------------|---------|
| homework | 10 | 有数据 | 无 | 无 |
| academic/semester | 5 | 有数据 | 无 | 无 |
| academic/timetable | 3 | 有数据 | 无 | 无 |
| academic/period | 2 | 有数据 | 无 | 无 |
| calendar | 3 | 有数据 | 无 | CalendarPanel 85 行占位 |
| bank/questions | 2 | 有数据 | 无 | 无 |
| bank/error-book | 4 | 76758 条 | 无 | 无 |
| joint-exams | 7 | 0 条 | jointExams.js 11 方法 | 无 |
| dashboard | 1 | 部分字段 null | 内联调用 | 102 行框架 |

## 增量 vs 新建论证

- **默认立场：增量增强已有代码**
- 前端全部做在 `frontend/`（Naive UI），不新建 frontend-nuxt/（已删除，决策已定）
- 9 个缺失模块的前端页面为 [N] 新建，因为确实不存在前端页面（已 grep 确认无同功能文件）
- 14 个页面增强全部为 [M] 修改已有文件
- 后端数据层 S1-B/C/D 为 ORM 字段扩展 + Alembic migration，增量操作
- 教学计划 service 为 [N] 新建，因为 `grep -rn "teaching_plan" src/edu_cloud/modules/` 确认无已有 service

## 交付路径

```
代码变更 -> vite build -> frontend/dist/ -> nginx 443 (try_files) -> https://mcu.asia -> 用户浏览器
```

- 每个 Task 完成后必须 `cd frontend && npx vite build`
- `npm run dev` 仅限开发调试，不算交付
- 后端变更通过 `systemctl restart edu-cloud` 生效

---

## 核心决策

| 决策 | 结论 | 理由 |
|------|------|------|
| 时间压力 | 无外部用户，按技术优先级推进 | 开发阶段，无上线截止日期 |
| 前端技术路线 | `frontend/`（Naive UI）是终态 | frontend-nuxt/ 已删除；20K LOC + 49 页面 + 生产 serving 完整；资产盘点原则 |
| stash 半成品 | 放弃，从零按调研重做 | 来源不可靠（限流截断 agent 产物）+ 冲突确定性高 + 违反调研优先原则 |
| 执行模型 | 调研到执行双阶段硬门控 | 用户明确要求调研清楚再动手 |
| Agent 治理 | 全局上下文必须注入 | 历史教训：agent 不了解全局会新建平行系统 |

## 执行模型：调研到执行双阶段

每个 Sprint 内部统一结构：

```
调研阶段（独立会话）
  1. 读目标模块后端代码（router/service/model）
  2. grep 调用方，确认接口签名和数据流
  3. 跑相关测试，记录当前基线
  4. 输出：调研摘要 + 执行 checklist

质量门控
  用户确认调研结果后，才进入执行

执行阶段（独立会话 or Agent 子代理）
  1. 按 checklist 逐项实现
  2. 每个功能单元：编码 -> 测试 -> build
  3. 执行完输出：git log + test output

验收门控
  全量 pytest + vitest + vite build
  与 Sprint 开头基线对比，不允许回归
```

关键纪律：
- 调研和执行分会话（WF-001 规划/执行分离）
- 每个功能单元改完代码后必须 `cd frontend && npx vite build`
- 声称完成必须附 git log / test output（L015）
- 并行 Agent 仅在文件不重叠时启用

## 纪律 1：调研硬门控

调研产物必须包含以下全部内容，缺任何一项不许动代码：

1. **资产盘点表**：每个要改的模块，已有什么（file:line 证据）
2. **端点实测**：curl 过的真实响应结构
3. **调用方清单**：grep 函数名，列出谁在用
4. **测试基线**：跑过 pytest -k module 的输出
5. **文件操作清单**：
   - 修改文件标 `[M]` + 现有行数
   - 新建文件标 `[N]` + 理由（为什么不能改已有文件）

## 纪律 2：Agent 全局注入协议

每个 Agent 子代理 prompt 必须包含三段，缺一不发：

**段 1 全局上下文**（从 CLAUDE.md 抽取）：
- 项目结构段（目录树 + 已有模块清单）
- 前端 serving 架构（nginx 443 到 frontend/dist/ 到用户）
- 已有 API client 列表（16 模块 + client.js）

**段 2 本次调研产物**（完整注入，不是摘要）：
- 资产盘点表
- 端点实测结果
- 文件操作清单（[M]/[N] 标记）

**段 3 禁令**：
- 增强已有文件，不新建平行模块
- 如需新建文件，先 grep 确认无同功能文件
- 不改 agent prompt 未提及的文件
- 改完必须 vite build

**主会话集成检查**（Agent 完成后逐项核实）：
- agent 新建的文件是否与已有文件功能重叠
- agent 修改的文件是否超出调研 checklist 范围
- router/sidebarConfig 合并后有无路由冲突
- vite build 是否成功
- pytest + vitest 是否无回归

---

## Sprint 0：清场（约 8h）

**目标**：消除技术债务、统一分支、建立干净基线。

### S0-T1：分支整理与合并（约 2h）

现状：
- `fix/tech-debt-phase0-2`（当前）领先 master 104 commits
- `feat/analytics-report` 含审计文档 + 前端增强
- `feat/kg-batch3b` 知识图谱 Phase 1 收尾
- `feat/conduct-roadmap-batch1` 德育 Batch 1
- 2 个 stash 待清理

动作：
1. 调研各分支 diff 范围，确认文件重叠情况
2. 制定合并顺序，逐个 merge 到 master
3. `git stash drop` 清理两个 stash
4. 确认 master 上 pytest + vitest 全绿

### S0-T2：安全修复收尾（约 2h）

PR #1 已修复大部分。剩余：

| 项 | 动作 |
|---|------|
| .env 从 git 移除 | `git rm --cached .env` |
| edu_cloud.db + .bak 从 git 移除 | `git rm --cached edu_cloud.db*` |
| logs/app.jsonl.* 从 git 移除 | `git rm --cached logs/app.jsonl.*` |
| edu-cloud.service 排查重启 | `journalctl` 查原因 + 重启 |

### S0-T3：前端测试修复 + 基线锁定（约 2h）

6 条 vitest 失败修复：
- router.test.js 路由断言 41 改为 44
- AppSidebar.test.js sidebar mock 3 条
- config.test.js parent items 超限
- sidebarConfig.conduct.test.js CONDUCT_ITEMS 导出

### S0-T4：CLAUDE.md 清理（约 1h）

- 删除所有 frontend-nuxt/ 相关描述
- 更新项目结构段
- 清理冻结文件引用
- 更新测试命令段

### S0-T5：文档归档整理（约 1h）

- frontend-migration-roadmap-design.md 标记 archived
- 确认 15 个活跃 plan 文件状态标记

### 出口标准

- [ ] master 包含所有特性分支工作
- [ ] stash 清空
- [ ] .env / .db / .jsonl 不在 git tracked 中
- [ ] pytest 无新增 failed（既有债 21 failed 已记录，不计入回归）+ vitest 0 failed + vite build 成功
- [ ] CLAUDE.md 无 frontend-nuxt 引用
- [ ] edu-cloud.service 运行中

---

## Sprint 1：考试阅卷主链路补全（约 25h）

**目标**：补齐数据最丰富的考试链路前端。

### 调研阶段（约 4h）

**错题本 + 题库**：
1. 读 `modules/bank/router.py` 确认 4 端点签名、请求参数、响应 schema
2. 读 `modules/bank/service.py` 确认 mastery_status 枚举值、过滤逻辑
3. curl 调端点看实际返回结构
4. 确认 student_id 来源（auth store / route param）
5. 确认 sidebarConfig 中 bank 模块入口

**Dashboard**：
1. 读 `api/dashboard.py` 确认 summary 返回字段（哪些有值、哪些 null）
2. 读 `config/dashboardConfig.js` 确认 10 角色配置映射
3. 读 `pages/DashboardPage.vue` 确认 getKpiValue() 逻辑
4. 不同角色 curl summary 端点，记录实际值
5. Activity Feed 数据源确认

**输出**：调研摘要 + 端点响应示例 + [M]/[N] checklist

### 执行阶段（约 21h，2-3 Agent 并行）

**S1-T1：错题本页面（约 8h）**
- [N] `frontend/src/api/bank.js`（4 函数，bank 模块无已有 client）
- [N] `frontend/src/pages/ErrorBookPage.vue`（mastery 筛选 + 科目筛选 + 统计卡 + AI 反馈）
- [M] `router/index.js` 加 `/error-book/:studentId`
- [M] `sidebarConfig.js` 学生管理组加入

**S1-T2：题库浏览页面（约 5h）**
- bank.js 复用 S1-T1
- [N] `frontend/src/pages/QuestionBankPage.vue`（类型/难度筛选 + 详情弹窗 + 知识点关联）
- [M] `router/index.js` + `sidebarConfig.js`

**S1-T3：Dashboard 角色化改造（约 8h）**
- [M] `src/edu_cloud/api/dashboard.py` 补 total_staff / pending_grading / pending_subjects
- [M] `frontend/src/pages/DashboardPage.vue` KPI 绑定 + Activity Feed
- 四角色验证

### 出口标准

- [ ] ErrorBookPage + QuestionBankPage 可从侧边栏访问
- [ ] Dashboard 四角色 KPI 显示真实数据
- [ ] vite build 成功，mcu.asia 可访问
- [ ] vitest + pytest 无回归

---

## Sprint 2：教务教学链路（约 25h）

**目标**：补齐教务 4 个前端空白模块 + 教学计划服务层。

### 调研阶段（约 5h）

**作业模块**：读 homework router/service/models，跑现有测试，curl 端点
**教务模块**：读 academic router/models，确认 semester activate 互斥逻辑、课表矩阵结构
**校历模块**：读 calendar router + CalendarPanel.vue 现状，确认 notification_rules 关联
**教学计划**：读 WP-E 设计 + `git stash show -p` 参考思路 + grep TeachingPlan model

### 执行阶段（约 20h，3 Agent 并行）

**S2-T1：作业管理页面（约 8h）**
- [N] `frontend/src/api/homework.js`（12 函数）
- [N] `frontend/src/pages/HomeworkPage.vue`（列表+创建+发布+批改+统计）
- [M] router + sidebarConfig

**S2-T2：教务三页面（约 8h）**
- [N] `frontend/src/api/academic.js`（10 函数）
- [N] `SemesterPage.vue` + `TimetablePage.vue` + `CalendarPage.vue`
- [M] router + sidebarConfig

**S2-T3：教学计划服务层（约 4h）**
- 如需新 model/migration：[N] + Alembic revision
- [N] `modules/teaching_plan/service.py` + `router.py`
- [M] `app.py` 注册路由
- 后端测试

### 出口标准

- [ ] 4 新前端页面可访问
- [ ] 教学计划后端 service + router + 测试就位
- [ ] vite build + pytest + vitest 无回归
- [ ] 如有 migration，alembic upgrade head 成功

---

## Sprint 3：管理与分析链路（约 25h）

**目标**：联考管理前端 + 学校/分析增强 + 数据层 S1-B/C/D。

### 调研阶段（约 6h，两路）

**路线 A 前端三模块**：
- 联考：读 joint_exam_api/service/models，确认 jointExams.js 一致性
- 学校：读 SchoolsPage + SchoolSettingsPage 现状，确认 capability_service 数据结构
- 分析：读 AnalysisPage 空壳 + analytics.js 方法消费情况 + power-options 可用性

**路线 B 数据层**：
- S1-B：grep depth_level 确认是否已有
- S1-C：grep Grade model + Class.grade_id 现状
- S1-D：读 profile/ 端点，确认 StudentProfileView VO 聚合范围
- 确认 migration 链当前 head

### 执行阶段（约 19h，3 路并行）

**S3-T1：联考管理页面（约 6h）**
- [N] `JointExamPage.vue` + `JointExamDetailPage.vue`
- [M] router + sidebarConfig

**S3-T2：学校管理 + 分析增强（约 7h）**
- [M] `SchoolsPage.vue`：搜索/筛选/统计
- [M] `SchoolSettingsPage.vue`：能力矩阵 Tab
- [M] `AnalysisPage.vue`：从空壳改为分析入口

**S3-T3：数据层 S1-B/C/D（约 6h）**
- S1-B：ConceptGraphNode + depth_level + migration
- S1-C：Grade model + Class.grade_id + migration
- S1-D：StudentProfileView VO
- 后端测试

### 出口标准

- [ ] 联考 2 页面 + 学校/分析增强完成
- [ ] S1-B/C/D migration 成功
- [ ] vite build + pytest + vitest 无回归

---

## Sprint 4：德育与家长链路（约 20h）

**目标**：德育 5 页面 + 家长端 7 页面从能用升级到好用。全部 [M] 修改，无新建。

### 调研阶段（约 3h）

- 逐页读现有代码，记录已有功能 + 缺失功能
- 确认 conduct.js 28 方法中哪些未被消费
- 确认 cp_token 独立认证和 parentClient 注入

### 执行阶段（约 17h，2 路并行）

**S4-T1：德育 5 页面增强（约 9h）**
- [M] ConductDashboard：+ 趋势图 + 时间段切换
- [M] ConductRecords：+ 类型筛选 + 统计卡 + 批量删除
- [M] ConductRankings：+ 分布图 + 趋势
- [M] ConductParents：+ 搜索 + 统计 + 邀请码入口
- [M] ConductExport：小幅增强

**S4-T2：家长端 7 页面增强（约 8h）**
- [M] ParentLogin：品牌视觉 + 记住手机号
- [M] ParentOverview：成绩摘要 + 积分走势 + 快捷入口
- [M] ParentDetails：时间/类型筛选 + 走势图
- [M] ParentRankings：变化箭头 + 勋章
- [M] ParentRules：搜索 + 分类切换
- [M] ParentRegister / ParentProfile：小幅优化

### 出口标准

- [ ] 12 页面增强完成，全部 [M] 无新建
- [ ] vite build + pytest + vitest 无回归

---

## Sprint 5：收尾与运维（约 15h）

**目标**：质量清理 + 运维基础 + ace 合入前期调研。

### 调研阶段（约 2h）

- grep 残留 TODO/FIXME
- 确认 _frozen/ 和 ComingSoonPage 引用
- nginx + SSL + 备份现状检查
- 读 card-editor-merge-design.md 评估前置条件

### 执行阶段（约 13h）

**S5-T1：代码质量清理（约 4h）**
- 冻结文件删除 + ComingSoonPage 清理
- marking/paper/studio 测试补全（各 +3）

**S5-T2：基础运维（约 5h）**
- HTTPS（Let's Encrypt + nginx SSL）
- 自动备份（cron + sqlite3 .backup）
- 健康检查 + 服务自启

**S5-T3：answer-card-editor 合入调研（约 4h）**
- 端点冲突评估
- 数据合并方案
- 前端挂载方案
- 输出合入 design v2 文档

### 出口标准

- [ ] 冻结文件 + 占位组件已清理
- [ ] marking/paper/studio 测试各 +3
- [ ] HTTPS 生效
- [ ] 自动备份运行 + 恢复验证
- [ ] ace 合入 design v2 产出

---

## 依赖关系

```
S0 --> S1 --> S2 --> S3 --> S5
                     |
                     +--> S4（可与 S3 并行或调序）
```

S4 与 S3 无依赖，可根据节奏调整先后。其余严格顺序。

## 审查来源

本设计基于 2026-04-26 五路并行深度审查（后端/前端/子项目/文档/部署运维），审查报告见审查会话上下文。
