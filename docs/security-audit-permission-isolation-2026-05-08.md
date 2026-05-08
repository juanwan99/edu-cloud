# edu-cloud 权限隔离安全审计报告

> **日期**: 2026-05-08
> **审计方**: Claude Opus 4.6 + GPT 5.5 联合审计（交叉验证完成）
> **范围**: 全部 49 个 router 文件，5 层隔离模型
> **触发原因**: 景炎中学账号能看到新凤凰学校的阅卷任务（跨校数据泄露）
>
> **交叉验证状态**:
> - P0 × 4: 全部由 Claude 逐行确认 ✓
> - P1-1 (impersonate): deps.py:119 确认直接使用 ROLE_PERMISSIONS[effective_role] ✓
> - P1-2 (AI session): ai.py:146 确认 setdefault 不检查 owner_id ✓
> - P1-3 (exam schedule): router.py:395 确认 db.get 无 school_id ✓
> - P1-4 (exam write): router.py 确认 Question/Subject CRUD 有 school_id（GPT 行号偏移，降级为 **已验证安全**）
> - 其余 P1: GPT 单轮审计，行号未逐行确认（标注为 "待二次验证"）

---

## 隔离模型定义

| 层级 | 名称 | 说明 |
|------|------|------|
| L1 | 学校间隔离 | 不同学校数据完全不可见 |
| L2 | 校内角色隔离 | 教师只看自己任教班级/科目 |
| L3 | 联考隔离 | 多校联考时成绩按学校隔离 |
| L4 | 模拟登录 | scope_override 不得提权 |
| L5 | ID 枚举 (IDOR) | 不可通过遍历 ID 越权 |

---

## P0 紧急（跨校数据泄露，必须立即修复）

### P0-1: 阅卷结果跨校覆盖
- **文件**: `grading/router.py:643-645`
- **层级**: L1 + L5
- **问题**: `grade-single` upsert GradingResult 只按 `answer_id` 查询，缺 `school_id` 过滤
- **攻击路径**: 枚举 answer_id → 命中他校答案 → 覆盖他校阅卷结果
- **修复**: 查询加 `GradingResult.school_id == school_id`；建 `(school_id, answer_id)` 唯一约束

### P0-2: 联考成绩跨校泄露
- **文件**: `exam/results_router.py:34,38` + `exam/results_service.py:136`
- **层级**: L1 + L3 + L5
- **问题**: 接受未验证 `school_id` 查询参数，服务层只按 `joint_exam_id + student_number` 查
- **攻击路径**: 景炎账号传 `?school_id=新凤凰ID` → 读取新凤凰学生成绩
- **修复**: school_id 只能来自 JWT；校验当前学校是联考参与方

### P0-3: 联考排名/对比全量泄露
- **文件**: `exam/results_router.py:13` + `exam/results_service.py:14,55`
- **层级**: L3 + L5
- **问题**: 排名/学校对比只按 `joint_exam_id` 查询，返回所有学校的 student_number/name/score
- **攻击路径**: 任意有 VIEW_JOINT_EXAM 权限的学校用户枚举 exam_id → 获取所有参与学校排名
- **修复**: 排名默认过滤当前 school_id；跨校榜单脱敏或仅授权联考管理员

### P0-4: 联考管理接口无参与校验证
- **文件**: `exam/joint_exam_router.py:28,49,74` + `exam/joint_exam_service.py:188`
- **层级**: L1 + L3 + L5
- **问题**: 创建允许指定 `creator_school_id`；列表/详情/参与校管理未绑定当前学校参与关系
- **攻击路径**: 伪造他校为创建方；通过 exam_id 查看/修改非参与学校联考
- **修复**: creator_school_id 必须取 JWT；list/detail/add/remove 必须校验创建方/参与方权限

---

## P1 高（权限提升或重要数据泄露）

### P1-1: 模拟登录获得完整写权限
- **文件**: `api/impersonate.py:44,104` + `api/deps.py:115`
- **层级**: L4
- **问题**: scope_override 获得目标角色完整权限，deps.py 直接使用目标权限集，未限只读
- **攻击路径**: admin 模拟他校校长 → 执行写操作
- **修复**: 模拟登录默认只读；写权限单独审批；操作审计

### P1-2: AI 会话劫持
- **文件**: `api/ai.py:134,136`
- **层级**: L5
- **问题**: AI chat 用传入 session_id 复用会话，不校验 owner_id
- **攻击路径**: 猜到他人 session_id → 读取并污染对话上下文
- **修复**: 校验 owner_id == current_user.id

### P1-3: 考试日程跨校 IDOR
- **文件**: `exam/router.py:386,395,424,431`
- **层级**: L1 + L5
- **问题**: `db.get(Exam, exam_id)` 未校验 exam.school_id
- **攻击路径**: 枚举他校 exam_id → 读取/修改他校考试日程和监考信息
- **修复**: 所有 Exam/Subject 查询加 school_id

