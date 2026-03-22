import pytest
from edu_cloud.services.approval_service import ApprovalService, APPROVAL_CHAINS
from edu_cloud.services.exceptions import StateError, PermissionDeniedError


def test_approval_chains_defined():
    assert "class_notification" in APPROVAL_CHAINS
    assert "school_notification" in APPROVAL_CHAINS
    assert "emergency" in APPROVAL_CHAINS


@pytest.mark.asyncio
async def test_create_approval_flow(db, seed_approver):
    svc = ApprovalService(db)
    flow = await svc.create_flow(
        document_id="doc1",
        chain_type="class_notification",
        approver_ids=[seed_approver["user_id"]],
    )
    assert flow.status == "pending"
    assert flow.current_step == 0


@pytest.mark.asyncio
async def test_approve_step(db, seed_approver):
    svc = ApprovalService(db)
    flow = await svc.create_flow(
        document_id="doc1",
        chain_type="class_notification",
        approver_ids=[seed_approver["user_id"]],
    )
    result = await svc.act_on_step(
        flow_id=flow.id,
        approver_id=seed_approver["user_id"],
        action="approved",
    )
    assert result.status == "approved"


@pytest.mark.asyncio
async def test_reject_step(db, seed_approver):
    svc = ApprovalService(db)
    flow = await svc.create_flow(
        document_id="doc1",
        chain_type="class_notification",
        approver_ids=[seed_approver["user_id"]],
    )
    result = await svc.act_on_step(
        flow_id=flow.id,
        approver_id=seed_approver["user_id"],
        action="rejected",
        comment="措辞不当",
    )
    assert result.status == "rejected"


@pytest.mark.asyncio
async def test_wrong_approver_denied(db, seed_approver):
    svc = ApprovalService(db)
    flow = await svc.create_flow(
        document_id="doc1",
        chain_type="class_notification",
        approver_ids=[seed_approver["user_id"]],
    )
    with pytest.raises(PermissionDeniedError):
        await svc.act_on_step(
            flow_id=flow.id,
            approver_id="wrong_user_id",
            action="approved",
        )


@pytest.mark.asyncio
async def test_already_completed_flow_cannot_act(db, seed_approver):
    svc = ApprovalService(db)
    flow = await svc.create_flow(
        document_id="doc1",
        chain_type="class_notification",
        approver_ids=[seed_approver["user_id"]],
    )
    await svc.act_on_step(flow_id=flow.id, approver_id=seed_approver["user_id"], action="approved")
    with pytest.raises((StateError, PermissionDeniedError, IndexError)):
        await svc.act_on_step(flow_id=flow.id, approver_id=seed_approver["user_id"], action="approved")


# ── F3 fix: 多步审批 + flow_id 不存在 ─────────────────────────────


@pytest.mark.asyncio
async def test_multi_step_approval(db, seed_approver):
    """F3: 双审批人链——首人批准后 flow 仍 pending, current_step 前进"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    # 创建第二个审批人
    user2 = User(username="principal1", display_name="李校长")
    user2.set_password("123456")
    db.add(user2)
    await db.flush()
    db.add(UserRole(user_id=user2.id, role="principal",
                    school_id=seed_approver["school_id"], is_primary=True))
    await db.flush()

    svc = ApprovalService(db)
    flow = await svc.create_flow(
        document_id="doc_multi",
        chain_type="school_notification",
        approver_ids=[seed_approver["user_id"], user2.id],
    )

    # 首人批准 → flow 仍 pending, step 前进到 1
    result = await svc.act_on_step(
        flow_id=flow.id, approver_id=seed_approver["user_id"], action="approved",
    )
    assert result.status == "pending"
    assert result.current_step == 1

    # 第一审批人不能再操作
    with pytest.raises(PermissionDeniedError):
        await svc.act_on_step(
            flow_id=flow.id, approver_id=seed_approver["user_id"], action="approved",
        )

    # 第二审批人批准 → flow 完成
    result = await svc.act_on_step(
        flow_id=flow.id, approver_id=user2.id, action="approved",
    )
    assert result.status == "approved"


@pytest.mark.asyncio
async def test_flow_not_found(db):
    """F3: 不存在的 flow_id → NotFoundError"""
    from edu_cloud.services.exceptions import NotFoundError

    svc = ApprovalService(db)
    with pytest.raises(NotFoundError):
        await svc.act_on_step(
            flow_id="nonexistent-flow", approver_id="anyone", action="approved",
        )
