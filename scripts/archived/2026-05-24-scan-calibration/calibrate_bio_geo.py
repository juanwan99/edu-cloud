#!/usr/bin/env python3
"""生物/地理选择题+条形码校准 — 轮廓检测 + 暗度仲裁 + 偏移补偿。

生物/地理答题卡: 5组×5行×4列 标准网格，模板已有 rows=5, cols=4。
扫描源: uploads/scan-input/796f7c26.../生物(地理)/XXXXA.jpg
"""
import json
import sqlite3
import sys
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from edu_cloud.modules.scan.vision.barcode import read_barcode
from edu_cloud.modules.scan.vision.fillmark import recognize_choice_group

DB = Path(__file__).resolve().parent.parent / "edu_cloud.db"
EXAM_ID = "796f7c26-77d6-4606-ba42-a1c2de2aa4f7"
SCHOOL_ID = "66d695f2-b9a6-4557-9f72-665c5c9f5e97"
SCAN_BASE = Path(__file__).resolve().parent.parent / "uploads/scan-input" / EXAM_ID

SUBJECTS = {
    "生物": {
        "subj_id": "72679087-436f-4da5-ae3b-ae80329403fc",
        "scan_dir": SCAN_BASE / "生物",
    },
    "地理": {
        "subj_id": "329f7ffa-2e21-4715-ac3f-d5c605d10877",
        "scan_dir": SCAN_BASE / "地理",
    },
}


def load_template(conn, subj_id):
    c = conn.cursor()
    c.execute("SELECT image_width, image_height, regions FROM templates WHERE subject_id = ? AND side = 'A'", (subj_id,))
    rows = c.fetchall()
    for r in rows:
        regions = json.loads(r[2]) if r[2] else []
        barcode = [reg for reg in regions if reg.get("type") == "barcode"]
        choices = [reg for reg in regions if reg.get("type") == "choice_group"]
        if choices:
            return {
                "tpl_w": r[0], "tpl_h": r[1],
                "barcode": barcode[0]["rect"] if barcode else None,
                "choices": choices,
            }
    return None


def load_db_answers(conn, subj_id):
    """返回 {student_id: [answer_ordered_by_qid]}。student_id 可能是6位条码号。"""
    c = conn.cursor()
    c.execute("""
        SELECT student_id, question_id, detected_answer
        FROM student_answers
        WHERE subject_id = ? AND question_type = 'choice'
          AND detected_answer IS NOT NULL AND detected_answer != ''
        ORDER BY student_id, question_id
    """, (subj_id,))
    result = defaultdict(list)
    for sid, qid, ans in c.fetchall():
        result[sid].append(ans)
    return dict(result)


