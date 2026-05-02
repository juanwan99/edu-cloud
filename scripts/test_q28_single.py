"""测试地理 Q28 评分优化效果 — 选几份偏差大的学生。"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from edu_cloud.config import settings
from edu_cloud.modules.grading.gemini_client import GeminiClient, _make_image_part
from edu_cloud.modules.grading.json_parser import extract_json
from edu_cloud.modules.grading.prompts import get_prompt, render_prompt
from edu_cloud.modules.grading.prompts.base import OCR_STRUCTURED_PROMPT_BASE
from edu_cloud.modules.grading.rubric_formatter import format_rubric_for_grading
from edu_cloud.modules.grading.ocr_validator import validate_ocr_blanks, recover_truncated_blanks
from edu_cloud.modules.grading.equivalence_guard import apply_equivalence_guard

EXAM_ID = "796f7c26-77d6-4606-ba42-a1c2de2aa4f7"
TEST_STUDENTS = ["250132", "250120", "250151", "250102", "250105"]

engine = create_async_engine(str(settings.DATABASE_URL))
Session = async_sessionmaker(engine)


async def main():
    llm = GeminiClient(
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL or "gemini-2.5-flash",
        max_retries=3,
    )

    async with Session() as db:
        # 找地理 Q28
        r = await db.execute(text(
            "SELECT q.id, q.name, q.max_score, q.question_type "
            "FROM questions q JOIN subjects s ON q.subject_id = s.id "
            "WHERE s.exam_id = :eid AND s.code = 'DL' AND q.name = '28'"
        ), {"eid": EXAM_ID})
        q_row = r.first()
        if not q_row:
            print("未找到地理 Q28")
            return
        qid, qname, max_score, qtype = q_row
        print(f"地理 Q28: id={qid}, 满分={max_score}")

        # 拿细则
        r = await db.execute(text("SELECT criteria FROM rubrics WHERE question_id = :qid"), {"qid": qid})
        criteria = json.loads(r.scalar())
        rubric_text = format_rubric_for_grading(criteria)
        print(f"\n=== 格式化后的细则 ===\n{rubric_text}\n")

        # 拿人工分
        human_scores = {}
        r = await db.execute(text(
            "SELECT sa.student_id, gr.final_score "
            "FROM grading_results gr JOIN student_answers sa ON gr.answer_id = sa.id "
            "WHERE sa.question_id = :qid"
        ), {"qid": qid})
        for row in r.fetchall():
            human_scores[row[0]] = row[1]

        # 拿学生答卷
        placeholders = ",".join(f":s{i}" for i in range(len(TEST_STUDENTS)))
        params = {"qid": qid}
        params.update({f"s{i}": s for i, s in enumerate(TEST_STUDENTS)})
        r = await db.execute(text(
            f"SELECT sa.id, sa.student_id, sa.image_path "
            f"FROM student_answers sa "
            f"WHERE sa.question_id = :qid AND sa.student_id IN ({placeholders})"
        ), params)
        answers = r.fetchall()

        results = []
        for ans_id, student_id, img_path in answers:
            upload_root = Path(settings.UPLOAD_DIR).resolve()
            if img_path.startswith("/uploads/"):
                local = upload_root / img_path.split("/uploads/", 1)[1]
            else:
                local = Path(img_path)

            if not local.exists():
                print(f"  {student_id}: 图片不存在 {local}")
                continue

            image_bytes = local.read_bytes()
            if len(image_bytes) < 5000:
                print(f"  {student_id}: 图片太小, 跳过")
                continue

            # OCR
            ocr_prompt = get_prompt("DL", "OCR_STRUCTURED", "senior") or OCR_STRUCTURED_PROMPT_BASE
            structure = "\n".join(f"- {c.get('blankNo', '?')}: {c.get('subQ', '')}" for c in criteria)
            ocr_prompt = render_prompt(ocr_prompt, {"rubricStructure": structure})

            blanks = await llm.extract_text(image_bytes=image_bytes, prompt=ocr_prompt)
            blanks = validate_ocr_blanks(blanks)
            blanks = recover_truncated_blanks(blanks, len(criteria))
            extracted_text = "\n".join(f"{b.get('blankNo', '?')}: {b.get('text', '')}" for b in blanks)

            # 评分
            grading_prompt_tpl = get_prompt("DL", "GRADING_TEXT", "senior")
            prompt = render_prompt(grading_prompt_tpl, {
                "fullScore": str(max_score),
                "rubric": rubric_text,
                "extractedText": extracted_text,
                "charStats": "",
            })

            grade_result = await llm.grade_text(prompt, max_score)
            raw_score = grade_result.score

            # 等价答案兜底
            guarded = apply_equivalence_guard(
                {"score": grade_result.score, "details": grade_result.details},
                criteria,
            )
            guarded_score = guarded["score"]

            human = human_scores.get(student_id, "?")
            print(f"\n--- {student_id} ---")
            print(f"  OCR: {extracted_text[:200]}")
            print(f"  AI原始: {raw_score}, 兜底后: {guarded_score}, 人工: {human}")
            if grade_result.details:
                for sub in grade_result.details:
                    for b in sub.get("blanks", []):
                        print(f"    空{b.get('index')}: {b.get('answer')} → {b.get('score')}/{b.get('fullScore')} ({b.get('reason')})")

            results.append({
                "student": student_id,
                "ai_raw": raw_score,
                "ai_guarded": guarded_score,
                "human": human,
                "diff_raw": raw_score - human if isinstance(human, (int, float)) else None,
                "diff_guarded": guarded_score - human if isinstance(human, (int, float)) else None,
            })

        print("\n=== 汇总 ===")
        print(f"{'学生':>8} {'AI原始':>6} {'兜底后':>6} {'人工':>6} {'原始偏差':>8} {'兜底偏差':>8}")
        for r in results:
            d1 = f"{r['diff_raw']:+.0f}" if r['diff_raw'] is not None else "?"
            d2 = f"{r['diff_guarded']:+.0f}" if r['diff_guarded'] is not None else "?"
            print(f"{r['student']:>8} {r['ai_raw']:>6.0f} {r['ai_guarded']:>6.0f} {r['human']:>6} {d1:>8} {d2:>8}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
