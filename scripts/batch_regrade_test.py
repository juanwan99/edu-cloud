"""批量重新评分测试脚本。

选50名学生，对语文/生物/地理三科：
1. 用新提示词重新生成评分细则（语文/生物）
2. 用 Gemini Batch API（经济模式，50%折扣）重新 OCR + 评分
3. 输出结果对比（新AI vs 旧AI vs 人工标注）
"""
import asyncio
import base64
import json
import logging
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from google.genai import types

from edu_cloud.config import settings
from edu_cloud.modules.grading.gemini_client import GeminiClient, _make_image_part
from edu_cloud.modules.grading.json_parser import extract_json
from edu_cloud.modules.grading.prompts import get_prompt, render_prompt
from edu_cloud.modules.grading.prompts.base import OCR_STRUCTURED_PROMPT_BASE, count_essay_chars
from edu_cloud.modules.grading.rubric_formatter import format_rubric_for_grading
from edu_cloud.modules.grading.ocr_validator import validate_ocr_blanks, recover_truncated_blanks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EXAM_ID = "796f7c26-77d6-4606-ba42-a1c2de2aa4f7"
SUBJECT_CODES = ["YW", "SW", "DL"]
NUM_STUDENTS = 50

engine = create_async_engine(str(settings.DATABASE_URL))
Session = async_sessionmaker(engine)


async def get_students(db) -> list[str]:
    """获取三科都有答卷的前50名学生。"""
    r = await db.execute(text(
        'SELECT sa.student_id, COUNT(DISTINCT s.code) as sc '
        'FROM student_answers sa '
        'JOIN questions q ON sa.question_id = q.id '
        'JOIN subjects s ON q.subject_id = s.id '
        "WHERE s.exam_id = :eid AND s.code IN ('YW','SW','DL') "
        "AND q.question_type != 'choice' "
        'GROUP BY sa.student_id HAVING sc = 3 '
        'ORDER BY sa.student_id LIMIT :lim'
    ), {"eid": EXAM_ID, "lim": NUM_STUDENTS})
    return [row[0] for row in r.fetchall()]


async def get_questions(db) -> list[dict]:
    """获取三科全部主观题。"""
    r = await db.execute(text(
        'SELECT q.id, q.name, q.max_score, q.question_type, s.code, s.name as subj_name, s.id as subject_id '
        'FROM questions q JOIN subjects s ON q.subject_id = s.id '
        "WHERE s.exam_id = :eid AND s.code IN ('YW','SW','DL') "
        "AND q.question_type != 'choice' "
        'ORDER BY s.code, CAST(q.name AS INTEGER)'
    ), {"eid": EXAM_ID})
    return [dict(zip(["id", "name", "max_score", "question_type", "subject_code", "subject_name", "subject_id"], row))
            for row in r.fetchall()]


async def get_rubrics(db, question_ids: list[str]) -> dict:
    """获取评分细则（按 question_id 索引）。"""
    placeholders = ",".join([f":q{i}" for i in range(len(question_ids))])
    params = {f"q{i}": qid for i, qid in enumerate(question_ids)}
    r = await db.execute(text(
        f'SELECT question_id, criteria FROM rubrics WHERE question_id IN ({placeholders})'
    ), params)
    result = {}
    for row in r.fetchall():
        result[row[0]] = json.loads(row[1])
    return result


async def get_answers(db, students: list[str], question_ids: list[str]) -> list[dict]:
    """获取学生答卷（含图片路径）。"""
    stu_ph = ",".join([f":s{i}" for i in range(len(students))])
    q_ph = ",".join([f":q{i}" for i in range(len(question_ids))])
    params = {}
    params.update({f"s{i}": s for i, s in enumerate(students)})
    params.update({f"q{i}": q for i, q in enumerate(question_ids)})
    r = await db.execute(text(
        f'SELECT sa.id, sa.student_id, sa.question_id, sa.image_path, sa.score '
        f'FROM student_answers sa '
        f'WHERE sa.student_id IN ({stu_ph}) AND sa.question_id IN ({q_ph}) '
        f'ORDER BY sa.student_id, sa.question_id'
    ), params)
    return [dict(zip(["id", "student_id", "question_id", "image_path", "manual_score"], row))
            for row in r.fetchall()]


