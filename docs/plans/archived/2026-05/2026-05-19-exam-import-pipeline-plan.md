# 外部考试数据导入管道 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 支持从联考平台（天一大联考等）导入 Excel 成绩数据，走标准 Question→StudentAnswer→GradingResult 管道，使分析报告/错题库/画像自动生效。

**Architecture:** 新增 `modules/exam_import/` 模块（Template A），包含 router + service + parser + models。Excel 解析后写入现有 exam/scan/grading 模型，复用现有 pipeline service 生成 snapshot/error_book。前端新增导入页面嵌入考试管理板块。

**Tech Stack:** FastAPI + SQLAlchemy async + openpyxl + 现有 pipeline service

**Design Doc:** `docs/plans/2026-05-19-exam-import-pipeline-design.md`

---

## File Structure

### 新建文件

```
src/edu_cloud/modules/exam_import/
  __init__.py                    # 模块入口
  router.py                      # 5 个 API 端点
  service.py                     # 导入业务逻辑（预览/匹配/写入/pipeline触发）
  parser.py                      # Excel 解析器（小题分横向表 + 总分横向表 + zip）
  models.py                      # ExamImportSession ORM

tests/test_modules/test_exam_import/
  __init__.py
  conftest.py                    # 模块级 fixture
  test_parser.py                 # Excel 解析单测
  test_service.py                # 业务逻辑单测
  test_router.py                 # API 端点集成测试

alembic/versions/xxxx_add_exam_import_session.py   # migration

frontend/src/pages/ExamImportPage.vue              # 导入页面（上传→预览→确认→结果）
frontend/src/api/examImport.js                     # API 调用层
```

### 修改文件

```
src/edu_cloud/api/router_registry.py:86            # 注册新模块 router
src/edu_cloud/core/permissions.py                   # 新增 IMPORT_EXAMS 权限
src/edu_cloud/modules/pipeline/service.py           # generate_exam_snapshots 支持导入的赋分/排名保留
frontend/src/config/sidebarConfig.js                # 侧边栏添加导入入口
frontend/src/router/index.js                        # 新增路由
```

---

## Task 1: Excel 解析器（parser.py）

**Files:**
- Create: `src/edu_cloud/modules/exam_import/__init__.py`
- Create: `src/edu_cloud/modules/exam_import/parser.py`
- Test: `tests/test_modules/test_exam_import/__init__.py`
- Test: `tests/test_modules/test_exam_import/test_parser.py`
- Test data: `tests/test_modules/test_exam_import/fixtures/`

### 1.1 解析结果数据结构

parser 输出统一的 `ParsedExamData` dataclass，与存储层解耦。

- [ ] **Step 1: 创建模块目录和 parser 数据结构**

```python
# src/edu_cloud/modules/exam_import/__init__.py
"""外部考试数据导入模块。"""

# src/edu_cloud/modules/exam_import/parser.py
"""Excel 解析器 — 将外部平台导出的 xlsx 解析为统一中间模型。"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

import openpyxl

SUBJECT_CODE_MAP = {
    "语文": "YW", "数学": "SX", "英语": "YY",
    "物理": "WL", "化学": "HX", "生物": "SW",
    "历史": "LS", "地理": "DL", "政治": "ZZ",
}

SUBJECT_MAX_SCORE = {
    "YW": 150, "SX": 150, "YY": 150,
    "WL": 100, "HX": 100, "SW": 100,
    "LS": 100, "DL": 100, "ZZ": 100,
}


@dataclass
class QuestionDef:
    name: str
    question_type: str  # choice / multi_choice / essay / unknown / synthetic
    max_score: float
    correct_answer: str | None = None
    max_score_inferred: bool = False  # F4: True=从数据推断，需教师确认


@dataclass
class StudentScore:
    student_key: str        # 考号 or 学号
    student_name: str
    class_name: str | None = None
    school_name: str | None = None
    elective: str | None = None  # 选科组合
    raw_total: float | None = None
    converted_score: float | None = None  # 赋分
    grade_level: str | None = None  # 等级
    class_rank: int | None = None
    school_rank: int | None = None
    objective_subtotal: float | None = None
    subjective_subtotal: float | None = None
    question_scores: dict[str, float] = field(default_factory=dict)
    is_absent: bool = False


@dataclass
class ParsedSubjectData:
    subject_name: str
    subject_code: str
    questions: list[QuestionDef]
    students: list[StudentScore]


@dataclass
class ParsedExamData:
    subjects: list[ParsedSubjectData]
    warnings: list[str] = field(default_factory=list)
```

- [ ] **Step 2: 创建测试 fixture — 最小小题分 xlsx**

```python
# tests/test_modules/test_exam_import/conftest.py
import pytest
from pathlib import Path
import openpyxl


@pytest.fixture
def sample_question_scores_xlsx(tmp_path) -> Path:
    """模拟天一大联考小题分导出格式（3学生×5题）"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Table"
    # Row 1: 合并表头
    ws.cell(1, 1, "学校")
    ws.cell(1, 2, "班级")
    ws.cell(1, 3, "考号")
    ws.cell(1, 4, "姓名")
    ws.cell(1, 5, "选科")
    ws.cell(1, 6, "生物")  # 科目名（合并区域起始）
    ws.cell(1, 13, "客观题")
    ws.cell(1, 16, "主观题")
    # Row 2: 详细列头
    ws.cell(2, 6, "赋分")
    ws.cell(2, 7, "原始分")
    ws.cell(2, 8, "等级")
    ws.cell(2, 9, "班名次")
    ws.cell(2, 10, "校名次")
    ws.cell(2, 11, "客观题")
    ws.cell(2, 12, "主观题")
    ws.cell(2, 13, "选择1")
    ws.cell(2, 14, "选择2")
    ws.cell(2, 15, "选择3")
    ws.cell(2, 16, "17")
    ws.cell(2, 17, "18")
    # Row 3-5: data
    for i, (name, exam_no, cls) in enumerate([
        ("张三", "3722230101", "2301"),
        ("李四", "3722230102", "2301"),
        ("王五", "3722230203", "2302"),
    ], start=3):
        ws.cell(i, 1, "测试学校")
        ws.cell(i, 2, cls)
        ws.cell(i, 3, exam_no)
        ws.cell(i, 4, name)
        ws.cell(i, 5, "物化生")
        ws.cell(i, 6, 85)      # 赋分
        ws.cell(i, 7, 70)      # 原始分
        ws.cell(i, 8, "A")     # 等级
        ws.cell(i, 9, i - 2)   # 班名次
        ws.cell(i, 10, i - 2)  # 校名次
        ws.cell(i, 11, 20)     # 客观题小计
        ws.cell(i, 12, 50)     # 主观题小计
        ws.cell(i, 13, "2.00") # 选择1
        ws.cell(i, 14, "0.00") # 选择2
        ws.cell(i, 15, "2.00") # 选择3
        ws.cell(i, 16, "12.00")  # 17
        ws.cell(i, 17, "8.00")  # 18

    fp = tmp_path / "生物_小题分.xlsx"
    wb.save(fp)
    return fp


@pytest.fixture
def sample_totals_xlsx(tmp_path) -> Path:
    """模拟科目总分横向表（3学生×3科）"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.cell(1, 1, "考号")
    ws.cell(1, 2, "姓名")
    ws.cell(1, 3, "班级")
    ws.cell(1, 4, "语文")
    ws.cell(1, 5, "数学")
    ws.cell(1, 6, "英语")
    ws.cell(1, 7, "总分")
    ws.cell(1, 8, "班名次")
    ws.cell(1, 9, "校名次")

    for i, (name, sn) in enumerate([("张三", "001"), ("李四", "002"), ("王五", "003")], start=2):
        ws.cell(i, 1, sn)
        ws.cell(i, 2, name)
        ws.cell(i, 3, "2301")
        ws.cell(i, 4, 110)  # 语文
        ws.cell(i, 5, 95)   # 数学
        ws.cell(i, 6, 120)  # 英语
        ws.cell(i, 7, 325)  # 总分
        ws.cell(i, 8, i - 1)
        ws.cell(i, 9, i - 1)

    fp = tmp_path / "scores.xlsx"
    wb.save(fp)
    return fp
```

- [ ] **Step 3: 写小题分解析器的 failing test**

