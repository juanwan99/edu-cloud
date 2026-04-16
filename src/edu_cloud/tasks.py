import logging
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.services.calendar_service import CalendarService
from edu_cloud.services.studio_service import StudioService
from edu_cloud.templates.document_templates import TEMPLATES

logger = logging.getLogger(__name__)

# F6 fix: 事件上下文填充模板内容（非空占位）
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
    content = {}
    ctx = {
        "event_title": rule["event_title"],
        "event_date": rule["event_date"],
        "school_name": "",  # 可后续从 school 表填充
        "today": str(date.today()),
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

        # F1 fix: 使用事件创建者的 user.id 作为 created_by（FK 约束）
        # F2 fix: assigned_to 设为事件创建者，确保其 Studio 队列可见
        doc = await studio_svc.create_document(
            type="notification",
            title=f"{rule['event_title']} — {template['name']}",
            content_json=content,
            school_id=rule["school_id"],
            created_by=rule["created_by"],
            source_context={
                "event_id": rule["event_id"],
                "event_date": rule["event_date"],
                "template_type": rule["template_type"],
                "auto_generated": True,
            },
        )
        # F2: 设置 assigned_to
        doc.assigned_to = rule["created_by"]
        await db.flush()

        # 标记规则已触发
        await cal_svc.mark_rule_triggered(rule["rule_id"])
        created += 1
        logger.info(f"Auto-drafted notification: {doc.title} (event: {rule['event_title']})")

    await db.commit()
    return created
