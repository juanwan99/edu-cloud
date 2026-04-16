# P2 Studio 产出实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现右栏 Studio 文档生成——AI 按模板生成报告/评语，教师可编辑、导出 PDF，需审批的通知走审批流。

**Architecture:** Document 模型（状态机 draft→reviewed→approved→executed）+ 模板系统 + L4 工具（AI Agent 可触发生成）+ 固化审批链。（Tiptap 富文本、WeasyPrint PDF 导出延期到 P2-后续迭代）

**Tech Stack:** SQLAlchemy (Document/DocumentVersion/ApprovalFlow), L4 tools, Vue 3 (Naive UI)

**Design Doc:** `docs/plans/2026-03-21-super-platform-design.md` §6

**P1 基础:** 138 tests, AI Agent (ReAct + 4 L1 tools), SSE chat, ToolRegistry

**完成标志:** 班主任点击"班级报告"模板 → AI 生成四段报告（含真实数据填充）→ 教师编辑措辞 → 确认审阅（PDF 导出延期到 P2-后续迭代，可用浏览器打印替代）

---

## 文件结构

### 新增文件（后端）

```
src/edu_cloud/
├── models/
│   ├── document.py          # Document + DocumentVersion 模型
│   └── approval.py          # ApprovalFlow + ApprovalStep 模型
├── services/
│   ├── studio_service.py    # 文档 CRUD + 状态机 + 版本管理
│   └── approval_service.py  # 审批流创建/推进/驳回
├── api/
│   └── studio.py            # Studio REST API（文档 CRUD + 状态转换）
├── ai/tools/
│   └── actions.py           # L4 执行动作工具（generate_report/generate_comment）
└── templates/
    └── document_templates.py # 模板定义（班级报告/学科分析/学生评语/家长通知）
```

### 新增文件（前端）

```
frontend/src/
├── components/studio/
│   ├── StudioPanel.vue      # 重写：模板卡片 + 行动队列
│   ├── TemplateCards.vue     # 模板卡片网格
│   └── DocumentPreview.vue  # 文档预览 + 编辑（Tiptap 富文本延期到 P2-后续迭代）
└── stores/
    └── studio.js            # Studio 状态管理
```

### 修改文件

```
src/edu_cloud/api/app.py             # 注册 studio router
src/edu_cloud/ai/agent.py            # ROLE_TOOL_CATEGORIES 添加 L4
src/edu_cloud/ai/tools/__init__.py   # 导入 actions
src/edu_cloud/core/permissions.py    # 确认 GENERATE_REPORT 等权限已存在 + subject_teacher 角色添加 GENERATE_REPORT
frontend/src/components/workspace/DataView.vue  # Studio 交互联动
pyproject.toml                       # 添加 weasyprint 依赖
```

### 测试文件

```
tests/
├── test_models/test_document.py     # Document/Version 模型测试
├── test_services/test_studio.py     # StudioService 状态机测试
├── test_services/test_approval.py   # 审批流测试
├── test_api/test_studio_api.py      # Studio API 集成测试
└── test_ai/test_tools_actions.py    # L4 工具测试
```

> **P2 范围声明:** 审批 API 接口（ApprovalBadge.vue 等）、Tiptap 富文本编辑器集成、WeasyPrint PDF 导出延期到 P2-后续迭代。本批次实现：Document 模型 + 模板 + StudioService + L4 工具 + Studio API (CRUD + 状态转换) + 前端基础交互。

---

## Task 1: Document 数据模型

**Files:**
- Create: `src/edu_cloud/models/document.py`, `src/edu_cloud/models/approval.py`
- Test: `tests/test_models/test_document.py`

- [ ] **Step 1: 写 Document 模型测试**

```python
# tests/test_models/test_document.py
from edu_cloud.models.document import Document, DocumentVersion
from edu_cloud.models.approval import ApprovalFlow, ApprovalStep

def test_document_fields():
    cols = {c.name for c in Document.__table__.columns}
    assert "type" in cols
    assert "title" in cols
    assert "status" in cols
    assert "content_json" in cols
    assert "content_html" in cols
    assert "pdf_url" in cols
    assert "source_context" in cols
    assert "ai_session_id" in cols
    assert "created_by" in cols
    assert "approved_by" in cols
    assert "school_id" in cols
    assert "version" in cols

def test_document_status_default():
    """新文档默认 draft 状态"""
    d = Document(type="report", title="测试", school_id="s1", created_by="u1")
    assert d.status == "draft"
    assert d.version == 1

def test_document_version_fields():
    cols = {c.name for c in DocumentVersion.__table__.columns}
    assert "document_id" in cols
    assert "version" in cols
    assert "content_json" in cols
    assert "edited_by" in cols
    assert "change_summary" in cols

def test_approval_flow_fields():
    cols = {c.name for c in ApprovalFlow.__table__.columns}
    assert "document_id" in cols
    assert "chain_type" in cols
    assert "current_step" in cols
    assert "status" in cols

def test_approval_step_fields():
    cols = {c.name for c in ApprovalStep.__table__.columns}
    assert "flow_id" in cols
    assert "approver_id" in cols
    assert "step_order" in cols
    assert "status" in cols
    assert "comment" in cols
```

- [ ] **Step 2: 运行确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_models/test_document.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 Document + DocumentVersion 模型**

```python
# src/edu_cloud/models/document.py
from sqlalchemy import Column, String, Integer, JSON, Text, ForeignKey, DateTime
from edu_cloud.models.base import Base, IdMixin, TimestampMixin

class Document(Base, IdMixin, TimestampMixin):
    __tablename__ = "documents"

    type = Column(String(50), nullable=False)           # report / notification / comment / paper
    title = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, default="draft")  # draft→reviewed→pending→approved→executed
    content_json = Column(JSON, nullable=True)           # 结构化内容
    content_html = Column(Text, nullable=True)           # 渲染后 HTML
    pdf_url = Column(String, nullable=True)              # PDF 路径
    source_context = Column(JSON, nullable=True)         # 生成时的上下文
    ai_session_id = Column(String, nullable=True)        # 关联 AI 会话
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    approved_by = Column(String, ForeignKey("users.id"), nullable=True)
    executed_at = Column(DateTime, nullable=True)
    execution_result = Column(JSON, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    school_id = Column(String, ForeignKey("registered_schools.id"), nullable=False)

class DocumentVersion(Base, IdMixin, TimestampMixin):
    __tablename__ = "document_versions"

    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    version = Column(Integer, nullable=False)
    content_json = Column(JSON, nullable=True)
    edited_by = Column(String, ForeignKey("users.id"), nullable=False)
    change_summary = Column(String(500), nullable=True)
```

