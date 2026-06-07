"""Test helper: seed per-school module-enable rows.

Not a test module (leading underscore) — imported explicitly by tests that build
a school directly and then call a gated *non-default* module route.
"""


async def enable_school_modules(db, *school_ids, codes=None):
    """Seed SchoolModule(enabled=True) rows for one or more schools.

    Phase 0.7E: the module middleware now fail-closes a gated *non-default* module
    (research / study_analytics / teaching) when its SchoolModule row is ABSENT,
    mirroring the frontend get_all_modules default (a module without a row is enabled
    IFF it is in DEFAULT_ENABLED). Tests that build a school directly (not via
    services.school_settings_service.init_school_modules) and then call a gated
    non-default route with a SCHOOL-scoped token (active_role_id / login) get a 403
    from the middleware before the route's own logic runs.

    Seeding enabled=True states the test precondition "this school has the module
    turned on", so the test exercises its real subject (data isolation / scope / 404
    semantics) instead of tripping the module gate. Pass explicit school ids, or none
    to enable modules for every school currently in the session.
    """
    from sqlalchemy import select
    from edu_cloud.models.school import School
    from edu_cloud.models.school_settings import SchoolModule, MODULE_CODES

    if not school_ids:
        school_ids = [s.id for s in (await db.execute(select(School))).scalars().all()]
    for sid in school_ids:
        for code in (codes or MODULE_CODES):
            db.add(SchoolModule(school_id=sid, module_code=code, enabled=True))
    await db.commit()
