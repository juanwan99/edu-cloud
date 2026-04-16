---
type: handoff
created: 2026-04-07 21:11:12
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-a4-card-editor-design.md
plan: null
---

# 小微排版引擎优化 — 交接卡

## 当前状态

**commit 93fa983 已提交，排版引擎核心重写完成，7 文件 381 行新增。**

### 已完成

1. **PDF 导出 500 修复** — `html_export.py` 改为 sync API + ThreadPoolExecutor，修复 Windows uvicorn --reload 的 SelectorEventLoop 不支持 subprocess 问题

2. **排版引擎重写** — `card_layout.py` 的 `calculate_layout()` 从数据填充器改为约束装箱算法：
   - 计算每题物理高度（mm）→ 顺序贪心装箱到 3 列（col0 剩余 + col1 + col2）
   - 硬约束：不溢出列高、题目保持顺序、col0 利用选择题下方空间
   - per-column heightRatio 归一化
   - `_apply_to_regions()` 重建 regions 结构（不再填充旧模板）
   - 答案超出一行自动加续行（`_make_blanks_for_answer()`）

3. **前端 flex 链路** — essay-item → essay-sub-block → essay-blanks → essay-line 全链路 flex column 布局：
   - sub-block 的 flex 按空行数量加权（`render.js` 行内 style `flex:{blanks.length}`）
   - essay-line 用 `flex: 1 1 0` + `min-height: 7.5mm` 均匀拉伸

4. **交互优化**：
   - 分割线拖拽 snap 到行网格（累积整行才触发，`interact.js`）
   - 横线宽度拖拽三档吸附 30%/48%/100%（`interact.js`）
   - 多空分号分隔符紧接横线末端（`render.js` + `styles.css`）
   - 标准答案虚化预览（浅红色 10.5pt），导出 PDF 时自动移除（`export.js`）
   - CSS 缓存破坏（`CardEditor.vue` 用 `Date.now()` 时间戳）

### 已验证的生物排版结果

```
A面 col0: 选择题(16道) + Q17(11分, 4小问6空) → 95/156mm
A面 col1: Q18(11分, 1小问9空) + Q19(12分, 4小问11空) → 230/243mm
A面 col2: Q20(12分, 3小问8空) + Q21(14分, 3小问10空) → 222/243mm
B面: 空
```

### 关键文件

| 文件 | 改动 |
|------|------|
| `src/edu_cloud/ai/tools/card_layout.py` | 排版引擎核心（装箱算法 + 高度估算 + regions 重建） |
| `src/edu_cloud/modules/card/html_export.py` | PDF 导出（sync API + ProactorEventLoop 修复） |
| `frontend/src/card-editor/render.js` | sub-block flex 加权 + 分号分隔 + 答案预览 |
| `frontend/src/card-editor/interact.js` | 行 snap + 三档宽度 |
| `frontend/public/card-editor/styles.css` | flex 链路 + 分号/答案样式 |
| `frontend/src/card-editor/export.js` | 导出时移除答案元素 |
| `frontend/src/components/CardEditor.vue` | CSS 缓存破坏 |

### 物理常量（与前端 CSS 对齐）

```python
COL_TOTAL_H = 270    # 列可用高度 mm
LINE_H = 8           # 每行高度 mm
HEADER_H = 10        # 题号行高度 mm
SAFETY_MARGIN = 0.9  # 防溢出安全系数
```

## 约束与偏好

**Tier: T2 流程**

- 用户是非开发者，需要直接看到可视化效果
- 后端启动：`cd C:\Users\Administrator\edu-cloud && python ~/.claude/scripts/serve.py python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 --reload`
- 前端已在运行：`http://localhost:5273`
- 登录用 `admin_principal_1 / 123456`（校长角色，platform_admin 看不到考试数据）
- 测试考试：`http://localhost:5273/exams/80f4fc02-bc73-40f5-9fb7-83de5b9bbd9c` → 可视化编辑 → 生物
- 测试答案文件：`D:\命题\2026一模\一模定稿\26年一模答案.docx`
- 排版数据文件：`src/editor_layouts/31c17116..._e1cc167b....json`
- CSS 在 `frontend/public/` 下，浏览器会缓存，需 Ctrl+Shift+R 强制刷新
- 用户要求：空间填满不留空白、不溢出边界、空行间距充足（AI 阅卷识别）、分号分隔多空

## 启动 Prompt

```
[edu-cloud] 小微排版继续优化 | {timestamp}
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-07-card-xiaowei-layout-handoff.md 了解上下文。

任务：
1. 重启后端（端口 9000），确认服务正常
2. 用户会给出进一步的排版优化需求，按需调整
3. 关键文件：C:\Users\Administrator\edu-cloud\src\edu_cloud\ai\tools\card_layout.py（排版引擎）和 C:\Users\Administrator\edu-cloud\frontend\src\card-editor\render.js（前端渲染）
```
