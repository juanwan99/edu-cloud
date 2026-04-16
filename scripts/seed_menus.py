"""好分数 8 模块 × 45 子菜单种子数据。

Usage:
    cd C:/Users/Administrator/edu-cloud
    python scripts/seed_menus.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import select
from edu_cloud.database import async_session
from edu_cloud.modules.menu.models import MenuConfig


MODULES = [
    {
        "code": "exam", "name": "阅卷", "icon": "document", "sort": 1,
        "roles": ["subject_teacher", "homeroom_teacher", "lesson_prep_leader",
                  "grade_leader", "teaching_research_leader", "academic_director", "principal"],
        "requires_module": "exam",
        "children": [
            {"code": "exam_list", "name": "考试列表", "path": "/exam/list", "icon": "list", "sort": 1},
            {"code": "exam_quiz", "name": "测验列表", "path": "/exam/quiz", "icon": "edit-pen", "sort": 2},
            {"code": "exam_grading", "name": "阅卷任务", "path": "/exam/grading", "icon": "finished", "sort": 3},
            {"code": "exam_answercard", "name": "答题卡工具", "path": "/exam/answercard", "icon": "postcard", "sort": 4},
            {"code": "exam_statistics", "name": "考试统计", "path": "/exam/statistics", "icon": "data-line", "sort": 5},
        ],
    },
    {
        "code": "report", "name": "分析", "icon": "data-analysis", "sort": 2,
        "roles": ["subject_teacher", "homeroom_teacher", "grade_leader",
                  "teaching_research_leader", "academic_director", "principal"],
        "requires_module": "study_analytics",
        "children": [
            {"code": "report_exam", "name": "考试报告", "path": "/report/exam", "icon": "document", "sort": 1},
            {"code": "report_contrast", "name": "班级对比", "path": "/report/contrast", "icon": "histogram", "sort": 2},
            {"code": "report_custom", "name": "自定义分析", "path": "/report/custom", "icon": "set-up", "sort": 3},
            {"code": "report_table", "name": "自定义表格", "path": "/report/table", "icon": "grid", "sort": 4},
            {"code": "report_level_score", "name": "等级赋分", "path": "/report/level-score", "icon": "medal", "sort": 5},
            {"code": "report_config", "name": "指标配置", "path": "/report/config", "icon": "setting", "sort": 6},
        ],
    },
    {
        "code": "study", "name": "学情", "icon": "trend-charts", "sort": 3,
        "roles": ["subject_teacher", "homeroom_teacher", "grade_leader",
                  "teaching_research_leader", "academic_director", "principal"],
        "requires_module": "study_analytics",
        "children": [
            {"code": "study_dashboard", "name": "数据看板", "path": "/study/dashboard", "icon": "odometer", "sort": 1},
            {"code": "study_class", "name": "班级学情", "path": "/study/class", "icon": "school", "sort": 2},
            {"code": "study_student", "name": "学生学情", "path": "/study/student", "icon": "user", "sort": 3},
            {"code": "study_layer", "name": "分层学情", "path": "/study/layer", "icon": "operation", "sort": 4},
        ],
    },
    {
        "code": "work", "name": "作业", "icon": "notebook", "sort": 4,
        "roles": ["subject_teacher", "homeroom_teacher", "lesson_prep_leader",
                  "grade_leader", "teaching_research_leader", "academic_director", "principal"],
        "requires_module": "homework",
        "children": [
            {"code": "work_list", "name": "作业列表", "path": "/work/list", "icon": "list", "sort": 1},
            {"code": "work_publish", "name": "布置作业", "path": "/work/publish", "icon": "edit", "sort": 2},
            {"code": "work_scan", "name": "扫描作业", "path": "/work/scan", "icon": "camera", "sort": 3},
            {"code": "work_sync", "name": "同步作业", "path": "/work/sync", "icon": "refresh", "sort": 4},
        ],
    },
    {
        "code": "lesson", "name": "教学", "icon": "reading", "sort": 5,
        "roles": ["subject_teacher", "homeroom_teacher", "lesson_prep_leader",
                  "grade_leader", "teaching_research_leader", "academic_director", "principal"],
        "requires_module": "teaching",
        "children": [
            {"code": "lesson_console", "name": "精准教学台", "path": "/lesson/console", "icon": "monitor", "sort": 1},
            {"code": "lesson_after_exam", "name": "考后分析", "path": "/lesson/after-exam", "icon": "document-checked", "sort": 2},
            {"code": "lesson_resources", "name": "备课资源", "path": "/lesson/resources", "icon": "folder-opened", "sort": 3},
            {"code": "lesson_space", "name": "我的空间", "path": "/lesson/space", "icon": "box", "sort": 4},
        ],
    },
    {
        "code": "research", "name": "教研", "icon": "collection", "sort": 6,
        "roles": ["subject_teacher", "lesson_prep_leader", "teaching_research_leader",
                  "academic_director", "principal"],
        "requires_module": "research",
        "children": [
            {"code": "research_questions", "name": "题库选题", "path": "/research/questions", "icon": "search", "sort": 1},
            {"code": "research_paper_builder", "name": "结构组卷", "path": "/research/paper-builder", "icon": "document-add", "sort": 2},
            {"code": "research_group_prep", "name": "集体备课", "path": "/research/group-prep", "icon": "chat-dot-round", "sort": 3},
            {"code": "research_knowledge", "name": "知识体系", "path": "/research/knowledge", "icon": "connection", "sort": 4},
            {"code": "research_plan", "name": "教学计划", "path": "/research/plan", "icon": "calendar", "sort": 5},
            {"code": "research_radar", "name": "考情雷达", "path": "/research/radar", "icon": "aim", "sort": 6},
            {"code": "research_school_resources", "name": "校本资源", "path": "/research/school-resources", "icon": "files", "sort": 7},
        ],
    },
    {
        "code": "baseinfo", "name": "基础信息", "icon": "user", "sort": 7,
        "roles": ["academic_director", "principal", "platform_admin"],
        "children": [
            {"code": "baseinfo_students", "name": "学生信息", "path": "/baseinfo/students", "icon": "user", "sort": 1},
            {"code": "baseinfo_teachers", "name": "教师信息", "path": "/baseinfo/teachers", "icon": "avatar", "sort": 2},
            {"code": "baseinfo_grades", "name": "年级管理", "path": "/baseinfo/grades", "icon": "school", "sort": 3},
            {"code": "baseinfo_records", "name": "人员动态", "path": "/baseinfo/records", "icon": "document", "sort": 4},
            {"code": "baseinfo_schedule", "name": "教师任课表", "path": "/baseinfo/schedule", "icon": "date", "sort": 5},
            {"code": "baseinfo_selected_exam", "name": "选考管理", "path": "/baseinfo/selected-exam", "icon": "checked", "sort": 6},
            {"code": "baseinfo_vip", "name": "版本权益", "path": "/baseinfo/vip", "icon": "trophy", "sort": 7},
        ],
    },
    {
        "code": "academic", "name": "教务", "icon": "office-building", "sort": 8,
        "roles": ["academic_director", "principal", "platform_admin"],
        "children": [
            {"code": "academic_semester", "name": "学期管理", "path": "/academic/semester", "icon": "calendar", "sort": 1},
            {"code": "academic_timetable", "name": "课表", "path": "/academic/timetable", "icon": "grid", "sort": 2},
            {"code": "academic_course_selection", "name": "选课", "path": "/academic/course-selection", "icon": "menu", "sort": 3},
            {"code": "academic_exam_schedule", "name": "考试安排", "path": "/academic/exam-schedule", "icon": "date", "sort": 4},
            {"code": "academic_score_manage", "name": "成绩管理", "path": "/academic/score-manage", "icon": "document-checked", "sort": 5},
        ],
    },
]


async def seed():
    async with async_session() as session:
        result = await session.execute(select(MenuConfig).limit(1))
        if result.scalar():
            print("menu_configs 已有数据，跳过")
            return

        for module in MODULES:
            parent = MenuConfig(
                code=module["code"],
                name=module["name"],
                icon=module["icon"],
                sort=module["sort"],
                roles=module["roles"],
                requires_module=module.get("requires_module"),
                is_active=True,
            )
            session.add(parent)
            await session.flush()

            for child in module["children"]:
                session.add(MenuConfig(
                    code=child["code"],
                    name=child["name"],
                    icon=child["icon"],
                    sort=child["sort"],
                    parent_id=parent.id,
                    path=child["path"],
                    roles=module["roles"],
                    is_active=True,
                ))

        await session.commit()
        total = sum(1 + len(m["children"]) for m in MODULES)
        print(f"已插入 {total} 条菜单记录（{len(MODULES)} 模块 + {total - len(MODULES)} 子菜单）")


if __name__ == "__main__":
    asyncio.run(seed())
