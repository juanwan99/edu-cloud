# edu-cloud 地基治理计划（2026-06-05）

> 性质：吸收成熟门户前的结构治理总纲。
> 目标：先把 Portal 聚合合同、模块边界、依赖循环、AI 工具归属、权限/模块开关和入口目录治理稳，再吸收成熟大学门户的首页、服务中心、业务系统中心、待办中心、消息中心和个人工作台。
> 范围：`/home/ops/projects/edu-cloud` 当前分支 `feat/module-governance-repair`。

---

## 一句话结论

当前地基已经有第一层守门线，但还不能直接承载成熟门户功能吸收。下一阶段必须先把首页聚合、模块开关、权限入口和 AI 工具归属收束到稳定合同，再逐步切断考试链路中的历史依赖循环。否则门户越抄越大，旧首页散调会扩大成不可维护的系统级耦合。

---

## 当前事实基线

### 已经具备的地基

- 模块合同已经成为治理源头：`src/edu_cloud/modules/*/MODULE.md` 汇总到 `docs/governance/modules.yaml`、`dependency-graph.md`、`debt-report.md`。
- 当前模块合同数：23。
- `exam_import` 已注册为模块，后端 `portal` 聚合模块已经存在。
- 治理检查当前可通过：
  - `python3 scripts/governance/aggregate_modules.py --check`
  - `python3 scripts/governance/check_module_dependencies.py --check`
  - `python3 scripts/governance/check_ai_tool_modules.py`
  - `python3 scripts/governance/check_permission_mirror.py`
- 权限镜像已经对齐：后端权限源在 `src/edu_cloud/core/permissions.py`，前端镜像在 `frontend/src/config/permissions.js`。
- 后端已经有第一版 Portal API：
  - `GET /api/v1/portal/summary`
  - `GET /api/v1/portal/todos`
  - `GET /api/v1/portal/messages`
  - `GET /api/v1/portal/calendar-digest`
  - `GET /api/v1/portal/services`

### 仍然存在的核心旧债

- 依赖图仍有 55 条跨模块边、30 个历史循环。核心循环簇集中在 `exam / pipeline / analytics / grading / scan / card / profile / knowledge / bank`。
- `pipeline` 是外发依赖中心，`exam` 是被依赖中心。优先风险是 `exam <-> pipeline`、`exam <-> grading` 和 `analytics <-> profile`。
- 旧首页 `frontend/src/pages/DashboardPage.vue` 仍直接调用业务接口：
  - `/dashboard/summary`
  - `/exams`
  - `/analytics/report/trend/grade`
  - `/notifications`
  - `/marking/my-assignments`
  - `/grading/tasks`
  - `/homework/tasks`
- Portal 后端目前只是最小聚合层：待办主要来自 homework，消息来自旧 notifications，日程来自 calendar；还缺 exam、grading、marking、analytics、approval、workflow、conduct 等聚合适配。
- AI 工具 67 个中，46 个挂在 `module_code="exam"`；其中大量 `analytics`、`profile`、`student`、`knowledge`、`system`、`action`、`adaptive` 域并不应长期由考试模块兜底。
- 前端入口目录分散在 `routeAccess.js`、`sidebarConfig.js`、Portal `SERVICE_CATALOG`。这些目录会随着门户吸收不断漂移。
- 前端模块为空时存在默认放行逻辑；`calendar` 入口只有 `moduleCode`，没有明确 permission。

---

## 治理原则

1. 先治理地基，再吸收成熟门户功能。
2. Portal 是首页和服务入口的唯一聚合边界，页面不能继续一边展示门户一边散调业务模块。
3. 业务模块拥有自己的表、状态机和写操作；Portal 只做读聚合和入口编排。
4. 新增功能只能增加清晰模块合同，不能增加未声明跨模块依赖。
5. 允许先用基线承认历史债，但每个后续阶段必须减少债务，不能只冻结债务。
6. 权限、模块开关、入口目录、AI 工具可见性必须使用同一套模块语义。

---

## 明确不做

- 不在地基治理完成前全量照抄大学门户页面。
- 不把 Portal 写成直接查询所有业务表的超级模块。
- 不在 `DashboardPage.vue` 里继续追加新的业务接口散调。
- 不通过前端隐藏菜单来替代后端权限和模块开关。
- 不用 `exam` 继续兜底所有分析、画像、学生、知识、系统类 AI 工具。
- 不为了短期跑通，把依赖循环从 import 层转移成隐式全局调用。

---

## Phase 0：冻结当前治理基线

### 目标

把当前“第一层地基”从工作区状态固定为可审查、可回滚、可继续推进的基线。

### 要做

- 整理当前分支未提交变更，明确哪些属于模块治理、哪些属于历史调查文档。
- 保留并固定以下治理基线：
  - `docs/governance/foundation-boundaries.md`
  - `docs/governance/module-dependencies.yaml`
  - `docs/governance/ai-tool-module-codes.yaml`
  - `docs/governance/portal-aggregation-contract.md`
