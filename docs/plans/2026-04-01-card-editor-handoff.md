---
type: handoff
created: 2026-04-01 20:06:20
project_dir: C:\Users\Administrator\edu-cloud
---

# 答题卡编辑器攻关 — 交接卡

## 背景

答题卡编辑器从 exam-ai 迁入 edu-cloud，代码 100% 一致（74959 行），但用户反馈"完全没法用"。本会话进行了端到端排查和修复。

## 已完成的改动（均未 commit）

### 1. 种子数据：新增 draft 状态考试
- **文件**: `C:\Users\Administrator\edu-cloud\src\edu_cloud\data\seed_demo.py`
- **改动**: 新增 `_seed_draft_exam()` 函数，创建"2026年春季期末考试"（status=draft），3 科（语/数/英），各有完整题目定义
- **原因**: 原种子数据只有 completed 状态考试，ExamDetailPage.vue:206 的 `:readonly="exam?.status !== 'draft'"` 导致编辑器全部 disabled
- **验证**: 1037 tests 全部通过

### 2. CSS：panel-toggle 定位修复
- **文件**: `C:\Users\Administrator\edu-cloud\frontend\public\card-editor\styles.css`
- **改动**: `.panel-toggle` 从 `position: fixed` 改为 `position: absolute`
- **原因**: fixed 定位相对视口，但编辑器左侧有 220px AppShell 侧边栏，导致按钮覆盖面板内容

### 3. CSS：面板宽度压缩
- **文件**: `C:\Users\Administrator\edu-cloud\frontend\public\card-editor\styles.css` + `CardEditor.vue`
- **改动**: 面板 340px→260px，padding 16px→12px，toggle left 同步调整
- **原因**: 用户要求给预览区更多空间

### 4. CSS：预览区顶格
- **文件**: `C:\Users\Administrator\edu-cloud\frontend\public\card-editor\styles.css` + `CardEditor.vue`
- **改动**: 
  - `.preview-wrap` padding/gap 归零，align-items 改为 flex-start
  - `.page` transform-origin 从 `top center` 改为 `top left`，移除 box-shadow/border-radius
  - `.page-label` 压缩
  - `.view-toggle` 压缩
- **原因**: 用户要求预览区完全顶格，不浪费空间（参考 exam-ai 的布局）

### 5. 选择题面板→预览同步修复
- **文件**: `C:\Users\Administrator\edu-cloud\frontend\src\components\CardEditor.vue`
- **改动**: `getValues()` 中新增 `_choices` → `choiceGroups` 同步逻辑（将扁平的 _choices 数组重建为分组格式）
- **原因**: 面板修改选择题后，`onAnyChange()` 不会更新 `config.choiceGroups`，导致 `buildChoiceGroupsHTML(config)` 读到旧数据，预览不更新

### 6. 选择题渲染：统一网格布局
- **文件**: `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\render.js`
- **改动**:
  - 删除 TQL 坐标分列渲染分支（line 110-151），所有情况走统一网格
  - 固定 perRow=16 列，列宽 `1fr`，不足的用空单元格填充
  - 不同选项数的题合并到同一网格，选项行数取最大值
  - 单题组不再走纵向布局（`vertical` 条件加 `qs.length >= 4`）
- **原因**: 用户要求所有学科选择题统一排列——固定 16 列间距、左对齐，不按 TQL 坐标分列

### 7. 填涂框高度减小
- **文件**: `C:\Users\Administrator\edu-cloud\frontend\public\card-editor\styles.css`
- **改动**: `.bracket` height 4.5mm→3mm，行间距 1.5mm→0.8mm
- **原因**: 用户要求选择题区域更紧凑

### 8. "请勿在此区域答题" 移除默认输出
- **文件**: `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\render.js`
- **改动**: 删除 A3 模板中 `<div class="no-answer-zone">` 的默认输出
- **保留**: CSS 样式类保留（供手动添加使用），双击粘贴文字功能保留
- **原因**: 用户要求默认不显示，但可手动添加

