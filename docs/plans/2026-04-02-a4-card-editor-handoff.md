---
type: handoff
created: 2026-04-02 19:19:20
project_dir: C:\Users\Administrator\edu-cloud
---

# A4 双面答题卡布局修复 — 交接卡

## 背景

答题卡编辑器原本只支持 A3 展开布局。本会话尝试为英语、化学等 A4 双面科目添加支持，修改了后端 TQL 解析和前端渲染。后端数据生成已正确（WSL 内验证通过），但前端存在多个结构性 bug 导致 A4 布局无法正常工作。

GPT Codex 独立诊断确认了 5 个根因（threadId: `019d4de2-4a4a-7020-af4f-9d80e63c2a76`）。

## 本会话已完成的改动（均未 commit）

### 后端（正确，已验证）

| 文件 | 改动 | 状态 |
|------|------|------|
| `src/edu_cloud/modules/card/tpl_parser.py` | A4 双面检测：`page_width <= 2000 + has_page1 → paper_size="A4", is_a4_dual=True`，不做 x 坐标偏移 | ✅ 正确 |
| `src/edu_cloud/modules/card/subject_defaults.py` | `tql_to_editor_layout` A4 双面分支：每面独立 region，跨面续写标记 `continuation=True` | ✅ 正确 |
| `tests/test_services_exam/test_tpl_parser.py` | 测试更新：A4 双面断言 | ✅ 14 passed |

WSL 内验证结果：
```
英语: paper=A4, A面=[col0: 4 fixed, col1: 2 essays], B面=[col0: 2 essays(写作第一节-cont + 写作第二节)]
化学: paper=A4, A面=[col0: 4 fixed, col1: 2 essays], B面=[col0: 3 essays(16题-cont + 17题 + 18题)]
```

### 前端（有结构性问题，需要重做）

| 文件 | 改动 | 状态 |
|------|------|------|
| `frontend/src/card-editor/render.js` | 新增 `_renderA4` A/B 双面渲染 | ❌ 硬编码 HTML，不走数据驱动 |
| `frontend/src/card-editor/render.js` | 题内分割线按小问插入 + 续写标题"（续）" | ✅ 可保留 |
| `frontend/src/card-editor/render.js` | 小问 × 删除按钮 | ✅ 可保留 |
| `frontend/src/card-editor/interact.js` | AbortController 替代 initialized 防 HMR 重复监听 | ✅ 可保留 |
| `frontend/src/card-editor/interact.js` | 分割线拖拽、小问删除按钮点击 | ✅ 可保留 |
| `frontend/src/components/CardEditor.vue` | `layoutFromServer` 防覆盖 + `onAnyChange(userEdit)` 分离保存 | ⚠️ 方向正确但不彻底 |
| `frontend/public/card-editor/styles.css` | 分割线 CSS 手柄 + 小问/分割线 × 按钮样式 | ✅ 可保留 |

### 已删除的坏数据

英语和化学的保存布局文件已手动删除（`src/editor_layouts/` 下），但自动保存机制可能再次创建。

## GPT 诊断的 5 个根因（必须全部修复）

### Bug 1（高）：API 优先返回历史坏布局
- **位置**: `src/edu_cloud/modules/card/router.py:61-89`
- **问题**: 只要存在旧保存文件就直接返回，绕过正确的 TQL 默认布局。之前错误保存的 A3 布局会被反复加载
- **修复方向**: `get_editor_layout()` 应拿 fresh default 做结构校验——若 default 是 A4 而 saved 是 A3，或 B 面 region 数少于 default，则丢弃 saved 的结构，只合并样式类 config/choices

### Bug 2（高）：paperSize 真值混乱
- **位置**: `CardEditor.vue:91-96`（select 默认 A3）、`CardEditor.vue:229-236`（getValues 从 DOM 读）、`render.js:367`（分支判断）
- **问题**: `layout.paper`、`config.paperSize`、DOM `<select>` 三个来源互相覆盖
- **修复方向**: 纸型单一真值改为 `layout.paper`；加载时强制 `layout.config.paperSize = layout.paper`；`renderFromLayout()` 优先看 `layout.paper`；去掉模板里硬编码的 `selected A3`

