# AI Grading B-End Code Review Report — Batch 1

**Topic:** 2026-04-22-ai-grading-b-end
**Reviewer:** GPT-5.4 via Codex MCP
**Commit range:** 7388d88..22ca92d (R1) → +0e4cd5b (R1 fix)
**Date:** 2026-04-23

## 变更理解

本批次实现 AI 阅卷 B 端改造 9 个 Task：Question 模型扩展 4 字段 + GradingTask question_id → 权限对齐 → Content API → Rubric AI 生成 → 题目级 GradingTask Router/Worker → Prompt 逐空明细升级 → dispatch/status questions 扩展 → AiGradingPage 前端 → 测试。共 28 文件 +2472/-94 行。

## 对抗性审查

GPT 独立读取全部 diff 和修改文件，按 4 Phase 结构化审查。Phase 0 验证 ORC-001~005 全部保持。Phase 1 发现测试 patch 掉核心逻辑导致空转。Phase 2 发现前后端契约错配、科目级重跑缺清理、AI rubric 绕过校验 3 个实质缺陷。Phase 3 识别集成级测试缺口。

## R1 Result: FAIL (3 HIGH + 2 MED)

## 发现清单

| ID | Severity | Type | Description | Status |
|----|----------|------|-------------|--------|
| F001 | HIGH | defect_fix | AiGradingPage 前后端契约错配：缺 subject_id、轮询字段名错、content 未加载 | resolved-correct (commit 0e4cd5b) |
| F002 | HIGH | defect_fix | 科目级重跑缺 ai_pending/ai_done 清理，撞 UniqueConstraint | resolved-correct (commit 0e4cd5b) |
| F003 | MED | defect_fix | AI rubric generate 绕过 _validate_criteria，信任客户端 max_score | resolved-correct (commit 0e4cd5b) |
| F004 | HIGH | test_gap | Worker details 落库测试 patch 核心逻辑，删实现测试仍过 | acknowledged — plan test_debt 已声明 Worker E2E 推迟到 v2 |
| F005 | MED | test_gap | 前端测试只覆盖静态渲染，不覆盖 AiGradingPage 交互契约 | acknowledged — plan test_debt 已声明前端 E2E 需手动验证 |

### R1 Fix Summary (commit 0e4cd5b)

1. **F001 fix:** AiGradingPage createTask 加 subject_id；轮询字段改 completed/total/status；选题后 getQuestion 加载完整 content
2. **F002 fix:** subject-level 分支添加 regrade 清理（与 question-level 对称）
3. **F003 fix:** generate endpoint 用 question.max_score 替代 req.max_score，LLM 返回后调 _validate_criteria

### R2 条件判定

R1 FAIL → 检查 R2 条件：
- 跨模块重构（exam/grading/worker/frontend 4 模块）满足
- R2 允许

### Raw Output

- R1: `docs/plans/.codex-raw-code-r1-20260423.log` (SHA256: `1aa26269eb1cc57f`)
