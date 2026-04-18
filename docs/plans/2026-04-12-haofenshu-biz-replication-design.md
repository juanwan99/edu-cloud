<!-- pre-takeover: archived for history, not active spec -->
# 好分数业务逻辑复刻 — 设计文档

> 创建: 2026-04-12 21:28:10
> 状态: 设计完成，待计划

## §0 背景与目标

edu-cloud 在 AI Agent/知识图谱/自适应学习方面远超好分数，但**教学侧业务骨架严重不完整**——作业、教学、教研、教务 4 个模块前端页面为零，学情/报告/基础信息覆盖度不足。好分数（haofenshu-clone，`~/haofenshu-clone/`）是一个完整的 K12 教育 SaaS 平台复刻，拥有 8 个完整业务模块、45 个前端页面、28 张数据库表、9 个后端路由模块。

**目标**：将好分数的业务完整度结构化融入 edu-cloud，同时保留 edu-cloud 的技术优势（AI Agent、知识图谱、RBAC、PostgreSQL、多校联考）。不是移植代码，是复刻业务骨架和 6 个架构模式。

**参考源**：
- 好分数前端：`~/haofenshu-clone/frontend/`（Nuxt 3 + Element Plus，45 页面）
- 好分数后端：`~/haofenshu-clone/server/`（Express + SQLite，28 表）
- 好分数文档：`~/haofenshu-clone/docs/`（architecture.md / business-logic.md / route-analysis.md）

## §1 决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 范围 | 8 模块全量铺开，架构先行 | 先把骨架打扎实 |
| 前端框架 | **Nuxt 3 + Element Plus** | 页面数到 45+ 时文件路由优势显著；Element Plus 是中国教育 SaaS 行业标准；AI 开发迁移成本可忽略 |
| 后端路由 | 保持 RESTful `/api/v1/{module}/` | edu-cloud 已有 182+ 端点用此风格，好分数的 `/proxy-*` 是逆向兼容产物 |
| 数据模型 | 扩展现有 79 张表 | 一套 schema + 一套 ORM + 一套 migration 链；禁止多套方案并存 |
| 种子数据 | 移植好分数种子并适配 edu-cloud schema | 52 真实学生 + 90 合成考试，所有模块有逼真演示数据 |
| 现有组件 | 全部迁移，统一 Element Plus 风格 | AI 浮窗 + 知识图谱 + 答题卡编辑器 + Studio 全部保留 |
| 导航架构 | 顶部模块导航 + 二级蓝条 + 后端驱动动态菜单 | 教育行业验证过的交互模式；10 种角色差异由后端菜单 API 控制 |

> **F013 (R3) 全局漂移修正说明**（2026-04-13 追加）：
> 本设计文档 Phase 1 部分已被 `2026-04-12-haofenshu-phase1-plan.md` 取代，以下章节与现实代码库/plan 不一致，以 plan.md 为准：
> - §2 目录 `edu-cloud/frontend/` → Phase 1 实际在 `edu-cloud/frontend-nuxt/`（plan.md INV-01：不修改现有 `frontend/`）
> - §3 menu_configs `roles TEXT[]`（PostgreSQL ARRAY）→ Phase 1 实际用 JSON（F005 R1：兼容 SQLite smoke test）
> - §4 useApi `login(phone, password)` → plan.md Task 6 按后端 `/auth/login` 实际参数 `username + password`
> - §4 useApi `switchRole(roleIndex)` → plan.md Task 6 按后端 `/auth/switch-role` 实际参数 `role_id`（F007 R1）
> - §4 useApi 示例 analytics 路径 `/analytics/power-options` / `/analytics/class/overview` / `/analytics/class/knp` / `/analytics/student/list` / `/analytics/student/trends` → 真实后端路由为 `/analytics/exam/{id}/summary` / `/distribution` / `/grade-aggregates` / `/report/trend/{grade|class|student}`，见 `src/edu_cloud/modules/analytics/router.py`；power-options 是 Phase 2 工作
> - §4 useApi `/knowledge/tree` → 真实后端路由为 `/knowledge-tree/graph`
> - §4 useApi `/study/*` 路由 → Phase 3 工作，Phase 1 useApi 不包含这些方法
> - §5 RankComputeService "写入 exam_scores.rank_in_class/rank_in_grade" → 实际表名为 `ExamResult`（见 `exam/models.py`），已在 plan.md Task 1 更正
> - §6 Phase 1 交付物 #9 "exam_scores 加 rank 字段" → 应为 `ExamResult 加 rank 字段`
> - §6 Phase 1 交付物 #6 "PowerFilter 挂载点" → plan Task 10 提供本地 stub，Phase 2 才真正接入后端
>
> Phase 2/3 将对本文档做全局重写；Phase 1 期间本文档仅作为业务参考，所有执行依据以 plan.md 为准。

