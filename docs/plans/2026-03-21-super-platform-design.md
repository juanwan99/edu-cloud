# edu-cloud 超级智能平台设计文档

> [2026-03-22 10:02:25 P1 实现完成] Commits: bba413e..8936134 (P1 AI 大脑 7 Task + R1/R2 修复, 138 tests)
> [2026-03-22 08:37:41 P0 实现完成] Commits: beab26e..03229e7 (P0 骨架 8 Task + R1/R2 修复, 94 tests)
> 创建时间: 2026-03-21 22:55:42
> 状态: P1 实现完成
> 范围: edu-cloud 从"联考后端"重构为"学校超级智能管理平台"
> 参照: Google NotebookLM 三栏布局
> GPT 架构审查: architecture-codex-review.md (2026-03-21, Q1-Q7 共识达成)

### §待处置（GPT Plan Review design-concern）

- **PR-07**: CLAUDE.md 角色边界已更新（2026-03-21），exam-ai 侧 CLAUDE.md 待同步
- **PR-08**: 引入 Alembic migration 后应停用 `create_all()` 启动自动建表。P0 Task 8 实施时处理。
- **R2-02**: WorkspaceService 的 grade_ids / subject_codes scope 过滤未实现。P0 只支持 homeroom_teacher + class_ids，grade_leader(grade_ids) 和 subject_teacher(subject_codes) 的完整 scope 隔离留待 P1 实现。

---

## §0 设计概要

edu-cloud 从纯后端联考 API 服务重构为 **AI 驱动的学校全业务操作系统**。

核心理念：**AI 不是附加功能，AI 就是操作界面本身。**

不同职务的教师登录后看到同一个三栏工作台，但左栏数据、中栏视图、右栏可用模板、AI 可用工具全部由角色和权限自动适配。平台兼具数据分析、文档生成、家校通信、论文写作能力。

### 架构决策总览（Claude 决策，GPT 审查后调整）

> Q1 和 Q3 与 GPT 推荐不同：GPT 建议 Q1=B(BFF)、Q3=C(独立服务)，
> 但考虑到 edu-cloud 无生产用户且单人开发，选择 A(单体重构) 和内建 Agent。
> 详细理由见 §1 和 §5。

| 问题 | 决策 | 理由 |
|------|------|------|
| Q1 单体vs微服务 | **A 单体重构** | edu-cloud 无生产用户，从头设计成本最低 |
| Q2 前端选型 | **Vue 3 + Naive UI** | 复用 exam-ai 组件资产 |
| Q3 Agent 位置 | **内建 edu-cloud** | 单人开发，少一个进程少一份运维 |
| Q4 数据融合 | **混合：高频同步+低频联邦** | 兼顾性能和隐私 |
| Q5 家校通信 | **企业微信为主，短信预留** | 100% 微信渗透率 |
| Q6 响应式 | **桌面三栏+移动 Tab** | 主力桌面端，移动端保留高频操作 |
| Q7 RBAC | **7+ 显式角色 + scope** | 角色驱动一切，底层预留自定义 |

---

## §1 系统定位与边界

### 重新定位

edu-cloud 不再是"联考管理后端"，而是 **学校超级智能平台**。

```
┌─────────────────────────────────────────────────┐
│              edu-cloud（超级平台）                 │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ 三栏前端  │  │ 平台后端  │  │  AI Agent 引擎 │  │
│  │ Vue 3    │  │ FastAPI  │  │  ReAct + Tools │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
│       │              │              │            │
│       └──────────────┼──────────────┘            │
│                      │                           │
└──────────────────────┼───────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ exam-ai  │ │knowledge │ │paper-skill│
    │ 校本数据  │ │  -base   │ │ 论文引擎  │
    │ 采集节点  │ │ 知识底座  │ │          │
    └──────────┘ └──────────┘ └──────────┘
```

### 职责划分

