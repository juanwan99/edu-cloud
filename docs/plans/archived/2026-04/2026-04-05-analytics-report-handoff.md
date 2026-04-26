---
type: handoff
created: 2026-04-05 17:57:53
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-analytics-report-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-analytics-report-plan.md
---

## 约束与偏好

**T3 流程，Gate 1 (Plan Review) 已通过（3 轮）。** Gate 2 (Code Review) pending。

1. **GPT 审查要点（3 轮积累）：** 权限校验是本 plan 最大风险面。特别注意：
   - metrics 角色白名单必须覆盖 metrics=None 场景（AR2-R2-01 教训）
   - student_trend 必须显式校验学生可见性（班级 + guardian）
   - grade_trend 有角色白名单，class_trend 拒绝家长
   - subject_code 口径必须全链路一致（快照路径 class_avg/grade_avg 不能混用总分口径）

2. **快照优先策略：** 趋势函数优先读 W1 预计算表（ExamAnalysisSnapshot / ClassExamReport / StudentExamSnapshot），仅在无快照时 fallback 实时聚合。注意 ClassExamReport 没有 subject_code 字段，有 subject_code 时应走 fallback。

3. **分数段唯一性：** PostgreSQL 用 partial unique index（非普通 UNIQUE），SQLite 测试靠 service 层 upsert 保证。

4. **PDF 导出：** 必须串起 Studio transition（draft→reviewed→executed），不能只 create_document。AI 工具和 HTTP 路由都要走这条路径。

5. **is_active 已移除：** 分数段配置改为硬删，无软删。

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-05 17:57:53
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-analytics-report-handoff.md，按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-05-analytics-report-plan.md 全部 13 Tasks 执行。使用 subagent-driven-development skill。完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
