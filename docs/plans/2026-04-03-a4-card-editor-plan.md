# A4 双面答题卡编辑器重构 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 按 GPT Codex 诊断的 5 个根因重构 A4 双面答题卡编辑器，统一 A3/A4 渲染架构。

**Architecture:** A3/A4 共用 `renderColumnRegions()` + `renderEssayRegion()`，只在页面骨架层区分纸型。A4 引入 `.a4-col` flex 容器（类似 `.a3-col`），让 `heightRatio` 正确分配空间。后端 layout 契约统一为 A4 每面 1 column。

**Tech Stack:** 原生 JS（card-editor/）、CSS、Python（FastAPI 后端）、pytest

**Design:** `docs/plans/2026-04-03-a4-card-editor-design.md`

**回归验证命令（每个 Task 完成后必跑）：**
```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_tpl_parser.py tests/test_api_exam/test_cards.py -x -q
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run
```

---

### Task 1: 后端 layout 契约统一 + 测试

**Files:**
- Modify: `src/edu_cloud/modules/card/subject_defaults.py:428-470` (tql_to_editor_layout A4 路径)
- Modify: `src/edu_cloud/modules/card/router.py:79-104` (A4 结构校验)
- Test: `tests/test_services_exam/test_tpl_parser.py`

**测试契约:**
1. A4 layout 每面只有 1 个 column（col:0），A 面含 fixed + essay，B 面无 fixed
   - 入口: `tql_to_editor_layout(tpl_path)` 返回的 layout dict
   - 反例: 错误实现会生成多 column（col:0 只有 fixed，col:1 有 essay），前端渲染时 A4 col 1+ 被忽略导致 essay 丢失
   - 边界: 无 B 面内容时 B 面 column 应存在但 regions 为空
   - 回归: 防止 A4 layout 多 column 导致前端渲染丢题
   - 命令: `python -m pytest tests/test_services_exam/test_tpl_parser.py::TestSubjectDefaults -v`

**审查清单:**
- ✓ A4 layout sides[0].columns 长度 == 1
- ✓ A4 layout sides[0].columns[0].regions 包含 type=fixed 和 type=essay
- ✓ A4 layout sides[1].columns[0].regions 不包含 type=fixed
- ✗ A4 layout sides[0].columns 长度 > 1（旧的多 column 结构）
- 关键行为: A3 科目的 layout 不受任何影响

**边界条件:**
- 无 B 面内容（useSideB=false 的科目如物理）→ B 面 columns[0].regions 为空列表
- 只有 1 个 essay（极端 A4 科目）→ A 面 col 0 有 fixed + 1 个 essay
- 跨面续写（英语 66 题跨 A/B 面）→ A 面和 B 面各有对应 region

- [ ] **Step 1: 写 A4 layout 契约测试**

在 `tests/test_services_exam/test_tpl_parser.py` 末尾新增 `TestSubjectDefaults` 类：

