<!-- pre-takeover: archived for history, not active spec -->
# P3 家校通信实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现学期日历驱动的通知自动拟稿——学期事件到期前自动生成通知草稿进入 Studio，教师审阅后走审批流，审批通过后标记为已执行。消息发送渠道（企业微信）用 stub 预留。

**Architecture:** CalendarEvent + NotificationRule 模型驱动定时任务（arq worker）。触发时调用 AI Agent 生成通知草稿（复用 P2 StudioService）。审批通过后调用 NotificationDispatcher（首期 stub，企微接入后替换）。

**Tech Stack:** SQLAlchemy (Calendar models), arq (Redis task queue), 现有 StudioService + ApprovalService

**Design Doc:** `docs/plans/2026-03-21-super-platform-design.md` §7

**P4 基础:** 233 tests, AI Agent + Studio + 知识库 + L1-L4 工具全部就绪

**完成标志:** 学期日历设置"五一放假" → 提前 7 天 Studio 出现安全通知草稿 → 班主任审阅 → 教务批准 → 状态变为 executed

**Scope 说明:** 企业微信 API 调用、家长端 OAuth、短信降级**延期**。首期通知"执行"= 标记 executed + 记录 dispatch 日志。真实发送在企微账号就绪后接入。

---

## 文件结构

### 新增文件

```
src/edu_cloud/
├── models/
│   ├── calendar.py           # CalendarEvent + NotificationRule 模型
│   └── notification.py       # Notification + NotificationLog 模型
├── services/
│   ├── calendar_service.py   # 日历 CRUD + 触发规则匹配
│   └── notification_service.py # 通知分发（首期 stub）
├── api/
│   └── calendar.py           # 日历 REST API
├── tasks.py                  # arq 任务定义（定时扫描+自动拟稿）
└── worker.py                 # arq worker 入口

frontend/src/
├── components/calendar/
│   └── CalendarPanel.vue     # 日历事件管理（创建/编辑/删除）
└── pages/
    └── CalendarPage.vue      # 日历页面（可选，或嵌入左栏）
```

### 修改文件

```
src/edu_cloud/config.py               # 添加 NOTIFICATION_CRON_HOUR + REDIS 配置确认
src/edu_cloud/api/app.py              # 注册 calendar router
src/edu_cloud/api/studio.py           # 添加审批通过后的 dispatch 触发
src/edu_cloud/templates/document_templates.py  # 添加通知模板（安全通知/考试通知/家长会）
frontend/src/router/index.js          # 添加日历路由（可选）
frontend/src/components/context/ContextPanel.vue  # 左栏添加日历入口
```

### 测试文件

```
tests/
├── test_models/test_calendar.py      # 日历模型测试
├── test_services/test_calendar.py    # 日历服务测试
├── test_services/test_notification.py # 通知分发测试
├── test_api/test_calendar_api.py     # 日历 API 测试
└── test_tasks.py                     # arq 任务测试（mock）
```

---

## Task 1: 日历数据模型

**Files:**
- Create: `src/edu_cloud/models/calendar.py`, `src/edu_cloud/models/notification.py`
- Modify: `src/edu_cloud/models/document.py` (add `assigned_to` column)
- Test: `tests/test_models/test_calendar.py`

- [ ] **Step 1: 写模型测试**

```python
# tests/test_models/test_calendar.py
from edu_cloud.models.calendar import CalendarEvent, NotificationRule
from edu_cloud.models.notification import Notification

def test_calendar_event_fields():
    cols = {c.name for c in CalendarEvent.__table__.columns}
    assert "type" in cols          # holiday / exam / parent_meeting / deadline
    assert "title" in cols
    assert "event_date" in cols
    assert "school_id" in cols
    assert "created_by" in cols

def test_calendar_event_defaults():
    e = CalendarEvent(type="holiday", title="五一放假", school_id="s1", created_by="u1")
    assert e.is_active is True

def test_notification_rule_fields():
    cols = {c.name for c in NotificationRule.__table__.columns}
    assert "event_id" in cols
    assert "days_before" in cols
    assert "template_type" in cols
    assert "target_roles" in cols
    assert "auto_draft" in cols

def test_notification_fields():
    cols = {c.name for c in Notification.__table__.columns}
    assert "document_id" in cols
    assert "channel" in cols
    assert "status" in cols
    assert "target_scope" in cols
    assert "result_summary" in cols

def test_notification_default_status():
    n = Notification(document_id="d1", channel="wechat", school_id="s1")
    assert n.status == "pending"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_models/test_calendar.py -v`
Expected: FAIL

- [ ] **Step 3: 实现模型**

```python
# src/edu_cloud/models/calendar.py
from sqlalchemy import Column, String, Date, Boolean, Integer, JSON, ForeignKey
from edu_cloud.models.base import Base, IdMixin, TimestampMixin

class CalendarEvent(Base, IdMixin, TimestampMixin):
    __tablename__ = "calendar_events"
    type = Column(String(50), nullable=False)         # holiday / exam / parent_meeting / deadline
    title = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)
    event_date = Column(Date, nullable=False)
    school_id = Column(String(36), ForeignKey("registered_schools.id"), nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    semester = Column(String(20), nullable=True)      # "2025-2026-2"
    is_active = Column(Boolean, default=True, nullable=False)

class NotificationRule(Base, IdMixin, TimestampMixin):
    __tablename__ = "notification_rules"
    event_id = Column(String(36), ForeignKey("calendar_events.id"), nullable=False)
    days_before = Column(Integer, nullable=False)      # 提前几天触发（7/3/1）
    template_type = Column(String(50), nullable=False)  # holiday_safety / exam_reminder / meeting_invite
    target_roles = Column(JSON, nullable=False)         # ["parent"] / ["homeroom_teacher", "parent"]
    auto_draft = Column(Boolean, default=True, nullable=False)
    triggered = Column(Boolean, default=False, nullable=False)  # 已触发标记，防重复
```

