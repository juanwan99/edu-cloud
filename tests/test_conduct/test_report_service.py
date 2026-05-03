"""Tests for conduct report_service — semester evaluation reports."""
import pytest
from datetime import date, timedelta

from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.conduct.models import (
    ConductRecord, ConductRuleCategory, ConductRuleItem, ConductSemester,
)
from edu_cloud.modules.conduct.report_service import (
    generate_semester_report,
    generate_school_report,
)
from edu_cloud.shared.auth import create_access_token


# ── seed helpers ──

async def _seed_class_with_records(db, school=None):
    """Create school + class + 3 students + 5 records spanning 2 weeks."""
    if school is None:
        school = School(name="报告测试中学", code="RPT01", is_active=True, district="TestDistrict")
        db.add(school)
        await db.flush()

    cls = Class(name="高一(1)班", grade="高一", grade_number=1, school_id=school.id)
    db.add(cls)
    await db.flush()

    students = []
    for i in range(3):
        s = Student(
            name=f"学生{chr(65 + i)}",
            student_number=f"RPT{i:03d}",
            class_id=cls.id,
            school_id=school.id,
        )
        db.add(s)
        students.append(s)
    await db.flush()

    operator = User(username="op_report", display_name="操作员报告")
    operator.set_password("test123")
    db.add(operator)
    await db.flush()

    today = date.today()
    # Student A: +5, +3 = 8 total
    db.add(ConductRecord(
        student_id=students[0].id, class_id=cls.id, points=5,
        reason="表现优秀", date=today, operator_id=operator.id,
    ))
    db.add(ConductRecord(
        student_id=students[0].id, class_id=cls.id, points=3,
        reason="帮助同学", date=today - timedelta(days=3), operator_id=operator.id,
    ))
    # Student B: -2 = -2 total
    db.add(ConductRecord(
        student_id=students[1].id, class_id=cls.id, points=-2,
        reason="迟到", date=today, operator_id=operator.id,
    ))
    # Student C: +1 = 1 total
    db.add(ConductRecord(
        student_id=students[2].id, class_id=cls.id, points=1,
        reason="值日认真", date=today - timedelta(days=1), operator_id=operator.id,
    ))
    # Student B: +4 = net +2 total
    db.add(ConductRecord(
        student_id=students[1].id, class_id=cls.id, points=4,
        reason="进步大", date=today, operator_id=operator.id,
    ))

    await db.commit()
    return {
        "school": school,
        "cls": cls,
        "students": students,
        "operator": operator,
    }


@pytest.fixture
async def report_data(db):
    return await _seed_class_with_records(db)


# ═══════════════════════════════════════════════════
# Unit tests: generate_semester_report
# ═══════════════════════════════════════════════════

class TestReportBasicStructure:
    async def test_report_basic_structure(self, db, report_data):
        """All top-level keys exist in the report."""
        result = await generate_semester_report(db, report_data["cls"].id)

        expected_keys = {
            "class_name", "semester_name", "period", "summary",
            "top_students", "bottom_students", "category_breakdown", "weekly_trend",
        }
        assert set(result.keys()) == expected_keys
        assert result["class_name"] == "高一(1)班"
        assert "start" in result["period"]
        assert "end" in result["period"]


class TestReportSummaryCounts:
    async def test_report_summary_counts(self, db, report_data):
        """Verify total_students, total_records, avg_points, positive_rate."""
        result = await generate_semester_report(db, report_data["cls"].id)
        s = result["summary"]

        assert s["total_students"] == 3
        assert s["total_records"] == 5
        # Total points: 5+3-2+1+4 = 11, 3 students => avg 3.67
        assert s["avg_points"] == round(11 / 3, 2)
        # Positive records: 4 out of 5
        assert s["positive_rate"] == round(4 / 5, 4)


class TestReportTopBottomStudents:
    async def test_report_top_bottom_students(self, db, report_data):
        """Students sorted correctly with rank field."""
        result = await generate_semester_report(db, report_data["cls"].id)

        top = result["top_students"]
        bottom = result["bottom_students"]

        # Top: Student A (8) > Student B (2) > Student C (1)
        assert len(top) == 3
        assert top[0]["name"] == "学生A"
        assert top[0]["points"] == 8
        assert top[0]["rank"] == 1
        assert top[1]["name"] == "学生B"
        assert top[1]["points"] == 2
        assert top[1]["rank"] == 2
        assert top[2]["name"] == "学生C"
        assert top[2]["points"] == 1
        assert top[2]["rank"] == 3

        # Bottom: Student C (1) > Student B (2) > Student A (8)
        assert len(bottom) == 3
        assert bottom[0]["name"] == "学生C"
        assert bottom[0]["points"] == 1
        assert bottom[0]["rank"] == 1
        assert bottom[1]["name"] == "学生B"
        assert bottom[1]["points"] == 2
        assert bottom[1]["rank"] == 2