```python
class TestSubjectDefaults:
    """A4 layout 契约测试。"""

    def test_a4_layout_single_column_per_side(self):
        """A4 布局每面只有 1 个 column。"""
        from edu_cloud.modules.card.subject_defaults import _fallback_layout, SUBJECT_CONFIGS
        config = dict(SUBJECT_CONFIGS["英语"])
        config["subjectTitle"] = "英语"
        layout = _fallback_layout(config)
        assert layout["paper"] == "A4"
        for side in layout["sides"]:
            assert len(side["columns"]) == 1, f"Side {side['side']} should have 1 column"
            assert side["columns"][0]["col"] == 0

    def test_a4_side_a_has_fixed_and_essay(self):
        """A4 A面 col 0 同时包含 fixed 和 essay regions。"""
        from edu_cloud.modules.card.subject_defaults import _fallback_layout, SUBJECT_CONFIGS
        config = dict(SUBJECT_CONFIGS["英语"])
        config["subjectTitle"] = "英语"
        layout = _fallback_layout(config)
        side_a = layout["sides"][0]
        regions = side_a["columns"][0]["regions"]
        types = [r["type"] for r in regions]
        assert "fixed" in types, "A面 col 0 应包含 fixed regions"
        assert "essay" in types, "A面 col 0 应包含 essay regions"

    def test_a4_side_b_no_fixed(self):
        """A4 B面不包含 fixed regions。"""
        from edu_cloud.modules.card.subject_defaults import _fallback_layout, SUBJECT_CONFIGS
        config = dict(SUBJECT_CONFIGS["英语"])
        config["subjectTitle"] = "英语"
        layout = _fallback_layout(config)
        side_b = layout["sides"][1]
        regions = side_b["columns"][0]["regions"]
        types = [r["type"] for r in regions]
        assert "fixed" not in types, "B面不应包含 fixed regions"

    def test_a4_chemistry_layout(self):
        """化学也是 A4 双面（14 选择 + 4 解答跨面）。"""
        from edu_cloud.modules.card.subject_defaults import _fallback_layout, SUBJECT_CONFIGS
        config = dict(SUBJECT_CONFIGS["化学"])
        config["subjectTitle"] = "化学"
        layout = _fallback_layout(config)
        # 化学: 14 选择 + 有 B 面 essays → 但 14 选择 < 30，fallback 判断不是 A4
        # 检查实际生成的纸型和结构一致性
        paper = layout["paper"]
        for side in layout["sides"]:
            for col in side["columns"]:
                for r in col["regions"]:
                    if r.get("type") == "essay":
                        assert "heightRatio" in r

    def test_a3_subjects_unaffected(self):
        """A3 科目布局不受影响：3 栏结构。"""
        from edu_cloud.modules.card.subject_defaults import _fallback_layout, SUBJECT_CONFIGS
        for name in ["数学", "物理", "生物", "历史", "政治", "地理"]:
            config = dict(SUBJECT_CONFIGS[name])
            config["subjectTitle"] = name
            layout = _fallback_layout(config)
            assert layout["paper"] == "A3", f"{name} should be A3"
            # A3 A面至少 2 栏（col 0 fixed + col 1+ essay）
            assert len(layout["sides"][0]["columns"]) >= 2, f"{name} A面 should have ≥2 columns"


@skip_no_tpl
class TestTqlA4Contract:
    """TQL 转换路径的 A4 契约测试（需要真实 .tpl 文件）。[F02 修复]"""

    def test_tql_english_a4_single_column(self):
        """TQL 英语模板转换后也满足 A4 单 column 契约。"""
        from edu_cloud.modules.card.subject_defaults import get_default_layout
        layout = get_default_layout("英语")
        assert layout["paper"] == "A4"
        for side in layout["sides"]:
            assert len(side["columns"]) == 1, f"Side {side['side']} should have 1 column"

    def test_tql_english_a_side_has_fixed_and_essay(self):
        """TQL 英语 A 面 col 0 同时含 fixed + essay。"""
        from edu_cloud.modules.card.subject_defaults import get_default_layout
        layout = get_default_layout("英语")
        regions = layout["sides"][0]["columns"][0]["regions"]
        types = [r["type"] for r in regions]
        assert "fixed" in types
        assert "essay" in types

    def test_tql_chemistry_a4_contract(self):
        """TQL 化学模板转换后满足 A4 契约。"""
        from edu_cloud.modules.card.subject_defaults import get_default_layout
        layout = get_default_layout("化学")
        if layout["paper"] == "A4":
            for side in layout["sides"]:
                assert len(side["columns"]) == 1
```

- [ ] **Step 2: 运行测试确认 A3 测试通过、A4 测试状态**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_tpl_parser.py::TestSubjectDefaults -v
```

预期: A3 测试通过，A4 测试可能需要调整（取决于 `_fallback_layout` 当前 A4 判断逻辑）。

- [ ] **Step 3: 修复 tql_to_editor_layout A4 路径 — col 合并**

在 `subject_defaults.py` 的 `tql_to_editor_layout()` 函数中，A4 路径组装 sides 时，将 col 1+ 的 essay regions 合并到 col 0：

当前代码（L429-436）：
```python
a_columns = [{"col": 0, "regions": col0_regions}]
for i, cid in enumerate(col_ids):
    a_columns.append({
        "col": i + 1,
        "regions": _make_regions(col_slots_a.get(cid, []), "A", i + 1, 0),
    })
```

修改为（仅 A4 路径）：
```python
if is_a4_dual:
    # A4: 所有 essay 合并到 col 0（与 fixed 同栏）
    all_a_essays = []
    for cid in col_ids:
        all_a_essays.extend(_make_regions(col_slots_a.get(cid, []), "A", 0, 0))
    a_columns = [{"col": 0, "regions": col0_regions + all_a_essays}]
else:
    a_columns = [{"col": 0, "regions": col0_regions}]
    for i, cid in enumerate(col_ids):
        a_columns.append({
            "col": i + 1,
            "regions": _make_regions(col_slots_a.get(cid, []), "A", i + 1, 0),
        })
```

B 面同理（L438-444）：
```python
if is_a4_dual:
    all_b_essays = []
    for cid in col_ids:
        all_b_essays.extend(_make_regions(col_slots_b.get(cid, []), "B", 0, 1))
    b_columns = [{"col": 0, "regions": all_b_essays}]
else:
    has_b = any(len(v) > 0 for v in col_slots_b.values())
    b_columns = []
    for i, cid in enumerate(col_ids):
        b_columns.append({
            "col": i,
            "regions": _make_regions(col_slots_b.get(cid, []), "B", i, 1) if has_b else [],
        })
