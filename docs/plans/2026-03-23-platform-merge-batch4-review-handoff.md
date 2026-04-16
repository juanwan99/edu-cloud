---
type: review-handoff
batch: 4
created: 2026-03-23 13:15:00
plan: docs/plans/2026-03-22-platform-merge-plan.md
design: docs/plans/2026-03-22-platform-merge-design.md
---

# Batch 4 审查交接单 — AI Agent & Workers

## 变更摘要

| Task | 描述 | Commits | 文件数 |
|------|------|---------|--------|
| 16 | AI Agent 核心合并 | 590b7de | 10 |
| 17 | AI 工具合并 + RBAC | 8a71b9b | 14 |
| 18 | Workers 合并 | 5a10279 | 5 |

**总计**: 3 commits, 27 files changed, +1940/-405 lines, 350 tests (基线 332 → 350)

## Task 16: AI Agent 核心合并 (590b7de)

### 变更内容

| 文件 | 操作 | 说明 |
|------|------|------|
| ai/schemas.py | 替换 | 取 exam-ai 版本（75 LOC）：ChatMessage.to_dict, ToolCall.from_openai/to_openai（Gemini _raw 兼容），AgentEvent 保留 edu-cloud 的 data=dict 默认 |
| ai/llm.py | 替换 | 取 exam-ai 版本（209 LOC）：LLMChatClient 双协议（OpenAI+Anthropic 自动检测），重试机制，llm-proxy slot 支持 |
| ai/context.py | 合并 | 保留 build_system_prompt + ROLE_CN（edu-cloud 原有），新增 AgentContext 类（session 管理 + token 预算裁剪 80K，exam-ai 版本） |
| ai/anonymizer.py | 替换 | 取 exam-ai 版本（66 LOC）：字段检测匿名化（_NAME_FIELDS 自动识别 name/student_name/display_name），student_number 自动剥离 |
| ai/agent.py | 修改 | 保留 edu-cloud 结构（ROLE_TOOL_CATEGORIES/DB audit/scope 注入），集成 AgentContext 可选多轮（context 和 anonymizer 为 keyword-only 参数，向后兼容），移除 _extract_names（被 Anonymizer 字段检测替代） |
| api/ai.py | 合并 | 新增 ChatRequest Pydantic 模型（消息验证），_sessions dict 缓存多轮会话，sessions CRUD 端点（GET/DELETE），LLMChatClient 替换 LLMClient，SSE done 事件 |
| ai/audit.py | 保留 | edu-cloud DB 持久化方案不变 |

### 设计决策

1. **agent.py 保留 edu-cloud 结构而非取 exam-ai loop.py**：edu-cloud 版本已有 ROLE_TOOL_CATEGORIES、DB audit、scope injection、_class_ids/_user_id 注入，这些是平台必需功能。exam-ai 的改进（AgentContext、字段匿名化）以可选参数方式集成。
2. **AgentContext 为可选**：`Agent.run()` 的 `context` 和 `anonymizer` 参数有默认值（None → 创建临时实例），既支持 api/ai.py 的多轮会话，又不破坏现有测试。
3. **ChatRequest 验证返回 200+error 而非 400**：保持与现有 test_ai_api.py 测试兼容。

### 审查关注点

- [ ] LLMChatClient 的 Anthropic 路径是否正确处理 tool_result 格式（tool_call_id → tool_use_id）
- [ ] AgentContext.build_messages 的 token 裁剪是否在多轮对话中正确保留最新消息
- [ ] api/ai.py 的 _sessions 内存缓存是否有泄漏风险（无 TTL/eviction）

## Task 17: AI 工具合并 + RBAC (8a71b9b)

### 变更内容