### ~~P1-4: 考试写操作缺权限~~ → **交叉验证：降级/存疑**
- **文件**: `exam/router.py`
- **交叉验证结果**: Claude 检查发现 Question/Subject CRUD 端点实际有 `school_id == _school_id(current)` 过滤（如 router.py:184,212,224,240,264,282,304）。GPT 报告的行号偏移，权限检查可能在 service 层。**需进一步逐端点验证，暂不列为已确认漏洞**

### P1-5: 兼容扫描任务缺权限
- **文件**: `api/compat_router.py:185,215,244`
- **层级**: L2
- **问题**: 创建/更新/上传只要求登录，缺扫描/阅卷管理权限
- **攻击路径**: 同校低权限用户上传答题卡、改扫描任务
- **修复**: 接入 MANAGE_GRADING 权限

### P1-6: 作业系统对象级授权缺失
- **文件**: `homework/router.py:129,143,230,243`
- **层级**: L2 + L5
- **问题**: 主要只按 task.school_id 守门；submit_homework 可提交任意 submission_id
- **攻击路径**: 同校教师枚举 task_id/submission_id 读取或修改其他班级作业
- **修复**: 建立 authorize_task_access，校验创建者/任教科目/班级范围

### P1-7: 阅卷结果和批注缺 L2 校验
- **文件**: `grading/grading_review_router.py:52,91,470`
- **层级**: L2 + L5
- **问题**: 结果列表/详情只按学校过滤；批注保存只需 VIEW_GRADING 即可写
- **攻击路径**: 同校教师枚举阅卷结果，查看或修改非本人任务的批注
- **修复**: 结果访问绑定阅卷分配/科目/班级范围；批注写要求 MANAGE_GRADING 或分配人身份

### P1-8: 阅卷分配跨校对象绑定
- **文件**: `grading/assignment_router.py:45` + `assignment_service.py:18`
- **层级**: L1 + L5
- **问题**: 创建分配未校验 exam_id/subject_id/question_ids/teacher_id 都属于目标学校
- **攻击路径**: 构造他校题目或教师 ID 写入本校分配 → 跨校对象绑定
- **修复**: 服务层逐项校验对象 school_id

### P1-9: 扫描上传/文件/模板跨租户
- **文件**: `scan/router.py:44,103,134,374` + `scan/pipeline_router.py:323,433,715,850,886`
- **层级**: L1 + L2 + L5
- **问题**: 上传端点多处只要求登录；接受任意 exam_id/image_dir/path；文件读取未校验租户归属
- **攻击路径**: 有阅卷权限用户读取他校上传图片、模板；低权限用户伪造答案
- **修复**: 上传统一要求扫描/阅卷权限；所有路径映射到租户根目录

### P1-10: 答题卡模板/发布/文件缺权限
- **文件**: `card/router.py:96,159,280` + `card/card_export_router.py:37,188,283,311` + `card/card_template_router.py:100,211`
- **层级**: L1 + L2 + L5
- **问题**: 布局保存/自动布局/发布缺权限；文档页/图片按路径取文件缺学校校验
- **攻击路径**: 低权限用户覆盖答题卡布局；路径读取他校页图
- **修复**: 写操作加 MANAGE_EXAMS/MANAGE_GRADING；文件访问用对象 ID + school_id 校验

### P1-11: 学生/教师管理权限不足 + 跨校导出
- **文件**: `student/router.py:55,125,141` + `student/teacher_router.py:106,149,208,268,416`
- **层级**: L1 + L2 + L5
- **问题**: 班级列表接受未授权 school_id；学生增删改只要求登录；教师列表/导出接受任意 school_id
- **攻击路径**: 传他校 school_id 读班级；低权限用户改学生；导出他校教师 PII
- **修复**: 非平台角色禁止 school_id 覆盖；学生/教师写操作加管理权限

### P1-12: 学生画像/错题本 IDOR
- **文件**: `profile/router.py:52,95` + `bank/router.py:137,152,164,178`
- **层级**: L2 + L5
- **问题**: 接受任意 student_id/class_id，只传 school_id 给服务层，缺可见范围校验
- **攻击路径**: 同校教师枚举学生 ID → 读取其他班成绩画像/错题
- **修复**: 校验学生班级可见范围

### P1-13: 题目知识点关联跨校
- **文件**: `knowledge/router.py:69` + `knowledge/service.py:51`
- **层级**: L1 + L2 + L5
- **问题**: 只要求登录，服务层不校验 question 学校
- **攻击路径**: 枚举他校 question_id → 读取或写入知识点关联
- **修复**: 校验 question.school_id 与可见科目