- [ ] **Step 4: 实现 ApprovalFlow + ApprovalStep 模型**

```python
# src/edu_cloud/models/approval.py
from sqlalchemy import Column, String, Integer, ForeignKey, Text, DateTime
from edu_cloud.models.base import Base, IdMixin, TimestampMixin

class ApprovalFlow(Base, IdMixin, TimestampMixin):
    __tablename__ = "approval_flows"

    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chain_type = Column(String(50), nullable=False)     # class_notification / school_notification / emergency
    current_step = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending")  # pending / approved / rejected

class ApprovalStep(Base, IdMixin, TimestampMixin):
    __tablename__ = "approval_steps"

    flow_id = Column(String, ForeignKey("approval_flows.id"), nullable=False)
    step_order = Column(Integer, nullable=False)
    approver_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), nullable=False, default="waiting")  # waiting / approved / rejected
    comment = Column(Text, nullable=True)
    acted_at = Column(DateTime, nullable=True)
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_models/test_document.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/models/document.py src/edu_cloud/models/approval.py tests/test_models/test_document.py
git commit -m "feat(P2-1): Document + DocumentVersion + ApprovalFlow 数据模型"
```

**审查清单:**
- ✓ Document 状态默认 draft, version 默认 1
- ✓ 所有表带 school_id（RLS 隔离）或通过 document FK 间接关联
- ✓ ApprovalStep 有 step_order 保证审批顺序
- ✗ 不应在模型层做状态转换逻辑（由 service 层处理）

**边界条件:**
- status 取值范围外的字符串 → 期望: DB 层不拦截（应用层验证）
- version=0 → 期望: 不应出现，默认 1
- document_id FK 不存在 → 期望: 外键错误

**测试契约:**
1. 模型字段完整性 + 默认值
   - 入口: 直接构造 ORM 对象
   - 反例: 错误实现可能遗漏 default 值导致 NOT NULL 插入失败
   - 边界: 最小字段集 / 全字段 / nullable 字段缺失
   - 回归: N/A
   - 命令: `python -m pytest tests/test_models/test_document.py -v`

---

## Task 2: 模板系统 + StudioService

**Files:**
- Create: `src/edu_cloud/templates/document_templates.py`, `src/edu_cloud/services/studio_service.py`
- Test: `tests/test_services/test_studio.py`

- [ ] **Step 1: 写模板系统测试**

```python
# tests/test_services/test_studio.py
import pytest
from edu_cloud.templates.document_templates import TEMPLATES, get_templates_for_role
from edu_cloud.services.studio_service import StudioService

def test_templates_have_required_keys():
    """每个模板必须有 name/sections/available_roles"""
    for key, tmpl in TEMPLATES.items():
        assert "name" in tmpl, f"{key} missing name"
        assert "sections" in tmpl, f"{key} missing sections"
        assert "available_roles" in tmpl, f"{key} missing available_roles"

def test_get_templates_for_homeroom_teacher():
    """班主任可用模板包含班级报告和评语"""
    templates = get_templates_for_role("homeroom_teacher")
    keys = [t["key"] for t in templates]
    assert "class_report" in keys
    assert "student_comment" in keys

def test_get_templates_for_parent():
    """家长无可用模板"""
    templates = get_templates_for_role("parent")
    assert len(templates) == 0

@pytest.mark.asyncio
async def test_create_document(db, seed_teacher):
    """创建文档草稿"""
    svc = StudioService(db)
    doc = await svc.create_document(
        type="report", title="七年级2班期中分析",
        content_json={"overview": "全班表现良好"},
        school_id=seed_teacher["school_id"],
        created_by=seed_teacher["user_id"],
        source_context={"exam_id": "e1", "class_id": "c1"},
    )
    assert doc.status == "draft"
    assert doc.version == 1

@pytest.mark.asyncio
async def test_update_document_creates_version(db, seed_teacher):
    """编辑文档自动创建版本记录"""
    svc = StudioService(db)
    doc = await svc.create_document(
        type="report", title="测试",
        content_json={"body": "v1"},
        school_id=seed_teacher["school_id"],
        created_by=seed_teacher["user_id"],
    )
    updated = await svc.update_document(
        doc.id, content_json={"body": "v2"},
        edited_by=seed_teacher["user_id"],
        change_summary="修改正文",
    )
    assert updated.version == 2
    assert updated.content_json["body"] == "v2"

@pytest.mark.asyncio
async def test_status_transition_draft_to_reviewed(db, seed_teacher):
    """draft → reviewed 转换"""
    svc = StudioService(db)
    doc = await svc.create_document(
        type="report", title="测试", content_json={},
        school_id=seed_teacher["school_id"],
        created_by=seed_teacher["user_id"],
    )
    doc = await svc.transition_status(doc.id, "reviewed")
    assert doc.status == "reviewed"

@pytest.mark.asyncio
async def test_invalid_status_transition(db, seed_teacher):
    """不允许跳过状态"""
    svc = StudioService(db)
    doc = await svc.create_document(
        type="report", title="测试", content_json={},
        school_id=seed_teacher["school_id"],
        created_by=seed_teacher["user_id"],
    )
    from edu_cloud.services.exceptions import StateError
    with pytest.raises(StateError):
        await svc.transition_status(doc.id, "approved")  # 不能从 draft 直接到 approved
```

- [ ] **Step 2: 创建 seed_teacher fixture（如不存在则更新 conftest）**

```python
# tests/conftest.py — 确保 seed_teacher fixture 返回 dict 包含 user_id 和 school_id
# P0 已有类似 fixture，按需调整返回格式
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_services/test_studio.py -v`
Expected: FAIL

- [ ] **Step 4: 实现模板系统**

