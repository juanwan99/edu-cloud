---
type: handoff
created: 2026-04-02 08:35:03
project_dir: C:\Users\Administrator\edu-cloud
---

# 答题卡编辑器攻关 — 交接卡（第二轮）

## 背景

接续上一轮攻关（`C:\Users\Administrator\edu-cloud\docs\plans\2026-04-01-card-editor-handoff.md`），本会话完成了大量编辑器功能改进和 bug 修复。所有改动**均未 commit**。

## 本会话完成的改动（均未 commit，共 13 文件 +694/-258 行）

### ExamDetailPage.vue — 科目管理
- 添加科目从手动填名+代码 → 预设 10 科复选框批量添加，默认全选，已有科目自动排除

### model.js — 布局分配
- `createDefaultLayout` 改为 essay 从 col 0 开始依次填充 6 个槽位（不再硬编码 col 1/2）

### CardEditor.vue — 布局加载
- 加载已保存布局后的结构修正：合并 col3+ 到 col2；填充空中间栏（完全空栏从后面借 region）
- 语文 B 面 essay 自动设为 `essay_cn` 类型
- 缩放适应模式（"适应"/"1:1" 按钮在 view-toggle 栏）
- `applyCSSToPage` 补偿缩放后的页面间距（marginBottom）
- 面板宽度 340→260px，预览区顶格

### render.js — 渲染引擎
- `tagRegions` 移到所有渲染之前执行（修复 `_side/_col` 标签缺失）
- `renderColumnRegions` 支持 `sideIdx/colIdx` 参数
- fill 类型 region 渲染为横线格式（题号 + 下划线）
- 连续 fill 合并为 2 列网格
- 空栏渲染 `empty-col-slot`（显示"右键添加题目"）
- `mergedRegions` 函数合并超出 3 栏的 regions
- `essay_cn` 语文作文渲染：标题行 + 正方形方格纸 + 每 200 字标注
  - 格子大小自动计算：`cellSize = sqrt(3 × colW × colH / target)`
  - 第一栏扣除 header 高度，三栏各自计算行数
- 题内分割线（`region.cuts`）虚线渲染
- 缩放补偿：`marginBottom = -(hPx * (1 - zoom))`
- 删除了 "请勿在此区域答题" 默认输出
- 选择题统一 16 列固定网格，删除 TQL 坐标分列分支

### interact.js — 交互层
- 右键菜单重构：
  - "添加题目分割线（拆为两道题）"
  - "添加题内分割线（阅卷切割）"
  - "编辑属性"
- 右键下划线：直接删除（不弹菜单）
- 右键小问标签（括号区）：直接删除整个小问
- 右键题内分割线：直接删除
- 空栏右键：显示"在此处添加题目"菜单，按 sideIdx/colIdx 精确定位
- 点击题目滚动：改用手动 `scrollTo` 只垂直滚动（修复水平偏移）
- 添加小问：改用 `stopImmediatePropagation` + `renderFromLayout` 直接渲染
- 删除旧的冲突 contextmenu 监听器

### panel.js — 左面板
- 删除题目：去掉"至少保留 1 个"限制
- 添加题目：空列支持直接创建新区域
- 新增题目默认值：`score: 12, subs: []`（无小问无下划线）
- 添加小问默认值：`blanks: []`（无下划线）
- 删除下划线：允许删到 0

### styles.css — 样式
- 语文作文方格纸样式（`.cn-grid-*`）
- 题内分割线样式（`.essay-cut-line`）
- 空栏占位样式（`.empty-col-slot`）
- 填涂框高度 4.5mm→3mm，行间距缩小
- 第一个空宽度修复：`flex: 0 0 auto`
- 页面标签间距压缩
- A/B 面间距修复（`margin: 2px 0 0`）

### seed_demo.py — 种子数据
- 新增 draft 状态考试（期末），3 科，用于答题卡编辑测试

## 未解决 / 需继续的问题

### 1. 逐科目 TQL 对齐（用户最新要求）
用户要求每个科目的编辑器排版对照 TQL 模板逐一优化。TQL 文件在 `D:\试卷数据\YueXiaoEr\Scanner\Templetes\`，通过 `tql_to_editor_layout()` 转换。目前数据层面的布局已接近 TQL，但视觉效果需要用户逐科目确认。

### 2. 添加小问一次添加多个（可能残留）
用户反馈"删 3 个再添加会一次加 3 个"。已修复 interact.js 的 `stopImmediatePropagation`，但未经用户实际验证。

### 3. 语文 A-C2 堆积 11 个 region
语文布局 col 2 合并了原 col 2（4 个）+ col 3（7 个）= 11 个 essay region。TQL 原始就是这样（col 2 有 4 个，col 3 有 7 个），合并后显示空间紧张。可能需要按 heightRatio 等比缩放。

### 4. 所有改动未 commit
13 个文件的改动全部在工作区，需要先让用户确认功能正确后 commit。

## 约束与偏好

- **这是 T1 级别的 UI 攻关任务**，不需要走 T3/T4 流程，无 design/plan 文档
- **用户是非专业开发者**，对 UI 要求直觉化——"顶格""不浪费空间""和 TQL 一样"
- **选择题排列铁律**：所有学科统一 16 列固定间距、左对齐
- **纠正后必须先停下来诊断**，不能急于改代码（用户多次强调）
- **禁止完成声明**直到用户在浏览器确认
- **视觉验证只能由用户做**，Claude 无法替代

## 关键文件速查

| 文件 | 说明 |
|------|------|
| `C:\Users\Administrator\edu-cloud\frontend\src\components\CardEditor.vue` | Vue 封装层，布局加载/修正/缩放 |
| `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\render.js` | 渲染引擎，A3 分栏/方格纸/分割线 |
| `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\model.js` | 布局数据模型，createDefaultLayout |
| `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\panel.js` | 左面板交互，题目增删 |
| `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\interact.js` | 预览区交互，右键菜单/拖拽/选中 |
| `C:\Users\Administrator\edu-cloud\frontend\public\card-editor\styles.css` | 样式 |
| `C:\Users\Administrator\edu-cloud\frontend\src\pages\ExamDetailPage.vue` | 入口页，科目管理 |
| `C:\Users\Administrator\edu-cloud\src\edu_cloud\data\seed_demo.py` | 种子数据 |
| `C:\Users\Administrator\edu-cloud\src\editor_layouts\` | 已保存的编辑器布局 JSON（7 个） |
| `D:\试卷数据\YueXiaoEr\Scanner\Templetes\` | TQL 模板文件（参考排版） |
| `C:\Users\Administrator\edu-cloud\src\edu_cloud\modules\card\subject_defaults.py` | TQL→编辑器布局转换 |

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-02 08:35:03
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-02-card-editor-handoff.md 了解上下文。

继续答题卡编辑器攻关。上轮完成了大量改动（13 文件，均未 commit），核心待办：

1. **逐科目 TQL 对齐**：用户要求每个科目的编辑器排版对照 TQL 模板优化。先看用户指定的科目，git diff 了解当前改动，然后听用户指令。

2. **用户反馈的残留 bug**：添加小问可能一次添加多个，需验证。

3. **所有改动未 commit**：用户确认后统一 commit。

先 git diff --stat 查看当前改动状态，等用户指令。
```
