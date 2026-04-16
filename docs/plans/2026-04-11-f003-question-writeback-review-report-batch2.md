[edu-cloud] GPT Reviewer | 2026-04-12 14:35:07
## 审查报告: Task 5-8 (Batch 2) — Round 1
结论: FAIL

GPT 原始输出: `docs/plans/.codex-code-review-batch2-raw.log`
GPT 原始输出 SHA256: `b69a09fff4992d27648edb58038b193d69497eb9031910f73d01d52c84f2288e`
GPT token 消耗: 132,460

### 第一段：测试充分性（Test Adequacy）

- S6/S6b（publish_card_atomic success + rollback）有效——删除 begin_nested 包裹后 S6 的 Question 残留断言失败
- S7a/S7b（SAVEPOINT 语义 + existing fast path）有效——删除核心逻辑后断言失败
- integration test（T8 router 接入）有效——200 + PDF 字节匹配
- **publish_card_atomic 失败路径无测试**：exam 不存在 / subject 不属于 exam / status=completed / HTML 为空等 fail-fast 分支仅有 grep 验证，无可失败测试
- **UniqueConstraint 回归无测试**：T5 加 `uq_question_subject_name` 后，`/api/v1/questions` 的 POST duplicate / PATCH rename 冲突无测试覆盖

### 第二段：行为正确性（Behavioral Correctness）

**变更理解（GPT 描述）：** Batch 2 分 4 个 Task：T5 加 Question 唯一约束（Alembic migration + models.py）；T6 实现 publish_card_atomic（PDF+skeleton 事务外，Question+Template+status 事务内 begin_nested 包裹）；T7 为 upsert_questions INSERT 路径加 SAVEPOINT retry 防御；T8 删除 router.py 80 行内联实现替换为 publish_card_atomic 调用。

**Executor 自审抽检：**
- 抽检 1: handoff 第 26 行"publish_card_atomic 事务边界：PDF/skeleton 事务外，DB 写事务内 begin_nested"→ 读 publish_service.py 确认 → 属实
- 抽检 2: handoff 第 16 行"UniqueConstraint 在 in-memory SQLite 下也生效"→ SQLite 确实支持唯一约束 → 属实
- 抽检 3: handoff 第 31 行"S7c 延期 test_debt（不写伪实现，R4-F003 遵守）"→ 确认无 S7c 伪实现 → 属实

**对抗性审查：**
- GPT 独立构造 ASGI 请求复现 F001：第二次 `POST /api/v1/questions`（同 subject_id + 同 name）→ 500 Internal Server Error；`PATCH /api/v1/questions/{id}`（rename 到已存在 name）→ 500。确认 UniqueConstraint 加入后 router.py 缺少 IntegrityError 处理
- GPT 确认 publish_card_atomic 的 fail-fast 分支（status check / exam 校验）只有 grep 验证，删掉这些分支后现有测试仍绿

### 第三段：未测试风险（Non-tested Risks）

- 真实并发命中 SAVEPOINT retry 分支仅靠 test_debt（S7c PostgreSQL CI），已登记且 deadline 2026-06-30，可接受
- publish_card_atomic 的 `begin_nested()` 外层包裹是 🔀 偏差（plan 未指定），SQLite 下必要但 PostgreSQL 行为需验证

### 发现清单

#### F001
| 字段 | 值 |
|------|-----|
| ID | F001 |
| Severity | HIGH |
| Category | code-bug |
| Type | defect_fix |
| Before-behavior | T5 加 `uq_question_subject_name` 后，`/api/v1/questions` 的 POST duplicate 和 PATCH rename 冒泡 IntegrityError → 500 |
| After-behavior | 捕获 IntegrityError → 返回 409 Conflict + 明确错误信息 |
| Inv-conflict | none |
| Evidence | models.py:52, router.py:163, router.py:219; GPT ASGI 复现 500 |
| Impact | schema 变更引入的跨入口回归，用户操作直接触发 500 |
| Repair hypothesis | create_question/update_question 加 IntegrityError catch → 409，补回归测试 |
| Status | verified |

#### F002
| 字段 | 值 |
|------|-----|
| ID | F002 |
| Severity | HIGH |
| Category | test-gap |
| Type | defect_fix |
| Before-behavior | test_question.py 10 tests 全为正常路径，无 duplicate/rename 冲突测试 |
| After-behavior | 补 POST duplicate + PATCH rename conflict 用例，断言非 500 |
| Inv-conflict | none |
| Evidence | test_question.py:50, :87 |
| Impact | 无法捕获 F001 |
| Status | verified |

#### F003
| 字段 | 值 |
|------|-----|
| ID | F003 |
| Severity | HIGH |
| Category | test-gap |
| Type | defect_fix |
| Before-behavior | publish_card_atomic 的 fail-fast 分支（status/exam/subject/HTML 校验）仅 grep 验证，删掉分支后测试仍绿 |
| After-behavior | 补 fail-fast 边界测试，断言 400/404 + 无副作用 |
| Inv-conflict | none |
| Evidence | publish_service.py:216, plan:1781 |
| Impact | fail-fast 分支可被删除而不被发现 |
| Status | verified |

#### P001
| 字段 | 值 |
|------|-----|
| ID | P001 |
| Severity | MED |
| Category | design-concern |
| Type | defect_fix |
| Before-behavior | handoff 把 INV-008 失败路径映射到 S6b success path |
| After-behavior | 修正映射 |
| Evidence | handoff:16,18; plan:406,1525 |
| Impact | 验证映射误导审计 |
| Status | verified |
| Planner 处置 | **design-concern — 不阻塞**。随 F003 失败路径测试一起修正 |

### Planner 处置

**F001+F002（HIGH code-bug + test-gap）：** T5 UniqueConstraint 引入的跨入口回归。修复涉及 `modules/exam/router.py` + `tests/test_api_exam/test_question.py`，不在 batch2 plan 声明的 T5-T8 文件范围内。按 review-templates.md Important Finding 追踪规则，**追加为 plan 新 Task**。scope_guard 需要用户授权扩展。

**F003（HIGH test-gap）：** 修复在 plan 范围内（`tests/test_services_exam/test_publish_service.py`），Executor 直接修复。

**P001（MED design-concern）：** 不阻塞。映射修正随 F003 一起处理。

**Round 2 scope：** F001+F002（需 scope 扩展）+ F003（plan 内），全部为 defect_fix。
