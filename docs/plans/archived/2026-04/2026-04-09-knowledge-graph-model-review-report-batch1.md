<!-- pre-takeover: archived for history, not active spec -->
[edu-cloud] GPT Reviewer | 2026-04-10 10:12:17
## 审查报告: Task 1-6 (Batch 1 后端)
结论: PASS (R2)

### 第一段：测试充分性（Test Adequacy）
R1 发现 4 个 test-gap（F001-F004），R2 修复后：
- plan 声明的所有边界条件都有对应测试
- edge 状态机 6 种合法转移全覆盖，含最终状态落库断言
- sync/backwrite 新旧 schema 兼容路径覆盖（5 个测试）
- Q3 阈值精确测试（0.7 不报 / 0.69 报 / 已审核排除）
- 发布过滤含 NULL→ai_draft、空视图、parent 角色强制覆盖
- 无 tautology 测试（GPT 反证验证通过）

### 第二段：行为正确性（Behavioral Correctness）

#### 变更理解
本批次在 knowledge_tree 模块上增量实现「可信骨架」：
1. edge 表新增 review_status 列（migration + model + config）
2. Graph API v2 响应增强（description/hard_counts/external_refs/confidence）
3. edge 审核状态机（4 态 6 转移，与 node 状态机独立）
4. 发布过滤（include_draft 参数 + 角色强制覆盖）
5. 质量巡检 API（6 规则：孤立/连通分量/低置信度/跨模块/无描述/rejected 堆积）
6. sync/backwrite 适配（knowledge.db ↔ PG edge review_status 双向同步）

#### 对抗性审查
GPT R1 独立抽检：
- 构造 parent 角色 + KNOWLEDGE_DRAFT_VISIBLE=False → 只返回 published 节点，0 条边 ✓
- 用临时 SQLite knowledge.db 跑 sync_knowledge_on_startup + edge set_review_status backwrite → happy path 打通 ✓

GPT R2 反证验证：
- F001: 删除 teacher_reviewed→published 转移 → test 失败 ✓
- F002: 去掉 edge review_status 读取/写入/回写 → 3 个 test 失败 ✓
- F003: 改 Q3 为 <=0.7 且不区分 ai_draft → 2 个 test 失败 ✓
- F004: 移除 include_draft 过滤和 parent 覆盖 → 4 个 test 失败 ✓

### 第三段：未测试风险（Non-tested Risks）
R1 标记的 4 处高风险点已全部被自动化测试覆盖。剩余低风险：并发 edge 审核冲突（设计层面已接受——SQLAlchemy ORM 级锁足够）。实现不像"只为过测试"而写。

### 发现清单

#### R1 Findings（已全部解决）

| ID | Severity | Category | Type | Status | 修复 |
|----|----------|----------|------|--------|------|
| F000 | LOW | design-concern | defect_fix | suggestion（不阻塞） | — |
| F001 | HIGH | test-gap | defect_fix | resolved-correct | 525255c |
| F002 | HIGH | test-gap | defect_fix | resolved-correct | 525255c |
| F003 | MED | test-gap | defect_fix | resolved-correct | 525255c |
| F004 | MED | test-gap | defect_fix | resolved-correct | 525255c |

**F001** | HIGH | test-gap | defect_fix
Before-behavior: edge 状态机测试只覆盖 3/6 转移，rejected→ai_draft 无最终状态断言。
After-behavior: 6 种合法转移 + nonexistent edge_id + 非法跳转全覆盖，每个有最终状态落库断言。
Evidence: test_edge_review.py
Status: resolved-correct (R2 verified)

**F002** | HIGH | test-gap | defect_fix
Before-behavior: Task 6 sync/backwrite 无自动化测试。
After-behavior: 5 个测试覆盖 read/write/old-schema/backwrite/no-column。
Evidence: test_sync_edge_review.py
Status: resolved-correct (R2 verified)

**F003** | MED | test-gap | defect_fix
Before-behavior: Q3 弱断言，阈值边界和已审核排除未验证。
After-behavior: confidence==0.7 不报/0.69 报 + teacher_reviewed 低置信度排除。
Evidence: test_quality_check.py
Status: resolved-correct (R2 verified)

**F004** | MED | test-gap | defect_fix
Before-behavior: 发布过滤只测 admin 显式传参。
After-behavior: NULL→ai_draft 过滤 + 空视图 + parent 角色强制覆盖。
Evidence: test_publish_filter.py
Status: resolved-correct (R2 verified)

#### R2 新发现

无。

### 测试统计
- R1: 110 知识树测试 → R2: 124 知识树测试 (+14)
- 全量: 1702 passed (3 pre-existing failures)