- 确认 CI 或本地验证包含模块合同、依赖基线、AI 工具模块归属、权限镜像检查。
- 给后续所有阶段设定共同前置门槛：不能新增未声明模块、不能新增未审核依赖边、不能新增未归属 AI 工具。

### 不做

- 不在本阶段重构业务代码。
- 不尝试一次性清空 30 个历史依赖循环。

### 验收

- 工作区变更可以按主题拆分审查。
- 四个治理脚本全部通过。
- 任何新增模块、依赖边、AI 工具、权限漂移都能被检查发现。

---

## Phase 1：Portal 首页聚合合同落地

### 目标

让首页从“页面散调业务接口”迁移到“Portal 统一聚合 API”，这是吸收成熟门户前最重要的地基动作。

### 要做

- 扩展 `src/edu_cloud/modules/portal` 的 source adapters：
  - exam：最近考试、考试状态、考试待处理。
  - grading：阅卷任务、质检风险、调度待办。
  - marking：我的阅卷任务。
  - analytics：趋势摘要、关键指标、报告入口。
  - homework：作业待办继续保留，但补齐角色范围。
  - conduct：德育待办和班级风险摘要。
  - studio/notifications：统一消息摘要。
  - approval/workflow：审批步骤和 AI 工作流步骤只读聚合。
  - calendar：近期日程摘要。
- 将 Portal DTO 扩展为首页需要的稳定读模型，但不让 Portal 拥有业务表。
- 把 `DashboardPage.vue` 的数据读取迁移到 `/api/v1/portal/*`。
- 为前端增加一个 Portal API adapter，页面只消费 adapter 输出。
- 保留现有视觉与角色工作台设计，但替换数据来源。

### 不做

- 不在首页组件里直接新增 `/exams`、`/grading`、`/analytics` 等业务调用。
- 不把审批、工作流、通知表直接 import 到 Portal 服务里。
- 不在 Portal 阶段重写所有业务页面。

### 验收

- `DashboardPage.vue` 不再直接调用旧业务聚合接口。
- 首页所有待办、消息、日程、服务入口都包含 `source_module`、`source_id`、`action_url`、`permission`、`module_code`。
- 关闭某个学校模块后，Portal 返回结果和前端入口同时消失。
- Portal service tests 覆盖 exam、grading、marking、analytics、homework、conduct、studio、calendar、approval、workflow 的关键正反例。

---

## Phase 2：统一入口目录、权限和模块开关

### 目标

让服务中心、侧边栏、路由守卫、首页服务入口使用同一套模块和权限语义，避免门户越做越大后入口漂移。

### 要做

- 明确入口目录单一源头。建议以后端 Portal service catalog 或独立 `app catalog` 为源头，前端 `routeAccess`、`sidebarConfig` 和服务中心从同一目录派生或被测试校验。
- 补齐 `calendar` 的明确 permission，不再只有 `moduleCode`。
- 收紧前端模块开关加载失败时的策略：学校范围角色不能因为 `enabledModules=[]` 自动放行所有模块。
- 对 `routeAccess.js`、`sidebarConfig.js`、Portal `SERVICE_CATALOG` 增加一致性测试。
- 明确平台管理员、区域管理员、学校角色、家长、教师等角色在 Portal 服务目录中的差异。

### 不做

- 不用多份手写目录长期并存。
- 不只靠前端菜单隐藏实现权限。
- 不把模块开关失败静默当作全部启用。

### 验收

- 所有入口的 `moduleCode` 都属于 `MODULE_CODES`。
- 所有需要权限的入口都有明确 permission。
- 关闭模块时，API、Portal 服务目录、侧边栏、路由守卫表现一致。
- 权限镜像检查继续通过。

---

## Phase 3：AI 工具归属重分类

### 目标

让 AI 工具的 `module_code` 真实表达模块归属，使学校模块开关能够正确控制工具可见性。

### 要做

- 分批重分类当前 46 个 `exam` 工具：
  - `analytics`、`profile`、`adaptive` 域优先评估迁移到 `study_analytics`。
  - `bank`、`knowledge` 域优先评估迁移到 `research`。
  - `student` 域明确是基础学生域、教学域还是分析域，不继续默认挂 `exam`。
  - `system`、`action` 域逐个判定，报告/文档类优先评估 `studio`，评语/成绩相关动作按实际业务模块归属。
  - 阅卷类工具保持 `grading`，作业类保持 `homework`，德育类保持 `conduct`。
- 更新 AI 工具基线，并为每批增加模块关闭后的可见性测试。
- 检查工具内部 import 是否暴露新的模块依赖债。

### 不做

- 不一次性机械替换所有 `exam`。
- 不只改 baseline 而不改运行时测试。
- 不把工具归属和工具实际读写的数据源分离。

### 验收

- `exam` 工具数量显著下降，非考试域不再长期挂在考试模块。
- 关闭 `study_analytics` 时，分析和画像类 AI 工具不可见。
- 关闭 `research` 时，题库、知识图谱、知识检索类 AI 工具不可见。
- `check_ai_tool_modules.py` 继续通过，并且测试覆盖模块开关语义。

---

## Phase 4：依赖循环拆解