```

- [ ] **Step 4: 加固 router.py A4 结构校验 [F01 修复]**

在 `router.py` 的 `get_editor_layout()` 中，扩展 `structure_mismatch` 检查。当前 L83 只检查 `default=A4 && saved!=A4`，新增：A4 saved layout 如果任一 side 有 >1 column，也视为 structure_mismatch：

```python
    # 扩展 A4 结构校验：A4 每面应只有 1 column
    if not structure_mismatch and saved_paper == "A4":
        saved_sides = layout.get("sides", [])
        for side in saved_sides:
            if len(side.get("columns", [])) > 1:
                structure_mismatch = True
                break
```

- [ ] **Step 5: 运行所有 tpl_parser + cards 测试**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_tpl_parser.py tests/test_api_exam/test_cards.py -x -q
```

预期: 全部 PASS（含新增的 A4 契约测试 + 旧的 A3 测试）。

- [ ] **Step 6: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/modules/card/subject_defaults.py src/edu_cloud/modules/card/router.py tests/test_services_exam/test_tpl_parser.py
git commit -m "feat: 统一 A4 layout 契约 — 每面单 column + 结构校验 + 契约测试"
```

---

### Task 2: CSS 修复 — 新增 .a4-col + 删除 flex:none hack

**Files:**
- Modify: `frontend/public/card-editor/styles.css:389-399`

**审查清单:**
- ✓ `.a4-col` 是 flex column 容器，`flex:1` 占剩余空间
- ✓ `.col-warning-bottom` 在 `.a4-col` 内通过 `margin-top:auto` 贴底
- ✗ `flex: none !important` 仍然存在
- 关键行为: A3 的 `.a3-col` 样式完全不动

- [ ] **Step 1: 修改 styles.css**

删除 L396-399（`flex: none !important` hack）：
```css
/* A4 页面内 essay-item 不用 flex 拉伸，用固定高度占比 */
.page[data-paper="A4"] .essay-item {
  flex: none !important;
}
```

将 `.a4-essay-area`（L389-395）替换为 `.a4-col`：
```css
/* A4 单栏 flex 容器（类似 a3-col，无 OMR 角标） */
.a4-col {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  border: 1px solid #000;
  border-top: none;
  overflow: hidden;
}
```

新增 `.a4-content` 容器样式和 B 面全高变体 [F05 修复]：
```css
/* A4 页面内容容器（flex column，铺满 page） */
.a4-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}
/* B 面全高变体：不需要 flex:1（没有固定区占位），直接铺满 */
.a4-col--full {
  flex: none;
  height: 100%;
}
```

- [ ] **Step 2: 确认 A3 样式不受影响**

验证：`.a3-col` 和 `.a3-layout` 的 CSS 规则完全不动。用 Grep 确认没有误改。

```bash
cd C:/Users/Administrator/edu-cloud && grep -n "a3-col\|a3-layout" frontend/public/card-editor/styles.css
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend/public/card-editor/styles.css
git commit -m "fix: A4 CSS — 新增 a4-col flex 容器，删除 flex:none hack"
```

---

### Task 3: 重写 _renderA4 + 提取 renderFixedRegions

**Files:**
- Modify: `frontend/src/card-editor/render.js:319-503` (renderA3Col 后到 _renderA4 结束)

**测试契约:**
1. A4 渲染使用 renderColumnRegions 复用 A3 的 essay 渲染逻辑
   - 入口: `renderFromLayout(previewWrap, a4Layout, config)` 在浏览器中调用
   - 反例: 错误实现会在 A4 中直接拼 HTML 绕过 renderColumnRegions，导致分割线拖拽/heightRatio 失效
   - 边界: B 面无 essay 时只渲染空 col-warning
   - 回归: 防止 A4 essay 区域丢失 flex 高度分配
   - 命令: 手动浏览器验证（前端无 pytest）

**审查清单:**
- ✓ `_renderA4` 调用 `renderColumnRegions()` 而非自己拼 essay HTML
- ✓ 固定区 HTML 通过 `renderFixedRegions()` 共享（A3 也调用）
- ✓ A4 B 面使用 `.a4-col` 容器
- ✗ 固定区 HTML 在 A3 和 A4 中有两份复制
- 关键行为: A3 渲染输出不变（仅将固定区 HTML 提取为函数，输出完全相同）

**边界条件:**
- B 面无 regions → 不渲染 B 面 page
- B 面有语文作文（essay_cn）→ 不走 a4-col，按现有 A3 作文逻辑渲染（此场景不存在于 A4，但防御性处理）
- A 面无 essay（只有固定区）→ a4-col 内只有 col-warning

- [ ] **Step 1: 提取 renderFixedRegions 函数**

在 `renderA3Col` 函数之后、`renderColumnRegions` 之前插入：

```javascript
function renderFixedRegions(config, digitBoxes, choiceGroupsHTML, fillHTML) {
  return `
    <div class="title-area">
      <div class="exam-title">${config.examTitle || ''}</div>
      <div class="subject-title">${config.subjectTitle || ''} 答 题 卡</div>
    </div>
    <div class="info-box">
      <div class="info-left">
        <div class="info-row"><span class="info-label">姓\u3000名</span><span class="info-line"></span></div>
        <div class="info-row"><span class="info-label">准考证号</span><span class="info-boxes">${digitBoxes}</span></div>
      </div>
      <div class="info-right"><div class="barcode-area">
        <span class="barcode-title">贴条形码区</span>
        <span class="barcode-hint">（正面朝上，切勿贴出虚线方框）</span>
      </div></div>
    </div>
    <div class="notice-box">
      <div class="notice-label-col"><span>注意事项</span></div>
      <div class="notice-middle">
        <div class="notice-content">
          <p>1.答题前，考生先将自己的姓名、准考证号填写清楚，并认真核对条形码上的姓名、准考证号和科目；</p>
          <p>2.选择题部分请用2B铅笔填涂方格，修改时用橡皮擦擦干净，不要留痕迹；</p>
          <p>3.非选择题部分请用0.5毫米黑色墨水签字笔书写，字体工整、笔迹清楚；</p>
          <p>4.在草稿纸、试题卷上答题无效；</p>
          <p>5.请勿折叠答题卡，保持字体工整、笔迹清晰、卡面清洁。</p>
        </div>
        <div class="absent-in-notice">
          <div class="absent-checkbox"></div>
          <div class="absent-line"></div>
          <span class="absent-hint">此方框为缺考考生标记，由监考员用2B铅笔填涂。</span>
        </div>
      </div>
      <div class="notice-example">
        <span>正确</span><span>填涂</span><span>示例</span>
        <div class="example-marks"><span class="filled"></span></div>
      </div>
    </div>
    <div class="section-bar">选 择 题（请用2B铅笔填涂）</div>
    <div class="choice-box">
      <div class="choice-groups">${choiceGroupsHTML}</div>
    </div>
    <div class="section-bar">非选择题（请用0.5毫米黑色墨水签字笔书写）</div>
    ${fillHTML}`;
}
```

- [ ] **Step 2: 修改 A3 渲染路径使用 renderFixedRegions**

在 `renderFromLayout` 的 A3 分支中，将 `leftCol` 变量替换为调用 `renderFixedRegions(config, digitBoxes, choiceGroupsHTML, fillHTML)`。现有硬编码 HTML（L374-415）删除，替换为函数调用。**输出完全相同。**

- [ ] **Step 3: 重写 _renderA4**

替换整个 `_renderA4` 函数（L506-613）：

```javascript
function _renderA4(previewWrap, layout, config, digitBoxes, choiceGroupsHTML, fillHTML) {
  const sideA = layout.sides[0];
  const sideB = layout.sides[1];

  // 为 regions 注入 _side/_col（交互模块需要）
  function tagRegions(side, sideIdx) {
    for (const col of side.columns) {
      for (const r of col.regions) {
        r._side = side.side;
        r._col = col.col;
        r._sideIdx = sideIdx;
      }
    }
  }
  tagRegions(sideA, 0);
  if (sideB) tagRegions(sideB, 1);

  // A 面 col 0 的非 fixed regions
  const aEssayRegions = sideA.columns[0]?.regions?.filter(r => r.type !== 'fixed') || [];

  const pageAContent = `
    <div class="a4-content">
      ${renderFixedRegions(config, digitBoxes, choiceGroupsHTML, fillHTML)}
      <div class="a4-col">
        ${renderColumnRegions(aEssayRegions, false, 0, 0)}
      </div>
    </div>`;

  // B 面：有 regions 时渲染，无 regions 时不渲染 B 面 page [F05 修复]
  let pageBHTML = '';
  if (sideB && sideB.columns) {
    const bRegions = sideB.columns[0]?.regions || [];
    if (bRegions.length > 0) {
      pageBHTML = `
        <div class="page-label">B 面（背面）</div>
        <div class="page" data-paper="A4" id="pageB">
          <div class="a4-content">
            <div class="a4-col a4-col--full">
              ${renderColumnRegions(bRegions, false, 1, 0)}
            </div>
          </div>
        </div>`;
    }
  }

  previewWrap.innerHTML = `
    <div class="page-label">A 面（正面）</div>
    <div class="page" data-paper="A4" id="pageA">${pageAContent}</div>
    ${pageBHTML}`;

  applyCSSToPage(previewWrap.querySelector('#pageA'), config);
  const pageBEl = previewWrap.querySelector('#pageB');
  if (pageBEl) applyCSSToPage(pageBEl, config);
}
```

- [ ] **Step 4: 跑后端回归测试**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_tpl_parser.py tests/test_api_exam/test_cards.py -x -q
```

