# edu-agent 演进设计：专用数据层 + 工作流引擎 + 工具重组

> 设计时间：2026-04-04 15:16
> 前置：edu-agent 内核已完成（30 Tasks / 39 tools / 1124 tests / GPT 15 轮审查通过）
> 范围：第一期 W1（考后分析）+ W3（学情画像）+ W6（异常巡检）
> GPT 补充审查：2026-04-04，10 个 HIGH + 7 个 MED 全部吸收

> [2026-04-05 13:49:33 实现完成] Commits: 1a0c1f2..26a83b5

## §0 设计决策记录

| # | 决策 | 结论 | 理由 |
|---|------|------|------|
| D1 | 架构模式 | 双模式（工作流 + 自由查询） | 已知场景走确定性轨道（快+准+省），未知问题保留 LLM 灵活性 |
| D2 | 权限架构 | DataScope（硬边界 + 软规则） | 硬边界代码层不可突破，软规则校级管理员可配置 |
| D3 | 数据策略 | 预计算 + 复用现有表 | 避免双写，Agent 专用表只放现有 pipeline 不产出的数据 |
| D4 | 工具策略 | 域分组 + 动态加载 | 每次对话只加载 1-2 个域（8-12 工具），不把全量扔给 LLM |
| D5 | 角色人格 | 教师/家长双 Persona | 不同工具集 + 工作流 + 展示逻辑 + Prompt 风格 |
| D6 | 工作流引擎 | 持久化状态机 + 幂等 | GPT 审查指出：无状态机/重试/补偿 = 不可靠。必须有 workflow_runs |
| D7 | 默认权限 | fail-closed | GPT 审查指出：无明确允许 = 拒绝。家长/临时权限安全底线 |
| D8 | 预计算表结构 | 常用键做列 + JSON 放稀疏数据 | GPT 审查指出：大 JSON 不可查询 |

## §1 DataScope（数据作用域）

### 核心原则

Agent 从登录那一刻起看到的是一个被裁剪过的数据世界。DataScope 在会话创建时一次性计算，全程不可放大。

### 两层架构

**硬边界（代码层，不可突破）：**

| 规则 | 说明 |
|------|------|
| 跨校隔离 | 永远不能看到其他学校的数据 |
| 家长锁定 | 家长永远只看自己孩子（通过 guardian_student_links） |
| 模块禁用 | school_modules 关掉的模块，工具直接不存在 |
| fail-closed | 无明确允许 = 拒绝（D7） |

**软规则（校级管理员可配置）：**

| 配置项 | 默认值 | 配置者 |
|-------|-------|-------|
| parent_can_see_ranking | false | principal |
| parent_can_see_distribution | false | principal |
| subject_teacher_cross_class | false | academic_director |
| grade_leader_cross_grade | false | principal |
| homeroom_teacher_cross_class | false | academic_director |
| agent_enabled_roles | 全教职 | principal |
| agent_write_enabled | true | principal |

### DataScope 数据结构

```python
@dataclass(frozen=True)  # 不可变
class DataScope:
    # ── 身份 ──
    user_id: str
    school_id: str
    role: str
    
    # ── 可见边界（从 user_roles + teacher_assignments 推导）──
    visible_class_ids: list[str] | None     # None = 不限（校级以上）
    visible_subject_codes: list[str] | None
    visible_grade_ids: list[str] | None
    visible_student_ids: list[str] | None   # 家长: [child_id]，教师: None
    district_ids: list[str] | None          # district_admin 专用
    
    # ── 操作边界（从 capabilities + school_settings 推导）──
    can_write: bool
    can_see_rankings: bool
    can_cross_school: bool
    
    # ── Agent 人格 ──
    persona: str  # "teacher_assistant" | "parent_advisor" | "admin_analyst"
    
    # ── 版本控制 ──
    version: int          # 递增版本号
    computed_at: datetime  # 计算时间
```

### 8 角色推导规则