| 系统 | 新职责 | 变化 |
|------|--------|------|
| edu-cloud | 统一入口、三栏工作台、AI Agent、RBAC、文档生成、家校通信、跨校分析 | 从"联考后端"升级为全平台 |
| exam-ai | 校本数据采集（扫描阅卷、成绩录入）、向云端同步数据 | 从"独立产品"退化为数据节点 |
| edu-knowledge-base | 课标/教材/文献/高考题库，被 AI Agent 按需查询 | 不变，作为知识层被消费 |
| paper-skill | 论文写作引擎，被 Studio 调用 | 不变，作为 Studio 的一个产出模板 |
| llm-proxy | LLM 统一网关 | 不变 |

### 关键决策

- edu-cloud 使用 **PostgreSQL 单库多租户 + RLS**（单台服务器，独立库过度设计）
- AI Agent 引擎**内建在 edu-cloud**，不做独立服务（单人开发，少一个进程少一份运维）
- exam-ai 的 AI Agent 代码（ReAct 循环 + 23 工具）作为**参考实现迁移**，不做代码共享

---

## §2 三栏 AI 工作台

### 布局结构

```
┌──────────────────────────────────────────────────────────────┐
│  顶栏：Logo + 角色切换 + 学期选择 + 通知铃铛 + 用户头像       │
├────────────┬───────────────────────────┬─────────────────────┤
│  左栏 280px │      中栏（自适应）         │   右栏 320px        │
│  可折叠     │                           │   可折叠             │
│            │  ┌─────────────────────┐  │                     │
│ ┌────────┐ │  │                     │  │  ┌───────────────┐  │
│ │上下文   │ │  │   数据呈现区         │  │  │  Studio 产出   │  │
│ │选择器   │ │  │   仪表盘/图表/表格    │  │  │               │  │
│ │        │ │  │                     │  │  │  📄 教学报告    │  │
│ │ 📁 考试 │ │  │                     │  │  │  📋 家长通知    │  │
│ │ 📁 班级 │ │  │                     │  │  │  ✍️ 学生评语    │  │
│ │ 📁 学生 │ │  └─────────────────────┘  │  │  📊 成绩分析    │  │
│ │ 📁 知识库│ │                           │  │  📝 教学反思    │  │
│ │ 📁 联考 │ │  ┌─────────────────────┐  │  │  📰 论文       │  │
│ │        │ │  │   AI 对话区           │  │  │               │  │
│ │        │ │  │   （底部，可拖拽高度）  │  │  │ ─────────── │  │
│ │ ────── │ │  │                     │  │  │  待审批队列    │  │
│ │ 最近使用 │ │  │  > 分析一下七年级...  │  │  │  ☐ 安全通知   │  │
│ │ 快捷入口 │ │  │  AI: 正在查询...     │  │  │  ☐ 期中报告   │  │
│ └────────┘ │  └─────────────────────┘  │  └───────────────┘  │
├────────────┴───────────────────────────┴─────────────────────┤
│  底栏：状态指示（AI 状态 / 数据同步状态 / 学期日历提醒）       │
└──────────────────────────────────────────────────────────────┘
```

### 三栏职责

| 栏 | 职责 | 内容随角色变化 |
|---|------|-------------|
| **左栏：上下文** | 选择"我要看什么" | 校长看全校，班主任看本班，教师看所教班级 |
| **中栏：工作台** | 上半区数据呈现 + 下半区 AI 对话 | 校长看指标仪表盘，教师看成绩分布 |
| **右栏：Studio** | AI 产出物 + 待审批行动 | 校长能生成发展报告，班主任能生成家长通知 |

### 左栏上下文选择器

结构化数据浏览器（非 NotebookLM 的"上传文件"）：

```
数据源树形结构（按角色过滤可见节点）：
├── 校本数据
│   ├── 考试（本学期 / 历史）
│   ├── 班级（我的班级 / 全年级）
│   ├── 学生（按班级浏览）
│   └── 课表 / 教学进度
├── 云端数据
│   ├── 联考（跨校数据）
│   ├── 知识库（课标 / 教材 / 文献）
│   └── 题库（高考真题）
└── 最近使用（快速回到上次上下文）
```

选中上下文后，中栏自动刷新对应数据视图，AI 对话也自动感知"当前在看什么"。

### 中栏工作台

分为**上半区（数据呈现）**和**下半区（AI 对话）**，中间分隔线可拖拽调节比例。

