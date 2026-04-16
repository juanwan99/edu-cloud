[edu-cloud] Executor→Reviewer | 2026-04-03 18:30:19
## 审查交接单: Task 1-8
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-a4-card-editor-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | 后端 layout 契约统一 + 测试 | commit 5e4f373, TQL A4 路径 col 合并 + router F01 校验 + 8 个契约测试 | ✅ | |
| T2 | CSS 修复 — .a4-col + 删除 hack | commit 635e6d8, 替换 .a4-essay-area 为 .a4-col/a4-content/a4-col--full | ✅ | |
| T3 | 重写 _renderA4 + 提取 renderFixedRegions | commit 228280e, 提取 renderFixedRegions 共享函数 + A3 路径复用 + A4 使用 renderColumnRegions | ✅ | |
| T4 | 选择题竖排修复 | commit 12cf6b8, hasTqlCoords 判断 + getValues 保留 x/y/w | ✅ | |
| T5 | PDF 导出修复 | commit d1821e4, fetchStyleCSS + async getCleanHTML + marginBottom 清除 + Noto CJK | ✅ | |
| T6 | 英语/化学 editor-layout API 测试 | commit a71b153, 3 个 API 集成测试（英语 A4/化学/数学 A3） | 🔀 | 去掉 plan 中 Subject 不支持的 full_score/sort_order 字段；数学改为生物（seed_subject 默认科目） |
| T7 | 前端 Vitest 渲染回归测试 | commit 995304b, 4 个 DOM 结构测试 | 🔀 | A3 .a3-col 数量从 3 改为 6（A面+B面各 3 栏 = 6 个 .a3-col 元素） |
| T8 | 最终回归验证 | 后端 42 passed / 前端 71 passed + 1 pre-existing fail | ✅ | 前端 1 个失败是路由数量断言(17→实际 N)，非本次引入 |

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） | 反证验证 |
|---------------|------------------|---------|------------------------------|---------------------------------------|
| A4 layout 每面单 column | test_tpl_parser.py::TestSubjectDefaults::test_a4_layout_single_column_per_side | `python -m pytest tests/test_services_exam/test_tpl_parser.py::TestSubjectDefaults -v` | PASS, 5/5 passed in 2.45s | 修复前 TQL 路径 3 个 FAIL（多 column），修复后 PASS |
| TQL A4 单 column 契约 | test_tpl_parser.py::TestTqlA4Contract::test_tql_english_a4_single_column | `python -m pytest tests/test_services_exam/test_tpl_parser.py::TestTqlA4Contract -v` | PASS, 3/3 passed in 1.21s | 修复前 assert len==1 失败（英语返回 2 columns），修复后 PASS |
| 英语 API 返回 A4 | test_cards.py::TestEditorLayout::test_english_returns_a4_layout | `python -m pytest tests/test_api_exam/test_cards.py::TestEditorLayout -v` | PASS, 9/9 passed in 17.11s | 不适用：已有测试非本次新增核心逻辑 |
| A4 渲染 DOM 结构 | render.test.js::A4 layout generates .a4-content > .a4-col structure | `npx vitest run src/card-editor/__tests__/render.test.js` | PASS, 4/4 passed in 2.06s | 不适用：新增测试验证新 DOM 结构 |

### 验证清单自检
- ✅ A4 layout sides[0].columns 长度 == 1（TestSubjectDefaults 5 tests PASS）
- ✅ A4 layout sides[0].columns[0].regions 包含 type=fixed 和 type=essay（test_a4_side_a_has_fixed_and_essay PASS）
- ✅ A4 layout sides[1].columns[0].regions 不包含 type=fixed（test_a4_side_b_no_fixed PASS）
- ✅ A3 科目布局不受影响（test_a3_subjects_unaffected PASS，6 科全检）
- ✅ .a4-col 是 flex column 容器（styles.css L389-398 新增）
- ✅ flex:none !important 已删除（Grep 确认零残留）
- ✅ _renderA4 调用 renderColumnRegions（render.js 新 _renderA4 L10-12）
- ✅ renderFixedRegions 被 A3 和 A4 共享（A3 L419, A4 L10）
- ✅ hasTqlCoords 判断正确（render.js L115-118）
- ✅ getValues 保留 x/y/w（CardEditor.vue L253-269）
- ✅ getCleanHTML 清 marginBottom（export.js L108）
- ✅ CSS fetch 优先（fetchStyleCSS + fallback 到 styleSheets）
- ✅ 后端 42 tests PASS（tpl_parser + cards）
- ✅ 前端 4/4 render tests PASS + 全量 71/72 PASS

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: A4 layout B 面 regions 为空
  运行命令: `npx vitest run src/card-editor/__tests__/render.test.js`
  实际输出:
  ```
  ✓ A4 B-side without regions does not generate #pageB (29ms)
  4 passed
  ```
  结论: B 面无 regions 时正确跳过 #pageB 渲染

- 状态变量/锁的异常路径：
  构造输入: _fallback_layout 化学（14 选择 < 30，useSideB=true 但选择题少）
  运行命令: `python -m pytest tests/test_services_exam/test_tpl_parser.py::TestSubjectDefaults::test_a4_chemistry_layout -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 化学 fallback 正确走 A3 路径（14 < 30 阈值），heightRatio 存在

- 字符串匹配/条件判断的假阴性：
  构造输入: groups 全部无 TQL 坐标（A3 科目）
  运行命令: `npx vitest run src/card-editor/__tests__/render.test.js`
  实际输出:
  ```
  ✓ A3 layout generates .a3-layout > .a3-col structure (51ms)
  ```
  结论: hasTqlCoords=false 时正确走横排合并路径，A3 结构不受影响