| 角色 | visible_classes | visible_subjects | visible_students | district_ids | persona |
|------|----------------|-----------------|-----------------|-------------|---------|
| platform_admin | None（全部跨校） | None | None | None | admin_analyst |
| district_admin | None（管辖区内） | None | None | [district_ids] | admin_analyst |
| principal | None（本校全部） | None | None | None | school_leader |
| academic_director | None（本校全部） | None | None | None | teacher_assistant |
| grade_leader | 本年级全部班 | None | None | None | teacher_assistant |
| homeroom_teacher | 自己班 + 任教班 | 全科(自己班) + 任教科 | None | None | teacher_assistant |
| subject_teacher | 任教班 | 任教科目 | None | None | teacher_assistant |
| parent | None | None | [child_ids] | None | parent_advisor |

**班主任特殊逻辑（GPT #C 指出）：** visible_class_ids 和 visible_subject_codes 不是独立列表，而是 `(class_id, subject_code)` pair 矩阵。班主任对自己班有全科权限，对其他任教班只有任教科目权限。从 teacher_assignments 推导。

### ScopedQuery 统一过滤层

```python
class ScopedQuery:
    """所有数据访问的统一入口。工具代码里看不到任何权限逻辑。"""
    
    def __init__(self, db: AsyncSession, scope: DataScope): ...
    
    async def execute(self, query: Select) -> Result:
        """自动注入 WHERE 条件：school_id + class_id + student_id + subject_code"""
        query = self._inject_scope(query)
        return await self.db.execute(query)
    
    def _inject_scope(self, query: Select) -> Select:
        # 1. school_id 强制（除 platform_admin）
        # 2. district_ids（district_admin 专用）
        # 3. class_ids / subject_codes / student_ids 按角色注入
        # 4. 不可放大——参数中的 class_id 必须在 visible_class_ids 内
```

### DataScope 版本失效（GPT #C-4 指出）

| 事件 | 影响 | 处理 |
|------|------|------|
| student.transferred | 班级成员变化 | 相关 scope 版本 +1，活跃会话降级为只读 |
| assignment.changed | 教师排课变化 | 教师 scope 重算 |
| role.changed | 角色变更 | 强制结束会话 |
| semester.switched | 学期切换 | 全校所有 scope 失效 |

实现方式：scope 带 version 字段，后台监听变更事件更新 version 表，每次 tool 调用前检查 version 是否匹配。不匹配 → 重算 scope 或终止会话。

### 前置数据模型补全（GPT #I-1 指出）

**新增表：`guardian_student_links`**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| guardian_user_id | FK→users | 家长 |
| student_id | FK→students | 孩子 |
| relationship | enum | father/mother/guardian/other |
| school_id | FK→schools | 隔离 |
| is_primary | bool | 主监护人 |
| created_at | timestamp | |

家长的 DataScope.visible_student_ids 从此表推导。

## §2 预计算数据模型

### 复用原则（GPT #B-1 指出）

| 数据 | 现有表 | 策略 |
|------|-------|------|
| 知识点掌握度 | student_knowledge_mastery（pipeline 产出） | **复用**，不新建 |
| 错题本 | student_error_books（pipeline 产出） | **复用** |
| 错误模式 | student_error_patterns（pipeline 产出） | **复用** |
| 成绩快照 | student_exam_snapshots（pipeline 产出） | **复用**，扩展字段 |
| 考试分析 | 无 | **新建** exam_analysis_snapshot |
| 班级报告 | 无 | **新建** class_exam_report |
| Agent 发现 | 无 | **新建** agent_findings |
| Agent 待办 | 无 | **新建** agent_tasks |
| 工作流执行记录 | 无 | **新建** workflow_runs + workflow_steps |

### 新增 Agent 专用表（5 张 + 2 张工作流元数据）

**表 1：`exam_analysis_snapshot`（考试分析快照）**

> GPT #B-2 指出：常用过滤键做列，JSON 只放稀疏数据

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| exam_id | FK→exams | 考试 |
| school_id | FK→schools | 隔离 |
| snapshot_type | enum | school_overview / subject_detail / grade_aggregate |
| target_type | string | school / grade / subject |
| target_id | string | 对应 grade_id 或 subject_id（school_overview 为 null） |
| subject_code | string | 可空，subject_detail 时填 |
| semester | string | 学期标识 |
| version | int | 同一 exam 可重算，版本递增 |
| status | enum | computing / ready / stale |
| metrics | JSON | 稀疏指标（均分/最高/最低/中位数/标准差/通过率/薄弱题 TOP5/异常列表） |
| computed_at | timestamp | |