### 9. 左栏渲染补丁（⚠️ 用户认为逻辑不对）
- **文件**: `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\render.js`
- **改动**: 在 leftCol 末尾追加 `renderColumnRegions(sideA.columns[0] 的非 fixed regions)`
- **原因**: 选择题后面的填空/解答题（col 0 的非 fixed regions）原本不被渲染
- **⚠️ 用户反馈**: 用户说"这个逻辑不对"，我没有完全理解用户的意思就急于辩护。**这个问题未解决。**

## 未解决的核心问题

### A3 左栏架构问题（用户纠正，未完成诊断）

**现状**: A3 答题卡 A 面有三栏。左栏（col 0）被硬编码为"纯固定区域"（标题+信息+注意事项+选择题+填空题），用 `leftCol` 字符串拼接。中栏（col 1）和右栏（col 2）用 `renderColumnRegions()` 动态渲染题目。

**问题**: 选择题后面紧接的解答题/填空题不显示。我的补丁是在 leftCol 后面追加 `renderColumnRegions(col0 非 fixed regions)`，但用户说"逻辑不对"。

**可能的正确方向**（需要和用户确认）:
1. model.js 的 `createDefaultLayout` 不应该把 fill/essay regions 放在 col 0——应该全部分配到 col 1/2 和 B 面
2. 或者左栏的固定区域下方应该自然地成为可用答题空间，和其他栏一样
3. 需要先问清楚用户的期望：左栏下方是留白还是放题目

**用户原话**: "原来的非答题区域为什么不能显示题目？这个逻辑不对。你觉得呢"

### 测试数据污染

Playwright 测试过程中修改了语文科目的 `_choices` 数据（题号改为 99、选项数改为 3/5/7 等），这些数据被自动保存到了服务器。其他科目也可能受影响。新会话需要清理或重置编辑器布局数据。

## 约束与偏好

- **用户是非专业开发者**，依靠元能力体系保障质量
- **答题卡编辑器从 exam-ai 迁入**，两边代码几乎一致，差异仅为 API 前缀（`/api/` vs `/api/v1/`）和认证对象格式
- **用户对 UI 要求直觉化**——"顶格""不浪费空间""和 exam-ai 一样"是核心诉求
- **选择题排列铁律**: 所有学科统一 16 列固定间距、左对齐，不按 TQL 坐标分列
- **纠正后必须先停下来诊断**，不能急于改代码

## 关键文件速查

| 文件 | 说明 |
|------|------|
| `C:\Users\Administrator\edu-cloud\frontend\src\components\CardEditor.vue` | Vue 封装层，674 行 |
| `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\render.js` | 渲染引擎，核心改动最多 |
| `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\model.js` | 布局数据模型 |
| `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\panel.js` | 左面板交互 |
| `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\interact.js` | 预览区交互 |
| `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\export.js` | 导出 |
| `C:\Users\Administrator\edu-cloud\frontend\public\card-editor\styles.css` | 样式 |
| `C:\Users\Administrator\edu-cloud\frontend\src\pages\ExamDetailPage.vue` | 入口页 |
| `C:\Users\Administrator\edu-cloud\src\edu_cloud\data\seed_demo.py` | 种子数据 |

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-01 20:06:20
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-01-card-editor-handoff.md 了解上下文。

继续答题卡编辑器攻关。上个会话完成了 9 项改动（均未 commit），核心未解决问题：

1. **A3 左栏架构问题**：用户说"非答题区域为什么不能显示题目，逻辑不对"。
   上个会话的补丁是在 leftCol 后追加 renderColumnRegions(col0 非 fixed regions)，但用户认为不对。
   需要先和用户确认期望，再决定正确方案。

2. **测试数据污染**：Playwright 测试修改了多个科目的 _choices 数据，需要清理。

先 git diff 查看当前所有改动，理解上下文后向用户确认架构问题的正确方向。
```
