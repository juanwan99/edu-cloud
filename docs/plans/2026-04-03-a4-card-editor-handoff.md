---
type: handoff
created: 2026-04-03 16:21:37
project_dir: C:\Users\Administrator\edu-cloud
---

# A4 双面答题卡编辑器 — 重构交接卡

## 背景

答题卡编辑器原本只支持 A3 展开布局（数学/语文/物理等 9 科），工作正常。本会话尝试为英语和化学添加 A4 双面支持，经过多轮修改但效果不理想。GPT Codex 独立诊断（threadId: `019d5264-3357-7131-86bc-2c538e9ca588`）确认了 5 个根因，建议重写 `_renderA4` 而非继续补丁。

## 本会话已完成的改动（均未 commit）

### 后端改动

| 文件 | 改动 | 状态 |
|------|------|------|
| `src/edu_cloud/modules/card/router.py` | get_editor_layout 结构校验：default=A4 但 saved=A3 时丢弃旧结构 | ✅ 可保留 |
| `src/edu_cloud/modules/card/subject_defaults.py` | tql_to_editor_layout A4 双面分支、_infer_sub_count（仅 A4 生效）、_fallback_layout 支持 A4、_build_subs 增加 blanks_per_sub 参数、displayLabel 支持 | ⚠️ 方向正确但需重新审视 |
| `src/edu_cloud/modules/card/tpl_parser.py` | A4 双面检测（page_width <= 2000）| ✅ 正确 |

### 前端改动

| 文件 | 改动 | 状态 |
|------|------|------|
| `frontend/src/card-editor/render.js` | _renderA4 重写（多次修改，架构漂移）| ❌ 需要重新设计 |
| `frontend/src/card-editor/render.js` | applyCSSToPage 改用 previewWrap.querySelector | ✅ 可保留 |
| `frontend/src/card-editor/render.js` | A4 高度从 210 改为 297 | ✅ 正确 |
| `frontend/src/card-editor/render.js` | renderFromLayout 改为 layout.paper 优先判断纸型 | ✅ 可保留 |
| `frontend/src/card-editor/export.js` | batchExportPdf 批量导出函数 | ⚠️ 功能完整但依赖正确的渲染 |
| `frontend/src/card-editor/model.js` | createDefaultLayout 支持 A4 单栏双面 | ✅ 可保留 |
| `frontend/src/components/CardEditor.vue` | paperSize 同步、去掉 select 硬编码 A3、A4 适配缩放 | ⚠️ 部分可保留 |
| `frontend/public/card-editor/styles.css` | A4 页面样式（多次调整）| ❌ 需要重新设计 |
| `frontend/src/pages/ExamDetailPage.vue` | "导出全部 PDF" 按钮 + handleBatchExportPdf | ✅ 可保留 |

### 已删除的数据

- `src/editor_layouts/*.json` — 所有保存的布局文件已被清空（本会话操作），所有科目会从 TQL 默认布局重新生成

## GPT Codex 独立诊断的 5 个根因

### 根因 1：A4 没有固定高度的 flex 容器（A/B 面高度不一致）
- **位置**: `frontend/public/card-editor/styles.css:133` + `render.js:506`
- **问题**: A3 靠 `.a3-layout`（grid）+ `.a3-col`（flex column）控制高度，`heightRatio` 通过 `flex:N` 分配空间。A4 的 `.page` 不是 flex 容器，`essay-item` 的 `flex:N` 无效。更糟的是 `styles.css` 用 `flex: none !important` 直接抹掉了 A4 essay 的 flex
- **修复方向**: A4 也需要一个固定高度的 flex column 容器（类似 `.a3-col`），让 `heightRatio` 正确分配空间

### 根因 2：页间距大（底部警告贴底失效）
- **位置**: `styles.css:266` `.col-warning-bottom { margin-top:auto }`
- **问题**: `margin-top: auto` 只在 flex 容器里才能贴底。A3 的 `.a3-col` 是 flex 所以成立；A4 的 `.page` 不是 flex，失效
- **修复方向**: 统一到 flex 容器体系

