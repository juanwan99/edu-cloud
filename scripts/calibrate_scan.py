#!/usr/bin/env python3
"""扫描识别校准 v5 — 轮廓检测 + 偏移补偿 + 暗度仲裁。"""
import sqlite3
import sys
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from edu_cloud.modules.scan.vision.barcode import read_barcode

DB = Path(__file__).resolve().parent.parent / "edu_cloud.db"
SCANS_DIR = Path(__file__).resolve().parent.parent / "storage/66d695f2-b9a6-4557-9f72-665c5c9f5e97/796f7c26-77d6-4606-ba42-a1c2de2aa4f7/scans/yuwen"
SUBJ_ID = "be86745a-67e4-4077-9132-409599350b54"

TPL_SIZE = {"width": 2481, "height": 1754}
BARCODE_REGION = {"x1": 720, "y1": 252, "x2": 1102, "y2": 421}
CHOICE_REGION = {"x1": 94, "y1": 560, "x2": 1162, "y2": 681}
QUESTION_LAYOUT = [[1, 2, 3], [5, 7, 8], [11, 14, 16], [17, 20]]
LABELS = ["A", "B", "C", "D"]

QID_TO_QNO = {
    "3b257ffd-1a1c-472e-a9f5-1d168e6baec9": 1,
    "7d0254b5-df22-4faf-aad2-f19717352290": 2,
    "98568afe-6de4-41f2-8dee-c85f05b82e6d": 3,
    "6bf229cc-5598-4166-b3dd-be8087917d82": 5,
    "5732a5c3-0543-40d4-99d5-4daf5f2ef5f1": 7,
    "a99e6fc7-722d-4b53-ac75-cb8704172bb7": 8,
    "952059be-2504-4dcc-b588-5dbfa3dcd8ef": 11,
    "beaddfa2-ddac-4185-bd58-bb249839bd8f": 14,
    "6458dcbd-c914-4321-9ec1-a792b2a64a0c": 16,
    "bf26d2dc-a514-457c-bc59-189cd82f7a79": 17,
    "4c459717-503d-44dd-aeb1-725de08d252a": 20,
}

BASE_X = 63 / 1420
GROUP_SP = 275 / 1420
OPT_SP = 50 / 1420
BOX_HW, BOX_HH = 18, 14


def _opt_cx(cw, g, o):
    return cw * (BASE_X + g * GROUP_SP + o * OPT_SP)


