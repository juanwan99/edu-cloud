[edu-cloud] GPT Reviewer | 2026-03-30 07:58:13
## 计划审查报告: Phase 1c Permission Engine (Task 1-8)
结论: FAIL

### GPT Findings + Claude 三态标注

| ID | Severity | Category | 三态 | 处置 |
|----|----------|----------|------|------|
| F-01 | HIGH | design-concern | contested → accepted-risk | 本 Phase 聚焦基础设施层，enforcement 在 Phase 1d |
| F-02 | HIGH | code-bug | **verified** | 必须修复：user_id FK 与 "-" 冲突 |
| F-03 | HIGH | design-concern | contested → accepted-risk | best-effort 审计是明确设计选择 |
| F-04 | MED | code-bug | **verified** | 必须修复：upsert 应区分 create/update |
| F-05 | MED | code-bug | **verified** | 必须修复：id_param 非主键时 db.get 失效 |
| F-06 | MED | test-gap | **verified** | 必须修复：补 API 级审计联动测试 |
| F-07 | LOW | design-concern | verified | 统一为"显式补导入" |
| F-08 | LOW | suggestion | verified | Task 1 已有边界条件，缺测试契约可接受 |

### 逐条分析

**F-01 (HIGH design-concern): Capability 无运行时执法点**
- GPT 论点：计划只建了 CRUD，没有把 check_capability 接入请求链
- Claude 反证：设计文档 §Phase 1c 明确定义 scope 为"Capability 可配置权限层 + ScopeFilter + 审计日志"，enforcement（require_capability 接入端点）属于 Phase 1d scope。这是有意的阶段拆分，不是遗漏
- **终态：accepted-risk**。reason: Capability enforcement 在下一 Phase 实现，本 Phase 交付基础设施

**F-02 (HIGH code-bug): audit_logs.user_id FK 约束与 "-" 默认值冲突** ✅
- GPT 论点完全正确。user_id 是 `ForeignKey("users.id")` 非空列，但 `current_user_var` 默认 "-"，写入时会违反 FK 约束
- **修复方案：** user_id 改为 `nullable=True`，无 user context 时写 `None` 而非 "-"

**F-03 (HIGH design-concern): 审计与业务不同事务**
- GPT 论点：write_audit_log 单独 commit，业务变更和审计可能不一致
- Claude 反证：这是计划中明确的 best-effort 设计选择。审计日志写入失败不应阻塞业务操作。设计文档 §审计日志 明确了"decorator 在 service 层自动记录"的 best-effort 语义。事务合并会引入审计失败→业务回滚的风险，对 MVP 阶段不合适
- **终态：accepted-risk**。reason: best-effort 审计是明确设计选择，Phase 2 可升级为事务内审计

**F-04 (MED code-bug): upsert_setting 固定 action="create"** ✅
- GPT 论点正确。upsert_setting 既创建又更新，但 @audited 固定为 "create"
- **修复方案：** 改为运行时判定——在函数内部先查 existing，根据有无 existing 手动调用 write_audit_log 而非用装饰器；或将装饰器 action 改为 "upsert"

**F-05 (MED code-bug): set_module_enabled 的 id_param="module_code" vs db.get 主键** ✅
- GPT 论点正确。`db.get(SchoolModule, "exam")` 会找不到记录（主键是 UUID）
- **修复方案：** 装饰器 `_entity_type_to_model` 改为支持 `(school_id, key)` 组合查询，或 set_module_enabled 不用 id_param 而是在函数内手动记录 before snapshot

**F-06 (MED test-gap): 无 API 级审计联动测试** ✅
- GPT 论点正确。现有审计 API 测试只验证"调 PATCH /settings 后 audit-logs 有记录"，但没验证 user_id 和 request_id 是否正确传递
- **修复方案：** 在 test_audit_logs.py 补充断言 `data[0]["user_id"] != "-"` 和 `data[0]["request_id"]` 不为 None

**F-07 (LOW design-concern): test_alembic_migration.py 指令矛盾**
- 统一为"显式补导入"，执行时按此处理

**F-08 (LOW suggestion): 缺测试契约和 Tier 标记**
- Task 2-8 已有完整测试契约段。Task 1 是纯 model 定义，边界条件已覆盖。可接受

### 阻塞修复清单（执行前必须解决）

1. **F-02**: `audit_log.py` — `user_id` 改为 `nullable=True`，默认 None
2. **F-04**: `school_settings_service.py` — upsert_setting 运行时判定 create/update
3. **F-05**: `audit_service.py` — 装饰器改用 select 查询而非 db.get，或对 module_code 类型的 id_param 做组合查询
4. **F-06**: `test_audit_logs.py` — 补 user_id + request_id 的 API 级断言
