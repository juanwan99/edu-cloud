"""Studio REST API: templates, document CRUD, status transitions."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.core.auth import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.services.studio_service import StudioService
from edu_cloud.services.paper_service import PaperService
from edu_cloud.templates.document_templates import get_templates_for_role

router = APIRouter(prefix="/api/v1/studio", tags=["studio"])


@router.get("/templates")
async def list_templates(current=Depends(get_current_user)):
    role = current["current_role"]
    role_name = role.role if hasattr(role, "role") else "unknown"
    return get_templates_for_role(role_name)


@router.get("/documents")
async def list_documents(
    status: str | None = None,
    current=Depends(require_permission(Permission.GENERATE_REPORT)),
    db: AsyncSession = Depends(get_db),
):
    user = current["user"]
    role = current["current_role"]
    school_id = getattr(role, "school_id", None)
    svc = StudioService(db)
    docs = await svc.list_documents(
        school_id=school_id, created_by=user.id, status=status
    )
    return [_doc_to_dict(d) for d in docs]


@router.post("/documents", status_code=201)
async def create_document(
    body: dict,
    current=Depends(require_permission(Permission.GENERATE_REPORT)),
    db: AsyncSession = Depends(get_db),
):
    if "type" not in body or "title" not in body:
        raise HTTPException(422, "缺少必填字段: type, title")

    user = current["user"]
    role = current["current_role"]
    svc = StudioService(db)
    doc = await svc.create_document(
        type=body["type"],
        title=body["title"],
        content_json=body.get("content_json", {}),
        school_id=getattr(role, "school_id", ""),
        created_by=user.id,
        source_context=body.get("source_context"),
    )
    await db.commit()
    return _doc_to_dict(doc)


@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    current=Depends(require_permission(Permission.GENERATE_REPORT)),
    db: AsyncSession = Depends(get_db),
):
    role = current["current_role"]
    school_id = getattr(role, "school_id", None)
    svc = StudioService(db)
    doc = await svc.get_document(doc_id, school_id=school_id)
    return _doc_to_dict(doc)


@router.patch("/documents/{doc_id}")
async def update_document(
    doc_id: str,
    body: dict,
    current=Depends(require_permission(Permission.GENERATE_REPORT)),
    db: AsyncSession = Depends(get_db),
):
    if "content_json" not in body:
        raise HTTPException(422, "缺少必填字段: content_json")

    user = current["user"]
    role = current["current_role"]
    school_id = getattr(role, "school_id", None)
    svc = StudioService(db)
    doc = await svc.update_document(
        doc_id,
        content_json=body["content_json"],
        edited_by=user.id,
        change_summary=body.get("change_summary", ""),
        school_id=school_id,
    )
    await db.commit()
    return _doc_to_dict(doc)


@router.post("/documents/{doc_id}/transition")
async def transition_document(
    doc_id: str,
    body: dict,
    # CB-2 fix: 改回 get_current_user，权限按文档类型在函数体内分别检查
    # subject_teacher 有 GENERATE_REPORT 但无 GENERATE_NOTIFICATION，两者都需要 transition
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if "status" not in body:
        raise HTTPException(422, "缺少必填字段: status")

    user = current["user"]
    role = current["current_role"]
    school_id = getattr(role, "school_id", None)
    role_name = getattr(role, "role", "unknown")

    # CB-2 fix: 先查文档类型，再按类型检查权限
    from edu_cloud.core.permissions import has_permission
    svc_check = StudioService(db)
    doc_check = await svc_check.get_document(doc_id, school_id=school_id)

    if doc_check.type == "notification":
        if not has_permission(role_name, Permission.GENERATE_NOTIFICATION):
            raise HTTPException(403, "需要 GENERATE_NOTIFICATION 权限")
        # F3: notification executed 需要额外的 SEND_NOTIFICATION 权限
        if body["status"] == "executed":
            if not has_permission(role_name, Permission.SEND_NOTIFICATION):
                raise HTTPException(403, "需要 SEND_NOTIFICATION 权限才能执行通知")
    else:
        if not has_permission(role_name, Permission.GENERATE_REPORT):
            raise HTTPException(403, "需要 GENERATE_REPORT 权限")

    svc = StudioService(db)
    doc = await svc.transition_status(doc_id, body["status"], school_id=school_id)

    # F4 fix: 通知类文档 transition 到 pending 时自动创建审批流
    if body["status"] == "pending" and doc.type == "notification":
        from edu_cloud.services.approval_service import ApprovalService
        template_info = doc.source_context or {}
        chain_type = template_info.get("approval_chain", "class_notification")
        approval_svc = ApprovalService(db)
        flow = await approval_svc.create_flow(
            document_id=doc.id,
            chain_type=chain_type,
            approver_ids=[],  # 首期: 由管理员手动指定审批人
        )
        # CB-3 fix: 空审批人时 flow 已标记为 approved，自动推进文档状态
        if flow.status == "approved":
            doc.status = "approved"
            await db.flush()

    # P3: 通知类文档 transition 到 executed 时触发分发
    if body["status"] == "executed" and doc.type == "notification":
        from edu_cloud.services.notification_service import NotificationService
        from datetime import datetime, timezone
        notif_svc = NotificationService(db)
        dispatch_result = await notif_svc.dispatch(
            document_id=doc.id,
            target_scope=doc.source_context or {},
            school_id=doc.school_id,
            channel="stub",
        )
        notification_sent = bool(
            dispatch_result.get("sent") and dispatch_result.get("channel") != "stub"
        )
        doc.execution_result = {
            **dispatch_result,
            "sent": notification_sent,
            "delivery_state": dispatch_result.get("delivery_state", "not_configured"),
        }
        doc.executed_at = datetime.now(timezone.utc)

    await db.commit()
    return _doc_to_dict(doc)


def _doc_to_dict(doc) -> dict:
    return {
        "id": doc.id,
        "type": doc.type,
        "title": doc.title,
        "status": doc.status,
        "content_json": doc.content_json,
        "content_html": doc.content_html,
        "pdf_url": doc.pdf_url,
        "version": doc.version,
        "executed_at": str(doc.executed_at) if doc.executed_at else None,
        "execution_result": doc.execution_result,
        "created_at": str(doc.created_at) if doc.created_at else None,
    }


@router.post("/paper/create")
async def create_paper(
    body: dict,
    current=Depends(require_permission(Permission.WRITE_PAPER)),
    db: AsyncSession = Depends(get_db),
):
    svc = PaperService()
    result = await svc.create_paper(
        budget_tier=body.get("budget_tier", "standard"),
        title=body.get("title"),
        seed_idea=body.get("seed_idea"),
    )
    if "error" in result:
        return result

    # 在 Studio 中创建关联文档记录
    user = current["user"]
    role = current["current_role"]
    studio_svc = StudioService(db)
    doc = await studio_svc.create_document(
        type="paper", title=result.get("title", "教育论文"),
        content_json={"paper_id": result["paper_id"], "stage": result["stage"], "status": result.get("status")},
        school_id=getattr(role, "school_id", ""),
        created_by=user.id,
        source_context={"paper_skill_id": result["paper_id"]},
    )
    await db.commit()
    return {"document_id": doc.id, "paper_id": result["paper_id"], "stage": result["stage"]}


@router.get("/paper/{paper_id}/status")
async def get_paper_status(
    paper_id: str,
    current=Depends(get_current_user),
):
    svc = PaperService()
    return await svc.get_status(paper_id)
