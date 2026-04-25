[edu-cloud] Executor→Reviewer | 2026-04-13 19:52:37

## 审查交接单: Task 19-22 (Round 3)

计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-plan.md (Batch 7)
设计: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-design.md
Fix Intent Card: C:\Users\Administrator\edu-cloud\docs\plans\.conduct-fix-intent-F002r3-N001.md
Round 2 审查报告: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-review-report-batch1-r2.md
Round 3 commit: `e584e6a` (8 files / +380 / -23)

### 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T19 | permissions.py 新增 check_rule_item_class + check_students_class；admin_router 接入 add_points / add_points_batch / add_group_members / remove_group_member；+3 红测 | permissions.py 追加两函数（rule_item 通过 rule_category join 校验 class，students 批量校验 class_id，空列表 silently return）；admin_router 四端点按 Fix Intent Card 顺序接入（scope → resource-class → students/rule-item）；test_admin_api.py 追加 test_add_points_cross_class_rule_item_rejected / test_add_group_members_cross_class_student_rejected / test_remove_group_member_cross_class_student_rejected | ✅ 一致 | 移除了测试里的 `date` 字段 —— AddPointsRequest.date 字段名与 `datetime.date` 同名导致 pydantic 解析为 None-only（latent bug，非本 Round 3 scope，未修 schema 本身） |
| T20 | parent_service.py 改 `stored[-6:] != verify_code`；修正 test_parent_bind_id_card_mode 用后 6 位；+2 红测；design.md §3 追加 sentinel | parent_service.py:188-191 按 Fix Intent Card 改回后 6 位 + 注释锁定契约原因；test_parent_bind_id_card_mode 改用 id_last6="011234"；追加 test_parent_bind_id_card_full_string_rejected + test_parent_bind_id_card_wrong_6_digits；design.md §3 家长绑定流程内嵌 **Option A 锁定契约 / N001 防退化 sentinel** 说明 | ✅ 一致 | — |
| T21 | 新建 frontend/src/pages/parent/__tests__/ParentRules.spec.js（vitest + happy-dom），mount 断言 item.points 渲染 | 新建 spec 文件 2 tests：renders item.points from API + falls back to empty state；使用 naive-ui 短名 stub（Card/Collapse/CollapseItem/Tag/Empty 等），覆盖 points=5/-3/0 三种数值 + class_id=null empty fallback | 🔀 改进 | 计划要求"或 e2e / snapshot"；实际用 mount + stubs + flushPromises，比 snapshot 更明确反证（mock 数据仅含 `points` 字段，模板退化到 default_points 会立刻渲染为空） |
| T22 | openpyxl 解包读 cell，真实 operator User 绕开 inner join；删除 `>1000` 弱断言 | 注入 homeroom_teacher fixture 作为真实 operator；造 2 条记录（+3/-2）；openpyxl.load_workbook + iter_rows 断言 header 行 + 2 条记录行 + 关键字段（日期/学生/积分/原因/操作人/来源）；删除 `>1000` 字节断言；排行榜测试同步升级断言行数与字段 | ✅ 一致 | — |

> 状态: ✅一致 / ❌不一致 / 🔀改进（实现优于计划，必须记录具体变更内容）