```python
# tests/test_modules/test_exam_import/test_parser.py
from edu_cloud.modules.exam_import.parser import parse_question_scores_xlsx, ParsedSubjectData


def test_parse_question_scores_basic(sample_question_scores_xlsx):
    result = parse_question_scores_xlsx(sample_question_scores_xlsx)

    assert len(result.subjects) == 1
    subj = result.subjects[0]
    assert subj.subject_name == "生物"
    assert subj.subject_code == "SW"
    assert len(subj.questions) == 5  # 选择1-3 + 17 + 18
    assert len(subj.students) == 3

    # 验证题目
    q1 = subj.questions[0]
    assert q1.name == "选择1"
    assert q1.question_type == "choice"

    q4 = subj.questions[3]
    assert q4.name == "17"
    assert q4.question_type == "essay"

    # 验证学生
    s1 = subj.students[0]
    assert s1.student_key == "3722230101"
    assert s1.student_name == "张三"
    assert s1.raw_total == 70
    assert s1.converted_score == 85
    assert s1.grade_level == "A"
    assert s1.class_rank == 1
    assert s1.question_scores["选择1"] == 2.0
    assert s1.question_scores["选择2"] == 0.0
    assert s1.question_scores["17"] == 12.0
```

- [ ] **Step 4: `pytest tests/test_modules/test_exam_import/test_parser.py::test_parse_question_scores_basic -v` → 确认 FAIL**

- [ ] **Step 5: 实现 `parse_question_scores_xlsx`**

```python
# 添加到 src/edu_cloud/modules/exam_import/parser.py

def _detect_subject_name(ws) -> str:
    """从 Row 1 的合并区域检测科目名。在 col 6 起查找非空值（跳过前5列固定列）。"""
    for c in range(6, ws.max_column + 1):
        v = ws.cell(row=1, column=c).value
        if v and str(v) in SUBJECT_CODE_MAP:
            return str(v)
    # fallback: 从文件名推断
    return ""


def _infer_question_type(name: str) -> str:
    if re.match(r"选择\d+", name):
        return "choice"
    return "essay"


def _infer_max_score(name: str, scores: list[float]) -> float:
    if not scores:
        return 0
    return max(scores)


def parse_question_scores_xlsx(file_path: str | Path) -> ParsedExamData:
    """解析天一大联考格式的小题分 xlsx。

    表头结构（2行）：
    Row 1: 学校|班级|考号|姓名|选科|{科目}(合并)|客观题(合并)|主观题(合并)
    Row 2: ...|赋分|原始分|等级|班名次|校名次|客观题|主观题|选择1|...|17|18|...
    """
    wb = openpyxl.load_workbook(file_path, read_only=False, data_only=True)
    ws = wb[wb.sheetnames[0]]
    warnings: list[str] = []

    subject_name = _detect_subject_name(ws)
    if not subject_name:
        # 尝试从文件名提取
        fname = Path(file_path).stem
        for sn in SUBJECT_CODE_MAP:
            if sn in fname:
                subject_name = sn
                break
    if not subject_name:
        warnings.append("无法识别科目名称")
        wb.close()
        return ParsedExamData(subjects=[], warnings=warnings)

    subject_code = SUBJECT_CODE_MAP[subject_name]

    # 解析 Row 2 表头，找到各列位置
    header2 = []
    for c in range(1, ws.max_column + 1):
        header2.append(ws.cell(row=2, column=c).value)

    # 定位聚合列和题目列
    AGG_NAMES = {"赋分", "原始分", "等级", "班名次", "校名次", "客观题", "主观题"}
    question_cols: list[tuple[int, str]] = []  # (col_index, question_name)
    agg_cols: dict[str, int] = {}

    for i, h in enumerate(header2):
        if h is None:
            continue
        h_str = str(h).strip()
        if h_str in AGG_NAMES:
            agg_cols[h_str] = i
        elif i >= 5 and h_str not in AGG_NAMES:
            question_cols.append((i, h_str))

    # 读取数据行
    students: list[StudentScore] = []
    scores_by_question: dict[str, list[float]] = {qn: [] for _, qn in question_cols}

    for row_idx in range(3, ws.max_row + 1):
        exam_no = ws.cell(row=row_idx, column=3).value
        name = ws.cell(row=row_idx, column=4).value
        if not exam_no and not name:
            continue

        qs: dict[str, float] = {}
        for col_i, q_name in question_cols:
            raw = ws.cell(row=row_idx, column=col_i + 1).value
            if raw is not None:
                try:
                    val = float(raw)
                    qs[q_name] = val
                    scores_by_question[q_name].append(val)
                except (ValueError, TypeError):
                    pass

        def _get_agg(key: str):
            if key not in agg_cols:
                return None
            v = ws.cell(row=row_idx, column=agg_cols[key] + 1).value
            return v

        def _safe_float(v):
            if v is None:
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        def _safe_int(v):
            if v is None:
                return None
            try:
                return int(v)
            except (ValueError, TypeError):
                return None

        students.append(StudentScore(
            student_key=str(exam_no) if exam_no else "",
            student_name=str(name) if name else "",
            class_name=str(ws.cell(row=row_idx, column=2).value or ""),
            school_name=str(ws.cell(row=row_idx, column=1).value or ""),
            elective=str(ws.cell(row=row_idx, column=5).value or ""),
            raw_total=_safe_float(_get_agg("原始分")),
            converted_score=_safe_float(_get_agg("赋分")),
            grade_level=str(_get_agg("等级")) if _get_agg("等级") else None,
            class_rank=_safe_int(_get_agg("班名次")),
            school_rank=_safe_int(_get_agg("校名次")),
            objective_subtotal=_safe_float(_get_agg("客观题")),
            subjective_subtotal=_safe_float(_get_agg("主观题")),
            question_scores=qs,
        ))

    # 构建 QuestionDef
    questions: list[QuestionDef] = []
    for _, q_name in question_cols:
        q_type = _infer_question_type(q_name)
        max_s = _infer_max_score(q_name, scores_by_question.get(q_name, []))
        questions.append(QuestionDef(
            name=q_name,
            question_type=q_type,
            max_score=max_s,
            max_score_inferred=True,  # F4: 从数据推断，preview 需标记
        ))

    wb.close()

    return ParsedExamData(
        subjects=[ParsedSubjectData(
            subject_name=subject_name,
            subject_code=subject_code,
            questions=questions,
            students=students,
        )],
        warnings=warnings,
    )
```

- [ ] **Step 6: `pytest tests/test_modules/test_exam_import/test_parser.py::test_parse_question_scores_basic -v` → 确认 PASS**

- [ ] **Step 7: 写总分解析器的 failing test**

```python
# tests/test_modules/test_exam_import/test_parser.py（追加）
from edu_cloud.modules.exam_import.parser import parse_totals_xlsx


def test_parse_totals_basic(sample_totals_xlsx):
    result = parse_totals_xlsx(sample_totals_xlsx)

    assert len(result.subjects) == 3  # 语文/数学/英语
    yw = next(s for s in result.subjects if s.subject_code == "YW")
    assert yw.subject_name == "语文"
    assert len(yw.questions) == 1
    assert yw.questions[0].name == "__TOTAL__"
    assert yw.questions[0].question_type == "synthetic"
    assert yw.questions[0].max_score == 150
    assert len(yw.students) == 3
    assert yw.students[0].raw_total == 110
```

- [ ] **Step 8: `pytest tests/test_modules/test_exam_import/test_parser.py::test_parse_totals_basic -v` → 确认 FAIL**

- [ ] **Step 9: 实现 `parse_totals_xlsx`**

