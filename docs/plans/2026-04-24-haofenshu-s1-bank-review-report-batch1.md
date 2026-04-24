# S1-A Code Review Report (R1, Gate G1-S1A-8)

**Topic**: haofenshu-s1-bank
**Gate**: code_review_batch1 (S1-A 整体，非多 batch 切分)
**Round**: R1
**Status**: **PASS**
**Reviewer**: GPT-5.4 via MCP (mcp__codex__codex)
**Timestamp**: 2026-04-24T19:30+08:00
**threadId**: `019dbf3c-0fdf-70f2-a24a-b8abb80d5613`

## 变更理解

S1-A 是 haofenshu-phase2 parent design 的 L1 数据层子 topic，负责给 `bank_questions` 表扩展 5 个学情闭环缺失字段（`source` / `explanation` / `knowledge_point_ids` / `difficulty_level` / `grade_id`），并作为 S1-B/C/D linear chain 的首环 migration。本次 R1 审查范围是 commit `e237c6c..0cf939a` 共 7 commit：

| Commit | 类型 | 描述 |
|--------|------|------|
| `e237c6c` | docs(plan) | S1-A 基线漂移机械修正（alembic head 36e25241→a8c7d2e4 + baseline post-1716bfe） |
| `ca8b349` | feat(bank) | T1 扩展 BankQuestion 5 字段（nullable）+ 3 新测试（TDD） |
| `20a6961` | fix(alembic) | 前置 multi-base chain 修复（f7a3b2c1d456.down_revision None→'8b3f659c1a2a'） |
| `a3731d6` | feat(alembic) | T2 linear chain 首环 migration (down_revision=a8c7d2e4f135, batch_alter_table +5 列) |
| `f8ea392` | test(alembic) | T3 migration smoke (新文件 tests/test_alembic_s1a_bank.py, 6 tests) |
| `0cf939a` | docs(handoff) | T4 Gate G1-S1A 通过 + 交棒 S1-C (handoff.md 14 行) |

**意图**：(1) ORM 层 add 5 nullable 字段 → (2) migration 层 batch_alter_table add_column ×5 / drop_column ×5 LIFO → (3) smoke test 验证 up/down/up 幂等 + 字段类型锁定 + 数据保留 → (4) handoff 交棒 S1-C。前置 multi-base fix 是开工后发现的 pre-existing bug（用户批准 β 路径单独修），不属 S1-A 原 scope 但 smoke 验证依赖它。

**scope 边界**（ORC）：env.py / app.py 零改动；tags (JSON) 和 bloom_level (String(20)) 保持原样；migration 禁 postgresql.JSONB。

## 对抗性审查

GPT 作为独立审查者（非 Claude 助手），对本次 7 commit 从代码事实出发做四阶段对抗性审查：

**工具可达性**：GPT 经 MCP 调用完全读取 plan / handoff / CLAUDE.md / git log / git diff / 修改文件全文；并在独立 detached worktree 复现 multi-base fix 前后的 pytest 状态作对照。

**对抗性验证动作**：
1. **Multi-base fix 效果真伪验证** — GPT 独立 detached worktree 跑 `tests/test_alembic_migration.py`：
   - 修前 (`ca8b349`): 1 failed + 1 error + 1 passed，错误 `f7a3b2c1d456` ALTER 不存在的 users 表
   - 修后 (`20a6961`): 3 passed
   - 结论：排除"测试被意外 skip"假设，确认恢复来自 linear chain 归一。

2. **Task 3 smoke test 非假阳性验证** — GPT 对每个新测试追问"如果 migration 绑错链 / 改错旧列 / upgrade/downgrade body 写错，这些用例是否真会失败"：
   - `test_migration_file_exists_and_down_revision_is_conduct_head` (line 44): 精确字符串匹配 `'a8c7d2e4f135'`，down_revision 错会 FAIL
   - `test_migration_chain_head_is_single` (line 60): alembic heads 返回多行会 FAIL
   - `test_new_columns_added_and_nullable` (line 72): 缺列或非 nullable 会 FAIL
   - `test_existing_columns_unchanged_after_upgrade` (line 86): bloom_level.length ≠ 20 或 tags 类型改变会 FAIL
   - `test_existing_data_preserved_through_migration` (line 120): 数据丢失或必填列 INSERT 失败会 FAIL
   - `test_upgrade_then_downgrade_is_clean` (line 174): 回滚不完整会 FAIL

