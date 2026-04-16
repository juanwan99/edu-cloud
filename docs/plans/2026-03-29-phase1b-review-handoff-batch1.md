[edu-cloud] Executor→Reviewer | 2026-03-29 23:24:32
## 审查交接单: Task 1-7
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-phase1b-base-info-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | TeacherAssignment ORM model + conftest import | commit 11c5d97, model + 2 tests | ✅ | |
| T2 | Teacher assignment service (4 functions) | commit 7a5ed01, service + 6 tests (含 P2 fix) | 🔀 | P2 fix: 新增 class_ids school_id 归属校验 + 跨校拒绝测试 |
| T3 | Teacher assignment API (4 endpoints) + scope guard | commit c7e0865, router + 8 tests (含 P6 fix) | 🔀 | P6 fix: class_ids Field(min_length=1) + 空数组拒绝测试 |
| T4 | SubjectSelection model + service (4 functions) | commit 8e4a798, model + service + 10 tests (含 P1 fix) | 🔀 | P1 fix: IntegrityError → ConflictError + 重复名测试 |
| T5 | Subject selection API (4 endpoints) + scope guard | commit c4a8b73, router + 9 tests (含 P1 API 覆盖) | 🔀 | P1 API fix: 重复名返回 409 |
| T6 | Alembic migration + env.py + test imports | commit 6efd90f, migration trimmed (仅新表) | ✅ | autogenerate 含 Phase 1a 残留，手动清理 |
| T7 | Frontend pages + API clients + sidebar + routes | commit 498efd5, 2 pages + 2 API clients + sidebar + router + test fix | 🔀 | P5 fix: router.test.js 15→17 路由计数 |

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） |
|---------------|------------------|---------|------------------------------|
| 批量创建幂等 | test_teacher_assignment_service::test_create_assignments_idempotent | `pytest tests/test_services/test_teacher_assignment_service.py::test_create_assignments_idempotent -v` | PASSED |
| 过滤查询 | test_teacher_assignment_service::test_list_assignments_filter | `pytest tests/test_services/test_teacher_assignment_service.py::test_list_assignments_filter -v` | PASSED |
| 跨校越权拦截 | test_teacher_assignments::test_principal_cannot_access_other_school_assignments | `pytest tests/test_api/test_teacher_assignments.py::test_principal_cannot_access_other_school_assignments -v` | PASSED |
| 校验规则拒绝 | test_subject_selections::test_create_selection_invalid_mode | `pytest tests/test_api/test_subject_selections.py::test_create_selection_invalid_mode -v` | PASSED |
| P1: 重复名 ConflictError | test_subject_selection_service::test_create_selection_duplicate_name | `pytest tests/test_services/test_subject_selection_service.py::test_create_selection_duplicate_name -v` | PASSED |
| P2: 跨校 FK 拒绝 | test_teacher_assignment_service::test_create_assignments_rejects_cross_school_class | `pytest tests/test_services/test_teacher_assignment_service.py::test_create_assignments_rejects_cross_school_class -v` | PASSED |
| P6: 空 class_ids 拒绝 | test_teacher_assignments::test_create_assignments_empty_class_ids_rejected | `pytest tests/test_api/test_teacher_assignments.py::test_create_assignments_empty_class_ids_rejected -v` | PASSED |
| P5: router test 更新 | router.test.js::AppShell has 17 child routes | `npx vitest run` | 68 passed |

### 验证清单自检
- ✅ UniqueConstraint 防止同教师同班同科同学期重复 — test_teacher_assignment_unique_constraint PASSED
- ✅ ForeignKey 关联 users/classes/schools — model 定义正确
- ✅ is_active 默认 True — test_teacher_assignment_model 验证
- ✅ require_permission(MANAGE_SCHOOL_SETTINGS) 保护所有端点 — test_assignments_requires_auth PASSED
- ✅ _check_school_scope 跨校防护 — test_principal_cannot_access_other_school_assignments PASSED (403)
- ✅ subject_codes 长度校验 1-7 — test_create_selection_too_many_subjects + test_create_selection_empty_subjects PASSED
- ✅ mode 枚举校验 — test_create_selection_invalid_mode PASSED (422)
- ✅ 同校同名唯一约束 → ConflictError — test_create_selection_duplicate_name PASSED + API test_create_selection_duplicate_name (409) PASSED
- ✅ P2: class_ids 归属校验 — test_create_assignments_rejects_cross_school_class PASSED
- ✅ P6: class_ids min_length=1 — test_create_assignments_empty_class_ids_rejected PASSED (422)
- ✅ P5: router.test.js 更新 — 68 frontend tests PASSED
- ✅ Alembic migration smoke test — 3 tests PASSED (upgrade/head-single/downgrade)

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: create_assignments with class_ids belonging to another school
  运行命令: `python -m pytest tests/test_services/test_teacher_assignment_service.py::test_create_assignments_rejects_cross_school_class -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 跨校外键校验正确拒绝

- 新增文件的边界 case：
  构造输入: create_selection with duplicate name in same school
  运行命令: `python -m pytest tests/test_services/test_subject_selection_service.py::test_create_selection_duplicate_name -v`
  实际输出:
  ```
  PASSED
  ```
  结论: IntegrityError 正确转换为 ConflictError

- 字符串匹配/条件判断的假阴性：
  构造输入: POST /assignments with empty class_ids=[]
  运行命令: `python -m pytest tests/test_api/test_teacher_assignments.py::test_create_assignments_empty_class_ids_rejected -v`
  实际输出:
  ```
  PASSED (422)
  ```
  结论: Pydantic min_length=1 正确拒绝空数组

### 全量测试结果
```
845 passed, 1 warning in 319.83s
```
前端: 68 passed (6 test files)
