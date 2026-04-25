---
baseline_command: "cd ~/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q"
baseline_verified_at: "2026-04-25 11:05"
baseline_count: 2172
---

# 成绩分析模块深度打穿 — 设计文档

> **原则：不铺摊子，一个模块一竿子捅到底。**
> 本文档是"模块化深度整合"的第一个打穿目标：成绩分析。

## 0. 现状诊断

### edu-cloud 已有（骨架完整）

| 维度 | 现状 | 深度 |
|---|---|---|
| 端点数 | 26 个 analytics 端点 | 结构到位 |
| 排名 | student_rankings + delta | 有进退步计算 |
| 分数段 | 可配置 segment + 3 级 fallback | 完整 |
| 临界生 | critical_students (±3 分阈值) | 有 worst_question |
| 等级赋分 | level_score_convert (百分位+线性插值) | 完整 |
| 趋势 | grade/class/student 三维 trend | 有快照 fallback |
| 箱线图 | class_boxplot (四分位) | 完整 |
| 知识热力图 | class_knowledge (班级×知识点) | 有框架 |
| 错因分析 | question_insights (4 类 regex) | 基础 |
| 诊断文本 | exam_diagnosis (模板拼接) | 基础 |
| 权限控制 | 角色白名单 + K-匿名(5人) | 完整 |
| 级联筛选 | power_options (年级→班级→科目→考试) | 完整 |
| 导出 | PDF/XLSX (Playwright Chromium) | 完整 |

### 好分数有而 edu-cloud 缺的（肌肉缺失）

| 缺失 | 影响 | 好分数实现 |
|---|---|---|
| **预计算管线为空** | ClassAnalysis/StudentAnalysis/StudentKnpMastery 全 0 行，26 端点跑的是实时查询，没有持久化分析结果 | W1 考后自动计算并入库 |
| **知识点掌握度为空** | student_knp_mastery 0 行，class_knowledge 返回的数据无实质内容 | 从答题记录反推每学生×每知识点掌握率 |
| **三维诊断缺失** | 没有"最弱知识点/未掌握人数最多/强弱差距最大"三个维度 | 班级分析的核心：worstKnowledges / unmasterMaxCnt / maxScoreDiff |
| **分层学情缺失** | 没有 Top25%/Mid50%/Low25% 分层分析 | 好分数核心：按层看掌握率、趋势、特征 |
| **常错题聚合缺失** | question_insights 有错因但没有"全班共性错题"聚合视角 | 按错误率排序 + 班级平均得分率 |

### 数据基础

| 表 | 行数 | 可用性 |
|---|---|---|
| student_answers | 142,847 | 原始答题数据，足够 |
| exam_results | 367 | 有成绩数据 |
| student_exam_snapshots | 11,183 | 有快照 |
| grading_results | 48 | AI 阅卷结果少 |
| class_analysis | **0** | 空 — 核心问题 |
| student_analysis | **0** | 空 — 核心问题 |
| student_knp_mastery | **0** | 空 — 核心问题 |

**结论**：142K 答题记录是金矿，但从未被"炼"成分析结果。骨架有了，缺的是"跑一遍预计算把表填满"。

## 1. 打穿策略

**不是加新端点，是让现有 26 个端点返回有深度的真数据。**

```
答题数据 142K 行
    ↓ [T1] 预计算管线
ClassAnalysis (班级级)  ← 均分/及格率/优秀率/分数分布/常错题/知识掌握
StudentAnalysis (学生级) ← 总分/排名/进退步/弱知识点
StudentKnpMastery (KP级) ← 每学生×每知识点掌握率
    ↓ [T2-T4] 深度算法
三维诊断 / 分层学情 / 常错题聚合
    ↓ [T5] 前端验证
report/ 7 个页面看到真数据
    ↓ [T6] 端到端验证
从考试发布→预计算→分析页面完整跑通
```

## 2. 任务拆解（6 个 Task，纵向打穿）

### T1: 预计算管线实现 (T3, 3-4h)

**目标**：实现 W1 post-exam pipeline，一次考试发布后自动填充 3 张分析表。

**输入**：exam_id（考试发布事件触发）
**处理**：
1. 查询该考试所有 student_answers + grading_results
2. 按班级聚合 → 写入 ClassAnalysis：
   - avg_score, max_score, min_score (从 GradingResult.final_score)
   - pass_rate = COUNT(score >= fullScore×0.6) / total
   - excellent_rate = COUNT(score >= fullScore×0.85) / total
   - score_distribution = 10 桶直方图 JSON
   - common_wrong_questions = 错误率 Top10 题目 JSON
   - knowledge_mastery = 每知识点班级平均掌握率 JSON
3. 按学生聚合 → 写入 StudentAnalysis：
   - total_score = SUM(各科 final_score)
   - rank_in_class, rank_in_grade (同分同名次跳号)
   - subject_scores = {科目: 分数} JSON
   - weak_knowledge = 掌握率 < 0.6 的知识点列表 JSON
   - improvement_trend = 与上次考试对比 JSON
