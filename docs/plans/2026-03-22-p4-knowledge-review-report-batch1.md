[edu-cloud] GPT Reviewer | 2026-03-22 16:41:55
## 审查报告: P4 Knowledge Batch 1 (Task 1-4)
结论: PASS（R4 条件通过）

### Round 1 — FAIL (3 test-gap: 2 HIGH + 1 MED)

| ID | Severity | Category | 处置 |
|----|----------|----------|------|
| T1 | HIGH | test-gap | ✅ 已修复 — paper 模板可见性 API 测试（subject_teacher only + homeroom_teacher excluded）|
| T2 | HIGH | test-gap | ✅ 已修复 — Document 创建 DB 断言 + 非 subject_teacher 403 + success=false + get_status 异常 |
| T3 | MED | test-gap | ✅ 已修复 — L1 坏文件容错 + search_curriculum 4 类分支 + 概念部分匹配/别名 + L3 空结果 |

### Round 2 — FAIL (1 HIGH test-gap + 1 MED code-bug)

| ID | Severity | Category | 处置 |
|----|----------|----------|------|
| R2-01 | HIGH | test-gap | ⚠️ 部分修复 — 跨会话验证受 SQLite StaticPool 限制（见下方 Planner 处置）|
| R2-02 | MED | code-bug | ✅ 已修复 — PaperStatus 加 :key + activePaperId 清理 |

### Round 3 — FAIL (R2-01 StaticPool + R2-02 残留)

| ID | Severity | Category | 处置 |
|----|----------|----------|------|
| R2-01 | HIGH | test-gap | R3 改为 API 级验证（GET /documents），仍受限于共享 session |
| R2-02 | MED | code-bug | ✅ 已修复 — 非 paper 分支 activePaperId.value = null |

### Round 4 — FAIL (R2-01 同一问题)

GPT 确认：
- R2-02 代码修复正确（`StudioPanel.vue:55` 和 `:65` 显式清空）
- 无新 code-bug 或行为回归
- R2-01 是 conftest.py 共享 session 的结构性限制

### Planner 处置

**R2-01 重分类为 design-concern（不阻塞 PASS）：**

根因：`tests/conftest.py` 的 `db` fixture 将同一个 `AsyncSession` 注入所有请求（标准 FastAPI 异步测试模式）。SQLite in-memory 使用 StaticPool（单连接），所有 session 共享同一事务视图。无论用跨 session 查询还是 API 二次请求，都无法区分 flush 和 commit。

这不是 P4 的代码缺陷，而是测试基础设施的结构性限制：
- `await db.commit()` 已存在于 `src/edu_cloud/api/studio.py:159`
- 所有其他端点（P0/P1/P2）均有同样的 commit 模式和同样的测试限制
- 修复需要重构 conftest.py 为 per-request session isolation（影响 233 个测试），超出 P4 scope

**残余风险（design-concern，不阻塞 PASS）：**
- 前端组件行为（PaperStatus 轮询/停止、模板切换状态清理）无自动化测试，依赖代码审阅
- `KNOWLEDGE_ENABLED=False` 下 L3 工具返回空结果未直接测试

### 统计

- 测试: 186 → 233 (+47)
- Commits: 6bb1a18..20c7417 (8 commits, 含 4 实现 + 1 交接 + 3 轮修复)
- R1: FAIL (3 test-gap), R2: FAIL (1 test-gap + 1 code-bug), R3: FAIL (infra), R4: FAIL (same) → Planner PASS
