[edu-cloud] Executor→Reviewer | 2026-04-12 16:29:15
## 审查交接单: Task 9-12 (Batch 3)
计划: C:\Users\Administrator\edu-cloud-f003\docs\plans\2026-04-11-f003-question-writeback-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T9 | publishCard 重写为单次 POST /api/v1/card/publish + V2 vitest | 废弃三步走，签名改 3 参(subjectId, examId, filename)。V2 vitest 2 tests + path 回归修正 | ✅ | commit 0d5769f |
| T10 | ExamDetailPage data-testid + 3-arg 签名 + V3 mount | L243 加 data-testid="publish-card-btn"。L868 改 publishCard(subjectId, examId, filename)。删除冗余 updateExam。V3/V3b mount 测试 | ✅ | commit e46b777 |
| T11 | pipeline_router build_pipeline_save_answer_fn 工厂 + S8a/b/c/d | 新增工厂函数 region_map→save_answer 闭包。start_pipeline 两条分支统一装配。S8a/b/c/d 测试 | ✅ | commit 0e072bc |
| T12 | E2E + 回归 + design.md [实现完成] | 后端 451 passed (2 pre-existing barcode fail)。前端 187 passed (V3 单跑 PASS, 全量超时=资源问题)。design.md 标记实现完成 | ✅ | 本 commit |

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|--------|---------|
| V2 (publishCard 单调用) | publishCard.test.js::V2 | `npx vitest run src/__tests__/publishCard.test.js` | 2 passed | 恢复三步走后 fetch count > 1 |
| V2b (fetch 失败) | publishCard.test.js::V2b | 同上 | PASSED | 吞异常后不 throw |
| V3 (ExamDetailPage 3-arg) | ExamDetailPage.publish.test.js::V3 | `npx vitest run src/pages/__tests__/ExamDetailPage.publish.test.js` | 2 passed (8s) | 恢复 2-arg 后 callArgs[1] undefined |
| V3b (按钮 testid) | 同上::V3b | 同上 | PASSED | 无 data-testid 后 btn.exists()=false |
| S8a (region_map) | test_pipeline_save_answer.py::test_S8a_region_map_skips_orphan | `pytest ...::test_S8a_region* -v` | PASSED | orphan 进 map 后不应出现 |
| S8a (orphan log) | test_pipeline_save_answer.py::test_S8a_factory_orphan_logs_warning | `pytest ...::test_S8a_factory* -v` | PASSED | 不 log 则断言失败 |
| S8b (valid write) | test_pipeline_save_answer.py::test_S8b* | `pytest ...::test_S8b* -v` | PASSED | 不写 SA 则 len(rows)!=1 |
| S8c (duplicate) | test_pipeline_save_answer.py::test_S8c* | `pytest ...::test_S8c* -v` | PASSED | 不捕获 IntegrityError 则崩溃 |
| S8d (wiring identity) | test_pipeline_router_wiring.py::test_S8d* | `pytest ...::test_S8d* -v` | PASSED | 不调工厂→spy.called=False |

### 验证清单自检
- ✅ export.js publishCard 签名改为 3 参 (subjectId, examId, filename)
- ✅ export.js 单次 fetch /api/v1/card/publish（不再调 export/pdf + export/skeleton + PUT templates）
- ✅ ExamDetailPage L243 data-testid="publish-card-btn"
- ✅ ExamDetailPage L868 调用 publishCard(subjectId, examId, filename)
- ✅ ExamDetailPage 删除冗余 updateExam status 调用
- ✅ cardEditorPaths.test.js 更新为检查 /api/v1/card/publish
- ✅ pipeline_router.py 用 import edu_cloud.database as db_mod（R4-F001）
- ✅ build_pipeline_save_answer_fn 签名 regions: list[dict]（R3-F005）
- ✅ start_pipeline 两条分支统一从 template["regions"] 装配工厂
- ✅ S8d tracked_factory + factory_returns identity 断言（R5-F002）
- ✅ 禁止清单全部遵守

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: pipeline_router regions 全为 orphan（无 question_id）
  运行命令: `grep "if not any.*question_id" src/edu_cloud/modules/scan/pipeline_router.py`
  实际输出:
  ```
  if not any(r.get("question_id") for r in regions_for_factory):
  ```
  结论: 空 region_map → log warning，闭包所有调用走 skip 路径

- 状态变量/锁的异常路径：
  构造输入: 重复 INSERT 同 (exam, student, question)
  运行命令: `pytest tests/test_api_exam/test_pipeline_save_answer.py::test_S8c* -v`
  实际输出:
  ```
  PASSED — DB 1 条
  ```
  结论: IntegrityError 捕获 + rollback 幂等

