"""题库搜索 + 统计概览 API 测试（WP-A TDD-lite）。"""
import pytest

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.bank.models import BankQuestion
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def bank_school(db):
    """Seed a school for bank tests."""
    school = School(name="题库测试校", code="BANKTEST", district="测试区", api_key_hash="x")
    db.add(school)
    await db.commit()
    await db.refresh(school)
    return school


@pytest.fixture
async def bank_user_headers(db, bank_school):
    """Create a user with VIEW_QUESTION_BANK scoped to bank_school."""
    user = User(username="bank_tester", display_name="Bank Tester")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    role = UserRole(
        user_id=user.id, role="academic_director",
        school_id=bank_school.id, is_primary=True,
    )
    db.add(role)
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "academic_director"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_bank_questions(db, bank_school):
    """Seed diverse bank questions for search/filter tests."""
    school_id = bank_school.id
    questions = [
        BankQuestion(
            content_text="解方程 2x + 3 = 7",
            question_type="fill_blank",
            max_score=5.0,
            difficulty_level="easy",
            source="期中考试",
            tags=["代数", "方程"],
            knowledge_point_ids=["kp_algebra_01", "kp_equation_01"],
            school_id=school_id,
        ),
        BankQuestion(
            content_text="证明三角形内角和等于180度",
            question_type="essay",
            max_score=10.0,
            difficulty_level="medium",
            source="期末考试",
            tags=["几何", "三角形"],
            knowledge_point_ids=["kp_geometry_01"],
            school_id=school_id,
        ),
        BankQuestion(
            content_text="计算圆的面积，半径为5cm",
            question_type="fill_blank",
            max_score=5.0,
            difficulty_level="easy",
            source="期中考试",
            tags=["几何", "圆"],
            knowledge_point_ids=["kp_geometry_02"],
            school_id=school_id,
        ),
        BankQuestion(
            content_text="求函数 f(x) = x^2 - 4x + 3 的极值",
            question_type="essay",
            max_score=12.0,
            difficulty_level="hard",
            source="模拟考试",
            tags=["代数", "函数"],
            knowledge_point_ids=["kp_algebra_01", "kp_function_01"],
            school_id=school_id,
        ),
        BankQuestion(
            content_text="下列哪个是等腰三角形的性质",
            question_type="choice",
            max_score=3.0,
            difficulty_level="easy",
            source="课堂测验",
            tags=["几何", "三角形"],
            knowledge_point_ids=["kp_geometry_01"],
            school_id=school_id,
        ),
    ]
    db.add_all(questions)
    await db.commit()
    return {"school_id": school_id, "count": len(questions)}


# ────────── 搜索端点测试 ──────────


@pytest.mark.asyncio
async def test_search_no_filters(client, bank_user_headers, seed_bank_questions):
    """无筛选条件返回全部题目（分页）。"""
    resp = await client.get("/api/v1/bank/questions/search", headers=bank_user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert data["total"] == 5
    assert len(data["items"]) == 5


@pytest.mark.asyncio
async def test_search_by_question_type(client, bank_user_headers, seed_bank_questions):
    """按题型筛选。"""
    resp = await client.get(
        "/api/v1/bank/questions/search",
        params={"question_type": "essay"},
        headers=bank_user_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    for item in data["items"]:
        assert item["question_type"] == "essay"


@pytest.mark.asyncio
async def test_search_by_difficulty(client, bank_user_headers, seed_bank_questions):
    """按难度筛选。"""
    resp = await client.get(
        "/api/v1/bank/questions/search",
        params={"difficulty_level": "easy"},
        headers=bank_user_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    for item in data["items"]:
        assert item["difficulty_level"] == "easy"


@pytest.mark.asyncio
async def test_search_by_source(client, bank_user_headers, seed_bank_questions):
    """按来源筛选。"""
    resp = await client.get(
        "/api/v1/bank/questions/search",
        params={"source": "期中考试"},
        headers=bank_user_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_search_by_keyword(client, bank_user_headers, seed_bank_questions):
    """关键词搜索 content_text。"""
    resp = await client.get(
        "/api/v1/bank/questions/search",
        params={"keyword": "三角形"},
        headers=bank_user_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    for item in data["items"]:
        assert "三角形" in item["content_text"]


@pytest.mark.asyncio
async def test_search_multi_condition(client, bank_user_headers, seed_bank_questions):
    """多条件 AND 组合筛选。"""
    resp = await client.get(
        "/api/v1/bank/questions/search",
        params={"question_type": "fill_blank", "difficulty_level": "easy"},
        headers=bank_user_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    for item in data["items"]:
        assert item["question_type"] == "fill_blank"
        assert item["difficulty_level"] == "easy"


@pytest.mark.asyncio
async def test_search_pagination(client, bank_user_headers, seed_bank_questions):
    """分页控制。"""
    resp = await client.get(
        "/api/v1/bank/questions/search",
        params={"page": 1, "page_size": 2},
        headers=bank_user_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2

    # 第二页
    resp2 = await client.get(
        "/api/v1/bank/questions/search",
        params={"page": 2, "page_size": 2},
        headers=bank_user_headers,
    )
    data2 = resp2.json()
    assert data2["page"] == 2
    assert len(data2["items"]) == 2


@pytest.mark.asyncio
async def test_search_excludes_embedding(client, bank_user_headers, seed_bank_questions):
    """搜索结果不包含 embedding 字段（大字段排除）。"""
    resp = await client.get("/api/v1/bank/questions/search", headers=bank_user_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert "embedding" not in item


@pytest.mark.asyncio
async def test_search_requires_auth(client):
    """无 JWT 返回 401。"""
    resp = await client.get("/api/v1/bank/questions/search")
    assert resp.status_code == 401


# ────────── 统计概览端点测试 ──────────


@pytest.mark.asyncio
async def test_stats_overview(client, bank_user_headers, seed_bank_questions):
    """统计概览返回 total + 分组计数。"""
    resp = await client.get(
        "/api/v1/bank/questions/stats/overview",
        headers=bank_user_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 5
    assert "by_question_type" in data
    assert "by_difficulty_level" in data
    assert "by_source" in data
    # 校验分组求和一致
    assert sum(data["by_question_type"].values()) == 5
    assert sum(data["by_difficulty_level"].values()) == 5
    assert sum(data["by_source"].values()) == 5


@pytest.mark.asyncio
async def test_stats_overview_requires_auth(client):
    """无 JWT 返回 401。"""
    resp = await client.get("/api/v1/bank/questions/stats/overview")
    assert resp.status_code == 401