**上半区**：根据左栏选中的上下文，动态渲染对应的数据组件：
- 选中「考试」→ 成绩分布图 + 得分率表格
- 选中「班级」→ 班级画像（各科均分/排名趋势）
- 选中「联考」→ 跨校对比柱状图
- 无选择时 → 角色默认仪表盘（校长看全校概览，教师看教学日历）

**下半区**：AI 对话，继承 exam-ai 的 ChatPanel 能力：
- SSE 流式输出
- 工具调用过程实时展示
- Markdown + 图表渲染
- AI 自动感知当前上下文（"我选了七年级2班 → AI 知道我在问这个班"）

### 右栏 Studio

两个区域：**产出模板** + **行动队列**。

**产出模板**（类似 NotebookLM 的卡片）：按角色显示可用模板，点击后 AI 自动基于当前上下文生成，产物进入下方行动队列。

**行动队列**：每个产物有状态（`草稿 → 已审阅 → 已审批 → 已执行`），教师可编辑草稿、确认后提交审批，有审批权的角色可直接批准并触发执行。

### 响应式策略

| 断点 | 布局 |
|------|------|
| ≥1200px | 三栏并排 |
| 768-1199px | 左栏折叠为图标栏，中栏+右栏 |
| <768px | 底部 Tab 切换（上下文/工作台/Studio），移动端只保留高频操作 |

---

## §3 角色权限体系（RBAC + Scope）

### 角色层级

```
教育局管理员 (district_admin)
    └── 校长 (principal)
         ├── 教务主任 (academic_director)
         │    └── 年级组长 (grade_leader)
         ├── 班主任 (homeroom_teacher)
         └── 科任教师 (subject_teacher)

家长 (parent) ─── 独立入口，只看自己孩子
平台管理员 (platform_admin) ─── 超管，运维用
```

### 权限模型：Role + Permission + Scope

```python
# 概念模型
class UserRole:
    role: str           # "homeroom_teacher"
    permissions: set    # {"VIEW_STUDENTS", "GENERATE_REPORT", "SEND_NOTIFICATION"...}
    scope: Scope        # 数据可见边界

class Scope:
    school_ids: list    # 可见学校（教育局看多校，教师看本校）
    grade_ids: list     # 可见年级（年级组长看本年级）
    class_ids: list     # 可见班级（班主任看本班，科任看所教班）
    subject_codes: list # 可见学科（科任教师看所教学科）
```

### 权限矩阵

| 权限 | 平台管理 | 教育局 | 校长 | 教务 | 年级组长 | 班主任 | 科任教师 | 家长 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 查看成绩数据 | ✅ | ✅多校 | ✅全校 | ✅全校 | ✅本年级 | ✅本班 | ✅所教班+科 | ✅本孩子 |
| AI 对话分析 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| 生成报告 | ❌ | ✅区域 | ✅全校 | ✅教务 | ✅年级 | ✅班级 | ✅学科 | ❌ |
| 生成通知 | ❌ | ✅ | ✅ | ✅ | ❌ | ✅本班 | ❌ | ❌ |
| 审批通知 | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 发送通知 | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 管理教师 | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 管理学校 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 联考管理 | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 写论文 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| AI 工具集 | 全部 | 跨校分析 | 全校分析 | 教务+分析 | 年级分析 | 班级+评语 | 学科+教研 | ❌ |

### Scope 如何影响三栏

```
班主任张老师（scope: school=实验中学, class=[七年级2班]）
  左栏：只看到七年级2班的学生、考试
  中栏：仪表盘只显示2班数据，AI 对话限定在2班范围
  右栏：可用模板 = 班级报告、学生评语、家长通知

校长李校长（scope: school=实验中学, grade=全部, class=全部）
  左栏：看到全校所有年级、班级、教师
  中栏：全校指标仪表盘，AI 可分析任意维度
  右栏：可用模板 = 学校发展报告、教师考核、全校通知
```

### 多角色与切换

一个人可能有多个角色（数学老师 + 七年级2班班主任）：
- 登录后默认进入**主要角色**
- 顶栏提供**角色切换器**，切换后三栏内容全部刷新
- 底层是同一个账号，不同角色只是切换 scope 和权限集