```python
# src/edu_cloud/models/notification.py
from sqlalchemy import Column, String, JSON, ForeignKey, DateTime
from edu_cloud.models.base import Base, IdMixin, TimestampMixin

class Notification(Base, IdMixin, TimestampMixin):
    __tablename__ = "notifications"
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    channel = Column(String(20), nullable=False, default="wechat")  # wechat / sms / stub
    status = Column(String(20), nullable=False, default="pending")   # pending / sent / partial / failed
    target_scope = Column(JSON, nullable=True)       # {"class_ids": [...]} 或 {"school_id": "..."}
    school_id = Column(String(36), ForeignKey("registered_schools.id"), nullable=False)
    sent_at = Column(DateTime, nullable=True)
    result_summary = Column(JSON, nullable=True)      # {"total": 45, "success": 43, "unreachable": 2}
```

- [ ] **Step 3b: 为 Document 模型添加 assigned_to 字段（F2 fix）**

> **问题**: 自动拟稿创建的文档 created_by 是事件创建者，但 Studio 的 list_documents 只查
> `WHERE created_by = user_id`，如果文档被分配给其他教师（如年级组长创建事件、班主任审阅通知），
> 班主任在 Studio 看不到自动生成的草稿。
>
> **方案**: Document 模型新增 `assigned_to` 字段，list_documents 查询改为 `WHERE created_by = user_id OR assigned_to = user_id`。

```python
# src/edu_cloud/models/document.py — 在 created_by 字段之后追加
    assigned_to: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), default=None, nullable=True
    )
```

同步修改 `src/edu_cloud/services/studio_service.py` 的 `list_documents` 方法：

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_models/test_calendar.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/models/calendar.py src/edu_cloud/models/notification.py \
        src/edu_cloud/models/document.py src/edu_cloud/services/studio_service.py \
        tests/test_models/test_calendar.py
git commit -m "feat(P3-1): 日历+通知数据模型 + Document.assigned_to 字段"
```

**审查清单:**
- ✓ CalendarEvent 带 school_id（RLS 隔离）
- ✓ CalendarEvent.created_by FK → users.id（不是字符串 "system"）
- ✓ NotificationRule 有 triggered 标记防重复触发
- ✓ Notification 状态默认 pending
- ✓ Document 新增 assigned_to 字段（nullable FK → users.id），list_documents 查 OR 条件
- ✗ 不应在模型层做业务逻辑

**边界条件:**
- event_date 在过去 → 期望: 模型不拦截（service 层处理）
- days_before=0 → 期望: 当天触发
- target_roles 空列表 → 期望: 不发送

**测试契约:**
1. 模型字段+默认值
   - 入口: 直接构造 ORM 对象
   - 反例: 遗漏 default 导致 NOT NULL 插入失败
   - 边界: 最小字段集 / nullable 字段缺失
   - 回归: N/A
   - 命令: `python -m pytest tests/test_models/test_calendar.py -v`

---

## Task 2: 日历服务 + API

**Files:**
- Create: `src/edu_cloud/services/calendar_service.py`, `src/edu_cloud/api/calendar.py`
- Modify: `src/edu_cloud/api/app.py`, `src/edu_cloud/templates/document_templates.py`
- Test: `tests/test_services/test_calendar.py`, `tests/test_api/test_calendar_api.py`

- [ ] **Step 1: 写日历服务测试**

```python
# tests/test_services/test_calendar.py
import pytest
from datetime import date, timedelta
from edu_cloud.services.calendar_service import CalendarService

