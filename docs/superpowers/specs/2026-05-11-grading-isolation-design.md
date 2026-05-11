# 阅卷数据隔离守卫设计

> 双模型深度调查（Claude + GPT Codex）确证 6 条污染路径 + 4 个间接影响。
> 本设计采用方案 A：单表加强守卫，零 schema 变更，零数据迁移。

## 问题陈述

人工阅卷和 AI 阅卷共用 `grading_results` 单表（GradingResult ORM），
通过 `status` 和 `source` 字段区分。设计意图是"单一权威分数源"，
但写入守卫不完整，导致两套系统之间存在确定性的交叉污染。

## 确证的污染路径

### P-001 [CRITICAL] AI Worker 污染已确认人工评分

`workers/grading.py:934-937` — `_upsert_ai_result()` 对 `status=confirmed`
的记录不拒绝写入，直接 setattr 写入 ai_score/ai_feedback/ai_raw_response 等 5 个字段。

这是确定性污染，非竞态条件：只要管理员对已有人工评分的科目启动 AI 阅卷，
所有人工评分记录都会被 AI 数据注入。

### P-002 [HIGH] AI 任务创建不检查人工进展

`grading/router.py:776-886` — 三个路径（批量/单题/科目级）只删除 `ai_pending`
状态的旧记录，不检查是否已有 `confirmed` 状态的人工评分。管理员可在教师人工阅卷
进行中无感知地启动 AI 阅卷。

### P-003 [HIGH] ungraded 模式泄露 AI 预评数据

`marking/scorer.py:257-269` — 人工阅卷的 `mode=ungraded` 只排除 `confirmed`
状态的答卷，不排除 `ai_done`。教师会看到 AI 已评的答卷（附带 AI 预评分），
且与 AI 审核流程存在操作同一答卷的可能（虽然有 confirmed 互斥保护）。

此条为已有设计（AI 辅助人工阅卷），双方互斥保护存在（两侧都检查 confirmed
后拒绝重复操作），暂不改动。记录在案以备后续评估。

### P-004 [HIGH] 无乐观锁并发保护

`workers/grading.py:943` + `marking/scorer.py:469` — 两处都只做 `version += 1`
递增，不验证入参版本号是否匹配当前值。无 `SELECT FOR UPDATE` 行锁。
并发读-改-写会导致后写覆盖先写。

### P-005 [MEDIUM] 进度统计被 ai_score IS NOT NULL 假设破坏

全链路用 `ai_score IS NOT NULL` 判断"AI 是否评过"。P-001 发生后，
纯人工记录也有 ai_score → `manual_only` 缩减、`ai_scored_count` 虚增、
AI 覆盖率/置信度/delta 统计全部失真。

涉及文件：`grading_review_router.py:289-300`、`scorer.py:105`、
`ai_report_service.py:218,246,265`。

### P-006 [HIGH] grade_single 质量抽检污染正式记录

`grading/router.py:643-684` — 质量抽检的 `grade_single` 端点会将评分结果
写入正式 `grading_results` 表。未评答卷变成 `ai_done` → 人工阅卷 ungraded
模式跳过它 → 教师只能在 ai_review 模式才看到。

### 间接影响

| 编号 | 位置 | 影响 |
|------|------|------|
| G-001 | `ai_report_service.py:218,246,265` | 覆盖率/置信度/AI-人工 delta 统计被污染行扭曲 |
| G-002 | `workers/grading.py:1089` | Worker 答卷选择用 `ai_score IS NOT NULL` 排除 → 误判已处理 |
| G-003 | `import_real_exam.py:154` | 按 school_id 批量删除（非在线路径，记录在案） |
| G-004 | `ranking_service.py:417-430` | 错因分析从 ai_raw_response 提取 → 注入后产生虚假错因 |

## 修复设计

### 原则

- 单表保持不变，零 ORM schema 变更
- 零 Alembic migration
- 每个改动独立可测试
- 收紧行为（拒绝写入 / 修正统计），不扩大写入范围
- 现有测试不应被破坏

### 改动 1：_upsert_ai_result 拒绝写入 confirmed

**文件**: `src/edu_cloud/workers/grading.py`
**函数**: `_upsert_ai_result()`（行 912-952）

当前行为（行 934-937）：
```python
if existing and existing.status == "confirmed":
    for k, v in ai_fields.items():
        setattr(existing, k, v)
    existing.version += 1
```

修改为：
```python
if existing and existing.status == "confirmed":
    logger.warning(
        "grading_isolation: skipping AI write for confirmed answer=%s, source=%s",
        answer_id, existing.source,
    )
    return "skipped_confirmed"
```

调用方 `process_grading_task` 中统计 skipped 数量，不计入 completed 也不计入 failed。

**解决**: P-001

### 改动 2：create_grading_task 前置告知

**文件**: `src/edu_cloud/modules/grading/router.py`
**函数**: `create_grading_task()`（行 721-999）

在三个路径（批量/单题/科目级）的清理逻辑之后、创建任务之前，查询已有 confirmed 数量：

```python
confirmed_count = (await db.execute(
    select(func.count(GradingResult.id)).where(
        GradingResult.question_id.in_(target_q_ids),
        GradingResult.school_id == school_id,
        GradingResult.status == "confirmed",
    )
)).scalar() or 0
```