### 数据隔离（PostgreSQL RLS）

```sql
ALTER TABLE students ENABLE ROW LEVEL SECURITY;

CREATE POLICY school_isolation ON students
    USING (school_id = current_setting('app.current_school_id')::uuid);
```

即使应用层代码有 bug 漏了 WHERE 条件，RLS 兜底保证教师绝不会看到别校数据。

### 家长端 UX

家长不进入三栏工作台，而是看到**专用简化页面**：
- 企业微信 OAuth 登录后直接进入"我的孩子"页面
- 只显示：孩子基本信息、各科成绩、教师评语、通知记录
- 无 AI 对话、无 Studio、无左栏选择器
- 本质是一个只读数据展示页，不是工作台

### 身份认证

| 入口 | 认证方式 | 说明 |
|------|---------|------|
| 教师/管理层 | 用户名密码 + JWT | 首期方案，最简单 |
| 家长 | 企业微信 OAuth | 微信扫码登录，自动绑定学生 |
| 未来 | 企业微信统一登录 | 教师也走企微，全面接管 |

---

## §4 数据模型与融合策略

### 数据主权原则

```
每类数据只有一个 Source of Truth（SOT）：

exam-ai（校本 SOT）          edu-cloud（云端 SOT）
├── 学生档案                 ├── 学校注册
├── 考试原始数据              ├── 平台用户/角色
├── 扫描切图                 ├── 联考编排
├── AI 阅卷原始结果           ├── 跨校聚合统计
├── 答案解析                 ├── Studio 产出物
                             ├── 通知/审批记录
                             ├── 学期日历
                             └── AI 会话记录

edu-knowledge-base（知识 SOT）
├── 课标/教材/文献
├── 知识骨架（L0-L2）
└── 高考题库
```

### edu-cloud 核心表

**组织与身份：**
- `schools` — 学校档案
- `users` — 平台用户
- `user_roles` — 多角色支持: user × role × scope

**教学数据（从 exam-ai 同步）：**
- `students` — 学生档案，school_id 隔离
- `classes` — 班级，grade + school
- `exams` — 考试元数据
- `exam_results` — 成绩: 学生×科目×总分
- `exam_item_scores` — 逐题得分，JSONB

**联考（现有 MVP 保留并扩展）：**
- `joint_exams` — 联考，6 状态机
- `joint_exam_participants` — 参与校
- `joint_exam_student_results` — 跨校成绩明细

**Studio 产出：**
- `documents` — AI 产出物: 报告/通知/评语，含 type, status(draft→reviewed→approved→executed), content_json, rendered_html, pdf_url, created_by, approved_by
- `document_versions` — 版本记录: 草稿→修改→终稿

**通信与审批：**
- `notifications` — 通知记录: 内容+渠道+状态
- `approval_flows` — 审批流: 发起人→审批人→状态
- `semester_calendar` — 学期日历: 事件+触发规则

**AI 引擎：**
- `ai_sessions` — 会话: user + context + messages
- `ai_tool_calls` — 工具调用审计日志，append-only
- `ai_cost_log` — LLM 调用成本追踪

### 数据同步策略（exam-ai → edu-cloud）

| 数据类型 | 同步方式 | 频率 | 说明 |
|---------|---------|------|------|
| 学生/班级档案 | 全量同步 | 每学期初 + 变更推送 | 低频，数据量小 |
| 考试元数据 | 增量推送 | 考试创建/完成时 | exam-ai 主动 POST |
| 成绩统计 | 增量推送 | 阅卷完成时 | 推送聚合统计，不推送原始切图 |
| 逐题明细 | 按需拉取 | AI 分析需要时 | edu-cloud 调 exam-ai API |
| 扫描切图 | 不同步 | - | 始终在 exam-ai 本地 |

同步接口复用现有 sync 端点并扩展：
- `POST /api/v1/sync/students` — 推送学生档案（新增）
- `POST /api/v1/sync/exam-results` — 推送考试成绩（新增）
- `GET /api/v1/sync/item-scores` — 按需拉取逐题明细（新增）

### 知识库接入

