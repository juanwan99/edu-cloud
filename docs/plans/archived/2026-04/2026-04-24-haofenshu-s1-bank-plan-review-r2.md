<!-- legacy-format -->
# S1-A haofenshu-s1-bank Plan Review R2（FAIL）

**Date**: 2026-04-24
**Reviewer**: GPT-5.4 (Codex CLI)
**Reviewed Plan**: [2026-04-24-haofenshu-s1-bank-plan.md](./2026-04-24-haofenshu-s1-bank-plan.md) (commit `d67b12a`)
**Previous Round**: R1 FAIL (commit `63090ee`, report `2026-04-24-haofenshu-s1-bank-plan-review.md`)
**Raw Log**: `.codex-plan-review-raw-s1a-r2-20260424_135759.log` (142KB)
**raw_output_hash**: `1e5d57613e0880033d0ffb41d59764c1d8a56f13813270b09bcb2407dcd5666b`
**subject_hash (plan R2)**: `5d551b5e5bc8ec3f8b730b7dc619befdc6afd998827a7c4bcd6027e37e4e5b73`

---

## 结论：R2 FAIL

5/6 R1 findings `resolved-correct`，1 contested（F-S1A-04），R2 新引入 2 MED。**0 HIGH**。

按 codex-review SKILL §Gate 条件：R3+ 禁止，R2 仍 FAIL → 必须**拆 topic 或 WONTFIX 或 manual_override**，不接受 R3 重审。

---

## R1 Findings 验证

| ID | 状态 | 说明 |
|----|------|------|
| F-S1A-01 | ✅ resolved-correct | `git rev-parse` 返回 d67b12a；Step 4.2 + Gate G1-S1A-4 真 Git 边界 |
| F-S1A-02 | ✅ resolved-correct | 经 bank_service.get_bank_question 真调用（非仅 import），但有连锁问题见 F-S1A-R2-01 |
| F-S1A-03 | ✅ resolved-correct | `bloom_length == 20` 精确断言，VARCHAR(10)/VARCHAR(255) 必 fail |
| F-S1A-04 | 🟡 contested | `claim→statement` 等大部分改好，但 invariants 仍用 `verification: pending_test` + `test_ref`，schema 真源规定 `test_ref` 仅限 `verification: existing_test` |
| F-S1A-05 | ✅ resolved-correct | plan + CLAUDE.md 统一为 `2064/22/1/23 @ 2026-04-24T11:04:27` |
| F-S1A-06 | ✅ resolved-correct | handoff 模板体实测 13 行，≤15 硬限达成 |

**GPT 独立核验摘要**：
- `alembic heads` 实测当前 = `a8c7d2e4f135 (head)`（非 `36e25241e55d`，存在未提交 conduct migration 文件 `alembic/versions/a8c7d2e4f135_conduct_add_updated_at_and_fk_indexes.py`，**并行 session 产物不在 d67b12a commit 内**，GPT 明确不作为 R2 问题计入）
- `git rev-parse --verify $(git log -1 --format=%H -- plan.md)^{commit}` → `d67b12a824c93ac4608f3c6cab83a5302567d1de` ✓
- `grep -n "statement:"` → 184/188/192/196/200 行 ✓（5 个 invariants 都用 statement）
- `grep -c "VARCHAR"` → 7 处（文案 + 类型家族二次守卫，不是 R1 宽松 substring 逃逸）
- handoff 模板体行数 = 13 ✓

---

## 新 Findings（R2 引入）

### F-S1A-R2-01（MED / test-gap）`bank_service.get_bank_question` 参数名错

**Before**: 现有 service 签名 `async def get_bank_question(db: AsyncSession, *, bank_question_id: str, school_id: str, ...)`（keyword-only）。

**After**: R2 plan Task 1 Step 1.1 新增入口级测试写 `await bank_service.get_bank_question(db, question_id=qid, school_id=school.id)` —— keyword 参数名 `question_id` 与 service 定义的 `bank_question_id` 不一致。

