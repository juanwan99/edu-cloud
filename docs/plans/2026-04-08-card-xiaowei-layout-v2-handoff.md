---
type: handoff
created: 2026-04-08 10:33:04
project_dir: C:\Users\Administrator\edu-cloud
design: null
plan: null
---

# 小微排版引擎 v2 — 交接卡

## 当前状态

**排版引擎 v2 重构已完成代码改动，尚未经用户视觉验收。** 需要新窗口启动后端、重新生成布局、让用户看效果并逐项调整。

### 已完成（本会话）

1. **答案解析器修复** — `answer_parser.py`：
   - 行首 ①②③ 创建新 sub（不再合并到上一个小问）
   - 去除答案尾部纯标点残留（`；` `。` 等人工分隔符）
   - label 字段透传到前端渲染

2. **标点规则实现** — `render.js`：
   - 单空无标点；多空中间分号、末尾句号
   - 续行（`continuation: true`）不参与标点判断，标点只加在每组独立空的末行

3. **排版算法重构** — `card_layout.py`：
   - 列分配从贪心改为全局最优分割（3-slot 枚举 + 容量惩罚）
   - 高度估算改用视觉行数（短空配对同行、续行合并）
   - 续行宽度升一档（30%→48%，48%→100%），孤字≤3字符合并到上一行
   - 输出 `targetHeight_mm`（定额高度）+ `heightRatio`（兼容）

4. **CSS 布局 v2 重写** — `styles.css`：
   - 4 层 flex-grow 链 → grid + 固定行高（`--essay-line-h: 9.5mm`）
   - `essay-item`: grid 布局，固定高度，不 flex-grow
   - `essay-body` / `essay-sub-block`: grid max-content，自然堆叠
   - `essay-row--first`: grid 分离标签列和内容列
   - `essay-row-content`: flex-start + gap，短空不再 space-between
   - `essay-line`: 固定高度 9.5mm（min 8mm, max 12mm），不参与纵向 grow

5. **渲染结构重构** — `render.js`：
   - `renderSingleBlank`: CSS 变量 `--blank-w` 代替 inline width
   - `renderSubsHTML`: essay-row / essay-row-content 结构，sub-block 不再 inline flex 加权
   - `renderEssayRegion`: 新增 `essay-body` 包裹层

### 未验收

- 用户尚未看到 v2 的视觉效果（后端刚重启，布局已重新生成）
- 可能需要微调 CSS 变量值（行高、间距）
- 其他科目（非生物）未测试

### 备份位置

重构前的文件备份在 `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\_backup_20260408\`（render.js + styles.css + card_layout.py）

### 关键文件

| 文件 | 改动 |
|------|------|
| `C:\Users\Administrator\edu-cloud\src\edu_cloud\ai\tools\card_layout.py` | 排版引擎核心（视觉行数 + 最优分割 + 定额高度） |
| `C:\Users\Administrator\edu-cloud\src\edu_cloud\modules\card\answer_parser.py` | 答案解析（①②③ 独立 sub + 标点清理） |
| `C:\Users\Administrator\edu-cloud\frontend\src\card-editor\render.js` | 渲染结构（essay-row/essay-row-content/essay-body） |
| `C:\Users\Administrator\edu-cloud\frontend\public\card-editor\styles.css` | CSS v2（grid 驱动，无纵向 flex-grow） |

### 物理常量（与 CSS 变量对齐）

```
后端: VISUAL_LINE_H=10mm, VISUAL_LINE_MAX=15mm, VISUAL_Q_GAP=5mm, SCORE_BONUS_PER_PT=0.5
CSS:  --essay-line-h=9.5mm, --essay-line-min-h=8mm, --essay-line-max-h=12mm
      --essay-row-gap=2.5mm, --essay-sub-gap=3mm, --essay-pair-gap=4mm
```

### 当前生物排版数据

```
Q17: col0, 6视觉行, target=125mm (col0可用156mm)
Q18: col1, 7视觉行, target=116mm (与Q19共享col1)
Q19: col1, 10视觉行, target=149mm
Q20: col2, 5视觉行, target=105mm (与Q21共享col2)
Q21: col2, 7视觉行, target=131mm
```

## 约束与偏好

**Tier: T2 流程**（排版优化，无架构变更）

- 用户是非开发者，需要直接看到可视化效果确认
- 后端启动：`cd C:\Users\Administrator\edu-cloud && python ~/.claude/scripts/serve.py python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 --reload`
- 前端已在运行：`http://localhost:5273`
- 登录用 `admin_principal_1 / 123456`（校长角色）
- 测试入口：`http://localhost:5273/exams/80f4fc02-bc73-40f5-9fb7-83de5b9bbd9c` → 可视化编辑 → 生物
- 测试答案文件：`D:\命题\2026一模\一模定稿\26年一模答案.docx`（已复制到 `C:\Users\Administrator\26年一模答案.docx`）
- CSS 在 `frontend/public/` 下，浏览器会缓存，需 Ctrl+Shift+R 强制刷新
- 点"小微排版"按钮上传答案文件可重新生成布局数据
- 用户标点规则：单空无标点，多空中间分号末尾句号（以小问为单位判断）
- 用户空宽度规则：按答案长度分配（≤8字→30%，9-20字→48%，>20字→100%）
- 用户短空布局规则：两个30%短空可同行排列，flex-start + gap，不用 space-between

## 启动 Prompt

```
[edu-cloud] 小微排版 v2 视觉验收 | {timestamp}
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-08-card-xiaowei-layout-v2-handoff.md 了解上下文。

任务：
1. 重启后端（端口 9000），确认服务正常
2. 让用户在浏览器查看生物排版效果（Ctrl+Shift+R 刷新）
3. 根据用户反馈微调排版参数（CSS 变量值、后端常量）
4. 关键文件：
   - C:\Users\Administrator\edu-cloud\src\edu_cloud\ai\tools\card_layout.py（排版引擎）
   - C:\Users\Administrator\edu-cloud\frontend\src\card-editor\render.js（前端渲染）
   - C:\Users\Administrator\edu-cloud\frontend\public\card-editor\styles.css（CSS 布局 v2）
```
