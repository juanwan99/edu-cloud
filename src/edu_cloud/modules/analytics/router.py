"""统计分析路由 — 从 exam-ai 迁入。支持 subject_id 单参数查询（Phase 2.3 examids 统一）。"""
import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.api.permissions import get_visible_subject_codes, get_visible_class_ids
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.analytics import service as analytics_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/exam/{exam_id}/summary")
async def exam_summary(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    return await analytics_service.exam_summary(
        db, exam_id=exam_id, school_id=role.school_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/subject/{subject_id}/summary")
async def subject_summary(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """单科目维度的考试总览。通过 subject_id 自动解析 exam_id。"""
    role = current["current_role"]
    exam_id, _ = await analytics_service.resolve_subject_to_exam(
        db, subject_id, role.school_id,
    )
    return await analytics_service.exam_summary(
        db, exam_id=exam_id, school_id=role.school_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/distribution")
async def exam_distribution(
    exam_id: str,
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    return await analytics_service.exam_distribution(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/subject/{subject_id}/distribution")
async def subject_distribution(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """单科目维度的成绩分布。通过 subject_id 自动解析 exam_id。"""
    role = current["current_role"]
    exam_id, _ = await analytics_service.resolve_subject_to_exam(
        db, subject_id, role.school_id,
    )
    return await analytics_service.exam_distribution(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/subject/{subject_id}/questions")
async def subject_question_analysis(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    return await analytics_service.subject_question_analysis(
        db, subject_id=subject_id, school_id=role.school_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/grade-aggregates")
async def grade_aggregates(
    exam_id: str,
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    return await analytics_service.grade_aggregates(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/subject/{subject_id}/grade-aggregates")
async def subject_grade_aggregates(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """单科目维度的年级聚合统计。通过 subject_id 自动解析 exam_id。"""
    role = current["current_role"]
    exam_id, _ = await analytics_service.resolve_subject_to_exam(
        db, subject_id, role.school_id,
    )
    return await analytics_service.grade_aggregates(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


# --- 分数段配置管理 ---

from edu_cloud.modules.analytics.segment_service import (
    get_segment_config, upsert_segment_config, list_segment_configs,
)


@router.get("/segments/config")
async def get_segments_config(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAM_RESULTS)),
):
    """获取本校分数段配置（默认 + 科目覆盖列表）。"""
    role = current["current_role"]
    school_id = role.school_id
    configs = await list_segment_configs(db, school_id)
    default_cfg = next((c for c in configs if c.subject_code is None), None)
    overrides = [c for c in configs if c.subject_code is not None]
    return {
        "default": {
            "boundaries": default_cfg.boundaries if default_cfg else [85, 70, 60],
            "labels": default_cfg.labels if default_cfg else ["优秀", "良好", "及格", "不及格"],
        },
        "overrides": [
            {"subject_code": c.subject_code, "boundaries": c.boundaries, "labels": c.labels}
            for c in overrides
        ],
    }


@router.put("/segments/config")
async def update_segments_config(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAM_RESULTS)),
):
    """创建或更新分数段配置（upsert）。"""
    role = current["current_role"]
    user = current["user"]
    cfg = await upsert_segment_config(
        db,
        school_id=role.school_id,
        boundaries=body["boundaries"],
        labels=body["labels"],
        created_by=user.id,
        subject_code=body.get("subject_code"),
    )
    await db.commit()
    return {
        "subject_code": cfg.subject_code,
        "boundaries": cfg.boundaries,
        "labels": cfg.labels,
    }


@router.delete("/segments/config/{subject_code}")
async def delete_segment_override(
    subject_code: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAM_RESULTS)),
):
    """删除科目覆盖配置（硬删）。不允许删除学校默认。"""
    role = current["current_role"]
    from sqlalchemy import select as sa_select, delete as sa_delete
    from edu_cloud.models.score_segment import ScoreSegmentConfig as SSC
    result = await db.execute(
        sa_select(SSC).where(
            SSC.school_id == role.school_id,
            SSC.subject_code == subject_code,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(404, "配置不存在")
    await db.execute(
        sa_delete(SSC).where(SSC.id == cfg.id)
    )
    await db.commit()
    return {"deleted": subject_code}


# --- 分析报告路由 ---

from edu_cloud.modules.analytics.report_service import (
    build_report, get_grade_trend, get_class_trend, get_student_trend,
)
from sqlalchemy import select as sa_select


@router.post("/report/query")
async def report_query(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """自定义分析构建器。按角色白名单裁剪 metrics。"""
    role = current["current_role"]
    exam_ids = body.get("exam_ids", [])
    if not exam_ids:
        raise HTTPException(422, "exam_ids 不能为空")
    RESTRICTED_METRICS = {"ranking", "top_bottom"}
    RESTRICTED_ROLES = {"parent", "homeroom_teacher", "subject_teacher"}
    ALL_METRICS = ["summary", "segments", "ranking", "questions", "top_bottom"]
    requested_metrics = body.get("metrics") or ALL_METRICS
    if role.role in RESTRICTED_ROLES:
        allowed_metrics = [m for m in requested_metrics if m not in RESTRICTED_METRICS]
    else:
        allowed_metrics = requested_metrics
    return await build_report(
        db,
        school_id=role.school_id,
        exam_ids=exam_ids,
        metrics=allowed_metrics,
        subject_codes=body.get("subject_codes"),
        class_ids=body.get("class_ids"),
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/report/trend/grade")
async def grade_trend_api(
    exam_ids: str = Query(..., description="逗号分隔的考试 ID"),
    subject_code: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    GRADE_TREND_ROLES = {"principal", "academic_director", "grade_leader", "platform_admin", "district_admin"}
    if role.role not in GRADE_TREND_ROLES:
        raise HTTPException(403, "无权查看年级趋势")
    ids = [eid.strip() for eid in exam_ids.split(",") if eid.strip()]
    return await get_grade_trend(
        db, school_id=role.school_id, exam_ids=ids,
        subject_code=subject_code,
        visible_subject_codes=get_visible_subject_codes(role),
    )


@router.get("/report/trend/class")
async def class_trend_api(
    exam_ids: str = Query(...),
    class_id: str = Query(...),
    subject_code: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    if role.role == "parent":
        raise HTTPException(403, "家长无权查看班级趋势")
    ids = [eid.strip() for eid in exam_ids.split(",") if eid.strip()]
    vis_classes = get_visible_class_ids(role)
    if vis_classes is not None and class_id not in vis_classes:
        raise HTTPException(403, "无权访问该班级")
    return await get_class_trend(
        db, school_id=role.school_id, exam_ids=ids, class_id=class_id,
        subject_code=subject_code,
        visible_subject_codes=get_visible_subject_codes(role),
    )


@router.get("/report/trend/student")
async def student_trend_api(
    exam_ids: str = Query(...),
    student_id: str = Query(...),
    subject_code: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """显式校验 student_id 可见性（班级/家长 guardian）。"""
    role = current["current_role"]
    ids = [eid.strip() for eid in exam_ids.split(",") if eid.strip()]
    # 家长：只能查自己孩子（优先于班级可见性）
    if role.role == "parent":
        from edu_cloud.models.guardian import GuardianStudentLink
        guard_result = await db.execute(
            sa_select(GuardianStudentLink.id).where(
                GuardianStudentLink.guardian_user_id == current["user"].id,
                GuardianStudentLink.student_id == student_id,
            )
        )
        if not guard_result.scalar_one_or_none():
            raise HTTPException(403, "家长只能查看自己孩子的数据")
    else:
        # 非家长：按班级可见性校验
        vis_classes = get_visible_class_ids(role)
        if vis_classes is not None:
            from edu_cloud.modules.student.models import Student
            stu_result = await db.execute(
                sa_select(Student.class_id).where(
                    Student.id == student_id, Student.school_id == role.school_id
                )
            )
            stu_row = stu_result.first()
            if not stu_row or stu_row.class_id not in vis_classes:
                raise HTTPException(403, "无权查看该学生数据")
    return await get_student_trend(
        db, school_id=role.school_id, exam_ids=ids, student_id=student_id,
        subject_code=subject_code,
        visible_subject_codes=get_visible_subject_codes(role),
    )


@router.post("/report/export", status_code=201)
async def export_report(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.GENERATE_REPORT)),
):
    """生成分析报告文档（走 Studio）。"""
    role = current["current_role"]
    user = current["user"]
    exam_ids = body.get("exam_ids", [])
    if not exam_ids:
        raise HTTPException(422, "exam_ids 不能为空")

    RESTRICTED_METRICS = {"ranking", "top_bottom"}
    RESTRICTED_ROLES = {"parent", "homeroom_teacher", "subject_teacher"}
    ALL_METRICS = ["summary", "segments", "ranking", "questions", "top_bottom"]
    requested_metrics = body.get("metrics") or ALL_METRICS
    if role.role in RESTRICTED_ROLES:
        allowed_metrics = [m for m in requested_metrics if m not in RESTRICTED_METRICS]
    else:
        allowed_metrics = requested_metrics

    report_data = await build_report(
        db, school_id=role.school_id, exam_ids=exam_ids,
        metrics=allowed_metrics,
        subject_codes=body.get("subject_codes"),
        class_ids=body.get("class_ids"),
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )

    from edu_cloud.modules.exam.models import Exam as ExamModel
    exam_result = await db.execute(sa_select(ExamModel).where(ExamModel.id == exam_ids[0]))
    exam = exam_result.scalar_one_or_none()
    title = body.get("title") or f"{exam.name if exam else '考试'}分析报告"

    from edu_cloud.modules.studio.service import StudioService
    svc = StudioService(db)
    doc = await svc.create_document(
        type="analysis_report",
        title=title,
        content_json={
            "report_type": "exam_analysis",
            "config": {"exam_ids": exam_ids, "metrics": body.get("metrics")},
            "sections": report_data["metrics"],
        },
        school_id=role.school_id,
        created_by=user.id,
    )
    # Studio 状态流转：draft → reviewed → executed
    await svc.transition_status(doc.id, "reviewed", school_id=role.school_id)
    await svc.transition_status(doc.id, "executed", school_id=role.school_id)
    await db.commit()

    return {
        "document_id": doc.id,
        "status": "executed",
        "title": doc.title,
    }


# --- Phase 2-A: 年级学科报告导出 ----------------------------------

from edu_cloud.modules.analytics.exporters import (
    build_grade_subject_report,
    render_grade_subject_report_pdf,
    render_grade_subject_report_xlsx,
    build_student_subject_report,
    render_student_subject_report_pdf,
    render_student_subject_report_xlsx,
)
from edu_cloud.services.exceptions import NotFoundError, PermissionDeniedError


@router.get("/report/grade/{exam_id}/{subject_id}/export")
async def export_grade_subject_report(
    exam_id: str,
    subject_id: str,
    format: str = Query("pdf", pattern="^(pdf|xlsx)$"),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """导出年级学科报告（PDF / XLSX）。

    权限：通过 visible_subject_codes / visible_class_ids 过滤。
    """
    role = current["current_role"]
    try:
        report = await build_grade_subject_report(
            db, exam_id=exam_id, subject_id=subject_id, school_id=role.school_id,
            visible_subject_codes=get_visible_subject_codes(role),
            visible_class_ids=get_visible_class_ids(role),
        )
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except PermissionDeniedError as e:
        raise HTTPException(403, str(e))

    base_name = f"{report['exam']['name']}-{report['subject']['name']}-年级报告"
    if format == "pdf":
        data = render_grade_subject_report_pdf(report)
        media_type = "application/pdf"
        filename = f"{base_name}.pdf"
    else:
        data = render_grade_subject_report_xlsx(report)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"{base_name}.xlsx"

    encoded = quote(filename)
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
        },
    )


@router.get("/report/student/{student_id}/{exam_id}/{subject_id}/export")
async def export_student_subject_report(
    student_id: str,
    exam_id: str,
    subject_id: str,
    format: str = Query("pdf", pattern="^(pdf|xlsx)$"),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """导出个人学科报告（PDF / XLSX）。

    权限：visible_class_ids / visible_subject_codes 双重过滤；
    家长/学生本人走 conduct/parent 体系（cp_token），不在此端点。
    """
    role = current["current_role"]
    try:
        report = await build_student_subject_report(
            db, student_id=student_id, exam_id=exam_id, subject_id=subject_id,
            school_id=role.school_id,
            visible_subject_codes=get_visible_subject_codes(role),
            visible_class_ids=get_visible_class_ids(role),
        )
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except PermissionDeniedError as e:
        raise HTTPException(403, str(e))

    base_name = (
        f"{report['student']['name']}-{report['exam']['name']}-"
        f"{report['subject']['name']}-个人报告"
    )
    if format == "pdf":
        data = render_student_subject_report_pdf(report)
        media_type = "application/pdf"
        filename = f"{base_name}.pdf"
    else:
        data = render_student_subject_report_xlsx(report)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"{base_name}.xlsx"

    encoded = quote(filename)
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
        },
    )


# --- PowerOptions 级联筛选器 ---

from edu_cloud.modules.analytics.power_options_service import get_power_options


@router.get("/power-options")
async def power_options(
    exam_type: str | None = Query(None),
    year: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """返回 年级→班级→科目→考试 级联筛选树。已按角色 RBAC 过滤。"""
    role = current["current_role"]
    return await get_power_options(
        db,
        school_id=role.school_id,
        visible_class_ids=get_visible_class_ids(role),
        visible_subject_codes=get_visible_subject_codes(role),
        exam_type=exam_type,
        year=year,
    )


# --- 等级赋分 ---

from edu_cloud.modules.analytics.level_score_service import convert_level_score


@router.post("/level-score/convert")
async def level_score_convert(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAM_RESULTS)),
):
    """等级赋分转换：原始分按百分位划分等级，线性插值赋分。"""
    role = current["current_role"]
    result = await convert_level_score(
        db,
        school_id=role.school_id,
        exam_id=body["exam_id"],
        subject_id=body["subject_id"],
        levels=body["levels"],
        class_id=body.get("class_id"),
    )
    if result is None:
        raise HTTPException(404, "无成绩数据")
    return result


# --- AI 深度分析 ---

from edu_cloud.modules.analytics.insights_service import (
    question_insights, exam_diagnosis, common_wrong_questions,
)


@router.get("/exam/{exam_id}/common-wrong-questions")
async def get_common_wrong_questions(
    exam_id: str,
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """常错题聚合：按题错误人数和平均得分率，按错误率降序。"""
    role = current["current_role"]
    return await common_wrong_questions(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/question-insights")
async def get_question_insights(
    exam_id: str,
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """题目错因聚合 + 难度/区分度。"""
    role = current["current_role"]
    return await question_insights(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/diagnosis")
async def get_exam_diagnosis(
    exam_id: str,
    subject_id: str | None = Query(None),
    class_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """考试诊断文本（模板拼接，ORC-007 不调 LLM）。"""
    role = current["current_role"]
    return await exam_diagnosis(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        class_id=class_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


from edu_cloud.modules.analytics.ranking_service import (
    student_rankings, critical_students, class_boxplot,
)


@router.get("/exam/{exam_id}/student-rankings")
async def get_student_rankings(
    exam_id: str,
    subject_id: str | None = Query(None),
    class_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """学生排名 + 进退步 delta。"""
    role = current["current_role"]
    return await student_rankings(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id, class_id=class_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/critical-students")
async def get_critical_students(
    exam_id: str,
    subject_id: str | None = Query(None),
    class_id: str | None = Query(None),
    threshold: int = Query(3),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """临界生筛选。"""
    role = current["current_role"]
    return await critical_students(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id, class_id=class_id,
        threshold=threshold,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/class-boxplot")
async def get_class_boxplot(
    exam_id: str,
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """各班分数箱线图数据。"""
    role = current["current_role"]
    return await class_boxplot(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


from edu_cloud.modules.analytics.ranking_service import class_knowledge, class_error_patterns
from edu_cloud.modules.analytics.diagnosis_service import class_diagnosis


@router.get("/exam/{exam_id}/class-knowledge")
async def get_class_knowledge(
    exam_id: str,
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """班级×知识点 掌握率热力图。"""
    role = current["current_role"]
    return await class_knowledge(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/class-diagnosis")
async def get_class_diagnosis(
    exam_id: str,
    subject_id: str | None = Query(None),
    class_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    return await class_diagnosis(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        class_id=class_id,
        visible_class_ids=get_visible_class_ids(role),
    )


@router.get("/exam/{exam_id}/class-error-patterns")
async def get_class_error_patterns(
    exam_id: str,
    subject_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """班级错误模式对比。"""
    role = current["current_role"]
    return await class_error_patterns(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


from edu_cloud.modules.analytics.layer_service import layer_analysis


@router.get("/exam/{exam_id}/layer-analysis")
async def get_layer_analysis(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    return await layer_analysis(
        db, exam_id=exam_id, school_id=role.school_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )
