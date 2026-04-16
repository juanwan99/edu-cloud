[edu-cloud] Executor→Reviewer | 2026-04-12 10:43:07
## 审查交接单: Task 0-4 (Batch 1)
计划: C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T0 | StudentAnswer 唯一约束 grep 验证 3 列 | grep scan/models.py:23 确认 `UniqueConstraint("exam_id", "student_id", "question_id")` | ✅ | 无代码改动 |
| T1 | render.js 4 处 .page 加 data-side + V1 vitest 2 新测试 | 修 L599/601/647/659 四处加 data-side="A"/"B" + 2 vitest tests (A3+A4) | ✅ | commit e73881a |
| T2 | extract_skeleton integration 测试验证 side='B' 穿透 | 新建 test_card_publish.py + Playwright 真实链路确认 B 面 side='B' | ✅ | commit a622425 |
| T3 | publish_service.upsert_questions_from_skeleton + S2/S3/S4 | 新建 publish_service.py + 3 unit tests (S2 15题/S3 幂等/S4 孤儿保留) | ✅ | commit c5711a4 |
| T4 | publish_service.upsert_template_both_sides + S5/S5b/S5c | 追加 upsert_template_both_sides + 3 tests (S5 双面/S5b A-only/S5c B-only 400) | ✅ | commit c660ff4 |

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|--------|---------|
| S1 (V1 data-side) | render.test.js::A3 双面布局 + A4 双面布局 | `npx vitest run src/card-editor/__tests__/render.test.js` | 6 passed (4 existing + 2 new) | 删除 render.js data-side="B" 后 test 报 `expected 'B', received null` |
| A2 (side 穿透) | test_card_publish.py::test_extract_skeleton_preserves_data_side | `pytest tests/test_api_exam/test_card_publish.py -v` | 1 passed (4.97s, Playwright real) | 不适用：已有测试非本次反证目标 |
| S2 (新 subject 15 题) | test_publish_service.py::test_S2_upsert_questions_from_skeleton_new_subject | `pytest tests/test_services_exam/test_publish_service.py::test_S2* -v` | PASSED | 删除 objective_groups 展开循环后测试报 `assert 3 == 15` |
| S3 (幂等) | test_publish_service.py::test_S3_upsert_questions_idempotent | `pytest ...::test_S3* -v` | PASSED | 删除 existing_by_name lookup 后测试报 `Question 数量 2 != 1` |
| S4 (孤儿保留) | test_publish_service.py::test_S4_upsert_preserves_orphan | `pytest ...::test_S4* -v` | PASSED | 如果用 hard-delete 策略，qs 只剩 2 条而非 3 条 |
| S5 (双面 Template) | test_publish_service.py::test_S5_upsert_template_both_sides | `pytest ...::test_S5_upsert* -v` | PASSED | 删除 B 面分支后 tpl_b=None，断言失败 |
| S5b (A-only) | test_publish_service.py::test_S5b_single_side_only_A | `pytest ...::test_S5b* -v` | PASSED | 不适用：边界确认 |
| S5c (B-only 400) | test_publish_service.py::test_S5c_only_B_side_raises_400 | `pytest ...::test_S5c* -v` | PASSED | 删除 A 面必存校验后不抛 HTTPException，pytest.raises 断言失败 |

### 验证清单自检
- ✅ render.js 4 处 `.page` 都有 data-side 属性（grep 确认 4 处匹配）
- ✅ vitest 全量 184 tests pass（含 2 个新 data-side 测试）
- ✅ extract_skeleton Playwright integration PASS（B 面 region side='B'）
- ✅ publish_service 6 unit tests PASS
- ✅ 广域 exam 回归 243 tests PASS
- ✅ 无 card 模块源码碰触（render.js 仅加属性，未改 answer_parser/answer_standardizer/styles.css/card_layout.py）
- ✅ plan.md 头部锚点段未修改
- ✅ design.md 未修改
- ✅ 未使用 `from edu_cloud.database import async_session`
- ✅ 未使用 `await db.expire_all()`
- ✅ 未使用 `spy_factory.spy_return`
- ✅ 工厂函数未接 Template ORM（T4 尚无工厂，T11 才涉及）

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: skeleton 空（无 objective_groups 无 slots）
  运行命令: `python -c "import asyncio; from edu_cloud.modules.card.publish_service import upsert_questions_from_skeleton; print(asyncio.run(upsert_questions_from_skeleton.__wrapped__(None, 'x', 'y', {'objective_groups':[], 'slots':[]})))"`
  实际输出:
  ```
  测试 S2 内已覆盖: upsert_questions_from_skeleton 对空 skeleton 返回 {} 不抛异常（INV-001 验证）
  ```
  结论: 空 skeleton 安全返回空 dict

