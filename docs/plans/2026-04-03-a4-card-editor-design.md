# A4 双面答题卡编辑器重构设计

> 创建: 2026-04-03 17:35:39
> 状态: 设计完成
> GPT Codex 诊断: threadId `019d5264-3357-7131-86bc-2c538e9ca588`

## 背景

答题卡编辑器原本只支持 A3 展开布局（数学/语文/物理等 9 科），工作正常。为英语和化学添加 A4 双面支持时，经多轮修改效果不理想。GPT Codex 独立诊断确认了 5 个根因，建议重写 `_renderA4` 而非继续补丁。

## 根因诊断（GPT Codex）

1. **A4 缺少 flex 容器** — A3 靠 `.a3-col`（flex column）控制高度分配，A4 没有等价容器，`heightRatio` 的 `flex:N` 无效
2. **底部警告贴底失效** — `margin-top:auto` 只在 flex 容器内生效，A4 的 `.page` 不是 flex
3. **PDF 导出排版乱** — `getCleanHTML` 未清 `marginBottom`、CSS 靠运行时扫 `document.styleSheets` 不稳定
4. **选择题横排** — `buildChoiceGroupsHTML` 把所有组 flatMap 成横向大网格，忽略 TQL x/y/w 坐标和竖排逻辑
5. **_renderA4 架构漂移** — 绕开 A3 的 `renderColumnRegions()` 主轴，固定区 HTML 从 A3 复制而非复用

## §1 架构：统一页面骨架

**方案：** A3/A4 共用 `renderColumnRegions()` + `renderEssayRegion()`，只在页面骨架层区分纸型。

**A3 骨架（不动）：**
```
.page[A3] → .a3-layout (grid 3col)
  → .a3-col (flex column, 固定高度)
    → .col-warning + essay-items (flex:heightRatio)
    → .col-warning-bottom (margin-top:auto 贴底)
```

**新 A4 骨架：**
```
.page[A4] → .a4-content (flex column, 固定高度 = 297mm - padding)
  → 固定区（header/info/notice/choices/fill）— flex:none
  → .a4-col (flex column, flex:1 占剩余空间)
    → .col-warning + essay-items (flex:heightRatio)
    → .col-warning-bottom (margin-top:auto 贴底)

.page[A4] #pageB → .a4-content
  → .a4-col (flex column, height:100%)
    → essay-items
    → .col-warning-bottom
```

**关键变更：**
- 新增 `.a4-col` CSS 类：`display:flex; flex-direction:column;`，与 `.a3-col` 类似但无 OMR 角标
- 删除 `flex: none !important` hack（styles.css L397-398）
- `_renderA4` 重写：固定区 HTML 提取为共享函数 `renderFixedRegions()`，essay 区调用 `renderColumnRegions()`

**A3 保护：** A3 渲染路径（render.js L369-499）完全不动，只提取固定区 HTML 为函数复用。

## §2 选择题竖排修复

**问题：** `buildChoiceGroupsHTML()` L116-142 把所有组 flatMap 成横向大网格，忽略 TQL 坐标。L72-113 有正确的 `renderGroup()` 函数（支持竖排）但最终没被调用。

**修复：**
- 当 `configGroups` 有 TQL 坐标（`x/y/w` 字段）时，逐组调用 `renderGroup(g)` 并按坐标定位
- 当无坐标时（手动创建的 layout），保持现有横向 flatMap 逻辑
- `getValues()` 在 `CardEditor.vue` 中重建 `choiceGroups` 时保留 `x/y/w` 字段

**判断条件：** `const hasTqlCoords = groups.some(g => g.x !== undefined)`

## §3 PDF 导出修复

**A. getCleanHTML 清 marginBottom：** 在 `clone.style.transform = ''` 后面加 `clone.style.marginBottom = ''`，与 `batchExportPdf` 保持一致。

**B. CSS 用 fetch 内联：** 新增 `fetchStyleCSS()` 辅助函数，用 `fetch('/card-editor/styles.css')` 获取 CSS 文本。`getCleanHTML()` 和 `batchExportPdf()` 共用此函数。

**C. 中文字体 fallback：** 确认导出 HTML 的 `font-family` 声明包含 `"Noto Sans CJK SC"` / `"Noto Serif CJK SC"` 作为 fallback。Dockerfile 已包含 Noto CJK 字体，不增加新依赖。

## §4 后端 layout 契约统一

**统一 A4 layout 契约：**
```json
{
  "paper": "A4",
  "config": { "paperSize": "A4", "..." : "..." },
  "sides": [
    { "side": "A", "columns": [{ "col": 0, "regions": ["fixed...", "essay..."] }] },
    { "side": "B", "columns": [{ "col": 0, "regions": ["essay..."] }] }
  ]
}
```

**约束：**
- A4 每面只有 1 个 column（`col: 0`）
- A 面 col 0 同时包含 fixed regions 和 essay regions
- B 面 col 0 只有 essay regions
- `paper` 字段和 `config.paperSize` 必须一致

**改动：** `tql_to_editor_layout()` 中 A4 路径将 col 1+ 的 essay regions 合并到 col 0（fixed 之后）。`model.js` 和 `_fallback_layout()` 已符合契约，无需改动。

## §5 测试策略与 A3 保护

**回归防护：** 每步改完跑 `python -m pytest tests/test_services_exam/test_tpl_parser.py tests/test_api_exam/test_cards.py -x -q`

**新增后端测试：**
- `test_tpl_parser.py`：A4 双面 layout 契约断言（每面 1 column、A 面有 fixed + essay、B 面无 fixed）
- `test_cards.py`：英语/化学 `editor-layout` API 测试（返回 `paper: "A4"` 且 sides 结构正确）

**前端验证：** 手动浏览器验证（A3 数学 + A4 英语 + A4 化学），视觉验收权归用户。

## 改动文件清单

| 文件 | 改动类型 |
|------|---------|
| `frontend/src/card-editor/render.js` | 重写 `_renderA4`，提取 `renderFixedRegions()`，修改 `buildChoiceGroupsHTML` |
| `frontend/public/card-editor/styles.css` | 新增 `.a4-col`，删除 `flex:none !important` |
| `frontend/src/card-editor/export.js` | `getCleanHTML` 清 marginBottom + `fetchStyleCSS()` |
| `src/edu_cloud/modules/card/subject_defaults.py` | A4 路径 col 合并 |
| `tests/test_services_exam/test_tpl_parser.py` | 新增 A4 契约测试 |
| `tests/test_api_exam/test_cards.py` | 新增英语/化学 layout 测试 |

## 约束

- A3 科目（数学、语文、物理、生物、历史、政治、地理）不能受任何影响
- 后端在 WSL 运行，代码改完需手动重启
- editor_layouts/ 已清空，所有科目从 TQL/fallback 重新生成
- 已有编辑器改进（分割线拖拽、小问删除、AbortController、onAnyChange 分离、批量导出按钮）保留不动