启动时加载 JSON 到内存索引（数据量可控），AI Agent 通过专用工具访问。不引入向量库（YAGNI）——结构化数据用结构化查询，比 RAG 准确且可控。

### SOT 冲突处理

写在哪里，哪里就是 SOT：
- 学生成绩 → SOT 在 exam-ai → edu-cloud 只读副本，不一致时以 exam-ai 为准
- 联考成绩 → SOT 在 edu-cloud
- 文档产出 / 通知记录 → SOT 在 edu-cloud，不同步回 exam-ai

---

## §5 AI Agent 引擎

### 架构

从 exam-ai Phase 1 迁移并扩展。核心：**自建 ReAct 循环 + 工具注册表**，不依赖 LangChain。

```
用户输入 → AI Agent 引擎
              ├── 1. 上下文注入（角色 + scope + 当前选中数据）
              ├── 2. ReAct 循环（3-8 步）
              │     ├── Thought → Action → Observation → 重复
              ├── 3. 输出（对话回复 → 中栏 / 结构化产物 → 右栏 Studio）
              └── 4. 审计（append-only 日志）
```

### 四层工具体系

| 层 | 工具类别 | 数据源 | 示例 |
|---|---------|-------|------|
| L1 校本分析 | 成绩/学生/班级/考试 | edu-cloud 同步库 | `get_exam_scores`, `compare_classes`, `student_profile` |
| L2 跨校分析 | 联考/区域对比 | edu-cloud 联考表 | `joint_exam_ranking`, `cross_school_compare` |
| L3 知识查询 | 课标/教材/题库/文献 | knowledge-base | `search_curriculum`, `search_gaokao`, `concept_graph` |
| L4 执行动作 | 文档生成/通知/审批 | edu-cloud | `generate_report`, `draft_notification`, `submit_approval` |

### 角色 → 工具绑定

```python
ROLE_TOOLS = {
    "principal": [L1_ALL, L2_ALL, L3_ALL, L4_REPORT, L4_NOTIFY],
    "academic_director": [L1_ALL, L2_ALL, L3_ALL, L4_REPORT, L4_NOTIFY, L4_EXAM],
    "grade_leader": [L1_GRADE_SCOPED, L2_VIEW, L3_ALL, L4_REPORT],
    "homeroom_teacher": [L1_CLASS_SCOPED, L3_ALL, L4_REPORT, L4_COMMENT, L4_NOTIFY_DRAFT],
    "subject_teacher": [L1_SUBJECT_SCOPED, L3_ALL, L4_REPORT, L4_PAPER],
    "district_admin": [L2_ALL, L4_REPORT],
}
```

### 安全边界（读/写分离）

- **读操作（L1-L3）**：AI 自主执行，不需确认
- **写操作（L4）**：生成草稿 → AI 自主执行，产物进入 Studio 待审阅；发送通知/修改数据 → 必须人工审批

**铁律：AI 永远不能自动发出通知或修改数据，只能拟稿。**

### 上下文注入

```python
def build_agent_context(user, workspace_state):
    return {
        "role": user.current_role,
        "scope": user.current_scope,
        "selected_context": workspace_state,  # 左栏选中的数据源
        "semester": current_semester(),
        "recent_actions": last_5_actions(),
    }
# 注入到 system prompt：
# "你正在协助 张老师（班主任，七年级2班）。
#  当前查看的是：2025-2026第二学期期中考试。
#  你可以使用的工具：[...]"
```

### 脱敏层

继承 exam-ai 设计：学生姓名匿名化（张三→S001），映射绑定会话，会话结束销毁。班级人数 <5 时不暴露个体数据（k-匿名）。

### LLM 调用

AI Agent → llm-proxy (port 8100) → 实际模型。默认 claude-sonnet-4-6，复杂分析可升级 claude-opus-4-6。每次调用记录 token 数 + 费用到 ai_cost_log。

### 审计日志

ai_tool_calls 表，append-only：session_id, user_id, role, tool, params, result_summary, duration_ms, ts。

---

## §6 Studio 文档生成引擎

### 产出物状态机

