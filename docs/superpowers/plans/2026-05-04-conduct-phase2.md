# 德育 Phase 2: 学期评价 + 行为预警 + 趋势增强

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Phase 1 三环打通基础上，增加学期评价报告、行为预警、趋势数据——继续零新增页面，全部嵌入现有视图。

**Architecture:** 新增 report_service（学期评价聚合）+ 扩展 event_service（阈值预警）+ 增强 scope_service（趋势数据）。前端在现有 Dashboard/ParentOverview 中增强展示。

**Tech Stack:** 同 Phase 1 — FastAPI + SQLAlchemy async / Vue 3 + Naive UI

---

## Task 1: 学期评价报告服务

**Files:**
- Create: `src/edu_cloud/modules/conduct/report_service.py`
- Modify: `src/edu_cloud/modules/conduct/admin_router.py`
- Create: `tests/test_conduct/test_report_service.py`

### 设计

一个函数 `generate_semester_report(db, class_id, semester_id=None)` 返回结构化学期评价：

```python
{
    "class_name": str,
    "semester_name": str,
    "period": {"start": str, "end": str},
    "summary": {
        "total_students": int,
        "total_records": int,
        "avg_points": float,
        "positive_rate": float,  # 加分记录占比
    },
    "top_students": [{"name": str, "points": int, "rank": int}, ...],  # top 10
    "bottom_students": [...],  # bottom 10
    "category_breakdown": [  # 按规则分类统计
        {"category": str, "positive_count": int, "negative_count": int, "net_points": int},
    ],
    "weekly_trend": [{"week": str, "positive": int, "negative": int}, ...],
    "highlights": {
        "most_improved": {"name": str, "delta": int} | null,  # 进步最大
        "most_consistent": {"name": str, "positive_streak": int} | null,  # 连续加分最多
    },
}
```

如果 semester_id=None，使用当前活跃学期（is_current=True）。如果没有活跃学期，使用最近 90 天。

### 端点

```
GET /api/v1/conduct/classes/{class_id}/report          # 班级学期评价
GET /api/v1/conduct/schools/{school_id}/report         # 学校学期评价（聚合各班）
```

学校级报告调用每个班的 generate_semester_report 然后聚合 summary + 班级排名。

- [ ] **Step 1: 写 report_service 失败测试**

```python
# tests/test_conduct/test_report_service.py
import pytest
from edu_cloud.modules.conduct.report_service import generate_semester_report

@pytest.mark.asyncio
async def test_report_basic_structure(db_session, seed_conduct_data):
    report = await generate_semester_report(db_session, seed_conduct_data["class_id"])
    assert "summary" in report
    assert "top_students" in report
    assert "category_breakdown" in report
    assert "weekly_trend" in report
    assert report["summary"]["total_students"] > 0

@pytest.mark.asyncio
async def test_report_with_semester(db_session, seed_conduct_data, seed_semester):
    report = await generate_semester_report(db_session, seed_conduct_data["class_id"], seed_semester["id"])
    assert report["semester_name"] == seed_semester["name"]

@pytest.mark.asyncio
async def test_report_category_breakdown(db_session, seed_conduct_with_rules):
    report = await generate_semester_report(db_session, seed_conduct_with_rules["class_id"])
    assert len(report["category_breakdown"]) > 0
    for cat in report["category_breakdown"]:
        assert "category" in cat
        assert "net_points" in cat

@pytest.mark.asyncio
async def test_report_empty_class(db_session, seed_empty_class):
    report = await generate_semester_report(db_session, seed_empty_class["class_id"])
    assert report["summary"]["total_records"] == 0
    assert report["top_students"] == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_conduct/test_report_service.py -v`

- [ ] **Step 3: 实现 report_service.py**

完整实现 generate_semester_report 函数。关键逻辑：
- 查询 ConductSemester（如果有 semester_id）确定日期范围
- 在日期范围内聚合 ConductRecord
- 按学生聚合 points → 排名
- 按 RuleCategory 聚合 → category_breakdown
- 按周聚合 → weekly_trend
- highlights: most_improved = 后半段 - 前半段 delta 最大的学生

- [ ] **Step 4: 添加端点到 admin_router.py**

```python
@router.get("/classes/{class_id}/report")
async def get_class_report(class_id: str, semester_id: str | None = None, ...)

@router.get("/schools/{school_id}/report")
async def get_school_report(school_id: str, semester_id: str | None = None, ...)
```

- [ ] **Step 5: 运行测试**