预期: 全部 PASS（前端变更不影响后端测试）。

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend/src/card-editor/render.js
git commit -m "refactor: 重写 _renderA4 — 统一 A3/A4 复用 renderColumnRegions + renderFixedRegions"
```

---

### Task 4: 选择题竖排修复

**Files:**
- Modify: `frontend/src/card-editor/render.js:40-143` (buildChoiceGroupsHTML)
- Modify: `frontend/src/components/CardEditor.vue:252-265` (getValues choiceGroups 重建)

**测试契约:**
1. TQL 坐标存在时逐组竖排渲染，无坐标时横排
   - 入口: `renderFromLayout(previewWrap, layout, config)` 渲染包含 choiceGroups 的布局
   - 反例: 错误实现会忽略 x/y/w 坐标，始终用 flatMap 横排——英语选择题变成 55 题横排大网格
   - 边界: 混合有/无坐标的 groups（不应发生，但防御性处理：全有→竖排，任一无→横排）
   - 回归: A3 科目的选择题渲染不变（A3 无 TQL 坐标时走横排）
   - 命令: 手动浏览器验证

**审查清单:**
- ✓ `hasTqlCoords` 判断正确（`groups.some(g => g.x !== undefined)`）
- ✓ 有坐标时调用已有的 `renderGroup(g)` 函数
- ✓ 无坐标时保持现有 flatMap 逻辑不变
- ✗ `getValues()` 重建 choiceGroups 时丢弃 x/y/w
- 关键行为: A3 科目（无 TQL 坐标）选择题渲染完全不变

**边界条件:**
- 全部 groups 都有坐标 → 逐组 renderGroup 竖排
- 全部 groups 都无坐标 → flatMap 横排（现有逻辑不变）
- 只有 1 个 group → renderGroup 或横排均可

- [ ] **Step 1: 修改 buildChoiceGroupsHTML 尾部逻辑**

替换 L115-142（`// 编辑器统一网格` 注释开始到函数结束）：

