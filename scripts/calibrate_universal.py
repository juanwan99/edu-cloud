#!/usr/bin/env python3
"""通用 OMR 校准 — 任何科目零配置，自动发现位置 + 自动映射题号。

用法:
    .venv/bin/python scripts/calibrate_universal.py 生物
    .venv/bin/python scripts/calibrate_universal.py 地理
    .venv/bin/python scripts/calibrate_universal.py 生物 地理
    .venv/bin/python scripts/calibrate_universal.py          # 全部科目
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

DB = Path(__file__).resolve().parent.parent / "edu_cloud.db"
PROJECT = Path(__file__).resolve().parent.parent
EXAM_ID = "796f7c26-77d6-4606-ba42-a1c2de2aa4f7"
SCHOOL_ID = "66d695f2-b9a6-4557-9f72-665c5c9f5e97"

MIN_DARKNESS = 18
BLANK_THRESHOLD = 22

SUBJECTS = {
    "语文": {
        "subj_id": "be86745a-67e4-4077-9132-409599350b54",
        "scan_dir": PROJECT / "storage" / SCHOOL_ID / EXAM_ID / "scans/yuwen",
        "scan_pattern": "subdir",
    },
    "生物": {
        "subj_id": "72679087-436f-4da5-ae3b-ae80329403fc",
        "scan_dir": PROJECT / "uploads/scan-input" / EXAM_ID / "生物",
        "scan_pattern": "flat",
    },
    "地理": {
        "subj_id": "329f7ffa-2e21-4715-ac3f-d5c605d10877",
        "scan_dir": PROJECT / "uploads/scan-input" / EXAM_ID / "地理",
        "scan_pattern": "flat",
    },
}


def list_scan_files(scan_dir, pattern):
    if pattern == "subdir":
        files = []
        for d in sorted(scan_dir.iterdir()):
            if d.is_dir():
                p = d / "page1.jpg"
                if p.exists():
                    files.append(p)
        return files
    return sorted(f for f in scan_dir.iterdir() if f.name.endswith("A.jpg"))


# ── 第一层：从 DB 读模板 ──────────────────────────────────────

def load_template(conn, subj_id):
    c = conn.cursor()
    c.execute(
        "SELECT image_width, image_height, regions "
        "FROM templates WHERE subject_id = ? AND side = 'A'",
        (subj_id,),
    )
    row = c.fetchone()
    if not row:
        return None
    regions = json.loads(row[2]) if row[2] else []
    return {
        "tpl_w": row[0],
        "tpl_h": row[1],
        "barcode": next(
            (r["rect"] for r in regions if r.get("type") == "barcode"), None
        ),
        "choices": sorted(
            [r for r in regions if r.get("type") == "choice_group"],
            key=lambda r: r.get("id", ""),
        ),
    }


# ── 第二层：自动位置发现 ──────────────────────────────────────

def _cluster_1d(values, min_gap=8):
    """将一组数值按间隔聚类，返回每簇的加权中心。"""
    if not values:
        return []
    arr = sorted(values)
    clusters = [[arr[0]]]
    for v in arr[1:]:
        if v - clusters[-1][-1] <= min_gap:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [int(np.mean(c)) for c in clusters]


def _infer_rows_cols(tpl):
    choices = tpl["choices"]
    if not choices:
        return 5, 4
    g0 = choices[0]
    rows = g0.get("rows") or g0.get("row")
    cols = g0.get("cols") or g0.get("col")
    if rows and cols:
        return rows, cols
    r = g0["rect"]
    w, h = r["x2"] - r["x1"], r["y2"] - r["y1"]
    if w > h * 1.5:
        return max(1, w // 90), 4
    return max(1, h // 35), 4


def discover_grid(scan_files, tpl, n_samples=100):
    choices = tpl["choices"]
    n_rows, n_cols = _infer_rows_cols(tpl)

    all_y1 = [g["rect"]["y1"] for g in choices]
    all_y2 = [g["rect"]["y2"] for g in choices]
    all_x1 = [g["rect"]["x1"] for g in choices]
    all_x2 = [g["rect"]["x2"] for g in choices]

    full_rect = {
        "x1": min(all_x1) - 20,
        "y1": min(all_y1) - 30,
        "x2": max(all_x2) + 20,
        "y2": max(all_y2) + 30,
    }

    img0 = cv2.imread(str(scan_files[0]), cv2.IMREAD_GRAYSCALE)
    sx = img0.shape[1] / tpl["tpl_w"]
    sy = img0.shape[0] / tpl["tpl_h"]
    fr_x1 = int(full_rect["x1"] * sx)
    fr_y1 = int(full_rect["y1"] * sy)

    transposed = _is_transposed(tpl)

    if transposed:
        # 转置布局：X 方向 = 题目位置，Y 方向 = 选项 ABCD
        # n_rows 在模板里是题目数，n_cols 是选项数 (4)
        n_questions_per_group = n_rows
        n_opts = n_cols  # 4

        col_per_group_initial = []
        for g in choices:
            rect = g["rect"]
            gx1 = int(rect["x1"] * sx) - fr_x1
            gx2 = int(rect["x2"] * sx) - fr_x1
            gw = gx2 - gx1
            skip = int(gw * 0.05)
            q_w = (gw - skip) / n_questions_per_group
            cols = [gx1 + skip + int((qi + 0.5) * q_w) for qi in range(n_questions_per_group)]
            col_per_group_initial.append(cols)

        avg_y1_val = np.mean(all_y1)
        avg_y2_val = np.mean(all_y2)
        tpl_h_range = avg_y2_val - avg_y1_val
        skip_top = tpl_h_range * 0.15
        opt_range = tpl_h_range - skip_top
        initial_rows = []
        for oi in range(n_opts):
            tpl_y = avg_y1_val + skip_top + (oi + 0.5) * opt_range / n_opts
            initial_rows.append(int(tpl_y * sy) - fr_y1)
    else:
        # 标准布局：X 方向 = 选项 ABCD，Y 方向 = 题目
        col_per_group_initial = []
        for g in choices:
            rect = g["rect"]
            gx1 = int(rect["x1"] * sx) - fr_x1
            gx2 = int(rect["x2"] * sx) - fr_x1
            gw = gx2 - gx1
            skip = int(gw * 0.13)
            opt_w = (gw - skip) / n_cols
            cols = [gx1 + skip + int((oi + 0.5) * opt_w) for oi in range(n_cols)]
            col_per_group_initial.append(cols)

        avg_y1_val = np.mean(all_y1)
        avg_y2_val = np.mean(all_y2)
        tpl_h_range = avg_y2_val - avg_y1_val
        initial_rows = []
        for ri in range(n_rows):
            tpl_y = avg_y1_val + (ri + 0.5) * tpl_h_range / n_rows
            scan_y = int(tpl_y * sy) - fr_y1
            initial_rows.append(scan_y)

    # ── 轮廓实测：计算 Y 偏移 ──
    all_cy = []
    for fpath in scan_files[:n_samples]:
        img = cv2.imread(str(fpath), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        ix1 = int(full_rect["x1"] * sx)
        iy1 = int(full_rect["y1"] * sy)
        ix2 = int(full_rect["x2"] * sx)
        iy2 = int(full_rect["y2"] * sy)
        crop = img[iy1:iy2, ix1:ix2]

        _, binary = cv2.threshold(crop, 80, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for cnt in contours:
            _, by, bw, bh = cv2.boundingRect(cnt)
            area = cv2.contourArea(cnt)
            if 5 < bw < 45 and 5 < bh < 40 and area > 20:
                all_cy.append(by + bh // 2)

    # 对每个轮廓 y，找最近的初始行，计算偏移
    offsets = []
    for cy in all_cy:
        dists = [cy - r for r in initial_rows]
        nearest = min(dists, key=abs)
        if abs(nearest) < 20:
            offsets.append(nearest)

    y_offset = int(np.median(offsets)) if offsets else 0
    row_centers = [r + y_offset for r in initial_rows]

    # ── X 偏移微调（轮廓 x 与初始列的偏移中位数）──
    all_cx_by_group = [[] for _ in choices]
    for fpath in scan_files[:n_samples]:
        img = cv2.imread(str(fpath), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        for gi, g in enumerate(choices):
            rect = g["rect"]
            gx1 = int(rect["x1"] * sx)
            gy1 = int(rect["y1"] * sy)
            gx2 = int(rect["x2"] * sx)
            gy2 = int(rect["y2"] * sy)
            crop = img[gy1:gy2, gx1:gx2]
            _, binary = cv2.threshold(crop, 80, 255, cv2.THRESH_BINARY_INV)
            contours, _ = cv2.findContours(
                binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            offset_x = gx1 - fr_x1
            for cnt in contours:
                bx, _, bw, bh = cv2.boundingRect(cnt)
                area = cv2.contourArea(cnt)
                if 5 < bw < 45 and 5 < bh < 40 and area > 20:
                    all_cx_by_group[gi].append(bx + bw // 2 + offset_x)

    col_per_group = []
    for gi, init_cols in enumerate(col_per_group_initial):
        cxs = all_cx_by_group[gi]
        x_offsets = []
        for cx in cxs:
            dists = [cx - c for c in init_cols]
            nearest = min(dists, key=abs)
            if abs(nearest) < 15:
                x_offsets.append(nearest)
        x_off = int(np.median(x_offsets)) if x_offsets else 0
        col_per_group.append([c + x_off for c in init_cols])

    return row_centers, col_per_group, full_rect


# ── 第三层：暗度检测 ──────────────────────────────────────────

def _is_transposed(tpl):
    """判断布局方向：rect 宽 > 高 × 1.5 → 转置（题号横向，选项纵向）。"""
    for g in tpl["choices"]:
        r = g["rect"]
        w = r["x2"] - r["x1"]
        h = r["y2"] - r["y1"]
        if w > h * 1.5:
            return True
    return False


def detect_choices(img_path, tpl, row_centers, col_per_group, full_rect,
                   box_hw=12, box_hh=10):
    """暗度检测 + 空白卡检测。返回 (answers_dict, is_blank)。"""
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None, True
    sx = img.shape[1] / tpl["tpl_w"]
    sy = img.shape[0] / tpl["tpl_h"]
    cx1 = int(full_rect["x1"] * sx)
    cy1 = int(full_rect["y1"] * sy)
    cx2 = int(full_rect["x2"] * sx)
    cy2 = int(full_rect["y2"] * sy)
    crop = img[cy1:cy2, cx1:cx2]
    ch, cw = crop.shape

    transposed = _is_transposed(tpl)
    labels = "ABCD"
    answers = {}
    all_max = []

    if transposed:
        n_opts = len(row_centers)
        for gi, q_positions in enumerate(col_per_group):
            for qi, qx in enumerate(q_positions):
                qno = gi * len(q_positions) + qi + 1
                scores = []
                for oi in range(n_opts):
                    oy = row_centers[oi]
                    bx1 = max(0, qx - box_hw); bx2 = min(cw, qx + box_hw)
                    by1 = max(0, oy - box_hh); by2 = min(ch, oy + box_hh)
                    box = crop[by1:by2, bx1:bx2]
                    scores.append(255 - float(np.mean(box)) if box.size > 0 else 0)
                best = int(np.argmax(scores))
                all_max.append(scores[best])
                if scores[best] > MIN_DARKNESS:
                    answers[qno] = labels[best]
    else:
        n_rows = len(row_centers)
        for gi, cols in enumerate(col_per_group):
            for ri in range(n_rows):
                qno = gi * n_rows + ri + 1
                ry = row_centers[ri]
                scores = []
                for ox in cols:
                    bx1 = max(0, ox - box_hw); bx2 = min(cw, ox + box_hw)
                    by1 = max(0, ry - box_hh); by2 = min(ch, ry + box_hh)
                    box = crop[by1:by2, bx1:bx2]
                    scores.append(255 - float(np.mean(box)) if box.size > 0 else 0)
                best = int(np.argmax(scores))
                all_max.append(scores[best])
                if scores[best] > MIN_DARKNESS:
                    answers[qno] = labels[best]

    is_blank = np.mean(all_max) < BLANK_THRESHOLD if all_max else True
    return answers, is_blank


# ── 第四层：自动 QID 映射 ──────────────────────────────────────

def auto_map_qids(conn, subj_id, scan_files, tpl, row_centers, col_per_group,
                  full_rect, n_map_samples=300):
    """用逐学生精确匹配自动建立 question_id → qno 映射。"""
    c = conn.cursor()
    c.execute(
        "SELECT student_id, question_id, detected_answer "
        "FROM student_answers "
        "WHERE subject_id = ? AND question_type = 'choice' "
        "  AND detected_answer IS NOT NULL AND detected_answer != ''",
        (subj_id,),
    )
    db_raw = defaultdict(dict)
    for sid, qid, ans in c.fetchall():
        db_raw[sid][qid] = ans

    all_qids = sorted(set(qid for d in db_raw.values() for qid in d))
    n_rows, _ = _infer_rows_cols(tpl)
    total_q = sum(g.get("rows") or n_rows for g in tpl["choices"])

    bc_rect = tpl["barcode"]
    tpl_size = {"width": tpl["tpl_w"], "height": tpl["tpl_h"]}

    det_results = {}
    for f in scan_files[:n_map_samples]:
        bc = read_barcode(f, crop_region=bc_rect, template_size=tpl_size)
        if bc is None or bc not in db_raw:
            continue
        det, is_blank = detect_choices(f, tpl, row_centers, col_per_group, full_rect)
        if det and not is_blank:
            det_results[bc] = det

    qid_best = {}
    for qid in all_qids:
        best_qno, best_match, best_total = None, -1, 0
        for qno in range(1, total_q + 1):
            match = total = 0
            for bc in det_results:
                db_a = db_raw[bc].get(qid, "")
                det_a = det_results[bc].get(qno, "")
                if db_a and det_a:
                    total += 1
                    if db_a == det_a:
                        match += 1
            if total > 0 and match > best_match:
                best_match = match
                best_total = total
                best_qno = qno
        qid_best[qid] = (best_qno, best_match, best_total)

    used = set()
    qid_to_qno = {}
    for qid in sorted(qid_best, key=lambda q: -qid_best[q][1]):
        qno, _, _ = qid_best[qid]
        if qno is not None and qno not in used:
            qid_to_qno[qid] = qno
            used.add(qno)

    for qid in all_qids:
        if qid not in qid_to_qno:
            for qno in range(1, total_q + 1):
                if qno not in used:
                    qid_to_qno[qid] = qno
                    used.add(qno)
                    break

    return qid_to_qno, db_raw


# ── 校准缓存 ──────────────────────────────────────────────────

def save_calibration(conn, subj_id, row_centers, col_per_group, full_rect):
    """将校准结果存入模板 anchors 字段。"""
    cal = json.dumps({
        "version": 1,
        "row_centers": row_centers,
        "col_per_group": col_per_group,
        "full_rect": full_rect,
    })
    c = conn.cursor()
    c.execute(
        "UPDATE templates SET anchors = ? WHERE subject_id = ? AND side = 'A'",
        (cal, subj_id),
    )
    conn.commit()


def load_calibration(conn, subj_id):
    """从模板 anchors 字段读取已有校准。返回 (row_centers, col_per_group, full_rect) 或 None。"""
    c = conn.cursor()
    c.execute(
        "SELECT anchors FROM templates WHERE subject_id = ? AND side = 'A'",
        (subj_id,),
    )
    row = c.fetchone()
    if not row or not row[0]:
        return None
    try:
        cal = json.loads(row[0])
        if isinstance(cal, dict) and cal.get("version") == 1:
            return cal["row_centers"], cal["col_per_group"], cal["full_rect"]
    except (json.JSONDecodeError, KeyError):
        pass
    return None


# ── 第五层：全量校准 ──────────────────────────────────────────

def run_calibration(name, conf, conn, recalibrate=False):
    subj_id = conf["subj_id"]
    scan_dir = conf["scan_dir"]
    scan_pattern = conf.get("scan_pattern", "flat")

    tpl = load_template(conn, subj_id)
    if not tpl:
        print(f"  {name}: 模板未找到")
        return

    n_rows, _ = _infer_rows_cols(tpl)
    total_q = sum(g.get("rows") or n_rows for g in tpl["choices"])
    a_files = list_scan_files(scan_dir, scan_pattern)

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    print(f"  模板: {tpl['tpl_w']}x{tpl['tpl_h']}, {len(tpl['choices'])} 组, {total_q} 题")
    print(f"  扫描: {len(a_files)} 张 ({scan_pattern})")

    # Step 1: 读取或发现位置
    cached = None if recalibrate else load_calibration(conn, subj_id)
    if cached:
        row_centers, col_per_group, full_rect = cached
        print("  [1/3] 使用已有校准 ✓")
    else:
        print("  [1/3] 首次校准，自动发现网格位置...")
        row_centers, col_per_group, full_rect = discover_grid(a_files, tpl)
        save_calibration(conn, subj_id, row_centers, col_per_group, full_rect)
        print("    校准结果已保存到模板")
    print(f"    行中心: {row_centers}")
    for gi, cols in enumerate(col_per_group):
        print(f"    组{gi+1} 列: {cols}")

    # Step 2: 自动映射 QID
    print("  [2/3] 自动映射 question_id → 题号...")
    qid_to_qno, db_raw = auto_map_qids(
        conn, subj_id, a_files, tpl, row_centers, col_per_group, full_rect
    )
    print(f"    映射完成: {len(qid_to_qno)}/{total_q}")

    # Step 3: 全量校准
    print("  [3/3] 全量检测对比...")
    db_mapped = defaultdict(dict)
    for sid in db_raw:
        for qid, ans in db_raw[sid].items():
            qno = qid_to_qno.get(qid)
            if qno:
                db_mapped[sid][qno] = ans

    bc_rect = tpl["barcode"]
    tpl_size = {"width": tpl["tpl_w"], "height": tpl["tpl_h"]}

    match_q = total_compared = perfect = n_students = n_blank = 0
    per_q = defaultdict(lambda: [0, 0])
    err_dist = defaultdict(int)
    mismatches = []

    for f in a_files:
        bc = read_barcode(f, crop_region=bc_rect, template_size=tpl_size)
        if bc is None or bc not in db_mapped:
            continue
        det, is_blank = detect_choices(f, tpl, row_centers, col_per_group, full_rect)
        if is_blank:
            n_blank += 1
            continue
        if det is None:
            continue

        n_students += 1
        student_ok = True
        db = db_mapped[bc]
        errs = 0

        for qno in range(1, total_q + 1):
            db_a = db.get(qno, "")
            det_a = det.get(qno, "")
            if not db_a:
                continue
            total_compared += 1
            per_q[qno][1] += 1
            if db_a == det_a:
                match_q += 1
                per_q[qno][0] += 1
            else:
                student_ok = False
                errs += 1
                if len(mismatches) < 15:
                    mismatches.append(f"    {bc} Q{qno:2d}: DB={db_a} DET={det_a}")
        err_dist[errs] += 1
        if student_ok:
            perfect += 1

    print(f"\n  [结果]")
    print(f"    空白卡跳过: {n_blank}")
    print(f"    有效学生: {n_students}")
    if total_compared > 0:
        rate = match_q / total_compared * 100
        err_students = n_students - perfect
        print(f"    逐题一致: {match_q}/{total_compared} ({rate:.3f}%)")
        print(f"    全对学生: {perfect}/{n_students} ({perfect/n_students*100:.1f}%)")
        print(f"    有差异学生: {err_students} ({err_students/n_students*100:.1f}%)")

        print(f"\n    各题:")
        for qno in range(1, total_q + 1):
            m, t = per_q[qno]
            pct = m / t * 100 if t > 0 else 0
            flag = "" if pct >= 99 else " ←"
            print(f"      Q{qno:2d}: {m:4d}/{t:4d} ({pct:5.1f}%){flag}")

    if mismatches:
        print(f"\n    不一致样本:")
        for m in mismatches:
            print(m)


def main():
    recal = "--recalibrate" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    conn = sqlite3.connect(str(DB))
    targets = args if args else list(SUBJECTS.keys())  #semantic-ok: 空 args 回退到全量，同原逻辑
    for name in targets:
        if name in SUBJECTS:
            conf = SUBJECTS[name]
            if conf["scan_dir"].exists():
                run_calibration(name, conf, conn, recalibrate=recal)
            else:
                print(f"  {name}: 目录不存在 {conf['scan_dir']}")
    conn.close()


if __name__ == "__main__":
    main()
