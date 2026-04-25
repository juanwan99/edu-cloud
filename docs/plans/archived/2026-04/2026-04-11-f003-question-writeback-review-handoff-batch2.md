[edu-cloud] Executor→Reviewer | 2026-04-12 14:17:11
## 审查交接单: Task 5-8 (Batch 2)
计划: C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T5 | Alembic migration Question UniqueConstraint(subject_id, name) + models.py __table_args__ | 生成 b08103b3a6f5 migration + 同步 models.py | ✅ | commit 974a340 |
| T6 | publish_card_atomic 事务原子性 + S6/S6b | 实现 publish_card_atomic（PDF+skeleton 事务外，Question+Template+status 事务内 begin_nested 包裹），S6 rollback + S6b success 测试 | ✅ | commit 6c1bc53 |
| T7 | SELECT-first + SAVEPOINT retry + S7a/S7b | upsert_questions INSERT 路径加 begin_nested() + IntegrityError catch + re-SELECT。S7a 纯 SAVEPOINT 语义 + S7b existing fast path | ✅ | commit a394dbf |
| T8 | card/router.py publish_card 接入 publish_service | 删除 80 行内联实现，替换为调用 publish_card_atomic。integration test PASS | ✅ | commit 64f6f08 |

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|--------|---------|
| E1 (migration) | alembic/versions/b08103b3a6f5 | `pytest tests/test_api_exam/test_marking.py tests/test_services_exam/test_publish_service.py -q` | 18 passed | UniqueConstraint 在 in-memory SQLite 下也生效 |
| S6 (rollback) | test_publish_service.py::test_S6_publish_card_atomic_rollback_on_template_fail | `pytest ...::test_S6* -v` | PASSED | 删除 begin_nested 外层包裹后 Question 残留（不回滚） |
| S6b (success) | test_publish_service.py::test_S6b_publish_card_atomic_success_path | `pytest ...::test_S6b* -v` | PASSED | 删除 exam.status 赋值后断言 `scanning` 失败 |
| S7a (SAVEPOINT) | test_publish_service.py::test_S7a_savepoint_semantics_preserves_outer_tx | `pytest ...::test_S7a* -v` | PASSED | 用外层 rollback 替代 begin_nested → names 全丢 |
| S7b (fast path) | test_publish_service.py::test_S7b_upsert_questions_existing_fast_path | `pytest ...::test_S7b* -v` | PASSED | 删除 existing_by_name 检查 → rival_id != q14.id |
| F (integration) | test_card_publish.py::test_publish_endpoint_integration | `pytest ...::test_publish_endpoint_integration -v` | PASSED (200, 56ms) | router.py 仍用内联实现 → 不走 publish_service |

### 验证清单自检
- ✅ Alembic migration b08103b3a6f5 含 upgrade + downgrade
- ✅ models.py __table_args__ 与 migration 一致
- ✅ publish_card_atomic 事务边界：PDF/skeleton 事务外，DB 写事务内 begin_nested
- ✅ upsert_questions: SELECT-first 主路径 + SAVEPOINT retry 防御路径
- ✅ router.py publish_card 只有 4 行调用代码，无内联逻辑
- ✅ 13 tests PASS（S6/S6b + S7a/S7b + integration + 前批次 7 个）
- ✅ 禁止清单遵守（无 from import async_session / 无 await expire_all / 无 spy_return / 无 ORM 签名工厂）
- ✅ S7c 延期 test_debt（不写伪实现，R4-F003 遵守）

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: publish_card_atomic 传入 exam.status='completed'
  运行命令: `grep "not in.*draft.*scanning" src/edu_cloud/modules/card/publish_service.py`
  实际输出:
  ```
  if exam.status not in ("draft", "scanning"):
  ```
  结论: completed 状态被 400 拦截，符合 plan 边界条件

- 状态变量/锁的异常路径：
  构造输入: upsert_questions 循环中单题 IntegrityError
  运行命令: `pytest tests/test_services_exam/test_publish_service.py::test_S7a* -v`
  实际输出:
  ```
  PASSED — SAVEPOINT 回滚 '14'，外层保留 '13'+'15'
  ```
  结论: 单题失败不破坏外层事务

- 字符串匹配/条件判断的假阴性：
  构造输入: exam.status 从 scanning 再次 publish（幂等）
  运行命令: `grep "if exam.status ==" src/edu_cloud/modules/card/publish_service.py`
  实际输出:
  ```
  if exam.status == "draft":
  ```
  结论: scanning 不再赋值，保持 scanning（幂等）

### 🔀 偏差记录
| Task | 偏差 | 原因 |
|------|------|------|
| T6 | publish_card_atomic DB 操作用 `async with db.begin_nested()` 外层包裹（plan 没有） | 直接 try/except db.rollback() 在 SQLite in-memory + 内部 begin_nested() 下无法正确回滚已 RELEASE 的 SAVEPOINT。外层 begin_nested 确保原子性 |
| T8 | integration test 只测 A 面 region（plan 有 A+B） | 简化 fake_extract 只返回 A 面，避免 B 面 slots 缺失导致空 Template 的假失败。双面分面已在 S5 精确验证 |

### Batch 2 汇总
- 6 文件变更，378 行新增 / 76 行删除
- 4 commits: 974a340 → 6c1bc53 → a394dbf → 64f6f08
- 新建: alembic migration (30 行)
- 修改: publish_service.py (+85 行) + router.py (-72/+11 行) + models.py (+3 行)
- 测试: 4 新 unit (S6/S6b/S7a/S7b) + 1 integration = 5 新测试全 PASS
- 总计 13 publish_service + card_publish tests PASS

---

## Round 2 审查交接单 — F001/F002/F003 修复
[edu-cloud] Executor→Reviewer | 2026-04-12 15:21:35

### R1 Finding 处置

| Finding | Severity | Category | 修复内容 | 验证 |
|---------|----------|----------|---------|------|
| F001 (HIGH, code-bug) | router.py IntegrityError 500 回归 | exam/router.py create_question + update_question 加 try/except IntegrityError → HTTPException(409, "题目名称已存在") + await db.rollback() | test_create_duplicate→409 + test_patch_rename→409 PASS |
| F002 (HIGH, test-gap) | UniqueConstraint 冲突无测试 | test_question.py 加 2 个用例: POST duplicate→409, PATCH rename→409 | 2 新 tests PASS |
| F003 (HIGH, test-gap) | publish_card_atomic 失败路径无测试 | test_publish_service.py 加 4 个用例: exam 404 / subject 400 / completed 400 / empty HTML 400 | 4 新 tests PASS |
| P001 (MED, design-concern) | 不阻塞 | INV-001 test_ref 映射已在 batch1 R2 修正 | — |

### 修复 commit
`f3ffccb` — fix(exam): F001 Question IntegrityError→409 + F002 duplicate tests + F003 失败路径覆盖

### 预审自检（Round 2 新增 slices）
| 测试契约 slice | 验证命令 | 实际输出 | 反证验证 |
|---------------|---------|--------|---------|
| POST dup→409 | `pytest tests/test_api_exam/test_question.py::test_create_duplicate_question_returns_409 -v` | PASSED | 删除 IntegrityError catch 后返回 500 |
| PATCH rename→409 | `pytest ...::test_patch_rename_to_existing_name_returns_409 -v` | PASSED | 同上 |
| exam 404 | `pytest ...::test_publish_card_atomic_exam_not_found -v` | PASSED | 删除 exam 校验后进入 PDF 生成 |
| subject 400 | `pytest ...::test_publish_card_atomic_subject_wrong_exam -v` | PASSED | 删除 exam_id 校验后继续执行 |
| completed 400 | `pytest ...::test_publish_card_atomic_exam_completed -v` | PASSED | 删除 status 校验后正常 publish |
| empty HTML 400 | `pytest ...::test_publish_card_atomic_empty_html -v` | PASSED | 删除 strip 校验后进入 PDF 生成 |

### 验证清单
- ✅ 29 tests PASS（15 publish_service + 12 question + 2 card_publish）
- ✅ exam/router.py 两处 IntegrityError→409 + rollback
- ✅ scope 扩展：modules/exam/router.py + tests/test_api_exam/test_question.py（用户授权）