```
draft(草稿) → reviewed(已审阅) → pending(待审批) → approved(已批准) → executed(已执行)
                                     ↓ rejected(打回修改) → draft
无需审批的产物可从 reviewed 直接到 executed。
```

### 产出物类型与审批规则

| 类型 | 可用角色 | 需要审批？ | 执行动作 |
|------|---------|----------|---------|
| 教学诊断报告 | 所有教师 | 否 | 导出 PDF / 存档 |
| 班级学情分析 | 班主任、年级组长 | 否 | 导出 PDF / 存档 |
| 学生评语 | 班主任 | 否 | 导出 / 打印 |
| 教学反思 | 科任教师 | 否 | 存档 |
| 家长通知 | 班主任拟稿 | **是 → 教务/校长审批** | 企业微信群发 |
| 全校通知 | 教务/校长拟稿 | **是 → 校长审批** | 企业微信群发 |
| 考试安排表 | 教务 | **是 → 校长审批** | 下发到各班 |
| 区域质量报告 | 教育局 | 否 | 导出 PDF |
| 论文 | 科任教师 | 否 | 调用 paper-skill 引擎 |

### 文档数据模型

```python
class Document:
    id: UUID
    type: str              # "report" / "notification" / "comment" / "paper"
    title: str
    status: str            # draft → reviewed → pending → approved → executed
    content_json: dict     # 结构化内容（AI 生成的原始数据）
    content_html: str      # 渲染后的 HTML（预览用）
    pdf_url: str | None    # 导出的 PDF 路径
    source_context: dict   # 生成时的左栏上下文
    ai_session_id: UUID    # 关联的 AI 会话（可追溯生成过程）
    created_by: UUID
    approved_by: UUID | None
    executed_at: datetime | None
    execution_result: dict | None  # 发送结果
    version: int
    school_id: UUID        # RLS 隔离

class DocumentVersion:
    document_id: UUID
    version: int
    content_json: dict
    edited_by: UUID
    edited_at: datetime
    change_summary: str
```

### 模板系统

每种产出物有预设模板，AI 按模板结构生成内容：

```python
TEMPLATES = {
    "class_report": {
        "name": "班级学情分析报告",
        "sections": [
            {"key": "overview", "title": "总体概况"},
            {"key": "subject_analysis", "title": "分科分析"},
            {"key": "student_tiers", "title": "分层分析"},
            {"key": "suggestions", "title": "教学建议"},
        ],
        "required_context": ["exam_id", "class_id"],
        "available_roles": ["homeroom_teacher", "grade_leader", "academic_director", "principal"],
    },
    "parent_notification": {
        "name": "家长通知",
        "sections": [
            {"key": "greeting", "title": "称呼"},
            {"key": "body", "title": "正文"},
            {"key": "requirements", "title": "注意事项"},
            {"key": "closing", "title": "落款"},
        ],
        "required_context": ["event_type"],
        "available_roles": ["homeroom_teacher", "academic_director", "principal"],
        "requires_approval": True,
    },
}
```

### AI 生成流程

用户点击模板卡片 → 收集当前上下文 → AI Agent 按 sections 逐段生成 → draft 进入行动队列 → 用户查看/编辑（富文本 Tiptap）→ 每次编辑保存新 version → reviewed → 审批流（如需）→ 执行。

### 论文通道

论文不在 edu-cloud 内生成，调用 paper-skill API 创建任务，完成后回调 edu-cloud，产出物出现在 Studio。

---

## §7 家校通信与学期日历

### 整体机制

```
学期日历（时间驱动）──→ AI 自动拟稿 ──→ Studio 草稿
教师手动发起 ─────────→ AI 辅助拟稿 ──→ Studio 草稿
                                           │
                                           ▼
                                      审批流（§6 状态机）
                                           │
                                           ▼ approved
                                      消息分发引擎
                                      ┌─────┴─────┐
                                      ▼           ▼
                                 企业微信API    短信降级
                                 （首期实现）   （预留接口）
```

### 学期日历