```python
# src/edu_cloud/templates/__init__.py
# （空）

# src/edu_cloud/templates/document_templates.py
TEMPLATES = {
    "class_report": {
        "key": "class_report",
        "name": "班级学情分析报告",
        "sections": [
            {"key": "overview", "title": "总体概况", "prompt": "概括本班本次考试整体表现，包括参加人数、平均分、及格率"},
            {"key": "subject_analysis", "title": "各题分析", "prompt": "分析得分率较低的题目，指出共性薄弱点"},
            {"key": "student_tiers", "title": "分层分析", "prompt": "将学生分为优秀/良好/待提高三层，各层人数和特点"},
            {"key": "suggestions", "title": "教学建议", "prompt": "针对薄弱知识点给出 2-3 条具体教学建议"},
        ],
        "required_context": ["exam_id", "class_id"],
        "available_roles": ["homeroom_teacher", "grade_leader", "academic_director", "principal"],
        "requires_approval": False,
    },
    "subject_analysis": {
        "key": "subject_analysis",
        "name": "学科分析报告",
        "sections": [
            {"key": "overview", "title": "学科概况", "prompt": "本次考试该学科的整体情况"},
            {"key": "difficulty", "title": "难度分析", "prompt": "各题得分率和区分度"},
            {"key": "suggestions", "title": "改进建议", "prompt": "教学改进方向"},
        ],
        "required_context": ["exam_id"],
        "available_roles": ["subject_teacher", "academic_director", "principal"],
        "requires_approval": False,
    },
    "student_comment": {
        "key": "student_comment",
        "name": "学生评语",
        "sections": [
            {"key": "academic", "title": "学业表现", "prompt": "基于成绩数据评价学习情况"},
            {"key": "growth", "title": "成长建议", "prompt": "给出个性化的改进建议"},
        ],
        "required_context": ["student_id"],
        "available_roles": ["homeroom_teacher"],
        "requires_approval": False,
    },
    "parent_notification": {
        "key": "parent_notification",
        "name": "家长通知",
        "sections": [
            {"key": "greeting", "title": "称呼", "prompt": "尊敬的家长"},
            {"key": "body", "title": "正文", "prompt": "根据事件类型生成通知正文"},
            {"key": "requirements", "title": "注意事项", "prompt": "需要家长配合的事项"},
            {"key": "closing", "title": "落款", "prompt": "学校名+日期"},
        ],
        "required_context": ["event_type"],
        "available_roles": ["homeroom_teacher", "academic_director", "principal"],
        "requires_approval": True,
        "approval_chain": "class_notification",
    },
}


def get_templates_for_role(role: str) -> list[dict]:
    """返回该角色可用的模板列表"""
    result = []
    for tmpl in TEMPLATES.values():
        if role in tmpl["available_roles"]:
            result.append({
                "key": tmpl["key"],
                "name": tmpl["name"],
                "requires_approval": tmpl.get("requires_approval", False),
                "required_context": tmpl.get("required_context", []),
            })
    return result
```

- [ ] **Step 5: 实现 StudioService**

```python
# src/edu_cloud/services/studio_service.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.models.document import Document, DocumentVersion
from edu_cloud.services.exceptions import NotFoundError, StateError, PermissionDeniedError

VALID_TRANSITIONS = {
    "draft": ["reviewed"],
    "reviewed": ["pending", "executed"],      # 无需审批可直接 executed
    "pending": ["approved", "rejected"],
    "rejected": ["draft"],                     # 打回后重新编辑
    "approved": ["executed"],
    "executed": [],                            # 终态
}

class StudioService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_document(
        self, type: str, title: str, content_json: dict,
        school_id: str, created_by: str,
        source_context: dict | None = None,
        ai_session_id: str | None = None,
    ) -> Document:
        doc = Document(
            type=type, title=title, status="draft",
            content_json=content_json,
            school_id=school_id, created_by=created_by,
            source_context=source_context,
            ai_session_id=ai_session_id,
            version=1,
        )
        self.db.add(doc)
        await self.db.flush()
        return doc

    async def update_document(
        self, doc_id: str, content_json: dict,
        edited_by: str, change_summary: str = "",
        school_id: str = None,
    ) -> Document:
        doc = await self._get_doc(doc_id, school_id=school_id)
        # 保存旧版本
        self.db.add(DocumentVersion(
            document_id=doc.id, version=doc.version,
            content_json=doc.content_json,
            edited_by=edited_by, change_summary=change_summary,
        ))
        # 更新文档
        doc.content_json = content_json
        doc.version += 1
        await self.db.flush()
        return doc

    async def transition_status(self, doc_id: str, new_status: str, school_id: str = None) -> Document:
        doc = await self._get_doc(doc_id, school_id=school_id)
        allowed = VALID_TRANSITIONS.get(doc.status, [])
        if new_status not in allowed:
            raise StateError(f"Cannot transition from '{doc.status}' to '{new_status}'")
        doc.status = new_status
        await self.db.flush()
        return doc

    async def list_documents(self, school_id: str, created_by: str | None = None, status: str | None = None) -> list[Document]:
        q = select(Document).where(Document.school_id == school_id)
        if created_by:
            q = q.where(Document.created_by == created_by)
        if status:
            q = q.where(Document.status == status)
        q = q.order_by(Document.created_at.desc())
        return (await self.db.execute(q)).scalars().all()

    async def get_document(self, doc_id: str, school_id: str = None) -> Document:
        return await self._get_doc(doc_id, school_id=school_id)

    async def _get_doc(self, doc_id: str, school_id: str = None) -> Document:
        doc = await self.db.get(Document, doc_id)
        if not doc:
            raise NotFoundError(f"Document {doc_id} not found")
        if school_id and doc.school_id != school_id:
            raise PermissionDeniedError("Cannot access documents from other schools")
        return doc
```

- [ ] **Step 6: 创建 templates 包目录**

```bash
mkdir -p src/edu_cloud/templates
touch src/edu_cloud/templates/__init__.py
```

- [ ] **Step 7: 运行确认通过**

Run: `python -m pytest tests/test_services/test_studio.py -v`
Expected: PASS (7 tests)

- [ ] **Step 8: Commit**

```bash
git add src/edu_cloud/templates/ src/edu_cloud/services/studio_service.py tests/
git commit -m "feat(P2-2): 模板系统 + StudioService（状态机 + 版本管理）"
```