> **F002 R1 范围扩展说明**（2026-04-13 追加）：
> 原 Batch 1 范围仅包含"新增 `/api/v1/menus`"（plan.md INV-02）。Code Review R1 识别 commit 3488b52 意外挂载了 `conduct_admin_router`（28 个 `/api/v1/conduct/classes/*` 端点），属 behavior_change。用户裁决：**批准保留并扩大 Batch 1 范围**。
> - 追认 commit: `3488b52798f423830037d94b36f277fd7c7afc28`
> - 新增暴露路由: `GET/POST/PUT/DELETE /api/v1/conduct/classes/{class_id}/*`（已在 `~/CLAUDE.md` "conduct 管理端点" 段描述，106 conduct tests 已覆盖）
> - plan.md INV-02 已同步追加此变更条目
> - 完整审批记录见 `docs/plans/2026-04-12-haofenshu-phase1-review-report-batch1-r2.md` 行为变更审批记录表

> **Batch 2 漂移与改进说明**（2026-04-13 追加）：
> Batch 2 实施（Task 4-9，commits `08d86f0..674cd99`）期间发生 8 项偏离 plan 的改进，均在审查交接单 `docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2.md` 记录。本段列出对未来工作有持续影响的漂移条目：
>
> 1. **Nuxt 3 锁定（非 Nuxt 4）**：`npx nuxi@latest init` 默认下载 Nuxt 4.4 minimal，回退到 Nuxt 3.17.7 以匹配 plan 标题「Nuxt 3」和目录结构（`frontend-nuxt/composables/` 不带 `app/` 前缀）。**持续影响**：Phase 2/3 若要升 Nuxt 4 需独立 brainstorming（目录结构会变更，影响全部 composables/layouts/pages 路径）。
> 2. **Vitest 2→3 peer 升级**：`@nuxt/test-utils@^3.14.4` 要求 vitest `^3.x`，package.json 从 `^2.1.5` 升到 `^3.2.0`。**持续影响**：Batch 3 和 Phase 2/3 的前端测试须按 vitest 3.x 语义写（`vi.hoisted` / `vi.mocked` / 等）。
> 3. **SSR 环境 guard 统一**：plan 骨架用 `import.meta.client`，Vitest+happy-dom 下为 undefined 导致 `setUser` 不写 localStorage。改为 `typeof window !== 'undefined'`（语义等价，universal 可用）。**持续影响**：Phase 2/3 Nuxt 侧客户端 guard 统一用此写法。
> 4. **Pinia store 归一化逻辑**：`applyLoginResponse` / `applySwitchRoleResponse` / `restoreFromStorage` 的归一化（is_primary 选主 + fallback roles[0] + JSON 损坏容错）成为 Phase 2/3 扩展 store 的模式参考，不要重新实现。
> 5. **useApi 27 方法 + 5 个 Phase 2/3 stub**：已对齐后端真实路由（analytics 11 / knowledge `/knowledge-tree/graph` / bank `/bank/questions` 等），与 design §4 原示例有偏差（详见 F013 R3 漂移段）。**持续影响**：Phase 2/3 新增 API 方法必须先读 `src/edu_cloud/modules/*/router.py` 确认真实路径。
> 6. **useMenus activeModule startsWith 理论误匹配（test_debt）**：`route.path.startsWith(c.path)` 对 `/exam/list` 与 `/examples` 理论冲突。当前种子数据（子菜单都是 `/module/sub` 二级结构）不触发。**持续影响**：Phase 2 填充子页面前须加分隔符（如 `c.path + '/'` 或等值匹配）。
> 7. **Batch 2 独立 Gate 代码路径 PASS**：端到端受 WSL 后端 hot-reload 失效（baseline 问题）阻塞 Step ③④，降级为代码路径 PASS + Gate 待 Reviewer 最终裁决。**持续影响**：Batch 3 端到端验证必须先修复 WSL hot-reload 或采用 `--reload=False` 静态启动。
> 8. **CLAUDE.md doc-sync 进度追加**：每个 Task commit 时更新 CLAUDE.md 项目段。**持续影响**：Phase 2/3 Executor 须继续此模式，doc-sync-guard 要求。

