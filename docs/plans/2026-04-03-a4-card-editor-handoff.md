---
type: handoff
created: 2026-04-03 21:11:52
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-a4-card-editor-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-a4-card-editor-plan.md
---

# A4 双面答题卡编辑器 — 实现完成交接卡

## 当前状态

**Plan Task 1-8 已全部执行，GPT Code Review 3 轮 PASS，Gate 1+2 均 pass，代码已推送 GitHub。**

Commits: `5e4f373..f604f68`（含追加修复），design.md 已标记 `[实现完成]`。

## 约束与偏好

**Tier: T3 流程**

### 执行后用户视觉验收发现并修复的问题

| 问题 | 根因 | 修复 commit | 教训 |
|------|------|------------|------|
| 选择题竖排劣化（所有 TQL 科目选择题排版乱） | Task 4 引入 `hasTqlCoords` 分支，编辑器选择题不应区分 TQL | `6b81465` revert | 编辑器选择题始终走 flatMap 横排，TQL 坐标仅用于 PDF 打印/扫描 |
| 英语选择题不紧凑 | flatMap 全局 maxOpts=7 拉高所有行 | `f8ee5b3`→`f604f68` | 改为每行自适应 batchMax |
| PDF A/B 面不分页 | `batchExportPdf` 导出 CSS 缺 `display:block!important`，styles.css `body{display:flex}` 导致水平并排 | `f604f68` | 两条导出路径 CSS 必须一致 |
| 编辑器 UI 泄漏到 PDF | `.empty-col-slot`（"右键添加题目"）未移除 | `1e39202` | 导出 DOM 清理列表需完整 |

### 关键铁律（后续开发必须遵守）

1. **编辑器选择题渲染始终走 flatMap 横排**，TQL 坐标不在编辑器中使用
2. **styles.css 的 `body{display:flex}` 是编辑器布局用**，导出 CSS 必须 `display:block!important`
3. **getCleanHTML 和 batchExportPdf 的清理逻辑必须同步**
4. **视觉类变更必须浏览器验证**，不能只靠测试 PASS

### 待处置（F004 design-concern）

GPT 审查指出 plan 缺 Contract Pack 段落。不阻塞，后续 T3/T4 plan 应补齐。

### 测试覆盖

- 后端 43 tests（tpl_parser 12 + cards 20 + 其余）
- 前端 4 Vitest（A4/A3 DOM 结构回归）
- 回归命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_tpl_parser.py tests/test_api_exam/test_cards.py -x -q`
- 前端命令: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`

## 启动 Prompt

```
[edu-cloud] 收尾确认 | {timestamp}
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-a4-card-editor-handoff.md 了解上下文。
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-a4-card-editor-design.md 确认设计。

A4 双面答题卡编辑器重构已完成（Task 1-8 + GPT 3 轮 PASS + 4 项追加修复）。

确认事项:
1. 全量测试: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_tpl_parser.py tests/test_api_exam/test_cards.py -x -q` + `cd frontend && npx vitest run`
2. gates.json plan_review + code_review 均 pass
3. design.md 已标记 [实现完成]
4. 代码已推送 GitHub

如有新发现的问题需要修复，按 T2 流程处理。完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