**审查清单:**
- ✓ 4 个模板定义完整（班级报告/学科分析/学生评语/家长通知）
- ✓ 模板按角色过滤
- ✓ 状态转换有合法性验证（VALID_TRANSITIONS）
- ✓ 编辑时自动创建 DocumentVersion
- ✗ 不应允许 draft→approved 跳转

**边界条件:**
- 不存在的 doc_id → 期望: NotFoundError
- draft→executed（跳过 reviewed）→ 期望: StateError
- 连续编辑 3 次 → 期望: version=4, 3 个 DocumentVersion 记录

**测试契约:**
1. 状态机合法性
   - 入口: `svc.transition_status(doc_id, new_status)`
   - 反例: 错误实现可能不验证转换合法性
   - 边界: 每种非法转换 / 已执行文档再编辑
   - 回归: N/A
   - 命令: `python -m pytest tests/test_services/test_studio.py -v`
2. 版本管理
   - 入口: `svc.update_document(doc_id, content, edited_by)`
   - 反例: 错误实现可能覆盖而非追加版本
   - 边界: 首次编辑 / 连续编辑 / 同时两人编辑
   - 回归: N/A
   - 命令: `python -m pytest tests/test_services/test_studio.py::test_update_document_creates_version -v`

---

## Task 3: 审批服务

**Files:**
- Create: `src/edu_cloud/services/approval_service.py`
- Test: `tests/test_services/test_approval.py`

- [ ] **Step 1: 写审批服务测试**

```python
# tests/test_services/test_approval.py
import pytest
from edu_cloud.services.approval_service import ApprovalService, APPROVAL_CHAINS
from edu_cloud.services.exceptions import StateError, PermissionDeniedError

def test_approval_chains_defined():
    """审批链定义完整"""
    assert "class_notification" in APPROVAL_CHAINS
    assert "school_notification" in APPROVAL_CHAINS
    assert "emergency" in APPROVAL_CHAINS

@pytest.mark.asyncio
async def test_create_approval_flow(db, seed_teacher, seed_approver):
    """创建审批流"""
    svc = ApprovalService(db)
    flow = await svc.create_flow(
        document_id="doc1",
        chain_type="class_notification",
        approver_ids=[seed_approver["user_id"]],
    )
    assert flow.status == "pending"
    assert flow.current_step == 0

@pytest.mark.asyncio
async def test_approve_step(db, seed_teacher, seed_approver):
    """审批人批准"""
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
    assert result.status == "approved"  # 单人审批链，批准后流程完成

@pytest.mark.asyncio
async def test_reject_step(db, seed_teacher, seed_approver):
    """审批人驳回"""
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
async def test_wrong_approver_denied(db, seed_teacher, seed_approver):
    """非审批人不能审批"""
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
async def test_already_completed_flow_cannot_act(db, seed_teacher, seed_approver):
    """F6 反例: 已 approved 的审批流不能再操作"""
    svc = ApprovalService(db)
    flow = await svc.create_flow(
        document_id="doc1",
        chain_type="class_notification",
        approver_ids=[seed_approver["user_id"]],
    )
    # 先批准
    await svc.act_on_step(flow_id=flow.id, approver_id=seed_approver["user_id"], action="approved")
    # 再次操作应失败（流程已完成，current_step 越界）
    with pytest.raises((StateError, PermissionDeniedError, IndexError)):
        await svc.act_on_step(flow_id=flow.id, approver_id=seed_approver["user_id"], action="approved")
```

- [ ] **Step 2: 添加 seed_approver fixture 到 conftest**

```python
# tests/conftest.py 追加
@pytest.fixture
async def seed_approver(db):
    """创建一个教务主任（审批人）"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    user = User(username="director1", display_name="王主任")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    from edu_cloud.models.school import RegisteredSchool
    school = (await db.execute(select(RegisteredSchool))).scalars().first()
    if not school:
        school = RegisteredSchool(name="审批测试校", code="APTEST", district="测试区", api_key_hash="x")
        db.add(school)
        await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.commit()
    return {"user_id": user.id, "school_id": school.id}
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_services/test_approval.py -v`
Expected: FAIL

- [ ] **Step 4: 实现审批服务**

```python
# src/edu_cloud/services/approval_service.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.models.approval import ApprovalFlow, ApprovalStep
from edu_cloud.services.exceptions import NotFoundError, PermissionDeniedError, StateError
from datetime import datetime, timezone

APPROVAL_CHAINS = {
    "class_notification": {"description": "班主任 → 教务主任"},
    "school_notification": {"description": "教务主任 → 校长"},
    "emergency": {"description": "校长直批"},
}

class ApprovalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_flow(
        self, document_id: str, chain_type: str, approver_ids: list[str],
    ) -> ApprovalFlow:
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
            self.db.add(ApprovalStep(
                flow_id=flow.id,
                step_order=i,
                approver_id=approver_id,
                status="waiting" if i == 0 else "waiting",
            ))
        await self.db.flush()
        return flow

    async def act_on_step(
        self, flow_id: str, approver_id: str, action: str, comment: str | None = None,
    ) -> ApprovalFlow:
        flow = await self.db.get(ApprovalFlow, flow_id)
        if not flow:
            raise NotFoundError(f"Flow {flow_id} not found")

        # 找当前步骤
        steps = (await self.db.execute(
            select(ApprovalStep)
            .where(ApprovalStep.flow_id == flow.id)
            .order_by(ApprovalStep.step_order)
        )).scalars().all()

        current = steps[flow.current_step] if flow.current_step < len(steps) else None
        if not current or current.approver_id != approver_id:
            raise PermissionDeniedError("Not the current approver")

        current.status = action
        current.comment = comment
        current.acted_at = datetime.now(timezone.utc)

        if action == "rejected":
            flow.status = "rejected"
        elif action == "approved":
            if flow.current_step + 1 >= len(steps):
                flow.status = "approved"  # 全部审批完成
            else:
                flow.current_step += 1    # 进入下一步
        await self.db.flush()
        return flow
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_services/test_approval.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/services/approval_service.py tests/
git commit -m "feat(P2-3): 审批服务 — 固化审批链 + 逐步推进 + 权限校验"
```

**审查清单:**
- ✓ 3 种审批链（班级通知/全校通知/紧急）
- ✓ 非审批人被拒（PermissionDeniedError）
- ✓ 驳回时整个流程变 rejected
- ✓ 多步审批逐步推进 current_step
- ✗ 不应允许已完成的审批流再次操作