**Evidence**:
- plan.md:376（测试代码）
- `src/edu_cloud/modules/bank/service.py:12-16`（service 签名）
- 现有 `tests/test_services_exam/test_bank_service.py:69` 用 `bank_question_id=q.id`（正确用法）

**Impact**: 按 R2 plan 文本照抄，新入口级测试会在调用前抛 `TypeError: get_bank_question() got an unexpected keyword argument 'question_id'`。F-S1A-02 的"入口级验证"职责本意是走 service 层发现字段 serialize 问题，但现在连调用都进不去。

**Repair hypothesis**:
- 将调用改为 `bank_question_id=qid`
- 或改走 router/API 层入口（但会超 S1-A scope）

---

### F-S1A-R2-02（MED / test-gap）测试文件现有函数数口径失真

**Before**: `tests/test_services_exam/test_bank_service.py` 当前已有 **6 个** test 函数（实测 `grep -c "^(async )?def test_"` = 6）。

**After**: R2 plan 多处写 "现有 3 + 新增 3 = 6 PASS"（Task 1 测试契约 / Step 1.4 / Gate G1-S1A-1 表 / commit message）—— 把"现有"数当成了 3（R1 的旧数字），实际已是 6。正确应为"现有 6 + 新增 3 = 9"。

**Evidence**:
- plan.md:271 / :276 / :416 / :924（4 处口径失真）
- `tests/test_services_exam/test_bank_service.py` 文件头到尾 `def test_` 共 6 处

**Impact**: 执行者按 R2 plan 验证时会用 `-v` 看到 **9** 个 test（不是 6），Gate G1-S1A-1 判据"6 PASS"永远不满足；另一方面全量 baseline +9 的口径（F-S1A-02 修正时已加）仍然正确，说明 R2 两处算术口径内部打架。

**Repair hypothesis**:
- 统一改为"现有 6 + 新增 3 = 9 PASS"
- 或不写死整文件总数，判据改"断言 3 个新增测试名存在 + 全文件无回归"

---

## F-S1A-04 contested 详解

Schema 真源规定：
- `contract-pack-schema.md:19`: `verification` 枚举 `existing_test / pending_test / uncovered`
- `contract-pack-schema.md:20`: `test_ref` 字段"仅 existing_test"（在 invariants 表格中）

R2 plan L181-200 的 5 个 invariants 全部写：
```yaml
verification: pending_test
test_ref: tests/test_alembic_s1a_bank.py::...
```

这对 schema 来说是不合规组合（pending_test 不该有 test_ref）。

**修复方向**（供参考）：
- 移除 `test_ref` 字段，把预期 test 名字信息搬到 `statement` 尾部或备注
- 或增加非标 `planned_test_ref` 字段（schema 未定义，需另起）
- 或接受 `test_ref` 作为"未来位置占位"（违反 schema 字面）

---

## Gate 决策（硬限）

按 codex-review SKILL §Gate 条件：
- **R3+ 禁止**（gates_lib.write_receipt raise ValueError for round >= 3 且 status != 'blocked'）
- **R2 FAIL 处置**：拆 topic / WONTFIX / manual_override

**本 plan 状态**：
- 剩余 3 finding 全是 plan 文本机械错（参数名 / 数字口径 / schema 字段组合），不涉设计根因
- 修复 diff 预估 ≤30 行（plan 内 4-5 处字符替换 + test_ref 处置决策）
- 拆 topic 无意义（scope 已最小 = 单 deliverable 1.1）
- WONTFIX 不合理（这些是真问题，执行时会卡）
- **建议 manual_override（user-approved）**：修完 3 finding 直接 commit，gates.json 从 R2 FAIL → manual_override，7 天有效期内完成 S1-A 实施

---

## Raw Evidence

Full Codex output: `docs/plans/.codex-plan-review-raw-s1a-r2-20260424_135759.log`（142KB）
raw_output_hash: `1e5d57613e0880033d0ffb41d59764c1d8a56f13813270b09bcb2407dcd5666b`