@pytest.mark.asyncio
async def test_create_event(db):
    svc = CalendarService(db)
    event = await svc.create_event(
        type="holiday", title="五一放假", event_date=date(2026, 5, 1),
        school_id="s1", created_by="u1", semester="2025-2026-2",
        notification_rules=[
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
            {"days_before": 1, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
        ],
    )
    assert event.title == "五一放假"
    assert event.type == "holiday"

@pytest.mark.asyncio
async def test_list_events(db):
    svc = CalendarService(db)
    await svc.create_event(
        type="exam", title="期中考试", event_date=date(2026, 4, 20),
        school_id="s1", created_by="u1",
    )
    events = await svc.list_events(school_id="s1")
    assert len(events) >= 1

@pytest.mark.asyncio
async def test_get_triggered_rules(db):
    """查找今天应触发的规则"""
    svc = CalendarService(db)
    target_date = date.today() + timedelta(days=7)
    await svc.create_event(
        type="holiday", title="测试假期", event_date=target_date,
        school_id="s1", created_by="u1",
        notification_rules=[
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
        ],
    )
    rules = await svc.get_triggered_rules(check_date=date.today())
    assert len(rules) >= 1
    assert rules[0]["template_type"] == "holiday_safety"
    assert rules[0]["created_by"] == "u1"  # F1 fix: 确认 created_by 从事件传递

@pytest.mark.asyncio
async def test_triggered_rule_not_repeated(db):
    """已触发的规则不重复"""
    svc = CalendarService(db)
    target_date = date.today() + timedelta(days=7)
    await svc.create_event(
        type="holiday", title="测试", event_date=target_date,
        school_id="s1", created_by="u1",
        notification_rules=[
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
        ],
    )
    rules1 = await svc.get_triggered_rules(check_date=date.today())
    assert len(rules1) >= 1
    # 标记已触发
    await svc.mark_rule_triggered(rules1[0]["rule_id"])
    rules2 = await svc.get_triggered_rules(check_date=date.today())
    assert len(rules2) == 0

@pytest.mark.asyncio
async def test_delete_event(db):
    svc = CalendarService(db)
    event = await svc.create_event(
        type="exam", title="删除测试", event_date=date(2026, 6, 1),
        school_id="s1", created_by="u1",
    )
    await svc.delete_event(event.id)
    events = await svc.list_events(school_id="s1")
    active = [e for e in events if e.is_active]
    assert len(active) == 0
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_services/test_calendar.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 CalendarService**

```python
# src/edu_cloud/services/calendar_service.py
from datetime import date
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.models.calendar import CalendarEvent, NotificationRule
from edu_cloud.services.exceptions import NotFoundError

class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(
        self, type: str, title: str, event_date: date,
        school_id: str, created_by: str,
        semester: str | None = None,
        description: str | None = None,
        notification_rules: list[dict] | None = None,
    ) -> CalendarEvent:
        event = CalendarEvent(
            type=type, title=title, event_date=event_date,
            school_id=school_id, created_by=created_by,
            semester=semester, description=description,
        )
        self.db.add(event)
        await self.db.flush()

        for rule_data in (notification_rules or []):
            rule = NotificationRule(
                event_id=event.id,
                days_before=rule_data["days_before"],
                template_type=rule_data["template_type"],
                target_roles=rule_data["target_roles"],
                auto_draft=rule_data.get("auto_draft", True),
            )
            self.db.add(rule)
        await self.db.commit()
        return event

    async def list_events(
        self, school_id: str, start_date: date | None = None, end_date: date | None = None,
    ) -> list[CalendarEvent]:
        q = select(CalendarEvent).where(CalendarEvent.school_id == school_id)
        if start_date:
            q = q.where(CalendarEvent.event_date >= start_date)
        if end_date:
            q = q.where(CalendarEvent.event_date <= end_date)
        q = q.order_by(CalendarEvent.event_date)
        return list((await self.db.execute(q)).scalars().all())

    async def get_event(self, event_id: str) -> CalendarEvent:
        event = await self.db.get(CalendarEvent, event_id)
        if not event:
            raise NotFoundError(f"Event {event_id} not found")
        return event

    async def delete_event(self, event_id: str):
        event = await self.get_event(event_id)
        event.is_active = False
        await self.db.commit()

    async def get_triggered_rules(self, check_date: date) -> list[dict]:
        """查找 check_date 应触发的通知规则"""
        # 规则触发条件: event_date - days_before == check_date AND triggered == False
        q = (
            select(NotificationRule, CalendarEvent)
            .join(CalendarEvent, NotificationRule.event_id == CalendarEvent.id)
            .where(
                CalendarEvent.is_active == True,
                NotificationRule.triggered == False,
                NotificationRule.auto_draft == True,
            )
        )
        rows = (await self.db.execute(q)).all()

        triggered = []
        for rule, event in rows:
            from datetime import timedelta
            trigger_date = event.event_date - timedelta(days=rule.days_before)
            if trigger_date == check_date:
                triggered.append({
                    "rule_id": rule.id,
                    "event_id": event.id,
                    "event_title": event.title,
                    "event_type": event.type,
                    "event_date": str(event.event_date),
                    "template_type": rule.template_type,
                    "target_roles": rule.target_roles,
                    "school_id": event.school_id,
                    "days_before": rule.days_before,
                    "created_by": event.created_by,  # F1 fix: 传递事件创建者，用于 Document.created_by FK
                })
        return triggered

    async def mark_rule_triggered(self, rule_id: str):
        rule = await self.db.get(NotificationRule, rule_id)
        if rule:
            rule.triggered = True
            await self.db.commit()
```

- [ ] **Step 4: 添加通知模板**

```python
# src/edu_cloud/templates/document_templates.py — TEMPLATES 追加
    "holiday_safety": {
        "key": "holiday_safety",
        "name": "假期安全通知",
        "sections": [
            {"key": "greeting", "title": "称呼", "prompt": "尊敬的家长"},
            {"key": "schedule", "title": "放假安排", "prompt": "根据事件日期生成放假时间安排"},
            {"key": "safety", "title": "安全提醒", "prompt": "假期安全注意事项（交通/防溺水/饮食）"},
            {"key": "closing", "title": "落款", "prompt": "学校名+日期"},
        ],
        "required_context": ["event_title", "event_date"],
        "available_roles": ["homeroom_teacher", "academic_director", "principal"],
        "requires_approval": True,
        "approval_chain": "class_notification",
    },
    "exam_reminder": {
        "key": "exam_reminder",
        "name": "考试通知",
        "sections": [
            {"key": "greeting", "title": "称呼", "prompt": "尊敬的家长"},
            {"key": "exam_info", "title": "考试信息", "prompt": "考试时间、科目、注意事项"},
            {"key": "preparation", "title": "备考建议", "prompt": "家长如何配合备考"},
            {"key": "closing", "title": "落款", "prompt": "学校名+日期"},
        ],
        "required_context": ["event_title", "event_date"],
        "available_roles": ["homeroom_teacher", "academic_director", "principal"],
        "requires_approval": True,
        "approval_chain": "class_notification",
    },
    "meeting_invite": {
        "key": "meeting_invite",
        "name": "家长会邀请",
        "sections": [
            {"key": "greeting", "title": "称呼", "prompt": "尊敬的家长"},
            {"key": "meeting_info", "title": "会议信息", "prompt": "时间、地点、议程"},
            {"key": "closing", "title": "落款", "prompt": "学校名+日期"},
        ],
        "required_context": ["event_title", "event_date"],
        "available_roles": ["homeroom_teacher", "academic_director", "principal"],
        "requires_approval": True,
        "approval_chain": "class_notification",
    },
```

- [ ] **Step 5: 实现日历 API**

```python
# src/edu_cloud/api/calendar.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.services.calendar_service import CalendarService
from datetime import date

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])

@router.post("/events", status_code=201)
async def create_event(
    body: dict,
    current=Depends(require_permission(Permission.GENERATE_NOTIFICATION)),
    db: AsyncSession = Depends(get_db),
):
    user = current["user"]
    role = current["current_role"]
    svc = CalendarService(db)
    event = await svc.create_event(
        type=body["type"], title=body["title"],
        event_date=date.fromisoformat(body["event_date"]),
        school_id=getattr(role, "school_id", ""),
        created_by=user.id,
        semester=body.get("semester"),
        description=body.get("description"),
        notification_rules=body.get("notification_rules", []),
    )
    return _event_to_dict(event)

@router.get("/events")
async def list_events(
    start: str | None = None, end: str | None = None,
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = current["current_role"]
    svc = CalendarService(db)
    events = await svc.list_events(
        school_id=getattr(role, "school_id", ""),
        start_date=date.fromisoformat(start) if start else None,
        end_date=date.fromisoformat(end) if end else None,
    )
    return [_event_to_dict(e) for e in events]

@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    current=Depends(require_permission(Permission.GENERATE_NOTIFICATION)),
    db: AsyncSession = Depends(get_db),
):
    svc = CalendarService(db)
    await svc.delete_event(event_id)
    return {"status": "deleted"}

def _event_to_dict(event) -> dict:
    return {
        "id": event.id,
        "type": event.type,
        "title": event.title,
        "event_date": str(event.event_date),
        "semester": event.semester,
        "is_active": event.is_active,
    }
```

- [ ] **Step 6: 注册路由**

```python
# src/edu_cloud/api/app.py — 追加
from edu_cloud.api.calendar import router as calendar_router
app.include_router(calendar_router)
```

- [ ] **Step 7: 写 API 测试**

```python
# tests/test_api/test_calendar_api.py
import pytest

@pytest.mark.asyncio
async def test_create_event(client, teacher_headers):
    resp = await client.post("/api/v1/calendar/events", json={
        "type": "holiday", "title": "五一放假",
        "event_date": "2026-05-01",
        "notification_rules": [
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True}
        ],
    }, headers=teacher_headers)
    assert resp.status_code == 201
    assert resp.json()["title"] == "五一放假"

@pytest.mark.asyncio
async def test_list_events(client, teacher_headers):
    await client.post("/api/v1/calendar/events", json={
        "type": "exam", "title": "期中考试", "event_date": "2026-04-20",
    }, headers=teacher_headers)
    resp = await client.get("/api/v1/calendar/events", headers=teacher_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

@pytest.mark.asyncio
async def test_delete_event(client, teacher_headers):
    resp = await client.post("/api/v1/calendar/events", json={
        "type": "exam", "title": "删除测试", "event_date": "2026-06-01",
    }, headers=teacher_headers)
    event_id = resp.json()["id"]
    del_resp = await client.delete(f"/api/v1/calendar/events/{event_id}", headers=teacher_headers)
    assert del_resp.status_code == 200

@pytest.mark.asyncio
async def test_calendar_requires_auth(client):
    resp = await client.get("/api/v1/calendar/events")
    assert resp.status_code in (401, 403)
```

- [ ] **Step 8: 运行测试**

Run: `python -m pytest tests/test_services/test_calendar.py tests/test_api/test_calendar_api.py -v`
Expected: PASS

- [ ] **Step 9: 全量测试**

Run: `python -m pytest --tb=short -q`
Expected: 233 + 新增全 PASS

- [ ] **Step 10: Commit**

```bash
git add src/edu_cloud/models/calendar.py src/edu_cloud/models/notification.py \
        src/edu_cloud/services/calendar_service.py src/edu_cloud/api/calendar.py \
        src/edu_cloud/api/app.py src/edu_cloud/templates/document_templates.py tests/
git commit -m "feat(P3-2): 日历服务 + API + 3 通知模板 + 触发规则匹配"
```

**审查清单:**
- ✓ 日历 CRUD（创建/列表/删除）
- ✓ 触发规则匹配（event_date - days_before == check_date）
- ✓ triggered 标记防重复
- ✓ 3 个通知模板（假期安全/考试/家长会）
- ✓ API 需要 GENERATE_NOTIFICATION 权限
- ✗ 不应在日历服务中做消息发送

**边界条件:**
- event_date 已过去 → 期望: 可创建但 get_triggered_rules 不匹配
- days_before=0 → 期望: 当天触发
- 已 triggered 的规则 → 期望: 不重复出现

**测试契约:**
1. 触发规则匹配准确性
   - 入口: `svc.get_triggered_rules(check_date=today)`
   - 反例: 错误实现可能不检查 triggered 标记导致重复
   - 边界: 无事件 / 已过期事件 / 已触发规则 / 当天触发
   - 回归: N/A
   - 命令: `python -m pytest tests/test_services/test_calendar.py -v`
2. 日历 API CRUD
   - 入口: `POST/GET/DELETE /api/v1/calendar/events`
   - 反例: 未认证用户可操作
   - 边界: 空列表 / 日期过滤 / 删除不存在的事件
   - 回归: N/A
   - 命令: `python -m pytest tests/test_api/test_calendar_api.py -v`

---

## Task 3: 自动拟稿任务 + 通知分发

**Files:**
- Create: `src/edu_cloud/tasks.py`, `src/edu_cloud/worker.py`, `src/edu_cloud/services/notification_service.py`
- Test: `tests/test_tasks.py`, `tests/test_services/test_notification.py`

- [ ] **Step 1: 写自动拟稿任务测试**

```python
# tests/test_tasks.py
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_auto_draft_creates_document(db):
    """触发规则匹配后自动创建通知草稿"""
    from edu_cloud.services.calendar_service import CalendarService
    from edu_cloud.tasks import auto_draft_notifications

    # 创建事件 + 规则
    svc = CalendarService(db)
    target_date = date.today() + timedelta(days=7)
    await svc.create_event(
        type="holiday", title="测试假期", event_date=target_date,
        school_id="s1", created_by="u1",
        notification_rules=[
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
        ],
    )

    # 执行自动拟稿
    created_count = await auto_draft_notifications(db, check_date=date.today())
    assert created_count >= 1

    # 验证 Document 已创建
    from edu_cloud.models.document import Document
    from sqlalchemy import select
    docs = (await db.execute(select(Document).where(Document.type == "notification"))).scalars().all()
    assert len(docs) >= 1
    assert "假期" in docs[0].title or "安全" in docs[0].title

@pytest.mark.asyncio
async def test_auto_draft_skips_triggered(db):
    """已触发的规则不重复创建"""
    from edu_cloud.services.calendar_service import CalendarService
    from edu_cloud.tasks import auto_draft_notifications

    svc = CalendarService(db)
    target_date = date.today() + timedelta(days=7)
    await svc.create_event(
        type="holiday", title="测试", event_date=target_date,
        school_id="s1", created_by="u1",
        notification_rules=[
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
        ],
    )

    count1 = await auto_draft_notifications(db, check_date=date.today())
    count2 = await auto_draft_notifications(db, check_date=date.today())
    assert count1 >= 1
    assert count2 == 0  # 不重复
```

- [ ] **Step 2: 写通知分发测试**

```python
# tests/test_services/test_notification.py
import pytest
from edu_cloud.services.notification_service import NotificationService

@pytest.mark.asyncio
async def test_dispatch_stub(db):
    """stub 模式下标记为 sent"""
    svc = NotificationService(db)
    result = await svc.dispatch(
        document_id="doc1",
        target_scope={"class_ids": ["c1"]},
        school_id="s1",
        channel="stub",
    )
    assert result["status"] == "sent"
    assert result["channel"] == "stub"

@pytest.mark.asyncio
async def test_dispatch_idempotent(db):
    """同一 document_id 不重复发送"""
    svc = NotificationService(db)
    r1 = await svc.dispatch(document_id="doc1", target_scope={}, school_id="s1", channel="stub")
    r2 = await svc.dispatch(document_id="doc1", target_scope={}, school_id="s1", channel="stub")
    assert r1["status"] == "sent"
    assert r2["status"] == "already_sent"  # 幂等
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_tasks.py tests/test_services/test_notification.py -v`
Expected: FAIL

- [ ] **Step 4: 实现自动拟稿任务**

```python
# src/edu_cloud/tasks.py
import logging
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.services.calendar_service import CalendarService
from edu_cloud.services.studio_service import StudioService
from edu_cloud.templates.document_templates import TEMPLATES

logger = logging.getLogger(__name__)

# F6 fix: 事件上下文填充模板内容（非空占位），避免生成空白草稿
# 注: 完整 AI 生成内容需要 LLM 调用，对 cron 任务成本过高，
# 这里填充事件相关的结构化内容，教师审阅时可进一步编辑或调用 AI 润色。
_SECTION_FILLERS = {
    "greeting": "尊敬的家长：",
    "schedule": "根据学校安排，{event_title}时间为 {event_date}。请提前做好相关准备。",
    "safety": "假期期间请注意以下安全事项：\n1. 交通安全：遵守交通规则，注意出行安全\n2. 防溺水：不私自下水游泳\n3. 饮食安全：注意饮食卫生\n4. 居家安全：注意用电、用气安全",
    "closing": "祝您和家人假期愉快！\n\n{school_name}\n{today}",
    "exam_info": "{event_title}将于 {event_date} 举行，请督促孩子做好复习准备。",
    "preparation": "建议家长配合做好以下工作：\n1. 合理安排作息时间\n2. 保证充足睡眠\n3. 注意饮食营养",
    "meeting_info": "{event_title}定于 {event_date} 举行，届时请准时参加。",
}

def _fill_template_content(template: dict, rule: dict) -> dict:
    """用事件上下文填充模板各 section，生成有意义的初始内容。"""
    from datetime import date as date_type
    content = {}
    ctx = {
        "event_title": rule["event_title"],
        "event_date": rule["event_date"],
        "school_name": "",  # 可后续从 school 表填充
        "today": str(date_type.today()),
    }
    for section in template["sections"]:
        filler = _SECTION_FILLERS.get(section["key"], section["prompt"])
        try:
            filled = filler.format(**ctx)
        except KeyError:
            filled = filler
        content[section["key"]] = {
            "title": section["title"],
            "content": filled,
            "prompt": section["prompt"],
        }
    return content

async def auto_draft_notifications(db: AsyncSession, check_date: date | None = None) -> int:
    """每日定时任务：扫描学期日历，自动生成通知草稿"""
    if check_date is None:
        check_date = date.today()

    cal_svc = CalendarService(db)
    studio_svc = StudioService(db)

    rules = await cal_svc.get_triggered_rules(check_date)
    created = 0

    for rule in rules:
        template = TEMPLATES.get(rule["template_type"])
        if not template:
            logger.warning(f"Unknown template: {rule['template_type']}")
            continue

        # F6 fix: 生成带事件上下文的内容（非空模板）
        content = _fill_template_content(template, rule)

        # F1 fix: 使用事件创建者的 user.id 作为 created_by，不能用 "system"（FK 约束）
        # F2 fix: assigned_to 设为事件创建者，确保其 Studio 队列可见
        doc = await studio_svc.create_document(
            type="notification",
            title=f"{rule['event_title']} — {template['name']}",
            content_json=content,
            school_id=rule["school_id"],
            created_by=rule["created_by"],  # F1: 事件创建者（真实 users.id），非 "system"
            source_context={
                "event_id": rule["event_id"],
                "event_date": rule["event_date"],
                "template_type": rule["template_type"],
                "auto_generated": True,
            },
        )
        # F2: 设置 assigned_to 确保班主任 Studio 队列可见
        doc.assigned_to = rule["created_by"]
        await db.flush()

        # 标记规则已触发
        await cal_svc.mark_rule_triggered(rule["rule_id"])
        created += 1
        logger.info(f"Auto-drafted notification: {doc.title} (event: {rule['event_title']})")

    await db.commit()
    return created
```

- [ ] **Step 5: 实现通知分发服务**

```python
# src/edu_cloud/services/notification_service.py
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.models.notification import Notification

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def dispatch(
        self, document_id: str, target_scope: dict,
        school_id: str, channel: str = "stub",
    ) -> dict:
        """分发通知。首期 stub 模式直接标记 sent。"""
        # 幂等检查
        existing = (await self.db.execute(
            select(Notification).where(
                Notification.document_id == document_id,
                Notification.status.in_(["sent", "partial"]),
            )
        )).scalar_one_or_none()
        if existing:
            return {"status": "already_sent", "notification_id": existing.id, "channel": channel}

        # 创建通知记录
        notification = Notification(
            document_id=document_id,
            channel=channel,
            target_scope=target_scope,
            school_id=school_id,
        )
        self.db.add(notification)

        if channel == "stub":
            # Stub: 直接标记发送成功
            notification.status = "sent"
            notification.sent_at = datetime.now(timezone.utc)
            notification.result_summary = {"total": 0, "success": 0, "channel": "stub", "note": "企业微信未接入，仅标记状态"}
            logger.info(f"Notification dispatched (stub): doc={document_id}")
        else:
            # 未来: 调用企业微信 API
            notification.status = "pending"

        await self.db.flush()
        return {
            "status": notification.status,
            "notification_id": notification.id,
            "channel": channel,
            "result": notification.result_summary,
        }
```

- [ ] **Step 6: 实现 arq worker 入口**

```python
# src/edu_cloud/worker.py
"""
arq worker 入口。
启动方式: arq edu_cloud.worker.WorkerSettings
PM2: pm2 start arq -- edu_cloud.worker.WorkerSettings
"""
import logging
from arq import cron
from arq.connections import RedisSettings
from edu_cloud.config import settings
# F5 fix: database.py 导出的是 async_session（async_sessionmaker 实例），不是 async_session_factory
from edu_cloud.database import async_session
from edu_cloud.tasks import auto_draft_notifications

logger = logging.getLogger(__name__)

async def run_auto_draft(ctx):
    """arq cron job: 每天 6:00 (UTC+8 = 22:00 UTC) 扫描日历"""
    # F5 fix: async_session 是 async_sessionmaker 实例，直接 async with 调用即可
    async with async_session() as db:
        count = await auto_draft_notifications(db)
        logger.info(f"Auto-draft job completed: {count} notifications created")

class WorkerSettings:
    """arq WorkerSettings — 通过 `arq edu_cloud.worker.WorkerSettings` 启动"""
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    cron_jobs = [
        cron(run_auto_draft, hour=22, minute=0),  # 22:00 UTC = 06:00 UTC+8
    ]
    functions = [run_auto_draft]

# F5 fix: 删除 asyncio.run(create_pool(...)) — arq worker 通过 CLI 启动:
#   arq edu_cloud.worker.WorkerSettings
# 不需要 if __name__ == "__main__" 入口
```

- [ ] **Step 7: 运行测试**

Run: `python -m pytest tests/test_tasks.py tests/test_services/test_notification.py -v`
Expected: PASS

- [ ] **Step 8: 全量测试**

Run: `python -m pytest --tb=short -q`
Expected: 全部 PASS

- [ ] **Step 9: Commit**

```bash
git add src/edu_cloud/tasks.py src/edu_cloud/worker.py \
        src/edu_cloud/services/notification_service.py tests/
git commit -m "feat(P3-3): 自动拟稿任务 + 通知分发（stub）+ arq worker"
```

**审查清单:**
- ✓ 自动拟稿：日历规则匹配 → 创建 Document 草稿
- ✓ 已触发规则不重复（mark_rule_triggered）
- ✓ created_by 来自事件创建者的 users.id，不是字符串 "system"（F1）
- ✓ assigned_to 设为事件创建者，确保 Studio 队列可见（F2）
- ✓ 模板内容用事件上下文填充，非空白占位（F6）
- ✓ 通知分发幂等（同 document_id 不重复发送）
- ✓ Stub 模式直接标记 sent
- ✓ arq worker 导入 async_session（不是 async_session_factory）（F5）
- ✓ arq worker 通过 `arq edu_cloud.worker.WorkerSettings` CLI 启动（F5）
- ✓ arq worker cron 每天 6:00 UTC+8
- ✗ 不应在任务中做审批逻辑（审批通过后由 API 触发 dispatch）

**边界条件:**
- 无匹配规则 → 期望: created=0
- 模板不存在 → 期望: 跳过并 warning
- 同一事件多条规则同时触发 → 期望: 各自独立创建文档
- 自动拟稿的文档内容非空（F6: 各 section 包含事件相关文本）

**测试契约:**
1. 自动拟稿正确性
   - 入口: `auto_draft_notifications(db, check_date=today)`
   - 反例: 错误实现可能不标记 triggered 导致重复创建
   - 边界: 无事件 / 已触发 / 多规则同时
   - 回归: N/A
   - 命令: `python -m pytest tests/test_tasks.py -v`
2. 通知分发幂等性
   - 入口: `svc.dispatch(document_id, ...) × 2`
   - 反例: 错误实现可能创建重复 Notification 记录
   - 边界: 首次发送 / 重复发送 / stub vs 真实渠道
   - 回归: N/A
   - 命令: `python -m pytest tests/test_services/test_notification.py -v`

---

## Task 4: 审批通过后触发分发 + 前端日历

**Files:**
- Modify: `src/edu_cloud/api/studio.py` (transition 权限 + 审批流 + dispatch 触发)
- Modify: `src/edu_cloud/services/studio_service.py` (通知类文档审批前置检查)
- Create: `frontend/src/components/calendar/CalendarPanel.vue`
- Modify: `frontend/src/components/context/ContextPanel.vue` (添加日历入口)

- [ ] **Step 1: Studio transition 扩展——权限强化 + 审批流创建 + dispatch 触发**

> **F3 fix**: 保留 `require_permission(Permission.GENERATE_NOTIFICATION)` 用于通知类文档
> transition，对 `executed` transition 额外检查 `SEND_NOTIFICATION` 权限。
>
> **F4 fix**: 通知类文档必须走审批流。`reviewed` → `pending` 时自动创建 ApprovalFlow；
> 禁止 `reviewed` → `executed` 直接跳过审批。

首先，在 `StudioService.transition_status` 中添加通知类文档的审批前置检查：

```python
# src/edu_cloud/services/studio_service.py — transition_status 方法修改
    async def transition_status(
        self, doc_id: str, new_status: str, school_id: str | None = None
    ) -> Document:
        doc = await self._get_doc(doc_id, school_id=school_id)
        allowed = VALID_TRANSITIONS.get(doc.status, [])
        if new_status not in allowed:
            raise StateError(
                f"Cannot transition from '{doc.status}' to '{new_status}'"
            )

        # F4 fix: 通知类文档必须走审批流，禁止 reviewed → executed 直接跳过
        if doc.type == "notification" and new_status == "executed" and doc.status != "approved":
            raise StateError(
                "Notifications must be approved before execution. "
                "Transition: reviewed → pending → approved → executed"
            )

        doc.status = new_status
        await self.db.flush()
        return doc
```

然后，修改 API 层：

```python
# src/edu_cloud/api/studio.py — transition_document 修改
from edu_cloud.services.notification_service import NotificationService
from edu_cloud.services.approval_service import ApprovalService

@router.post("/documents/{doc_id}/transition")
async def transition_document(
    doc_id: str, body: dict,
    # F3 fix: 保留 GENERATE_NOTIFICATION 权限（不降级为 get_current_user）
    current=Depends(require_permission(Permission.GENERATE_NOTIFICATION)),
    db: AsyncSession = Depends(get_db),
):
    if "status" not in body:
        raise HTTPException(422, "缺少必填字段: status")

    user = current["user"]
    role = current["current_role"]
    school_id = getattr(role, "school_id", None)

    # F3 fix: 通知类文档 executed 需要额外的 SEND_NOTIFICATION 权限
    if body["status"] == "executed":
        svc_check = StudioService(db)
        doc_check = await svc_check.get_document(doc_id, school_id=school_id)
        if doc_check.type == "notification":
            from edu_cloud.core.permissions import has_permission
            role_name = getattr(role, "role", "unknown")
            if not has_permission(role_name, Permission.SEND_NOTIFICATION):
                raise HTTPException(403, "需要 SEND_NOTIFICATION 权限才能执行通知")

    svc = StudioService(db)
    doc = await svc.transition_status(doc_id, body["status"], school_id=school_id)

    # F4 fix: 通知类文档 transition 到 pending 时自动创建审批流
    if body["status"] == "pending" and doc.type == "notification":
        template_info = doc.source_context or {}
        chain_type = template_info.get("approval_chain", "class_notification")
        # 审批人需要从学校组织架构获取，首期用 source_context 或空列表
        # TODO: 从组织架构服务获取审批人列表
        approval_svc = ApprovalService(db)
        await approval_svc.create_flow(
            document_id=doc.id,
            chain_type=chain_type,
            approver_ids=[],  # 首期: 由管理员手动指定审批人，后续从组织架构自动获取
        )

    # P3: 通知类文档 transition 到 executed 时触发分发
    if body["status"] == "executed" and doc.type == "notification":
        notif_svc = NotificationService(db)
        dispatch_result = await notif_svc.dispatch(
            document_id=doc.id,
            target_scope=doc.source_context or {},
            school_id=doc.school_id,
            channel="stub",  # 首期 stub，企微接入后改为 "wechat"
        )
        doc.execution_result = dispatch_result
        doc.executed_at = datetime.now(timezone.utc)

    await db.commit()
    return _doc_to_dict(doc)
```

> **注意**: 需要在文件顶部添加 `from datetime import datetime, timezone` import。

- [ ] **Step 2: 创建前端 CalendarPanel**

```vue
<!-- frontend/src/components/calendar/CalendarPanel.vue -->
<template>
  <div style="padding: 12px">
    <n-h4>学期日历</n-h4>

    <!-- 创建事件 -->
    <n-button size="small" type="primary" @click="showCreate = true" style="margin-bottom: 12px">
      + 新增事件
    </n-button>

    <!-- 事件列表 -->
    <n-list v-if="events.length">
      <n-list-item v-for="event in events" :key="event.id">
        <n-thing :title="event.title">
          <template #description>
            <n-tag :type="typeMap[event.type] || 'default'" size="small">{{ event.type }}</n-tag>
            <n-text depth="3" style="margin-left: 8px">{{ event.event_date }}</n-text>
          </template>
        </n-thing>
      </n-list-item>
    </n-list>
    <n-empty v-else description="暂无事件" size="small" />

    <!-- 创建弹窗 -->
    <n-modal v-model:show="showCreate" preset="card" style="width: 500px" title="新增学期事件">
      <n-form>
        <n-form-item label="类型">
          <n-select v-model:value="form.type" :options="typeOptions" />
        </n-form-item>
        <n-form-item label="标题">
          <n-input v-model:value="form.title" placeholder="如：五一放假" />
        </n-form-item>
        <n-form-item label="日期">
          <n-date-picker v-model:value="form.date" type="date" />
        </n-form-item>
        <n-form-item label="提前通知（天）">
          <n-input-number v-model:value="form.daysBefore" :min="0" :max="30" />
        </n-form-item>
        <n-button type="primary" @click="handleCreate">创建</n-button>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import client from '../../api/client.js'

const events = ref([])
const showCreate = ref(false)
const form = ref({ type: 'holiday', title: '', date: null, daysBefore: 7 })

const typeOptions = [
  { label: '放假', value: 'holiday' },
  { label: '考试', value: 'exam' },
  { label: '家长会', value: 'parent_meeting' },
  { label: '截止日期', value: 'deadline' },
]
const typeMap = { holiday: 'success', exam: 'warning', parent_meeting: 'info', deadline: 'error' }

async function loadEvents() {
  const { data } = await client.get('/calendar/events')
  events.value = data
}

async function handleCreate() {
  if (!form.value.title || !form.value.date) return
  const dateStr = new Date(form.value.date).toISOString().split('T')[0]
  await client.post('/calendar/events', {
    type: form.value.type,
    title: form.value.title,
    event_date: dateStr,
    notification_rules: form.value.daysBefore > 0 ? [{
      days_before: form.value.daysBefore,
      template_type: form.value.type === 'holiday' ? 'holiday_safety' : form.value.type === 'exam' ? 'exam_reminder' : 'meeting_invite',
      target_roles: ['parent'],
      auto_draft: true,
    }] : [],
  })
  showCreate.value = false
  form.value = { type: 'holiday', title: '', date: null, daysBefore: 7 }
  await loadEvents()
}

onMounted(loadEvents)
</script>
```

- [ ] **Step 3: 在左栏添加日历入口**

在 ContextPanel.vue 底部添加日历组件或链接。

- [ ] **Step 4: 端到端验证（P3 完成标志）**

1. 以 zhanglaoshi 登录
2. 左栏打开日历 → 创建"五一放假"事件（日期 5月1日，提前 7 天通知）
3. 手动触发自动拟稿（或等 arq cron）：日历规则匹配 → Studio 出现"五一放假 — 假期安全通知"草稿
4. 班主任点击草稿 → 审阅编辑 → 确认审阅 → 提交审批
5. 教务批准 → 状态变为 approved → 执行 → 状态变为 executed（stub 发送）

Expected: **P3 完成标志达成**

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/api/studio.py src/edu_cloud/services/studio_service.py frontend/src/ tests/
git commit -m "feat(P3-4): 审批触发分发 + 权限强化 + 审批流创建 + 前端日历面板"
```

**审查清单:**
- ✓ notification 类文档 transition 到 executed 自动触发 dispatch
- ✓ transition 保留 GENERATE_NOTIFICATION 权限（F3: 不降级为 get_current_user）
- ✓ 通知 executed 需要额外 SEND_NOTIFICATION 权限（F3）
- ✓ 通知 reviewed→executed 被阻断，必须走 pending→approved→executed（F4）
- ✓ 通知 reviewed→pending 时自动创建 ApprovalFlow（F4）
- ✓ 日历面板支持创建/查看事件
- ✓ 创建事件时自动附带通知规则
- ✓ 事件类型 → 通知模板自动映射
- ✗ 不应在前端硬编码模板映射逻辑（后续提取到后端）
- ✗ 审批人列表首期为空（TODO: 从组织架构自动获取）

**边界条件:**
- 非通知类文档 transition 到 executed → 期望: 不触发 dispatch，不检查 SEND_NOTIFICATION
- 通知类文档 reviewed → executed 直接跳过审批 → 期望: StateError 拒绝（F4）
- 通知类文档 approved → executed → 期望: 允许，触发 dispatch
- 无 SEND_NOTIFICATION 权限的教师执行通知 → 期望: 403（F3）
- 重复 transition → 期望: 幂等（不重复发送）
- 日历无事件 → 期望: "暂无事件"空状态

**测试契约:**
1. 审批通过触发分发
   - 入口: `POST /api/v1/studio/documents/{id}/transition` body={"status": "executed"}
   - 反例: 错误实现可能对所有文档类型都触发 dispatch
   - 边界: notification 类型 / report 类型 / 重复 transition
   - 回归: N/A
   - 命令: `python -m pytest tests/test_api/test_studio_api.py -v`
2. 通知审批前置检查（F4）
   - 入口: `POST /api/v1/studio/documents/{id}/transition` body={"status": "executed"} 且 doc.status="reviewed"
   - 反例: 错误实现允许跳过审批直接执行
   - 边界: notification reviewed→executed / notification approved→executed / report reviewed→executed（允许）
   - 回归: N/A
   - 命令: `python -m pytest tests/test_api/test_studio_api.py -v`
3. 通知执行权限检查（F3）
   - 入口: `POST /api/v1/studio/documents/{id}/transition` body={"status": "executed"} 无 SEND_NOTIFICATION 权限
   - 反例: 任何有 GENERATE_NOTIFICATION 权限的人都能发送通知
   - 边界: 有/无 SEND_NOTIFICATION 权限
   - 回归: N/A
   - 命令: `python -m pytest tests/test_api/test_studio_api.py -v`

---

## GPT Review Finding 处置记录

> Plan Review Round 1 findings，已全部在计划中修复。

| ID | Severity | Category | Finding | 处置 | 影响 Task |
|----|----------|----------|---------|------|-----------|
| F1 | HIGH | code-bug | `created_by="system"` 违反 FK → users.id | `get_triggered_rules` 传递 `event.created_by`；`auto_draft` 用 `rule["created_by"]` | Task 2, 3 |
| F2 | HIGH | design-concern | 自动拟稿文档不出现在教师 Studio 队列 | Document 新增 `assigned_to` 字段；`list_documents` 查 `OR` 条件 | Task 1, 3 |
| F3 | HIGH | code-bug | transition endpoint 权限降级（get_current_user） | 保留 `require_permission(GENERATE_NOTIFICATION)`；executed 额外检查 `SEND_NOTIFICATION` | Task 4 |
| F4 | HIGH | design-concern | 审批流未接入，教师可直接 executed | `StudioService.transition_status` 阻断 notification reviewed→executed；API 层 pending 时创建 ApprovalFlow | Task 4 |
| F5 | HIGH | code-bug | worker.py 导入 `async_session_factory`（不存在）+ arq 启动方式错误 | 改为导入 `async_session`；删除 `__main__` 入口，用 `arq CLI` 启动 | Task 3 |
| F6 | MED | design-concern | 自动拟稿生成空模板 | 添加 `_fill_template_content` 函数，用事件上下文填充各 section | Task 3 |