class TestReportCategoryBreakdown:
    async def test_report_category_breakdown(self, db, report_data):
        """Records with rule_item_id show their category; others show '其他'."""
        cls = report_data["cls"]
        operator = report_data["operator"]
        student = report_data["students"][0]

        # Create a rule category and item
        cat = ConductRuleCategory(
            name="课堂纪律", class_id=cls.id, scope="class",
        )
        db.add(cat)
        await db.flush()
        item = ConductRuleItem(name="认真听讲", points=2, category_id=cat.id)
        db.add(item)
        await db.flush()

        # Add a record with rule_item_id
        db.add(ConductRecord(
            student_id=student.id, class_id=cls.id, points=2,
            reason="课堂表现好", date=date.today(), operator_id=operator.id,
            rule_item_id=item.id,
        ))
        await db.commit()

        result = await generate_semester_report(db, cls.id)
        breakdown = result["category_breakdown"]

        category_names = [b["category"] for b in breakdown]
        assert "课堂纪律" in category_names
        assert "其他" in category_names

        # The "课堂纪律" category should have 1 positive record
        discipline = next(b for b in breakdown if b["category"] == "课堂纪律")
        assert discipline["positive_count"] == 1
        assert discipline["negative_count"] == 0
        assert discipline["net_points"] == 2


class TestReportEmptyClass:
    async def test_report_empty_class(self, db, report_data):
        """Class with no records returns zeros and empty lists."""
        school = report_data["school"]
        empty_cls = Class(name="空班", grade="高一", grade_number=99, school_id=school.id)
        db.add(empty_cls)
        await db.commit()

        result = await generate_semester_report(db, empty_cls.id)

        assert result["class_name"] == "空班"
        assert result["summary"]["total_students"] == 0
        assert result["summary"]["total_records"] == 0
        assert result["summary"]["avg_points"] == 0.0
        assert result["summary"]["positive_rate"] == 0.0
        assert result["top_students"] == []
        assert result["bottom_students"] == []
        assert result["category_breakdown"] == []


class TestReportWithSemesterFilter:
    async def test_report_with_semester_filter(self, db, report_data):
        """Records outside semester range are excluded."""
        cls = report_data["cls"]

        # Create a semester that only covers yesterday -> tomorrow
        today = date.today()
        sem = ConductSemester(
            name="测试学期",
            class_id=cls.id,
            start_date=today - timedelta(days=1),
            end_date=today,
            is_current=False,
        )
        db.add(sem)
        await db.commit()

        result = await generate_semester_report(db, cls.id, semester_id=sem.id)

        assert result["semester_name"] == "测试学期"
        # Only records within [today-1, today] should be included.
        # From seed: today: +5, -2, +4; today-1: +1 => 4 records
        # (today-3: +3 is excluded)
        assert result["summary"]["total_records"] == 4


# ═══════════════════════════════════════════════════
# Unit tests: generate_school_report
# ═══════════════════════════════════════════════════

class TestSchoolReport:
    async def test_school_report(self, db, report_data):
        """School report aggregates multiple classes."""
        school = report_data["school"]

        # Add a second class with records
        cls2 = Class(name="高一(2)班", grade="高一", grade_number=2, school_id=school.id)
        db.add(cls2)
        await db.flush()
        s2 = Student(
            name="学生D", student_number="RPT_D",
            class_id=cls2.id, school_id=school.id,
        )
        db.add(s2)
        await db.flush()
        db.add(ConductRecord(
            student_id=s2.id, class_id=cls2.id, points=10,
            reason="优秀", date=date.today(), operator_id=report_data["operator"].id,
        ))
        await db.commit()

        result = await generate_school_report(db, school.id)

        assert result["school_name"] == "报告测试中学"
        assert result["summary"]["total_classes"] == 2
        # Class 1: 3 students, Class 2: 1 student
        assert result["summary"]["total_students"] == 4
        # Class 1: 5 records, Class 2: 1 record
        assert result["summary"]["total_records"] == 6
        assert len(result["class_rankings"]) == 2

        # Each class ranking has required fields
        for cr in result["class_rankings"]:
            assert "class_name" in cr
            assert "avg_points" in cr
            assert "record_count" in cr
            assert "top_student" in cr


# ═══════════════════════════════════════════════════
# HTTP endpoint tests
# ═══════════════════════════════════════════════════

class TestClassReportEndpoint:
    async def test_class_report_endpoint(self, client, db, report_data):
        """GET /classes/{class_id}/report returns 200 with correct shape."""
        cls = report_data["cls"]
        school = report_data["school"]

        # Create a user with VIEW_CONDUCT for this class
        user = User(username="teacher_rpt", display_name="报告教师")
        user.set_password("test123")
        db.add(user)
        await db.flush()
        role = UserRole(
            user_id=user.id, role="homeroom_teacher",
            school_id=school.id, class_ids=[cls.id], is_primary=True,
        )
        db.add(role)
        await db.commit()

        token = create_access_token({"sub": user.id, "role": "homeroom_teacher"})
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.get(
            f"/api/v1/conduct/classes/{cls.id}/report",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "class_name" in data
        assert "summary" in data
        assert "top_students" in data
        assert "weekly_trend" in data


class TestSchoolReportEndpoint:
    async def test_school_report_endpoint(self, client, db, report_data, admin_user, admin_headers):
        """GET /schools/{school_id}/report returns 200 with correct shape."""
        school = report_data["school"]

        resp = await client.get(
            f"/api/v1/conduct/schools/{school.id}/report",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "school_name" in data
        assert "summary" in data
        assert "class_rankings" in data