## §2 前端项目结构

```
edu-cloud/frontend/                     # Nuxt 3 项目根
├── nuxt.config.ts                      # SSR: false, Element Plus, Pinia
├── composables/
│   ├── useApi.ts                       # 统一 API 客户端（单入口，按域分组）
│   ├── usePowerOptions.ts              # 级联筛选器（年级→班级→学科→考试）
│   ├── useMenus.ts                     # 动态菜单加载 + 模块切换
│   └── useAiChat.ts                    # AI 浮窗 SSE streaming
├── middleware/
│   └── auth.global.ts                  # 全局路由守卫（cookie token）
├── layouts/
│   ├── default.vue                     # 主布局：顶部导航 + 二级蓝条 + 内容区
│   ├── fullscreen.vue                  # 全屏布局：阅卷/批改/监控（无 chrome）
│   └── auth.vue                        # 登录页布局（无导航）
├── stores/
│   ├── auth.ts                         # 用户 + 角色 + 菜单 + 角色切换
│   └── context.ts                      # 当前学校/年级/学期上下文
├── pages/
│   ├── index.vue                       # 重定向到 /home 或 /login
│   ├── login.vue                       # 登录页（layout: auth）
│   ├── home.vue                        # 首页（模块卡片，动态渲染可见模块）
│   ├── exam/                           # 考试管理（5 页）
│   │   ├── list.vue                    #   考试列表
│   │   ├── quiz.vue                    #   测验列表
│   │   ├── grading.vue                 #   阅卷任务
│   │   ├── answercard.vue              #   答题卡工具
│   │   └── statistics.vue              #   考试统计
│   ├── report/                         # 分析报告（6 页）
│   │   ├── exam.vue                    #   考试报告
│   │   ├── contrast.vue                #   班级对比
│   │   ├── custom.vue                  #   自定义分析
│   │   ├── table.vue                   #   自定义表格
│   │   ├── level-score.vue             #   等级赋分
│   │   └── config.vue                  #   指标配置
│   ├── study/                          # 学情分析（4 页）
│   │   ├── dashboard.vue               #   数据看板
│   │   ├── class.vue                   #   班级学情
│   │   ├── student.vue                 #   学生学情
│   │   └── layer.vue                   #   分层学情
│   ├── work/                           # 作业（4 页）
│   │   ├── list.vue                    #   作业列表
│   │   ├── publish.vue                 #   布置作业
│   │   ├── scan.vue                    #   扫描作业
│   │   └── sync.vue                    #   同步作业
│   ├── lesson/                         # 教学（4 页）
│   │   ├── console.vue                 #   精准教学台
│   │   ├── after-exam.vue              #   考后分析
│   │   ├── resources.vue               #   备课资源
│   │   └── space.vue                   #   我的空间
│   ├── research/                       # 教研（7 页）
│   │   ├── questions.vue               #   题库选题
│   │   ├── paper-builder.vue           #   结构组卷
│   │   ├── group-prep.vue              #   集体备课
│   │   ├── knowledge.vue               #   知识体系
│   │   ├── plan.vue                    #   教学计划
│   │   ├── radar.vue                   #   考情雷达
│   │   └── school-resources.vue        #   校本资源
│   ├── baseinfo/                       # 基础信息（7 页）
│   │   ├── students.vue                #   学生信息
│   │   ├── teachers.vue                #   教师信息
│   │   ├── grades.vue                  #   年级管理
│   │   ├── records.vue                 #   人员动态
│   │   ├── schedule.vue                #   教师任课表
│   │   ├── selected-exam.vue           #   选考管理
│   │   └── vip.vue                     #   版本权益
│   ├── academic/                       # 教务（5 页）
│   │   ├── semester.vue                #   学期管理
│   │   ├── timetable.vue               #   课表
│   │   ├── course-selection.vue        #   选课
│   │   ├── exam-schedule.vue           #   考试安排
│   │   └── score-manage.vue            #   成绩管理
│   └── knowledge-tree/                 # edu-cloud 独有
│       └── index.vue                   #   知识图谱
├── components/
│   ├── ai/                             # AI 浮窗（全局悬浮）
│   │   ├── AiFloatingButton.vue
│   │   └── AiSlidePanel.vue
│   ├── card-editor/                    # 答题卡编辑器
│   │   └── CardEditor.vue
│   ├── knowledge-tree/                 # 知识图谱（AntV G6）
│   │   ├── ConceptMapPanel.vue
│   │   └── ... (现有 10+ 组件)
│   ├── common/                         # 通用业务组件
│   │   ├── PowerFilter.vue             #   级联筛选器 UI
│   │   ├── StatCards.vue               #   统计卡片组
│   │   └── ScoreDistribution.vue       #   分数段分布图
│   └── shell/                          # 布局壳层
│       ├── TopNav.vue                  #   顶部 8 模块导航
│       ├── SubNav.vue                  #   二级蓝条
│       └── UserDropdown.vue            #   用户菜单
```

