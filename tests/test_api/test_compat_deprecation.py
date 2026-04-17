"""compat_router 退役信号测试 (Phase 5 首动作)。

契约：docs/plans/compat-router-deprecation.md §4.1 三层信号
  1. Python DeprecationWarning（运行时）
  2. HTTP Response header: Deprecation / Sunset / Link
  3. 结构化日志: msg="deprecated_compat_call", extra={endpoint, replacement, sunset}
"""
import logging
import warnings

import pytest
from httpx import AsyncClient

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole


@pytest.fixture
async def depr_seed(client: AsyncClient, db):
    """compat deprecation 测试所需的最小 seed（学校+principal 用户）。"""
    school = School(id="ds1", name="depr测试校", code="DEPR01")
    db.add(school)
    await db.commit()

    user = User(id="du1", username="depr_user", display_name="depr用户")
    user.set_password("pass123")
    db.add(user)
    await db.commit()

    db.add(UserRole(user_id="du1", role="principal", school_id="ds1", is_primary=True))
    await db.commit()
    return {"school_id": "ds1", "user_id": "du1"}


class TestCompatDeprecationSignal:
    """compat_router 三层 deprecation 信号。"""

    async def test_response_headers_carry_deprecation_trio(
        self, client: AsyncClient, depr_seed
    ):
        """调用 compat 端点的响应携带 Deprecation / Sunset / Link 三件套。"""
        resp = await client.post(
            "/api/auth/login",
            json={"school_code": "DEPR01", "username": "depr_user", "password": "pass123"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("Deprecation") == "true"
        sunset = resp.headers.get("Sunset")
        assert sunset and sunset.startswith("2026-"), f"Sunset missing or malformed: {sunset!r}"
        link = resp.headers.get("Link")
        assert link and 'rel="successor-version"' in link
        assert "/api/v1/auth/login" in link

    async def test_deprecation_warning_is_emitted(self, client: AsyncClient, depr_seed):
        """调用 compat 端点触发 Python DeprecationWarning (含端点与替代路径)。"""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            resp = await client.post(
                "/api/auth/login",
                json={"school_code": "DEPR01", "username": "depr_user", "password": "pass123"},
            )
            assert resp.status_code == 200
        depr = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert depr, "no DeprecationWarning captured"
        msg = str(depr[0].message)
        assert "/api/auth/login" in msg
        assert "/api/v1/auth/login" in msg

    async def test_structured_log_written(
        self, client: AsyncClient, depr_seed, caplog, monkeypatch
    ):
        """compat 调用产生 WARNING 级日志，msg=deprecated_compat_call + extra 字段齐全。

        logging_config.py:65 设置 edu_cloud root propagate=False，
        caplog 默认挂在 root 上收不到，用 monkeypatch 临时开 propagate。
        """
        monkeypatch.setattr(logging.getLogger("edu_cloud"), "propagate", True)
        caplog.set_level(logging.WARNING, logger="edu_cloud.api.compat_router")

        resp = await client.post(
            "/api/auth/login",
            json={"school_code": "DEPR01", "username": "depr_user", "password": "pass123"},
        )
        assert resp.status_code == 200

        matches = [r for r in caplog.records if r.getMessage() == "deprecated_compat_call"]
        assert matches, (
            "no deprecated_compat_call WARNING log captured; "
            f"records={[(r.name, r.levelname, r.getMessage()) for r in caplog.records]}"
        )
        rec = matches[0]
        assert getattr(rec, "endpoint", None) == "/api/auth/login"
        assert getattr(rec, "replacement", None) == "/api/v1/auth/login"
        assert getattr(rec, "sunset", None), "extra.sunset missing"