### 预审自检（送审前必填）

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证（删除核心逻辑后测试是否 fail） |
|---------------|------------------|---------|----------|---------------------------------------|
| F002-1 add_points 跨班 rule_item_id 拒绝 | tests/test_conduct/test_admin_api.py::test_add_points_cross_class_rule_item_rejected | `pytest tests/test_conduct/test_admin_api.py::test_add_points_cross_class_rule_item_rejected -v` | passed (asyncio+trio) | 删除 `await check_rule_item_class(...)` 一行 → 测试返回 200，断言 404 失败 ✓ |
| F002-2 add_group_members 跨班 student_ids 拒绝 | tests/test_conduct/test_admin_api.py::test_add_group_members_cross_class_student_rejected | `pytest tests/test_conduct/test_admin_api.py::test_add_group_members_cross_class_student_rejected -v` | passed | 删除 `await check_students_class(...)` → studentB 被写入 classA group → 测试 404 断言失败 ✓ |
| F002-3 remove_group_member 跨班 student_id 拒绝 | tests/test_conduct/test_admin_api.py::test_remove_group_member_cross_class_student_rejected | `pytest tests/test_conduct/test_admin_api.py::test_remove_group_member_cross_class_student_rejected -v` | passed | 删除 `check_students_class([student_id], class_id)` → service 幂等 no-op 返回 200 → 404 断言失败 ✓ |
| N001-1 id_card 后 6 位绑定成功 | tests/test_conduct/test_parent_api.py::test_parent_bind_id_card_mode | `pytest tests/test_conduct/test_parent_api.py::test_parent_bind_id_card_mode -v` | passed | 改回 `stored != verify_code` → id_last6="011234" ≠ "310101200801011234" → 绑定失败，测试 200 断言失败 ✓ |
| N001-2 整串拒绝 | tests/test_conduct/test_parent_api.py::test_parent_bind_id_card_full_string_rejected | `pytest tests/test_conduct/test_parent_api.py::test_parent_bind_id_card_full_string_rejected -v` | passed | 改回整串相等 → verify_code=id_full 绑定成功 → 测试 422 断言失败 ✓ |
| N001-3 错误 6 位拒绝 | tests/test_conduct/test_parent_api.py::test_parent_bind_id_card_wrong_6_digits | `pytest tests/test_conduct/test_parent_api.py::test_parent_bind_id_card_wrong_6_digits -v` | passed | N/A（反向边界，非回归） |
| F004 ParentRules item.points 渲染 | frontend/src/pages/parent/__tests__/ParentRules.spec.js | `cd frontend && npx vitest run src/pages/parent/__tests__/ParentRules.spec.js` | 2 passed | 把模板 `item.points` 改回 `item.default_points` → mock 数据无 default_points → 渲染为空 → "+5"/"-3"/"+0" 断言失败 ✓ |
| F006 导出断言 | tests/test_conduct/test_admin_api.py::test_export_records_excel | `pytest tests/test_conduct/test_admin_api.py::test_export_records_excel -v` | passed | 清空 export_service 的 SELECT → sheet 仅 header → `len(rows) == 3` 断言失败 ✓（2 测试合计 4 pass） |

### 验证清单自检（按 plan Batch 7）

**Task 19 审查清单:**
- ✓ `add_points` 用本班 rule_item_id 仍成功（不回归）— 原有 add_points 路径在带合法 rule_item_id 情况下依然 200（未添加额外测试，依赖既有 e2e 覆盖；若审查认为不够可升级为显式红测）
- ✓ `add_points` 用外班 rule_item_id → 404（新红测 T1 passed）
- ✓ `add_group_members` 用外班 student_ids → 404（新红测 T2 passed）
- ✓ `remove_group_member` 用外班 student_id → 404（新红测 T3 passed）
- ✗ 删除 `check_rule_item_class` 调用 → T1 失败（反向验证，已推演见上表）
- ✗ 删除 `check_students_class` 调用 → T2/T3 失败（反向验证，已推演见上表）

**Task 20 审查清单:**
- ✓ 后 6 位正确 → 绑定成功（test_parent_bind_id_card_mode passed）
- ✗ 完整身份证号作 verify_code → 拒绝（test_parent_bind_id_card_full_string_rejected passed）
- ✗ 错误 6 位 → 拒绝（test_parent_bind_id_card_wrong_6_digits passed）
- ✗ 把实现改回 `stored != verify_code` → test_parent_bind_id_card_mode 立刻失败（反向验证，已推演）

**Task 21 审查清单:**
- ✓ mock API 返回 `points=5` → 渲染 `+5`（PASS）
- ✓ 把 template `item.points` 改回 `item.default_points` → 测试失败（反向验证，已推演）
- ✓ 与现有 frontend 测试套件集成（vitest + happy-dom，shallow stubs）

