# 数据模型参考（按需查阅）

> 本文件从 CLAUDE.md 移出，按需 Read。不再每次会话注入。

## 数据模型概要

**ORM Import 约定**（见 `docs/arch/orm-placement.md`）：
- **外部代码统一从 `edu_cloud.models.*` 入口 import**（如 `from edu_cloud.models.grading import GradingTask`）
- 模块内部代码可直接 import 本模块 models（如 `modules/exam/service.py` 可写 `from edu_cloud.modules.exam.models import Exam`）
- `edu_cloud.models/` 下每个模块都有对应文件（平台层真实定义 或 re-export stub 指向 `modules/*/models.py`），19 个入口全覆盖

**模块分层规范**：见 `docs/arch/module-template.md`（三类模板 A/B/C + 决策树 + 20 模块现状对照）

| 表 | 关键字段 | 说明 |
|---|---------|------|
| schools | code(唯一), api_key_hash(Optional), is_active, district | 学校档案（原 registered_schools） |
| users | username(唯一), display_name, hashed_password, is_active, employee_id, gender, id_card, title, hire_date, education, university, office_phone, notes | 统一用户（含教师档案 9 列扩展） |
| user_roles | user_id(FK), role, school_id(FK), class_ids, is_primary | 多角色+scope |
| llm_slots | school_id(FK,nullable), slot_number, api_url, api_key, model, is_enabled, tier(nullable) | LLM 槽位配置（学校覆盖>平台默认>.env，tier: mini/standard/advanced） |
| agent_profiles | owner_user_id(FK→users), school_id(FK→schools), profile_type, display_name, preferences(JSON), memory_summary(Text) | Agent 身份（唯一约束：user+school） |
| agent_runs | profile_id(FK→agent_profiles), session_id, tools_resolved(JSON), tools_selected(JSON), model_used, model_tier, intent_domains(JSON), token_input, token_output | Agent 执行记录 |
| joint_exams | name, status(draft→...→archived), subjects(JSON), created_by(FK→users), creator_school_id(FK) | 联考 |
| joint_exam_participants | joint_exam_id(FK), school_id(FK), status, is_creator | 参与校 |
| joint_exam_student_results | joint_exam_id, school_id, subject_code, student_name/number, total_score, detail_scores(JSON) | 成绩明细 |
| documents | type, title, status, content_json, created_by(FK→users), assigned_to(FK), school_id(FK) | Studio 文档 |
| calendar_events | type, title, event_date, school_id(FK), created_by(FK→users), semester, is_active | 校历事件 |
| notification_rules | event_id(FK), days_before, template_type, target_roles(JSON), auto_draft, triggered | 通知触发规则 |
| notifications | document_id(FK), channel, status, target_scope(JSON), school_id(FK) | 通知发送记录 |
| school_settings | school_id(FK), category, key(唯一per school), value(Text,nullable) | 学校 KV 配置 |
| school_modules | school_id(FK), module_code(唯一per school), enabled, config(Text,nullable) | 模块开关（9 codes: exam/grading/homework/study_analytics/research/teaching/calendar/studio/conduct）。`DEFAULT_ENABLED` 默认启用 6 个：exam/grading/homework/calendar/studio/**conduct**（2026-04-13 conduct 加入默认集，现存学校经 `scripts/archived/backfill_conduct_module.py` 补齐（已归档，任务完成），契约测试 `test_default_enabled_includes_conduct` 防止回退） |
| teacher_assignments | user_id(FK), class_id(FK), subject_code, semester, school_id(FK), is_active | 教师排课记录（唯一约束：user+class+subject+semester） |
| subject_selections | school_id(FK), name(唯一per school), subject_codes(JSON), mode, is_active | 学校选考科目组合（模式: 3+1+2/3+3/custom） |
| capabilities | school_id(FK), role, domain, action, enabled(default True) | 学校级角色能力配置（唯一约束：school+role+domain+action） |
| audit_logs | school_id(FK,nullable), user_id(FK,nullable), entity_type, entity_id, action, before_data(JSON), after_data(JSON), request_id | 变更审计日志 |
| homework_tasks | school_id(FK), title, task_type(regular/pre_exam/post_exam), subject_code, class_id(FK,nullable), assigned_by(FK), exam_id(FK,nullable), deadline, status(draft→active→expired→closed), content(Text), grading_mode | 作业任务 |
| homework_submissions | task_id(FK), student_id(FK), status(pending/submitted/graded), score(Float,nullable), feedback(Text), submit_time, content(Text), graded_by(FK,nullable), graded_at | 作业提交记录（唯一约束：task+student） |
| guardian_student_links | guardian_user_id(FK→users), student_id, relationship, is_primary, school_id(FK) | 家长-学生绑定（唯一约束：guardian+student） |
| workflow_runs | workflow_name, trigger_type, trigger_ref, idempotency_key(唯一), status, current_step, total_steps, retry_count, started_at, completed_at, last_error | 工作流执行实例 |
| workflow_steps | run_id(FK→workflow_runs), step_index, step_name, status, input_summary(JSON), output_summary(JSON), started_at, completed_at, error | 工作流步骤记录 |
| exam_analysis_snapshot | exam_id(FK→exams), snapshot_type, target_type, target_id, subject_code, semester, version, status, metrics(JSON), computed_at | 考试分析快照（不可变，版本递增） |
| class_exam_report | exam_id(FK→exams), class_id, grade_rank, class_avg, grade_avg, vs_last_exam, metrics(JSON), version, status, computed_at | 班级考试报告 |
| agent_findings | finding_type, severity, target_type, target_id, summary, detail(JSON), status, notify_roles(JSON), idempotency_key(唯一), resolved_at | Agent 巡检发现（幂等） |
| agent_tasks | finding_id(FK→agent_findings,nullable), task_type, assignee_role, payload(JSON), status, school_id(FK) | Agent 生成的待办任务 |
| score_segment_config | school_id(FK), subject_code(nullable), boundaries(JSON), labels(JSON), created_by(FK→users,nullable) | 学校级分数段配置（默认+科目覆盖，partial unique index） |
| scope_versions | school_id, user_id, version, last_reason（唯一约束：school+user） | Scope 版本追踪（角色变更时递增） |
| entity_memory | entity_type(String30), entity_id, school_id, facts(JSON) | 跨会话实体记忆（student/teacher/class/session_episode），复合索引 (school_id, entity_type, entity_id) |
| project_state | project_type, project_id, owner_id, school_id, state(JSON), checkpoints(JSON,default=[]), status(String20,default=active) | 跨会话项目进度（paper/courseware 等），索引 (owner_id,school_id) + (project_type,project_id) |
| concept_graph_nodes | id(PK,String64), name, knowledge_level(String10), primary_module(idx), description, synced_at, subject, node_type(concept/big_concept), display_order, review_status, reviewed_by, reviewed_at, aliases_json, evidence_ids_json, difficulty, bloom_level | 知识图谱节点（投影自 knowledge.db concepts + big_concepts） |
| concept_big_concept_map | concept_id(PK,FK→nodes), big_concept_id(PK,FK→nodes), is_primary | BigConcept→Concept 映射 |
| concept_graph_edges | id(PK,serial), source_id(FK→nodes), target_id(FK→nodes), relation_type, strength, confidence, review_status(String20,default=ai_draft), synced_at | 知识图谱边（UniqueConstraint: source+target+type） |
| edit_sync_failures | id(PK,serial), operation_json, error_message, created_at | 知识图谱编辑回写失败记录 |
| concept_stats | concept_id(PK,FK→nodes CASCADE), exam_frequency, exam_coverage, avg_difficulty, importance_score, planning_weight(JSON), textbook_chapters(JSON), study_unit_id, estimated_minutes, prerequisite_depth, computed_at | 概念统计指标（Phase 1，从 knowledge.db + MCU 投影计算）|
| answer_logs | student_id, knowledge_point_id, question_id, is_correct, response_time_ms, exam_id, answered_at | 自适应学习作答日志 |
| student_da_mastery | student_id, knowledge_point_id, p_mastery, p_transit, p_slip, p_guess, attempt_count, correct_count, last_updated | BKT 掌握度（唯一：student+kp） |
| da_bkt_params | knowledge_point_id(唯一), p_init, p_transit, p_slip, p_guess, sample_count, last_calibrated | BKT 全局先验参数 |
| da_knowledge_point_map | knowledge_point_id(唯一), concept_node_id(FK→concept_graph_nodes), subject_code, difficulty, bloom_level | 知识点→概念图映射 |
| question_da_override | question_id(唯一), difficulty_override, bloom_level_override, knowledge_point_ids(JSON), reason | 题目自适应属性覆盖 |
| adaptive_cards | student_id, card_type, payload(JSON), status, school_id, created_at | 自适应学习卡片（诊断/推荐） |
| da_catalog_snapshot | snapshot_id(PK), school_id, subject_code, snapshot_data(JSON), created_at | 知识点目录快照 |
