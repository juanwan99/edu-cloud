[edu-cloud] GPT Reviewer | 2026-04-18 13:14:00

<!-- anchor: finding-classification -->
## 审查报告: Batch 3.b.iii（Round 1）

- 结论: **FAIL**
- Reviewer: GPT Codex (gpt-5.4) via codex-cli aiproxy
- Subject: commits `121a6c9..ad7e957`（+2 race mutant test + R3 review-handoff）
- Raw output: `docs/plans/.codex-code-review-raw.log`（SHA256 `e5d288bf33e3ce99664523591fa4278f9cad801c57ebcb881c934d2746822072`）
- gates.json key: `code_review_batch3b_iii` / round=1 / status=fail
- 派发 handoff: `docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3biii.md`（@ `80b57fb`）
- R3 review handoff: `docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3biii.md`
- Worktree: `/home/ops/projects/edu-cloud-w2` / 分支 `feat/kg-batch3b`

## 变更理解

R3 修复 R2-F001 HIGH test-gap（fetchSeq guard 无异步竞态 mutant test 锁定），单 batch 2 commit:

- `121a6c9` test(frontend): ExamItemsTab.test.js +2 it（resolve race + reject race），deferred promise + setProps 入口
- `ad7e957` docs(plans): R3 审查交接单 batch3biii（Fix Card + 反证矩阵 1+2 实测粘贴 fail 输出 + 自查四要素）

基线: R2 156 → R3 knowledge-tree 子集 14 files / **158 tests PASS**（+2 race mutant）。
ExamItemsTab.vue 零改动（F001 code 已 R2 resolved-correct），反证后 git diff 零残留。

## 对抗性审查

GPT 独立验证:

