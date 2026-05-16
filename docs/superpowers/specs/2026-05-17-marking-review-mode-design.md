# 阅卷复核模式设计

> 2026-05-17 | 方案 A：在现有 ReviewPage 加 reviewed mode

## 背景

ReviewPage 当前只有两个模式：
- `ungraded`：待批改答卷（未 confirmed）
- `ai_review`：AI 已评但未确认（status=ai_done）

用户需要复核已批改的答卷（status=confirmed），对比 AI 分和终分，发现分歧可改分。当前无此入口。

同时 `ai_review` 模式存在内部不一致：`get_next` 按 `status=ai_done` 过滤，`get_answer_at` 按 `source IN (ai, ai_override)` 过滤，集合不一致。

## 改动范围

### 后端（2 文件）

**src/edu_cloud/modules/marking/scorer.py**

1. `get_next_answer` 新增 `mode="reviewed"` 分支：
   - 浏览集合：`grading_results WHERE status='confirmed' AND question_id=? AND school_id=?`
   - 排序：按 `student_id` ASC（与其他模式一致）
   - 支持 `divergence_min` 参数：传入时只返回 `abs(ai_score - final_score) >= divergence_min` 的记录
   - 无记录时返回 None（前端显示"无匹配答卷"）

2. `get_answer_at` 新增 `mode="reviewed"` 分支：
   - 浏览集合同上
   - 支持同样的 `divergence_min` 参数
   - position.total 反映过滤后的总数

3. 修复 `ai_review` 模式的 `get_answer_at`：
   - 将 `GradingResult.source.in_(["ai", "ai_override"])` 改为 `GradingResult.ai_score.isnot(None)`
   - 与 `get_subjects_with_progress` 的 ai_scored_count 查询一致

**src/edu_cloud/modules/marking/router.py**

4. `next_answer` 端点：接受 `mode` 参数扩展为 `ungraded | ai_review | reviewed`
   - `reviewed` 模式跳过 assignment 权限检查（同 ai_review）
   - 新增 `divergence_min: float | None = None` 查询参数

5. `answer_at` 端点：同上

6. `confirm_score` 端点（已有）：
   - 当 grading_result 已是 `confirmed` 状态时（复核改分场景），在 `review_comment` 追加旧分数记录：`"复核改分: {old_final_score} → {new_final_score}"`
   - `version` 字段 +1（已有 CAS 逻辑）

### 前端（2 文件）

**frontend/src/pages/ReviewPage.vue**

7. 顶栏按钮组从 2 个变 3 个：`待阅 | AI 复核 | 已批改`

8. `onMounted` / `switchMode`：读取 `route.query.mode`，如果是 `reviewed` 则初始化到已批改 tab

9. 已批改 tab 特有 UI：
   - 翻页器旁增加「只看分歧」开关 + 分值输入（默认关闭）
   - 打开后调用 API 带 `divergence_min` 参数
   - AI 分 vs 终分并排显示，`abs(差值) >= 3` 时红色高亮
   - 评分面板可编辑，和 ungraded 模式一样的操作

10. `done` 状态处理：已批改模式下不显示"全部完成"成功页，改为显示"共 N 条记录"

**frontend/src/pages/MarkingSelectPage.vue**

11. "复核" 按钮跳转从 `/marking/grade/${row.id}` 改为 `/marking/grade/${row.id}?mode=reviewed`

## 不改动的部分

- grading_results 表结构不变
- student_answers 表不变
- AI 阅卷 worker（grading.py）不变
- import_real_exam.py 不在此次范围（需单独修复 DELETE 连坐 bug）
- MarkingProgressPage（阅卷进度页）不变

## 语义统一规则

本次改动后，各查询的语义约定：

| 概念 | 查询条件 | 用于 |
|------|---------|------|
| "AI 已评" | `ai_score IS NOT NULL` | 进度统计、ai_review 浏览集合 |
| "已确认" | `status = 'confirmed'` | reviewed 浏览集合、graded_count |
| "人工已评" | `source = 'manual' AND final_score IS NOT NULL` | 人工进度条 |
| "待阅" | `student_answer NOT IN (confirmed grading_results)` | ungraded 浏览集合 |

禁止再用 `source IN ('ai', 'ai_override')` 判断"AI 是否评过"——统一用 `ai_score IS NOT NULL`。

## 测试要点

- reviewed 模式能浏览所有 confirmed 记录
- divergence_min 过滤正确（只返回分歧 ≥ N 的）
- 复核改分后 version +1，review_comment 记录旧分数
- ai_review 模式的 get_answer_at 修复后，浏览集合与 get_next 一致
- 已批改模式翻页不出现"全部完成"误判