async def get_old_ai_scores(db, answer_ids: list[str]) -> dict:
    """获取旧AI评分结果。"""
    if not answer_ids:
        return {}
    ph = ",".join([f":a{i}" for i in range(len(answer_ids))])
    params = {f"a{i}": aid for i, aid in enumerate(answer_ids)}
    r = await db.execute(text(
        f'SELECT answer_id, ai_score FROM grading_results WHERE answer_id IN ({ph})'
    ), params)
    return {row[0]: row[1] for row in r.fetchall()}


async def regenerate_rubric(llm: GeminiClient, db, question: dict) -> list[dict]:
    """用新提示词为一道题重新生成评分细则。"""
    from edu_cloud.modules.grading.prompts import get_prompt as _get_prompt

    subject_code = question["subject_code"]
    rubric_prompt_tpl = _get_prompt(subject_code, "RUBRIC_GENERATION", "senior")

    if not rubric_prompt_tpl:
        logger.warning("No RUBRIC_GENERATION prompt for %s, skipping", subject_code)
        return []

    # 获取题目内容和图片
    r = await db.execute(text(
        'SELECT content, reference_answer, content_images, reference_answer_images '
        'FROM questions WHERE id = :qid'
    ), {"qid": question["id"]})
    row = r.fetchone()
    if not row:
        return []

    content, ref_answer, content_images_json, ref_images_json = row
    content_images = json.loads(content_images_json) if content_images_json else []
    ref_images = json.loads(ref_images_json) if ref_images_json else []

    # 构建prompt参数
    image_desc = ""
    question_section = f"【题目原文】\n{content or '(见图片)'}"
    answer_section = f"【参考答案】\n{ref_answer or '(见图片)'}"

    prompt_text = render_prompt(rubric_prompt_tpl, {
        "imageDescription": image_desc,
        "questionSection": question_section,
        "answerSection": answer_section,
        "fullScore": str(question["max_score"]),
    })

    # 收集图片
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    parts = []
    for img_path in content_images + ref_images:
        if img_path.startswith("/uploads/"):
            local = upload_root / img_path.split("/uploads/", 1)[1]
        else:
            local = upload_root / img_path
        if local.exists():
            parts.append(_make_image_part(local.read_bytes()))

    parts.append(types.Part.from_text(text=prompt_text))
    contents = [types.Content(role="user", parts=parts)]

    # 调用 LLM
    raw = await llm._generate(contents, method="rubric_gen", max_tokens=16384)
    parsed = extract_json(raw)
    if parsed and isinstance(parsed, dict) and "rubricItems" in parsed:
        return parsed["rubricItems"]
    elif parsed and isinstance(parsed, list):
        return parsed
    logger.error("Failed to parse rubric for %s Q%s: %s", subject_code, question["name"], raw[:200])
    return []


async def run_ocr_batch(llm: GeminiClient, answers: list[dict], rubrics: dict, questions_map: dict) -> dict:
    """批量 OCR（Batch API）。返回 {answer_id: ocr_text}。"""
    requests = []
    answer_order = []

    for ans in answers:
        qid = ans["question_id"]
        criteria = rubrics.get(qid, [])
        q = questions_map[qid]
        subject_code = q["subject_code"]

        # 构建 OCR prompt
        ocr_prompt = get_prompt(subject_code, "OCR_STRUCTURED", "senior") or get_prompt(subject_code, "OCR", "senior")
        if ocr_prompt:
            structure = "\n".join(f"- {c.get('blankNo', '?')}: {c.get('subQ', '')}" for c in criteria)
            ocr_prompt = render_prompt(ocr_prompt, {"rubricStructure": structure})
        else:
            ocr_prompt = OCR_STRUCTURED_PROMPT_BASE
            structure = "\n".join(f"- {c.get('blankNo', '?')}: {c.get('subQ', '')}" for c in criteria)
            ocr_prompt = render_prompt(ocr_prompt, {"rubricStructure": structure})

        # 读图片
        img_path = ans["image_path"]
        upload_root = Path(settings.UPLOAD_DIR).resolve()
        if img_path.startswith("/uploads/"):
            local = upload_root / img_path.split("/uploads/", 1)[1]
        else:
            local = Path(img_path)

        if not local.exists():
            logger.warning("Image not found: %s", local)
            continue

        image_bytes = local.read_bytes()
        if len(image_bytes) < 5000:
            # 空白卷
            answer_order.append((ans["id"], "BLANK"))
            continue

        image_part = _make_image_part(image_bytes)
        parts = [image_part, types.Part.from_text(text=ocr_prompt)]
        contents = [types.Content(role="user", parts=parts)]

        requests.append({"contents": contents, "max_tokens": 4096})
        answer_order.append((ans["id"], len(requests) - 1))

    if not requests:
        return {}

    logger.info("OCR Batch: submitting %d requests...", len(requests))
    job_name = await llm.create_batch_job(requests)
    logger.info("OCR Batch job: %s, polling...", job_name)
    results = await llm.poll_batch_job(job_name, poll_interval=5, timeout=1200)
    logger.info("OCR Batch complete: %d results", len(results))

    # 解析结果
    ocr_results = {}
    batch_idx = 0
    for answer_id, idx_or_flag in answer_order:
        if idx_or_flag == "BLANK":
            ocr_results[answer_id] = []
            continue
        resp = results[idx_or_flag] if idx_or_flag < len(results) else None
        if resp and resp.get("text"):
            parsed = extract_json(resp["text"])
            if parsed and isinstance(parsed, dict):
                blanks = parsed.get("blanks", [])
            elif parsed and isinstance(parsed, list):
                blanks = parsed
            else:
                blanks = []
            ocr_results[answer_id] = blanks
        else:
            ocr_results[answer_id] = []

    return ocr_results