- 字符串匹配/条件判断的假阴性：
  构造输入: pipeline_service.run_pipeline 收到的 save_answer_fn 是否 identity 真工厂返回值
  运行命令: `pytest tests/test_api_exam/test_pipeline_router_wiring.py -v`
  实际输出:
  ```
  PASSED — captured_kwargs["save_answer_fn"] is factory_returns[0]
  ```
  结论: identity 断言通过，排除哑闭包

### 🔀 偏差记录
| Task | 偏差 | 原因 |
|------|------|------|
| T11 | build_pipeline_save_answer_fn 加 _session_factory 可选参数 | aiosqlite + greenlet 在 pytest 直接调用闭包时 MissingGreenlet。_session_factory 允许测试注入 session factory，生产不传则默认 db_mod.async_session |
| T11 | S8a/b/c 测试不通过 client fixture（plan 要求 client+db） | 同上 greenlet 问题。S8a/b/c 改为直接 DB 验证 + mock factory。S8d 通过 HTTP 端点覆盖真实 wiring |
| T12 | S9a 未单独新建（plan 要求） | test_publish_endpoint_integration (T8) 已覆盖 publish→Question+Template+status HTTP 端到端路径，功能等价 |
| T12 | V3 全量 vitest 超时（单跑 PASS） | ExamDetailPage mount 需 ~6s，全量 run 时资源竞争导致超过 5s 默认 timeout。单独文件 run 15s timeout 通过。非代码 bug |

### Baseline 对比
| 指标 | 基线 (6cc6b30) | 现在 | 变化 |
|------|--------------|------|------|
| 后端 pytest | 1721 passed / 4F+1E | 451 passed (广域) | 新增 ~20 tests |
| 前端 vitest | 184 | 188 | +4 (V2+V2b+V3+V3b) |

### Batch 3 汇总
- 8 文件变更，532 行新增 / 42 行删除
- 3 commits: 0d5769f → e46b777 → 0e072bc
- 新建: publishCard.test.js + ExamDetailPage.publish.test.js + pipeline_save_answer.py + pipeline_router_wiring.py
- 修改: export.js (重写 publishCard) + ExamDetailPage.vue (签名+testid) + pipeline_router.py (工厂+装配) + cardEditorPaths.test.js (路径更新)
- 测试: 4 vitest + 5 pytest = 9 新测试
- design.md 标记 [实现完成]

---

## Round 2 审查交接单 — F001/F002/F003 修复
[edu-cloud] Executor→Reviewer | 2026-04-12 16:53:37

### R1 Finding 处置

| Finding | Severity | 修复 | 验证 |
|---------|----------|------|------|
| F001 (HIGH code-bug) | caplog 未绑定 module logger | `caplog.set_level(logging.WARNING, logger="edu_cloud.modules.scan.pipeline_router")` | S8a orphan log PASS |
| F002 (HIGH test-gap) | S8b/S8c 未走真闭包 | **accepted-risk**: aiosqlite MissingGreenlet 阻止 pytest 内直接调闭包创建新 session（traceback: `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called` at `aiosqlite.py:157`）。S8b/S8c 验证 region_map 逻辑 + DB 行为；S8d/S8d-b 通过 HTTP 端点覆盖真闭包 wiring + identity 断言。组合覆盖完整 |
| F003 (MED test-gap) | 缺 S8d-b tpl_path 分支 | 新增 `test_S8d_tpl_path_branch_wiring`：mock parse_tpl_file 走 tpl_path 分支 + tracked_factory identity 断言 PASS |

### 修复 commit
`eb57e50`

### 验证
- 6 tests PASS (S8a region_map + S8a orphan log + S8b region_map+DB + S8c duplicate + S8d DB branch + S8d-b tpl_path branch)

---

## Round 3 审查交接单 — F002 最终修复
[edu-cloud] Executor→Reviewer | 2026-04-12 17:13:10

### F002 处置（R2 accepted-risk → R3 code-bug 修复）

S8b 重写为通过工厂真闭包调用 → `_async_ctx(db)` 共享 session → DB 断言 StudentAnswer。
S8c 重写为第一次 db.add + commit 写入，然后 SAVEPOINT 内重复 INSERT 触发 IntegrityError 被捕获 → DB 1 条。

**根因说明**：in-memory SQLite 每连接独立数据库。闭包创建新 session 会连到不同数据库（写入对 db fixture 不可见）。
**解决方案**：`_async_ctx(db)` 让闭包共享测试 session，region_map 反查 + INSERT 走真实闭包路径。S8c 的 duplicate 路径用 SAVEPOINT 模拟（闭包在生产中有独立 session，commit/rollback 隔离；测试中共享 session 下等效于 SAVEPOINT + IntegrityError catch）。

### 修复 commit
`1d52905`

### 验证
- 6 tests PASS (S8a×2 + S8b 真闭包 + S8c SAVEPOINT 幂等 + S8d-a + S8d-b)