**表 2：`class_exam_report`（班级考试报告）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| exam_id | FK | 考试 |
| class_id | FK | 班级 |
| school_id | FK | 隔离 |
| grade_rank | int | 班级在年级中的排名 |
| class_avg | float | 班均分 |
| grade_avg | float | 年级均分 |
| vs_last_exam | float | 与上次考试的均分变化 |
| metrics | JSON | 进退步学生/薄弱科目/需关注列表 |
| version | int | |
| status | enum | computing / ready / stale |
| computed_at | timestamp | |

**表 3：`agent_findings`（Agent 发现）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| school_id | FK | 隔离 |
| finding_type | enum | grading_overdue / submission_low / score_anomaly / attendance_drop |
| severity | enum | info / warning / critical |
| target_type | string | exam / class / student / homework |
| target_id | string | 对应实体 ID |
| summary | text | 人类可读摘要 |
| detail | JSON | 结构化详情（阈值/实际值/偏差） |
| status | enum | new / notified / acknowledged / resolved |
| notify_roles | JSON | 应通知哪些角色 |
| idempotency_key | string | unique，防重复（target_type+target_id+finding_type+date） |
| created_at | timestamp | |
| resolved_at | timestamp | 可空 |

**表 4：`agent_tasks`（Agent 待办）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| school_id | FK | 隔离 |
| finding_id | FK→findings | 可空，由哪个发现触发 |
| task_type | enum | generate_report / send_notification / flag_review |
| assignee_role | string | 分配给哪个角色 |
| payload | JSON | 任务参数 |
| status | enum | pending / in_progress / completed / cancelled |
| created_at | timestamp | |

**表 5：`workflow_runs`（工作流执行记录）（GPT #D-1 指出）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| school_id | FK | 隔离 |
| workflow_name | string | post_exam_analysis / student_profile / patrol |
| trigger_type | enum | event / schedule / intent |
| trigger_ref | string | exam_id / cron expression / session_id |
| idempotency_key | string | unique（school_id + workflow + trigger_ref + date） |
| status | enum | pending / running / completed / failed / retrying |
| current_step | int | 当前执行到第几步 |
| total_steps | int | 总步数 |
| retry_count | int | 已重试次数（上限 3） |
| next_retry_at | timestamp | 可空 |
| started_at | timestamp | |
| completed_at | timestamp | 可空 |
| last_error | text | 可空，最后一次失败原因 |

**表 6：`workflow_steps`（工作流步骤记录）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| run_id | FK→workflow_runs | 所属执行 |
| step_index | int | 步骤序号 |
| step_name | string | compute_snapshot / detect_anomalies 等 |
| status | enum | pending / running / completed / failed / skipped |
| input_summary | JSON | 输入摘要（调试用） |
| output_summary | JSON | 输出摘要（产出了几条记录等） |
| started_at | timestamp | |
| completed_at | timestamp | |
| error | text | 可空 |

### 数据生命周期

```
事件触发                          定时调度
    │                               │
    ▼                               ▼
exam.published ──→ W1 考后分析    每日 04:00 ──→ W3 画像更新
                   │               每小时    ──→ W6 异常巡检
                   │
                   ▼
             写入 workflow_runs（幂等键去重）
                   │
                   ├─ exam_analysis_snapshot (新建)
                   ├─ class_exam_report (新建)
                   ├─ student_exam_snapshots (复用，更新)
                   ├─ student_knowledge_mastery (复用，增量更新)
                   ├─ agent_findings (新建)
                   └─ 推送通知
```

**过期与重算触发（GPT #D-2 指出）：**