async def run_grading_batch(
    llm: GeminiClient,
    answers: list[dict],
    ocr_results: dict,
    rubrics: dict,
    questions_map: dict,
) -> dict:
    """批量评分（Batch API）。返回 {answer_id: score}。"""
    requests = []
    answer_order = []

    for ans in answers:
        answer_id = ans["id"]
        qid = ans["question_id"]
        criteria = rubrics.get(qid, [])
        q = questions_map[qid]
        subject_code = q["subject_code"]

        blanks = ocr_results.get(answer_id, [])
        if not blanks:
            answer_order.append((answer_id, "BLANK"))
            continue

        # 构建评分 prompt
        grading_prompt_tpl = get_prompt(subject_code, "GRADING_TEXT", "senior")
        if not grading_prompt_tpl:
            answer_order.append((answer_id, "NO_PROMPT"))
            continue

        rubric_text = format_rubric_for_grading(criteria)
        blanks = validate_ocr_blanks(blanks)
        blanks = recover_truncated_blanks(blanks, len(criteria))
        extracted_text = "\n".join(f"{b.get('blankNo', '?')}: {b.get('text', '')}" for b in blanks)

        char_stats = ""
        if q.get("question_type") == "essay":
            raw_text = "".join(b.get("text", "") for b in blanks)
            _, char_stats = count_essay_chars(raw_text)

        prompt = render_prompt(grading_prompt_tpl, {
            "fullScore": str(q["max_score"]),
            "rubric": rubric_text,
            "extractedText": extracted_text,
            "charStats": char_stats,
        })

        parts = [types.Part.from_text(text=prompt)]
        contents = [types.Content(role="user", parts=parts)]

        requests.append({"contents": contents, "max_tokens": 4096})
        answer_order.append((answer_id, len(requests) - 1))

    if not requests:
        return {}

    logger.info("Grading Batch: submitting %d requests...", len(requests))
    job_name = await llm.create_batch_job(requests)
    logger.info("Grading Batch job: %s, polling...", job_name)
    results = await llm.poll_batch_job(job_name, poll_interval=5, timeout=1200)
    logger.info("Grading Batch complete: %d results", len(results))

    # 解析结果
    scores = {}
    # 建立 answer_id -> question_id 映射
    aid_to_qid = {a["id"]: a["question_id"] for a in answers}
    for answer_id, idx_or_flag in answer_order:
        if idx_or_flag in ("BLANK", "NO_PROMPT"):
            scores[answer_id] = 0.0
            continue
        resp = results[idx_or_flag] if idx_or_flag < len(results) else None
        if resp and resp.get("text"):
            parsed = extract_json(resp["text"])
            if parsed and isinstance(parsed, dict):
                raw_score = parsed.get("score", 0)
                qid = aid_to_qid.get(answer_id)
                max_s = questions_map[qid]["max_score"] if qid else 100
                scores[answer_id] = min(max(float(raw_score), 0), max_s)
            else:
                scores[answer_id] = None
        else:
            scores[answer_id] = None

    return scores


