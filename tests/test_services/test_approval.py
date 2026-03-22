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