4. 按学生×知识点 → 写入 StudentKnpMastery：
   - stu_rate = SUM(该KP相关题得分) / SUM(该KP相关题满分)
   - class_rate = 班级该KP平均掌握率
   - grade_rate = 年级该KP平均掌握率

**验收**：手动触发一次现有考试 → 3 张表有数据 → 现有 trend 端点命中快照而非实时计算。

### T2: 三维班级诊断 (T2, 2h)

**目标**：新增 `GET /analytics/exam/{id}/class-diagnosis` 端点。

**算法**（来自好分数）：
```
输入：exam_id, class_id
输出：{
  worstKnowledges: [],        // 按班级掌握率升序 Top5
  unmasterMaxCntKnowledges: [], // 按未掌握人数降序 Top5
  maxScoreDiffKnowledges: [],  // 按(最高分率-最低分率)降序 Top5
  weakKnpCount: floor(total_kp × 0.3),
  commonWrongQueCnt: N
}
```

**数据源**：T1 写入的 ClassAnalysis.knowledge_mastery + StudentKnpMastery。

**验收**：端点返回 3 个维度的知识点诊断数据 + 测试覆盖。

### T3: 分层学情分析 (T2, 2h)

**目标**：新增 `GET /analytics/exam/{id}/layer-analysis` 端点。

**算法**（来自好分数）：
```
输入：exam_id, class_id (可选)
处理：
  1. 按分数段分层：优秀(>=85%) / 良好(60-84%) / 待提升(<60%)
  2. 每层统计：人数、平均得分率、各知识点平均掌握率
  3. 层间对比：哪些知识点在不同层差异最大
输出：{
  layers: [{name, range, studentCount, avgScoreRate, knpMastery: [...]}],
  totalStudents: N,
  overallAvgRate: X,
  maxDiffKnowledges: [] // 层间差异最大的知识点
}
```

**验收**：端点返回分层数据 + 测试覆盖。

### T4: 常错题聚合增强 (T2, 1.5h)

**目标**：增强现有 `question-insights` 或新增 `GET /analytics/exam/{id}/common-wrong-questions`。

**算法**：
```
输入：exam_id, class_id
处理：
  1. 找班级所有学生答错的题（is_correct=0 或 final_score < max_score×0.6）
  2. 按题目聚合：错误人数、班级平均得分率、题型
  3. 按错误率降序排列
输出：{
  wrongQuestionCnt: N,
  scoreRateMean: X,
  questions: [{
    question_id, question_no, question_type,
    max_score, avg_score, mean_rate,
    wrong_count, total_count
  }]
}
```

**验收**：端点返回按错误率排序的题目列表 + 测试。

### T5: 前端 report/ 页面填充 (T2, 3-4h)

**目标**：让 `frontend-nuxt/pages/report/` 的 7 个页面显示真实数据。

**按页面**：
1. **exam.vue** — 接入 summary + distribution + grade_aggregates + question_insights + diagnosis
2. **contrast.vue** — 接入 class_boxplot + class_knowledge + class_error_patterns + 新增 class-diagnosis
3. **students.vue** — 接入 student_rankings + student_trend
4. **level-score.vue** — 已有 level_score_convert，验证前端交互
5. **config.vue** — 已有 segment config CRUD，验证
6. **custom.vue** — 接入 report/query 多指标选择器
7. **table.vue** — 接入导出功能

**验收**：dev server 启动后，每个页面能看到基于真实数据的图表和表格。

### T6: 端到端验证 (T1, 1.5h)

**目标**：模拟完整业务流程验证。

**流程**：
1. 用 seed 数据的考试 → 手动触发 W1 pipeline
2. 检查 3 张预计算表是否填充正确
3. 访问 report/ 每个页面，确认数据展示
4. 验证权限：subject_teacher 看不到排名
5. 验证级联筛选：选年级→选班级→选科目→选考试 全链路

**验收**：完整走通一次"考试发布→分析报告可看"的闭环。

## 3. 执行约束

- **不新建模块**：全部在现有 analytics module 内完成
- **不新建表**：ClassAnalysis / StudentAnalysis / StudentKnpMastery 已存在，只需填充
- **不改现有端点签名**：新功能加新端点，不破坏已有 API
- **TDD**：每个 Task 先写测试再实现
- **基线守卫**：每个 Task 完成后跑全量 pytest，不低于 2172

## 4. 好分数公式速查

| 指标 | 公式 | 阈值 |
|---|---|---|
| 及格率 | COUNT(score >= fullScore×0.6) / total | 60% |
| 优秀率 | COUNT(score >= fullScore×0.85) / total | 85% |
| 排名 | 同分同名次，下一名跳号 | — |
| 进退步 | current_total - prev_total, ±10分分类 | ±10 |
| 分数段 | 10 等分桶 或 可配置 [85,70,60] | 可配置 |
| 知识点掌握率 | SUM(学生KP题得分) / SUM(KP题满分) | — |
| 弱知识点数 | floor(总KP数 × 0.3) | 30% |
| 分层 | Top 25% / Mid 50% / Low 25% | 可配置 |
| 临界生 | score ∈ [passLine-N, passLine) | N=3-10 |
