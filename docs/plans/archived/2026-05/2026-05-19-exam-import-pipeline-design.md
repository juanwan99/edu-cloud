# 外部考试数据导入管道设计

> 状态：设计确认，待实施
> 日期：2026-05-19
> 范围：edu-cloud 支持从联考平台（天一大联考等）导入成绩数据

## 1. 业务背景

学校的考试不只来自 edu-cloud 自有的扫描阅卷流水线，还包括：
- 外部联考平台（天一大联考、好分数等）
- 区/市统考
- 本校月考（手工录分）

这些外部考试提供 Excel 成绩数据，必须导入 edu-cloud 并与自有数据走同一套分析、错题、画像管道。

## 2. 核心架构：统一事实层

所有考试数据（无论自有阅卷还是外部导入）走同一条链路：

```
导入/扫描 → Question → StudentAnswer → GradingResult(confirmed)
                                          ↓
                              pipeline 自动生成：
                              - student_exam_snapshots（画像趋势）
                              - exam_results（总分排名）
                              - student_error_books（错题库）
                              - student_error_patterns（错误模式）
```

外部导入不分叉，下游分析报告、错题库零改动。

### 2.1 元数据 vs 次级数据

只导入元数据（不可推导的事实），次级数据由系统计算：

| 分类 | 内容 | 来源 |
|------|------|------|
| 元数据 | 每学生每题得分 | 小题分.xlsx |
| 元数据 | 每题标准答案 + 满分 | 试题分析.xlsx（2列） |
| 元数据 | 每学生赋分/等级/排名 | 小题分.xlsx 聚合列 |
| 次级 | 综合指标/一分一段/分数段/名次段/平均分/等级分布/前N名/优秀生/试题均分对比 | 系统从元数据计算 |
| 次级 | 知识点分析/关键能力/核心素养 | 系统从元数据+知识点映射计算 |

## 3. 两种导入模式

| 模式 | 输入 | 产出 | 适用场景 |
|------|------|------|---------|
| 小题分导入 | 小题分.xlsx（+ 可选题目信息） | Question + StudentAnswer + GradingResult + 错题库 | 联考平台导出 |
| 总分导入 | 科目总分横向表 | synthetic Question + StudentAnswer + GradingResult | 月考手工录分 |

## 4. 文件格式

### 4.1 小题分 xlsx（直接接受平台导出格式）

```
Row 1: 学校 | 班级 | 考号 | 姓名 | 选科 | {科目}(合并) | 客观题(合并) | 主观题(合并)
Row 2:                                    | 赋分 | 原始分 | 等级 | 班名次 | 校名次 | 客观题 | 主观题 | 选择1 | ... | 17 | 18 | ...
Row 3+: 数据行
```

解析规则：
- 前 5 列固定：学校/班级/考号/姓名/选科
- 聚合列（赋分/原始分/等级/班名次/校名次/客观题小计/主观题小计）→ 存入 snapshot
- 剩余列 = 逐题得分（列名即题号）→ 创建 Question + StudentAnswer

### 4.2 题目信息（可选补充）

两种方式：
1. 上传试题分析.xlsx（系统只提取答案+满分两列，忽略次级统计）
2. 在预览页面手动补填

### 4.3 总分横向表（简化模板）

```
考号 | 姓名 | 班级 | 选科 | 语文 | 语文(赋分) | 数学 | ... | 总分 | 班名次 | 校名次
```

列名识别规则：
- 精确匹配科目名 → 原始分列
- `XX(赋分)` → 赋分列
- `总分` / `班名次` / `校名次` / `年级名次` / `全体名次` → 固定语义

### 4.4 多科目

- 联考：上传 zip（按文件夹名/文件名自动识别科目）
- 单科：上传单个 xlsx
- 不搞多 sheet 合并

## 5. API 设计

```
POST   /api/v1/exam-imports                    上传文件 + 考试元信息 → 返回 import_id + 预览
PATCH  /api/v1/exam-imports/{id}/mapping       确认学生映射 + 题目信息
POST   /api/v1/exam-imports/{id}/commit        正式写入
GET    /api/v1/exam-imports/{id}               查看导入状态/结果
DELETE /api/v1/exam-imports/{id}               取消未提交的导入
```

上传参数：
- `file`: xlsx 或 zip（必填）
- `exam_name`: 考试名称（必填）
- `exam_type`: 月考/联考/统考/期中/期末（必填）
- `grade_scope`: 高一/高二/高三（必填）
- `exam_date`: 考试日期（可选）
- `import_mode`: `questions`（小题分）/ `totals`（仅总分）

## 6. 数据流

### 6.1 小题分导入