```javascript
  // 判断是否有 TQL 坐标
  const hasTqlCoords = groups.some(g => g.x !== undefined);

  if (hasTqlCoords) {
    // TQL 坐标模式：逐组渲染，用相对定位放置
    return groups.map(g => renderGroup(g)).join('');
  }

  // 无坐标模式：所有题目合并，固定 perRow 列，横排（现有逻辑）
  const allQs = groups.flatMap(g => g.questions.map(q => ({ ...q, options: q.options || g.options })));
  const maxOpts = Math.max(...allQs.map(q => q.options));
  let html = '';
  const colTemplate = `4mm repeat(${perRow}, 1fr) 4mm`;
  for (let start = 0; start < allQs.length; start += perRow) {
    const batch = allQs.slice(start, start + perRow);
    const count = batch.length;
    const rows = maxOpts + 1;
    let cells = '<div class="omr-left"></div>';
    for (const q of batch) cells += `<div class="choice-cell choice-header">${q.qno}</div>`;
    for (let e = count; e < perRow; e++) cells += '<div class="choice-cell"></div>';
    cells += '<div class="omr-right"></div>';
    for (let o = 0; o < maxOpts; o++) {
      cells += '<div class="omr-left"><div class="omr-dot"></div></div>';
      for (const q of batch) {
        if (o < q.options) {
          cells += `<div class="choice-cell"><span class="bracket">${symbols[o]}</span></div>`;
        } else {
          cells += '<div class="choice-cell"></div>';
        }
      }
      for (let e = count; e < perRow; e++) cells += '<div class="choice-cell"></div>';
      cells += '<div class="omr-right"><div class="omr-dot"></div></div>';
    }
    html += `<div class="choice-group"><div class="choice-grid-inner" style="grid-template-columns: ${colTemplate}; grid-template-rows: repeat(${rows}, auto);">${cells}</div></div>`;
  }
  return html;
```

- [ ] **Step 2: 修改 getValues 保留 TQL 坐标**

在 `CardEditor.vue` L252-265，修改 choiceGroups 重建逻辑，保留原始 configGroups 的 x/y/w：

```javascript
  if (window._choices && window._choices.length > 0) {
    // 如果原始 config 有带坐标的 choiceGroups，保留坐标
    const origGroups = base.choiceGroups || [];
    const origMap = new Map();
    for (const g of origGroups) {
      if (g.x !== undefined) origMap.set(`${g.start}-${g.count}`, g);
    }

    const groups = []
    let cur = { start: window._choices[0].qno, options: window._choices[0].options, count: 1 }
    for (let i = 1; i < window._choices.length; i++) {
      const c = window._choices[i]
      if (c.options === cur.options && c.qno === cur.start + cur.count) {
        cur.count++
      } else {
        // 尝试从原始 groups 恢复坐标
        const orig = origMap.get(`${cur.start}-${cur.count}`);
        if (orig) { cur.x = orig.x; cur.y = orig.y; cur.w = orig.w; }
        groups.push(cur)
        cur = { start: c.qno, options: c.options, count: 1 }
      }
    }
    const orig = origMap.get(`${cur.start}-${cur.count}`);
    if (orig) { cur.x = orig.x; cur.y = orig.y; cur.w = orig.w; }
    groups.push(cur)
    vals.choiceGroups = groups
  }
```

