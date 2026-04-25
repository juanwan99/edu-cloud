[edu-cloud] GPT Reviewer | 2026-03-30 09:36:21
## 审查报告: Task 1-8
结论: PASS (Round 3)

### 变更理解

本批次为 edu-cloud 添加三个独立子系统：
1. **Capability 可配置权限层** — Capability ORM (school×role×domain×action) + Service (init/get/set/check 宽松策略) + API (GET/PATCH/POST init，MANAGE_SCHOOL_SETTINGS 权限 + 跨校防护)
2. **ScopeFilter 查询工具** — 基于 UserRole 的 school_id/class_ids/grade_ids/subject_codes 自动注入 WHERE 条件，集成到 list_assignments
3. **AuditLog 审计日志** — AuditLog ORM + @audited 装饰器 (before/after snapshot) + write_audit_log + API (GET，支持 entity_type/user_id/action/date 过滤分页)

三者独立叠加在现有 Permission RBAC 之上，不修改现有代码。

### 对抗性审查

GPT Round 1 构造了 3 个对抗性场景：
- **班主任班级越权**: ScopeFilter 集成只传 subject_col 不传 class_col → 班主任看到全校排课（CR-01，已修复）
- **并发双击 init**: 两个请求同时初始化能力 → SELECT 间隙 autoflush 触发 IntegrityError 500（CR-02，R3 修复）
- **日期过滤空转**: 删除 start_date/end_date 过滤逻辑，全部测试仍通过（CR-03，已修复）

### 发现清单

| ID | Severity | Category | Evidence | Impact | 状态 |
|----|----------|----------|----------|--------|------|
| CR-01 | MED | code-bug | teacher_assignment_service.py:27 — scope.apply 缺 class_col | 班主任角色 class_ids 限域失效 | R2 修复 ✅ |
| CR-02 | MED | code-bug | capability_service.py:69 — SELECT 循环触发 autoflush 撞唯一约束 | 并发 init 返回 500 | R3 修复 ✅ (autoflush=False + IntegrityError catch) |
| CR-03 | MED | test-gap | test_audit_logs.py — start_date/end_date 无测试 | 过滤逻辑可被删除而不被发现 | R2 修复 ✅ |

### 审查轮次摘要

| Round | 结果 | 修复内容 |
|-------|------|---------|
| R1 | FAIL (3 MED) | CR-01 class_col + CR-02 try/except IntegrityError + CR-03 date filter test |
| R2 | FAIL (1 MED) | CR-02 async with db.no_autoflush 破坏 async session |
| R3 | PASS | CR-02 改为 db.autoflush=False + try/finally 恢复 |

### 测试充分性
- plan 中声明的边界条件均有对应测试
- F-06 API 级 user_id/request_id 验证有效
- F-04 upsert create/update 区分有效
- CR-01 class_ids scope 过滤有效
- CR-03 日期过滤有效

### 未测试风险
- 并发: CR-02 已在架构层修复（autoflush=False + IntegrityError catch）
- 空值: user_id=None 审计 F-02 修复有效
