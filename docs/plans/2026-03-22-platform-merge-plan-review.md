# Plan Review Report — exam-ai → edu-cloud 合并

> GPT 5.4 Codex 独立审查 + Planner 处置
> 审查时间: 2026-03-22

## R1 结果: FAIL（6 HIGH + 4 MED）

| ID | Severity | Category | Finding | 处置 |
|----|---------|----------|---------|------|
| PMR-001 | HIGH | code-bug | ROLE_TOOL_CATEGORIES 在 agent.py 不在 permissions.py，计划指错文件 | **已修复** — Task 17 目标改为 ai/agent.py |
| PMR-002 | HIGH | design-concern | ExamResult 设计文档说删、计划说保留，矛盾 | **已修复** — 设计文档同步更新为"保留为聚合视图" + ADR |
| PMR-003 | HIGH | design-concern | Alembic "新 initial migration" 对已有迁移处理不清 | **已修复** — 明确"无生产数据 → 删旧建新"，标注生产场景需 rename |
| PMR-004 | HIGH | test-gap | 多个行为变更 Task 缺少 5 字段测试契约 | **已修复** — Task 3(auth), Task 12(多租户) 补充完整测试契约 |
| PMR-005 | HIGH | test-gap | Task 12 API 测试只验"可达"，不验多租户隔离 | **已修复** — 补充跨 school 越权 + 资源不存在 + 旧路径 404 |
| PMR-006 | HIGH | test-gap | Task 5 LLMSlot 测试是逻辑镜像 | **已修复** — 补充 slot 优先级 + disabled + fallback 入口级测试 |
| PMR-007 | MED | design-concern | school 模块在文件列表不一致 | **已修复** — Task 1 Files 清单补 school |
| PMR-008 | MED | design-concern | Task 11 过大（8 模块同时处理） | **已修复** — 拆为 11a(knowledge) + 11b(studio/calendar) + 11c(其余) |
| PMR-009 | MED | design-concern | llm_router.py 与 llm_config_router.py 命名混淆 | **已修复** — 内部逻辑改名 slot_selector.py |
| PMR-010 | MED | design-concern | 无 per-batch 风险矩阵 | **已修复** — 补充 7 个高风险区域 + 额外验证要求 |

## 修复摘要

- 计划文件：10 处修改（文件目标、测试契约、Task 拆分、风险矩阵、Alembic 策略）
- 设计文件：2 处修改（ExamResult ADR、删除表更新）
- 全部 10 个 finding 已处置

## Gate 判定

全部 HIGH finding 已修复 → **待 R2 确认 PASS**。