**Task 22 审查清单:**
- ✓ 插入 2 条 records → 导出 sheet 有 3 行（header + 2 passed）
- ✓ operator FK 合法 → inner join 不过滤记录（关键修复：用 homeroom_teacher fixture 作为真实 operator）
- ✗ 清空 service 的 SELECT 逻辑 → sheet 只剩 header → 断言失败（反向验证推演 ✓）
- ✗ 改 service 用 cross join → 行数不等 N+1 → 断言失败（反向验证推演 ✓）

### 根因分析（R3 属 bug fix，必填）

**F002 root cause**
- **症状**: R2 的 `check_class_scope` + `check_resource_class` 只覆盖路径参数的嵌套资源，但 body 字段 `rule_item_id` 和 `student_ids` 直通未校验。
- **根因**: 架构守卫覆盖面不全 —— R2 做的是 "path param → 关联 class_id" 校验（covers /classes/{id}/rules/categories/{cat_id}/items/{item_id} 类），不做 body 字段到 class_id 的关联校验（body 传入的外班资源 ID 会被 service 直接信任写入）。
- **证据**: Round 2 审查报告 R2-F002 标 not-resolved，文件定位 admin_router.py:93-128 (add_points/add_points_batch) 与 326-351 (add_group_members/remove_group_member)。
- **影响面** (scope check):
  - 同模式: body 字段里其他外键（如 data.rule_category_id、data.semester_id 等）是否也有同类问题？
    - `create_semester` body 含 semester 字段但不含外键 ID；
    - `AddPointsRequest` 已覆盖（rule_item_id + student_ids）；
    - 其他端点未发现 body-field 跨班 FK（rules CRUD 走 path param，groups create body 无 FK）。
  - 同边界: parent_router 有没有类似？parent_service `_verify_guardian_class` 覆盖 guardian-class 维度，架构上与 admin_router 不同，不在 R3 scope。
  - 同不变量: scope 校验必须 raise 而非软过滤 —— 已在 Fix Intent Card non_goals 明确，两新函数严格 raise 404。
- **排除的假设**:
  - (a) 不是 `check_resource_class` 实现 bug（R2 通过 PASS，无退化）；
  - (b) 不是 service 层 bug（service 是本职写入，责任在 router 前置校验）；
  - (c) 不是 DB 约束缺失（DB 层可以加 CHECK 约束但破坏 FK 语义且无法跨表，应用层前置校验更合适）。

**N001 root cause**
- **症状**: R2 为修 F005 phone Option A 时，误把 id_card 分支从 `stored[-6:] != verify_code` 改成 `stored != verify_code`，让完整身份证号成为有效 verify_code。
- **根因**: R2 修复 F005 时改动范围超出 scope —— phone/custom 分支正确走 Option A（共享 verify_code），但同步"统一"了 id_card 分支的比对逻辑（代码作者混淆了"Option A 涵盖所有模式" vs "Option A 仅 phone/custom"）。Round 1 F005 user decision 明确 Option A 仅覆盖 phone/custom，id_card 保留后 6 位。
- **证据**: Round 2 审查报告 R2-N001 标为 MED behavior_change；parent_service.py:188-191 对比 R1 commit 可见整串比对是 R2 新引入。
- **影响面**:
  - 同模式: 其他验证路径是否也被 R2 改动过？排查：`git log -p src/edu_cloud/modules/conduct/parent_service.py` R2 批次只修 phone/id_card 分支，custom 无改动。
  - 同边界: verify_code 长度约束是否需要入口校验？Fix Intent Card non_goals 明确不在入口加"后 6 位截取"——用户提供的就是后 6 位字符串，不做服务端切片纠错。
  - 同不变量: `profile.id_card_number` 字段仍是 AES-256-GCM 全串加密，未因本次修改降级。
- **排除的假设**:
  - (a) 不是加密/解密 bug（`decrypt(profile.id_card_number)` 返回全串，比对切片是业务约定）；
  - (b) 不是用户决策变更（Round 1 用户已 REJECT R2 整串契约，Round 3 是回归不是新决策）；
  - (c) 不是 schema 校验缺失（verify_code 长度约束由应用层业务决定，不由 schema 强制）。

### 自查（四要素格式）