### 目标

把历史依赖循环从“被基线允许”变成“持续减少直到归零”。优先处理考试链路核心循环簇。

### 第一批：切 `exam <-> pipeline`

- 把考试发布后的流程触发改为事件、应用服务或明确 adapter。
- `exam` 不直接依赖 `pipeline` 内部服务。
- `pipeline` 不直接 import `exam` 内部模型做强耦合编排。

### 第二批：切 `pipeline -> analytics/profile/bank/knowledge/student`

- 将 pipeline 中的跨模块派生写入改为 source adapters 或事件订阅。
- 分离“考试处理流程”和“分析/画像/题库/知识沉淀”的后置任务。

### 第三批：切 `exam <-> grading`、`grading/scan/card`

- 明确 exam 只拥有考试和科目，grading 拥有阅卷任务和质检，scan/card 拥有采集与答题卡。
- 用稳定 DTO 或 adapter 替代互相 import 内部模型。

### 第四批：切 `analytics <-> profile`

- 将学生画像沉淀为 profile 的读写边界，analytics 只消费 profile 暴露的查询接口或读模型。

### 不做

- 不为了消除 import 循环而把所有逻辑塞进一个 shared 巨型模块。
- 不把 SQL 查询复制到多个模块制造数据语义漂移。
- 不在没有测试的情况下移动状态变更逻辑。

### 验收

- 第一里程碑：30 个历史循环降到 10 个以内。
- 第二里程碑：`pipeline` 外发依赖从 10 个下降到 3 个以内。
- 第三里程碑：依赖循环归零。
- `check_module_dependencies.py --check` 从“禁止新增债”升级为“要求债务下降或归零”。

---

## Phase 5：门户能力吸收准备

### 目标

在地基稳定后，准备吸收成熟大学门户的业务模块，但只吸收业务逻辑和信息架构，不复制其大学场景不适合中小学的部分。

### 可吸收模块

- 首页聚合：通知、待办、日程、常用服务、身份上下文、快捷入口。
- 服务中心：按角色、模块、权限过滤的服务目录。
- 业务系统中心：把考试、阅卷、作业、德育、教务、教研等作为系统入口统一展示。
- 待办中心：跨模块待处理事项统一列表。
- 消息中心：通知、审批、系统消息、日程提醒统一入口。
- 个人工作台：当前身份、职责范围、常用事项、最近访问。

### 需要中小学化改造

- 大学的院系、专业、学工、科研、资产等模块不能直接照搬。
- 中小学重点应围绕班级、年级、学科、教师、家长、学生、考试、作业、德育和教务。
- 大学门户的“办事大厅”可以借鉴，但入口要映射到 edu-cloud 的模块合同和权限体系。

### 不做

- 不照搬大学门户的数据模型。
- 不复制其 UI 结构导致当前中小学角色工作台失焦。
- 不绕开 Portal 合同直接在页面里加成熟门户接口。

### 验收

- 每个吸收功能都能落到一个 edu-cloud 模块 owner。
- 每个入口都有 `moduleCode`、permission、action route。
- 每个聚合项都有 source module 和 source id。
- 新增模块必须有 `MODULE.md`，并通过依赖、权限、AI 工具治理检查。

---

## 总体验收门槛

完成本计划后，项目应达到：

- 首页聚合只通过 Portal 合同消费数据。
- 服务入口、路由守卫、侧边栏和 Portal 服务目录语义一致。
- 学校模块开关能同时影响 API、菜单、Portal 项和 AI 工具。
- AI 工具不再大面积错挂 `exam`。
- 核心依赖循环持续下降，最终归零。
- 新功能吸收前必须先声明模块 owner、权限、模块开关和 Portal 暴露方式。

---

## 风险控制

### 风险 1：计划过大导致长期不可合并

控制方式：按 Phase 拆小 PR，每个 Phase 可独立验证和回滚。

### 风险 2：Portal 变成超级模块

控制方式：Portal 只能依赖 source service/adapter，不能拥有业务表，不能直接 import source table model。

### 风险 3：权限和模块开关前后端不一致

控制方式：增加入口目录一致性测试，并保留 `check_permission_mirror.py`。

### 风险 4：AI 工具重分类影响教师使用

控制方式：分批迁移，先加可见性测试，再按域移动工具归属。

### 风险 5：依赖循环拆解引入行为回归

控制方式：先围绕考试发布、阅卷调度、成绩分析、画像沉淀建立回归测试，再移动依赖。

---

## 推荐执行顺序

1. Phase 0：冻结当前治理基线。
2. Phase 1：Portal 首页聚合合同落地。
3. Phase 2：统一入口目录、权限和模块开关。
4. Phase 3：AI 工具归属重分类。
5. Phase 4：依赖循环拆解。
6. Phase 5：开始吸收成熟门户功能。

最关键的先手是 Phase 1。因为用户最想吸收的是门户和首页聚合，而当前最大的扩张风险也正是在旧首页继续散调业务模块。先把首页迁到 Portal 合同，后面的服务中心、待办中心、消息中心才有正确承载层。