**边界条件:**
- flow_id 不存在 → 期望: NotFoundError
- 已 approved 的流程再 approve → 期望: 错误（越界）
- approver_ids 为空 → 期望: 流程立即 approved 或报错

**测试契约:**
1. 审批权限隔离
   - 入口: `svc.act_on_step(flow_id, wrong_approver, "approved")`
   - 反例: 错误实现可能不检查 approver_id
   - 边界: 正确审批人 / 错误审批人 / 已审批的流程
   - 回归: N/A
   - 命令: `python -m pytest tests/test_services/test_approval.py -v`

---

## Task 4: L4 执行动作工具

**Files:**
- Create: `src/edu_cloud/ai/tools/actions.py`
- Modify: `src/edu_cloud/ai/tools/__init__.py`, `src/edu_cloud/ai/agent.py`
- Test: `tests/test_ai/test_tools_actions.py`

- [ ] **Step 1: 写 L4 工具测试**

```python
# tests/test_ai/test_tools_actions.py
import pytest
from edu_cloud.ai.tools.actions import generate_report, generate_comment

@pytest.mark.asyncio
async def test_generate_report(db, seed_exam_with_results):
    """生成班级报告创建 Document"""
    from edu_cloud.models.document import Document
    from sqlalchemy import select

    result = await generate_report(
        template="class_report",
        context={"exam_id": seed_exam_with_results["exam_id"], "class_id": seed_exam_with_results["class_id"]},
        _db=db,
        _school_id=seed_exam_with_results["school_id"],
        _user_id="test_user",
        _class_ids=[seed_exam_with_results["class_id"]],
    )
    assert "document_id" in result
    assert result["status"] == "draft"
    assert result["title"] is not None

    # 验证 DB 中确实创建了文档
    doc = await db.get(Document, result["document_id"])
    assert doc is not None
    assert doc.type == "report"

@pytest.mark.asyncio
async def test_generate_report_unknown_template(db, seed_exam_with_results):
    """未知模板返回错误"""
    result = await generate_report(
        template="nonexistent",
        context={},
        _db=db, _school_id=seed_exam_with_results["school_id"],
        _user_id="test", _class_ids=[],
    )
    assert "error" in result

@pytest.mark.asyncio
async def test_generate_report_missing_context(db, seed_exam_with_results):
    """F6 反例: 缺少必需 exam_id → 返回错误"""
    result = await generate_report(
        template="class_report",
        context={},  # class_report 需要 exam_id + class_id
        _db=db, _school_id=seed_exam_with_results["school_id"],
        _user_id="test", _class_ids=[],
    )
    assert "error" in result
    assert "缺少必需上下文" in result["error"]

@pytest.mark.asyncio
async def test_generate_comment(db, seed_exam_with_results):
    """生成学生评语"""
    result = await generate_comment(
        student_number="T000",
        _db=db,
        _school_id=seed_exam_with_results["school_id"],
        _user_id="test_user",
        _class_ids=[seed_exam_with_results["class_id"]],
    )
    assert "document_id" in result
    assert result["type"] == "comment"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_ai/test_tools_actions.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 L4 工具**

```python
# src/edu_cloud/ai/tools/actions.py
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.ai.registry import tools
from edu_cloud.services.studio_service import StudioService
from edu_cloud.templates.document_templates import TEMPLATES

@tools.register(
    name="generate_report",
    description="根据模板和上下文生成报告草稿。返回文档 ID，教师可在 Studio 中编辑。",
    parameters={
        "type": "object",
        "properties": {
            "template": {"type": "string", "description": "模板 key：class_report / subject_analysis / parent_notification"},
            "context": {"type": "object", "description": "上下文参数，如 exam_id, class_id"},
        },
        "required": ["template", "context"],
    },
    category="L4_action",
)
async def generate_report(
    template: str, context: dict,
    _db: AsyncSession = None, _school_id: str = None,
    _user_id: str = None, _class_ids: list = None,
) -> dict:
    if template not in TEMPLATES:
        return {"error": f"未知模板: {template}"}

    tmpl = TEMPLATES[template]

    # F3 fix: 验证 required_context
    missing = [k for k in tmpl.get("required_context", []) if k not in context]
    if missing:
        return {"error": f"缺少必需上下文: {', '.join(missing)}"}

    svc = StudioService(_db)

    # 获取真实数据填充 section 内容（基础文本摘要，非 AI 生成散文）
    # AI 对话会话后续可进一步润色和细化
    from edu_cloud.ai.tools.analytics import get_exam_scores, get_class_stats
    data_summary = {}
    try:
        if "exam_id" in context:
            scores = await get_exam_scores(
                exam_id=context["exam_id"],
                _db=_db, _school_id=_school_id, _class_ids=_class_ids,
            )
            data_summary["scores"] = scores
        if "class_id" in context:
            stats = await get_class_stats(
                class_id=context["class_id"],
                _db=_db, _school_id=_school_id, _class_ids=_class_ids,
            )
            data_summary["stats"] = stats
    except Exception:
        pass  # 数据获取失败时用空内容降级

    content = {}
    for section in tmpl["sections"]:
        # 根据 section key 和 data_summary 生成基础内容
        section_content = _build_section_content(section["key"], data_summary)
        content[section["key"]] = {
            "title": section["title"],
            "content": section_content,
            "prompt": section["prompt"],
        }

    doc = await svc.create_document(
        type="report" if "notification" not in template else "notification",
        title=f"{tmpl['name']}",
        content_json=content,
        school_id=_school_id,
        created_by=_user_id,
        source_context=context,
    )
    await _db.commit()

    return {
        "document_id": doc.id,
        "title": doc.title,
        "status": doc.status,
        "type": doc.type,
        "sections": list(content.keys()),
        "requires_approval": tmpl.get("requires_approval", False),
        "message": f"已创建{tmpl['name']}草稿，请在右栏 Studio 中查看和编辑。",
    }