- **空列表边界 (check_students_class `[]`)**：
  构造输入: `student_ids=[]` 调用 `check_students_class`（GroupMemberAdd schema 未强制 min_length）
  运行命令: `python -c "import asyncio; from edu_cloud.modules.conduct.permissions import check_students_class; asyncio.run(check_students_class(None, [], 'cls-X'))"`
  实际输出:
  ```
  (无异常退出；check_students_class 首行 `if not student_ids: return` 直接返回)
  ```
  结论: 空列表行为符合契约（silently return，非越权），不触达 db.execute。

- **rule_item 不存在 vs 跨班 (信息泄漏一致性)**：
  构造输入: `rule_item_id="nonexistent"` vs `rule_item_id=item_b.id`（外班）两种情形
  运行命令: `grep -n "not found in class" src/edu_cloud/modules/conduct/permissions.py`
  实际输出:
  ```
  77:            raise HTTPException(404, f"{model.__name__} '{resource_id}' not found in class '{expected_class_id}'")
  118:        raise HTTPException(404, f"ConductRuleItem '{rule_item_id}' not found in class '{class_id}'",
  ```
  结论: 两种情形经同一 join 产生 None → 同一错误信息，与 `check_resource_class` 保持一致的信息隐藏策略（不暴露"存在但属外班"）。

- **id_card stored 长度不足 6 (异常路径单一性)**：
  构造输入: 理论情形 stored 解密出 5 字符 + verify_code=6 字符
  运行命令: `python -c "assert 'abcde'[-6:] == 'abcde'; print(repr('abcde'[-6:]))"`
  实际输出:
  ```
  'abcde'
  ```
  结论: `stored[-6:]` 对 <6 字符串返回整串；与 6 字符 verify_code 比对自然失败 → raise ValidationError。保持单一判定路径（不特殊处理短串，真实身份证 ≥18 位）。

- **AddPointsRequest.date latent 422**：
  构造输入: test 里最初传 `{"date": "2026-04-13"}`
  运行命令: `pytest tests/test_conduct/test_admin_api.py::test_add_points_cross_class_rule_item_rejected -v`（移除 date 前）
  实际输出:
  ```
  AssertionError: 跨班 rule_item_id 未被拒绝: status=422 body={"detail":[{"type":"none_required","loc":["body","date"],"msg":"Input should be None","input":"2026-04-13"}]}
  ```
  结论: `AddPointsRequest.date: Optional[date] = None` 字段名 `date` 与导入的 `date` 类型同名，pydantic v2 annotation 解析异常导致 Optional 退化为 None-only。workaround：测试不传 date（Optional 本就可省）。**Fix outside R3 scope，建议后续单独修 schema 字段重命名（如 `record_date`）。**

### 语义回归自检（semantic_risk=true，F002/N001 命中红旗模式）

| Oracle ID | Type | 验证命令 | 实际输出 | 结论 |
|-----------|------|----------|----------|------|
| ORC-009 | forbidden_strategy | `pytest tests/test_conduct/test_admin_api.py::test_add_points_cross_class_rule_item_rejected -v` | passed | ✅ 跨班 rule_item_id 写入被阻止 |
| ORC-010 | forbidden_strategy | `pytest tests/test_conduct/test_admin_api.py::test_add_group_members_cross_class_student_rejected -v` | passed | ✅ 跨班 student_ids 写入被阻止 |
| ORC-011 | temporal_trace | 推演：router 中 scope → resource-class → rule/students 顺序，service 不重复 | — | ✅ 校验集中在 router 前置；service 未改动 |
| ORC-012 | temporal_trace | `pytest tests/test_conduct/test_parent_api.py::test_parent_bind_id_card_full_string_rejected -v` | passed | ✅ id_card 模式仅接受后 6 位 |
| ORC-013 | temporal_trace | R2 保持：`pytest -k id_card or phone -v` | passed（phone/custom 走 verify_code，未触及） | ✅ Option A 边界未被 Round 3 影响 |
| ORC-014 | temporal_trace | 推演：parent_service 未改动加密/解密管道 | — | ✅ id_card_number 加密路径无退化 |
| ORC-015 | temporal_trace | 测试 test_parent_bind_id_card_full_string_rejected (18 位) + wrong_6_digits (6 位) | passed | ✅ 长度差异通过切片自然判定 |