3. **ORC 独立核实** — 四条硬约束都经 `git diff` / `grep` / 文件直读独立复核（详见 §发现清单 下方表）。

4. **测试实跑** — GPT 独立执行 `pytest tests/test_alembic_s1a_bank.py tests/test_services_exam/test_bank_service.py tests/test_alembic_migration.py -q --tb=short` 得 **18 passed**，与本次改动范围完全一致。

## 发现清单

**未发现符合 L017 边界的 `defect_fix` / `test_gap` / `design_concern` finding。**

| Phase | 检查项 | 结果 |
|-------|--------|------|
| Phase 0 | Contract Pack (INV-S1A-001~005 / CE-S1A-001~003 / TD-S1A-001~003) | 全部落地或按约定 defer 到 S1-C/S1-D |
| Phase 1 | 测试充分性（Task 1 的 3 新 test + Task 3 的 6 smoke test） | 非假阳性——GPT 独立验证"错误实现会真实 FAIL" |
| Phase 2 | 行为正确性 + ORC 遵守 | ORC-S1A-001/002/003/004 全部满足 |
| Phase 3 | 未测试风险 | 无 deferred 到 S1-C/S1-D 以外的遗漏 |

### ORC 独立核实

| ORC | Rule | GPT 证据 | 状态 |
|-----|------|---------|------|
| ORC-S1A-001 | down_revision == 'a8c7d2e4f135' | `alembic/versions/a88094ee4ea6_s1a_bank_question_extension.py:16` 正确锚点 | ✅ |
| ORC-S1A-002 | alembic/env.py + api/app.py 零改动 | `git diff e237c6c~1..0cf939a -- alembic/env.py src/edu_cloud/api/app.py` 空输出 | ✅ |
| ORC-S1A-003 | tags/bloom_level 保持原样 | `src/edu_cloud/modules/bank/models.py:31,32` 未被改动 | ✅ |
| ORC-S1A-004 | sa.JSON() 禁 postgresql.JSONB | `a88094ee4ea6_s1a_bank_question_extension.py:31` 用 `sa.JSON()` | ✅ |

### Contract Pack 覆盖度

- **INV-S1A-001~005**: 均可在 Gate 命令或实现中对应（`plan.md:188`+）
- **CE-S1A-001~003**: mitigation 已由 Task 3 smoke test 覆盖
- **TD-S1A-001~003**: 明确 defer 到 S1-C/S1-D (`plan.md:230`+)，在 handoff `:11` 延续——审查员判定合理

### Multi-base fix (commit 20a6961) 独立验证

GPT 在 detached worktree 对照实验：
- **修前** (`ca8b349`): `tests/test_alembic_migration.py` → **1 failed + 1 error + 1 passed**。错误直接落在 `f7a3b2c1d456` 对不存在的 `users` 表执行 `ALTER`。
- **修后** (`20a6961`): `tests/test_alembic_migration.py` → **3 passed**。

**结论**：既有 2 个 alembic smoke 的恢复**来自 linear chain 修正**，不是 skip 或其他副作用。Plan L865 "failed < 22 为有益副作用" 条款适用，不阻塞 Gate。

### Test 实跑验证

GPT 独立执行:
```
pytest tests/test_alembic_s1a_bank.py tests/test_services_exam/test_bank_service.py tests/test_alembic_migration.py -q --tb=short
```
结果: **18 passed**（6 S1-A smoke + 9 bank_service + 3 既有 alembic smoke），与本次改动范围完全一致。

## Gate 判定

**PASS**（R1）— 无 HIGH/MED finding，ORC 全过，测试全绿，multi-base fix 独立复现验证。

## 最终结论

**最终结论: PASS**

---

**References:**
- Raw log: `docs/plans/.codex-raw-code-review-s1a-20260424_192905.log`
- Raw log SHA256: `1143bc9864918bb976d2214403cf77cebe676daf9cf311b93f3e8094deb7caff`
- Diff range hash: `3036cc623ba13f3f081d660ec56c948693b7a59d7653de5a749d78f67233b619`
- Plan: `docs/plans/2026-04-24-haofenshu-s1-bank-plan.md`
- Handoff: `docs/plans/2026-04-24-haofenshu-s1-bank-handoff.md`
- MCP threadId: `019dbf3c-0fdf-70f2-a24a-b8abb80d5613`