- [ ] **Step 3: 跑后端回归测试**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_tpl_parser.py tests/test_api_exam/test_cards.py -x -q
```

预期: 全部 PASS。

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend/src/card-editor/render.js frontend/src/components/CardEditor.vue
git commit -m "fix: 选择题竖排 — TQL 坐标存在时逐组 renderGroup，保留 x/y/w"
```

---

### Task 5: PDF 导出修复

**Files:**
- Modify: `frontend/src/card-editor/export.js:73-143` (getCleanHTML)
- Modify: `frontend/src/card-editor/export.js:211-289` (batchExportPdf CSS 部分)

**测试契约:**
1. getCleanHTML 清 marginBottom + CSS 用 fetch 内联
   - 入口: 点击"导出 PDF"按钮或调用 `batchExportPdf()`
   - 反例: 错误实现不清 marginBottom → 页面互相顶压；CSS 扫描失败 → PDF 无样式
   - 边界: styles.css fetch 失败 → fallback 到 document.styleSheets 扫描（降级而非崩溃）
   - 回归: N/A
   - 命令: 手动浏览器测试导出

**审查清单:**
- ✓ `getCleanHTML` 的 `clone.style.marginBottom = ''` 与 `batchExportPdf` 一致
- ✓ CSS 获取优先用 `fetch('/card-editor/styles.css')`
- ✓ fetch 失败时 fallback 到 `document.styleSheets` 扫描
- ✓ 导出 HTML 的 `font-family` 包含 Noto CJK fallback
- ✗ 两条导出路径的 CSS 获取方式不一致
- 关键行为: A3 和 A4 的 PDF 导出都受益

- [ ] **Step 1: 新增 fetchStyleCSS 辅助函数 + 改造 getCleanHTML 为 async**

在 `export.js` 的 `getCleanHTML` 函数之前插入：

```javascript
let _cachedStyleCSS = null;

async function fetchStyleCSS() {
  if (_cachedStyleCSS) return _cachedStyleCSS;
  try {
    const resp = await fetch('/card-editor/styles.css');
    if (resp.ok) {
      _cachedStyleCSS = await resp.text();
      return _cachedStyleCSS;
    }
  } catch { /* fetch 失败，降级 */ }
  // fallback: 运行时扫描 document.styleSheets
  for (const sheet of document.styleSheets) {
    try {
      if (sheet.href && sheet.href.includes('styles.css')) {
        return Array.from(sheet.cssRules).map(r => r.cssText).join('\n');
      }
    } catch { /* 跨域 */ }
  }
  return '';
}
```

将 `getCleanHTML` 改为 `async function getCleanHTML()`：

在 L86 `clone.style.transform = '';` 之后加：
```javascript
    clone.style.marginBottom = '';
```

将 L105-113 的 styleSheets 扫描替换为：
```javascript
  const styleContent = await fetchStyleCSS();
```

更新 font-family fallback（L130）：
```javascript
  font-family: SimSun, "宋体", "Noto Serif CJK SC", serif;
```

- [ ] **Step 2: 更新所有 getCleanHTML 调用方为 await**

`export.js` 内部调用 `getCleanHTML` 的位置：
- L24: `const html = getCleanHTML()` → `const html = await getCleanHTML()`
- L51: 同上
- L162: `publishCard` 中 → 已是 async，加 await 即可

`CardEditor.vue` 中如果有调用也需更新（通过 `window._getCleanHTML` 暴露）。

- [ ] **Step 3: 简化 batchExportPdf 中的 CSS 获取**

将 `batchExportPdf` L273-280 的 styleSheets 扫描替换为：
```javascript
      const styleContent = await fetchStyleCSS();
```

同时更新 font-family：
```javascript
body { font-family: SimSun, "宋体", "Noto Serif CJK SC", serif; ...
```

- [ ] **Step 4: 跑后端回归测试**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_tpl_parser.py tests/test_api_exam/test_cards.py -x -q
```

预期: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend/src/card-editor/export.js
git commit -m "fix: PDF 导出 — 清 marginBottom + CSS fetch 内联 + Noto CJK fallback"
```

---

### Task 6: 英语/化学 editor-layout API 测试

**Files:**
- Modify: `tests/test_api_exam/test_cards.py`

**测试契约:**
1. 英语/化学通过 API 返回 A4 双面布局
   - 入口: `GET /api/v1/card/editor-layout/{subject_id}` 返回 layout
   - 反例: 如果 _fallback_layout 的 A4 判断条件错误，英语会返回 A3 layout
   - 边界: 科目名为"英语A"时（带后缀）也能匹配 TQL
   - 回归: 数学等 A3 科目仍返回 A3
   - 命令: `python -m pytest tests/test_api_exam/test_cards.py::TestEditorLayout -v`

**审查清单:**
- ✓ 英语 subject 通过 API 返回 paper=A4
- ✓ 返回的 layout sides 结构符合 A4 契约
- ✗ A3 科目返回 A4（错误的纸型判断）
- 关键行为: 现有 TestEditorLayout 测试不受影响