将 `confirmed_count` 和 warning 文本附在任务创建响应中。不阻断创建。

**解决**: P-002

### 改动 3：grade_single 永不写入

**文件**: `src/edu_cloud/modules/grading/router.py`
**函数**: `grade_single()`（行 643-684）

移除所有对 GradingResult 的 INSERT/UPDATE 操作。该端点只做：
1. 调用 OCR + LLM 评分 pipeline
2. 返回评分结果（score/confidence/feedback/details）
3. 不写入 grading_results 表

**解决**: P-006

### 改动 4：所有写入点加行锁

**文件**: `workers/grading.py`、`marking/scorer.py`、`grading_review_router.py`

三处查询 existing GradingResult 时加 `with_for_update()`：

```python
existing = (await db.execute(
    select(GradingResult)
    .where(GradingResult.answer_id == answer_id)
    .with_for_update()
)).scalar_one_or_none()
```

PostgreSQL 行锁在事务 commit/rollback 时自动释放，不影响读操作。
SQLite（测试环境）不支持 `FOR UPDATE`，asyncpg 专属语法；
测试中使用 SQLite 时 `with_for_update()` 会被忽略（SQLAlchemy 行为）。

**解决**: P-004

### 改动 5：统计修正——消除 ai_score IS NOT NULL 假设

统一规则：
- 判断"AI 是否评过并确认" → `source IN ('ai', 'ai_override')`
- 判断"纯人工评分" → `source == 'manual'`
- 判断"是否还需要 AI 评" → `status` 字段（ai_pending/ai_done/confirmed）
- `ai_score IS NOT NULL` **不再用于任何业务判断**

| 文件 | 位置 | 当前 | 修正 |
|------|------|------|------|
| `grading_review_router.py` | BQ4 ai_scored (行 289) | `ai_score.isnot(None)` | `source.in_(['ai','ai_override'])` |
| `grading_review_router.py` | BQ4 manual_only (行 294) | `confirmed AND ai_score.is_(None)` | `source == 'manual'` |
| `scorer.py` | get_subjects_with_progress (行 105) | `ai_score.isnot(None)` | `source.in_(['ai','ai_override'])` |
| `ai_report_service.py` | coverage/confidence/delta (行 218,246,265) | `ai_score IS NOT NULL` | `source.in_(['ai','ai_override'])` |

**注意**: `scorer.py:183-198`（ai_review 模式的统计）保持用 `ai_score.is_not(None)`，
因为这里查的是 `status=ai_done` 的记录（source 还没有值），语义正确。

**解决**: P-005, G-001

### 改动 6：Worker 答卷选择修正

**文件**: `src/edu_cloud/workers/grading.py`
**位置**: 答卷查询排除条件（约行 1089）

当前：用 `ai_score IS NOT NULL` 排除已评答卷。
修正：用 `status IN ('ai_done', 'confirmed')` 排除。

**解决**: G-002

## 测试计划

新建 `tests/test_api_exam/test_grading_isolation_advanced.py`，5 个用例：

### T1: test_manual_confirmed_then_ai_upsert_skipped
- 前置：人工评分 → GradingResult(status=confirmed, source=manual)
- 动作：调用 _upsert_ai_result 尝试写入
- 断言：记录不变，ai_score 保持 NULL，返回 skipped_confirmed

### T2: test_ai_done_then_manual_score_correct_source
- 前置：AI 评分 → GradingResult(status=ai_done, ai_score=8)
- 动作：教师 submit_score(score=6)
- 断言：status=confirmed, source=ai_override, final_score=6, ai_score=8 保留

### T3: test_concurrent_submit_score_and_review
- 前置：AI 评分 → GradingResult(status=ai_done)
- 动作：并发 submit_score + submit_review（asyncio.gather）
- 断言：一个成功一个 409，最终只有一条 confirmed 记录

### T4: test_dispatch_status_counts_with_mixed_sources
- 前置：创建混合记录（3 manual + 3 ai + 2 ai_override）
- 动作：调用 dispatch/status
- 断言：ai_scored=5, manual_only=3, confirmed=8

### T5: test_grade_single_does_not_write_to_db
- 前置：已有 GradingResult(status=confirmed)
- 动作：调用 grade_single
- 断言：返回评分结果，数据库记录不变

## 不改的部分

| 组件 | 理由 |
|------|------|
| GradingResult ORM schema | 不加字段、不改字段类型 |
| Alembic migrations | 零迁移 |
| CSV 导出 (`exporter.py`) | 用 final_score + confirmed，不受影响 |
| 前端 ReviewPage 双模式 | AI 复核在人工页面看 AI 结果是合理设计 |
| marking/next ai_review 模式 | 合理设计，有 confirmed 互斥保护 |
| P-003（ungraded 泄露 ai_done） | 已有互斥保护，是有意的 AI 辅助设计 |
| G-003（import_real_exam 批量删除） | 非在线路径，记录在案 |
| G-004（错因分析） | P-001 修复后不会有虚假 ai_raw_response |

## 影响评估

- **改动文件数**: 5 个后端文件 + 1 个测试文件
- **现有测试影响**: 需检查是否有测试依赖 grade_single 的写入行为
- **前端影响**: create_task 响应新增 warning 字段，前端可选展示
- **数据迁移**: 无
- **部署风险**: 低——所有改动收紧行为，不扩大写入范围
