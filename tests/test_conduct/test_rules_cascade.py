"""Tests for school-level rule cascade (Task 2).

School-scope rules automatically appear when querying class rules,
marked as readonly. School-level CRUD endpoints for principals/academic_directors.
"""
import pytest

from edu_cloud.modules.conduct.models import ConductRuleCategory, ConductRuleItem
from edu_cloud.modules.conduct import rules_service


# ── Helpers ──


async def _create_school_category(db, school_id, name="校级纪律", sort_order=0):
    """Create a school-scope rule category directly via service."""
    return await rules_service.create_category(
        db, school_id=school_id, name=name, scope="school", sort_order=sort_order,
    )


async def _create_class_category(db, class_id, name="班级纪律", sort_order=0):
    """Create a class-scope rule category directly via service."""
    return await rules_service.create_category(
        db, class_id=class_id, name=name, scope="class", sort_order=sort_order,
    )


# ── Service-layer tests ──


@pytest.mark.anyio
async def test_school_rule_visible_in_class(db, school_class_student):
    """School-level categories (with items) appear in class rules as readonly."""
    school, cls, _ = school_class_student

    # Create school-scope category + item
    school_cat = await _create_school_category(db, school.id, "校级文明礼仪")
    await rules_service.create_item(db, school_cat["id"], "课堂纪律", points=-2)

    # Create class-scope category
    await _create_class_category(db, cls.id, "班级卫生")

    # Query rules for the class
    rules = await rules_service.get_rules(db, cls.id)
    assert len(rules) == 2

    # School rule first, marked readonly
    school_rule = rules[0]
    assert school_rule["name"] == "校级文明礼仪"
    assert school_rule["scope"] == "school"
    assert school_rule["readonly"] is True
    assert len(school_rule["items"]) == 1
    assert school_rule["items"][0]["name"] == "课堂纪律"
    assert school_rule["items"][0]["points"] == -2

    # Class rule second, not readonly
    class_rule = rules[1]
    assert class_rule["name"] == "班级卫生"
    assert class_rule["scope"] == "class"
    assert class_rule["readonly"] is False


@pytest.mark.anyio
async def test_class_rule_not_visible_in_other_class(db, school_class_student):
    """A category for class A does not appear when querying class B."""
    school, cls, _ = school_class_student

    # Create a category for the existing class
    await _create_class_category(db, cls.id, "高一(1)班规则")

    # Create another class in the same school
    from edu_cloud.modules.student.models import Class
    other_cls = Class(name="高一(2)班", grade="高一", grade_number=2, school_id=school.id)
    db.add(other_cls)
    await db.commit()

    # Query rules for the other class -- should be empty (no school rules either)
    rules = await rules_service.get_rules(db, other_cls.id)
    assert len(rules) == 0


@pytest.mark.anyio
async def test_school_rules_sorted_first(db, school_class_student):
    """School-scope rules always come before class-scope rules."""
    school, cls, _ = school_class_student

    # Create class rule first (sort_order=0)
    await _create_class_category(db, cls.id, "班级AAA", sort_order=0)
    # Create school rule second (sort_order=10, higher number)
    await _create_school_category(db, school.id, "校级ZZZ", sort_order=10)

    rules = await rules_service.get_rules(db, cls.id)
    assert len(rules) == 2
    # School comes first despite higher sort_order and later alpha name
    assert rules[0]["scope"] == "school"
    assert rules[0]["name"] == "校级ZZZ"
    assert rules[1]["scope"] == "class"
    assert rules[1]["name"] == "班级AAA"


@pytest.mark.anyio
async def test_create_category_school_scope(db, school_class_student):
    """create_category with scope='school' sets correct fields."""
    school, _, _ = school_class_student

    result = await rules_service.create_category(
        db, school_id=school.id, name="校级奖励", scope="school", sort_order=5,
    )
    assert result["scope"] == "school"
    assert result["name"] == "校级奖励"
    assert result["sort_order"] == 5

    # Verify DB record
    cat = await db.get(ConductRuleCategory, result["id"])
    assert cat is not None
    assert cat.school_id == school.id
    assert cat.class_id is None
    assert cat.scope == "school"


# ── HTTP endpoint tests ──


@pytest.mark.anyio
async def test_school_rules_endpoint(
    client, db, school_class_student, homeroom_headers,
):
    """GET /conduct/schools/{school_id}/rules returns only school-scope categories."""
    school, cls, _ = school_class_student

    # Create one school-scope and one class-scope category
    await _create_school_category(db, school.id, "校级考勤")
    await rules_service.create_item(
        db,
        (await _create_school_category(db, school.id, "校级安全"))["id"],
        "禁止追逐打闹",
        points=-3,
    )
    await _create_class_category(db, cls.id, "班级学习")

    resp = await client.get(
        f"/api/v1/conduct/schools/{school.id}/rules",
        headers=homeroom_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Only school-scope categories returned
    assert len(data) == 2
    names = {r["name"] for r in data}
    assert names == {"校级考勤", "校级安全"}

    # Verify nested items
    safety_rule = next(r for r in data if r["name"] == "校级安全")
    assert len(safety_rule["items"]) == 1
    assert safety_rule["items"][0]["name"] == "禁止追逐打闹"

    # Class category NOT included
    assert "班级学习" not in names


@pytest.mark.anyio
async def test_create_school_rule_category_endpoint(
    client, db, school_class_student, homeroom_headers,
):
    """POST /conduct/schools/{school_id}/rules/categories creates a school-scope category."""
    school, _, _ = school_class_student

    resp = await client.post(
        f"/api/v1/conduct/schools/{school.id}/rules/categories",
        headers=homeroom_headers,
        json={"name": "校级品德", "sort_order": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "校级品德"
    assert data["scope"] == "school"
    assert data["sort_order"] == 3

    # Verify in DB
    cat = await db.get(ConductRuleCategory, data["id"])
    assert cat.school_id == school.id
    assert cat.class_id is None
