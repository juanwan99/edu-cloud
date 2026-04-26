[edu-cloud] GPT Reviewer | 2026-03-18 18:58:47

## Plan Review: edu-cloud P1 联考 MVP

结论: **9 findings（3 HIGH code-bug 需修复，4 design-concern Planner 处置，1 LOW suggestion）**

### Finding 清单

| ID | Severity | Category | 描述 | Planner 处置 |
|----|----------|----------|------|-------------|
| F001 | HIGH | code-bug | 中间件 `except Exception` 会吞掉 Service 异常，异常处理器无法生效 | **接受** — Task 1 补充中间件重构 |
| F002 | HIGH | code-bug | `district_admin` 缺少 `MANAGE_SCHOOLS` 权限，与设计文档矛盾 | **接受** — Task 2 补充 permissions.py 修改 |
| F003 | HIGH | code-bug | 模板下载单 URL 无法同时交付 skeleton+PDF，exam-ai 落库目标不明确 | **接受** — 改为 zip 包下载 |
| F004 | HIGH | design-concern | JointExamScore 删除无回滚策略 | **不阻塞** — MVP 无生产数据，直接替换合理；记入 design.md §待处置 |
| F005 | MED | code-bug | get_student_detail 缺少各科排名位次字段 | **接受** — Task 9 补充 rank 计算 |
| F006 | MED | design-concern | GradingResult 实际是 AIGradingResult，Task 10 grep 目标错误 | **接受** — 修正为 AIGradingResult |
| F007 | MED | design-concern | 非参与校异常类型不一致（NotFoundError vs 403） | **接受** — 统一为 PermissionDeniedError → 403 |
| F008 | MED | design-concern | Alembic/Dockerfile 无独立 Task；Task 11 缺 Testable Slices | **接受** — 补 Task 0 基础设施 |
| F009 | LOW | suggestion | Task 8 粒度过大，建议拆分 | **记录但不拆分** — 执行时 Executor 可按 sync.py 分步 commit |
