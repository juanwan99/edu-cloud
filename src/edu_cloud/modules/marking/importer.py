import logging
import platform
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.services.marking_workflow import Exam, Question, StudentAnswer, Subject

logger = logging.getLogger(__name__)


def _normalize_path(folder_path: str) -> Path:
    """将 Windows 路径转为当前平台可用路径。

    在 WSL 中运行时，自动将 D:/xxx 或 D:\\xxx 转为 /mnt/d/xxx。
    """
    match = re.match(r'^([A-Za-z]):[/\\](.*)$', folder_path)
    if match and platform.system() == "Linux":
        drive = match.group(1).lower()
        rest = match.group(2).replace('\\', '/')
        wsl_path = f"/mnt/{drive}/{rest}"
        logger.info("Windows 路径转 WSL: %s → %s", folder_path, wsl_path)
        return Path(wsl_path)
    return Path(folder_path)


async def import_from_folder(
    db: AsyncSession,
    exam_id: str,
    folder_path: str,
    school_id: str,
) -> dict:
    """扫描文件夹结构，创建 Subject/Question/StudentAnswer 记录。

    文件夹结构：{folder_path}/{科目名}/{题号}/{学生ID}.png
    幂等：已存在的记录跳过。
    支持 Windows 路径自动转 WSL 路径。
    """
    root = _normalize_path(folder_path)
    if not root.is_dir():
        raise ValueError(f"文件夹不存在: {folder_path} (resolved: {root})")

    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise ValueError(f"考试不存在: {exam_id}")

    # 预加载已有数据到内存，避免逐条查询
    existing_subjects = {}
    for s in (await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    )).scalars().all():
        existing_subjects[s.name] = s

    existing_questions = {}  # (subject_id, name) → Question
    for q in (await db.execute(
        select(Question).where(Question.subject_id.in_(
            [s.id for s in existing_subjects.values()]
        ))
    )).scalars().all() if existing_subjects else []:
        existing_questions[(q.subject_id, q.name)] = q

    existing_answers = set()  # (exam_id, student_id, question_id)
    for row in (await db.execute(
        select(StudentAnswer.student_id, StudentAnswer.question_id).where(
            StudentAnswer.exam_id == exam_id,
            StudentAnswer.school_id == school_id,
        )
    )).all():
        existing_answers.add((exam_id, row[0], row[1]))

    stats = {"subjects_created": 0, "questions_created": 0, "answers_created": 0, "answers_skipped": 0}
    batch = []  # 攒批量 add
    BATCH_SIZE = 500

    for subject_dir in sorted(root.iterdir()):
        if not subject_dir.is_dir():
            continue
        subject_name = subject_dir.name

        subject = existing_subjects.get(subject_name)
        if not subject:
            code = subject_name.upper()[:10]
            subject = Subject(
                exam_id=exam_id, name=subject_name,
                code=code, school_id=school_id,
            )
            db.add(subject)
            await db.flush()
            existing_subjects[subject_name] = subject
            stats["subjects_created"] += 1
            logger.info("创建科目: %s (code=%s)", subject_name, code)

        for question_dir in sorted(subject_dir.iterdir()):
            if not question_dir.is_dir():
                continue
            question_name = question_dir.name

            question = existing_questions.get((subject.id, question_name))
            if not question:
                question = Question(
                    subject_id=subject.id, name=question_name,
                    question_type="essay", max_score=10.0,
                    school_id=school_id,
                )
                db.add(question)
                await db.flush()
                existing_questions[(subject.id, question_name)] = question
                stats["questions_created"] += 1

            image_exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
            image_files = sorted(
                f for f in question_dir.iterdir()
                if f.is_file() and f.suffix.lower() in image_exts
            )

            for img_file in image_files:
                student_id = img_file.stem
                key = (exam_id, student_id, question.id)

                if key in existing_answers:
                    stats["answers_skipped"] += 1
                    continue

                # 直接用 str(img_file) 避免昂贵的 resolve() 调用
                image_path = str(img_file)
                batch.append(StudentAnswer(
                    exam_id=exam_id, subject_id=subject.id,
                    student_id=student_id, question_id=question.id,
                    image_path=image_path, school_id=school_id,
                ))
                existing_answers.add(key)
                stats["answers_created"] += 1

                if len(batch) >= BATCH_SIZE:
                    db.add_all(batch)
                    await db.flush()
                    batch.clear()
                    logger.debug("批量写入 %d 条答卷记录", BATCH_SIZE)

    # 写入剩余
    if batch:
        db.add_all(batch)
        await db.flush()

    await db.commit()
    logger.info("导入完成: %s", stats)
    return stats