```python
# 添加到 src/edu_cloud/modules/exam_import/parser.py

def parse_totals_xlsx(file_path: str | Path) -> ParsedExamData:
    """解析科目总分横向表。

    表头（1行）：考号|姓名|班级|选科?|语文|语文(赋分)?|数学|...|总分|班名次|校名次|...
    """
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    warnings: list[str] = []

    header = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]

    FIXED_COLS = {"考号", "学号", "准考证号", "姓名", "班级", "选科", "选科组合",
                  "总分", "班名次", "校名次", "年级名次", "全体名次", "全体人数", "考试状态"}
    RANK_PATTERN = re.compile(r"(.+)(名次|人数|排名)$")
    CONVERTED_PATTERN = re.compile(r"(.+)\(赋分\)$")
    GRADE_PATTERN = re.compile(r"(.+)\(等级\)$")

    # 识别科目列和特殊列
    col_map: dict[str, int] = {}  # header_name -> col_index
    subject_cols: list[tuple[int, str, str]] = []  # (col_index, subject_name, subject_code)
    converted_cols: dict[str, int] = {}  # subject_name -> col_index

    for i, h in enumerate(header):
        if h is None:
            continue
        h_str = str(h).strip()
        col_map[h_str] = i

        m_conv = CONVERTED_PATTERN.match(h_str)
        if m_conv:
            converted_cols[m_conv.group(1)] = i
            continue

        m_grade = GRADE_PATTERN.match(h_str)
        if m_grade:
            continue

        if h_str in FIXED_COLS or RANK_PATTERN.match(h_str):
            continue

        code = SUBJECT_CODE_MAP.get(h_str)
        if code:
            subject_cols.append((i, h_str, code))

    # 读数据行
    subjects_data: dict[str, ParsedSubjectData] = {}
    for _, sname, scode in subject_cols:
        max_score = SUBJECT_MAX_SCORE.get(scode, 100)
        subjects_data[sname] = ParsedSubjectData(
            subject_name=sname,
            subject_code=scode,
            questions=[QuestionDef(
                name="__TOTAL__", question_type="synthetic", max_score=max_score,
            )],
            students=[],
        )

    id_col = col_map.get("考号") or col_map.get("学号") or col_map.get("准考证号")
    name_col = col_map.get("姓名")
    class_col = col_map.get("班级")
    rank_class_col = col_map.get("班名次")
    rank_school_col = col_map.get("校名次")

    for row in ws.iter_rows(min_row=2, values_only=False):
        vals = [c.value for c in row]
        student_key = str(vals[id_col]) if id_col is not None and vals[id_col] else ""
        student_name = str(vals[name_col]) if name_col is not None and vals[name_col] else ""
        if not student_key and not student_name:
            continue

        class_name = str(vals[class_col]) if class_col is not None and vals[class_col] else None
        c_rank = None
        if rank_class_col is not None:
            try:
                c_rank = int(vals[rank_class_col])
            except (ValueError, TypeError):
                pass
        s_rank = None
        if rank_school_col is not None:
            try:
                s_rank = int(vals[rank_school_col])
            except (ValueError, TypeError):
                pass

        for col_i, sname, scode in subject_cols:
            raw = vals[col_i]
            if raw is None:
                continue
            try:
                score = float(raw)
            except (ValueError, TypeError):
                continue

            conv = None
            if sname in converted_cols:
                try:
                    conv = float(vals[converted_cols[sname]])
                except (ValueError, TypeError):
                    pass

            subjects_data[sname].students.append(StudentScore(
                student_key=student_key,
                student_name=student_name,
                class_name=class_name,
                raw_total=score,
                converted_score=conv,
                class_rank=c_rank,
                school_rank=s_rank,
                question_scores={"__TOTAL__": score},
            ))

    wb.close()
    return ParsedExamData(
        subjects=[s for s in subjects_data.values() if s.students],
        warnings=warnings,
    )
```

- [ ] **Step 10: `pytest tests/test_modules/test_exam_import/test_parser.py -v` → 确认 2 PASS**

- [ ] **Step 11: 写 zip 解析器（F7: 多科目支持）**

```python
# 添加到 src/edu_cloud/modules/exam_import/parser.py

import zipfile
import tempfile

MAX_ZIP_FILES = 200
MAX_ZIP_TOTAL_SIZE = 100 * 1024 * 1024  # 100MB
MAX_ZIP_RATIO = 20  # 压缩比上限

def parse_zip(file_path: str | Path) -> ParsedExamData:
    """解析 zip 包（每科一个文件夹，查找 *小题分*.xlsx）。"""
    all_subjects: list[ParsedSubjectData] = []
    warnings: list[str] = []

    with zipfile.ZipFile(file_path) as zf:
        # F7: 安全校验
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_FILES:
            raise ValueError(f"Too many files in zip: {len(infos)}")
        total_uncompressed = sum(i.file_size for i in infos)
        if total_uncompressed > MAX_ZIP_TOTAL_SIZE:
            raise ValueError(f"Zip too large: {total_uncompressed} bytes")
        zip_size = Path(file_path).stat().st_size
        if zip_size > 0 and total_uncompressed / zip_size > MAX_ZIP_RATIO:
            raise ValueError("Zip bomb detected")

        for info in infos:
            # 拒绝路径穿越、symlink、非 xlsx
            if info.filename.startswith("/") or ".." in info.filename:
                raise ValueError(f"Unsafe path: {info.filename}")
            if info.external_attr >> 16 & 0o120000 == 0o120000:
                raise ValueError(f"Symlink rejected: {info.filename}")

        with tempfile.TemporaryDirectory() as tmpdir:
            # 只解压 .xlsx 文件
            for info in infos:
                if info.filename.lower().endswith(".xlsx") and not info.is_dir():
                    zf.extract(info, tmpdir)
            tmp = Path(tmpdir)

            # 查找所有 *小题分*.xlsx
            for xlsx in tmp.rglob("*小题分*.xlsx"):
                result = parse_question_scores_xlsx(xlsx)
                all_subjects.extend(result.subjects)
                warnings.extend(result.warnings)

            # 如果没找到小题分，尝试找总分表
            if not all_subjects:
                for xlsx in tmp.rglob("*.xlsx"):
                    if "小题分" not in xlsx.name:
                        result = parse_totals_xlsx(xlsx)
                        all_subjects.extend(result.subjects)
                        warnings.extend(result.warnings)

    if not all_subjects:
        warnings.append("zip 中未找到可识别的成绩文件")

    return ParsedExamData(subjects=all_subjects, warnings=warnings)
```

- [ ] **Step 12: 写 zip 解析 test**

```python
# tests/test_modules/test_exam_import/test_parser.py（追加）
import zipfile

def test_parse_zip_multi_subject(tmp_path, sample_question_scores_xlsx):
    """F7: zip 包含多科目文件"""
    zip_path = tmp_path / "exam.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(sample_question_scores_xlsx, "生物/生物_小题分.xlsx")

    from edu_cloud.modules.exam_import.parser import parse_zip
    result = parse_zip(zip_path)
    assert len(result.subjects) == 1
    assert result.subjects[0].subject_name == "生物"
```

- [ ] **Step 13: `pytest tests/test_modules/test_exam_import/test_parser.py -v` → 3 PASS**

- [ ] **Step 14: Commit**

```bash
git add src/edu_cloud/modules/exam_import/ tests/test_modules/test_exam_import/
git commit -m "feat(exam-import): Excel parser — 小题分 + 总分 + zip 三种格式解析"
```

---

## Task 2: ExamImportSession 模型 + Migration

**Files:**
- Create: `src/edu_cloud/modules/exam_import/models.py`
- Create: `alembic/versions/xxxx_add_exam_import_session.py`
- Test: `tests/test_modules/test_exam_import/test_models.py`

- [ ] **Step 1: 写模型**

```python
# src/edu_cloud/modules/exam_import/models.py
"""外部考试导入会话。"""
from sqlalchemy import String, Float, Integer, ForeignKey, JSON, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class ExamImportSession(Base, IdMixin, TimestampMixin):
    __tablename__ = "exam_import_sessions"

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    exam_name: Mapped[str] = mapped_column(String(200))
    exam_type: Mapped[str] = mapped_column(String(20))
    grade_scope: Mapped[str] = mapped_column(String(50))
    import_mode: Mapped[str] = mapped_column(String(20))  # questions / totals
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending → previewing → committed → failed → cancelled
    file_path: Mapped[str | None] = mapped_column(String(500), default=None)
    preview_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    mapping_data: Mapped[dict | None] = mapped_column(JSON, default=None)
    result_summary: Mapped[dict | None] = mapped_column(JSON, default=None)
    committed_by: Mapped[str | None] = mapped_column(String(36), default=None)
    exam_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("exams.id"), default=None)
    exam_date: Mapped[str | None] = mapped_column(String(20), default=None)
```

- [ ] **Step 2: 写 failing test**

```python
# tests/test_modules/test_exam_import/test_models.py
import pytest
from edu_cloud.modules.exam_import.models import ExamImportSession


@pytest.mark.asyncio
async def test_create_import_session(db):
    from tests.conftest import _seed_school
    school = await _seed_school(db)

    session = ExamImportSession(
        school_id=school.id,
        exam_name="测试考试",
        exam_type="月考",
        grade_scope="高一",
        import_mode="questions",
        status="pending",
    )
    db.add(session)
    await db.commit()
    assert session.id is not None
```

