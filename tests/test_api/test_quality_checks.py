import pytest


@pytest.mark.asyncio
async def test_get_quality_report(client, admin_headers):
    resp = await client.get(
        "/api/v1/grading/quality-report/fake-exam-id",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_checks" in data
    assert data["has_blocking_issues"] is False
