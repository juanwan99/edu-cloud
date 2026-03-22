"""Approval workflow service — fixed chains, step-by-step progression."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.approval import ApprovalFlow, ApprovalStep
from edu_cloud.services.exceptions import NotFoundError, PermissionDeniedError, StateError

APPROVAL_CHAINS = {
    "class_notification": {"description": "班主任 → 教务主任"},
    "school_notification": {"description": "教务主任 → 校长"},
    "emergency": {"description": "校长直批"},
}


class ApprovalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_flow(
        self,
        document_id: str,
        chain_type: str,
        approver_ids: list[str],
    ) -> ApprovalFlow:
        """Create an approval flow with ordered steps."""
        if chain_type not in APPROVAL_CHAINS:
            raise StateError(f"Unknown approval chain: {chain_type}")

        flow = ApprovalFlow(
            document_id=document_id,
            chain_type=chain_type,
            current_step=0,
            status="pending",
        )
        self.db.add(flow)
        await self.db.flush()

        for i, approver_id in enumerate(approver_ids):
            self.db.add(
                ApprovalStep(
                    flow_id=flow.id,
                    step_order=i,
                    approver_id=approver_id,
                    status="waiting",
                )
            )
        await self.db.flush()
        return flow

    async def act_on_step(
        self,
        flow_id: str,
        approver_id: str,
        action: str,
        comment: str | None = None,
    ) -> ApprovalFlow:
        """Approve or reject the current step of a flow."""
        flow = await self.db.get(ApprovalFlow, flow_id)
        if not flow:
            raise NotFoundError(f"Flow {flow_id} not found")

        steps = (
            await self.db.execute(
                select(ApprovalStep)
                .where(ApprovalStep.flow_id == flow.id)
                .order_by(ApprovalStep.step_order)
            )
        ).scalars().all()

        if flow.status in ("approved", "rejected") or flow.current_step >= len(steps):
            raise StateError("Approval flow already completed")

        current = steps[flow.current_step]
        if current.approver_id != approver_id:
            raise PermissionDeniedError("Not the current approver")

        current.status = action
        current.comment = comment
        current.acted_at = datetime.now(timezone.utc)

        if action == "rejected":
            flow.status = "rejected"
        elif action == "approved":
            if flow.current_step + 1 >= len(steps):
                flow.status = "approved"
            else:
                flow.current_step += 1

        await self.db.flush()
        return flow