设计要点：
- `pages/` 完全复刻好分数 8 模块目录，`knowledge-tree/` 是 edu-cloud 独有新增
- 4 个核心 composable（useApi / usePowerOptions / useMenus / useAiChat）覆盖横切关注点
- `components/common/` 提取好分数页面中重复的 UI 模式
- 三种 layout 覆盖所有场景

## §3 动态菜单系统

### 数据模型

新增 `menu_configs` 表：

```sql
CREATE TABLE menu_configs (
    id SERIAL PRIMARY KEY,
    code VARCHAR(32) NOT NULL,          -- 模块代码: exam, report, study...
    name VARCHAR(64) NOT NULL,          -- 显示名: 阅卷, 分析, 学情...
    icon VARCHAR(32),                   -- Element Plus 图标名
    sort INTEGER NOT NULL DEFAULT 0,    -- 排序权重
    parent_id INTEGER REFERENCES menu_configs(id),  -- 二级菜单指向父级
    path VARCHAR(128),                  -- 前端路由: /exam/list
    roles TEXT[] NOT NULL DEFAULT '{}', -- 可见角色: {teacher, principal, ...}
    requires_module VARCHAR(32),        -- 依赖学校模块开关（复用 school_modules）
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### API

```
GET /api/v1/menus
```

返回当前用户角色可见的菜单树（已按 roles + school_modules 过滤）：

```json
{
  "menus": [
    {
      "code": "exam",
      "name": "阅卷",
      "icon": "document",
      "sort": 1,
      "children": [
        { "name": "考试列表", "path": "/exam/list", "icon": "list" },
        { "name": "测验列表", "path": "/exam/quiz", "icon": "edit-pen" }
      ]
    }
  ]
}
```

### 前端 composable

```typescript
// composables/useMenus.ts
export function useMenus() {
  const authStore = useAuthStore()
  
  async function loadMenus() {
    const api = useApi()
    const res = await api.getMenus()
    authStore.setMenus(res.menus)
  }
  
  const activeModule = computed(() => {
    const route = useRoute()
    return authStore.menus.find(m => 
      m.children?.some(c => route.path.startsWith(c.path))
    ) || null
  })
  
  const currentSubMenus = computed(() => activeModule.value?.children || [])
  
  return { loadMenus, activeModule, currentSubMenus }
}
```

与好分数的区别：
- 好分数用 config.js 的 54 条 PATH_MAP 硬编码，我们用数据库表支持运行时修改
- 好分数用 `extra.filter` 函数做 VIP 过滤，我们用 `roles[]` + `requires_module` 双重过滤
- 好分数单角色，我们支持角色切换——切角色后重新 `loadMenus()`

## §4 统一 API 客户端

### useApi composable

单入口，按域分组，TypeScript 类型安全：

```typescript
// composables/useApi.ts
export function useApi() {
  const token = useCookie('edu_token')
  
  async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
    return $fetch(`/api/v1${path}`, {
      headers: { Authorization: `Bearer ${token.value}` },
      ...opts
    })
  }

  return {
    // Auth
    login: (phone, password) => request('/auth/login', { method: 'POST', body: { phone, password } }),
    switchRole: (roleIndex) => request('/auth/switch-role', { method: 'POST', body: { roleIndex } }),
    
    // Menu
    getMenus: () => request<MenuResponse>('/menus'),
    
    // Exam
    getExams: (params) => request('/exams', { query: params }),
    getExam: (id) => request(`/exams/${id}`),
    createExam: (data) => request('/exams', { method: 'POST', body: data }),
    
    // Analysis
    getPowerOptions: (params) => request('/analytics/power-options', { query: params }),
    getClassOverview: (params) => request('/analytics/class/overview', { method: 'POST', body: params }),
    getClassKnpList: (params) => request('/analytics/class/knp', { method: 'POST', body: params }),
    getStudentAnalysis: (params) => request('/analytics/student/list', { method: 'POST', body: params }),
    getStudentTrends: (params) => request('/analytics/student/trends', { method: 'POST', body: params }),
    
    // Study
    getSchoolDashboard: () => request('/study/dashboard'),
    getClassStudy: (params) => request('/study/class', { method: 'POST', body: params }),
    getStudentStudy: (params) => request('/study/student', { method: 'POST', body: params }),
    
    // Homework
    getHomeworkList: (params) => request('/homework/tasks', { query: params }),
    createHomework: (data) => request('/homework/tasks', { method: 'POST', body: data }),
    getSubmissions: (taskId) => request(`/homework/tasks/${taskId}/submissions`),
    gradeSubmissions: (taskId, grades) => request(`/homework/tasks/${taskId}/grade`, { method: 'POST', body: { grades } }),
    
    // Research
    getKnowledgeTree: (subjectId) => request('/knowledge/tree', { query: { subjectId } }),
    searchQuestions: (params) => request('/bank/questions', { query: params }),
    generatePaper: (config) => request('/bank/paper/generate', { method: 'POST', body: config }),
    
    // BaseInfo
    getStudents: (params) => request('/students', { query: params }),
    getTeachers: (params) => request('/teachers', { query: params }),
    getGrades: () => request('/grades'),
    
    // AI
    chatStream: (message, sessionId?) => 
      $fetch('/api/v1/ai/chat', { method: 'POST', body: { message, sessionId }, responseType: 'stream' }),
    
    // Raw
    raw: request,
    token,
  }
}
```

### usePowerOptions 级联筛选器

复刻好分数分析模块核心 UX 模式——一次加载级联树，前端 computed 联动：

```typescript
// composables/usePowerOptions.ts
export function usePowerOptions() {
  const api = useApi()
  const tree = ref<PowerOption[]>([])
  const examInfoMap = ref<Record<string, ExamInfo>>({})
  
  const selectedGrade = ref('')
  const selectedClass = ref('')
  const selectedSubject = ref('')
  const selectedExamIds = ref<string[]>([])
  
  const gradeOptions = computed(() => tree.value.map(g => g.grade))
  const classOptions = computed(() => {
    const grade = tree.value.find(g => g.grade === selectedGrade.value)
    return grade?.classes.map(c => c.class) || []
  })
  const subjectOptions = computed(() => {
    const grade = tree.value.find(g => g.grade === selectedGrade.value)
    const cls = grade?.classes.find(c => c.class === selectedClass.value)
    return cls?.subjects.map(s => s.subject) || []
  })
  const examOptions = computed(() => {
    const grade = tree.value.find(g => g.grade === selectedGrade.value)
    const cls = grade?.classes.find(c => c.class === selectedClass.value)
    const subj = cls?.subjects.find(s => s.subject === selectedSubject.value)
    return (subj?.examids || []).map(id => ({ id, ...examInfoMap.value[id] }))
  })
  
  const analysisParams = computed<AnalysisParams>(() => ({
    clazz: selectedClass.value,
    subject: selectedSubject.value,
    examids: selectedExamIds.value,
    isTeach: false,
  }))
  
  async function load(examType?: number, year?: number) {
    const res = await api.getPowerOptions({ examType, year })
    tree.value = res.powerOptions
    examInfoMap.value = res.examInfoMap
    if (tree.value.length) selectedGrade.value = tree.value[0].grade
  }
  
  return {
    load, tree, examInfoMap,
    selectedGrade, selectedClass, selectedSubject, selectedExamIds,
    gradeOptions, classOptions, subjectOptions, examOptions,
    analysisParams,
  }
}
```

PowerFilter 组件封装一次，report/study/lesson 等所有需要级联筛选的页面复用。

## §5 后端数据模型扩展

### 已有不需动的

| 好分数表 | edu-cloud 对应 | 状态 |
|---------|---------------|------|
| schools | schools + school_settings + school_modules | 更完整 |
| users / user_roles | users + user_roles (10 角色 RBAC) | 更完整 |
| grades / classes | grades + classes | 已有 |
| students | students | 已有 |
| exams / exam_subjects | exams + exam_subjects | 已有 |
| questions / student_answers | questions + student_answers | 已有 |
| knowledge_points | concept_graph_nodes (3 层+图谱) | 更完整 |
| question_bank | question_bank | 已有 |
| homework_tasks / homework_submissions | homework_tasks + homework_submissions | 已有 |
| report_configs | score_segment_config | 已有 |

### 需要扩展的字段

> **F010 (R2) 修正**：原草稿写的是 `exam_scores` 和 `exams.exam_type`，但现有代码库中：
> - 结果表名为 `ExamResult`（`src/edu_cloud/modules/exam/models.py:68`），不是 `exam_scores`
> - `Exam.exam_type` 已存在（`exam/models.py:28`），无需再次添加
>
> 最终以 plan.md Task 1 为准：仅在 `ExamResult` 加 `rank_in_class` / `rank_in_grade`。

```sql
-- [superseded — 仅保留历史记录] 旧草稿写的是 exam_scores，实际表名为 ExamResult
-- ALTER TABLE exam_scores ADD COLUMN rank_in_class INTEGER;
-- ALTER TABLE exam_scores ADD COLUMN rank_in_grade INTEGER;

