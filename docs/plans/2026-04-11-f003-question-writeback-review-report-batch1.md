[edu-cloud] GPT Reviewer | 2026-04-12 11:38:14
<!-- anchor: finding-classification -->
## 审查报告: Task 0-4 (Batch 1)
结论: FAIL

GPT 原始输出: `docs/plans/.codex-code-review-batch1-raw.log`
GPT 原始输出 SHA256: `2190464c466790c3f7af22036f4aece0f33bbb2476bcbbeb40ad8c02aa5a829f`
GPT token 消耗: 108,309

### 第一段：测试充分性（Test Adequacy）

- render.js 的 2 个 vitest 新增测试有效（data-side="A"/"B" 断言精确）
- extract_skeleton 的 Playwright integration test 有效（B 面 side='B' 穿透验证）
- **publish_service S5/S5b 测试不充分**：只断言 Template 存在性（`.side == "A"` / `tpl_b is None`），不校验模板内 `regions` 内容。GPT 确认"删掉分面核心逻辑后这两组测试仍可通过"
- **INV-001 映射失真**：Contract Pack 把 INV-001（空 skeleton 返回空字典）映射到 test_S2，但 test_S2 实际只覆盖 15 题 happy path，无任何空输入断言。Executor 自审声称"S2 内已覆盖空 skeleton"与事实不符

### 第二段：行为正确性（Behavioral Correctness）

**变更理解（GPT 描述）：** Batch 1 分 5 个 Task 推进"Question 写入责任链重设"的前置层。T0 验证 StudentAnswer 唯一约束存在（grep 确认，无代码变更）。T1 在 render.js 的 4 处 `.page` 元素追加 `data-side="A"/"B"` 属性，让前端 DOM 携带面标识供 `extract_skeleton` 穿透。T2 用 Playwright integration 测试验证 B 面 `side='B'` 能正确穿透到 skeleton region。T3 新建 `publish_service.py` 实现 `upsert_questions_from_skeleton`（从 skeleton 创建/更新 Question 记录，含 objective_groups 展开 + slots.sub_regions 展开 + 幂等 + 孤儿保留）。T4 追加 `upsert_template_both_sides`（按 side 分面构建双面 Template 并持久化）。

**Executor 自审抽检：**
- 抽检 1: handoff 第 37-40 行声称"S2 内已覆盖空 skeleton"→ 读 test_S2（test_publish_service.py:35-70），实际只测 15 题 happy path，**不实** → 直接影响判定
- 抽检 2: handoff 第 17 行 S1 反证"删除 render.js data-side='B' 后 test 报 `expected 'B', received null`"→ 逻辑合理，vitest 断言精确到属性值
- 抽检 3: handoff 第 22 行 S5 反证"删除 B 面分支后 tpl_b=None，断言失败"→ 读 test_S5（test_publish_service.py:173-174），`assert tpl_b is not None` 确实会失败，但这只证明 tpl_b 存在性，不证明 tpl_b 的 regions 内容正确

**对抗性审查：**
- 边界输入构造：GPT 独立构造双面 skeleton（essay-13 side='A' + essay-14 side='B'）调用 `upsert_template_both_sides` → 得到 `A ['essay-13', 'essay-14']`、`B ['essay-13', 'essay-14']`，两面都包含全部 region（应分别只含对应面的 region）
- 异常路径追踪：根因在 publish_service.py:129-131 把未过滤的 `skeleton.get("slots", [])` 整体传给 `skeleton_to_paperseg_json`，该函数内部用 slots.sub_regions 构建 regions，覆盖了 side_skeleton.regions 的过滤效果
- 假阴性检测：S5/S5b 测试断言只检查 Template 存在性，不检查 regions 内容，无法捕获上述分面错误 → F001 被 F002 的弱断言放过

其他确认：
- T1 render.js 的 data-side 属性添加正确（4 处 grep 确认）
- T2 extract_skeleton integration 穿透验证正确
- T3 upsert_questions_from_skeleton 的 15 题创建和幂等/孤儿保留逻辑正确

### 第三段：未测试风险（Non-tested Risks）

- **上游契约错位**：真实 `extract_skeleton()` 只产出 `regions`，不产出 `slots`（slots 来自编辑器 model 层），而当前 publish_service 的主观题模板路径仍依赖 slots.sub_regions。这意味着 batch2 T6 `publish_card_atomic` 整合时，slots 字段可能为空或不一致
- **跨批次风险**：F001 的修复方向直接影响 T6 和 T11 的 skeleton→Template 数据流设计

### 发现清单

#### F001
| 字段 | 值 |
|------|-----|
| ID | F001 |
| Severity | HIGH |
| Category | code-bug |
| Type | defect_fix |
| Before-behavior | `upsert_template_both_sides()` 虽按 side 过滤 regions，但把全量 slots 传给导出层，A/B 两面都写入全部主观题 region |
| After-behavior | 每个 Template 只应包含对应面的 regions；A-only 输入应保留 A 面 region |
| Inv-conflict | possible（与 Contract Pack CE-004 "按 side 构建双面 Template" 的语义不一致） |
| Evidence | publish_service.py:121, :125, :129-131; GPT 独立复现 `A ['essay-13','essay-14']` `B ['essay-13','essay-14']` |
| Impact | 后续批次接入真实 publish 链路时，扫描端按 side 取模板会切错题区 |
| Repair hypothesis | 修复方向应统一"按 side 过滤后的题区来源"，让模板内容和 question_map 从同一份分面后语义模型导出。禁止只在测试里放宽断言或在导出后事后裁剪 tpl.regions。requires independent fix design + Semantic Regression Gate |
| Status | verified |

#### F002
| 字段 | 值 |
|------|-----|
| ID | F002 |
| Severity | HIGH |
| Category | test-gap |
| Type | defect_fix |
| Before-behavior | S5/S5b 只断言 Template 存在性（side + count），不校验模板 regions 内容；删掉分面核心逻辑后测试仍通过 |
| After-behavior | 测试应在 A/B 两面分别断言 region 集合和 question_id 绑定，确保错误实现必然失败 |
| Inv-conflict | none |
| Evidence | test_publish_service.py:173-181, :206-209; GPT 确认"删掉分面核心逻辑也未必失败" |
| Impact | 直接放过 F001，Contract Pack CE-004 的 mitigation 实际无效 |
| Repair hypothesis | 把断言提升到模板内容级。禁止 `assert tpl_a is not None` / `assert len(...) == n` 等弱断言替代分面语义验证 |
| Status | verified |

#### F003
| 字段 | 值 |
|------|-----|
| ID | F003 |
| Severity | MED |
| Category | test-gap |
| Type | defect_fix |
| Before-behavior | Contract Pack INV-001 映射到 test_S2，handoff 自检声称"S2 内已覆盖空 skeleton"；test_S2 实际只覆盖 15 题 happy path，无空输入断言 |
| After-behavior | INV-001 应有独立空输入测试，test_ref/handoff 映射与实际一致 |
| Inv-conflict | none |
| Evidence | plan.md:368-371（INV-001 test_ref → test_S2）; test_publish_service.py:35-70（test_S2 无空输入断言）; review-handoff-batch1.md:37-40（自审声称不实） |
| Impact | verification 映射不准确 + Executor 自审失真 |
| Repair hypothesis | 拆出独立空输入测试，修正 Contract Pack test_ref 映射和 handoff 自审描述 |
| Status | verified |

### Planner 处置

全部 3 个 finding 均为 defect_fix，无 behavior_change，无需行为变更审批。

Round 1 FAIL → Executor 修复 F001 + F002 + F003 后提交 Round 2 审查交接单。