Run: `.venv/bin/python -m pytest tests/test_conduct/test_report_service.py tests/test_conduct/ -v`

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(conduct): semester report service — 学期评价报告自动生成"
```

---

## Task 2: 行为预警系统

**Files:**
- Modify: `src/edu_cloud/modules/conduct/event_service.py`
- Modify: `src/edu_cloud/modules/conduct/models.py`（ConductClassConfig 加阈值字段）
- Create: `alembic/versions/e_conduct_alert_threshold.py`
- Modify: `src/edu_cloud/modules/conduct/admin_service.py`
- Create: `tests/test_conduct/test_alerts.py`

### 设计

在 ConductClassConfig 中新增阈值字段：
```python
alert_threshold: Mapped[int | None] = mapped_column(Integer, default=None, nullable=True)
# 当学生累计积分低于此值时触发预警。None = 不预警
```

在 event_service.py 中新增函数 `check_alert_threshold(db, student_id, class_id)`:
1. 查询 ConductClassConfig 的 alert_threshold
2. 如果为 None，跳过
3. 计算学生当前累计积分
4. 如果低于阈值，创建预警通知给家长 + 班主任

在 admin_service.py 的 add_points 末尾，除了 notify_parents，还调用 check_alert_threshold。

通知类型区分：title 前缀 `[预警]` 表示阈值通知，普通积分通知无前缀。

- [ ] **Step 1: 写预警测试**

```python
# tests/test_conduct/test_alerts.py
import pytest
from edu_cloud.modules.conduct.event_service import check_alert_threshold

@pytest.mark.asyncio
async def test_alert_triggered_below_threshold(db_session, seed_alert_data):
    """积分低于阈值时触发预警"""
    count = await check_alert_threshold(
        db_session, seed_alert_data["student_id"], seed_alert_data["class_id"]
    )
    assert count > 0  # 至少通知家长

@pytest.mark.asyncio
async def test_no_alert_above_threshold(db_session, seed_alert_data_above):
    """积分高于阈值时不触发"""
    count = await check_alert_threshold(
        db_session, seed_alert_data_above["student_id"], seed_alert_data_above["class_id"]
    )
    assert count == 0

@pytest.mark.asyncio
async def test_no_alert_when_disabled(db_session, seed_alert_data_no_threshold):
    """阈值为 None 时不触发"""
    count = await check_alert_threshold(
        db_session, seed_alert_data_no_threshold["student_id"], seed_alert_data_no_threshold["class_id"]
    )
    assert count == 0
```

- [ ] **Step 2: 添加 alert_threshold 字段 + migration**

ConductClassConfig 新增 `alert_threshold` 列。Migration 添加 nullable integer 列。

- [ ] **Step 3: 实现 check_alert_threshold**

在 event_service.py 中追加函数。

- [ ] **Step 4: 在 add_points 中触发预警检查**

admin_service.py add_points 末尾追加：
```python
from edu_cloud.modules.conduct.event_service import check_alert_threshold
for student_id in student_ids:
    await check_alert_threshold(db, student_id, class_id)
```

- [ ] **Step 5: 运行测试**

Run: `.venv/bin/python -m pytest tests/test_conduct/test_alerts.py tests/test_conduct/ -v`

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(conduct): behavior alert system — 积分低于阈值自动预警"
```

---

## Task 3: Dashboard 趋势增强 + 前端集成

**Files:**
- Modify: `src/edu_cloud/modules/conduct/scope_service.py`（school/district 加趋势）
- Modify: `frontend/src/pages/conduct/ConductDashboard.vue`（趋势图 + 报告入口）
- Modify: `frontend/src/pages/conduct/ConductSettings.vue`（预警阈值配置）
- Modify: `frontend/src/pages/parent/ParentOverview.vue`（学期评价摘要卡）
- Modify: `frontend/src/api/conduct.js`（新增 API）
- Create: `tests/test_conduct/test_scope_trend.py`

### 后端：scope_service 趋势增强

school_overview 和 district_overview 目前没有趋势数据。增强：

- `_school_overview` 返回中新增 `"trend"` 字段（同 class_overview 的 weekly_trend 格式，全校聚合）
- `_district_overview` 返回中新增 `"trend"` 字段（全区聚合）

复用现有 `_weekly_trend` 函数，只需传入正确的 class_ids。

### 前端

1. **ConductDashboard**: school/district scope 也显示趋势图（复用现有 buildTrendOption）
2. **ConductSettings**: 新增"行为预警"区域——一个数字输入框设置 alert_threshold
3. **ParentOverview**: 调用 report API 展示学期评价摘要卡（总分+排名+趋势标签）
4. **conduct.js**: 新增 `getClassReport(classId, params)`, `getSchoolReport(schoolId, params)`, `updateConductConfig` 已有

- [ ] **Step 1: 增强 scope_service + 测试**

```python
# test_scope_trend.py
@pytest.mark.asyncio
async def test_school_overview_has_trend(db_session, seed_conduct_data):
    result = await get_conduct_overview(db_session, "school", [seed_conduct_data["school_id"]])
    assert "trend" in result
```

- [ ] **Step 2: 前端 Dashboard 增强**

school/district template 块中增加趋势图。

- [ ] **Step 3: ConductSettings 预警配置**

阈值输入框 + 调用 updateConductConfig。

- [ ] **Step 4: ParentOverview 学期摘要**

调用 report endpoint 展示简要学期评价。

- [ ] **Step 5: 前端测试**

Run: `npx vitest run src/pages/conduct/ src/pages/parent/`

- [ ] **Step 6: Build**

Run: `cd frontend && npx vite build`

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(conduct): trend + alerts UI + semester summary — Phase 2 前端集成"
```

---

## Task 4: 集成验证

- [ ] **Step 1: 后端全量 conduct 测试**
- [ ] **Step 2: 前端全量测���**
- [ ] **Step 3: Build 确认**