-- 正确版本（见 plan.md Task 1 Step 3）:
-- ExamResult 加排名预计算字段
ALTER TABLE exam_result ADD COLUMN rank_in_class INTEGER;
ALTER TABLE exam_result ADD COLUMN rank_in_grade INTEGER;

-- [superseded] exams.exam_type 已存在于代码库，无需重复 migration
-- ALTER TABLE exams ADD COLUMN exam_type VARCHAR(16) DEFAULT 'regular';
```

### 需要新增的表

**class_analysis — 班级维度预聚合**：

```sql
CREATE TABLE class_analysis (
    id SERIAL PRIMARY KEY,
    exam_id INTEGER NOT NULL REFERENCES exams(id),
    exam_subject_id INTEGER NOT NULL REFERENCES exam_subjects(id),
    class_id INTEGER NOT NULL REFERENCES classes(id),
    avg_score NUMERIC(6,2),
    max_score NUMERIC(6,2),
    min_score NUMERIC(6,2),
    pass_rate NUMERIC(5,2),
    excellent_rate NUMERIC(5,2),
    student_count INTEGER,
    score_distribution JSONB,
    common_wrong_questions JSONB,
    knowledge_mastery JSONB,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (exam_id, exam_subject_id, class_id)
);
```

**student_analysis — 学生维度预聚合**：

```sql
CREATE TABLE student_analysis (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id),
    exam_id INTEGER NOT NULL REFERENCES exams(id),
    total_score NUMERIC(7,2),
    rank_in_class INTEGER,
    rank_in_grade INTEGER,
    subject_scores JSONB,
    weak_knowledge JSONB,
    improvement_trend JSONB,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (student_id, exam_id)
);
```

**student_knp_mastery — 学生知识点掌握度矩阵**：

```sql
CREATE TABLE student_knp_mastery (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id),
    exam_id INTEGER NOT NULL REFERENCES exams(id),
    knp_id INTEGER NOT NULL,
    stu_rate NUMERIC(4,3),
    class_rate NUMERIC(4,3),
    grade_rate NUMERIC(4,3),
    UNIQUE (student_id, exam_id, knp_id)
);
```

**menu_configs — 动态菜单**：见 §3。

### 需要新增的后端 Service

| Service | 职责 | 关键方法 |
|---------|------|---------|
| AnalysisComputeService | 考试完成后计算预聚合 | compute_class_analysis(), compute_student_analysis(), compute_knp_mastery() |
| PowerOptionsService | 构建级联筛选树 | get_power_options(user, exam_type, year) — 按角色过滤可见范围 |
| ExamCompositeKeyService | examids 复合键编解码 | encode(exam_id, subject_id, exam_subject_id) ↔ decode("123:4:5") |
| RankComputeService | 排名预计算 | compute_ranks(exam_id) — 写入 exam_scores.rank_in_class/rank_in_grade |
| MenuService | 动态菜单 CRUD + 查询 | get_menus_for_user(user) — 按角色+模块过滤 |
| TeachingPlanService | 教学计划 CRUD | create/list/update/delete |
| TimetableService | 课表管理 | create/list/update |
| ResourceService | 教研资源库 | upload/search/download |
| CollectivePrepService | 集体备课 | create/list/complete |
| SemesterService | 学期管理 | create/list/set_current |

计算触发时机：考试状态变为 completed 时，通过 arq worker 异步触发 AnalysisComputeService + RankComputeService，结果写入预聚合表。前端查询直接读预聚合表。

### 种子数据移植

```python
# scripts/seed_haofenshu.py
# 1. 读好分数 seed-real.js + seed-full.js
# 2. 转为 edu-cloud SQLAlchemy model
# 3. 映射：school/students/exams/scores/knowledge_points
# 4. 生成预聚合：class_analysis + student_analysis + student_knp_mastery
# 5. 生成 menu_configs 种子（8 模块 45 子菜单）
```

## §6 Phase 分拆

### Phase 1：架构基座

交付物：
1. Nuxt 3 项目初始化（Element Plus + Pinia + CSS 变量主题）
2. 三种 layout（default / fullscreen / auth）
3. 动态菜单系统（menu_configs 表 + API + useMenus + TopNav/SubNav）
4. useApi composable（全量方法签名，对接已有后端端点）
5. usePowerOptions composable + PowerFilter 组件
6. 8 模块 × 45 页面 stub（标题 + 面包屑 + PowerFilter 挂载点）
7. home.vue（模块卡片入口）+ login.vue（对接 auth API）
8. 后端 4 张新表 migration
9. exam_scores 加 rank 字段 migration
10. MenuService + GET /api/v1/menus 端点
11. menu_configs 种子数据

完成标准：
- `npx nuxt dev --port 3000` 启动后可登录
- 登录后顶部 8 模块导航按角色过滤显示
- 点任意模块跳转到 stub 页面，二级蓝条正确显示
- `pytest` 全绿（现有 1582 + 新增 menu 测试）
- Alembic migration 可正向执行

不包含：业务页面实现、AI 组件迁移、种子数据（除 menu 外）

### Phase 2：现有功能迁移

交付物：
1. 考试模块：ExamListPage → exam/list.vue 等
2. 分析模块：Analytics* → report/exam.vue 等
3. 阅卷/批改：GradingTasksPage → exam/grading.vue、MarkingPage（fullscreen layout）
4. 答题卡编辑器：CardEditor 全套 → components/card-editor/（Element Plus）
5. 知识图谱：10+ 组件 → components/knowledge-tree/（保留 G6，壳换 Element Plus）
6. AI 浮窗：AiFloatingButton + AiSlidePanel → components/ai/（useAiChat composable）
7. 基础信息：Schools/Settings/Assignments/Selections → baseinfo/
8. 学校设置/角色切换

完成标准：
- 现有 21 个页面功能全部可用
- AI 浮窗可发消息、收流式回复
- 知识图谱可渲染
- 答题卡编辑器可编辑导出
- 无 Naive UI 残留

### Phase 3：新模块填充

| 模块 | 页面 | 后端新增 | 关键能力 |
|------|------|---------|---------|
| work/ | 4 | HomeworkService 扩展 | 布置→提交→批改→统计闭环 |
| lesson/ | 4 | TeachingPlanService, ResourceService | 精准教学台 + 考后分析 + 备课资源 |
| research/ | 7 | PaperGenerateService, CollectivePrepService | 题库 + 5 种组卷 + 集体备课 |
| academic/ | 5 | TimetableService, SemesterService | 学期 + 课表 + 选课 + 考试安排 |
| study/ 补全 | 4 | PowerOptionsService, AnalysisComputeService | 看板 + 班级/学生/分层学情 |
| report/ 补全 | 3 | ClassComparisonService, LevelScoreService | 对比 + 赋分 + 自定义 |
| baseinfo/ 补全 | 4 | StudentCrudService, TeacherCrudService | CRUD + 年级 + 人员动态 |
| 种子数据 | - | seed_haofenshu.py | 52 学生 + 90 考试 + 51840 成绩 |

### Phase 间依赖

```
Phase 1 (架构基座)
   ├── Phase 2 (现有功能迁移)     # 可并行
   └── Phase 3 (新模块填充)       # 可并行