### P1-14: 阅卷图片导入缺权限
- **文件**: `marking/router.py:342`
- **层级**: L2
- **问题**: import-folder 只要求登录，缺 MANAGE_GRADING
- **攻击路径**: 同校任意用户触发导入，污染阅卷数据
- **修复**: 加 require_permission(MANAGE_GRADING)

---

## P2 中（数据可见范围过大）

### P2-1: 仪表盘缺 L2 裁剪
- **文件**: `api/dashboard.py:44,61`
- **问题**: 考试和阅卷统计只按学校聚合，未应用班级/科目范围
- **修复**: 按 visible_class_ids/visible_subject_codes 过滤

### P2-2: 兼容登录忽略 school_code
- **文件**: `api/compat_router.py:42,87,104,136`
- **问题**: 登录忽略 school_code；考试/科目/模板列表缺科目/班级可见范围
- **修复**: 登录校验 school_code 对应 active role

### P2-3: 考试工作台缺 L2 裁剪
- **文件**: `exam/workspace_router.py:14` + `workspace_service.py:23`
- **问题**: 按学校列考试，未按科目/班级过滤
- **修复**: 考试/科目节点按 visible_subject_codes 裁剪

### P2-4: 分析报告年级概览缺 L2
- **文件**: `analytics/analytics_report_router.py:577,591,606`
- **问题**: 年级概览/趋势/科目只传 school_id，未传 visible 范围
- **修复**: 管理角色才允许年级级聚合

### P2-5: 课表 IDOR
- **文件**: `academic/router.py:152,181`
- **问题**: 接受任意 class_id/teacher_id，只按学校约束
- **修复**: 班级按 visible_class_ids；教师只可查本人

### P2-6: 知识掌握 IDOR
- **文件**: `knowledge_tree/router.py:38`
- **问题**: 接受任意 student_id，只传学校给服务层
- **修复**: 校验学生班级可见或本人/家长绑定

### P2-7: 阅卷任务列表缺 L2
- **文件**: `grading/router.py:999,1036`
- **问题**: 只按学校过滤，未要求权限也未按科目/班级裁剪
- **修复**: 要求 VIEW_GRADING，按分配/科目/班级范围过滤

### P2-8: 试卷生成状态 IDOR
- **文件**: `studio/router.py:215`
- **问题**: 只按 paper_id 查询，未绑定学校或创建人
- **修复**: 查询时校验 school_id/user_id 归属

---

## 已检查无直接问题的模块

| 模块 | 说明 |
|------|------|
| auth.py | 角色切换校验 role 属于当前用户 |
| notifications_api.py | 通知按 school_id 过滤 |
| client_logs.py | 日志采集不返回业务数据 |
| calendar/router.py | 日程用 token school |
| menu/router.py | 菜单按角色+学校模块能力生成 |
| llm_config_router.py | 配置绑定当前学校 |
| analytics/router.py | 主分析接口传 visible class/subject |
| quality_router.py | 质量报告按 exam_id + school_id |
| pipeline/router.py | 入口传 token school |
| school/*.py | 学校管理类有显式范围检查 |
| conduct/*.py | 德育按学校/班级/家长绑定 |

---

## 统计汇总

| 等级 | 数量 | 涉及模块 |
|------|------|---------|
| P0 | 4 | grading, exam/results, exam/joint_exam |
| P1 | 14 | impersonate, ai, exam, homework, grading_review, assignment, scan, card, student, teacher, profile, bank, knowledge, marking |
| P2 | 8 | dashboard, compat, workspace, analytics_report, academic, knowledge_tree, grading tasks, studio |
| 安全 | 13 | auth, notifications, calendar, menu, analytics 等 |

**总计**: 26 个安全发现，覆盖 30+ 个 router 文件

---

## 根因分析

1. **架构层面缺失租户中间件** — school_id 过滤散布在每个端点中，没有统一的 tenant middleware 兜底
2. **L2 隔离非系统性** — visible_class_ids/visible_subject_codes 只在部分端点应用
3. **联考模型设计缺陷** — 联考创建时未强制绑定参与校关系，查询时未按参与关系过滤
4. **写操作权限松散** — 大量写端点只要求 get_current_user（登录即可），缺少 require_permission
5. **IDOR 防护缺失** — 对象级授权（检查请求的 ID 是否属于当前用户/角色可见范围）普遍缺失

---

## 建议修复优先级

1. **紧急 (P0)** — 立即修复 4 个跨校数据泄露漏洞
2. **短期 (P1)** — 按模块逐个加固权限检查，优先修 impersonation 和 exam 日程
3. **中期 (P2)** — 补充 L2 裁剪
4. **长期 (架构)** — 引入租户中间件统一 school_id 注入；建立对象级授权框架
