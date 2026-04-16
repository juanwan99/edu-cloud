---
type: handoff
created: 2026-04-09 11:35:07
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-scan-pipeline-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-scan-pipeline-plan.md
---

# 试卷全链路打通 — 交接卡

## 约束与偏好

**Tier: T3 流程**（跨模块新增路由层 + 修改 publish 逻辑）

- paper-seg 代码零改动——所有兼容逻辑在 edu-cloud 侧实现
- 兼容登录端点忽略 `school_code` 字段，直接走 edu-cloud 用户认证
- publish 端点需允许 `scanning` 状态重新发布（支持多科目独立发布）
- exam.status 仅在 `draft` 时自动转 `scanning`，已经是 `scanning` 则保持
- 模板响应格式必须包含 `image_size: {width, height}`（而非 `image_width/image_height`），这是 paper-seg 客户端期望的格式
- 切图上传的 Multipart 字段名必须精确匹配：`exam_id/subject_id/student_id/question_id/image`
- 选择题上传自动判分：对比 Question.correct_answer，正确给满分，错误给 0 分

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-09 11:35:07
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-scan-pipeline-handoff.md，按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-scan-pipeline-plan.md Task 1-6 执行。使用 executing-plans skill。完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