```

Phase 2 和 Phase 3 在 Phase 1 完成后可并行推进。

### 规模估算

| Phase | 前端文件 | 后端文件 | Migration |
|-------|---------|---------|-----------|
| 1 | ~60 | ~8 | 2 |
| 2 | ~30 | 0 | 0 |
| 3 | ~45 | ~25 | 0 |

## §7 吸收的 6 个架构模式

1. **页面按业务域分目录**：8 模块文件夹制，目录即模块
2. **统一 API composable**：单入口 useApi()，30+ 方法按域分组
3. **后端驱动动态菜单**：menu_configs 表 + roles/module 双重过滤，前端零硬编码
4. **级联筛选器**：usePowerOptions 一次加载树，computed 联动，PowerFilter 组件复用
5. **预聚合表 + 排名预计算**：考试完成时异步计算，前端直读，不做实时聚合
6. **全屏工作区模式**：fullscreen layout 隐藏所有 chrome，阅卷/批改最大化

## §8 旧前端处置

现有 `edu-cloud/frontend/`（Vite + Vue 3 + Naive UI）在 Phase 1 完成后**整体替换**为新 Nuxt 3 项目。具体流程：

1. Phase 1 在 `edu-cloud/frontend-nuxt/` 下构建新项目
2. Phase 2 将现有页面逐个迁移到新项目
3. Phase 2 完成后，`frontend/` 重命名为 `frontend-legacy/`（保留 30 天备查），`frontend-nuxt/` 重命名为 `frontend/`
4. 30 天后删除 `frontend-legacy/`

过渡期两个前端可以同时运行在不同端口，共享同一后端。

## §9 不变量

以下 edu-cloud 已有能力不因本次复刻而改变或削弱：

- 10 角色 RBAC + DataScope 数据隔离
- AI Agent 体系（56 工具 / 5 Phase / 跨会话记忆）
- 知识图谱可视化（AntV G6 力导向图）
- 自适应学习（BKT 引擎 + 路径规划）
- 多校联考能力
- PostgreSQL + Alembic migration 链
- 后端 RESTful API 风格（/api/v1/）
- arq + Redis 异步任务