### Bug 3（高）：`_renderA4()` 不走数据驱动
- **位置**: `frontend/src/card-editor/render.js:505-591`
- **问题**: A4 分支硬编码了固定区 HTML，没有像 A3 那样从 `sides/columns/regions` 结构化渲染，绕开了列容器、角标、边框体系
- **修复方向**: 删除硬编码 A4 页面，A4 也从 `sides/columns/regions` 数据驱动渲染。A 面固定区来自 `fixed` region，每面逐列逐 region 渲染

### Bug 4（中高）：fallback 硬编码 A3
- **位置**: `subject_defaults.py:553`（`"paper": "A3"`）、`model.js:38`（`config.paperSize || 'A3'`）
- **问题**: `_fallback_layout` 无条件返回 A3 + 3 栏。`createDefaultLayout` 也默认 A3
- **修复方向**: fallback 也要支持 A4 双面；英语、化学即便 fallback 也保留 `A4 + A/B sides` 结构

### Bug 5（中）：非数字 slot_id 解析为 qno=0
- **位置**: `subject_defaults.py:366-370`
- **问题**: 写作题 `Q_写作第一节` 的 slot_id 解析为 `qno=0`，显示为"0.（本小题满分 25 分）"
- **修复方向**: 对非数字 slot_id 保留 `displayLabel`，不强转为 0

## 本会话另外完成的编辑器改进（可保留）

1. **题内分割线**：以小问为单位的可拖拽分割线（`afterSub` 定位 + snap 到小问间隙）
2. **小问 × 删除按钮**：hover 时右上角显示，左键点击整体删除小问
3. **HMR 安全**：AbortController 管理 document 事件监听器生命周期
4. **自动保存分离**：`onAnyChange(userEdit)` 参数区分用户编辑和系统事件

## 约束与偏好

- **T3 流程**：5 个结构性 bug，跨后端 API + 前端渲染 + 数据流
- **不打补丁**：用户明确要求定位根本原因解决，拒绝防御性 workaround
- **A3 科目不能受影响**：数学、语文、物理等 A3 科目的布局必须保持不变
- **后端服务在 WSL 内运行**：`python3 -m uvicorn`，文件变更可能不触发 `--reload`，需手动重启确认
- **WSL 内用 `python3` 不是 `python`**（Windows 本地用 `python`）
- **保存的布局文件**在 `src/editor_layouts/`，按 `{school_id}_{subject_id}.json` 命名
- **用户非常沮丧**：之前反复修复失败，不要走弯路，按 GPT 诊断的优先级逐个修

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-02 19:19:20
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-02-a4-card-editor-handoff.md 了解上下文。

任务：修复 A4 双面答题卡编辑器的 5 个结构性 bug（GPT Codex 已诊断）。按优先级执行：

1. Bug 1: router.py — API 返回历史坏布局时做结构校验
2. Bug 2: CardEditor.vue + render.js — paperSize 单一真值收敛到 layout.paper
3. Bug 3: render.js — 重写 _renderA4()，数据驱动渲染（复用 A3 的 renderA3Col/renderColumnRegions 体系）
4. Bug 4: subject_defaults.py + model.js — fallback 支持 A4
5. Bug 5: subject_defaults.py — 非数字 slot_id 保留 displayLabel

每个 bug 修完后跑 `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_tpl_parser.py -x -q` 确认不回归。全部完成后跑完整测试套件。

注意：后端在 WSL 内运行，代码改完后需手动重启服务器验证前端效果。已有的编辑器改进（分割线拖拽、小问删除、AbortController、onAnyChange 分离）保留不动。

使用 executing-plans skill。完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