def _build_section_content(section_key: str, data_summary: dict) -> str:
    """根据 section key 和查询数据生成基础文本内容（非 AI 散文）。"""
    scores = data_summary.get("scores", {})
    stats = data_summary.get("stats", {})
    if section_key == "overview" and stats:
        avg = stats.get("average", "N/A")
        count = stats.get("student_count", "N/A")
        pass_rate = stats.get("pass_rate", "N/A")
        return f"全班 {count} 人参加考试，平均分 {avg}，及格率 {pass_rate}。"
    if section_key == "subject_analysis" and scores:
        return f"成绩数据已加载（共 {len(scores.get('items', []))} 条记录），待教师审阅和 AI 细化。"
    if section_key == "student_tiers" and stats:
        return f"优秀: {stats.get('excellent_count', 'N/A')} 人，良好: {stats.get('good_count', 'N/A')} 人，待提高: {stats.get('needs_improvement_count', 'N/A')} 人。"
    return ""  # 无数据时留空，AI 对话后续填充


@tools.register(
    name="generate_comment",
    description="为指定学生生成评语草稿。",
    parameters={
        "type": "object",
        "properties": {
            "student_number": {"type": "string", "description": "学生学号"},
        },
        "required": ["student_number"],
    },
    category="L4_action",
)
async def generate_comment(
    student_number: str,
    _db: AsyncSession = None, _school_id: str = None,
    _user_id: str = None, _class_ids: list = None,
) -> dict:
    from edu_cloud.models.student import Student
    from sqlalchemy import select

    student = (await _db.execute(
        select(Student).where(Student.student_number == student_number, Student.school_id == _school_id)
    )).scalar_one_or_none()
    if not student:
        return {"error": f"学生 {student_number} 不存在"}

    svc = StudioService(_db)
    doc = await svc.create_document(
        type="comment",
        title=f"{student.name} 评语",
        content_json={
            "student_name": student.name,
            "student_number": student.student_number,
            "academic": {"title": "学业表现", "content": ""},
            "growth": {"title": "成长建议", "content": ""},
        },
        school_id=_school_id,
        created_by=_user_id,
        source_context={"student_id": student.id},
    )
    await _db.commit()

    return {
        "document_id": doc.id,
        "type": "comment",
        "title": doc.title,
        "status": "draft",
        "message": f"已为{student.name}创建评语草稿。",
    }
```

- [ ] **Step 4: 更新工具导入和角色映射**

```python
# src/edu_cloud/ai/tools/__init__.py — 追加
from edu_cloud.ai.tools import actions  # noqa: F401

# src/edu_cloud/ai/agent.py — ROLE_TOOL_CATEGORIES 追加 L4
ROLE_TOOL_CATEGORIES = {
    "platform_admin": None,
    "district_admin": ["L2_cross_school"],
    "principal": ["L1_analytics", "L2_cross_school", "L4_action"],
    "academic_director": ["L1_analytics", "L2_cross_school", "L4_action"],
    "grade_leader": ["L1_analytics", "L4_action"],
    "homeroom_teacher": ["L1_analytics", "L4_action"],
    "subject_teacher": ["L1_analytics", "L4_action"],
}

# src/edu_cloud/ai/agent.py — registry.execute() 注入 _user_id（约第 121 行）
# L4 工具需要 _user_id 来设置 Document.created_by，现有调用缺少此参数。
# 将 registry.execute() 的 kwargs 从：
#     _db=db, _school_id=school_id, _class_ids=class_ids,
# 改为：
#     _db=db, _school_id=school_id, _class_ids=class_ids, _user_id=user_id,
# （user_id 已在 agent.run() 签名中，无需额外传入）

# src/edu_cloud/core/permissions.py — subject_teacher 添加 GENERATE_REPORT
# 当前 subject_teacher 缺少此权限，导致科任教师无法使用 Studio API
# 在 "subject_teacher" 的权限集合中追加：
#     Permission.GENERATE_REPORT,
# 修改后应为：
#     "subject_teacher": {
#         Permission.VIEW_STUDENTS, Permission.VIEW_EXAMS, Permission.VIEW_SCORES,
#         Permission.VIEW_QUESTION_BANK,
#         Permission.GENERATE_REPORT,   # <-- 新增
#         Permission.USE_AI_CHAT, Permission.WRITE_PAPER,
#     },
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_ai/test_tools_actions.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: 全量测试**

Run: `python -m pytest --tb=short -q`
Expected: 138 + 新增全 PASS

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/ai/tools/ src/edu_cloud/ai/agent.py src/edu_cloud/core/permissions.py tests/
git commit -m "feat(P2-4): L4 执行动作工具 — generate_report + generate_comment + 角色映射 + subject_teacher 权限"
```

**审查清单:**
- ✓ generate_report 按模板创建 Document（status=draft）
- ✓ generate_comment 关联学生数据
- ✓ ROLE_TOOL_CATEGORIES 已添加 L4_action
- ✓ 未知模板返回 error 而非抛异常
- ✗ 不应在工具中自动提交审批（由教师手动操作）

**边界条件:**
- 未知模板 → 期望: 返回 error dict
- 学生不存在 → 期望: 返回 error dict
- _user_id 为空 → 期望: Document.created_by 为空（或报错）

**测试契约:**
1. L4 工具创建文档
   - 入口: `generate_report(template, context, _db, _school_id, _user_id)`
   - 反例: 错误实现可能不持久化到 DB
   - 边界: 未知模板 / 空 context / 缺少 required_context
   - 回归: N/A
   - 命令: `python -m pytest tests/test_ai/test_tools_actions.py -v`

---

## Task 5: Studio REST API

**Files:**
- Create: `src/edu_cloud/api/studio.py`
- Modify: `src/edu_cloud/api/app.py`
- Test: `tests/test_api/test_studio_api.py`

- [ ] **Step 1: 写 Studio API 测试**

```python
# tests/test_api/test_studio_api.py
import pytest

@pytest.mark.asyncio
async def test_get_templates(client, teacher_headers):
    """获取当前角色可用模板"""
    resp = await client.get("/api/v1/studio/templates", headers=teacher_headers)
    assert resp.status_code == 200
    templates = resp.json()
    assert len(templates) >= 1
    assert any(t["key"] == "class_report" for t in templates)

@pytest.mark.asyncio
async def test_list_documents_empty(client, teacher_headers):
    """无文档时返回空列表"""
    resp = await client.get("/api/v1/studio/documents", headers=teacher_headers)
    assert resp.status_code == 200
    assert resp.json() == []