| 事件 | 影响的预计算表 | 处理 |
|------|-------------|------|
| exam.published | snapshot + report + diagnosis | 全量重算 |
| teacher_review.overridden | student_exam_snapshots | 增量更新受影响学生 |
| student.transferred | class_exam_report | 标记 stale，下次查询时重算 |
| semester.switched | 全部 | 新学期不继承旧快照 |

## §3 工作流引擎

### 架构

```
WorkflowEngine
  ├─ WorkflowRegistry        # 注册所有工作流定义
  ├─ WorkflowExecutor        # 执行引擎（持久化状态机）
  │    ├─ 创建 workflow_runs 记录
  │    ├─ 按 steps 顺序执行，每步写 workflow_steps
  │    ├─ 每步传入 DataScope（自动裁剪）
  │    ├─ 失败时记录错误 + 按策略重试（最多 3 次）
  │    └─ 幂等键去重（school_id + workflow + trigger_ref + date）
  │
  └─ WorkflowTrigger         # 触发器
       ├─ EventTrigger        # 事件驱动（exam.published）
       ├─ ScheduleTrigger     # 定时（arq cron）
       └─ IntentTrigger       # 对话意图匹配
```

**两种运行模式：**

| 模式 | 触发 | 执行者 | 产出 |
|------|------|-------|------|
| 后台模式 | 事件/定时 | arq worker | 写预计算表 + findings + tasks |
| 对话模式 | 用户提问 | api/ai.py | 读预计算表 → 格式化回答 |

**并发控制（GPT #D-3 指出）：** 按 `school_id + workflow_name + trigger_ref` 做 DB 级幂等键。同一考试重复发布 → 跳过。两考试同时发布 → 各自独立 run，不冲突。

### W1：考后分析

**后台流程（exam.published 触发）：**

```
Step 1: compute_exam_snapshot
  读: scores + subjects + questions
  写: exam_analysis_snapshot (school_overview + per-subject)

Step 2: compute_class_reports
  读: scores + classes + Step1 年级数据
  写: class_exam_report × N 个班级

Step 3: compute_student_diagnoses
  读: scores + knowledge_points + 历史成绩
  写: student_exam_snapshots（复用，扩展诊断字段）

Step 4: detect_anomalies
  规则: 班级均分偏离 > 2σ(critical) / 学生排名变化 > 50(warning) / 题目得分率 < 0.3(info)
  写: agent_findings
  注意: 接入校历（GPT #D-4），节假日/联考周调高阈值

Step 5: dispatch_notifications
  推送: 教务主任(全校概览+critical) / 班主任(本班+异常学生) / 家长(孩子诊断，如果开通)
```

**对话流程：**

```
意图匹配 → 检查 snapshot 是否 ready
  ├─ ready → 按角色选择展示粒度（1 轮返回）
  │   ├─ principal → 全校概览 + 异常告警
  │   ├─ grade_leader → 本年级各班对比
  │   ├─ homeroom_teacher → 本班报告 + 需关注学生
  │   ├─ subject_teacher → 所教科目各班对比 + 薄弱题
  │   └─ parent → 孩子个人诊断 + 建议
  ├─ computing → "分析正在计算中，预计 X 分钟后完成"
  └─ 不存在 → "该考试尚未发布成绩"
```

### W3：学情画像

**后台流程（每日 04:00 + exam.published）：**

```
Step 1: update_knowledge_mastery
  读: 最近考试 scores + questions + knowledge_points
  写: student_knowledge_mastery（复用，增量更新）

Step 2: update_student_profiles
  读: 历次 exam_snapshots + mastery + error_books
  写: student_exam_snapshots（复用，扩展画像字段：趋势/雷达/错误模式）

Step 3: compute_class_weakness
  读: 本班学生 mastery 数据
  写: class_exam_report.weakness 字段更新

Step 4: generate_learning_advice（Tier 1 模型，限流）
  读: student profiles + mastery
  用 LLM 生成个性化学习建议
  写: student_exam_snapshots.learning_advice
  限制: 每天最多 100 个学生（成本控制）
```

**对话流程：**