- [ ] **Step 3: 在 `tests/conftest.py` 顶部 import 中添加模型注册**

```python
# 在 conftest.py 的 import 区块末尾添加（确保 ORM 注册到 Base.metadata）：
import edu_cloud.modules.exam_import.models  # noqa: F401
```

- [ ] **Step 4: `pytest tests/test_modules/test_exam_import/test_models.py -v` → PASS**

- [ ] **Step 5: 生成 Alembic migration**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python -c "
# 手动创建 migration 文件
# down_revision：执行时用 `alembic heads` 确认实际 head
"
```

Migration 内容：

```python
# alembic/versions/xxxx_add_exam_import_session.py
"""add exam_import_sessions table

Revision ID: <auto>
Revises: <current alembic head — run `alembic heads` to confirm>
"""
from alembic import op
import sqlalchemy as sa

revision = "<auto>"
down_revision = "a1b2_chat_msgs"  # 执行时用 `alembic heads` 确认实际 head

def upgrade():
    op.create_table(
        "exam_import_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id"), nullable=False, index=True),
        sa.Column("exam_name", sa.String(200), nullable=False),
        sa.Column("exam_type", sa.String(20), nullable=False),
        sa.Column("grade_scope", sa.String(50), nullable=False),
        sa.Column("import_mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("preview_data", sa.JSON, nullable=True),
        sa.Column("mapping_data", sa.JSON, nullable=True),
        sa.Column("result_summary", sa.JSON, nullable=True),
        sa.Column("committed_by", sa.String(36), nullable=True),
        sa.Column("exam_id", sa.String(36), sa.ForeignKey("exams.id"), nullable=True),
        sa.Column("exam_date", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

def downgrade():
    op.drop_table("exam_import_sessions")
```

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/exam_import/models.py alembic/versions/ tests/
git commit -m "feat(exam-import): ExamImportSession model + migration"
```

---

## Task 3: 导入服务（service.py）— 预览 + 学生匹配

**Files:**
- Create: `src/edu_cloud/modules/exam_import/service.py`
- Test: `tests/test_modules/test_exam_import/test_service.py`

- [ ] **Step 1: 写 failing test — 学生匹配逻辑**

```python
# tests/test_modules/test_exam_import/test_service.py
import pytest
from edu_cloud.modules.exam_import.service import match_students
from edu_cloud.modules.exam_import.parser import StudentScore


@pytest.mark.asyncio
async def test_match_students_by_number(db):
    """精确匹配 student_number"""
    from edu_cloud.modules.student.models import Student, Class
    school_id = "test-school-001"
    cls = Class(name="2301班", grade="高一", school_id=school_id)
    db.add(cls)
    await db.flush()
    stu = Student(name="张三", student_number="3722230101", class_id=cls.id,
                  school_id=school_id, grade="高一")
    db.add(stu)
    await db.commit()

    parsed = [StudentScore(student_key="3722230101", student_name="张三", class_name="2301")]
    result = await match_students(db, parsed, school_id)

    assert len(result.matched) == 1
    assert result.matched[0].edu_student_id == stu.id
    assert len(result.unmatched) == 0


@pytest.mark.asyncio
async def test_match_students_fallback_name_class(db):
    """student_number 不匹配时回退到 姓名+班级"""
    from edu_cloud.modules.student.models import Student, Class
    school_id = "test-school-002"
    cls = Class(name="2301班", grade="高一", school_id=school_id)
    db.add(cls)
    await db.flush()
    stu = Student(name="李四", student_number="OLD_NUMBER", class_id=cls.id,
                  school_id=school_id, grade="高一")
    db.add(stu)
    await db.commit()

    parsed = [StudentScore(student_key="NEW_NUMBER", student_name="李四", class_name="2301")]
    result = await match_students(db, parsed, school_id)

    assert len(result.matched) == 1
    assert result.matched[0].edu_student_id == stu.id


@pytest.mark.asyncio
async def test_match_students_unmatched(db):
    """无法匹配的学生归入 unmatched"""
    parsed = [StudentScore(student_key="UNKNOWN", student_name="不存在", class_name="9999")]
    result = await match_students(db, parsed, "no-school")

    assert len(result.matched) == 0
    assert len(result.unmatched) == 1
```

- [ ] **Step 2: `pytest tests/test_modules/test_exam_import/test_service.py -v` → FAIL**

- [ ] **Step 3: 实现 match_students**

```python
# src/edu_cloud/modules/exam_import/service.py
"""外部考试导入业务逻辑。"""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam_import.parser import (
    ParsedExamData, ParsedSubjectData, StudentScore, QuestionDef,
)
from edu_cloud.modules.student.models import Student, Class

logger = logging.getLogger(__name__)


@dataclass
class MatchedStudent:
    parsed: StudentScore
    edu_student_id: str
    edu_class_id: str | None = None
    match_method: str = ""  # number / name_class


@dataclass
class MatchResult:
    matched: list[MatchedStudent] = field(default_factory=list)
    unmatched: list[StudentScore] = field(default_factory=list)
    ambiguous: list[tuple[StudentScore, list[str]]] = field(default_factory=list)  # F5: (parsed, candidate_ids)


def _normalize_class(raw: str) -> str:
    m = re.search(r"(\d{4})", raw)
    return m.group(1) if m else raw.strip()


async def match_students(
    db: AsyncSession,
    students: list[StudentScore],
    school_id: str,
) -> MatchResult:
    result = MatchResult()

    # 预加载本校全部学生
    rows = await db.execute(
        select(Student.id, Student.student_number, Student.name, Student.class_id, Class.name.label("class_name"))
        .outerjoin(Class, Class.id == Student.class_id)
        .where(Student.school_id == school_id)
    )
    all_students = rows.all()

    by_number: dict[str, tuple] = {}
    by_name_class: dict[tuple[str, str], list[tuple]] = {}  # F5: multimap 检测重复
    for row in all_students:
        by_number[row.student_number] = row
        if row.class_name:
            norm_cls = _normalize_class(row.class_name)
            by_name_class.setdefault((row.name, norm_cls), []).append(row)

    for parsed in students:
        # 1. 精确匹配 student_number
        db_row = by_number.get(parsed.student_key)
        if db_row:
            result.matched.append(MatchedStudent(
                parsed=parsed, edu_student_id=db_row.id,
                edu_class_id=db_row.class_id, match_method="number",
            ))
            continue

        # 2. 回退：姓名 + 班级（F5: 唯一性检查）
        norm_cls = _normalize_class(parsed.class_name) if parsed.class_name else ""
        candidates = by_name_class.get((parsed.student_name, norm_cls), [])
        if len(candidates) == 1:
            db_row = candidates[0]
            result.matched.append(MatchedStudent(
                parsed=parsed, edu_student_id=db_row.id,
                edu_class_id=db_row.class_id, match_method="name_class",
            ))
            continue
        elif len(candidates) > 1:
            # F5: 同名同班多人 → 标记 ambiguous，归入 unmatched
            result.ambiguous.append((parsed, [r.id for r in candidates]))
            continue

        result.unmatched.append(parsed)

    return result
```

- [ ] **Step 4: `pytest tests/test_modules/test_exam_import/test_service.py -v` → 3 PASS**

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/exam_import/service.py tests/test_modules/test_exam_import/test_service.py
git commit -m "feat(exam-import): student matching service — number + name_class fallback"
```

---

## Task 4: 导入服务 — commit 写入（Question + StudentAnswer + GradingResult + ExamResult）

> **Review Fix F1/F3/F4/F6/F8:** 幂等 upsert + ExamResult 写入 + 满分强校验 + source 区分 + 缺考处理

**Files:**
- Modify: `src/edu_cloud/modules/exam_import/service.py`
- Test: `tests/test_modules/test_exam_import/test_service.py`

- [ ] **Step 1: 写 failing test — commit 完整链路（含 ExamResult + source 区分）**

```python
# tests/test_modules/test_exam_import/test_service.py（追加）
from edu_cloud.modules.exam_import.service import commit_import
from edu_cloud.modules.exam_import.parser import ParsedExamData, ParsedSubjectData, QuestionDef, StudentScore
from edu_cloud.modules.exam.models import Exam, Subject, Question, ExamResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult


@pytest.mark.asyncio
async def test_commit_import_creates_full_chain(db):
    """commit 写入 Exam → Subject → Question → StudentAnswer → GradingResult → ExamResult"""
    from edu_cloud.modules.student.models import Student, Class
    school_id = "test-school-commit"

    cls = Class(name="2301班", grade="高一", school_id=school_id)
    db.add(cls)
    await db.flush()
    stu = Student(name="张三", student_number="001", class_id=cls.id,
                  school_id=school_id, grade="高一")
    db.add(stu)
    await db.commit()

    parsed = ParsedExamData(subjects=[
        ParsedSubjectData(
            subject_name="语文", subject_code="YW",
            questions=[
                QuestionDef(name="选择1", question_type="choice", max_score=2, correct_answer="A"),
                QuestionDef(name="17", question_type="essay", max_score=12),
            ],
            students=[
                StudentScore(
                    student_key="001", student_name="张三", class_name="2301",
                    raw_total=110, converted_score=None, class_rank=1, school_rank=1,
                    question_scores={"选择1": 2.0, "17": 8.0},
                ),
            ],
        ),
    ])

    matched = [MatchedStudent(
        parsed=parsed.subjects[0].students[0],
        edu_student_id=stu.id, edu_class_id=cls.id, match_method="number",
    )]

    result = await commit_import(
        db, parsed=parsed, matched_students={"001": matched[0]},
        school_id=school_id, exam_name="测试月考",
        exam_type="月考", grade_scope="高一", import_mode="questions",
    )

    assert result["exam_id"] is not None
    assert result["questions_created"] == 2
    assert result["answers_created"] == 2
    assert result["grading_results_created"] == 2
    assert result["exam_results_created"] == 1

    # 验证链路完整
    exam = (await db.execute(select(Exam).where(Exam.id == result["exam_id"]))).scalar_one()
    assert exam.source == "import_questions"

    # F3: ExamResult 已写入
    er = (await db.execute(select(ExamResult).where(ExamResult.exam_id == exam.id))).scalar_one()
    assert er.total_score == 110
    assert er.rank_in_class == 1

    # F6: GradingResult.source 区分模式
    grs = (await db.execute(select(GradingResult).where(GradingResult.school_id == school_id))).scalars().all()
    assert all(gr.source == "import_questions" for gr in grs)


@pytest.mark.asyncio
async def test_commit_import_upsert_idempotent(db):
    """F1: 同一考试重复导入不报错，分数被更新"""
    from edu_cloud.modules.student.models import Student, Class
    school_id = "test-school-upsert"
    cls = Class(name="2301班", grade="高一", school_id=school_id)
    db.add(cls)
    await db.flush()
    stu = Student(name="张三", student_number="U001", class_id=cls.id,
                  school_id=school_id, grade="高一")
    db.add(stu)
    await db.commit()

    def _make_parsed(score):
        return ParsedExamData(subjects=[ParsedSubjectData(
            subject_name="数学", subject_code="SX",
            questions=[QuestionDef(name="1", question_type="choice", max_score=3)],
            students=[StudentScore(
                student_key="U001", student_name="张三", class_name="2301",
                raw_total=score, question_scores={"1": score},
            )],
        )])

    matched = {"U001": MatchedStudent(
        parsed=_make_parsed(2).subjects[0].students[0],
        edu_student_id=stu.id, edu_class_id=cls.id, match_method="number",
    )}

    # 第一次导入
    r1 = await commit_import(db, parsed=_make_parsed(2), matched_students=matched,
                              school_id=school_id, exam_name="重复考试",
                              exam_type="月考", grade_scope="高一", import_mode="questions")

    # 第二次导入（同考试，分数变化）— 传入已有 exam_id 触发 upsert
    matched["U001"].parsed = _make_parsed(3).subjects[0].students[0]
    r2 = await commit_import(db, parsed=_make_parsed(3), matched_students=matched,
                              school_id=school_id, exam_name="重复考试",
                              exam_type="月考", grade_scope="高一", import_mode="questions",
                              existing_exam_id=r1["exam_id"])

    # 验证分数已更新，不是重复创建
    answers = (await db.execute(
        select(StudentAnswer).where(StudentAnswer.exam_id == r1["exam_id"])
    )).scalars().all()
    assert len(answers) == 1  # 不是 2
    assert answers[0].score == 3.0  # 已更新


@pytest.mark.asyncio
async def test_commit_absent_student(db):
    """F8: 缺考学生写入 is_absent=True"""
    from edu_cloud.modules.student.models import Student, Class
    school_id = "test-school-absent"
    cls = Class(name="2301班", grade="高一", school_id=school_id)
    db.add(cls)
    await db.flush()
    stu = Student(name="张三", student_number="A001", class_id=cls.id,
                  school_id=school_id, grade="高一")
    db.add(stu)
    await db.commit()

    # 第一次：正常得分
    parsed_normal = ParsedExamData(subjects=[ParsedSubjectData(
        subject_name="语文", subject_code="YW",
        questions=[QuestionDef(name="1", question_type="choice", max_score=2)],
        students=[StudentScore(
            student_key="A001", student_name="张三", class_name="2301",
            raw_total=2, question_scores={"1": 2.0},
        )],
    )])
    matched = {"A001": MatchedStudent(
        parsed=parsed_normal.subjects[0].students[0],
        edu_student_id=stu.id, edu_class_id=cls.id, match_method="number",
    )}
    r1 = await commit_import(db, parsed=parsed_normal, matched_students=matched,
                              school_id=school_id, exam_name="缺考测试",
                              exam_type="月考", grade_scope="高一", import_mode="questions")

    # 验证正常导入
    answers = (await db.execute(
        select(StudentAnswer).where(StudentAnswer.exam_id == r1["exam_id"])
    )).scalars().all()
    assert len(answers) == 1
    assert answers[0].score == 2.0
    grs = (await db.execute(select(GradingResult).where(GradingResult.answer_id == answers[0].id))).scalars().all()
    assert grs[0].final_score == 2.0

    # 第二次：重导为缺考（正常→缺考互转）
    parsed_absent = ParsedExamData(subjects=[ParsedSubjectData(
        subject_name="语文", subject_code="YW",
        questions=[QuestionDef(name="1", question_type="choice", max_score=2)],
        students=[StudentScore(
            student_key="A001", student_name="张三", class_name="2301",
            is_absent=True, question_scores={},
        )],
    )])
    matched["A001"].parsed = parsed_absent.subjects[0].students[0]
    await commit_import(db, parsed=parsed_absent, matched_students=matched,
                        school_id=school_id, exam_name="缺考测试",
                        exam_type="月考", grade_scope="高一", import_mode="questions",
                        existing_exam_id=r1["exam_id"])

    # 验证缺考：StudentAnswer.is_absent + GradingResult.final_score=None
    await db.expire_all()
    answers = (await db.execute(
        select(StudentAnswer).where(StudentAnswer.exam_id == r1["exam_id"])
    )).scalars().all()
    assert len(answers) == 1
    assert answers[0].is_absent is True
    assert answers[0].score is None
    grs = (await db.execute(select(GradingResult).where(GradingResult.answer_id == answers[0].id))).scalars().all()
    assert grs[0].final_score is None
```

- [ ] **Step 2: `pytest tests/test_modules/test_exam_import/test_service.py::test_commit_import_creates_full_chain -v` → FAIL**

- [ ] **Step 3: 实现 commit_import（含 F1 upsert + F3 ExamResult + F6 source + F8 缺考）**

```python
# 添加到 src/edu_cloud/modules/exam_import/service.py

import json
import uuid
from sqlalchemy.exc import IntegrityError
from edu_cloud.modules.exam.models import Exam, Subject, Question, ExamResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult


def _new_id() -> str:
    return str(uuid.uuid4())


async def commit_import(
    db: AsyncSession,
    *,
    parsed: ParsedExamData,
    matched_students: dict[str, MatchedStudent],
    school_id: str,
    exam_name: str,
    exam_type: str,
    grade_scope: str,
    import_mode: str,
    exam_date: str | None = None,
    existing_exam_id: str | None = None,  # F1: upsert 时传入已有 exam_id
) -> dict:
    source = f"import_{import_mode}"  # F6: import_questions / import_totals

    # F1: 幂等 — 复用已有 exam 或新建
    if existing_exam_id:
        exam_row = await db.execute(select(Exam).where(Exam.id == existing_exam_id))
        exam = exam_row.scalar_one()
    else:
        exam = Exam(
            id=_new_id(), name=exam_name, card_title=exam_name,
            status="completed", exam_type=exam_type, grade_scope=grade_scope,
            school_id=school_id, source=source,
        )
        if exam_date:
            exam.exam_date = exam_date
        db.add(exam)
    await db.flush()

    total_questions = 0
    total_answers = 0
    total_grading = 0
    total_exam_results = 0

    # F3: 收集每学生总分用于写 ExamResult
    student_totals: dict[str, dict] = {}  # edu_student_id → {total, class_rank, school_rank}

    for subj_data in parsed.subjects:
        # F1: upsert subject
        existing_subj = await db.execute(
            select(Subject).where(Subject.exam_id == exam.id, Subject.code == subj_data.subject_code)
        )
        subject = existing_subj.scalar_one_or_none()
        if not subject:
            subject = Subject(
                id=_new_id(), exam_id=exam.id,
                name=subj_data.subject_name, code=subj_data.subject_code,
                school_id=school_id,
            )
            db.add(subject)
            await db.flush()

        # F1: upsert questions
        q_map: dict[str, Question] = {}
        for qdef in subj_data.questions:
            existing_q = await db.execute(
                select(Question).where(Question.subject_id == subject.id, Question.name == qdef.name)
            )
            q = existing_q.scalar_one_or_none()
            if q:
                q.max_score = qdef.max_score
                q.correct_answer = qdef.correct_answer or q.correct_answer
                q.question_type = qdef.question_type
            else:
                q = Question(
                    id=_new_id(), subject_id=subject.id,
                    name=qdef.name, question_type=qdef.question_type,
                    max_score=qdef.max_score,
                    correct_answer=qdef.correct_answer,
                    school_id=school_id,
                )
                db.add(q)
                total_questions += 1
            q_map[qdef.name] = q
        await db.flush()

        for stu_score in subj_data.students:
            match = matched_students.get(stu_score.student_key)
            if not match:
                continue

            # F8: 缺考学生 — 每题 upsert is_absent=True + 清 GradingResult
            if stu_score.is_absent:
                for q_name, q in q_map.items():
                    existing_sa = await db.execute(
                        select(StudentAnswer).where(
                            StudentAnswer.exam_id == exam.id,
                            StudentAnswer.student_id == match.edu_student_id,
                            StudentAnswer.question_id == q.id,
                        )
                    )
                    sa = existing_sa.scalar_one_or_none()
                    if sa:
                        sa.is_absent = True
                        sa.score = None
                        sa.detected_answer = None
                        # 清除关联的 GradingResult（正常→缺考互转）
                        existing_gr = await db.execute(
                            select(GradingResult).where(GradingResult.answer_id == sa.id)
                        )
                        gr = existing_gr.scalar_one_or_none()
                        if gr:
                            gr.final_score = None
                            gr.status = "confirmed"
                            gr.source = source
                    else:
                        sa = StudentAnswer(
                            id=_new_id(), exam_id=exam.id, subject_id=subject.id,
                            student_id=match.edu_student_id, question_id=q.id,
                            score=None, is_absent=True,
                            question_type=q.question_type, school_id=school_id,
                        )
                        db.add(sa)
                        total_answers += 1
                continue

            for q_name, score in stu_score.question_scores.items():
                q = q_map.get(q_name)
                if not q:
                    continue

                detected = None
                if q.correct_answer and score >= q.max_score:
                    detected = q.correct_answer

                # F1/F8: upsert StudentAnswer（支持缺考→正常互转）
                existing_sa = await db.execute(
                    select(StudentAnswer).where(
                        StudentAnswer.exam_id == exam.id,
                        StudentAnswer.student_id == match.edu_student_id,
                        StudentAnswer.question_id == q.id,
                    )
                )
                sa = existing_sa.scalar_one_or_none()
                if sa:
                    sa.score = score
                    sa.detected_answer = detected
                    sa.is_absent = False  # F8: 重导时清除缺考标记
                else:
                    sa = StudentAnswer(
                        id=_new_id(), exam_id=exam.id, subject_id=subject.id,
                        student_id=match.edu_student_id, question_id=q.id,
                        score=score, detected_answer=detected,
                        question_type=q.question_type, school_id=school_id,
                    )
                    db.add(sa)
                    total_answers += 1
                await db.flush()

                # F1/F6: upsert GradingResult（补全所有字段）
                existing_gr = await db.execute(
                    select(GradingResult).where(GradingResult.answer_id == sa.id)
                )
                gr = existing_gr.scalar_one_or_none()
                if gr:
                    gr.final_score = score
                    gr.max_score = q.max_score
                    gr.status = "confirmed"
                    gr.source = source  # F6: 保持正确的 source
                else:
                    gr = GradingResult(
                        id=_new_id(), answer_id=sa.id, question_id=q.id,
                        school_id=school_id, final_score=score,
                        max_score=q.max_score, status="confirmed", source=source,
                    )
                    db.add(gr)
                    total_grading += 1

            # F3: 收集总分
            if stu_score.raw_total is not None:
                if match.edu_student_id not in student_totals:
                    student_totals[match.edu_student_id] = {
                        "total": 0, "class_rank": stu_score.class_rank,
                        "school_rank": stu_score.school_rank,
                    }
                student_totals[match.edu_student_id]["total"] += stu_score.raw_total

    # F3: 写 ExamResult
    for stu_id, info in student_totals.items():
        existing_er = await db.execute(
            select(ExamResult).where(ExamResult.exam_id == exam.id, ExamResult.student_id == stu_id)
        )
        er = existing_er.scalar_one_or_none()
        if er:
            er.total_score = info["total"]
            er.rank_in_class = info["class_rank"]
            er.rank_in_grade = info["school_rank"]
        else:
            er = ExamResult(
                id=_new_id(), exam_id=exam.id, student_id=stu_id,
                school_id=school_id, total_score=info["total"],
                detail_scores=json.dumps({"source": source}),
                rank_in_class=info["class_rank"], rank_in_grade=info["school_rank"],
            )
            db.add(er)
            total_exam_results += 1

    await db.commit()

    return {
        "exam_id": exam.id,
        "subjects_created": len(parsed.subjects),
        "questions_created": total_questions,
        "answers_created": total_answers,
        "grading_results_created": total_grading,
        "exam_results_created": total_exam_results,
    }
```

- [ ] **Step 4: `pytest tests/test_modules/test_exam_import/test_service.py -v` → 4 PASS**

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/exam_import/service.py tests/test_modules/test_exam_import/test_service.py
git commit -m "feat(exam-import): commit service — writes Question+StudentAnswer+GradingResult chain"
```

---

## Task 5: Post-import pipeline — snapshot + error_book（含赋分保留）

> **Review Fix F2/F9:** 总分模式跳过 error_book；snapshot 覆盖后同步更新 score_rate

**Files:**
- Modify: `src/edu_cloud/modules/exam_import/service.py`（添加 trigger_post_import_pipeline）
- Modify: `src/edu_cloud/modules/pipeline/service.py`（generate_exam_snapshots 支持保留导入的赋分/排名）
- Test: `tests/test_modules/test_exam_import/test_service.py`

- [ ] **Step 1: 写 failing test — pipeline 触发后 snapshot 保留导入赋分**

```python
# tests/test_modules/test_exam_import/test_service.py（追加）
from edu_cloud.modules.profile.models import StudentExamSnapshot
from edu_cloud.modules.bank.models import StudentErrorBook


@pytest.mark.asyncio
async def test_post_import_pipeline_preserves_converted_score(db):
    """pipeline 生成 snapshot 后，导入的赋分/排名被保留"""
    from edu_cloud.modules.student.models import Student, Class
    from edu_cloud.modules.exam_import.service import commit_import, run_post_import_pipeline

    school_id = "test-school-pipeline"
    cls = Class(name="2301班", grade="高一", school_id=school_id)
    db.add(cls)
    await db.flush()
    stu = Student(name="张三", student_number="P001", class_id=cls.id,
                  school_id=school_id, grade="高一")
    db.add(stu)
    await db.commit()

    parsed = ParsedExamData(subjects=[
        ParsedSubjectData(
            subject_name="生物", subject_code="SW",
            questions=[QuestionDef(name="选择1", question_type="choice", max_score=2)],
            students=[StudentScore(
                student_key="P001", student_name="张三", class_name="2301",
                raw_total=70, converted_score=85, grade_level="A",
                class_rank=1, school_rank=1,
                question_scores={"选择1": 2.0},
            )],
        ),
    ])

    matched = {"P001": MatchedStudent(
        parsed=parsed.subjects[0].students[0],
        edu_student_id=stu.id, edu_class_id=cls.id, match_method="number",
    )}
    result = await commit_import(
        db, parsed=parsed, matched_students=matched,
        school_id=school_id, exam_name="联考",
        exam_type="联考", grade_scope="高一", import_mode="questions",
    )

    await run_post_import_pipeline(db, exam_id=result["exam_id"], school_id=school_id, parsed=parsed, matched_students=matched)

    snap = (await db.execute(
        select(StudentExamSnapshot).where(
            StudentExamSnapshot.exam_id == result["exam_id"],
            StudentExamSnapshot.subject_code == "SW",
        )
    )).scalar_one()

    assert snap.converted_score == 85
    assert snap.total_score == 2.0  # 小题分求和
```

- [ ] **Step 2: 实现 run_post_import_pipeline**

```python
# 添加到 src/edu_cloud/modules/exam_import/service.py

from edu_cloud.modules.pipeline.service import (
    populate_error_books, generate_exam_snapshots, update_error_patterns,
)
from edu_cloud.modules.profile.models import StudentExamSnapshot


async def run_post_import_pipeline(
    db: AsyncSession,
    *,
    exam_id: str,
    school_id: str,
    parsed: ParsedExamData,
    matched_students: dict[str, MatchedStudent],
) -> dict:
    # 1. snapshot 始终生成
    snapshots = await generate_exam_snapshots(db, exam_id=exam_id, school_id=school_id)

    # F2: 总分模式不生成错题库（显式用 import_mode 判断，避免混合数据误跳）
    errors = 0
    patterns = 0
    is_totals = all(
        q.question_type == "synthetic"
        for subj in parsed.subjects for q in subj.questions
    )
    if not is_totals:
        errors = await populate_error_books(db, exam_id=exam_id, school_id=school_id)
        patterns = await update_error_patterns(db, exam_id=exam_id, school_id=school_id)

    # 2. 用导入值覆盖 snapshot 的赋分/排名（官方数据优先于计算值）
    overrides = 0
    for subj_data in parsed.subjects:
        for stu_score in subj_data.students:
            match = matched_students.get(stu_score.student_key)
            if not match:
                continue

            if stu_score.converted_score is None and stu_score.class_rank is None:
                continue

            row = await db.execute(
                select(StudentExamSnapshot).where(
                    StudentExamSnapshot.student_id == match.edu_student_id,
                    StudentExamSnapshot.exam_id == exam_id,
                    StudentExamSnapshot.subject_code == subj_data.subject_code,
                    StudentExamSnapshot.school_id == school_id,
                )
            )
            snap = row.scalar_one_or_none()
            if not snap:
                continue

            if stu_score.converted_score is not None:
                snap.converted_score = stu_score.converted_score
            if stu_score.grade_level is not None:
                snap.error_summary = snap.error_summary or {}
                snap.error_summary["grade_level"] = stu_score.grade_level
            if stu_score.class_rank is not None:
                snap.class_rank = stu_score.class_rank
            if stu_score.school_rank is not None:
                snap.grade_rank = stu_score.school_rank
            # F9: 如果导入了官方原始分，同步更新 score_rate
            if stu_score.raw_total is not None and snap.max_score and snap.max_score > 0:
                snap.total_score = stu_score.raw_total
                snap.score_rate = round(stu_score.raw_total / snap.max_score, 4)
            overrides += 1

    await db.commit()

    return {"snapshots": snapshots, "error_books": errors, "error_patterns": patterns, "overrides": overrides}
```

- [ ] **Step 3: `pytest tests/test_modules/test_exam_import/test_service.py -v` → 5 PASS**

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/modules/exam_import/service.py tests/test_modules/test_exam_import/test_service.py
git commit -m "feat(exam-import): post-import pipeline — snapshot+error_book+赋分保留"
```

---

## Task 6: API 端点（router.py）+ 模块注册

**Files:**
- Create: `src/edu_cloud/modules/exam_import/router.py`
- Modify: `src/edu_cloud/api/router_registry.py`
- Modify: `src/edu_cloud/core/permissions.py`
- Test: `tests/test_modules/test_exam_import/test_router.py`

- [ ] **Step 1: 添加权限枚举**

```python
# src/edu_cloud/core/permissions.py — 在 Permission 枚举中添加：
IMPORT_EXAMS = "import_exams"
```

并在 RBAC 映射中给 `academic_director` 和 `school_admin` 角色授予此权限。

- [ ] **Step 2: 写 router**

```python
# src/edu_cloud/modules/exam_import/router.py
"""外部考试导入 API。"""
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import get_db, get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.exam_import.models import ExamImportSession
from edu_cloud.modules.exam_import import parser, service
from edu_cloud.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/exam-imports", tags=["exam-import"])


@router.post("", status_code=201)
async def create_import(
    file: UploadFile = File(...),
    exam_name: str = Form(...),
    exam_type: str = Form(...),
    grade_scope: str = Form(...),
    import_mode: str = Form("questions"),
    exam_date: str = Form(""),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.IMPORT_EXAMS)),
):
    role = current["current_role"]
    school_id = role.school_id
    if not school_id:
        raise HTTPException(400, "Cross-school import not supported")

    if import_mode not in ("questions", "totals"):
        raise HTTPException(400, f"Invalid import_mode: {import_mode}")

    # F10: 安全校验
    allowed_ext = {".xlsx", ".xls", ".zip"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_ext:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    # F10: UUID 文件名防重复和路径注入
    import uuid as _uuid
    safe_name = f"{_uuid.uuid4().hex}{ext}"
    upload_dir = Path(settings.UPLOAD_DIR) / school_id / "exam-imports"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / safe_name
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 解析（支持 xlsx 和 zip）
    if ext == ".zip":
        parsed = parser.parse_zip(file_path)
    elif import_mode == "questions":
        parsed = parser.parse_question_scores_xlsx(file_path)
    else:
        parsed = parser.parse_totals_xlsx(file_path)

    if not parsed.subjects:
        raise HTTPException(400, f"No subjects found. Warnings: {parsed.warnings}")

    # 匹配学生
    all_students = []
    for subj in parsed.subjects:
        all_students.extend(subj.students)
    # 去重
    seen = set()
    unique_students = []
    for s in all_students:
        if s.student_key not in seen:
            seen.add(s.student_key)
            unique_students.append(s)

    match_result = await service.match_students(db, unique_students, school_id)

    # 创建 session
    import uuid
    session = ExamImportSession(
        id=str(uuid.uuid4()),
        school_id=school_id,
        exam_name=exam_name,
        exam_type=exam_type,
        grade_scope=grade_scope,
        import_mode=import_mode,
        status="previewing",
        file_path=str(file_path),
        exam_date=exam_date or None,
        preview_data={
            "subjects": [
                {
                    "name": s.subject_name, "code": s.subject_code,
                    "questions": [{"name": q.name, "type": q.question_type, "max_score": q.max_score, "answer": q.correct_answer} for q in s.questions],
                    "student_count": len(s.students),
                }
                for s in parsed.subjects
            ],
            "match_summary": {
                "matched": len(match_result.matched),
                "unmatched": len(match_result.unmatched),
                "ambiguous": len(match_result.ambiguous),  # F5
                "unmatched_names": [s.student_name for s in match_result.unmatched[:20]],
                "ambiguous_names": [(s.student_name, ids) for s, ids in match_result.ambiguous[:10]],  # F5
            },
            # F4: 标记所有推断的满分（教师需在 mapping 阶段确认）
            "questions_need_confirm": [
                {"subject": s.subject_name, "question": q.name, "inferred_max": q.max_score,
                 "inferred_type": q.question_type, "is_inferred": q.max_score_inferred}
                for s in parsed.subjects for q in s.questions
                if q.max_score_inferred
            ],
            "warnings": parsed.warnings,
        },
    )
    db.add(session)
    await db.commit()

    return {
        "import_id": session.id,
        "status": session.status,
        "preview": session.preview_data,
    }


@router.patch("/{import_id}/mapping")
async def update_mapping(
    import_id: str,
    mapping: dict,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.IMPORT_EXAMS)),
):
    from sqlalchemy import select
    role = current["current_role"]
    session = (await db.execute(
        select(ExamImportSession).where(
            ExamImportSession.id == import_id,
            ExamImportSession.school_id == role.school_id,  # 跨校隔离
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Import session not found")
    if session.status != "previewing":
        raise HTTPException(400, f"Cannot update mapping in status: {session.status}")

    session.mapping_data = mapping
    await db.commit()
    return {"status": "ok"}


@router.post("/{import_id}/commit")
async def commit_import_endpoint(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.IMPORT_EXAMS)),
):
    from sqlalchemy import select
    session = (await db.execute(
        select(ExamImportSession).where(
            ExamImportSession.id == import_id,
            ExamImportSession.school_id == role.school_id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Import session not found")
    if session.status != "previewing":
        raise HTTPException(400, f"Cannot commit in status: {session.status}")

    role = current["current_role"]

    # 重新解析文件（支持 xlsx 和 zip）
    fp = Path(session.file_path)
    if fp.suffix.lower() == ".zip":
        parsed = parser.parse_zip(fp)
    elif session.import_mode == "questions":
        parsed = parser.parse_question_scores_xlsx(fp)
    else:
        parsed = parser.parse_totals_xlsx(fp)

    # 重新匹配
    all_students = []
    for subj in parsed.subjects:
        all_students.extend(subj.students)
    seen = set()
    unique = []
    for s in all_students:
        if s.student_key not in seen:
            seen.add(s.student_key)
            unique.append(s)
    match_result = await service.match_students(db, unique, session.school_id)
    matched_map = {m.parsed.student_key: m for m in match_result.matched}

    # 写入
    try:
        result = await service.commit_import(
            db, parsed=parsed, matched_students=matched_map,
            school_id=session.school_id, exam_name=session.exam_name,
            exam_type=session.exam_type, grade_scope=session.grade_scope,
            import_mode=session.import_mode, exam_date=session.exam_date,
        )

        # pipeline
        pipeline_result = await service.run_post_import_pipeline(
            db, exam_id=result["exam_id"], school_id=session.school_id,
            parsed=parsed, matched_students=matched_map,
        )

        session.status = "committed"
        session.exam_id = result["exam_id"]
        session.committed_by = current.get("user_id")
        session.result_summary = {**result, "pipeline": pipeline_result}
        await db.commit()

        return {"status": "committed", "result": session.result_summary}

    except Exception as e:
        session.status = "failed"
        session.result_summary = {"error": str(e)}
        await db.commit()
        raise HTTPException(500, f"Import failed: {e}")


@router.get("/{import_id}")
async def get_import(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.IMPORT_EXAMS)),
):
    from sqlalchemy import select
    role = current["current_role"]
    session = (await db.execute(
        select(ExamImportSession).where(
            ExamImportSession.id == import_id,
            ExamImportSession.school_id == role.school_id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(404)
    return {
        "import_id": session.id, "status": session.status,
        "exam_name": session.exam_name, "exam_id": session.exam_id,
        "preview": session.preview_data, "result": session.result_summary,
    }


@router.delete("/{import_id}")
async def cancel_import(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.IMPORT_EXAMS)),
):
    from sqlalchemy import select
    role = current["current_role"]
    session = (await db.execute(
        select(ExamImportSession).where(
            ExamImportSession.id == import_id,
            ExamImportSession.school_id == role.school_id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(404)
    if session.status == "committed":
        raise HTTPException(400, "Cannot cancel committed import")
    session.status = "cancelled"
    await db.commit()
    return {"status": "cancelled"}
```

- [ ] **Step 3: 注册路由**

```python
# src/edu_cloud/api/router_registry.py — MODULE_ROUTERS 末尾添加：
    # exam-import
    ("edu_cloud.modules.exam_import.router", "router"),
```

- [ ] **Step 4: 写 router 集成测试**

```python
# tests/test_modules/test_exam_import/test_router.py
import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_create_import_endpoint(client, admin_headers, seed_school, sample_question_scores_xlsx):
    """上传 xlsx → 返回 preview"""
    with open(sample_question_scores_xlsx, "rb") as f:
        resp = await client.post(
            "/api/v1/exam-imports",
            files={"file": ("生物_小题分.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={
                "exam_name": "测试联考",
                "exam_type": "联考",
                "grade_scope": "高一",
                "import_mode": "questions",
            },
            headers=admin_headers,
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "previewing"
    assert data["import_id"]
    assert len(data["preview"]["subjects"]) == 1
```

- [ ] **Step 5: `pytest tests/test_modules/test_exam_import/test_router.py -v` → PASS**

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/exam_import/router.py src/edu_cloud/api/router_registry.py src/edu_cloud/core/permissions.py tests/
git commit -m "feat(exam-import): API endpoints — upload/preview/commit/cancel + module registration"
```

---

## Task 7: 前端导入页面

**Files:**
- Create: `frontend/src/pages/ExamImportPage.vue`
- Create: `frontend/src/api/examImport.js`
- Modify: `frontend/src/config/sidebarConfig.js`
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: API 调用层**

```javascript
// frontend/src/api/examImport.js
import client from './client'

export function createImport(formData) {
  return client.post('/exam-imports', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function updateMapping(importId, mapping) {
  return client.patch(`/exam-imports/${importId}/mapping`, mapping)
}

export function commitImport(importId) {
  return client.post(`/exam-imports/${importId}/commit`)
}

export function getImport(importId) {
  return client.get(`/exam-imports/${importId}`)
}

export function cancelImport(importId) {
  return client.delete(`/exam-imports/${importId}`)
}
```

- [ ] **Step 2: 导入页面（上传→预览→确认→结果 四步）**

创建 `frontend/src/pages/ExamImportPage.vue`，使用 Naive UI 的 `n-steps` + `n-upload` + `n-data-table` 组件。

四个步骤：
1. **上传**：选文件 + 填考试名称/类型/年级/日期 + 选模式（小题分/总分）
2. **预览**：展示识别的科目/题目列表 + 学生匹配结果（已匹配/未匹配）
3. **确认**：汇总即将写入的数据量 + 确认按钮
4. **结果**：导入成功/失败统计

- [ ] **Step 3: 注册路由和侧边栏**

```javascript
// frontend/src/router/index.js — AppShell children 中添加：
{
  path: '/exam-import',
  name: 'ExamImport',
  component: () => import('../pages/ExamImportPage.vue'),
  meta: { permission: 'import_exams', title: '成绩导入' },
},
```

```javascript
// frontend/src/config/sidebarConfig.js — 考试阅卷板块添加：
{ label: '成绩导入', key: '/exam-import', icon: 'UploadOutlined', permission: 'import_exams' },
```

- [ ] **Step 4: vite build + 验证页面可访问**

```bash
cd /home/ops/projects/edu-cloud/frontend && npx vite build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ExamImportPage.vue frontend/src/api/examImport.js frontend/src/config/sidebarConfig.js frontend/src/router/index.js
git commit -m "feat(exam-import): frontend import page — upload/preview/confirm/result flow"
```

---

## Task 8: 用真实数据端到端验证

**Files:**
- Test: `tests/test_modules/test_exam_import/test_e2e.py`

- [ ] **Step 1: 用真实天一大联考数据验证 parser**

```python
# tests/test_modules/test_exam_import/test_e2e.py
import pytest
from pathlib import Path
from edu_cloud.modules.exam_import.parser import parse_question_scores_xlsx

REAL_DATA = Path("/tmp/exam-bio/生物/生物_小题分.xlsx")

@pytest.mark.skipif(not REAL_DATA.exists(), reason="真实数据不存在")
def test_parse_real_tianyi_data():
    result = parse_question_scores_xlsx(REAL_DATA)
    assert len(result.subjects) == 1
    subj = result.subjects[0]
    assert subj.subject_name == "生物"
    assert subj.subject_code == "SW"
    assert len(subj.questions) == 21  # 选择1-16 + 17-21
    assert len(subj.students) >= 190
    # 验证第一个学生
    s1 = subj.students[0]
    assert s1.student_name == "惠应之"
    assert s1.raw_total == 70
    assert s1.converted_score == 91
    assert s1.grade_level == "A"
```

- [ ] **Step 2: 运行全部测试确认无回归**

```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_modules/test_exam_import/ -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_modules/test_exam_import/test_e2e.py
git commit -m "test(exam-import): e2e validation with real 天一大联考 data"
```

---

## 任务依赖关系

```
Task 1 (parser)
  → Task 3 (service: 匹配)
    → Task 4 (service: commit)
      → Task 5 (pipeline)
        → Task 6 (router + 注册)
          → Task 7 (前端)
            → Task 8 (e2e)
Task 2 (model + migration) → Task 6 (router 依赖 model)
```