```
上传 xlsx/zip
  → 解析表头（识别科目、题目列、学生身份列）
  → 生成预览：
      - 识别到的科目和题目列表（含推断的满分）
      - 学生匹配结果（已匹配/未匹配/多候选）
      - 题目信息补填区（答案、满分、题型）
  → 教师确认
  → 写入：
      1. Exam (status=completed, source=import_questions)
      2. Subject per 科目
      3. Question per 题目 (name/type/max_score/correct_answer)
      4. StudentAnswer per 学生×题目 (score)
      5. GradingResult per StudentAnswer (final_score=score, status=confirmed, source=import)
  → post-import pipeline：
      - student_exam_snapshots（总分/赋分/排名/得分率）
      - exam_results（总分汇总）
      - student_error_books（得分 < 满分的记录）
      - student_error_patterns（按科目聚合）
```

### 6.2 总分导入

```
上传 xlsx
  → 解析表头（识别科目列、排名列）
  → 预览 + 学生匹配
  → 教师确认
  → 写入：
      1. Exam (status=completed, source=import_totals)
      2. Subject per 科目
      3. Question per 科目 (name="__TOTAL__", type=synthetic, max_score=科目满分)
      4. StudentAnswer per 学生×科目 (score=总分)
      5. GradingResult (final_score=总分, status=confirmed, source=import)
  → post-import pipeline（同上，但 error_books 不生成）
```

## 7. 学生匹配

优先级：
1. `考号 = students.student_number` 精确匹配
2. `姓名 + 班级` 确定性匹配（同校内唯一）

预览页面展示三类：
- 已匹配：直接关联
- 多候选：教师选择
- 未匹配：教师决定跳过或手动关联

不自动创建学生记录。

## 8. 赋分/排名处理

小题分中的赋分/等级/班名次/校名次作为**官方导入值**直接存入 snapshot，不由系统重算。

| 字段 | 存储位置 | 来源 |
|------|---------|------|
| 原始分 | snapshot.total_score | 小题分求和（或导入值） |
| 赋分 | snapshot.converted_score | 导入值 |
| 等级 | snapshot.error_summary.grade_level | 导入值 |
| 班名次 | snapshot.class_rank | 导入值 |
| 校名次 | snapshot.grade_rank | 导入值 |
| 赋分对照表 | 不导入 | 小题分已含每学生赋分结果 |

## 9. Exam 来源标记

`exams.source` 字段区分：
- `scan` = 自有扫描阅卷
- `import_questions` = 外部导入（小题分）
- `import_totals` = 外部导入（仅总分）

分析模块根据 source 决定是否展示小题级分析。

## 10. 幂等性

幂等键：`school_id + exam_id + subject_code + student_number + question_name`

同一考试重复导入：
- 默认 upsert：更新已有记录的分数
- 记录变更日志（旧值→新值 + import_batch_id）
- 重新触发 pipeline 重建 snapshot/error_book

## 11. 新增/修改的数据模型

### 11.1 新表：exam_import_sessions

```python
class ExamImportSession(Base, IdMixin, TimestampMixin):
    school_id: str          # FK → schools
    exam_name: str          # 考试名称
    exam_type: str          # 月考/联考/统考/期中/期末
    grade_scope: str        # 高一/高二/高三
    import_mode: str        # questions / totals
    status: str             # pending / previewing / committed / failed / cancelled
    file_path: str          # 上传文件路径
    preview_data: dict      # JSON: 解析预览结果
    mapping_data: dict      # JSON: 教师确认的映射
    result_summary: dict    # JSON: 导入结果统计
    committed_by: str       # FK → users
    exam_id: str | None     # FK → exams（commit 后填入）
```

### 11.2 现有表修改

- `exams.source`: 新增枚举值 `import_questions` / `import_totals`
- `student_exam_snapshots`: 已有 `converted_score` 字段（本次新增）
- `GradingResult.source`: 新增枚举值 `import`

### 11.3 Question 标记

外部导入的 Question 通过以下方式标记：
- `question_type = "synthetic"`: 仅总分导入时的虚拟题
- `question_type = "choice" / "essay" / "unknown"`: 小题分导入时的真实题

## 12. 前端页面

新增一个导入页面（嵌入考试管理板块）：

1. **上传步骤**：选择文件 + 填写考试元信息 + 选择导入模式
2. **预览步骤**：展示解析结果 + 学生匹配 + 题目信息补填
3. **确认步骤**：展示最终写入摘要 + 确认按钮
4. **结果步骤**：导入完成统计

## 13. 不在范围内

- 赋分对照表导入（赋分以导入的学生级结果为准）
- 多平台 adapter 自动识别（首期只支持通用格式 + 天一大联考格式）
- 知识点自动映射（知识点分析文件不导入，后续手动关联）
- 试卷 PDF 存储（后续独立功能）