def detect_choices_contour(img_path, tpl):
    """轮廓检测法：每组裁切 → 找填涂块 → 按相对位置映射 ABCD。"""
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    img_h, img_w = img.shape[:2]
    sx = img_w / tpl["tpl_w"]
    sy = img_h / tpl["tpl_h"]

    all_answers = []
    for group in sorted(tpl["choices"], key=lambda g: g.get("id", "")):
        rect = group["rect"]
        rows = group.get("rows", 5)
        x1 = int(rect["x1"] * sx); y1 = int(rect["y1"] * sy)
        x2 = int(rect["x2"] * sx); y2 = int(rect["y2"] * sy)
        crop = img[y1:y2, x1:x2]
        ch, cw = crop.shape
        row_h = ch / rows

        _, binary = cv2.threshold(crop, 80, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        marks = []
        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            area = cv2.contourArea(cnt)
            if 6 < bw < 55 and 6 < bh < 45 and area > 40:
                marks.append({"cx": bx + bw // 2, "cy": by + bh // 2, "area": area})

        row_answers = [""] * rows
        for ri in range(rows):
            ry_min = ri * row_h
            ry_max = (ri + 1) * row_h
            row_marks = [m for m in marks if ry_min <= m["cy"] < ry_max]
            if not row_marks:
                continue
            if len(row_marks) == 1:
                m = row_marks[0]
            else:
                best_m = None; best_dark = -1
                for m in row_marks:
                    bx1 = max(0, m["cx"] - 15); bx2 = min(cw, m["cx"] + 15)
                    by1 = max(0, m["cy"] - 12); by2 = min(ch, m["cy"] + 12)
                    box = crop[by1:by2, bx1:bx2]
                    dark = 255 - np.mean(box) if box.size > 0 else 0
                    if dark > best_dark:
                        best_dark = dark; best_m = m
                m = best_m
            skip_ratio = 0.18
            opt_area = cw * (1 - skip_ratio)
            rel_x = m["cx"] - cw * skip_ratio
            if rel_x < 0:
                continue
            opt_idx = min(3, int(rel_x / opt_area * 4))
            row_answers[ri] = "ABCD"[opt_idx]

        all_answers.extend(row_answers)
    return all_answers


def detect_barcode(img_path, tpl):
    if not tpl.get("barcode"):
        return None
    return read_barcode(
        img_path,
        crop_region=tpl["barcode"],
        template_size={"width": tpl["tpl_w"], "height": tpl["tpl_h"]},
    )


def run_subject(name, conf, conn):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    tpl = load_template(conn, conf["subj_id"])
    if not tpl:
        print(f"  模板未找到！")
        return

    print(f"  模板: {tpl['tpl_w']}x{tpl['tpl_h']}, {len(tpl['choices'])} 组选择题")
    total_q = sum(g.get("rows", 5) for g in tpl["choices"])
    print(f"  预期题数: {total_q}")

    scan_dir = conf["scan_dir"]
    a_files = sorted([f for f in scan_dir.iterdir() if f.name.endswith("A.jpg")])
    print(f"  扫描A面: {len(a_files)} 张")

    db_answers = load_db_answers(conn, conf["subj_id"])
    print(f"  DB有选择题: {len(db_answers)} 学生")

    # 条形码校准
    bc_total = bc_ok = bc_fail = 0
    barcode_map = {}
    for f in a_files:
        bc_total += 1
        result = detect_barcode(f, tpl)
        if result is None:
            bc_fail += 1
        else:
            barcode_map[f.stem.rstrip("A")] = result
            bc_ok += 1

    print(f"\n  [条形码] 识别={bc_ok}/{bc_total} ({bc_ok/bc_total*100:.1f}%)")
    if bc_ok > 0:
        samples = list(barcode_map.items())[:3]
        print(f"  样本: {samples}")

    # 选择题校准
    match_q = total_compared = 0
    perfect = 0
    n_students = 0
    per_q = defaultdict(lambda: [0, 0])
    mismatches = []

    for f in a_files:
        file_id = f.stem.rstrip("A")
        detected = detect_choices_contour(f, tpl)
        if detected is None:
            continue

        barcode = barcode_map.get(file_id)
        snum = barcode if barcode and barcode in db_answers else None
        if snum is None:
            continue

        db_ans = db_answers[snum]
        if len(db_ans) != len(detected):
            continue

        n_students += 1
        student_ok = True
        for i in range(len(detected)):
            db_a = db_ans[i] if i < len(db_ans) else ""
            det_a = detected[i]
            if not db_a:
                continue
            total_compared += 1
            per_q[i][1] += 1
            if db_a == det_a:
                match_q += 1
                per_q[i][0] += 1
            else:
                student_ok = False
                if len(mismatches) < 20:
                    mismatches.append(f"    {snum} Q{i+1}: DB={db_a} DET={det_a}")
        if student_ok:
            perfect += 1

    print(f"\n  [选择题一致性]")
    print(f"    对比学生: {n_students}")
    if total_compared > 0:
        print(f"    逐题一致: {match_q}/{total_compared} ({match_q/total_compared*100:.2f}%)")
        print(f"    全题一致: {perfect}/{n_students} ({perfect/n_students*100:.1f}%)")
    print(f"\n    各题:")
    for i in sorted(per_q.keys()):
        m, t = per_q[i]
        pct = m / t * 100 if t > 0 else 0
        print(f"      Q{i+1:2d}: {m:4d}/{t:4d} ({pct:5.1f}%)")
    if mismatches:
        print(f"\n    不一致样本 (前20):")
        for m in mismatches:
            print(m)


def main():
    conn = sqlite3.connect(str(DB))
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["生物", "地理"]
    for name in targets:
        if name in SUBJECTS:
            run_subject(name, SUBJECTS[name], conn)
    conn.close()


if __name__ == "__main__":
    main()