```
意图匹配 → 按角色分流
  ├─ parent → 读孩子画像 → "小明最近数学进步了，但导数部分还需加强..."
  ├─ homeroom_teacher → 读本班画像 → "3班整体稳中有升，5名学生数学退步明显..."
  └─ subject_teacher → 读所教班学科维度 → "3班和5班导数应用都偏弱，建议集中讲练..."
```

### W6：异常巡检

**后台流程（每小时）：**

```
Step 1: scan_grading_overdue
  规则: 阅卷任务创建 > 72h 未完成（校历排除节假日）
  产出: finding(grading_overdue, warning)

Step 2: scan_submission_low
  规则: 作业距截止 < 24h 且 提交率 < 50%
  产出: finding(submission_low, warning)

Step 3: scan_score_anomaly（仅有新考试数据时）
  规则: 班级均分偏离年级 > 2σ
  产出: finding(score_anomaly, critical)

Step 4: deduplicate_and_dispatch
  去重: idempotency_key（同 target+type 24h 内不重复）
  限流: 每角色每天最多 10 条推送
```

### 三工作流协作

```
W6 持续监控 ──→ 发现异常 → findings
                              │
W1 考后分析 ←── exam.published │
  │                            │
  └─ snapshot/report/diagnosis ──→ 喂给 W3
                                     │
W3 画像累积 ←── 每日 + 考后 ──────────┘
  │
  └─ 家长端展示 / 教师端辅助
```

## §4 工具重组 + 意图路由

### 工具分类

**工作流内部工具（不暴露给 LLM）：**

| 工作流 | 内部工具 |
|-------|---------|
| W1 | compute_exam_snapshot, compute_class_reports, compute_student_diagnoses, detect_anomalies |
| W3 | update_mastery, update_profiles, compute_weakness, generate_advice |
| W6 | scan_grading, scan_submission, scan_score, deduplicate_dispatch |

**域工具（自由模式，LLM 按需调用）：**

| 域 | 工具 | 工具数 |
|----|------|-------|
| 考试查询 | get_exam_overview*, get_exam_detail, get_subject_questions | 3 |
| 成绩分析 | get_class_report*, get_student_diagnosis*, compare_classes, rank_students | 4 |
| 学生画像 | get_student_profile*, get_knowledge_map, get_error_patterns, get_student_trend | 4 |
| 作业管理 | list_homework, get_homework_stats, assign_homework, submit_homework | 4 |
| 知识查询 | search_curriculum, search_textbook, get_concept_info, get_knowledge_tree | 4 |
| 报告生成 | generate_report, generate_comment | 2 |
| 异常概览 | get_findings*, get_agent_tasks* | 2 |

*标 `*` = 新工具（读预计算表），替代现有多工具组合。

**域工具总数：23 个。** LLM 每次只看 1-2 个域（8-12 个工具）。

**工具输出约束（GPT #E-2 指出）：** 所有明细工具强制 `limit` 参数（默认 20，最大 50）。摘要工具返回 `summary_only` 模式。防止 token 爆炸。

### 合并映射（现有 → 新）

| 合并前（现有 39 个中） | 合并为 | 数据源 |
|---------------------|-------|--------|
| get_exam_summary + get_score_distribution + get_question_analysis + get_grade_aggregates | get_exam_overview | exam_analysis_snapshot |
| get_student_scores + get_student_trend + get_student_knowledge_map + get_error_pattern | get_student_profile | student_exam_snapshots + mastery |
| get_class_scores + get_class_stats + get_class_knowledge_weakness | get_class_report | class_exam_report |
| get_exam_scores + rank_students | rank_students（保留，加分页） | 实时查询 |

**保留不合并的：** get_exam_detail, get_subject_questions, compare_classes, search_*, assign_homework, submit_homework, generate_report, generate_comment — 这些语义独立，不应合并。

### IntentRouter

```
用户提问
    │
    ▼
IntentRouter.classify(message, scope)
    │
    ├─ 匹配工作流意图？
    │   ├─ 考后分析模式 → W1 对话流程
    │   ├─ 学情画像模式 → W3 对话流程
    │   ├─ 异常概览模式 → W6 对话流程
    │   └─ WorkflowEngine.run_dialog(workflow, scope)
    │
    └─ 不匹配 → 自由模式
        │
        ▼
    DomainClassifier.select_domains(message)
        │
        ├─ 选出 1-2 个相关域
        └─ AgentLoop.run(message, tools=域工具, scope=scope)
```