@pytest.mark.asyncio
async def test_create_and_get_document(client, teacher_headers):
    """创建+查看文档"""
    create_resp = await client.post("/api/v1/studio/documents", json={
        "type": "report", "title": "测试报告",
        "content_json": {"overview": {"title": "概况", "content": "测试内容"}},
    }, headers=teacher_headers)
    assert create_resp.status_code == 201
    doc_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/studio/documents/{doc_id}", headers=teacher_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "测试报告"

@pytest.mark.asyncio
async def test_update_document(client, teacher_headers):
    """编辑文档"""
    resp = await client.post("/api/v1/studio/documents", json={
        "type": "report", "title": "测试",
        "content_json": {"body": "v1"},
    }, headers=teacher_headers)
    doc_id = resp.json()["id"]

    update_resp = await client.patch(f"/api/v1/studio/documents/{doc_id}", json={
        "content_json": {"body": "v2"},
        "change_summary": "修改正文",
    }, headers=teacher_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["version"] == 2

@pytest.mark.asyncio
async def test_transition_status(client, teacher_headers):
    """状态转换"""
    resp = await client.post("/api/v1/studio/documents", json={
        "type": "report", "title": "测试", "content_json": {},
    }, headers=teacher_headers)
    doc_id = resp.json()["id"]

    tr_resp = await client.post(f"/api/v1/studio/documents/{doc_id}/transition", json={
        "status": "reviewed",
    }, headers=teacher_headers)
    assert tr_resp.status_code == 200
    assert tr_resp.json()["status"] == "reviewed"

@pytest.mark.asyncio
async def test_studio_requires_auth(client):
    """未认证返回 401"""
    resp = await client.get("/api/v1/studio/templates")
    assert resp.status_code in (401, 403)

@pytest.mark.asyncio
async def test_cross_school_access_denied(client, teacher_headers, other_school_doc_id):
    """F6 反例: 学校 A 的用户不能访问学校 B 的文档"""
    resp = await client.get(
        f"/api/v1/studio/documents/{other_school_doc_id}",
        headers=teacher_headers,
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_api/test_studio_api.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 Studio API**

```python
# src/edu_cloud/api/studio.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.services.studio_service import StudioService
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
    docs = await svc.list_documents(school_id=school_id, created_by=user.id, status=status)
    return [_doc_to_dict(d) for d in docs]

@router.post("/documents", status_code=201)
async def create_document(
    body: dict,
    current=Depends(require_permission(Permission.GENERATE_REPORT)),
    db: AsyncSession = Depends(get_db),
):
    user = current["user"]
    role = current["current_role"]
    svc = StudioService(db)
    doc = await svc.create_document(
        type=body["type"], title=body["title"],
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
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = current["current_role"]
    school_id = getattr(role, "school_id", None)
    svc = StudioService(db)
    doc = await svc.get_document(doc_id, school_id=school_id)
    return _doc_to_dict(doc)

@router.patch("/documents/{doc_id}")
async def update_document(
    doc_id: str, body: dict,
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    doc_id: str, body: dict,
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = current["current_role"]
    school_id = getattr(role, "school_id", None)
    svc = StudioService(db)
    doc = await svc.transition_status(doc_id, body["status"], school_id=school_id)
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
        "created_at": str(doc.created_at) if doc.created_at else None,
    }
```

- [ ] **Step 4: 注册路由**

```python
# src/edu_cloud/api/app.py — 追加
from edu_cloud.api.studio import router as studio_router
app.include_router(studio_router)
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_api/test_studio_api.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: 全量测试**

Run: `python -m pytest --tb=short -q`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/api/studio.py src/edu_cloud/api/app.py tests/
git commit -m "feat(P2-5): Studio REST API — 模板/文档CRUD/状态转换/权限"
```

**审查清单:**
- ✓ GET /templates 按角色过滤
- ✓ POST /documents 创建文档（201）
- ✓ PATCH /documents/{id} 编辑+版本递增
- ✓ POST /documents/{id}/transition 状态转换
- ✓ 所有端点需要认证
- ✗ 不应允许跨 school_id 访问文档

**边界条件:**
- 未认证 → 401
- 文档不存在 → 404
- 非法状态转换 → 409

**测试契约:**
1. 文档 CRUD 完整链路
   - 入口: `POST /api/v1/studio/documents` → `GET` → `PATCH` → `transition`
   - 反例: 错误实现可能不持久化 version 增长
   - 边界: 空 content_json / 不存在的 doc_id / 重复创建
   - 回归: N/A
   - 命令: `python -m pytest tests/test_api/test_studio_api.py -v`

---

## Task 6: Studio 前端

**Files:**
- Modify: `frontend/src/components/studio/StudioPanel.vue`
- Create: `frontend/src/components/studio/TemplateCards.vue`, `frontend/src/components/studio/DocumentPreview.vue`
- Create: `frontend/src/stores/studio.js`

- [ ] **Step 1: 创建 studio store**

```javascript
// frontend/src/stores/studio.js
import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '../api/client.js'

export const useStudioStore = defineStore('studio', () => {
  const templates = ref([])
  const documents = ref([])
  const currentDoc = ref(null)
  const loading = ref(false)

  async function loadTemplates() {
    const { data } = await client.get('/studio/templates')
    templates.value = data
  }

  async function loadDocuments() {
    const { data } = await client.get('/studio/documents')
    documents.value = data
  }

  async function getDocument(docId) {
    loading.value = true
    try {
      const { data } = await client.get(`/studio/documents/${docId}`)
      currentDoc.value = data
    } finally { loading.value = false }
  }

  async function updateDocument(docId, contentJson, changeSummary) {
    const { data } = await client.patch(`/studio/documents/${docId}`, {
      content_json: contentJson, change_summary: changeSummary,
    })
    currentDoc.value = data
    await loadDocuments()
  }

  async function transitionStatus(docId, status) {
    const { data } = await client.post(`/studio/documents/${docId}/transition`, { status })
    currentDoc.value = data
    await loadDocuments()
  }

  return { templates, documents, currentDoc, loading, loadTemplates, loadDocuments, getDocument, updateDocument, transitionStatus }
})
```

- [ ] **Step 2: 创建 TemplateCards 组件**

```vue
<!-- frontend/src/components/studio/TemplateCards.vue -->
<template>
  <div>
    <n-h4 style="margin-bottom: 12px">生成</n-h4>
    <n-grid :cols="2" :x-gap="8" :y-gap="8">
      <n-gi v-for="tmpl in studioStore.templates" :key="tmpl.key">
        <n-card size="small" hoverable style="cursor: pointer" @click="$emit('select', tmpl)">
          <template #header>
            <n-text style="font-size: 13px">{{ tmpl.name }}</n-text>
          </template>
          <n-tag v-if="tmpl.requires_approval" size="tiny" type="warning">需审批</n-tag>
        </n-card>
      </n-gi>
    </n-grid>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useStudioStore } from '../../stores/studio.js'

const studioStore = useStudioStore()
defineEmits(['select'])
onMounted(() => studioStore.loadTemplates())
</script>
```

- [ ] **Step 3: 创建 DocumentPreview 组件**

```vue
<!-- frontend/src/components/studio/DocumentPreview.vue -->
<template>
  <n-modal v-model:show="visible" preset="card" style="width: 700px" :title="doc?.title || '文档预览'">
    <template v-if="doc">
      <div v-for="(section, key) in doc.content_json" :key="key" style="margin-bottom: 16px">
        <n-h4>{{ section.title || key }}</n-h4>
        <n-input
          v-model:value="editableContent[key]"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 10 }"
          placeholder="AI 将在此生成内容..."
        />
      </div>
      <n-space justify="end" style="margin-top: 16px">
        <n-button @click="handleSave">保存修改</n-button>
        <n-button type="primary" @click="handleConfirm">
          {{ doc.status === 'draft' ? '确认审阅' : '导出 PDF' }}
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useStudioStore } from '../../stores/studio.js'

const props = defineProps({ doc: Object })
const visible = defineModel('show', { type: Boolean })
const studioStore = useStudioStore()
const editableContent = ref({})

watch(() => props.doc, (newDoc) => {
  if (newDoc?.content_json) {
    const content = {}
    for (const [key, section] of Object.entries(newDoc.content_json)) {
      content[key] = section.content || section || ''
    }
    editableContent.value = content
  }
}, { immediate: true })

async function handleSave() {
  const updated = { ...props.doc.content_json }
  for (const [key, val] of Object.entries(editableContent.value)) {
    if (typeof updated[key] === 'object') updated[key].content = val
    else updated[key] = val
  }
  await studioStore.updateDocument(props.doc.id, updated, '手动编辑')
}

async function handleConfirm() {
  if (props.doc.status === 'draft') {
    await studioStore.transitionStatus(props.doc.id, 'reviewed')
  }
  // PDF 导出在后续实现
}
</script>
```

- [ ] **Step 4: 重写 StudioPanel**

```vue
<!-- frontend/src/components/studio/StudioPanel.vue -->
<template>
  <div style="padding: 12px; height: 100%; display: flex; flex-direction: column; overflow-y: auto;">
    <!-- 模板卡片 -->
    <TemplateCards @select="handleTemplateSelect" />

    <n-divider />

    <!-- 行动队列 -->
    <n-h4>文档</n-h4>
    <n-list v-if="studioStore.documents.length">
      <n-list-item v-for="doc in studioStore.documents" :key="doc.id" style="cursor: pointer" @click="openDoc(doc)">
        <n-thing :title="doc.title">
          <template #description>
            <n-space size="small">
              <n-tag :type="statusType(doc.status)" size="small">{{ doc.status }}</n-tag>
              <n-text depth="3" style="font-size: 12px">v{{ doc.version }}</n-text>
            </n-space>
          </template>
        </n-thing>
      </n-list-item>
    </n-list>
    <n-empty v-else description="暂无文档" size="small" />

    <!-- 文档预览弹窗 -->
    <DocumentPreview v-model:show="showPreview" :doc="studioStore.currentDoc" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useStudioStore } from '../../stores/studio.js'
import { useAiChatStore } from '../../stores/aiChat.js'
import TemplateCards from './TemplateCards.vue'
import DocumentPreview from './DocumentPreview.vue'

const studioStore = useStudioStore()
const chatStore = useAiChatStore()
const showPreview = ref(false)

function statusType(status) {
  const map = { draft: 'default', reviewed: 'info', pending: 'warning', approved: 'success', executed: 'success' }
  return map[status] || 'default'
}

async function handleTemplateSelect(tmpl) {
  // 通过 AI 对话触发生成
  await chatStore.sendMessage(`请帮我生成${tmpl.name}`)
  studioStore.loadDocuments()
}

async function openDoc(doc) {
  await studioStore.getDocument(doc.id)
  showPreview.value = true
}

onMounted(() => studioStore.loadDocuments())
</script>
```

- [ ] **Step 5: 端到端验证（P2 完成标志）**

Run: 启动后端 + 前端 + llm-proxy
1. 以 zhanglaoshi 登录
2. 右栏看到模板卡片（班级报告、学生评语）
3. 点击"班级学情分析报告" → AI 对话触发生成 → 右栏出现草稿
4. 点击草稿 → 弹窗预览 → 编辑段落 → 保存 → 确认审阅

Expected: **P2 完成标志达成**（PDF 导出用简化方案：浏览器打印）

- [ ] **Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat(P2-6): Studio 前端 — 模板卡片 + 文档列表 + 预览编辑 + 状态转换"
```

**审查清单:**
- ✓ 模板卡片按角色显示
- ✓ 点击模板触发 AI 对话生成
- ✓ 文档列表显示状态标签和版本号
- ✓ 预览弹窗支持逐段编辑
- ✓ 保存/确认审阅按钮功能正常
- ✗ 不应在前端硬编码模板内容（从 API 获取）

**边界条件:**
- 无模板可用（parent 角色）→ 期望: 空卡片区
- 无文档 → 期望: "暂无文档"空状态
- AI 未生成文档时点击模板 → 期望: 通过对话触发

**测试契约:**
1. Studio 前端交互
   - 入口: 点击模板卡片 → AI 对话 → 右栏刷新
   - 反例: 错误实现可能不刷新文档列表
   - 边界: 模板为空 / AI 超时 / 网络断开
   - 回归: N/A
   - 命令: 手动验证