```python
class CalendarEvent:
    type: str                # "holiday" / "exam" / "parent_meeting" / "deadline"
    title: str               # "五一放假"
    date: date               # 2026-05-01
    notification_rules: list[NotificationRule]

class NotificationRule:
    days_before: int         # 提前几天触发（7 / 3 / 1）
    template_type: str       # "holiday_safety" / "exam_reminder"
    target_roles: list[str]  # ["parent"]
    auto_draft: bool         # True: AI 自动拟稿进 Studio
```

### 自动拟稿流程

每日定时任务（凌晨 6:00）扫描学期日历 → 触发条件匹配 → AI Agent 调用模板生成通知草稿 → 进入对应负责人的 Studio 行动队列（draft 状态）→ 审阅/编辑 → 审批 → 群发。

### 审批流

场景固化，不做通用工作流引擎（YAGNI）：

```python
APPROVAL_CHAINS = {
    "class_notification":  ["homeroom_teacher → academic_director"],
    "grade_notification":  ["grade_leader → academic_director"],
    "school_notification": ["academic_director → principal"],
    "emergency":           ["principal"],  # 紧急通知校长直发
}
```

### 消息分发

统一消息出口，首期只实现企业微信。未绑定微信的家长记录为"未触达"（首期不发短信，预留接口）。发送必须幂等——同一 notification_id 重复调用不会重复发送。

### 企业微信接入（首期最小集）

- 学校通知 API（发送文本/图文消息到家长）
- 家长通讯录同步（学生-家长绑定关系）
- OAuth 登录（家长扫码进平台看孩子数据）

---

## §8 技术栈与部署架构

### 技术选型

| 层 | 选型 | 理由 |
|---|------|------|
| 前端框架 | Vue 3 + Naive UI | 复用 exam-ai 组件 |
| 前端构建 | Vite | Vue 3 标配 |
| 前端图表 | ECharts | exam-ai 已用 |
| 前端富文本 | Tiptap | JSON ↔ HTML 双向 |
| 后端框架 | FastAPI + Uvicorn | 现有选型 |
| ORM | SQLAlchemy 2.0 async | 支持 RLS |
| 数据库 | PostgreSQL 15+ | RLS + JSONB + 全文检索 |
| 迁移 | Alembic | 现有选型 |
| 缓存/任务队列 | Redis + arq | 定时任务、会话缓存 |
| LLM 网关 | llm-proxy (port 8100) | 已有 |
| PDF 生成 | WeasyPrint | HTML→PDF |
| 认证 | python-jose + bcrypt | 现有选型 |
| 企业微信 | httpx 直调 API | 接口简单，不引入 SDK |

### 部署拓扑（单台服务器）

```
Nginx (80/443)
├── /            → edu-cloud 前端 (静态文件)
├── /api/        → edu-cloud 后端 (port 9000)
├── /exam/       → exam-ai 前端 (静态文件)
├── /exam/api/   → exam-ai 后端 (port 8000)
└── /paper/      → paper-skill (port 9103)

PM2 进程管理
├── edu-cloud-api     (uvicorn, port 9000)
├── exam-ai-api       (uvicorn, port 8000)
├── paper-skill       (node, port 9103)
├── llm-proxy         (uvicorn, port 8100)
└── edu-cloud-worker  (arq worker, 定时任务)

PostgreSQL
├── edu_cloud   (主库)
└── exam_ai     (校本库)

Redis — 会话缓存 + 任务队列
```

### 目录结构

```
edu-cloud/
├── frontend/                    # Vue 3 前端
│   └── src/
│       ├── layouts/WorkbenchLayout.vue
│       ├── components/
│       │   ├── context/         # 左栏
│       │   ├── workspace/       # 中栏
│       │   ├── studio/          # 右栏
│       │   └── shared/
│       ├── stores/              # Pinia
│       └── pages/
├── src/edu_cloud/               # Python 后端
│   ├── api/                     # 路由层（<10 行/文件）
│   ├── services/                # 业务逻辑层
│   ├── ai/                      # AI Agent 引擎
│   │   ├── agent.py             # ReAct 循环
│   │   ├── context.py
│   │   ├── anonymizer.py
│   │   ├── tools/               # L1-L4 工具
│   │   └── audit.py
│   ├── models/                  # SQLAlchemy 模型
│   ├── core/                    # 权限、事件
│   ├── channels/                # 消息渠道（wechat/base）
│   ├── knowledge/               # 知识库加载
│   ├── config.py
│   ├── database.py
│   └── logging_config.py
├── alembic/
├── tests/
└── pyproject.toml
```

