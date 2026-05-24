<!-- legacy-format -->
# 扫描识别系统校准 Handoff

## Goal
校准景炎中学七年级期中考试的条形码+选择题填涂识别系统，目标一致率 ≥99%。

## 当前状态

| 科目 | 条形码 | 选择题（排除脏数据） | 脚本 | 状态 |
|------|--------|---------------------|------|------|
| 语文 | 99.93% | 99.94% | `calibrate_scan.py` | ✅ 达标 |
| 生物 | 100% | **99.75%** | `calibrate_universal.py` | ✅ 达标 |
| 地理 | 100% | **99.15%** | `calibrate_universal.py` | ✅ 达标 |
| 数学 | - | 检测可行，无参考数据 | `calibrate_universal.py` | ⚠️ 待参考答案 |

## 架构

```
模板 DB (regions) → discover_grid (首次) → 校准结果 → 缓存到 anchors 字段
                                                           ↓
扫描图 → detect_choices (每次) → 暗度法检测 → {qno: 'A'/'B'/'C'/'D'}
                                                           ↓
                               auto_map_qids → qid→qno 映射 → 全量对比
```

**校准只跑一次**：首次运行自动发现气泡位置并存入 DB `anchors` 字段，后续直接读取。

**两种布局自动识别**：
- 标准（生物/地理）：题目纵向，选项横向
- 转置（数学）：题目横向，选项纵向（按 rect 宽高比自动判断）

## Must Preserve
- 语文 calibrate_scan.py 的 v5 算法（已验证达标，独立脚本）
- `src/edu_cloud/modules/scan/vision/barcode.py` 和 `fillmark.py`（生产代码）
- DB 中已有的选择题数据（校方系统导入的真值）
- 生物/地理的缓存校准数据（templates.anchors 字段）

## Must Not Change
- calibrate_scan.py（语文专用，已锁定）
- barcode.py / fillmark.py（生产代码）

## 关键文件

| 文件 | 用途 |
|------|------|
| `scripts/calibrate_universal.py` | 通用校准（生物/地理/数学，自动缓存） |
| `scripts/calibrate_scan.py` | 语文校准 v5（独立，已锁定） |
| `scripts/archived/2026-05-24-scan-calibration/calibrate_bio_geo.py` | 旧版，已被 universal 替代，已归档 |

## 用法

```bash
# 校准所有科目（首次自动发现，后续读缓存）
.venv/bin/python scripts/calibrate_universal.py

# 校准指定科目
.venv/bin/python scripts/calibrate_universal.py 生物

# 强制重新校准（忽略缓存）
.venv/bin/python scripts/calibrate_universal.py --recalibrate
```

## 待办

1. **数学模板修正**：R03 的 rows 应为 11（实际 11 题），Q8/Q9 间有间隔需拆组
2. **数学参考数据**：需要校方选择题答案导入后才能做准确率对比
3. **LLM 校准集成**：Vertex AI 已通（gemini-2.5-flash），可用于结构识别辅助 OpenCV 精确定位
4. **高三一模扫描**：`uploads/scan-input/1947ae38.../数学/` 有 367 学生扫描，但对应考试无科目记录