**意图分类实现（分期）：**

| 阶段 | 方式 | 覆盖率估计 |
|------|------|----------|
| 第一期 | 关键词规则 + 实体槽位提取 | 教师 50-60%，家长 60-70% |
| 第二期 | Tier 3 轻量模型 1 轮分类 | 80%+ |
| 第三期 | 学习型路由（历史命中率调优） | 90%+ |

**实体槽位（GPT #F-2 指出）：** 意图分类前先提取 exam/class/student/subject/time 实体。低置信度 → 反问用户确认，不猜。

## §5 角色人格

### 两个 Persona

| 维度 | teacher_assistant | parent_advisor |
|------|------------------|---------------|
| 适用角色 | 5 个教职角色 | parent |
| 可用工作流 | W1 + W3 + W6 | W3（仅自己孩子） |
| 可用域工具 | 全部 7 域 | 画像 + 知识 + 作业查看（3 域，只读） |
| 写操作 | 有 | 无 |
| 排名展示 | 完整 | 由 parent_can_see_ranking 校级配置决定（true=具体排名，false=隐藏） |
| 其他学生 | 可见（脱敏） | 永远不可见 |
| Prompt 风格 | 专业分析、用术语、引用数字 | 温和通俗、建议导向、鼓励为主 |
| 主动推送 | 异常告警、阅卷催办、作业统计 | 成绩出来了、学习建议更新了 |

### 家长端差异化（GPT #G 指出）

**推送分层：**

| 层级 | 频率 | 内容 |
|------|------|------|
| 即时 | 仅 critical | 成绩发布通知 |
| 每日摘要 | 每天 20:00 | 作业完成度 + 今日课堂表现（如有） |
| 周报 | 每周日 | 本周学习趋势 + 知识点掌握变化 + 家庭建议 |

**家长核心体验：** 趋势 > 排名，建议 > 数字，可操作 > 纯展示。

### 前置权限补全（GPT #G-1 指出）

parent 角色需要在 `core/permissions.py` 中添加 `USE_AI_CHAT` 权限。当前未包含。

## §6 与现有代码的兼容性

### 需要改动的模块

| 模块 | 改动性质 | 规模 |
|------|---------|------|
| `api/ai.py` | 新增 DataScope 计算、IntentRouter、WorkflowEngine 调度、Persona 选择 | 大（重构入口） |
| `ai/agent_loop.py` | 小改：接受 DataScope、支持域工具动态传入 | 小（现有接口兼容） |
| `ai/tool_access.py` | 默认策略改 fail-closed | 小 |
| `ai/prompts.py` | 新增 parent_advisor prompt 模板 | 中 |
| `core/permissions.py` | parent 加 USE_AI_CHAT | 小 |
| `api/permissions.py` | ScopeFilter 统一下沉为 ScopedQuery | 中 |
| 所有 service 查询层 | 接入 ScopedQuery（替代各自 WHERE） | 大（但渐进式） |

### 可复用的

| 模块 | 复用方式 |
|------|---------|
| AgentLoop | 自由模式直接用，不改核心循环 |
| ToolRegistry + ToolSpec | 域工具注册方式不变 |
| LLMProxyAdapter | 不变 |
| CapabilityProbe + LoopStrategy | 不变 |
| SensitivityRouter + Anonymizer | 不变 |
| 现有 39 工具 | 渐进替换——新工具上线前旧工具继续服务 |
| capabilities + school_settings 表 | 软规则配置直接复用 |
| school_modules 表 | 模块开关直接复用 |
| EventBus (exam.published) | 工作流触发器直接挂载 |
| arq worker | 后台工作流执行环境 |

## §7 未来扩展（第一期不做，预留）

