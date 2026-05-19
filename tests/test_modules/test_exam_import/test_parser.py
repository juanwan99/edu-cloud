"""Tests for exam_import Excel parser."""

import zipfile

import openpyxl
import pytest

from edu_cloud.modules.exam_import.parser import (
    ParsedExamData,
    parse_question_scores_xlsx,
    parse_totals_xlsx,
    parse_zip,
)


# ── fixtures (inlined to avoid scope-ledger conftest trigger) ─────


@pytest.fixture
def sample_question_scores_xlsx(tmp_path):
    """Create a minimal question-score xlsx (3 students x 5 questions)."""
    fp = tmp_path / "生物小题分.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active

    # Row 1: fixed headers + merged subject header + aggregate sub-headers
    ws.append([
        "学校", "班级", "考号", "姓名", "选科",
        "生物", None, None, None, None, None, None,
        "选择1", "选择2", "选择3", "17", "18",
    ])
    # Row 2: aggregate sub-headers + question column names
    ws.append([
        None, None, None, None, None,
        "赋分", "原始分", "等级", "班名次", "校名次", "客观题", "主观题",
        "选择1", "选择2", "选择3", "17", "18",
    ])

    # Row 3-5: student data
    ws.append([
        "一中", "高三1班", "2024001", "张三", "物化生",
        85.0, 78.0, "A", 1, 3, 10, 68,
        2, 2, "2.00", 15, 12,
    ])
    ws.append([
        "一中", "高三1班", "2024002", "李四", "物化生",
        80.0, 72.0, "B", 2, 5, 8, 64,
        2, 1, 2, 12, 10,
    ])
    ws.append([
        "二中", "高三2班", "2024003", "王五", "史地政",
        70.0, 65.0, "B", 1, 8, 7, 58,
        1, 2, 2, 10, 8,
    ])

    wb.save(str(fp))
    wb.close()
    return fp


@pytest.fixture
def sample_totals_xlsx(tmp_path):
    """Create a minimal totals xlsx (3 students x 3 subjects)."""
    fp = tmp_path / "总分表.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active

    ws.append([
        "考号", "姓名", "班级", "语文", "语文(赋分)",
        "数学", "英语", "总分", "班名次", "校名次",
    ])
    ws.append(["2024001", "张三", "高三1班", 120, 125, 130, 140, 390, 1, 2])
    ws.append(["2024002", "李四", "高三1班", 110, 115, 125, 135, 370, 2, 4])
    ws.append(["2024003", "王五", "高三2班", 100, 105, 115, 120, 335, 1, 7])

    wb.save(str(fp))
    wb.close()
    return fp


# ── tests ─────────────────────────────────────────────────────────


def test_parse_question_scores_basic(sample_question_scores_xlsx):
    """Verify subject, questions, students, scores, ranks, and question types."""
    result = parse_question_scores_xlsx(sample_question_scores_xlsx)

    assert isinstance(result, ParsedExamData)
    assert len(result.subjects) == 1

    subj = result.subjects[0]
    assert subj.subject_name == "生物"
    assert subj.subject_code == "SW"

    # 5 question columns: 选择1, 选择2, 选择3, 17, 18
    assert len(subj.questions) == 5
    q_names = [q.name for q in subj.questions]
    assert q_names == ["选择1", "选择2", "选择3", "17", "18"]

    # question type inference
    assert subj.questions[0].question_type == "choice"  # 选择1
    assert subj.questions[1].question_type == "choice"  # 选择2
    assert subj.questions[3].question_type == "essay"    # 17
    assert subj.questions[4].question_type == "essay"    # 18

    # max_score inferred from data
    assert subj.questions[0].max_score_inferred is True
    assert subj.questions[0].max_score == 2.0   # max(2, 2, 1)
    assert subj.questions[3].max_score == 15.0  # max(15, 12, 10)

    # 3 students
    assert len(subj.students) == 3

    s1 = subj.students[0]
    assert s1.student_key == "2024001"
    assert s1.student_name == "张三"
    assert s1.school_name == "一中"
    assert s1.class_name == "高三1班"
    assert s1.elective == "物化生"
    assert s1.converted_score == 85.0
    assert s1.raw_total == 78.0
    assert s1.grade_level == "A"
    assert s1.class_rank == 1
    assert s1.school_rank == 3
    assert s1.objective_subtotal == 10.0
    assert s1.subjective_subtotal == 68.0

    # question scores -- string "2.00" should parse to 2.0
    assert s1.question_scores["选择3"] == 2.0
    assert s1.question_scores["17"] == 15.0
    assert s1.question_scores["18"] == 12.0


def test_parse_totals_basic(sample_totals_xlsx):
    """Verify subjects, synthetic question, max scores, and student scores."""
    result = parse_totals_xlsx(sample_totals_xlsx)

    assert isinstance(result, ParsedExamData)
    assert len(result.subjects) == 3

    # subjects detected
    subj_codes = sorted(s.subject_code for s in result.subjects)
    assert subj_codes == ["SX", "YW", "YY"]

    # find 语文
    yw = next(s for s in result.subjects if s.subject_code == "YW")
    assert yw.subject_name == "语文"
    assert len(yw.questions) == 1
    assert yw.questions[0].name == "__TOTAL__"
    assert yw.questions[0].question_type == "synthetic"
    assert yw.questions[0].max_score == 150  # from SUBJECT_MAX_SCORE

    # 3 students in each subject
    assert len(yw.students) == 3

    s1 = next(s for s in yw.students if s.student_key == "2024001")
    assert s1.student_name == "张三"
    assert s1.raw_total == 120.0
    assert s1.converted_score == 125.0  # 赋分 column
    assert s1.class_rank == 1
    assert s1.school_rank == 2
    assert s1.question_scores == {"__TOTAL__": 120.0}

    # 数学 has no 赋分 column
    sx = next(s for s in result.subjects if s.subject_code == "SX")
    s1_sx = next(s for s in sx.students if s.student_key == "2024001")
    assert s1_sx.raw_total == 130.0
    assert s1_sx.converted_score is None


def test_parse_zip_multi_subject(tmp_path, sample_question_scores_xlsx, sample_totals_xlsx):
    """Pack xlsx files into a zip and verify multi-subject parse."""
    zip_path = tmp_path / "exam_data.zip"
    with zipfile.ZipFile(str(zip_path), "w") as zf:
        zf.write(str(sample_question_scores_xlsx), "生物小题分.xlsx")
        zf.write(str(sample_totals_xlsx), "总分表.xlsx")

    result = parse_zip(zip_path)

    assert isinstance(result, ParsedExamData)
    # 生物小题分 -> 1 subject (SW), 总分表 -> 3 subjects (YW, SX, YY) = 4 total
    assert len(result.subjects) == 4

    codes = sorted(s.subject_code for s in result.subjects)
    assert codes == ["SW", "SX", "YW", "YY"]

    # The 小题分 file should use parse_question_scores_xlsx (has per-question data)
    sw = next(s for s in result.subjects if s.subject_code == "SW")
    assert len(sw.questions) == 5  # per-question, not synthetic

    # The totals file should use parse_totals_xlsx (has synthetic questions)
    yw = next(s for s in result.subjects if s.subject_code == "YW")
    assert len(yw.questions) == 1
    assert yw.questions[0].name == "__TOTAL__"