def _find_marks(crop):
    _, binary = cv2.threshold(crop, 80, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    marks = []
    for cnt in contours:
        bx, by, bw, bh = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)
        if 15 < bw < 60 and 12 < bh < 50 and area > 200:
            marks.append({"cx": bx + bw // 2, "cy": by + bh // 2, "area": area})
    return marks


def _detect_offset(marks, cw):
    """检测系统性偏移：如果正负偏移各占约一半，说明有半格漂移。"""
    if len(marks) < 3:
        return 0.0
    offsets = []
    for m in marks:
        best_abs, best_off = 999, 0
        for g in range(4):
            for o in range(4):
                off = m["cx"] - _opt_cx(cw, g, o)
                if abs(off) < best_abs:
                    best_abs, best_off = abs(off), off
        offsets.append(best_off)
    pos = [o for o in offsets if o > 10]
    neg = [o for o in offsets if o < -10]
    if pos and neg and len(pos) + len(neg) >= len(offsets) * 0.6:
        return np.mean(pos)
    return 0.0


def _darkness_pick(crop, cw, ch, gi, ri, shift=0.0):
    """用暗度测量选出最佳选项。"""
    row_cy = int((ri + 0.5) * ch / 3)
    best_opt, best_score = None, -1
    for o in range(4):
        ecx = int(_opt_cx(cw, gi, o) + shift)
        bx1 = max(0, ecx - BOX_HW)
        bx2 = min(cw, ecx + BOX_HW)
        by1 = max(0, row_cy - BOX_HH)
        by2 = min(ch, row_cy + BOX_HH)
        box = crop[by1:by2, bx1:bx2]
        if box.size == 0:
            continue
        score = 255 - np.mean(box)
        if score > best_score:
            best_score = score
            best_opt = o
    if best_opt is not None and best_score > 20:
        return LABELS[best_opt]
    return None


def detect_choices(page1_path):
    img = cv2.imread(str(page1_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    img_h, img_w = img.shape[:2]
    sx = img_w / TPL_SIZE["width"]
    sy = img_h / TPL_SIZE["height"]
    x1 = int(CHOICE_REGION["x1"] * sx)
    y1 = int(CHOICE_REGION["y1"] * sy)
    x2 = int(CHOICE_REGION["x2"] * sx)
    y2 = int(CHOICE_REGION["y2"] * sy)
    crop = img[y1:y2, x1:x2]
    ch, cw = crop.shape
    row_h = ch / 3

    marks = _find_marks(crop)
    shift = _detect_offset(marks, cw)

    # Phase 1: 轮廓映射
    slot = {}  # (gi, ri) → [(option_idx, mark)]
    for m in marks:
        ri = min(int(m["cy"] / row_h), 2)
        best_d, best_g, best_o = float("inf"), 0, 0
        for g in range(4):
            for o in range(4):
                d = abs(m["cx"] - _opt_cx(cw, g, o) - shift)
                if d < best_d:
                    best_d, best_g, best_o = d, g, o
        if best_d > cw * OPT_SP * 0.7:
            continue
        key = (best_g, ri)
        if key not in slot:
            slot[key] = []
        slot[key].append((best_o, m))

    results = {}
    for gi, q_list in enumerate(QUESTION_LAYOUT):
        for ri, qno in enumerate(q_list):
            key = (gi, ri)
            entries = slot.get(key, [])
            if len(entries) == 1:
                results[qno] = LABELS[entries[0][0]]
            elif len(entries) > 1:
                # 多 mark 冲突 → 暗度仲裁
                ans = _darkness_pick(crop, cw, ch, gi, ri, shift)
                if ans:
                    results[qno] = ans
            else:
                # 无 mark → 尝试暗度兜底
                ans = _darkness_pick(crop, cw, ch, gi, ri, shift)
                if ans:
                    results[qno] = ans

    return results


def load_db_answers(conn):
    c = conn.cursor()
    c.execute("""
        SELECT s.student_number, sa.question_id, sa.detected_answer
        FROM student_answers sa
        JOIN students s ON sa.student_id = s.id
        WHERE sa.subject_id = ? AND sa.question_type = 'choice'
          AND sa.detected_answer IS NOT NULL AND sa.detected_answer != ''
    """, (SUBJ_ID,))
    result = defaultdict(dict)
    for snum, qid, ans in c.fetchall():
        qno = QID_TO_QNO.get(qid)
        if qno is not None:
            result[snum][qno] = ans
    return dict(result)


def main():
    conn = sqlite3.connect(str(DB))
    db_answers = load_db_answers(conn)
    student_dirs = sorted([d for d in SCANS_DIR.iterdir() if d.is_dir()])

    print(f"学生总数: {len(student_dirs)}")
    print("=" * 70)

    # 条形码
    bc_total = bc_ok = bc_fail = 0
    for d in student_dirs:
        page1 = d / "page1.jpg"
        if not page1.exists():
            continue
        bc_total += 1
        r = read_barcode(page1, crop_region=BARCODE_REGION, template_size=TPL_SIZE)
        if r is None:
            bc_fail += 1
        elif r == "25" + d.name[-4:]:
            bc_ok += 1
    print(f"[条形码] 识别={bc_total - bc_fail}/{bc_total} 匹配={bc_ok}/{bc_total - bc_fail}")

    # 选择题
    total_q = match_q = perfect = 0
    per_q = {q: [0, 0] for q in [1, 2, 3, 5, 7, 8, 11, 14, 16, 17, 20]}
    mismatches = []

    for d in student_dirs:
        page1 = d / "page1.jpg"
        snum = d.name
        if not page1.exists() or snum not in db_answers:
            continue
        detected = detect_choices(page1)
        if detected is None:
            continue
        db = db_answers[snum]
        student_ok = True
        for qno in sorted(set(list(db.keys()) + list(detected.keys()))):
            db_a = db.get(qno, "")
            det_a = detected.get(qno, "")
            if not db_a and not det_a:
                continue
            if not db_a or not det_a:
                student_ok = False
                continue
            total_q += 1
            per_q[qno][1] += 1
            if db_a == det_a:
                match_q += 1
                per_q[qno][0] += 1
            else:
                student_ok = False
                mismatches.append(f"  {snum} Q{qno:2d}: DB={db_a} DET={det_a}")
        if student_ok:
            perfect += 1

    n_stu = len([d for d in student_dirs if d.name in db_answers])
    print(f"\n[选择题一致性]")
    print(f"  逐题一致: {match_q}/{total_q} ({match_q/total_q*100:.3f}%)")
    print(f"  不一致数: {total_q - match_q}")
    print(f"  全题一致: {perfect}/{n_stu} ({perfect/n_stu*100:.1f}%)")
    print(f"\n  各题:")
    for qno in [1, 2, 3, 5, 7, 8, 11, 14, 16, 17, 20]:
        m, t = per_q[qno]
        pct = m / t * 100 if t > 0 else 0
        print(f"    Q{qno:2d}: {m}/{t} ({pct:.1f}%)")
    if mismatches:
        print(f"\n  剩余不一致 ({len(mismatches)}):")
        for m in mismatches:
            print(m)

    conn.close()


if __name__ == "__main__":
    main()