| 场景 | 预留方式 |
|------|---------|
| W2 作业追踪工作流 | workflow_runs 表已支持新 workflow_name |
| W4 家校沟通/日历通知 | calendar_events + notifications 表已有 |
| W5 学期汇总报告 | exam_analysis_snapshot 支持 semester 维度 |
| 走班制/教学班 | 预留 teaching_class_memberships 表设计 |
| 德育/考勤/行为 | agent_findings.finding_type 可扩展 |
| 学期报告/教师考核 | workflow + report 模板可扩展 |
| 可解释性/申诉链路 | workflow_runs + snapshot version 提供审计追踪 |
| 运营指标看板 | workflow_runs 表已含 SLA 数据 |

## §8 实现分批建议

| 批次 | 内容 | 依赖 |
|------|------|------|
| B1 基础设施 | DataScope + ScopedQuery + guardian_student_links + workflow_runs/steps 表 + fail-closed 改造 | 无 |
| B2 W1 考后分析 | exam_analysis_snapshot + class_exam_report + 5 步后台流程 + 3 个新域工具 + 对话模式 | B1 |
| B3 W3 学情画像 | 复用 pipeline 表 + profile 扩展 + 4 步后台流程 + 学生画像域工具 + 家长 Persona | B1 |
| B4 W6 异常巡检 | agent_findings + agent_tasks + 4 步巡检 + 异常概览域工具 + 通知推送 | B1 |
| B5 IntentRouter | 意图分类 + 实体提取 + 域动态加载 + 工具合并上线 | B2+B3+B4 |
| B6 集成收尾 | 旧工具下线 + 全量测试 + 端到端验证 | B5 |

## 附录：GPT 补充审查处置记录

| GPT Finding | Severity | 处置 |
|------------|----------|------|
| A: 缺走班/排课/代课场景 | HIGH | 第一期不做，§7 预留 teaching_class_memberships |
| A: 缺家校沟通/日历工作流 | HIGH | 第一期不做，§7 预留 W4 |
| A: 缺学期报告/教师考核/德育 | MED | §7 预留事件类型 |
| B: 预计算表与 pipeline 表重叠 | HIGH | §2 复用原则：能复用就复用 |
| B: 大 JSON 不可查询 | HIGH | §2 常用键做列（D8） |
| B: 缺 guardian/workflow 表 | HIGH | §1 guardian_student_links + §3 workflow_runs/steps |
| C: UserRole 缺 district/student/有效期 | HIGH | §1 DataScope 从多表推导，不改 UserRole |
| C: ScopeFilter 无 school_id 不过滤 | HIGH | §1 ScopedQuery 强制过滤（fail-closed） |
| C: 班主任 class×subject 矩阵 | HIGH | §1 pair 矩阵推导 |
| C: scope 版本失效 | MED | §1 version 字段 + 事件监听 |
| D: 工作流无状态机/重试 | HIGH | §3 workflow_runs + retry（D6） |
| D: 预计算过期条件不全 | HIGH | §2 过期触发表 |
| D: 并发和幂等 | HIGH | §3 idempotency_key |
| D: W6 阈值误报 | MED | §3 接入校历 |
| E: 明细工具 token 爆炸 | HIGH | §4 强制 limit/top_n |
| E: 家长跨域编排 | MED | §3 W3 对话模式组合返回 |
| F: 复合意图误分类 | HIGH | §4 实体槽位 + 低置信度反问 |
| F: 关键词覆盖率有限 | MED | §4 分期升级路线 |
| G: 家长权限缺失 | HIGH | §5 补 USE_AI_CHAT |
| G: 家长核心体验 | HIGH | §5 趋势>排名，建议>数字 |
| G: 推送分层 | MED | §5 即时/日报/周报 |
| H: api/ai.py 改动大 | HIGH | §6 确认改动清单 |
| H: tool_access fail-closed | MED | §6 确认（D7） |
| I: 监护关系无模型 | HIGH | §1 guardian_student_links |
| I: 缺可解释性 | MED | §7 预留（workflow_runs + version） |
| I: 知识库单学科 | MED | §7 预留多学科 config |
| I: 缺运营指标 | MED | §7 预留（workflow_runs 含 SLA） |
