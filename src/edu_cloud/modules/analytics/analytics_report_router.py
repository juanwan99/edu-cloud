"""统计分析报告/趋势/导出子路由。"""
import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.api.permissions import get_visible_subject_codes, get_visible_class_ids
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.analytics.report_service import (
    build_report, get_grade_trend, get_class_trend, get_student_trend,
)
from edu_cloud.modules.analytics.exporters import (
    build_grade_subject_report,
    render_grade_subject_report_pdf,
    render_grade_subject_report_xlsx,
    build_student_subject_report,
    render_student_subject_report_pdf,
    render_student_subject_report_xlsx,
)
from edu_cloud.services.exceptions import NotFoundError, PermissionDeniedError
from edu_cloud.modules.analytics.ranking_service import (
    student_rankings, critical_students, class_boxplot,
    class_knowledge, class_error_patterns,
)
from edu_cloud.modules.analytics.diagnosis_service import class_diagnosis
from edu_cloud.modules.analytics.layer_service import layer_analysis
from edu_cloud.modules.analytics.grade_service import (
    get_grade_overview, get_grade_exam_trend, get_grade_subject_comparison,
)
from edu_cloud.modules.analytics.power_options_service import get_power_options
from edu_cloud.modules.analytics.level_score_service import convert_level_score
from edu_cloud.modules.analytics.insights_service import (
    question_insights, exam_diagnosis, common_wrong_questions,
)
from edu_cloud.modules.analytics.ai_report_service import build_ai_grading_report
from edu_cloud.modules.analytics.ai_diagnosis_service import get_or_generate as ai_diagnosis_get_or_generate

logger = logging.getLogger(__name__)

router = APIRouter()


# --- PowerOptions 级联筛选器 ---

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
    class_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """题目错因聚合 + 难度/区分度。"""
    role = current["current_role"]
    return await question_insights(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        class_id=class_id,
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


@router.get("/exam/{exam_id}/ai-grading-report")
async def get_ai_grading_report(
    exam_id: str,
    subject_id: str | None = Query(None),
    class_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """AI 阅卷报告：覆盖率、置信度、AI/人工差异、流水线质量和诊断建议。"""
    role = current["current_role"]
    return await build_ai_grading_report(
        db,
        exam_id=exam_id,
        school_id=role.school_id,
        subject_id=subject_id,
        class_id=class_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


# --- 分析报告路由 ---

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


# --- 排名/临界生/箱线图 ---

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


# --- 班级诊断/知识点/错误模式 ---

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
    class_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """班级错误模式对比。"""
    role = current["current_role"]
    return await class_error_patterns(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        class_id=class_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


# --- 分层学情 ---

@router.get("/exam/{exam_id}/layer-analysis")
async def get_layer_analysis(
    exam_id: str,
    subject_id: str | None = Query(None),
    class_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    return await layer_analysis(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id,
        class_id=class_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
    )


# --- 年级聚合分析 (WP-D) ---

@router.get("/grade/{grade_id}/overview")
async def grade_overview(
    grade_id: str,
    exam_id: str = Query(..., description="考试 ID"),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """年级概览：某次考试中该年级各班级的聚合数据。"""
    role = current["current_role"]
    return await get_grade_overview(
        db, school_id=role.school_id, grade_id=grade_id, exam_id=exam_id,
        visible_subject_codes=get_visible_subject_codes(role),
    )


@router.get("/grade/{grade_id}/trend")
async def grade_exam_trend(
    grade_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """年级考情趋势：该年级最近 N 次考试的年级级别聚合。"""
    role = current["current_role"]
    return await get_grade_exam_trend(
        db, school_id=role.school_id, grade_id=grade_id, limit=limit,
    )


@router.get("/grade/{grade_id}/subjects")
async def grade_subject_comparison(
    grade_id: str,
    exam_id: str = Query(..., description="考试 ID"),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """年级科目对比：某次考试中该年级各科目的聚合数据。"""
    role = current["current_role"]
    return await get_grade_subject_comparison(
        db, school_id=role.school_id, grade_id=grade_id, exam_id=exam_id,
    )


# --- AI 诊断 ---

@router.post("/exam/{exam_id}/ai-diagnosis")
async def generate_ai_diagnosis(
    exam_id: str,
    force_refresh: bool = Query(False),
    subject_id: str | None = Query(None),
    class_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """生成 AI 诊断报告（缓存命中则直接返回）。"""
    role = current["current_role"]
    return await ai_diagnosis_get_or_generate(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id, class_id=class_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
        user_role=role.role,
        force_refresh=force_refresh,
    )


@router.get("/exam/{exam_id}/ai-diagnosis")
async def get_ai_diagnosis(
    exam_id: str,
    subject_id: str | None = Query(None),
    class_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """获取缓存的 AI 诊断报告（不触发生成）。"""
    from edu_cloud.modules.analytics.ai_diagnosis_service import build_snapshot, _get_cache
    role = current["current_role"]
    snapshot = await build_snapshot(
        db, exam_id=exam_id, school_id=role.school_id,
        subject_id=subject_id, class_id=class_id,
        visible_subject_codes=get_visible_subject_codes(role),
        visible_class_ids=get_visible_class_ids(role),
        user_role=role.role,
    )
    cached = await _get_cache(db, snapshot.snapshot.snapshot_hash)
    if not cached:
        return {"status": "not_found", "message": "尚未生成 AI 诊断报告"}
    return cached