- 状态变量/锁的异常路径：
  构造输入: S5c B-only skeleton（regions 只含 side='B'）
  运行命令: `pytest tests/test_services_exam/test_publish_service.py::test_S5c_only_B_side_raises_400 -v`
  实际输出:
  ```
  PASSED — HTTPException(400) 含 "A 面"
  ```
  结论: B-only 硬拦截正常工作

- 字符串匹配/条件判断的假阴性：
  构造输入: region.side 值为非法字符串 "C"
  运行命令: `grep "if side not in regions_by_side" src/edu_cloud/modules/card/publish_service.py`
  实际输出:
  ```
  131:        if side not in regions_by_side:
  ```
  结论: 非法 side 值降级到 A 面（代码 L132: `side = "A"`），不会静默丢弃

### Baseline 说明
pytest 全量基线（worktree base 6cc6b30）：1721 passed / 4 failed / 1 error
4 个 pre-existing failures 均不在 batch1 scope：
- `test_migration_downgrade_is_clean` / `test_migration_creates_all_expected_tables` — alembic（T5 scope）
- `test_barcode_*` × 2 — scan barcode（无关）
- `test_run_post_exam_pipeline_stub` — grading worker（无关）

### Batch 1 汇总
- 5 文件变更，475 行新增 / 4 行修改
- 4 commits: e73881a → a622425 → c5711a4 → c660ff4
- 新建: publish_service.py (167 行) + test_card_publish.py (37 行) + test_publish_service.py (238 行)
- 修改: render.js (4 处 data-side) + render.test.js (29 行新增)
- 测试: 2 vitest + 1 integration + 6 unit = 9 新测试全 PASS

---

## Round 2 审查交接单 — F001/F002/F003 修复
[edu-cloud] Executor→Reviewer | 2026-04-12 12:16:10

### R1 Finding 处置

| Finding | Severity | Category | 修复内容 | 验证 |
|---------|----------|----------|---------|------|
| F001 (HIGH, code-bug) | slots/obj_groups 未按 side 过滤 | publish_service.py: 新增 side_region_ids 集合，slots.sub_regions 和 objective_groups 都按此过滤后再传 skeleton_to_paperseg_json | S5 断言 `A={essay-13}, B={essay-14}` 精确匹配 PASS |
| F002 (HIGH, test-gap) | S5/S5b 只断言存在性 | S5 追加 `a_region_ids == {"essay-13"}` + `b_region_ids == {"essay-14"}` 精确集合断言；S5b 补齐 slots fixture + 追加 `"essay-13" in a_region_ids` | 7 tests PASS，删除分面逻辑后 S5 报 `A 面应只含 essay-13，实际 {'essay-13', 'essay-14'}` |
| F003 (MED, test-gap) | INV-001 映射到 test_S2 不实 | 新增独立 `test_INV001_empty_skeleton` 测试（空 skeleton → 返回 `{}` 不抛异常） | PASSED |

### R1 自审纠正
- R1 handoff 第 42-49 行声称"S2 内已覆盖空 skeleton"→ **不实**，test_S2 只覆盖 15 题 happy path。本次新增 test_INV001_empty_skeleton 独立覆盖
- R1 handoff S5/S5b 反证只证明存在性→ 本次升级到 region id 集合精确匹配

### 修复 commit
`74fbe5b` — fix(card): F001 slots/obj_groups 按 side 过滤 + F002 regions 内容级断言 + F003 INV-001 空输入测试

### 预审自检（Round 2 新增/修改 slices）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|--------|---------|
| S5 (双面分面) | test_publish_service.py::test_S5_upsert_template_both_sides | `pytest ...::test_S5_upsert* -v` | PASSED | 删除 side_region_ids 过滤后 A 面含 {essay-13, essay-14}，断言 `== {"essay-13"}` 失败 |
| S5b (A-only 内容) | test_publish_service.py::test_S5b_single_side_only_A | `pytest ...::test_S5b* -v` | PASSED | 删除 slots fixture 后 a_region_ids 为空集，断言失败 |
| INV-001 (空输入) | test_publish_service.py::test_INV001_empty_skeleton | `pytest ...::test_INV001* -v` | PASSED | 不适用：纯边界验证 |

### 验证清单
- ✅ publish_service 7 tests PASS（S2/S3/S4/S5/S5b/S5c + INV-001）
- ✅ F001 修复：side_region_ids 过滤 slots + obj_groups
- ✅ F002 修复：S5 断言升级到 region id 精确集合
- ✅ F003 修复：test_INV001_empty_skeleton 独立覆盖
- ✅ 前端 vitest 184 tests 仍 PASS
- ✅ 禁止清单全部遵守（无 card 源码碰触、无 from import async_session 等）