| 文件 | 操作 | 说明 |
|------|------|------|
| tools/analytics_score.py | 新建 | L2_analytics（5 tools）：exam_summary/distribution/question_analysis/student_scores/class_scores |
| tools/analytics_compare.py | 新建 | L2_analytics（3 tools）：compare_classes/rank_students/grade_aggregates |
| tools/exams.py | 新建 | L1_exam（3 tools）：exam_list/detail/subject_questions |
| tools/students.py | 新建 | L1_student（4 tools）：class_list/roster/search/profile |
| tools/bank.py | 新建 | L5_bank（2 tools）：error_book/question_stats |
| tools/profile.py | 新建 | L6_profile（4 tools）：trend/knowledge_map/weakness/error_pattern |
| tools/knowledge_db.py | 新建 | L3_knowledge_db（2 tools）：knowledge_tree/question_knowledge_points |
| tools/analytics.py | 修改 | 移除 compare_classes/get_student_profile（被新工具替代），重分类 L1_analytics → L2_cross_school |
| tools/__init__.py | 重写 | 注册全部 10 个工具模块（31 tools） |
| ai/agent.py | 修改 | ROLE_TOOL_CATEGORIES 扩展为 9 类别，新增 parent 角色 |

### RBAC 映射（设计文档 §5.2）

| 角色 | 类别数 | 包含 |
|------|--------|------|
| platform_admin | 全部 | None（无限制） |
| district_admin | 3 | L2_cross_school, L3_knowledge, L3_knowledge_db |
| principal | 8 | L1_exam/student, L2_analytics/cross_school, L3_knowledge/db, L4_action, L6_profile |
| academic_director | 7 | L1_exam/student, L2_analytics/cross_school, L3_knowledge/db, L4_action |
| grade_leader | 6 | L1_exam/student, L2_analytics/cross_school, L3_knowledge/db |
| homeroom_teacher | 8 | L1_exam/student, L2_analytics/cross_school, L3_knowledge/db, L5_bank, L6_profile |
| subject_teacher | 7 | L1_exam/student, L2_analytics/cross_school, L3_knowledge/db, L5_bank |
| parent | 1 | L6_profile |

### 设计决策

1. **旧 analytics.py 的 compare_classes/get_student_profile 被移除**：这两个工具使用旧模型（ExamResult/ClassGroup），被新工具（使用 service 层）替代。
2. **工具注册采用全局装饰器模式**：exam-ai 使用 `register_xxx_tools(registry)` 函数式注册，edu-cloud 使用 `@tools.register()` 装饰器。统一为装饰器模式（更简洁）。
3. **所有工具 import 使用 lazy loading**：service/model 的 import 在函数体内（`from edu_cloud.modules.xxx import ...`），避免循环依赖和启动时间开销。

### 审查关注点

- [ ] 7 个新工具文件的 import 路径是否全部正确指向 edu_cloud.modules.*
- [ ] ROLE_TOOL_CATEGORIES 映射是否与设计文档 §5.2 一致（特别是 parent 角色）
- [ ] analytics.py 删除的 compare_classes 是否有其他代码引用（已用 Grep 确认仅测试引用）
- [ ] 工具注入参数 _visible_classes/_visible_subjects 在 Agent.run 中是否被传递（当前未传递，依赖 _class_ids）

## Task 18: Workers 合并 (5a10279)

### 变更内容

| 文件 | 操作 | 说明 |
|------|------|------|
| workers/grading.py | 新建 | 迁入 exam-ai 的 process_grading_task（193 LOC）+ run_post_exam_pipeline stub |
| worker.py | 修改 | functions 列表新增 process_grading_task + run_post_exam_pipeline |

### 设计决策

1. **_create_llm_client 使用 settings 而非 llm_router**：edu-cloud 没有 llm_router 服务，直接从 settings 读 LLM 配置。后续可集成 llm_slots 表。
2. **run_post_exam_pipeline 为 stub**：profile 快照/错题本更新逻辑待后续实现。

### 审查关注点

- [ ] grading.py 中 LLMClient import 路径是否正确（from edu_cloud.modules.grading.llm_client）
- [ ] process_grading_task 的 session_factory 容错逻辑是否合理（fallback 创建 local_engine）

## 测试覆盖

| 测试文件 | 新增/修改 | 测试数 |
|---------|----------|--------|
| test_schemas.py | +3 新增 | 7 |
| test_anonymizer.py | 重写 | 6 |
| test_context.py | +4 新增 | 6 |
| test_ai_api.py | 无变更 | 5 |
| test_registry.py | 修改 | 9 |
| test_agent.py | 无变更 | 8 |
| test_tools_analytics.py | -5 移除 | 6 |
| test_tools_registration.py | 新建 | 10 |
| test_grading_worker.py | 新建 | 5 |
| **总计** | | **350** (基线 332) |
