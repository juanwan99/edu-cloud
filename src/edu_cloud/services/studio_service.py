"""StudioService: document CRUD with version tracking and status state machine."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.document import Document, DocumentVersion
from edu_cloud.services.exceptions import NotFoundError, PermissionDeniedError, StateError

VALID_TRANSITIONS = {
    "draft": ["reviewed"],
    "reviewed": ["pending", "executed"],
    "pending": ["approved", "rejected"],
    "rejected": ["draft"],
    "approved": ["executed"],
    "executed": [],
}


class StudioService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_document(
        self,
        type: str,
        title: str,
        content_json: dict,
        school_id: str,
        created_by: str,
        source_context: dict | None = None,
        ai_session_id: str | None = None,
    ) -> Document:
        doc = Document(
            type=type,
            title=title,
            status="draft",
            content_json=content_json,
            school_id=school_id,
            created_by=created_by,
            source_context=source_context,
            ai_session_id=ai_session_id,
            version=1,
        )
        self.db.add(doc)
        await self.db.flush()
        return doc

    async def update_document(
        self,
        doc_id: str,
        content_json: dict,
        edited_by: str,
        change_summary: str = "",
        school_id: str | None = None,
    ) -> Document:
        doc = await self._get_doc(doc_id, school_id=school_id)
        # Save old version before overwriting
        self.db.add(
            DocumentVersion(
                document_id=doc.id,
                version=doc.version,
                content_json=doc.content_json,
                edited_by=edited_by,
                change_summary=change_summary,
            )
        )
        doc.content_json = content_json
        doc.version += 1
        await self.db.flush()
        return doc

    async def transition_status(
        self, doc_id: str, new_status: str, school_id: str | None = None
    ) -> Document:
        doc = await self._get_doc(doc_id, school_id=school_id)
        allowed = VALID_TRANSITIONS.get(doc.status, [])
        if new_status not in allowed:
            raise StateError(
                f"Cannot transition from '{doc.status}' to '{new_status}'"
            )
        doc.status = new_status
        await self.db.flush()
        return doc

    async def list_documents(
        self,
        school_id: str,
        created_by: str | None = None,
        status: str | None = None,
    ) -> list[Document]:
        q = select(Document).where(Document.school_id == school_id)
        if created_by:
            # F2 fix: 同时匹配 created_by 和 assigned_to，确保自动拟稿文档对被指派教师可见
            from sqlalchemy import or_
            q = q.where(or_(Document.created_by == created_by, Document.assigned_to == created_by))
        if status:
            q = q.where(Document.status == status)
        q = q.order_by(Document.created_at.desc())
        return list((await self.db.execute(q)).scalars().all())

    async def get_document(
        self, doc_id: str, school_id: str | None = None
    ) -> Document:
        return await self._get_doc(doc_id, school_id=school_id)

    async def _get_doc(
        self, doc_id: str, school_id: str | None = None
    ) -> Document:
        doc = await self.db.get(Document, doc_id)
        if not doc:
            raise NotFoundError(f"Document {doc_id} not found")
        if school_id and doc.school_id != school_id:
            raise PermissionDeniedError(
                "Cannot access documents from other schools"
            )
        return doc
