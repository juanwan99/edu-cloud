[edu-cloud] GPT Reviewer | 2026-04-13 20:22:00

## 审查报告: Task 19-22
结论: PASS

### 第二轮 Round 3 重审 (commit 93f0b60)

本轮只复核上一版唯一阻塞项 F007（`test_export_rankings_excel` 的 test-gap），不重复审查已在 Round 3 首轮确认的 F002 / F004 / F006 records / N001。

- 已执行：
  - `git log --oneline e584e6a~1..93f0b60`
  - `git diff 93f0b60~1..93f0b60 -- tests/test_conduct/test_admin_api.py`
  - 通读 `tests/test_conduct/test_admin_api.py` 中修改后的 `test_export_rankings_excel`
  - 通读 `src/edu_cloud/modules/conduct/export_service.py` 的 `export_rankings_excel`
  - 额外执行 `pytest -q tests/test_conduct/test_admin_api.py -k test_export_rankings_excel`，结果通过
- 静态判定：
  - a. 若删除 service 中的 `SUM(points)` 聚合，测试会失败。当前测试固定断言学生 B 总分为 `10 (=7+3)`、学生 A 总分为 `-3 (=2-5)`；任何“取单条记录值 / 非聚合值 / 重复行”实现都无法同时满足这两个断言与 `len(rows) == 3`。
  - b. 若把 `ORDER BY ... DESC` 改成 ASC，测试会失败。当前测试显式断言第 1 名是李四（10 分）、第 2 名是张三（-3 分），并且补了一条 `rows[1][3] > rows[2][3]`，顺序反转后立即红。
  - c. 若清空 select 返回，测试会失败。工作簿只剩 header，`len(rows)` 会从预期 `3` 退化为 `1`。
  - d. 该测试不是逻辑镜像。它校验的是 HTTP 导出的最终 Excel 可观察契约：排名、姓名、学号、总积分；期望值来自手工构造数据的业务结果，不是把 SQL 查询或排序实现原样复述一遍。
- 结论：
  - F007 已 resolved-correct。
  - 本轮未发现新的 HIGH / MED code-bug 或 test-gap finding。

### 第一段：测试充分性（Test Adequacy）

先审测试，再审实现。Round 3 首轮的唯一阻塞点是 F007：旧版 `test_export_rankings_excel` 只覆盖“单学生、零积分”，无法证明排行榜导出的“聚合 + 排序”核心语义。

本次补丁已把这个缺口补实：

- `test_export_rankings_excel` 现在构造 2 名学生、4 条积分记录，且两名学生总分一正一负，避免单学生/同分场景掩盖错误。
- 断言覆盖了三个关键维度：返回行数、排名顺序、聚合总分。
- 该测试对错误实现具有有效杀伤力：
  - 破坏 `SUM(points)` 会导致总分不再是 `10 / -3`；
  - 破坏 `ORDER BY total DESC` 会导致第 1 行不再是李四；
  - 返回空结果或重复/缺失结果会导致行数断言失败。

因此，Round 3 首轮报告中“F006 只完成一半”的结论，在本次补丁后已闭环；F007 不再构成阻塞。

### 第二段：行为正确性（Behavioral Correctness）

`src/edu_cloud/modules/conduct/export_service.py` 中 `export_rankings_excel()` 的核心实现仍是：

- `select(Student, coalesce(sum(ConductRecord.points), 0).label("total"))`
- `outerjoin(ConductRecord, ConductRecord.student_id == Student.id)`
- `group_by(Student.id)`
- `order_by(coalesce(sum(ConductRecord.points), 0).desc())`

修改后的测试针对的正是这段实现的外部行为，而不是与其同构的内部复述：

- 它通过 API 实际导出 Excel，再用 `openpyxl` 解包断言最终 workbook 内容；
- 它不检查 SQLAlchemy 语句对象本身，也不依赖内部标签名或表达式拼装细节；
- 它验证的是业务契约“谁排第 1、谁排第 2、各自总分是多少”，这正是排行榜导出对外承诺的行为。

因此，从行为正确性角度看，F007 对应的测试补丁是有效的回归保护，而不是表面覆盖。

### 第三段：未测试风险（Non-tested Risks）

本轮仅复核 F007。就这次补丁本身而言，未再看到新的 HIGH / MED 级残余风险。

- 未覆盖的 tie-breaker（同分时稳定顺序）不属于 F007 首轮 finding 的缺口，也不是本次补丁声称要解决的目标。
- `semester_id` 分支未被这个测试触达，但这同样不属于本次 F007 补丁的回归面；当前补丁已充分闭环首轮指出的“SUM / ORDER BY 语义未测”问题。

### 发现清单

本轮无阻塞 finding。

### 结论

第二轮 Round 3 重审确认：commit `93f0b60` 已把 F007 从 `resolved-partial` 提升为 `resolved-correct`。由于本轮未发现新的 HIGH / MED 阻塞项，Round 3 最终结论为 PASS。