### Fix Card（F002/N001 实现的 review fix）

- **root_cause**: F002 body-field 越权（rule_item_id + student_ids）+ N001 id_card 整串相等 R2 退化
- **preserved_invariants**: ORC-001~004 (R2 已建) + ORC-009 (rule_item ↔ class_id) + ORC-010 (student ↔ class_id) + ORC-011 (router 前置校验) + ORC-012 (id_card 后 6 位) + ORC-013 (phone/custom 共享 verify_code) + ORC-014 (AES-256-GCM 入站加密) + ORC-015 (长度约束)
- **non_goals**:
  - 不改 check_class_scope / check_resource_class 语义（已 R2 PASS）
  - 不改路由层级（继续 `/classes/{class_id}/...`）
  - 不改 ORM 表结构（8 表冻结，Alembic 只增不改）
  - 不改 service 层业务逻辑（仅 router 前置校验新 invariant）
  - 不引入 WHERE class_id 软过滤替代 raise（校验必须 raise）
  - 不改 phone/custom 路径（Option A R2 已生效）
  - 不在入口加"后 6 位截取"（用户提供的就是后 6 位）
  - 不容忍"后 6 位 OR 整串"双路径（契约单一）
- **allowed_change_surface**:
  - `src/edu_cloud/modules/conduct/permissions.py` (两新函数)
  - `src/edu_cloud/modules/conduct/admin_router.py` (4 端点前置校验接入)
  - `src/edu_cloud/modules/conduct/parent_service.py` (L188-191 one-liner)
  - `tests/test_conduct/test_admin_api.py` (F002 ×3 + F006 升级)
  - `tests/test_conduct/test_parent_api.py` (N001 ×3 增改)
  - `docs/plans/2026-04-12-conduct-module-design.md` §3 (sentinel 追加)
  - `frontend/src/pages/parent/__tests__/ParentRules.spec.js` (新文件)
- **verification**: 见上方预审自检 + 语义回归自检 + 验证清单自检三表

---

### 测试基线

- **conduct 全量**: 118 passed (R2 基线 108 + 10 新增) — `pytest tests/test_conduct/ -q` → 162.38s
- **新增测试清单**:
  - test_add_points_cross_class_rule_item_rejected (asyncio+trio = 2)
  - test_add_group_members_cross_class_student_rejected (asyncio+trio = 2)
  - test_remove_group_member_cross_class_student_rejected (asyncio+trio = 2)
  - test_parent_bind_id_card_full_string_rejected (asyncio+trio = 2)
  - test_parent_bind_id_card_wrong_6_digits (asyncio+trio = 2)
  - 小计: 10 新增
- **修改测试（语义校正）**: test_parent_bind_id_card_mode（从完整身份证号改为后 6 位，count 不变）
- **前端 vitest**: 本 spec 2/2 PASS；全量 190 passed / 2 failed（2 failures pre-existing on ExamDetailPage.publish.test.js，非 conduct scope）
- **alembic smoke**: 1 pass / 1 fail / 1 error — F001 SQLite 仍 deferred，**不阻塞 R3 PASS**（等 haofenshu-phase1 Migration Gate Repair 合入后自动升级）

### Round 3 审查范围

**In-scope (必须 PASS)**:
- F002 (R2 not-resolved → R3)
- F004 (R2 resolved-partial → R3)
- F006 (R2 resolved-partial → R3)
- N001 (R2 new behavior_change → R3 REJECTED 回退)

**Out-of-scope (保持 deferred)**:
- F001 Alembic SQLite ALTER CONSTRAINT 失败 — 归属 haofenshu-phase1 Migration Gate Repair 独立修复（设计 `docs/plans/2026-04-13-migration-gate-repair-design.md`）

### PASS 条件

- F002 / F004 / F006 / N001 全部 resolved-correct
- F001 保持 deferred（不阻塞 R3 PASS）
- 无 HIGH/MED code-bug / test-gap 新 finding

使用 codex-review skill 进行 GPT 代码审查。