### 根因 3：PDF 导出排版乱（3 个子问题）
- **位置**: `export.js:73` getCleanHTML + `export.js:105` CSS 抽取 + `html_export.py:23`
- **问题 A**: `getCleanHTML()` 清了 `transform` 但没清 `marginBottom`（负值补偿），导致页面互相顶压。批量导出清了 `marginBottom`，两条链路不一致
- **问题 B**: CSS 靠运行时扫 `document.styleSheets` 抽取，不稳定，可能拿不到
- **问题 C**: Playwright 服务端可能没有中文字体（宋体/黑体），字体度量变化导致排版漂移
- **修复方向**: getCleanHTML 同时清 marginBottom；CSS 改为 fetch 内联；服务端装中文字体

### 根因 4：A4 选择题横排（应该是 3 列竖排）
- **位置**: `render.js:115` buildChoiceGroupsHTML + `CardEditor.vue:249` getValues
- **问题**: buildChoiceGroupsHTML 最终把所有组 flatMap 成一个固定 perRow 的横向大网格，完全忽略了 TQL 的 x/y/w 坐标和竖排逻辑。getValues() 每次重建 choiceGroups 时丢弃 x/y/w
- **修复方向**: 保留 TQL 坐标，恢复 renderGroup() 的竖排逻辑

### 根因 5：_renderA4 架构漂移
- **位置**: `render.js:506-610`
- **问题**: A4 绕开了 A3 的 `renderColumnRegions()` 主轴，自己 flatten regions；固定区 HTML 从 A3 复制了一份而非复用；默认模型和 TQL 模型的 layout 契约不统一
- **修复方向**: GPT 建议重写 _renderA4，统一 A3/A4 复用 `renderColumnRegions()` + `renderEssayRegion()`，只在页面骨架层区分（A3 = 3 栏 frame，A4 = 1 栏 frame，但内部都是 flex column）

## GPT 建议的架构方向

> 统一方向：A3/A4 共用 `renderColumnRegions()` 和 `renderEssayRegion()`，只把"页面骨架"抽象成 `renderPageFrame({ paper, side, fixedRegions, answerColumns })`。A3 用 3 栏 frame，A4 用 1 栏 frame，但都要有同样的"固定高度内部 flex 容器"。同时把 A4 layout 契约统一成一种形式。

## 约束与偏好

- **T3 流程**：跨多文件（后端布局 + 前端渲染 + CSS + 导出），有架构重新设计
- **不打补丁**：用户明确拒绝继续打补丁，要求按 GPT 诊断的根因做架构修复
- **A3 科目不能劣化**：数学、语文、物理等 A3 科目的布局和导出必须保持不变
- **TQL 模板是唯一参照**：导出的 PDF 排版必须与 TQL 模板原图一致
- **后端在 WSL 运行**：文件变更可能不触发 `--reload`，需手动重启
- **WSL 内用 `python3`，Windows 用 `python`**
- **用户当前登录账户**：`admin_academic_director_2`（育才实验中学，5 个考试）。密码 `123456`
- **已安装 playwright + chromium** 在 WSL 中（`pip install --break-system-packages playwright && playwright install chromium`）
- **editor_layouts/ 已清空**：所有保存的布局文件已删除，所有科目从 TQL 默认重新生成

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-03 16:21:37
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-a4-card-editor-handoff.md 了解上下文。

任务：按 GPT Codex 独立诊断的 5 个根因，重构 A4 双面答题卡编辑器。核心工作：

1. 重写 _renderA4()：统一 A3/A4 复用 renderColumnRegions + renderEssayRegion，A4 用 1 栏 flex column frame（类似 a3-col）
2. 修复 A4 CSS：添加 a4-col 容器（flex column + 固定高度），删除 flex:none !important hack
3. 修复 PDF 导出：getCleanHTML 清 marginBottom + CSS 改为 fetch 内联 + 检查中文字体
4. 修复选择题竖排：保留 TQL x/y/w 坐标，恢复 buildChoiceGroupsHTML 的竖排逻辑
5. 统一 A4 layout 契约（model.js 和 subject_defaults.py 一致）

铁律：A3 科目（数学等）不能受任何影响。每步改完跑测试 `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_tpl_parser.py tests/test_api_exam/test_cards.py -x -q` 确认不回归。

注意：后端在 WSL 内运行，代码改完后需手动重启。已有的编辑器改进（分割线拖拽、小问删除、AbortController、onAnyChange 分离、批量导出按钮）保留不动。

完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
