import pytest
from edu_cloud.models.capability import Capability, CAPABILITY_DOMAINS, CAPABILITY_ACTIONS


@pytest.mark.asyncio
async def test_capability_domains_contains_nine():
    assert len(CAPABILITY_DOMAINS) == 9
    assert "exam" in CAPABILITY_DOMAINS
    assert "system" in CAPABILITY_DOMAINS


@pytest.mark.asyncio
async def test_capability_actions():
    assert CAPABILITY_ACTIONS == {"read", "write"}


@pytest.mark.asyncio
async def test_capability_model(db, seed_school):
    school, _ = seed_school
    cap = Capability(
        school_id=school.id,
        role="principal",
        domain="exam",
        action="read",
        enabled=True,
    )
    db.add(cap)
    await db.commit()
    await db.refresh(cap)
    assert cap.id is not None
    assert cap.role == "principal"
    assert cap.domain == "exam"
    assert cap.action == "read"
    assert cap.enabled is True


@pytest.mark.asyncio
async def test_capability_unique_constraint(db, seed_school):
    from sqlalchemy.exc import IntegrityError

    school, _ = seed_school
    c1 = Capability(school_id=school.id, role="principal", domain="exam", action="read", enabled=True)
    c2 = Capability(school_id=school.id, role="principal", domain="exam", action="read", enabled=False)
    db.add(c1)
    await db.flush()
    db.add(c2)
    with pytest.raises(IntegrityError):
        await db.flush()