- [ ] **Step 1: 在 TestEditorLayout 类中新增 A4 科目测试**

```python
    async def test_english_returns_a4_layout(self, client: AsyncClient, seed_subject, db):
        """英语科目应返回 A4 双面布局。[F03 修复: assert 而非 if]"""
        from edu_cloud.modules.exam.models import Subject
        headers, exam_id, _ = seed_subject
        eng = Subject(
            exam_id=exam_id, name="英语", code="english",
            school_id="test-school-id", full_score=150, sort_order=2,
        )
        db.add(eng)
        await db.commit()
        await db.refresh(eng)

        resp = await client.get(f"/api/v1/card/editor-layout/{eng.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        layout = data["layout"]
        paper = layout.get("paper") or layout.get("config", {}).get("paperSize")
        assert paper == "A4", f"英语应返回 A4，实际返回 {paper}"
        assert len(layout["sides"]) == 2
        for side in layout["sides"]:
            assert len(side["columns"]) == 1
            assert side["columns"][0]["col"] == 0

    async def test_chemistry_returns_correct_layout(self, client: AsyncClient, seed_subject, db):
        """化学科目布局结构测试。[F04 修复: 补化学用例]"""
        from edu_cloud.modules.exam.models import Subject
        headers, exam_id, _ = seed_subject
        chem = Subject(
            exam_id=exam_id, name="化学", code="chemistry",
            school_id="test-school-id", full_score=100, sort_order=3,
        )
        db.add(chem)
        await db.commit()
        await db.refresh(chem)

        resp = await client.get(f"/api/v1/card/editor-layout/{chem.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        layout = data["layout"]
        paper = layout.get("paper") or layout.get("config", {}).get("paperSize")
        # 化学可能是 A4（TQL 路径）或 A3（fallback，14 选择 < 30）
        # 无论哪种纸型，结构必须一致
        if paper == "A4":
            for side in layout["sides"]:
                assert len(side["columns"]) == 1

    async def test_math_stays_a3(self, client: AsyncClient, seed_subject):
        """数学科目不应误升为 A4。[F03 修复: 反例断言]"""
        headers, _, subject_id = seed_subject  # seed_subject 默认是数学
        resp = await client.get(f"/api/v1/card/editor-layout/{subject_id}", headers=headers)
        assert resp.status_code == 200
        layout = resp.json()["layout"]
        paper = layout.get("paper") or layout.get("config", {}).get("paperSize")
        assert paper == "A3", f"数学应返回 A3，实际返回 {paper}"
```

注意：英语 fallback 条件（>30 选择题 + B 面）在测试环境中满足。化学 fallback 为 A3（14 < 30），但 TQL 路径可能返回 A4。

- [ ] **Step 2: 运行测试**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api_exam/test_cards.py::TestEditorLayout -v
```

预期: 全部 PASS。

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add tests/test_api_exam/test_cards.py
git commit -m "test: 英语 editor-layout A4 契约验证"
```

---

### Task 7: 前端 Vitest 渲染回归测试 [F06 修复]

**Files:**
- Create: `frontend/src/card-editor/__tests__/render.test.js`

**测试契约:**
1. renderFromLayout 对 A4 layout 生成正确 DOM 结构
   - 入口: `renderFromLayout(container, a4Layout, config)` 在 happy-dom 中调用
   - 反例: 错误实现不生成 `.a4-col` 容器 → 断言 querySelector('.a4-col') 为 null 时失败
   - 边界: B 面无 regions → 无 #pageB 元素
   - 回归: 防止 A4 渲染路径回退到旧的 flat HTML
   - 命令: `cd frontend && npx vitest run src/card-editor/__tests__/render.test.js`

**审查清单:**
- ✓ A4 layout 生成 `.a4-content > .a4-col` 结构
- ✓ A3 layout 生成 `.a3-layout > .a3-col` 结构（不变）
- ✗ A4 layout 生成 `.a4-essay-area`（旧结构）

**边界条件:**
- A4 无 B 面 → 不生成 #pageB
- A4 B 面有 regions → 生成 `.a4-col.a4-col--full`
- A3 layout → 生成 3 个 `.a3-col`

- [ ] **Step 1: 写 Vitest 渲染测试**