async def test_single(llm: GeminiClient, answer: dict, rubrics: dict, questions_map: dict) -> dict | None:
    """测试单份答卷（验证流程正确性）。"""
    qid = answer["question_id"]
    criteria = rubrics.get(qid, [])
    q = questions_map[qid]
    subject_code = q["subject_code"]

    # 读图片
    img_path = answer["image_path"]
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    if img_path.startswith("/uploads/"):
        local = upload_root / img_path.split("/uploads/", 1)[1]
    else:
        local = Path(img_path)

    if not local.exists():
        return None

    image_bytes = local.read_bytes()
    if len(image_bytes) < 5000:
        return {"answer_id": answer["id"], "ocr": [], "score": 0.0}

    # OCR
    ocr_prompt = get_prompt(subject_code, "OCR_STRUCTURED", "senior") or get_prompt(subject_code, "OCR", "senior")
    if ocr_prompt:
        structure = "\n".join(f"- {c.get('blankNo', '?')}: {c.get('subQ', '')}" for c in criteria)
        ocr_prompt = render_prompt(ocr_prompt, {"rubricStructure": structure})
    else:
        ocr_prompt = OCR_STRUCTURED_PROMPT_BASE

    blanks = await llm.extract_text(image_bytes=image_bytes, prompt=ocr_prompt)
    blanks = validate_ocr_blanks(blanks)
    blanks = recover_truncated_blanks(blanks, len(criteria))

    extracted_text = "\n".join(f"{b.get('blankNo', '?')}: {b.get('text', '')}" for b in blanks)

    if not any(b.get("text", "").strip() for b in blanks):
        return {"answer_id": answer["id"], "ocr": blanks, "score": 0.0}

    # 评分
    grading_prompt_tpl = get_prompt(subject_code, "GRADING_TEXT", "senior")
    rubric_text = format_rubric_for_grading(criteria)

    char_stats = ""
    if q.get("question_type") == "essay":
        raw_text = "".join(b.get("text", "") for b in blanks)
        _, char_stats = count_essay_chars(raw_text)

    prompt = render_prompt(grading_prompt_tpl, {
        "fullScore": str(q["max_score"]),
        "rubric": rubric_text,
        "extractedText": extracted_text,
        "charStats": char_stats,
    })

    grade_result = await llm.grade_text(prompt, q["max_score"])
    return {
        "answer_id": answer["id"],
        "ocr": blanks,
        "score": grade_result.score,
        "details": grade_result.details,
    }