1. **vitest 子集复跑**: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ExamItemsTab.test.js` → 7/7 PASS；`cd frontend && npx vitest run src/__tests__/knowledge-tree/` → 158/158 PASS ✓
2. **Test A resolve race 验证**: 删 try guard `if (mySeq !== fetchSeq) return` → Test A 红（A 覆盖 B：UI 含 stem-A/99）✓
3. **Test B reject race 验证**: 删 catch guard `if (mySeq !== fetchSeq) return` → Test B 红（A reject 清空：UI 显示"暂无"）✓
4. **finally guard mutant 验证（GPT 独立新增）**: 把 `if (mySeq === fetchSeq) loading.value = false` 改为无条件 `loading.value = false` → 新增 158 测仍全绿 ❌ **→ 触发 R3-F001**
5. **Contract Pack 交叉核对**: INV-002 引用 `test_exam_frequency_l1_set_equals_kb_l1` 未落盘；INV-004 引用 ModuleOverviewPanel `statsOverview=null` 降级断言未落盘 → **触发 P0-F001**（process，非 3.b.iii scope）

## 第一段: 测试充分性（Test Adequacy）

Test A/B 两路径（try/catch）达标。**finally guard 不达标**——缺一个"旧请求先 settle、新请求仍 pending"的确定性 deferred-promise race test，显式断言 `loading` 不被旧请求关闭。派发 handoff §Fix Intent Card 反证矩阵 #3 的 pre-declare 理由（"A 晚到 finally 把 loading 置 false 时 B 已完成"）仅覆盖 "A 晚到 == B 已完成" 单一场景；GPT mutant 指出另一条路径："A 先 settle / B 后 settle"，此时 finally guard 专属锁 loading。

## 第二段: 行为正确性

新增两个测试本身确定性。入口、时序控制、DOM 断言均符合派发 handoff 设计契约（deferred promise + setProps + DOM 断言）。无新代码行为缺陷。

## 第三段: 未测试风险

集中在 stale request 提前关闭 loading 的 lifecycle 分支。`finally` guard 是 ExamItemsTab.vue:63 `if (mySeq === fetchSeq) loading.value = false` —— 若删 guard 成无条件 `loading.value = false`，新增 158 测不触发 fail。

## Findings

### R3-F001

- ID: R3-F001
- Severity: **HIGH**
- Category: test-gap
- Type: defect_fix
- Red-flag: ✅ lifecycle / race condition → **requires independent fix design + Semantic Regression Gate**
- Before-behavior: 当前新增 2 race test 只锁 try/catch 两分支；若把 `if (mySeq === fetchSeq) loading.value = false`（L63 finally）改成无条件 `loading.value = false`，158 测仍全绿，旧请求先结束时可提前关闭最新请求的 loading
- After-behavior: 入口级 race test 锁 finally 分支 —— A→B 切换后，**A 先 settle 而 B 仍 pending** 时，UI 继续保持 loading=true 直到 B 完成
- Evidence:
  - `frontend/src/components/knowledge-tree/ExamItemsTab.vue:63`（finally guard 三处之一）
  - `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js:79`（Test A resolve race，覆盖 try guard）
  - `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js:104`（Test B reject race，覆盖 catch guard）
  - `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:2793`（T11 testable slice "仅最新请求生效"）
  - `docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3b-r2.md:70`（R2-F001 原话"锁住 items / total / loading 三类最新状态"）
  - `docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3biii.md:79`（pre-declare 反证 #3 deferred 理由）
- Impact: R2-F001 明确要求锁 items / total / **loading** 三类最新状态；本 R3 只补前两类，finally lifecycle guard 仍可被删而不触发失败。按 test-gap 规则 HIGH，阻塞 PASS
- Repair hypothesis:
  1. 补一个"旧请求先 settle、新请求仍 pending"的确定性 deferred-promise 入口测试，显式断言 `loading` 不被旧请求关闭
  2. Forbidden fix patterns：把 "B 已完成" 的场景当作 finally 代理 / 继续用同步 mock / 用 sleep 或定时器伪造竞态
  3. requires independent fix design + Semantic Regression Gate

### P0-F001

- ID: P0-F001
- Severity: **MED**
- Category: design-concern
- Type: defect_fix
- Red-flag: ❌ 非 red-flag（process finding / Contract Pack 映射准确性）
- Before-behavior: Contract Pack 把部分 invariant 标成"已有 verification"，但当前分支并没有落下对应测试或断言不完整
- After-behavior: Contract Pack 应只映射到当前已存在且确实覆盖该 invariant 的测试；未落盘或未覆盖完整的项应显式标 deferred / test_debt
- Evidence:
  - `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:4023`（INV-002 声称 `test_exam_frequency_l1_set_equals_kb_l1`）
  - `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:4036`（INV-004 声称 ModuleOverviewPanel `statsOverview=null` 降级断言）
  - `tests/test_knowledge_tree/test_stats_service.py:34`（当前只落 `test_exam_frequency_excludes_l0`）
  - `frontend/src/__tests__/knowledge-tree/ModuleOverviewPanel.test.js:23`（当前 4 基础用例，无 null 降级断言）
- Impact: Phase 0 "verification 映射是否准确"目前不能完全成立。后续 Gate 会误判不变量覆盖度。属 process finding，**非本 3.b.iii scope**（INV-002 测试 plan T14 Step 0 落盘 / INV-004 测试 plan T13 Step 4 落盘，均 Phase B 范围）
- Repair hypothesis:
  1. 把 Contract Pack 映射回当前真实已落盘测试，未实现覆盖明确改成 deferred / test_debt
  2. Forbidden fix patterns：继续引用"将来会有"的测试名充当当前 verification
  3. requires independent fix design + Semantic Regression Gate

## 结论

**FAIL**（1 HIGH + 1 MED）。

### R2 升级条件判定（gates_lib §Gate 条件）

| 条件 | 检查 | 结果 |
|------|------|------|
| Tier = T4 | 本 topic tier=T3 | ❌ |
| topic 标签含 remote / deploy / publish | `kg-phase1` / `batch3b_iii` 不含 | ❌ |
| 跨模块重构（≥2 文件 + ≥2 模块）| R3 修改 1 文件（`ExamItemsTab.test.js`），1 模块（`knowledge-tree`）| ❌ |

**R2 升级条件均不满足** → 按 codex-review skill §Gate 条件："R2 条件不满足 → 直接拆 topic"。

### 建议处置（由 Planner / 用户裁定）

1. **Option A**: 拆子 batch 3.b.iv，在 3.b.iv scope 内补一个 finally guard race mutant test（Test C："A 先 settle、B pending" 断言 `loading=true`），并实测粘贴反证 #3 fail 输出
2. **Option B**: R3-F001 标记 WONTFIX + test_debt TD-004（需要 Planner 明确 deadline 和 risk 签字）
3. **Option C**: 用户 L017 behavior_change 批准豁免 R2 升级（非 T4/remote/跨模块但特批 R2）→ 本会话 Executor 直接补 Test C → R2 重审

### P0-F001 处置

- P0-F001 属 process finding，INV-002/INV-004 对应测试在 **plan T13 Step 4 + T14 Step 0 范围**（Phase B）
- 建议：标记 deferred-to-phase-b，Phase B 实施时同步修 Contract Pack 映射
- **不阻塞 3.b.iii** 的 PASS/FAIL 裁决（只是 FAIL 的原因全部来自 R3-F001 HIGH）

---

status: submitted-r1-fail