### 关键约束

- 前后端同仓库（monorepo）
- API 路由层 <10 行/文件，业务逻辑全在 services/
- AI 工具与 services 调用同一层
- 所有表带 school_id + RLS

---

## §9 分阶段实施路线

### P0：骨架搭建

**目标：三栏框架跑通 + RBAC + 基础数据呈现。**

| Task | 内容 |
|------|------|
| P0-1 | 前端脚手架：Vite + Vue 3 + Naive UI + 路由 + Pinia |
| P0-2 | WorkbenchLayout.vue 三栏布局 + 响应式断点 |
| P0-3 | 后端 RBAC 重构：users + user_roles + scope + RLS |
| P0-4 | 登录页 + JWT 认证 + 角色切换器 |
| P0-5 | 左栏上下文选择器（静态树形结构）|
| P0-6 | 中栏数据呈现：统计卡片 + ECharts |
| P0-7 | 数据同步接口：exam-ai 推送学生/班级/成绩 |
| P0-8 | 种子数据 + Alembic 首个 migration |

**完成标志：** 班主任登录 → 左栏选考试 → 中栏看到成绩分布图。

### P1：AI 大脑

**目标：中栏底部 AI 对话可用。**

| Task | 内容 |
|------|------|
| P1-1 | AI Agent 引擎：ReAct 循环 + 工具注册表 |
| P1-2 | L1 工具（8个）：校本分析 |
| P1-3 | L2 工具（4个）：跨校分析 |
| P1-4 | 上下文注入 + 角色工具过滤 |
| P1-5 | 脱敏层 |
| P1-6 | AI 对话前端组件（SSE + 工具调用展示）|
| P1-7 | 审计日志 |

**完成标志：** 班主任问"我们班数学考得怎么样" → AI 返回带图表的分析。

### P2：Studio 产出

**目标：右栏能生成文档。**

| Task | 内容 |
|------|------|
| P2-1 | 产出物数据模型 + migration |
| P2-2 | 模板系统（3 个首批模板）|
| P2-3 | L4 工具：generate_report / generate_comment |
| P2-4 | 右栏 Studio 前端 |
| P2-5 | 文档预览 + 富文本编辑（Tiptap）|
| P2-6 | PDF 导出（WeasyPrint）|
| P2-7 | 审批流 |

**完成标志：** 班主任点击"班级报告" → AI 生成 → 修改 → 导出 PDF。

### P3：家校通信

**目标：通知从拟稿到群发跑通。**

| Task | 内容 |
|------|------|
| P3-1 | 学期日历数据模型 + 管理 API + 前端 |
| P3-2 | 定时任务：日历扫描 → AI 自动拟稿 |
| P3-3 | 通知模板（4 个首批）|
| P3-4 | 企业微信接入 |
| P3-5 | 消息分发引擎 + 幂等 |
| P3-6 | 家长端：企微 OAuth → 只读查看 |

**完成标志：** 学期日历"五一放假" → 提前 7 天自动拟通知 → 审批 → 家长微信收到。

### P4：知识深度

**目标：AI 能引用课标/教材，教师能写论文。**

| Task | 内容 |
|------|------|
| P4-1 | 知识库加载模块 |
| P4-2 | L3 工具（4个）|
| P4-3 | paper-skill 接入 |
| P4-4 | 论文进度回显 |

**完成标志：** 教师问课标要求 → AI 引用原文。点"论文" → paper-skill 启动。

### 里程碑总结

```
P0 骨架  →  能看    →  "三栏工作台，能看数据"
P1 AI    →  能问    →  "AI 能回答教学问题"
P2 Studio → 能产出  →  "AI 分析变成文档报告"
P3 通信  →  能触达  →  "通知能发到家长手机"
P4 知识  →  能引用  →  "AI 有课标教材知识支撑"
```

每个 Phase 结束时都是可独立交付的产品状态。