async def main():
    logger.info("=" * 60)
    logger.info("批量重新评分测试 — 语文/生物/地理 × 50学生")
    logger.info("=" * 60)

    llm = GeminiClient(
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL or "gemini-2.5-flash",
        max_retries=3,
    )

    async with Session() as db:
        # Step 1: 获取数据
        logger.info("Step 1: 获取学生和题目数据...")
        students = await get_students(db)
        logger.info("  选取 %d 名学生", len(students))

        questions = await get_questions(db)
        questions_map = {q["id"]: q for q in questions}
        logger.info("  共 %d 道主观题", len(questions))

        rubrics = await get_rubrics(db, [q["id"] for q in questions])
        logger.info("  已有 %d 份评分细则", len(rubrics))

        # Step 2: 重新生成语文/生物细则
        logger.info("\nStep 2: 重新生成语文/生物评分细则...")
        for q in questions:
            if q["subject_code"] in ("YW", "SW"):
                # 检查是否已手动设定（manual source 的不覆盖）
                r = await db.execute(text(
                    'SELECT source FROM rubrics WHERE question_id = :qid'
                ), {"qid": q["id"]})
                row = r.fetchone()
                if row and row[0] == "manual":
                    logger.info("  跳过 %s Q%s（手动细则）", q["subject_name"], q["name"])
                    continue

                logger.info("  生成 %s Q%s 细则...", q["subject_name"], q["name"])
                new_criteria = await regenerate_rubric(llm, db, q)
                if new_criteria:
                    rubrics[q["id"]] = new_criteria
                    # 保存到数据库
                    criteria_json = json.dumps(new_criteria, ensure_ascii=False)
                    await db.execute(text(
                        'UPDATE rubrics SET criteria = :c, source = "ai_generated", '
                        'updated_at = CURRENT_TIMESTAMP WHERE question_id = :qid'
                    ), {"c": criteria_json, "qid": q["id"]})
                    await db.commit()
                    logger.info("    ✓ 生成 %d 个得分点", len(new_criteria))
                else:
                    logger.warning("    ✗ 生成失败，保留旧细则")

        # Step 3: 获取答卷
        logger.info("\nStep 3: 获取答卷...")
        answers = await get_answers(db, students, [q["id"] for q in questions])
        logger.info("  共 %d 份答卷", len(answers))

        # 获取旧AI分数
        old_scores = await get_old_ai_scores(db, [a["id"] for a in answers])
        logger.info("  旧AI评分: %d 份", len(old_scores))

        # Step 4: 先测试3份验证流程
        logger.info("\nStep 4: 测试3份答卷验证流程...")
        test_answers = [a for a in answers if a["image_path"]][:3]
        for i, ta in enumerate(test_answers):
            q = questions_map[ta["question_id"]]
            result = await test_single(llm, ta, rubrics, questions_map)
            if result:
                logger.info("  测试%d: %s Q%s | student=%s | 新AI=%.1f | 旧AI=%s | 人工=%s",
                    i+1, q["subject_name"], q["name"], ta["student_id"],
                    result["score"],
                    old_scores.get(ta["id"], "N/A"),
                    ta["manual_score"] if ta["manual_score"] is not None else "N/A")
            else:
                logger.warning("  测试%d: 失败（图片不存在）", i+1)

        # Step 5: 批量 OCR（Batch API 经济模式）
        logger.info("\nStep 5: 批量 OCR（经济模式）...")
        valid_answers = [a for a in answers if a["image_path"]]

        # 分批处理（每批最多100份，Batch API 限制）
        BATCH_SIZE = 100
        all_ocr_results = {}
        for i in range(0, len(valid_answers), BATCH_SIZE):
            batch = valid_answers[i:i+BATCH_SIZE]
            logger.info("  OCR 批次 %d/%d (%d份)...",
                i//BATCH_SIZE + 1, (len(valid_answers)-1)//BATCH_SIZE + 1, len(batch))
            ocr_batch = await run_ocr_batch(llm, batch, rubrics, questions_map)
            all_ocr_results.update(ocr_batch)

        logger.info("  OCR 完成: %d 份", len(all_ocr_results))

        # Step 6: 批量评分（Batch API 经济模式）
        logger.info("\nStep 6: 批量评分（经济模式）...")
        all_scores = {}
        for i in range(0, len(valid_answers), BATCH_SIZE):
            batch = valid_answers[i:i+BATCH_SIZE]
            logger.info("  评分批次 %d/%d (%d份)...",
                i//BATCH_SIZE + 1, (len(valid_answers)-1)//BATCH_SIZE + 1, len(batch))
            scores_batch = await run_grading_batch(llm, batch, all_ocr_results, rubrics, questions_map)
            all_scores.update(scores_batch)

        logger.info("  评分完成: %d 份", len(all_scores))

        # Step 7: 输出结果对比
        logger.info("\n" + "=" * 80)
        logger.info("结果对比")
        logger.info("=" * 80)

        # 按科目统计
        by_subject = {}
        for ans in valid_answers:
            q = questions_map[ans["question_id"]]
            code = q["subject_code"]
            if code not in by_subject:
                by_subject[code] = {"name": q["subject_name"], "diffs_old": [], "diffs_new": [], "details": []}

            new_score = all_scores.get(ans["id"])
            old_score = old_scores.get(ans["id"])
            manual = ans["manual_score"]

            if new_score is not None and manual is not None:
                by_subject[code]["diffs_new"].append(abs(float(new_score) - float(manual)))
            if old_score is not None and manual is not None:
                by_subject[code]["diffs_old"].append(abs(float(old_score) - float(manual)))

            by_subject[code]["details"].append({
                "student": ans["student_id"],
                "question": q["name"],
                "new_ai": new_score,
                "old_ai": old_score,
                "manual": manual,
            })

        # 输出汇总
        print("\n" + "=" * 80)
        print(f"{'科目':<6} {'学生数':<8} {'答卷':<8} {'有标注':<8} {'旧MAE':<10} {'新MAE':<10} {'改善':<8}")
        print("=" * 80)

        total_old_diffs = []
        total_new_diffs = []

        for code in SUBJECT_CODES:
            if code not in by_subject:
                continue
            info = by_subject[code]
            n_answers = len(info["details"])
            n_annotated_old = len(info["diffs_old"])
            n_annotated_new = len(info["diffs_new"])

            mae_old = sum(info["diffs_old"]) / len(info["diffs_old"]) if info["diffs_old"] else 0
            mae_new = sum(info["diffs_new"]) / len(info["diffs_new"]) if info["diffs_new"] else 0

            improve = f"{(1 - mae_new/mae_old)*100:.0f}%" if mae_old > 0 else "N/A"

            total_old_diffs.extend(info["diffs_old"])
            total_new_diffs.extend(info["diffs_new"])

            print(f"{info['name']:<6} {NUM_STUDENTS:<8} {n_answers:<8} {n_annotated_new:<8} "
                  f"{mae_old:<10.2f} {mae_new:<10.2f} {improve:<8}")

        print("-" * 80)
        total_mae_old = sum(total_old_diffs) / len(total_old_diffs) if total_old_diffs else 0
        total_mae_new = sum(total_new_diffs) / len(total_new_diffs) if total_new_diffs else 0
        total_improve = f"{(1 - total_mae_new/total_mae_old)*100:.0f}%" if total_mae_old > 0 else "N/A"
        print(f"{'总计':<6} {NUM_STUDENTS:<8} {len(valid_answers):<8} {len(total_new_diffs):<8} "
              f"{total_mae_old:<10.2f} {total_mae_new:<10.2f} {total_improve:<8}")

        # 输出详细对比（有标注的）
        print("\n\n=== 详细对比（有人工标注） ===")
        print(f"{'科目':<4} {'题号':<6} {'学生':<10} {'旧AI':<8} {'新AI':<8} {'人工':<8} {'旧差':<8} {'新差':<8} {'改善':<4}")
        print("-" * 70)

        for code in SUBJECT_CODES:
            if code not in by_subject:
                continue
            for d in by_subject[code]["details"]:
                if d["manual"] is None or d["new_ai"] is None:
                    continue
                old_diff = abs(float(d["old_ai"]) - float(d["manual"])) if d["old_ai"] is not None else None
                new_diff = abs(float(d["new_ai"]) - float(d["manual"]))

                if old_diff is not None:
                    if new_diff < old_diff:
                        flag = "✓"
                    elif new_diff > old_diff:
                        flag = "✗"
                    else:
                        flag = "="
                    old_str = f"{old_diff:+.1f}"
                else:
                    flag = "?"
                    old_str = "N/A"

                print(f"{by_subject[code]['name']:<4} {d['question']:<6} {d['student']:<10} "
                      f"{d['old_ai'] or 'N/A':<8} {d['new_ai']:<8.1f} {d['manual']:<8} "
                      f"{old_str:<8} {new_diff:+.1f}{'':<4} {flag}")

        # 保存完整结果到文件
        output = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config": {
                "exam_id": EXAM_ID,
                "num_students": NUM_STUDENTS,
                "subjects": SUBJECT_CODES,
                "model": llm.model,
            },
            "summary": {
                "total_answers": len(valid_answers),
                "total_annotated": len(total_new_diffs),
                "mae_old": total_mae_old,
                "mae_new": total_mae_new,
                "improvement": total_improve,
            },
            "by_subject": {
                code: {
                    "name": info["name"],
                    "mae_old": sum(info["diffs_old"]) / len(info["diffs_old"]) if info["diffs_old"] else 0,
                    "mae_new": sum(info["diffs_new"]) / len(info["diffs_new"]) if info["diffs_new"] else 0,
                }
                for code, info in by_subject.items()
            },
            "details": [
                d for code in SUBJECT_CODES if code in by_subject
                for d in by_subject[code]["details"]
            ],
        }

        output_path = Path(__file__).parent.parent / "data" / "regrade_results.json"
        output_path.parent.mkdir(exist_ok=True)
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
        logger.info("\n结果已保存: %s", output_path)


if __name__ == "__main__":
    asyncio.run(main())
