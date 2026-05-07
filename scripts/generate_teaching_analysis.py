#!/usr/bin/env python3
"""Generate teaching analysis for AI grading report.

Runs LLM analysis on each question using rubric + answer stats,
then generates subject summaries and principal conclusions.
Results are merged into ai-grading-full-data.json.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from edu_cloud.modules.analytics.prompts.question_analysis import (
    build_principal_summary_prompt,
    build_question_analysis_prompt,
    build_subject_summary_prompt,
)

DB_PATH = ROOT / "edu_cloud.db"
EXAM_ID = "796f7c26-77d6-4606-ba42-a1c2de2aa4f7"
DATA_PATH = ROOT / "docs" / "ai-grading-full-data.json"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"


def main() -> None:
    full_data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        rubrics = load_rubrics(conn)
        references = load_references(conn)
    finally:
        conn.close()

    p2 = full_data.get("panel2_answer", {})
    by_question = p2.get("byQuestion", {})

    question_analyses: dict[str, dict[str, Any]] = {}
    by_subject_analyses: dict[str, list[dict[str, Any]]] = {}

    for key, qdata in by_question.items():
        subject = qdata["subject"]
        qno = qdata["qno"]
        print(f"Analyzing {subject} Q{qno}...", end=" ", flush=True)

        rubric_items = rubrics.get((subject, qno), [])
        ref_answer = references.get((subject, qno), "")

        prompt = build_question_analysis_prompt(
            subject=subject,
            question_no=qno,
            max_score=qdata["maxScore"],
            reference_answer=ref_answer,
            rubric_items=rubric_items,
            stats=qdata,
        )

        result = call_llm(prompt)
        if result:
            question_analyses[key] = result
            by_subject_analyses.setdefault(subject, []).append(
                {**result, "questionNo": qno, "maxScore": qdata["maxScore"]}
            )
            actions_count = len(result.get("prioritizedActions") or [])
            print(f"OK ({actions_count} actions)")
        else:
            print("FAILED")

    subject_summaries: dict[str, dict[str, Any]] = {}
    for subject, analyses in by_subject_analyses.items():
        print(f"Summarizing {subject}...", end=" ", flush=True)
        prompt = build_subject_summary_prompt(
            subject=subject, question_analyses=analyses
        )
        result = call_llm(prompt)
        if result:
            result["subject"] = subject
            subject_summaries[subject] = result
            print("OK")
        else:
            print("FAILED")

    print("Generating principal conclusions...", end=" ", flush=True)
    overall_stats = p2.get("overall", {})
    prompt = build_principal_summary_prompt(
        subject_summaries=list(subject_summaries.values()),
        overall_stats=overall_stats,
    )
    principal_result = call_llm(prompt)
    if principal_result:
        print("OK")
    else:
        print("FAILED")

    full_data["teaching_analysis"] = {
        "byQuestion": question_analyses,
        "bySubject": subject_summaries,
        "principalConclusions": (
            principal_result.get("conclusions") if principal_result else []
        ),
    }

    DATA_PATH.write_text(
        json.dumps(full_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nWrote teaching analysis to {DATA_PATH}")
    print(f"  Questions analyzed: {len(question_analyses)}/18")
    print(f"  Subject summaries: {len(subject_summaries)}")
    print(
        f"  Principal conclusions: "
        f"{len(principal_result.get('conclusions', [])) if principal_result else 0}"
    )

    for target in [ROOT / "frontend" / "public", ROOT / "frontend" / "dist"]:
        if target.exists():
            import shutil

            shutil.copy2(DATA_PATH, target / DATA_PATH.name)
            print(f"  Published to {target.relative_to(ROOT)}")


def load_rubrics(
    conn: sqlite3.Connection,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT s.name as subject, q.name as qno, r.criteria
        FROM rubrics r
        JOIN questions q ON q.id = r.question_id
        JOIN subjects s ON s.id = q.subject_id
        WHERE q.subject_id IN (SELECT id FROM subjects WHERE exam_id = ?)
        """,
        (EXAM_ID,),
    ).fetchall()

    result: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        criteria = json.loads(row["criteria"]) if row["criteria"] else []
        result[(row["subject"], row["qno"])] = criteria
    return result


def load_references(
    conn: sqlite3.Connection,
) -> dict[tuple[str, str], str]:
    rows = conn.execute(
        """
        SELECT s.name as subject, q.name as qno, q.reference_answer
        FROM questions q
        JOIN subjects s ON s.id = q.subject_id
        WHERE q.subject_id IN (SELECT id FROM subjects WHERE exam_id = ?)
          AND q.reference_answer IS NOT NULL
        """,
        (EXAM_ID,),
    ).fetchall()

    return {
        (row["subject"], row["qno"]): row["reference_answer"] or ""
        for row in rows
    }


def call_llm(prompt: str, retries: int = 2) -> dict[str, Any] | None:
    for attempt in range(retries + 1):
        try:
            resp = httpx.post(
                DEEPSEEK_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                },
                timeout=60,
                proxy="http://127.0.0.1:7890",
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return parse_json_response(content)
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
                continue
            print(f"  Error: {e}")
            return None


def parse_json_response(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


if __name__ == "__main__":
    main()