```javascript
// frontend/src/card-editor/__tests__/render.test.js
import { describe, it, expect, beforeEach } from 'vitest'
import { renderFromLayout, applyCSSToPage } from '../render.js'

function makeA4Layout() {
  return {
    paper: 'A4',
    config: { paperSize: 'A4', examTitle: 'Test', subjectTitle: '英语',
      choiceCount: 0, optionCount: 4, choicePerRow: 15, choiceGroups: [],
      fillCount: 0, essayCount: 1, essayConfig: [{ score: 10 }],
      titleSize: 14, subtitleSize: 16, titleSpacing: 1, subtitleSpacing: 4,
      titleGap: 1, subtitleGap: 1.5, infoHeight: 18, infoPadding: 2,
      infoRowGap: 2, infoFontSize: 10, infoBorderWidth: 1, nameLineWidth: 35,
      digitCount: 9, digitBoxSize: 4.5, digitGap: 0.8, barcodeWidthPct: 40,
      barcodeTitleSize: 12, noticeHeight: 20, noticeLabelWidth: 6,
      noticeLabelSize: 10, noticeFontSize: 7, exampleWidth: 10,
      noticeBorderWidth: 1, absentPadding: 1, zoom: 100 },
    sides: [
      { side: 'A', columns: [{ col: 0, regions: [
        { id: 'header', type: 'fixed', role: 'header' },
        { id: 'essay-1', type: 'essay', qno: 1, score: 10, subs: [], heightRatio: 1 },
      ]}]},
      { side: 'B', columns: [{ col: 0, regions: [
        { id: 'essay-2', type: 'essay', qno: 2, score: 10, subs: [], heightRatio: 1 },
      ]}]},
    ],
  }
}

function makeA3Layout() {
  return {
    paper: 'A3',
    config: { paperSize: 'A3', examTitle: 'Test', subjectTitle: '数学',
      choiceCount: 0, optionCount: 4, choicePerRow: 15, choiceGroups: [],
      fillCount: 0, essayCount: 1, essayConfig: [{ score: 10 }],
      titleSize: 14, subtitleSize: 16, titleSpacing: 1, subtitleSpacing: 4,
      titleGap: 1, subtitleGap: 1.5, infoHeight: 18, infoPadding: 2,
      infoRowGap: 2, infoFontSize: 10, infoBorderWidth: 1, nameLineWidth: 35,
      digitCount: 9, digitBoxSize: 4.5, digitGap: 0.8, barcodeWidthPct: 40,
      barcodeTitleSize: 12, noticeHeight: 20, noticeLabelWidth: 6,
      noticeLabelSize: 10, noticeFontSize: 7, exampleWidth: 10,
      noticeBorderWidth: 1, absentPadding: 1, zoom: 100 },
    sides: [
      { side: 'A', columns: [
        { col: 0, regions: [{ id: 'header', type: 'fixed', role: 'header' }] },
        { col: 1, regions: [{ id: 'essay-1', type: 'essay', qno: 1, score: 10, subs: [], heightRatio: 1 }] },
        { col: 2, regions: [] },
      ]},
      { side: 'B', columns: [
        { col: 0, regions: [] }, { col: 1, regions: [] }, { col: 2, regions: [] },
      ]},
    ],
  }
}

describe('renderFromLayout', () => {
  let container

  beforeEach(() => {
    container = document.createElement('div')
    // mock window globals card-editor expects
    window._choices = []
  })

  it('A4 layout generates .a4-content > .a4-col structure', () => {
    const layout = makeA4Layout()
    renderFromLayout(container, layout, layout.config)
    expect(container.querySelector('.a4-content')).not.toBeNull()
    expect(container.querySelector('.a4-col')).not.toBeNull()
    expect(container.querySelector('.a3-layout')).toBeNull()
  })

  it('A4 B-side with regions generates #pageB with .a4-col--full', () => {
    const layout = makeA4Layout()
    renderFromLayout(container, layout, layout.config)
    const pageB = container.querySelector('#pageB')
    expect(pageB).not.toBeNull()
    expect(pageB.querySelector('.a4-col--full')).not.toBeNull()
  })

  it('A4 B-side without regions does not generate #pageB', () => {
    const layout = makeA4Layout()
    layout.sides[1].columns[0].regions = []
    renderFromLayout(container, layout, layout.config)
    expect(container.querySelector('#pageB')).toBeNull()
  })

  it('A3 layout generates .a3-layout > .a3-col structure', () => {
    const layout = makeA3Layout()
    renderFromLayout(container, layout, layout.config)
    expect(container.querySelector('.a3-layout')).not.toBeNull()
    expect(container.querySelectorAll('.a3-col').length).toBe(3)
    expect(container.querySelector('.a4-col')).toBeNull()
  })
})
```

- [ ] **Step 2: 运行 Vitest**

```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/card-editor/__tests__/render.test.js
```

预期: 全部 PASS。

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend/src/card-editor/__tests__/render.test.js
git commit -m "test: A4/A3 渲染 DOM 结构 Vitest 回归测试"
```

---

### Task 8: 最终回归验证

**审查清单:**
- ✓ 全部后端测试通过
- ✓ 全部前端 Vitest 测试通过
- ✓ A3 科目（数学等）布局不受影响
- ✓ design.md 标记状态

- [ ] **Step 1: 跑完整回归（后端 + 前端）**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_tpl_parser.py tests/test_api_exam/test_cards.py -v
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run
```

预期: 所有后端和前端测试 PASS。

- [ ] **Step 2: 输出审查交接单**

按 review-templates.md 格式输出审查交接单，包含逐 Task 自审表 + 验证清单自检 + 自查段。
