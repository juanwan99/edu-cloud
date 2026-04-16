---
type: handoff
created: 2026-04-12 18:03:37
project_dir: C:\Users\Administrator\edu-cloud
design: null
plan: null
parent_handoff: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-08-card-xiaowei-layout-v2-handoff.md
---

# 小微排版 v2 视觉验收 — 交接卡

> **前置交接卡**: `2026-04-08-card-xiaowei-layout-v2-handoff.md`（完整的 v2 改动说明、物理常量、CSS 变量对齐表）。本文件只写增量状态变化。

## Tier 声明

**T2 流程**（视觉验收 + commit，无架构变更）

## 当前状态（2026-04-12 更新）

**WIP 代码在 git stash 里**，master 工作区干净。

```bash
git stash list
# stash@{0}: On master: card-v2-xiaowei-layout-wip-pending-visual-review
```

**恢复命令**: `cd C:\Users\Administrator\edu-cloud && git stash pop stash@{0}`

恢复后 5 个文件变为 unstaged modified：
- `frontend/public/card-editor/styles.css` (142 行) — CSS grid v2
- `frontend/src/card-editor/render.js` (84 行) — essay-row 渲染结构 + data-side
- `src/edu_cloud/ai/tools/card_layout.py` (264 行) — 视觉行数 + 最优分割 + 续行升档
- `src/edu_cloud/modules/card/answer_parser.py` (16 行) — ①②③ 独立 sub + 标点清理
- `src/edu_cloud/modules/card/answer_standardizer.py` (4 行) — LLM_PROXY_URL→LLM_API_URL 修正

## 自上次交接卡以来的变化

1. **F003 已合并到 master** (`1709c8c`)：render.js 现在有 `data-side="A"/"B"` 属性（F003 T1 加入），card v2 WIP 的 render.js 改动基于 F003 合并后的版本，不会冲突
2. **WIP 从工作区移到 stash**：本会话为执行 F003 T4 做了 stash → worktree merge → stash pop → 再 stash 保存
3. **answer_standardizer.py 新增改动**：`LLM_PROXY_URL` → `LLM_API_URL` + `/v1/` 路径修正（配置字段名变更，与 llm-proxy 当前接口对齐）

## 约束与偏好

- 用户是非开发者，需直接看可视化效果确认
- 后端已在运行（端口 9000），前端需重启（上次启动在 5274）
- 登录：`admin_principal_1 / 123456`（校长角色）
- 测试入口：考试管理 → 选一个 draft 考试 → 可视化编辑 → 选科目 → 点"小微排版"上传答案文件
- 测试答案文件：`C:\Users\Administrator\26年一模答案.docx`
- CSS 在 `frontend/public/` 下，浏览器需 Ctrl+Shift+R 强制刷新
- 验收维度（前置交接卡 §用户规则）：
  - 单空无标点，多空中间分号末尾句号
  - 空宽度按答案长度分配（≤8字→30%，9-20字→48%，>20字→100%）
  - 两个 30% 短空可同行排列
  - 续行升一档宽度
  - 孤字（≤3字符末行）合并到上一行

## 启动 Prompt

```
[edu-cloud] 小微排版 v2 视觉验收 | 2026-04-12 18:03:37
项目: C:\Users\Administrator\edu-cloud
读取交接卡: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-card-v2-visual-review-handoff.md
读取前置交接卡: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-08-card-xiaowei-layout-v2-handoff.md

步骤:
1. git stash pop stash@{0} 恢复 card v2 WIP（5 文件）
2. 启动前端: cd C:\Users\Administrator\edu-cloud\frontend && python ~/.claude/scripts/serve.py "C:/Program Files/nodejs/npm.cmd" run dev
3. 确认后端 9000 端口正常: curl http://localhost:9000/api/v1/health
4. 让用户在浏览器操作：
   - 登录 admin_principal_1/123456
   - 进入考试管理 → draft 考试 → 可视化编辑 → 选科目
   - 点"小微排版" → 上传 C:\Users\Administrator\26年一模答案.docx
   - Ctrl+Shift+R 刷新查看效果
5. 用户反馈后微调参数（CSS 变量/后端常量）
6. 验收通过后 commit card v2 WIP

关键文件:
- C:\Users\Administrator\edu-cloud\src\edu_cloud\ai\tools\card_layout.py（排版引擎）
- C:\Users\Administrator\edu-cloud\frontend\src\card-editor\render.js（前端渲染）
- C:\Users\Administrator\edu-cloud\frontend\public\card-editor\styles.css（CSS v2）
- C:\Users\Administrator\edu-cloud\src\edu_cloud\modules\card\answer_parser.py（答案解析）
- C:\Users\Administrator\edu-cloud\src\edu_cloud\modules\card\answer_standardizer.py（LLM 配置修正）
```
