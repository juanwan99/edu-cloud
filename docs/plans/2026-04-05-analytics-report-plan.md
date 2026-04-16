# Phase 3.3 分析报告 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 edu-cloud 添加分数段配置、自定义分析构建器、跨考试对比趋势、PDF 报告导出能力。

**Architecture:** 在现有 `modules/analytics/` 下扩展 segment_service + report_service，复用 W1 预计算表（exam_analysis_snapshot / class_exam_report）和 pipeline 产出（student_exam_snapshots）。PDF 导出走现有 Studio Document 流程。新增 3 个 AI Agent 工具。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic + pytest / Vue 3 + Naive UI + ECharts + Vitest

---

## File Structure

### 后端新增

| 文件 | 职责 |
|------|------|
| `src/edu_cloud/models/score_segment.py` | ScoreSegmentConfig 数据模型 |
| `src/edu_cloud/modules/analytics/segment_service.py` | 分数段 CRUD + 分段计算 |
| `src/edu_cloud/modules/analytics/report_service.py` | 自定义分析构建 + 跨考试对比 + PDF 导出 |
| `src/edu_cloud/ai/tools/analytics_report.py` | 3 个 AI Agent 工具 |
| `alembic/versions/xxxx_add_score_segment_config.py` | Alembic migration |

### 后端修改

| 文件 | 变更 |
|------|------|
| `src/edu_cloud/modules/analytics/service.py` | exam_distribution 支持动态分数段 |
| `src/edu_cloud/modules/analytics/router.py` | 新增 7 路由 |
| `src/edu_cloud/ai/tools/__init__.py` | 注册新工具模块 |
| `tests/conftest.py` | 导入 score_segment 模型 |

### 前端新增

| 文件 | 职责 |
|------|------|
| `frontend/src/pages/AnalyticsReportPage.vue` | 分析报告页面（查询构建器 + 结果展示） |
| `frontend/src/pages/AnalyticsTrendPage.vue` | 跨考试趋势页面（折线图） |
| `frontend/src/components/analytics/ScoreSegmentSettings.vue` | 分数段配置组件 |

### 前端修改

| 文件 | 变更 |
|------|------|
| `frontend/src/api/analytics.js` | 新增 API 调用 |
| `frontend/src/router/index.js` | 新增 2 路由 |
| `frontend/src/config/sidebarConfig.js` | 新增 2 侧栏项 |

### 测试新增

| 文件 | 覆盖范围 |
|------|---------|
| `tests/test_services_exam/test_segment_service.py` | 分数段 CRUD + 计算逻辑 |
| `tests/test_services_exam/test_report_service.py` | 自定义分析 + 趋势对比 |
| `tests/test_api_exam/test_analytics_report.py` | 报告 API 路由 |
| `tests/test_ai/test_tools_analytics_report.py` | AI 工具 |
| `frontend/src/pages/__tests__/AnalyticsReportPage.test.js` | 前端报告页 |

---

## Contract Pack

### invariants

1. **分数段唯一性**: 每校最多 1 条默认配置（subject_code=NULL），每校每科最多 1 条覆盖。PostgreSQL 用 partial unique index 保证。
   - verification: `test_upsert_prevents_duplicate_default` (Task 1)
2. **学生数据可见性**: student_trend API 必须校验调用者对 student_id 的可见权限（班级可见性 + 家长 guardian 绑定），不可凭 student_id 越权。
   - verification: `test_student_trend_forbidden_for_other_class` (Task 7)
3. **趋势数据一致性**: 趋势 API 优先读 W1 预计算快照（ExamAnalysisSnapshot / ClassExamReport / StudentExamSnapshot），仅在无快照时实时聚合。两种路径必须返回兼容结构。
   - verification: `test_grade_trend` + `test_class_trend` + `test_student_trend` (Task 6)
4. **metrics 角色白名单**: parent/homeroom_teacher/subject_teacher 不能获取 ranking/top_bottom 指标，report/query API 强制裁剪。
   - verification: `test_report_query_restricted_metrics` (Task 7)

### counter_examples

1. **越权学生趋势**: 科任教师请求非任教班学生的 trend/student → 应返回 403。如果测试仍 PASS，说明可见性校验缺失。
   - tests_that_still_pass: `test_student_trend_api`（当前只测正常路径）
   - mitigation: Task 7 补越权测试
2. **NULL 唯一性绕过**: 连续创建两条 subject_code=NULL 的默认配置 → 应被 service 层 upsert 阻止（SQLite 无 partial index）。如果第二条被创建，说明 upsert 逻辑有缺陷。
   - tests_that_still_pass: `test_create_default_segment`
   - mitigation: Task 1 `test_upsert_prevents_duplicate_default` 验证

### risk_modules

| 模块 | 变更类型 | 风险等级 |
|------|---------|---------|
| `modules/analytics/segment_service.py` | 新增 | 低 — 纯 CRUD |
| `modules/analytics/report_service.py` | 新增 | 中 — 聚合逻辑复杂度 |
| `modules/analytics/service.py` (exam_distribution) | 修改 | 中 — 破坏现有分布 API 返回格式 |
| `modules/analytics/router.py` | 修改 | 高 — 7 个新 public API 端点，权限校验关键 |
| `ai/tools/analytics_report.py` | 新增 | 中 — 3 个 Agent 工具 |

### test_debt

无。本 plan 所有 public API 和 service 函数均有测试覆盖。

---

## Task 1: ScoreSegmentConfig 数据模型 + Migration

**Files:**
- Create: `src/edu_cloud/models/score_segment.py`
- Modify: `tests/conftest.py:38` (添加模型导入)
- Test: `tests/test_services_exam/test_segment_service.py`

- [ ] **Step 1: 创建模型文件**

```python
# src/edu_cloud/models/score_segment.py
"""分数段配置模型。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Index, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TenantMixin, TimestampMixin


class ScoreSegmentConfig(Base, IdMixin, TenantMixin, TimestampMixin):
    """学校级分数段配置（per school + optional per subject override）。"""
    __tablename__ = "score_segment_config"
    __table_args__ = (
        # PostgreSQL: UNIQUE(a, b) 不阻止多个 NULL b。用两个 partial index：
        Index("uq_segment_school_default", "school_id",
              unique=True, postgresql_where=text("subject_code IS NULL")),
        Index("uq_segment_school_subject", "school_id", "subject_code",
              unique=True, postgresql_where=text("subject_code IS NOT NULL")),
    )

    subject_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, default=None,
    )
    boundaries: Mapped[list] = mapped_column(
        JSON, default=lambda: [85, 70, 60],
    )
    labels: Mapped[list] = mapped_column(
        JSON, default=lambda: ["优秀", "良好", "及格", "不及格"],
    )
    # AR-05: 去掉 is_active 软删（简化为硬删，避免与 partial unique index 冲突）
    created_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True,
    )
```

- [ ] **Step 2: 在 conftest.py 注册��型**

在 `tests/conftest.py` 的 `import edu_cloud.models.scope_version` 行之后添加：

```python
import edu_cloud.models.score_segment  # noqa: F401
```

- [ ] **Step 3: 写基础模型测试**

```python
# tests/test_services_exam/test_segment_service.py
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.score_segment import ScoreSegmentConfig
from sqlalchemy import select


@pytest.fixture
async def school(db):
    s = School(name="SegTest", code="SEG01")
    db.add(s)
    await db.commit()
    return s


async def test_create_default_segment(db, school):
    cfg = ScoreSegmentConfig(school_id=school.id)
    db.add(cfg)
    await db.commit()

    result = await db.execute(
        select(ScoreSegmentConfig).where(
            ScoreSegmentConfig.school_id == school.id,
            ScoreSegmentConfig.subject_code.is_(None),
        )
    )
    row = result.scalar_one()
    assert row.boundaries == [85, 70, 60]
    assert row.labels == ["优秀", "良好", "及格", "不及格"]


async def test_upsert_prevents_duplicate_default(db, school):
    """Service 层 upsert 阻止同校重复默认配置（partial index 在 PostgreSQL 生效，SQLite 靠 service 层）。"""
    from edu_cloud.modules.analytics.segment_service import upsert_segment_config
    await upsert_segment_config(db, school.id, [85, 70, 60], ["优", "良", "及", "不"])
    await db.commit()
    # 第二次 upsert 应更新而非新建
    await upsert_segment_config(db, school.id, [90, 75, 60], ["A", "B", "C", "D"])
    await db.commit()
    from sqlalchemy import select
    result = await db.execute(
        select(ScoreSegmentConfig).where(
            ScoreSegmentConfig.school_id == school.id,
            ScoreSegmentConfig.subject_code.is_(None),
        )
    )
    configs = list(result.scalars().all())
    assert len(configs) == 1  # upsert, not duplicate
    assert configs[0].boundaries == [90, 75, 60]
```

- [ ] **Step 4: 运行测试验证**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_segment_service.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: 生成 Alembic migration**

Run: `cd C:/Users/Administrator/edu-cloud && python -m alembic revision --autogenerate -m "add score_segment_config"`

验证生成的文件包含 `create_table('score_segment_config', ...)` 和唯一约束。

- [ ] **Step 6: Commit**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/models/score_segment.py tests/test_services_exam/test_segment_service.py tests/conftest.py alembic/versions/*score_segment*
git commit -m "feat(analytics): add ScoreSegmentConfig model + migration"
```

**审查清单:**
- ✓ ScoreSegmentConfig 有 school_id + subject_code 唯一约束
- ✓ 默认值 [85,70,60] + ["优秀","良好","及格","不及格"]
- ✓ subject_code=null 代表学校默认
- ✗ 同一 school_id 出现两个 subject_code=null → 应抛唯一约束异常

**边界条件:**
- 空 boundaries `[]` → 期望: 只有一个段（全员归入同一档）
- subject_code=null 重复 → 期望: 数据库唯一约束报错
- boundaries 非降序（如 `[60, 70, 85]`）→ 期望: service 层校验拒绝，model 层不限制

**测试契约:**
1. 创建默认分数段配置
   - 入口: `ScoreSegmentConfig(school_id=...)` 直接写入数据库
   - 反例: 错误实现可能遗漏默认值导致 boundaries=None
   - 边界: 无参数创建 / subject_code=None
   - 回归: N/A
   - 命令: `pytest tests/test_services_exam/test_segment_service.py::test_create_default_segment -v`
2. 同校同科目唯一约束
   - 入口: 连续插入两条相同 school_id + subject_code 的记录
   - 反例: 缺唯一约束导致数据重复
   - 边界: subject_code=null 重复 / 相同 subject_code 重复
   - 回归: N/A
   - 命令: `pytest tests/test_services_exam/test_segment_service.py::test_subject_override_unique -v`

---

## Task 2: segment_service — 分数段 CRUD + 计算逻辑

**Files:**
- Create: `src/edu_cloud/modules/analytics/segment_service.py`
- Test: `tests/test_services_exam/test_segment_service.py` (扩展)

- [ ] **Step 1: 写 compute_segments 失败测试**

在 `tests/test_services_exam/test_segment_service.py` 追加：

```python
from edu_cloud.modules.analytics.segment_service import (
    compute_segments, get_segment_config, upsert_segment_config,
)


def test_compute_segments_default():
    scores = [95, 82, 73, 65, 50, 88, 40]
    result = compute_segments(
        scores=scores, max_score=100.0,
        boundaries=[85, 70, 60], labels=["优秀", "良好", "及格", "不及格"],
    )
    assert len(result) == 4
    excellent = next(s for s in result if s["label"] == "优秀")
    assert excellent["count"] == 2  # 95, 88
    poor = next(s for s in result if s["label"] == "不及格")
    assert poor["count"] == 2  # 50, 40


def test_compute_segments_empty():
    result = compute_segments(scores=[], max_score=100.0, boundaries=[85, 70, 60], labels=["优秀", "良好", "及格", "不及格"])
    assert all(s["count"] == 0 for s in result)


def test_compute_segments_max_score_zero():
    result = compute_segments(scores=[0, 0], max_score=0.0, boundaries=[85, 70, 60], labels=["优秀", "良好", "及格", "不及格"])
    # max_score=0 → all scores percentage=0 → all in lowest segment
    assert result[-1]["count"] == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_segment_service.py::test_compute_segments_default -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: 实现 segment_service**

```python
# src/edu_cloud/modules/analytics/segment_service.py
"""分数段配置 CRUD + 分段计算。"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.score_segment import ScoreSegmentConfig
from edu_cloud.services.exceptions import ValidationError

logger = logging.getLogger(__name__)

DEFAULT_BOUNDARIES = [85, 70, 60]
DEFAULT_LABELS = ["优秀", "良好", "及格", "不及格"]


def compute_segments(
    scores: list[float],
    max_score: float,
    boundaries: list[int],
    labels: list[str],
) -> list[dict]:
    """将原始分按百分比阈值分段。

    boundaries 降序，如 [85, 70, 60]。labels 比 boundaries 多一个。
    返回 [{label, count, percentage, boundary_min, boundary_max}]。
    """
    n = len(scores)
    segments = []
    sorted_boundaries = sorted(boundaries, reverse=True)

    for i, label in enumerate(labels):
        if i == 0:
            b_min = sorted_boundaries[0]
            b_max = 101  # inclusive upper
        elif i < len(sorted_boundaries):
            b_min = sorted_boundaries[i]
            b_max = sorted_boundaries[i - 1]
        else:
            b_min = 0
            b_max = sorted_boundaries[-1] if sorted_boundaries else 101

        count = 0
        for score in scores:
            pct = (score / max_score * 100) if max_score > 0 else 0
            if b_min <= pct < b_max:
                count += 1
            elif i == 0 and pct >= b_min:
                # 最高段: >= boundary
                count += 1

        segments.append({
            "label": label,
            "count": count,
            "percentage": round(count / n, 4) if n > 0 else 0,
            "boundary_min": b_min,
            "boundary_max": b_max,
        })

    return segments


async def get_segment_config(
    db: AsyncSession, school_id: str, subject_code: str | None = None,
) -> tuple[list[int], list[str]]:
    """获取分数段配置。优先科目覆盖，fallback 学校默认，最终 fallback 硬编码默认。"""
    if subject_code:
        result = await db.execute(
            select(ScoreSegmentConfig).where(
                ScoreSegmentConfig.school_id == school_id,
                ScoreSegmentConfig.subject_code == subject_code,
            )
        )
        cfg = result.scalar_one_or_none()
        if cfg:
            return cfg.boundaries, cfg.labels

    # fallback: 学校默认
    result = await db.execute(
        select(ScoreSegmentConfig).where(
            ScoreSegmentConfig.school_id == school_id,
            ScoreSegmentConfig.subject_code.is_(None),
        )
    )
    cfg = result.scalar_one_or_none()
    if cfg:
        return cfg.boundaries, cfg.labels

    return DEFAULT_BOUNDARIES, DEFAULT_LABELS


async def upsert_segment_config(
    db: AsyncSession,
    school_id: str,
    boundaries: list[int],
    labels: list[str],
    created_by: str | None = None,
    subject_code: str | None = None,
) -> ScoreSegmentConfig:
    """创建或更新分数段配置（upsert 语义）。"""
    if len(labels) != len(boundaries) + 1:
        raise ValidationError(f"labels 数量({len(labels)})必须比 boundaries({len(boundaries)})多 1")
    if boundaries != sorted(boundaries, reverse=True):
        raise ValidationError("boundaries 必须降序排列")
    if any(b < 0 or b > 100 for b in boundaries):
        raise ValidationError("boundaries 值必须在 0-100 之间")

    result = await db.execute(
        select(ScoreSegmentConfig).where(
            ScoreSegmentConfig.school_id == school_id,
            ScoreSegmentConfig.subject_code == subject_code
            if subject_code
            else ScoreSegmentConfig.subject_code.is_(None),
        )
    )
    cfg = result.scalar_one_or_none()

    if cfg:
        cfg.boundaries = boundaries
        cfg.labels = labels
    else:
        cfg = ScoreSegmentConfig(
            school_id=school_id,
            subject_code=subject_code,
            boundaries=boundaries,
            labels=labels,
            created_by=created_by,
        )
        db.add(cfg)

    await db.flush()
    return cfg


async def list_segment_configs(
    db: AsyncSession, school_id: str,
) -> list[ScoreSegmentConfig]:
    """列出学校所有分数段配置（默认 + 科目覆盖）。"""
    result = await db.execute(
        select(ScoreSegmentConfig).where(
            ScoreSegmentConfig.school_id == school_id,
        )
    )
    return list(result.scalars().all())
```

- [ ] **Step 4: 运行测试验证**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_segment_service.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: 写 CRUD 测试**

在 `tests/test_services_exam/test_segment_service.py` 追加：

```python
async def test_upsert_create_default(db, school):
    cfg = await upsert_segment_config(
        db, school_id=school.id,
        boundaries=[90, 75, 60],
        labels=["A", "B", "C", "D"],
    )
    await db.commit()
    assert cfg.subject_code is None
    assert cfg.boundaries == [90, 75, 60]


async def test_upsert_update_existing(db, school):
    await upsert_segment_config(db, school.id, [85, 70, 60], ["优", "���", "及", "不"])
    await db.commit()
    await upsert_segment_config(db, school.id, [90, 75, 60], ["A", "B", "C", "D"])
    await db.commit()
    configs = await list_segment_configs(db, school.id)
    defaults = [c for c in configs if c.subject_code is None]
    assert len(defaults) == 1
    assert defaults[0].boundaries == [90, 75, 60]


async def test_upsert_validation_labels_count(db, school):
    with pytest.raises(Exception, match="labels 数量"):
        await upsert_segment_config(db, school.id, [85, 70, 60], ["A", "B"])


async def test_upsert_validation_order(db, school):
    with pytest.raises(Exception, match="降序"):
        await upsert_segment_config(db, school.id, [60, 70, 85], ["A", "B", "C", "D"])


async def test_get_config_subject_override(db, school):
    await upsert_segment_config(db, school.id, [85, 70, 60], ["优", "良", "及", "不"])
    await db.commit()
    await upsert_segment_config(db, school.id, [90, 80, 60], ["A", "B", "C", "D"], subject_code="math")
    await db.commit()

    b, l = await get_segment_config(db, school.id, subject_code="math")
    assert b == [90, 80, 60]

    b2, l2 = await get_segment_config(db, school.id, subject_code="chinese")
    assert b2 == [85, 70, 60]  # fallback to school default


async def test_get_config_hardcoded_fallback(db, school):
    b, l = await get_segment_config(db, school.id)
    assert b == [85, 70, 60]
    assert l == ["优秀", "良好", "及格", "不及格"]
```

- [ ] **Step 6: 运行全部 segment 测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_segment_service.py -v`
Expected: 11 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/analytics/segment_service.py tests/test_services_exam/test_segment_service.py
git commit -m "feat(analytics): segment_service — CRUD + compute_segments"
```

**审查清单:**
- ✓ compute_segments 按百分比阈值正确分段
- ✓ get_segment_config 三级 fallback（科目→学校→硬编码）
- ✓ upsert 语义：存在则更新，不存在则创建
- ✓ 校验：labels 比 boundaries 多 1 / boundaries 降序 / 值在 0-100
- ✗ boundaries 非降序 → 抛 ValidationError
- ✗ labels 数量不匹配 → 抛 ValidationError

**边界条件:**
- 空 scores 列表 → 期望: 所有段 count=0, percentage=0
- max_score=0 → 期望: 所有分数 percentage=0，全部归入最低段
- 无配置的学校 → 期望: 返回硬编码默认值 [85,70,60]

---

## Task 3: 修改 exam_distribution 支持动态分数段

**Files:**
- Modify: `src/edu_cloud/modules/analytics/service.py:126-161`
- Test: `tests/test_services_exam/test_analytics.py` (扩展)

- [ ] **Step 1: 写动态分数段测试**

在 `tests/test_services_exam/test_analytics.py` 末尾追加：

```python
from edu_cloud.modules.analytics.segment_service import upsert_segment_config


async def test_exam_distribution_uses_school_config(db, analytics_data):
    """exam_distribution 应使用学校配置的分数段而非硬编码。"""
    school = analytics_data["school"]
    exam = analytics_data["exam"]
    # 配置学校分数段为 2 段: >=50 "通过" / <50 "不通过"
    await upsert_segment_config(
        db, school.id, boundaries=[50], labels=["通过", "不通过"],
    )
    await db.commit()

    from edu_cloud.modules.analytics.service import exam_distribution
    result = await exam_distribution(db, exam_id=exam.id, school_id=school.id)
    labels = [iv["label"] for iv in result["intervals"]]
    assert "通过" in labels
    assert "不通过" in labels
```

注意：此测试需要 `analytics_data` fixture，它已在文件中定义（包含 school, exam, subject, question, 3 students with scores 8/7/9）。

- [ ] **Step 2: 运行确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_analytics.py::test_exam_distribution_uses_school_config -v`
Expected: FAIL（当前返回硬编码 intervals，无 label 字段）

- [ ] **Step 3: 修改 exam_distribution**

修改 `src/edu_cloud/modules/analytics/service.py` 的 `exam_distribution` 函数，将硬编码 intervals 替换为动态配置：

```python
async def exam_distribution(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    await _verify_exam(db, exam_id, school_id)
    subjects = await _get_subjects(db, exam_id, school_id, visible_subject_codes, subject_id)
    subj_ids = [s.id for s in subjects]
    max_by_subject = await _get_max_by_subject(db, subj_ids, school_id)

    student_totals: dict[str, float] = {}
    total_max = sum(max_by_subject.get(s.id, 0.0) for s in subjects)
    for subj in subjects:
        scores = await get_effective_scores(db, subj.id, school_id, visible_class_ids)
        for s in scores:
            student_totals[s["student_id"]] = student_totals.get(s["student_id"], 0.0) + s["effective_score"]

    # 动态分数段配置
    subject_code = subjects[0].code if len(subjects) == 1 else None
    from edu_cloud.modules.analytics.segment_service import get_segment_config, compute_segments
    boundaries, labels = await get_segment_config(db, school_id, subject_code)

    values = list(student_totals.values())
    intervals = compute_segments(values, total_max, boundaries, labels)

    return {
        "exam_id": exam_id,
        "subject_id": subject_id,
        "intervals": intervals,
        "total_students": len(student_totals),
    }
```

- [ ] **Step 4: 运行测试验证**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_analytics.py -v`
Expected: 全部 PASS（新测试 + 旧测试兼容）

注意：旧测试检查的 `intervals` 格式从 `{range, count, percentage}` 变为 `{label, count, percentage, boundary_min, boundary_max}`。如果旧测试断言了 `range` 字段，需要更新断言。

- [ ] **Step 5: 修复旧测试断言（如需）**

检查 `tests/test_api_exam/test_analytics.py` 中 distribution 相关断言。将 `range` 字段断言改为 `label` 字段，或检查 `intervals` 列表长度。

- [ ] **Step 6: 运行全量 analytics 测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_analytics.py tests/test_api_exam/test_analytics.py tests/test_api_exam/test_analytics_class_filter.py tests/test_api_exam/test_analytics_subject_id.py -v`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/analytics/service.py tests/
git commit -m "feat(analytics): exam_distribution uses dynamic score segments"
```

**审查清单:**
- ✓ 无配置时行为与原始 5 档一致（hardcoded fallback）
- ✓ 有学校配置时使用学校配��
- ✓ 单科目查询时使用科目覆盖配置
- ✗ 旧测试断言格式不兼容 → 需更新

---

## Task 4: 分数段 API 路由

**Files:**
- Modify: `src/edu_cloud/modules/analytics/router.py`
- Test: `tests/test_api_exam/test_analytics_report.py`

- [ ] **Step 1: 写 API 测试**

```python
# tests/test_api_exam/test_analytics_report.py
"""分析报�� API 测试。"""
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole


@pytest.fixture
async def report_user(db):
    school = School(name="ReportSchool", code="RPT01")
    db.add(school)
    await db.commit()
    user = User(username="director", display_name="教务主任")
    user.set_password("123456")
    db.add(user)
    await db.commit()
    role = UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True)
    db.add(role)
    await db.commit()
    return {"user": user, "school": school, "role": role}


async def test_get_segment_config_default(client, report_user, db):
    """未配置时返回硬编码默认值。"""
    from edu_cloud.shared.auth import create_access_token
    token = create_access_token({"sub": report_user["user"].id, "role_id": report_user["role"].id})
    resp = await client.get(
        "/api/v1/analytics/segments/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["default"]["boundaries"] == [85, 70, 60]
    assert data["overrides"] == []


async def test_upsert_segment_config(client, report_user, db):
    from edu_cloud.shared.auth import create_access_token
    token = create_access_token({"sub": report_user["user"].id, "role_id": report_user["role"].id})
    resp = await client.put(
        "/api/v1/analytics/segments/config",
        json={"boundaries": [90, 75, 60], "labels": ["A", "B", "C", "D"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["boundaries"] == [90, 75, 60]

    # 验证持久���
    resp2 = await client.get(
        "/api/v1/analytics/segments/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.json()["default"]["boundaries"] == [90, 75, 60]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api_exam/test_analytics_report.py -v`
Expected: FAIL (404)

- [ ] **Step 3: 在 router.py 添加分数段路由**

在 `src/edu_cloud/modules/analytics/router.py` 末尾追加：

```python
from edu_cloud.modules.analytics.segment_service import (
    get_segment_config, upsert_segment_config, list_segment_configs,
)


@router.get("/segments/config")
async def get_segments_config(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
):
    """获取本校分数段配置（默认 + 科目覆盖列表）。"""
    role = current["current_role"]
    school_id = role.school_id
    configs = await list_segment_configs(db, school_id)
    default_cfg = next((c for c in configs if c.subject_code is None), None)
    overrides = [c for c in configs if c.subject_code is not None]
    return {
        "default": {
            "boundaries": default_cfg.boundaries if default_cfg else [85, 70, 60],
            "labels": default_cfg.labels if default_cfg else ["优秀", "良好", "及格", "不及格"],
        },
        "overrides": [
            {"subject_code": c.subject_code, "boundaries": c.boundaries, "labels": c.labels}
            for c in overrides
        ],
    }


@router.put("/segments/config")
async def update_segments_config(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
):
    """创建或更新分数段配置（upsert）。"""
    role = current["current_role"]
    user = current["user"]
    cfg = await upsert_segment_config(
        db,
        school_id=role.school_id,
        boundaries=body["boundaries"],
        labels=body["labels"],
        created_by=user.id,
        subject_code=body.get("subject_code"),
    )
    await db.commit()
    return {
        "subject_code": cfg.subject_code,
        "boundaries": cfg.boundaries,
        "labels": cfg.labels,
    }


@router.delete("/segments/config/{subject_code}")
async def delete_segment_override(
    subject_code: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
):
    """AR-05: 删除科目覆盖配置（硬删）。不允许删除学校默认。"""
    role = current["current_role"]
    from sqlalchemy import select as sa_select, delete as sa_delete
    from edu_cloud.models.score_segment import ScoreSegmentConfig as SSC
    result = await db.execute(
        sa_select(SSC).where(
            SSC.school_id == role.school_id,
            SSC.subject_code == subject_code,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(404, "配置不存在")
    await db.execute(
        sa_delete(SSC).where(SSC.id == cfg.id)
    )
    await db.commit()
    return {"deleted": subject_code}
```

- [ ] **Step 4: 运行测试验证**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api_exam/test_analytics_report.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/analytics/router.py tests/test_api_exam/test_analytics_report.py
git commit -m "feat(analytics): segment config GET/PUT API routes"
```

**审查清单:**
- ✓ GET 返回 default + overrides 结构
- ✓ PUT upsert 语��，支持 subject_code 可选
- ✓ academic_director 有 MANAGE_SCHOOL_SETTINGS 权限
- ✗ 无效 boundaries（非降序/超范围）→ 422 错误

---

## Task 5: report_service — 自定义分析构建器

**Files:**
- Create: `src/edu_cloud/modules/analytics/report_service.py`
- Test: `tests/test_services_exam/test_report_service.py`

- [ ] **Step 1: 写查询构建器测试**

```python
# tests/test_services_exam/test_report_service.py
"""分析报告 service 测试。"""
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, AIGradingResult
from edu_cloud.modules.student.models import Class, Student


@pytest.fixture
async def report_data(db):
    """创建学校 + 2 次考试 + 班级 + 学生 + 成绩。"""
    school = School(name="ReportSchool", code="RPT02")
    db.add(school)
    await db.commit()

    cls = Class(name="一班", grade="七年级", school_id=school.id)
    db.add(cls)
    await db.commit()

    students = []
    for i in range(3):
        s = Student(name=f"学生{i}", student_number=f"S{i:03d}", class_id=cls.id, school_id=school.id)
        db.add(s)
        students.append(s)
    await db.commit()

    user = User(username="rpt_teacher", display_name="T")
    user.set_password("p")
    db.add(user)
    await db.commit()

    exams = []
    from datetime import datetime
    for idx, (name, date) in enumerate([
        ("月考1", datetime(2026, 3, 15)),
        ("期中", datetime(2026, 4, 15)),
    ]):
        exam = Exam(name=name, school_id=school.id, exam_date=date)
        db.add(exam)
        await db.commit()
        subj = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
        db.add(subj)
        await db.commit()
        q = Question(subject_id=subj.id, name="Q1", question_type="objective", max_score=100.0, school_id=school.id)
        db.add(q)
        await db.commit()

        task = GradingTask(
            subject_id=subj.id, school_id=school.id,
            status="completed", total=3, completed=3, failed=0, created_by=user.id,
        )
        db.add(task)
        await db.commit()

        base_scores = [80, 70, 90] if idx == 0 else [85, 75, 88]
        for si, score in enumerate(base_scores):
            ans = StudentAnswer(
                exam_id=exam.id, subject_id=subj.id, student_id=students[si].id,
                question_id=q.id, image_path=f"/fake/{idx}_{si}.png", school_id=school.id,
            )
            db.add(ans)
            await db.flush()
            gr = AIGradingResult(
                answer_id=ans.id, question_id=q.id, score=float(score),
                max_score=100.0, school_id=school.id,
            )
            db.add(gr)
        await db.commit()

        exams.append({"exam": exam, "subject": subj, "question": q})

    return {"school": school, "class": cls, "students": students, "exams": exams, "user": user}


async def test_build_report_summary(db, report_data):
    from edu_cloud.modules.analytics.report_service import build_report
    result = await build_report(
        db,
        school_id=report_data["school"].id,
        exam_ids=[report_data["exams"][0]["exam"].id],
        metrics=["summary"],
    )
    assert "summary" in result["metrics"]
    summary = result["metrics"]["summary"]
    assert summary["total_students"] == 3


async def test_build_report_segments(db, report_data):
    from edu_cloud.modules.analytics.report_service import build_report
    result = await build_report(
        db,
        school_id=report_data["school"].id,
        exam_ids=[report_data["exams"][0]["exam"].id],
        metrics=["segments"],
    )
    assert "segments" in result["metrics"]
    intervals = result["metrics"]["segments"]["intervals"]
    assert len(intervals) == 4  # default 4 segments
```

- [ ] **Step 2: 运行确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_report_service.py::test_build_report_summary -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: 实现 report_service（核心 build_report）**

```python
# src/edu_cloud/modules/analytics/report_service.py
"""自定义分析构建器 + 跨考试对比 + PDF 导出。"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam, Subject
from edu_cloud.modules.analytics.service import (
    exam_summary, exam_distribution, grade_aggregates,
    subject_question_analysis, _get_subjects, _get_max_by_subject,
)
from edu_cloud.modules.analytics import get_effective_scores
from edu_cloud.modules.analytics.segment_service import get_segment_config, compute_segments
from edu_cloud.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def build_report(
    db: AsyncSession,
    school_id: str,
    exam_ids: list[str],
    metrics: list[str] | None = None,
    subject_codes: list[str] | None = None,
    class_ids: list[str] | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """自定义分析构建器：按指定维度聚合分析结���。"""
    all_metrics = metrics or ["summary", "segments", "ranking", "questions", "top_bottom"]
    result_metrics: dict = {}

    for exam_id in exam_ids:
        exam_result = await db.execute(
            select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
        )
        exam = exam_result.scalar_one_or_none()
        if not exam:
            raise NotFoundError(f"Exam {exam_id} not found")

    # 对第一个考试做分析（多考试时 summary/segments 取第一个，趋势走 trend API）
    primary_exam_id = exam_ids[0]

    effective_subject_codes = visible_subject_codes
    if subject_codes:
        if visible_subject_codes:
            effective_subject_codes = [c for c in subject_codes if c in visible_subject_codes]
        else:
            effective_subject_codes = subject_codes

    effective_class_ids = visible_class_ids
    if class_ids:
        if visible_class_ids:
            effective_class_ids = [c for c in class_ids if c in visible_class_ids]
        else:
            effective_class_ids = class_ids

    if "summary" in all_metrics:
        result_metrics["summary"] = await exam_summary(
            db, exam_id=primary_exam_id, school_id=school_id,
            visible_subject_codes=effective_subject_codes,
            visible_class_ids=effective_class_ids,
        )

    if "segments" in all_metrics:
        result_metrics["segments"] = await exam_distribution(
            db, exam_id=primary_exam_id, school_id=school_id,
            visible_subject_codes=effective_subject_codes,
            visible_class_ids=effective_class_ids,
        )

    if "ranking" in all_metrics:
        result_metrics["ranking"] = await grade_aggregates(
            db, exam_id=primary_exam_id, school_id=school_id,
            visible_subject_codes=effective_subject_codes,
            visible_class_ids=effective_class_ids,
        )

    if "questions" in all_metrics:
        subjects = await _get_subjects(db, primary_exam_id, school_id, effective_subject_codes)
        questions_data = []
        for subj in subjects:
            qa = await subject_question_analysis(
                db, subject_id=subj.id, school_id=school_id,
                visible_subject_codes=effective_subject_codes,
                visible_class_ids=effective_class_ids,
            )
            questions_data.append(qa)
        result_metrics["questions"] = questions_data

    if "top_bottom" in all_metrics:
        subjects = await _get_subjects(db, primary_exam_id, school_id, effective_subject_codes)
        student_totals: dict[str, float] = {}
        for subj in subjects:
            scores = await get_effective_scores(db, subj.id, school_id, effective_class_ids)
            for s in scores:
                student_totals[s["student_id"]] = student_totals.get(s["student_id"], 0) + s["effective_score"]

        ranked = sorted(student_totals.items(), key=lambda x: x[1], reverse=True)
        n = len(ranked)
        top_n = max(1, n // 10)
        result_metrics["top_bottom"] = {
            "top_10pct": [{"student_id": sid, "score": sc} for sid, sc in ranked[:top_n]],
            "bottom_10pct": [{"student_id": sid, "score": sc} for sid, sc in ranked[-top_n:]],
            "total_students": n,
        }

    return {
        "exam_ids": exam_ids,
        "metrics": result_metrics,
    }
```

- [ ] **Step 4: 运行测试验证**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_report_service.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/analytics/report_service.py tests/test_services_exam/test_report_service.py
git commit -m "feat(analytics): report_service — custom analysis builder"
```

**审查清单:**
- ✓ build_report 按 metrics 列表选择性执行
- ✓ subject_codes / class_ids 与 visible_* 交集后传递
- ✓ 不存在的 exam_id → NotFoundError
- ✗ exam_ids 为空列表 → 应提前返回空结果

**边界条件:**
- exam_ids 只有一个 → 期望: 正常返回单考试分析
- metrics 为空 → 期望: 默认全部指标
- 无成绩数据的考试 → 期望: summary 返回 total_students=0，不报错

---

## Task 6: report_service — 跨考试对比趋势

**Files:**
- Modify: `src/edu_cloud/modules/analytics/report_service.py`
- Test: `tests/test_services_exam/test_report_service.py` (扩展)

- [ ] **Step 1: 写趋势测试**

在 `tests/test_services_exam/test_report_service.py` 追加：

```python
async def test_grade_trend(db, report_data):
    from edu_cloud.modules.analytics.report_service import get_grade_trend
    exam_ids = [e["exam"].id for e in report_data["exams"]]
    result = await get_grade_trend(db, school_id=report_data["school"].id, exam_ids=exam_ids)
    assert len(result["points"]) == 2
    # 月考1 在前（日期更早）
    assert result["points"][0]["exam_name"] == "月考1"
    assert result["points"][1]["exam_name"] == "期中"
    # 期中均分更高 (85+75+88)/3=82.67 > (80+70+90)/3=80
    assert result["points"][1]["avg"] > result["points"][0]["avg"]


async def test_class_trend(db, report_data):
    from edu_cloud.modules.analytics.report_service import get_class_trend
    exam_ids = [e["exam"].id for e in report_data["exams"]]
    class_id = report_data["class"].id
    result = await get_class_trend(
        db, school_id=report_data["school"].id, exam_ids=exam_ids, class_id=class_id,
    )
    assert len(result["points"]) == 2
    assert all("class_avg" in p for p in result["points"])


async def test_student_trend(db, report_data):
    from edu_cloud.modules.analytics.report_service import get_student_trend
    exam_ids = [e["exam"].id for e in report_data["exams"]]
    student_id = report_data["students"][0].id
    result = await get_student_trend(
        db, school_id=report_data["school"].id, exam_ids=exam_ids, student_id=student_id,
    )
    assert len(result["points"]) == 2
    assert result["points"][0]["score"] == 80  # 月考1 score
    assert result["points"][1]["score"] == 85  # 期中 score
```

- [ ] **Step 2: 运行确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_report_service.py::test_grade_trend -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: 实现三个趋势函数**

在 `src/edu_cloud/modules/analytics/report_service.py` 末尾追加：

```python
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.models.agent_snapshot import ExamAnalysisSnapshot, ClassExamReport
from edu_cloud.modules.profile.models import StudentExamSnapshot


async def get_grade_trend(
    db: AsyncSession,
    school_id: str,
    exam_ids: list[str],
    subject_code: str | None = None,
    visible_subject_codes: list[str] | None = None,
) -> dict:
    """年级趋势：优先读 ExamAnalysisSnapshot（W1 预计算），无快照时实时聚合。"""
    exams = await _load_exams_sorted(db, school_id, exam_ids)
    boundaries, labels = await get_segment_config(db, school_id, subject_code)
    points = []

    for exam in exams:
        # AR-04: 优先读 W1 预计算快照
        snap_query = select(ExamAnalysisSnapshot).where(
            ExamAnalysisSnapshot.exam_id == exam.id,
            ExamAnalysisSnapshot.school_id == school_id,
            ExamAnalysisSnapshot.snapshot_type == "school_overview",
            ExamAnalysisSnapshot.status == "ready",
        )
        if subject_code:
            snap_query = snap_query.where(ExamAnalysisSnapshot.subject_code == subject_code)
        snap_result = await db.execute(snap_query)
        snapshot = snap_result.scalar_one_or_none()

        if snapshot and snapshot.metrics:
            m = snapshot.metrics
            points.append({
                "exam_id": exam.id,
                "exam_name": exam.name,
                "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
                "avg": m.get("avg"),
                "median": m.get("median"),
                "pass_rate": m.get("pass_rate"),
                "excellent_rate": m.get("excellent_rate"),
                "student_count": m.get("student_count", 0),
            })
            continue

        # Fallback: 实时聚合（无快照时）
        subjects = await _get_subjects(db, exam.id, school_id, visible_subject_codes)
        if subject_code:
            subjects = [s for s in subjects if s.code == subject_code]

        student_totals: dict[str, float] = {}
        total_max = 0.0
        for subj in subjects:
            max_by = await _get_max_by_subject(db, [subj.id], school_id)
            total_max += max_by.get(subj.id, 0.0)
            scores = await get_effective_scores(db, subj.id, school_id)
            for s in scores:
                student_totals[s["student_id"]] = student_totals.get(s["student_id"], 0) + s["effective_score"]

        values = list(student_totals.values())
        n = len(values)
        avg = round(sum(values) / n, 2) if n > 0 else 0
        segs = compute_segments(values, total_max, boundaries, labels)
        pass_rate = sum(s["count"] for s in segs[:-1]) / n if n > 0 else 0
        excellent_rate = segs[0]["count"] / n if n > 0 else 0

        points.append({
            "exam_id": exam.id,
            "exam_name": exam.name,
            "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
            "avg": avg,
            "median": round(sorted(values)[n // 2], 2) if n > 0 else 0,
            "pass_rate": round(pass_rate, 4),
            "excellent_rate": round(excellent_rate, 4),
            "student_count": n,
        })

    return {"points": points}


async def get_class_trend(
    db: AsyncSession,
    school_id: str,
    exam_ids: list[str],
    class_id: str,
    subject_code: str | None = None,
    visible_subject_codes: list[str] | None = None,
) -> dict:
    """班级趋势：优先读 ClassExamReport（W1 预计算），无快照时实时聚合。"""
    exams = await _load_exams_sorted(db, school_id, exam_ids)
    points = []

    for exam in exams:
        # AR-04: 优先读 W1 预计算 ClassExamReport
        # R3-F001: ClassExamReport 没有 subject_code 字段，只存总分口径。
        # 有 subject_code 过滤时必须跳过快照路径，直接走 fallback 实时聚合。
        report = None
        if not subject_code:
            report_result = await db.execute(
                select(ClassExamReport).where(
                    ClassExamReport.exam_id == exam.id,
                    ClassExamReport.school_id == school_id,
                    ClassExamReport.class_id == class_id,
                    ClassExamReport.status == "ready",
                )
            )
            report = report_result.scalar_one_or_none()

        if report:
            class_avg = report.class_avg or 0
            points.append({
                "exam_id": exam.id,
                "exam_name": exam.name,
                "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
                "class_avg": class_avg,
                "grade_avg": report.grade_avg,
                "grade_rank": report.grade_rank,
                "vs_prev": round(class_avg - points[-1]["class_avg"], 2) if points else None,
            })
            continue

        # Fallback: 实时聚合
        subjects = await _get_subjects(db, exam.id, school_id, visible_subject_codes)
        if subject_code:
            subjects = [s for s in subjects if s.code == subject_code]

        all_students: dict[str, float] = {}
        for subj in subjects:
            scores = await get_effective_scores(db, subj.id, school_id)
            for s in scores:
                all_students[s["student_id"]] = all_students.get(s["student_id"], 0) + s["effective_score"]

        student_ids = list(all_students.keys())
        student_class_map: dict[str, str] = {}
        if student_ids:
            result = await db.execute(
                select(Student.id, Student.class_id).where(Student.id.in_(student_ids))
            )
            student_class_map = {row.id: row.class_id for row in result.all()}

        class_values = [sc for sid, sc in all_students.items() if student_class_map.get(sid) == class_id]
        class_avg = round(sum(class_values) / len(class_values), 2) if class_values else 0
        all_values = list(all_students.values())
        grade_avg = round(sum(all_values) / len(all_values), 2) if all_values else 0

        class_avgs_map: dict[str, list] = {}
        for sid, score in all_students.items():
            cid = student_class_map.get(sid, "unknown")
            class_avgs_map.setdefault(cid, []).append(score)
        class_avg_sorted = sorted(
            [(cid, sum(scores) / len(scores)) for cid, scores in class_avgs_map.items()],
            key=lambda x: x[1], reverse=True,
        )
        grade_rank = next((i + 1 for i, (cid, _) in enumerate(class_avg_sorted) if cid == class_id), None)

        points.append({
            "exam_id": exam.id,
            "exam_name": exam.name,
            "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
            "class_avg": class_avg,
            "grade_avg": grade_avg,
            "grade_rank": grade_rank,
            "vs_prev": round(class_avg - points[-1]["class_avg"], 2) if points else None,
        })

    return {"class_id": class_id, "points": points}


async def get_student_trend(
    db: AsyncSession,
    school_id: str,
    exam_ids: list[str],
    student_id: str,
    subject_code: str | None = None,
    visible_subject_codes: list[str] | None = None,
) -> dict:
    """学生趋势：优先读 StudentExamSnapshot（pipeline 预计算），无快照时实时聚合。"""
    exams = await _load_exams_sorted(db, school_id, exam_ids)
    points = []

    for exam in exams:
        # AR-04: 优先读 pipeline 预计算的 StudentExamSnapshot
        snap_query = select(StudentExamSnapshot).where(
            StudentExamSnapshot.exam_id == exam.id,
            StudentExamSnapshot.student_id == student_id,
            StudentExamSnapshot.school_id == school_id,
        )
        if subject_code:
            snap_query = snap_query.where(StudentExamSnapshot.subject_code == subject_code)
        else:
            # AR2-R2-04: 无科目过滤时只取 _total 总分快照，避免 sum 各科重复计算
            snap_query = snap_query.where(StudentExamSnapshot.subject_code == "_total")
        snap_result = await db.execute(snap_query)
        snapshot = snap_result.scalar_one_or_none()

        if snapshot:
            # AR2-R2-05: 快照命中后补查 class_avg / grade_avg
            # R3-F001: ClassExamReport 没有 subject_code 字段（总分口径），
            # 有 subject_code 时只能从 ExamAnalysisSnapshot（有 subject_code）获取均值。
            from edu_cloud.modules.student.models import Student as StudentModel
            stu_row = await db.execute(
                select(StudentModel.class_id).where(StudentModel.id == student_id)
            )
            stu_class = stu_row.scalar_one_or_none()
            snap_class_avg = None
            snap_grade_avg = None
            if stu_class and not subject_code:
                # ClassExamReport 只有总分口径，仅无 subject_code 时可用
                cr_result = await db.execute(
                    select(ClassExamReport).where(
                        ClassExamReport.exam_id == exam.id,
                        ClassExamReport.school_id == school_id,
                        ClassExamReport.class_id == stu_class,
                        ClassExamReport.status == "ready",
                    )
                )
                cr = cr_result.scalar_one_or_none()
                if cr:
                    snap_class_avg = cr.class_avg
                    snap_grade_avg = cr.grade_avg
            if snap_grade_avg is None:
                ea_query = select(ExamAnalysisSnapshot).where(
                    ExamAnalysisSnapshot.exam_id == exam.id,
                    ExamAnalysisSnapshot.school_id == school_id,
                    ExamAnalysisSnapshot.snapshot_type == "school_overview",
                    ExamAnalysisSnapshot.status == "ready",
                )
                if subject_code:
                    ea_query = ea_query.where(ExamAnalysisSnapshot.subject_code == subject_code)
                ea_result = await db.execute(ea_query)
                ea = ea_result.scalar_one_or_none()
                if ea and ea.metrics:
                    snap_grade_avg = ea.metrics.get("avg")
            points.append({
                "exam_id": exam.id,
                "exam_name": exam.name,
                "exam_date": snapshot.exam_date.isoformat() if snapshot.exam_date else (exam.exam_date.isoformat() if exam.exam_date else None),
                "score": snapshot.total_score,
                "class_rank": snapshot.class_rank,
                "grade_rank": snapshot.grade_rank,
                "class_avg": snap_class_avg,
                "grade_avg": snap_grade_avg,
            })
            continue

        # Fallback: 实时聚合
        subjects = await _get_subjects(db, exam.id, school_id, visible_subject_codes)
        if subject_code:
            subjects = [s for s in subjects if s.code == subject_code]

        all_students: dict[str, float] = {}
        for subj in subjects:
            scores = await get_effective_scores(db, subj.id, school_id)
            for s in scores:
                all_students[s["student_id"]] = all_students.get(s["student_id"], 0) + s["effective_score"]

        student_score = all_students.get(student_id)
        if student_score is None:
            continue

        ranked = sorted(all_students.values(), reverse=True)
        grade_rank = ranked.index(student_score) + 1

        result = await db.execute(select(Student.class_id).where(Student.id == student_id))
        row = result.first()
        class_id = row.class_id if row else None
        class_rank = None
        class_avg = None
        if class_id:
            student_ids_list = list(all_students.keys())
            if student_ids_list:
                cls_result = await db.execute(
                    select(Student.id, Student.class_id).where(Student.id.in_(student_ids_list))
                )
                cls_map = {r.id: r.class_id for r in cls_result.all()}
                class_scores = sorted(
                    [sc for sid, sc in all_students.items() if cls_map.get(sid) == class_id],
                    reverse=True,
                )
                class_rank = class_scores.index(student_score) + 1 if student_score in class_scores else None
                class_avg = round(sum(class_scores) / len(class_scores), 2) if class_scores else None

        all_values = list(all_students.values())
        grade_avg = round(sum(all_values) / len(all_values), 2) if all_values else 0

        points.append({
            "exam_id": exam.id,
            "exam_name": exam.name,
            "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
            "score": student_score,
            "class_rank": class_rank,
            "grade_rank": grade_rank,
            "class_avg": class_avg,
            "grade_avg": grade_avg,
        })

    return {"student_id": student_id, "points": points}


async def _load_exams_sorted(
    db: AsyncSession, school_id: str, exam_ids: list[str],
) -> list[Exam]:
    """加载并按 exam_date 升序排列考试。"""
    result = await db.execute(
        select(Exam)
        .where(Exam.id.in_(exam_ids), Exam.school_id == school_id)
        .order_by(Exam.exam_date.asc())
    )
    exams = list(result.scalars().all())
    if len(exams) != len(exam_ids):
        found_ids = {e.id for e in exams}
        missing = [eid for eid in exam_ids if eid not in found_ids]
        raise NotFoundError(f"Exams not found: {missing}")
    return exams
```

- [ ] **Step 4: 运行测试验证**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_report_service.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/analytics/report_service.py tests/test_services_exam/test_report_service.py
git commit -m "feat(analytics): grade/class/student trend — cross-exam comparison"
```

**审查清单:**
- ✓ 三个趋势按 exam_date 升序排列
- ✓ class_trend 包含 vs_prev（与上次对比）
- ✓ class_trend 有 subject_code 时跳过 ClassExamReport 快照（R3-F001，总分口径不适用）
- ✓ student_trend 包含 class_rank + grade_rank
- ✓ student_trend 补查均值时按 subject_code 过滤 ExamAnalysisSnapshot（R3-F001）
- ✓ 缺失的 exam_id → NotFoundError
- ✗ 学生在某次考试无成绩 → 跳过该考试点

**边界条件:**
- 只有 1 次考试 → 期望: points 长度 1, vs_prev=None
- 学生在第 2 次考试无成绩 → 期望: points 长度 1（只有第 1 次）
- 空 exam_ids → 期望: NotFoundError

---

## Task 7: 报告 API 路由（query + trend + export）

**Files:**
- Modify: `src/edu_cloud/modules/analytics/router.py`
- Test: `tests/test_api_exam/test_analytics_report.py` (扩展)

- [ ] **Step 1: 写 API 测试**

在 `tests/test_api_exam/test_analytics_report.py` 追加：

```python
from datetime import datetime
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, AIGradingResult
from edu_cloud.modules.student.models import Class, Student


@pytest.fixture
async def report_exam_data(db, report_user):
    """创建考试数据用于报告测试。"""
    school = report_user["school"]
    user = report_user["user"]
    cls = Class(name="一班", grade="七年级", school_id=school.id)
    db.add(cls)
    await db.commit()

    stu = Student(name="张三", student_number="S001", class_id=cls.id, school_id=school.id)
    db.add(stu)
    await db.commit()

    exam = Exam(name="月考", school_id=school.id, exam_date=datetime(2026, 3, 15))
    db.add(exam)
    await db.commit()
    subj = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
    db.add(subj)
    await db.commit()
    q = Question(subject_id=subj.id, name="Q1", question_type="objective", max_score=100.0, school_id=school.id)
    db.add(q)
    await db.commit()

    task = GradingTask(subject_id=subj.id, school_id=school.id, status="completed", total=1, completed=1, failed=0, created_by=user.id)
    db.add(task)
    await db.commit()

    ans = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu.id, question_id=q.id, image_path="/fake.png", school_id=school.id)
    db.add(ans)
    await db.flush()
    gr = AIGradingResult(answer_id=ans.id, question_id=q.id, score=85.0, max_score=100.0, school_id=school.id)
    db.add(gr)
    await db.commit()

    return {"exam": exam, "subject": subj, "student": stu, "class": cls}


async def test_report_query(client, report_user, report_exam_data, db):
    from edu_cloud.shared.auth import create_access_token
    token = create_access_token({"sub": report_user["user"].id, "role_id": report_user["role"].id})
    resp = await client.post(
        "/api/v1/analytics/report/query",
        json={
            "exam_ids": [report_exam_data["exam"].id],
            "metrics": ["summary"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "summary" in resp.json()["metrics"]


async def test_grade_trend_api(client, report_user, report_exam_data, db):
    from edu_cloud.shared.auth import create_access_token
    token = create_access_token({"sub": report_user["user"].id, "role_id": report_user["role"].id})
    resp = await client.get(
        "/api/v1/analytics/report/trend/grade",
        params={"exam_ids": report_exam_data["exam"].id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["points"]) == 1


async def test_export_report(client, report_user, report_exam_data, db):
    from edu_cloud.shared.auth import create_access_token
    token = create_access_token({"sub": report_user["user"].id, "role_id": report_user["role"].id})
    resp = await client.post(
        "/api/v1/analytics/report/export",
        json={
            "exam_ids": [report_exam_data["exam"].id],
            "metrics": ["summary"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert "document_id" in resp.json()


# R3-F003: 负向测试 — invariant #4 metrics 角色白名单
async def test_report_query_restricted_metrics(client, db, report_exam_data):
    """parent/homeroom_teacher/subject_teacher 不能获取 ranking/top_bottom 指标。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User, UserRole
    from edu_cloud.shared.auth import create_access_token
    import uuid

    school = report_exam_data["class"].school_id  # reuse existing school
    # 创建 homeroom_teacher 用户
    ht_user = User(id=str(uuid.uuid4()), username="ht_test", display_name="班主任", hashed_password="x", is_active=True)
    db.add(ht_user)
    await db.flush()
    ht_role = UserRole(
        user_id=ht_user.id, role="homeroom_teacher", school_id=school,
        class_ids=[report_exam_data["class"].id], is_primary=True,
    )
    db.add(ht_role)
    await db.commit()

    token = create_access_token({"sub": ht_user.id, "role_id": ht_role.id})
    resp = await client.post(
        "/api/v1/analytics/report/query",
        json={
            "exam_ids": [report_exam_data["exam"].id],
            "metrics": ["summary", "ranking", "top_bottom"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    metrics = resp.json()["metrics"]
    # ranking 和 top_bottom 应被裁剪
    assert "ranking" not in metrics
    assert "top_bottom" not in metrics
    assert "summary" in metrics


# R3-F003: 负向测试 — invariant #2 学生可见性
async def test_student_trend_forbidden_for_other_class(client, db, report_exam_data):
    """科任教师请求非任教班学生的 trend/student → 应返回 403。"""
    from edu_cloud.models.user import User, UserRole
    from edu_cloud.modules.student.models import Class, Student
    from edu_cloud.shared.auth import create_access_token
    import uuid

    school_id = report_exam_data["class"].school_id
    # 创建另一个班级和学生
    other_cls = Class(name="二班", grade="七年级", school_id=school_id)
    db.add(other_cls)
    await db.commit()
    other_stu = Student(name="李四", student_number="S099", class_id=other_cls.id, school_id=school_id)
    db.add(other_stu)
    await db.commit()

    # 创建只能看一班的科任教师
    st_user = User(id=str(uuid.uuid4()), username="st_test", display_name="科任", hashed_password="x", is_active=True)
    db.add(st_user)
    await db.flush()
    st_role = UserRole(
        user_id=st_user.id, role="subject_teacher", school_id=school_id,
        class_ids=[report_exam_data["class"].id], is_primary=True,
    )
    db.add(st_role)
    await db.commit()

    token = create_access_token({"sub": st_user.id, "role_id": st_role.id})
    resp = await client.get(
        "/api/v1/analytics/report/trend/student",
        params={"exam_ids": report_exam_data["exam"].id, "student_id": other_stu.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: 运行确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api_exam/test_analytics_report.py::test_report_query -v`
Expected: FAIL (404)

- [ ] **Step 3: 在 router.py 添加报告路由**

在 `src/edu_cloud/modules/analytics/router.py` 末尾追加：

```python
from edu_cloud.modules.analytics.report_service import (
    build_report, get_grade_trend, get_class_trend, get_student_trend,
)
from edu_cloud.api.permissions import get_visible_subject_codes, get_visible_class_ids
from edu_cloud.services.studio_service import StudioService
from fastapi import HTTPException


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
    # AR-02: 角色 metrics 白名单 — 家长/科任不能看 ranking/top_bottom
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
async def grade_trend(
    exam_ids: str = Query(..., description="逗号分隔的考试 ID"),
    subject_code: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    # AR2-R2-03: 年级趋势仅限校长/教务/年级组长
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
async def class_trend(
    exam_ids: str = Query(...),
    class_id: str = Query(...),
    subject_code: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    role = current["current_role"]
    # AR2-R2-03: 家长不能查看班级趋势
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
async def student_trend(
    exam_ids: str = Query(...),
    student_id: str = Query(...),
    subject_code: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """AR-02: 显式校验 student_id 可见性（班级/家长 guardian）。"""
    role = current["current_role"]
    ids = [eid.strip() for eid in exam_ids.split(",") if eid.strip()]
    # 学生可见性校验
    vis_classes = get_visible_class_ids(role)
    if vis_classes is not None:
        from sqlalchemy import select as sa_select
        from edu_cloud.modules.student.models import Student
        stu_result = await db.execute(
            sa_select(Student.class_id).where(
                Student.id == student_id, Student.school_id == role.school_id
            )
        )
        stu_row = stu_result.first()
        if not stu_row or stu_row.class_id not in vis_classes:
            raise HTTPException(403, "无权查看该学生数据")
    # 家长：只能查自己孩子
    if role.role == "parent":
        from sqlalchemy import select as sa_select
        from edu_cloud.models.guardian import GuardianStudentLink
        guard_result = await db.execute(
            sa_select(GuardianStudentLink.id).where(
                GuardianStudentLink.guardian_user_id == current["user"].id,
                GuardianStudentLink.student_id == student_id,
            )
        )
        if not guard_result.scalar_one_or_none():
            raise HTTPException(403, "家长只能查看自己孩子的数据")
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

    # AR2-R2-01: export 路由同样需要按角色过滤 metrics
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

    # 获取考试��称用于标题
    from edu_cloud.modules.exam.models import Exam as ExamModel
    exam_result = await db.execute(select(ExamModel).where(ExamModel.id == exam_ids[0]))
    exam = exam_result.scalar_one_or_none()
    title = body.get("title") or f"{exam.name if exam else '考试'}分析报告"

    svc = StudioService(db)
    doc = await svc.create_document(
        type="analysis_report",
        title=title,
        content_json={
            "report_type": "exam_analysis",
            "config": {
                "exam_ids": exam_ids,
                "metrics": body.get("metrics"),
            },
            "sections": report_data["metrics"],
        },
        school_id=role.school_id,
        created_by=user.id,
    )
    # AR-03: 串起 Studio 状态流转 → reviewed → executed（跳过审批）
    await svc.transition(doc.id, "reviewed", user.id, school_id=role.school_id)
    await svc.transition(doc.id, "executed", user.id, school_id=role.school_id)
    await db.commit()
    # 刷新获取最新状态（含 pdf_url，由 transition→executed 触发渲染）
    doc = await svc.get_document(doc.id, school_id=role.school_id)

    return {
        "document_id": doc.id,
        "status": doc.status,
        "title": doc.title,
        "pdf_url": doc.pdf_url,
    }
```

添加缺失的 import（在文件顶部）：

```python
from edu_cloud.core.permissions import Permission
from edu_cloud.api.deps import require_permission
```

- [ ] **Step 4: 运行测试验证**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api_exam/test_analytics_report.py -v`
Expected: 7 tests PASS (含 R3-F003 新增的 2 个负向测试)

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/analytics/router.py tests/test_api_exam/test_analytics_report.py
git commit -m "feat(analytics): report query/trend/export API routes"
```

**审查清单:**
- ✓ POST /report/query 接受 exam_ids + metrics + filters
- ✓ GET /report/trend/{grade,class,student} 参数传递正确
- ✓ POST /report/export 创建 Studio Document
- ✓ class_trend 做可见班级权限检查
- ✗ 空 exam_ids → 422 错误
- ✗ homeroom_teacher 请求 ranking/top_bottom → 被裁剪（R3-F003 负向测试）
- ✗ subject_teacher 请求非任教班学生趋势 → 403（R3-F003 负向测试）

---

## Task 8: AI Agent 工具（3 个）

**Files:**
- Create: `src/edu_cloud/ai/tools/analytics_report.py`
- Modify: `src/edu_cloud/ai/tools/__init__.py`
- Test: `tests/test_ai/test_tools_analytics_report.py`

- [ ] **Step 1: 写工具测试**

```python
# tests/test_ai/test_tools_analytics_report.py
"""分析报告 AI 工具测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from edu_cloud.ai.tools.analytics_report import get_score_segments, compare_exams


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.db = AsyncMock()
    ctx.school_id = "school-1"
    ctx.subject_codes = None
    ctx.class_ids = None
    ctx.data_scope = None
    return ctx


async def test_compare_exams_missing_exam_ids(mock_ctx):
    """缺少 exam_ids 应返回明确错误（非空壳 ToolResult）。"""
    result = await compare_exams({"target_type": "grade"}, mock_ctx)
    assert result.success is False
    assert "exam_ids" in result.error


async def test_compare_exams_missing_target_id_for_class(mock_ctx):
    """class 维度缺 target_id → 错误。"""
    result = await compare_exams({"exam_ids": ["e1"], "target_type": "class"}, mock_ctx)
    assert result.success is False
    assert "target_id" in result.error


# R3-F004: generate_analysis_report 成功路径集成测试
async def test_generate_analysis_report_success(db, analytics_data):
    """generate_analysis_report 应创建 Studio Document 并完成状态流转。"""
    from unittest.mock import MagicMock
    from edu_cloud.ai.tools.analytics_report import generate_analysis_report

    school = analytics_data["school"]
    exam = analytics_data["exams"][0]["exam"]

    ctx = MagicMock()
    ctx.db = db
    ctx.school_id = school.id
    ctx.user_id = analytics_data["user"].id
    ctx.subject_codes = None
    ctx.class_ids = None

    result = await generate_analysis_report({"exam_ids": [exam.id]}, ctx)
    assert result.success is True
    assert "document_id" in result.data
    assert result.data["status"] == "executed"

    # 验证 Document 实际存在于数据库
    from sqlalchemy import select
    from edu_cloud.modules.studio.models import Document
    doc_row = await db.execute(
        select(Document).where(Document.id == result.data["document_id"])
    )
    doc = doc_row.scalar_one_or_none()
    assert doc is not None
    assert doc.status == "executed"
    assert doc.type == "analysis_report"
```

- [ ] **Step 2: 实现工具**

```python
# src/edu_cloud/ai/tools/analytics_report.py
"""分析报告 AI 工具（3 个）。L2_analytics 类别。"""
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@tools.register(
    name="get_score_segments",
    description="获取本校分数段配置，以及某次考试按分数段的学生分布。",
    category="L2_analytics",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "academic_director", "grade_leader", "homeroom_teacher"],
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
            "subject_code": {"type": "string", "description": "可选，科目代码（用科目覆盖配置）"},
        },
        "required": ["exam_id"],
    },
)
async def get_score_segments(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id", "")
    subject_code = input.get("subject_code")
    try:
        from edu_cloud.modules.analytics.segment_service import get_segment_config
        from edu_cloud.modules.analytics.service import exam_distribution

        boundaries, labels = await get_segment_config(ctx.db, ctx.school_id, subject_code)
        # R3-F002: subject_code 必须传给 exam_distribution，否则返回全科总分分布
        # 而非指定科目分布。通过 visible_subject_codes 限定为单科目实现过滤。
        effective_subject_codes = ctx.subject_codes
        if subject_code:
            if effective_subject_codes:
                effective_subject_codes = [c for c in effective_subject_codes if c == subject_code]
            else:
                effective_subject_codes = [subject_code]
        dist = await exam_distribution(
            ctx.db, exam_id=exam_id, school_id=ctx.school_id,
            visible_subject_codes=effective_subject_codes,
            visible_class_ids=ctx.class_ids,
        )
        return ToolResult(success=True, data={
            "config": {"boundaries": boundaries, "labels": labels},
            "distribution": dist,
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="compare_exams",
    description="跨考试对比趋势。支持年级/班级/学生三种维度。返回多次考试的趋势数据点。",
    category="L2_analytics",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "academic_director", "grade_leader", "homeroom_teacher"],
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    parameters={
        "type": "object",
        "properties": {
            "exam_ids": {"type": "array", "items": {"type": "string"}, "description": "考试 ID 列表（2+）"},
            "target_type": {"type": "string", "enum": ["grade", "class", "student"], "description": "对比维度"},
            "target_id": {"type": "string", "description": "class 维度传 class_id，student 维度传 student_id"},
            "subject_code": {"type": "string", "description": "可选，按科目过滤"},
        },
        "required": ["exam_ids", "target_type"],
    },
)
async def compare_exams(input: dict, ctx: ToolContext) -> ToolResult:
    exam_ids = input.get("exam_ids", [])
    target_type = input.get("target_type", "grade")
    target_id = input.get("target_id")
    subject_code = input.get("subject_code")

    if not exam_ids:
        return ToolResult(success=False, error="需要提供 exam_ids")

    try:
        from edu_cloud.modules.analytics.report_service import (
            get_grade_trend, get_class_trend, get_student_trend,
        )

        if target_type == "grade":
            data = await get_grade_trend(
                ctx.db, ctx.school_id, exam_ids, subject_code,
                visible_subject_codes=ctx.subject_codes,
            )
        elif target_type == "class":
            if not target_id:
                return ToolResult(success=False, error="class 维度需要提供 target_id (class_id)")
            if ctx.class_ids is not None and target_id not in ctx.class_ids:
                return ToolResult(success=False, error="无权访问该班级")
            data = await get_class_trend(
                ctx.db, ctx.school_id, exam_ids, target_id, subject_code,
                visible_subject_codes=ctx.subject_codes,
            )
        elif target_type == "student":
            if not target_id:
                return ToolResult(success=False, error="student 维度需要提供 target_id (student_id)")
            data = await get_student_trend(
                ctx.db, ctx.school_id, exam_ids, target_id, subject_code,
                visible_subject_codes=ctx.subject_codes,
            )
        else:
            return ToolResult(success=False, error=f"不支持的 target_type: {target_type}")

        return ToolResult(success=True, data=data)
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="generate_analysis_report",
    description="生成考试分析报告文档（PDF）。创建 Studio 文档，可通过文档中心下载。",
    category="L2_analytics",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "academic_director", "grade_leader"],
    risk_level="medium",
    is_read_only=False,
    sensitivity="school",
    parameters={
        "type": "object",
        "properties": {
            "exam_ids": {"type": "array", "items": {"type": "string"}, "description": "考试 ID 列表"},
            "metrics": {"type": "array", "items": {"type": "string"}, "description": "可选，指标列表"},
            "title": {"type": "string", "description": "可选，报告标题"},
        },
        "required": ["exam_ids"],
    },
)
async def generate_analysis_report(input: dict, ctx: ToolContext) -> ToolResult:
    exam_ids = input.get("exam_ids", [])
    if not exam_ids:
        return ToolResult(success=False, error="需要提供 exam_ids")

    try:
        from edu_cloud.modules.analytics.report_service import build_report
        from edu_cloud.services.studio_service import StudioService
        from sqlalchemy import select
        from edu_cloud.modules.exam.models import Exam

        report_data = await build_report(
            ctx.db, school_id=ctx.school_id, exam_ids=exam_ids,
            metrics=input.get("metrics"),
            visible_subject_codes=ctx.subject_codes,
            visible_class_ids=ctx.class_ids,
        )

        exam_result = await ctx.db.execute(select(Exam).where(Exam.id == exam_ids[0]))
        exam = exam_result.scalar_one_or_none()
        title = input.get("title") or f"{exam.name if exam else '考试'}分析报告"

        svc = StudioService(ctx.db)
        user_id = ctx.user_id if hasattr(ctx, "user_id") else "agent"
        doc = await svc.create_document(
            type="analysis_report",
            title=title,
            content_json={
                "report_type": "exam_analysis",
                "config": {"exam_ids": exam_ids, "metrics": input.get("metrics")},
                "sections": report_data["metrics"],
            },
            school_id=ctx.school_id,
            created_by=user_id,
        )
        # AR2-R2-06: 与 HTTP export 路由一致，串起 Studio 状态流转
        await svc.transition(doc.id, "reviewed", user_id, school_id=ctx.school_id)
        await svc.transition(doc.id, "executed", user_id, school_id=ctx.school_id)
        await ctx.db.commit()

        return ToolResult(success=True, data={
            "document_id": doc.id,
            "title": doc.title,
            "status": "executed",
            "message": f"报告「{title}」已创建并完成状态流转，可在文档中心查看和导�� PDF",
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))
```

- [ ] **Step 3: 在 tools/__init__.py 注册**

在 `src/edu_cloud/ai/tools/__init__.py` 的导入列表中添加：

```python
import edu_cloud.ai.tools.analytics_report  # noqa: F401  — 分析报告（3 tools）
```

- [ ] **Step 4: 运行测试验证**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tools_analytics_report.py -v`
Expected: 3 tests PASS (含 R3-F004 新增的 generate_analysis_report 成功路径测试)

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/ai/tools/analytics_report.py src/edu_cloud/ai/tools/__init__.py tests/test_ai/test_tools_analytics_report.py
git commit -m "feat(analytics): 3 AI agent tools — segments/compare/report"
```

**审查清单:**
- ✓ get_score_segments 返回配置 + 分布，subject_code 正确传递给 exam_distribution（R3-F002）
- ✓ compare_exams 支持 grade/class/student 三维度
- ✓ generate_analysis_report 创建 Studio 文档并完成状态流转（R3-F004 集成测试覆盖）
- ✓ 权限通过 ctx.class_ids / ctx.subject_codes 裁剪
- ✗ 缺 exam_ids → 返回 error ToolResult
- ✗ class 维度缺 target_id → 返回 error ToolResult

**边界条件:**
- 缺 exam_ids → 期望: success=False, error 含 "exam_ids"
- class 维度无 target_id → 期望: success=False, error 含 "target_id"
- 无效 target_type → 期望: success=False, error 含 "不支持"

**测试契约:**
1. compare_exams 缺 exam_ids 返回错误
   - 入口: `compare_exams({"target_type": "grade"}, ctx)`
   - 反例: 错误实现可能忽略空 exam_ids 后抛未捕获异常而非返回 error ToolResult
   - 边界: 空列表 / 缺键
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_tools_analytics_report.py::test_compare_exams_missing_exam_ids -v`
2. compare_exams class 维度缺 target_id 返回错误
   - 入口: `compare_exams({"exam_ids": ["e1"], "target_type": "class"}, ctx)`
   - 反例: 错误实现可能用 None 作为 class_id 查询全量数据
   - 边界: target_id 为空字符串 / 缺键
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_tools_analytics_report.py::test_compare_exams_missing_target_id_for_class -v`
3. generate_analysis_report 成功路径创建文档并流转状态（R3-F004）
   - 入口: `generate_analysis_report({"exam_ids": [exam.id]}, ctx)` 使用真实 db fixture
   - 反例: 错误实现可能创建文档但不调用 transition，导致 status 停留在 draft
   - 边界: 单考试 / 无自定义 title（使用默认标题）
   - 回归: N/A
   - 命令: `pytest tests/test_ai/test_tools_analytics_report.py::test_generate_analysis_report_success -v`

---

## Task 9: 前端 — API 层 + 路由 + 侧栏

**Files:**
- Modify: `frontend/src/api/analytics.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/config/sidebarConfig.js`

- [ ] **Step 1: 扩展 API 层**

```javascript
// frontend/src/api/analytics.js — 追加
export const getSegmentConfig = () => client.get('/analytics/segments/config')
export const updateSegmentConfig = (data) => client.put('/analytics/segments/config', data)

export const queryReport = (data) => client.post('/analytics/report/query', data)
export const getGradeTrend = (params) => client.get('/analytics/report/trend/grade', { params })
export const getClassTrend = (params) => client.get('/analytics/report/trend/class', { params })
export const getStudentTrend = (params) => client.get('/analytics/report/trend/student', { params })
export const exportReport = (data) => client.post('/analytics/report/export', data)
```

- [ ] **Step 2: 添加路由**

在 `frontend/src/router/index.js` 的 `children` ���组中，Analytics 路由之后添加：

```javascript
// Analytics report
{ path: 'analytics/report', name: 'AnalyticsReport', component: () => import('../pages/AnalyticsReportPage.vue'), meta: { permissions: ['view_scores'] } },
{ path: 'analytics/trend', name: 'AnalyticsTrend', component: () => import('../pages/AnalyticsTrendPage.vue'), meta: { permissions: ['view_scores'] } },
```

- [ ] **Step 3: 添加侧栏项**

在 `frontend/src/config/sidebarConfig.js` 中，为 principal / academic_director / grade_leader / homeroom_teacher / subject_teacher 的 `数据分析` / `成绩分析` 项之后添加：

```javascript
{ icon: 'report', label: '分析报���', route: '/analytics/report', moduleCode: 'study_analytics' },
{ icon: 'trend', label: '成绩趋势', route: '/analytics/trend', moduleCode: 'study_analytics' },
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/analytics.js frontend/src/router/index.js frontend/src/config/sidebarConfig.js
git commit -m "feat(frontend): analytics report routes + sidebar + API layer"
```

---

## Task 10: 前端 — AnalyticsReportPage.vue

**Files:**
- Create: `frontend/src/pages/AnalyticsReportPage.vue`
- Test: `frontend/src/pages/__tests__/AnalyticsReportPage.test.js`

- [ ] **Step 1: 创建页面组件**

```vue
<!-- frontend/src/pages/AnalyticsReportPage.vue -->
<template>
  <div class="analytics-report">
    <n-card title="分析报告">
      <!-- 查询面板 -->
      <n-space vertical :size="16">
        <n-space>
          <n-select
            v-model:value="selectedExamIds"
            :options="examOptions"
            multiple
            placeholder="选择考试（可多选）"
            style="min-width: 300px"
          />
          <n-select
            v-model:value="selectedMetrics"
            :options="metricOptions"
            multiple
            placeholder="选择指标"
            style="min-width: 200px"
          />
          <n-button type="primary" @click="runQuery" :loading="loading">
            生成分析
          </n-button>
          <n-button @click="handleExport" :loading="exporting" :disabled="!reportData">
            导出 PDF
          </n-button>
        </n-space>

        <!-- 结果区域 -->
        <template v-if="reportData">
          <n-tabs type="line">
            <n-tab-pane v-if="reportData.metrics.summary" name="summary" tab="总览">
              <n-descriptions bordered :column="3">
                <n-descriptions-item label="参考人数">
                  {{ reportData.metrics.summary.total_students }}
                </n-descriptions-item>
                <n-descriptions-item
                  v-for="subj in reportData.metrics.summary.subjects || []"
                  :key="subj.subject_id"
                  :label="subj.subject_name + ' 均分'"
                >
                  {{ subj.avg_score }}
                </n-descriptions-item>
              </n-descriptions>
            </n-tab-pane>

            <n-tab-pane v-if="reportData.metrics.segments" name="segments" tab="分数段分布">
              <v-chart :option="segmentChartOption" style="height: 400px" />
            </n-tab-pane>

            <n-tab-pane v-if="reportData.metrics.ranking" name="ranking" tab="班级排名">
              <n-data-table
                :columns="rankingColumns"
                :data="reportData.metrics.ranking.class_rankings || []"
                :pagination="false"
              />
            </n-tab-pane>

            <n-tab-pane v-if="reportData.metrics.top_bottom" name="top_bottom" tab="尖子生/临界生">
              <n-space vertical>
                <n-card title="前 10%">
                  <n-data-table
                    :columns="topColumns"
                    :data="reportData.metrics.top_bottom.top_10pct"
                    :pagination="false"
                    size="small"
                  />
                </n-card>
                <n-card title="后 10%">
                  <n-data-table
                    :columns="topColumns"
                    :data="reportData.metrics.top_bottom.bottom_10pct"
                    :pagination="false"
                    size="small"
                  />
                </n-card>
              </n-space>
            </n-tab-pane>
          </n-tabs>
        </template>
      </n-space>
    </n-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { queryReport, exportReport } from '../api/analytics'
import client from '../api/client'

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const message = useMessage()
const loading = ref(false)
const exporting = ref(false)
const reportData = ref(null)
const selectedExamIds = ref([])
const selectedMetrics = ref(['summary', 'segments', 'ranking'])
const examOptions = ref([])

const metricOptions = [
  { label: '考试总览', value: 'summary' },
  { label: '分数段分布', value: 'segments' },
  { label: '班级排名', value: 'ranking' },
  { label: '题目分析', value: 'questions' },
  { label: '尖子生/临界生', value: 'top_bottom' },
]

const rankingColumns = [
  { title: '排名', key: 'rank' },
  { title: '班级', key: 'class_name' },
  { title: '均分', key: 'avg_score' },
  { title: '人数', key: 'student_count' },
]

const topColumns = [
  { title: '学生', key: 'student_id' },
  { title: '总分', key: 'score' },
]

const segmentChartOption = computed(() => {
  const segments = reportData.value?.metrics?.segments?.intervals || []
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: segments.map(s => s.label) },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: segments.map(s => s.count),
      itemStyle: { color: '#63e2b7' },
    }],
  }
})

onMounted(async () => {
  try {
    const resp = await client.get('/exams')
    examOptions.value = (resp.data || []).map(e => ({
      label: e.name,
      value: e.id,
    }))
  } catch { /* ignore */ }
})

async function runQuery() {
  if (!selectedExamIds.value.length) {
    message.warning('请至少选择一次考试')
    return
  }
  loading.value = true
  try {
    const resp = await queryReport({
      exam_ids: selectedExamIds.value,
      metrics: selectedMetrics.value,
    })
    reportData.value = resp.data
  } catch (e) {
    message.error(e.response?.data?.detail || '查询失败')
  } finally {
    loading.value = false
  }
}

async function handleExport() {
  exporting.value = true
  try {
    const resp = await exportReport({
      exam_ids: selectedExamIds.value,
      metrics: selectedMetrics.value,
    })
    message.success(`报告已创建: ${resp.data.title}，可在文档中心查看`)
  } catch (e) {
    message.error(e.response?.data?.detail || '导出失败')
  } finally {
    exporting.value = false
  }
}
</script>
```

- [ ] **Step 2: 写 Vitest 测试**

```javascript
// frontend/src/pages/__tests__/AnalyticsReportPage.test.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import AnalyticsReportPage from '../AnalyticsReportPage.vue'

vi.mock('../../api/analytics', () => ({
  queryReport: vi.fn(),
  exportReport: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: [] }) },
}))

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div />', props: ['option'] },
}))

describe('AnalyticsReportPage', () => {
  it('renders query controls', () => {
    const wrapper = mount(AnalyticsReportPage, {
      global: { plugins: [createPinia()], stubs: { 'n-card': true, 'n-space': true, 'n-select': true, 'n-button': true, 'n-tabs': true } },
    })
    expect(wrapper.html()).toContain('分析报告')
  })
})
```

- [ ] **Step 3: 运行前端测试**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/pages/__tests__/AnalyticsReportPage.test.js`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AnalyticsReportPage.vue frontend/src/pages/__tests__/AnalyticsReportPage.test.js
git commit -m "feat(frontend): AnalyticsReportPage — query builder + chart + export"
```

---

## Task 11: 前端 — AnalyticsTrendPage.vue

**Files:**
- Create: `frontend/src/pages/AnalyticsTrendPage.vue`

- [ ] **Step 1: 创建趋势页面**

```vue
<!-- frontend/src/pages/AnalyticsTrendPage.vue -->
<template>
  <div class="analytics-trend">
    <n-card title="成绩趋势">
      <n-space vertical :size="16">
        <n-space>
          <n-select
            v-model:value="selectedExamIds"
            :options="examOptions"
            multiple
            placeholder="选择考试（至少2次）"
            style="min-width: 300px"
          />
          <n-radio-group v-model:value="dimension">
            <n-radio-button value="grade">年级</n-radio-button>
            <n-radio-button value="class">班级</n-radio-button>
            <n-radio-button value="student">学生</n-radio-button>
          </n-radio-group>
          <n-select
            v-if="dimension === 'class'"
            v-model:value="selectedClassId"
            :options="classOptions"
            placeholder="选择班级"
            style="min-width: 150px"
          />
          <n-select
            v-if="dimension === 'student'"
            v-model:value="selectedStudentId"
            :options="studentOptions"
            placeholder="选择学生"
            filterable
            style="min-width: 150px"
          />
          <n-button type="primary" @click="loadTrend" :loading="loading">
            查看趋势
          </n-button>
        </n-space>

        <v-chart v-if="chartOption" :option="chartOption" style="height: 400px" />
      </n-space>
    </n-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { getGradeTrend, getClassTrend, getStudentTrend } from '../api/analytics'
import client from '../api/client'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const message = useMessage()
const loading = ref(false)
const selectedExamIds = ref([])
const dimension = ref('grade')
const selectedClassId = ref(null)
const selectedStudentId = ref(null)
const examOptions = ref([])
const classOptions = ref([])
const studentOptions = ref([])
const trendData = ref(null)

const chartOption = computed(() => {
  if (!trendData.value?.points?.length) return null
  const points = trendData.value.points
  const xData = points.map(p => p.exam_name)

  if (dimension.value === 'grade') {
    return {
      tooltip: { trigger: 'axis' },
      legend: {},
      xAxis: { type: 'category', data: xData },
      yAxis: { type: 'value' },
      series: [
        { name: '均分', type: 'line', data: points.map(p => p.avg), smooth: true },
        { name: '及格率', type: 'line', data: points.map(p => (p.pass_rate * 100).toFixed(1)), yAxisIndex: 0 },
      ],
    }
  } else if (dimension.value === 'class') {
    return {
      tooltip: { trigger: 'axis' },
      legend: {},
      xAxis: { type: 'category', data: xData },
      yAxis: { type: 'value' },
      series: [
        { name: '班级均分', type: 'line', data: points.map(p => p.class_avg), smooth: true },
        { name: '年级均分', type: 'line', data: points.map(p => p.grade_avg), smooth: true, lineStyle: { type: 'dashed' } },
      ],
    }
  } else {
    return {
      tooltip: { trigger: 'axis' },
      legend: {},
      xAxis: { type: 'category', data: xData },
      yAxis: { type: 'value' },
      series: [
        { name: '得分', type: 'line', data: points.map(p => p.score), smooth: true },
        { name: '班级均分', type: 'line', data: points.map(p => p.class_avg), smooth: true, lineStyle: { type: 'dashed' } },
      ],
    }
  }
})

onMounted(async () => {
  try {
    const resp = await client.get('/exams')
    examOptions.value = (resp.data || []).map(e => ({ label: e.name, value: e.id }))
  } catch { /* ignore */ }
  try {
    const resp = await client.get('/classes')
    classOptions.value = (resp.data || []).map(c => ({ label: c.name, value: c.id }))
  } catch { /* ignore */ }
})

async function loadTrend() {
  if (selectedExamIds.value.length < 1) {
    message.warning('请至少选择一次考试')
    return
  }
  loading.value = true
  try {
    const examIdsStr = selectedExamIds.value.join(',')
    let resp
    if (dimension.value === 'grade') {
      resp = await getGradeTrend({ exam_ids: examIdsStr })
    } else if (dimension.value === 'class') {
      if (!selectedClassId.value) { message.warning('请选择班级'); return }
      resp = await getClassTrend({ exam_ids: examIdsStr, class_id: selectedClassId.value })
    } else {
      if (!selectedStudentId.value) { message.warning('请选择学生'); return }
      resp = await getStudentTrend({ exam_ids: examIdsStr, student_id: selectedStudentId.value })
    }
    trendData.value = resp.data
  } catch (e) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/AnalyticsTrendPage.vue
git commit -m "feat(frontend): AnalyticsTrendPage — cross-exam trend charts"
```

---

## Task 12: 前端 — ScoreSegmentSettings 组件 + 嵌入学校配置页

**Files:**
- Create: `frontend/src/components/analytics/ScoreSegmentSettings.vue`
- Modify: `frontend/src/pages/SchoolSettingsPage.vue`

- [ ] **Step 1: 创建分数段设置组件**

```vue
<!-- frontend/src/components/analytics/ScoreSegmentSettings.vue -->
<template>
  <n-space vertical :size="16">
    <n-card title="学校默认分数段">
      <n-space vertical>
        <n-dynamic-input
          v-model:value="defaultConfig.boundaries"
          :on-create="() => 60"
          placeholder="阈值（如 85）"
        >
          <template #default="{ value, index }">
            <n-input-number
              :value="value"
              @update:value="v => defaultConfig.boundaries[index] = v"
              :min="0" :max="100"
              style="width: 120px"
            />
          </template>
        </n-dynamic-input>
        <n-dynamic-input
          v-model:value="defaultConfig.labels"
          :on-create="() => ''"
          placeholder="标签（如 优秀）"
        />
        <n-button type="primary" @click="saveDefault" :loading="saving" size="small">
          保存
        </n-button>
      </n-space>
    </n-card>

    <n-card title="科目覆盖" v-if="overrides.length">
      <n-data-table :columns="overrideColumns" :data="overrides" :pagination="false" size="small" />
    </n-card>
  </n-space>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { getSegmentConfig, updateSegmentConfig } from '../../api/analytics'

const message = useMessage()
const saving = ref(false)
const defaultConfig = ref({ boundaries: [85, 70, 60], labels: ['优秀', '良好', '及格', '不及格'] })
const overrides = ref([])

const overrideColumns = [
  { title: '科目', key: 'subject_code' },
  { title: '阈值', key: 'boundaries', render: row => row.boundaries.join(', ') },
  { title: '标签', key: 'labels', render: row => row.labels.join(', ') },
]

onMounted(async () => {
  try {
    const resp = await getSegmentConfig()
    defaultConfig.value = resp.data.default
    overrides.value = resp.data.overrides
  } catch { /* use defaults */ }
})

async function saveDefault() {
  saving.value = true
  try {
    await updateSegmentConfig({
      boundaries: defaultConfig.value.boundaries,
      labels: defaultConfig.value.labels,
    })
    message.success('保存成功')
  } catch (e) {
    message.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>
```

- [ ] **Step 2: 在 SchoolSettingsPage 中引入**

在 `frontend/src/pages/SchoolSettingsPage.vue` 的 `<n-tabs>` 中添加新 Tab：

```vue
<n-tab-pane name="segments" tab="分数段">
  <ScoreSegmentSettings />
</n-tab-pane>
```

在 `<script setup>` 中添加导入：

```javascript
import ScoreSegmentSettings from '../components/analytics/ScoreSegmentSettings.vue'
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/analytics/ScoreSegmentSettings.vue frontend/src/pages/SchoolSettingsPage.vue
git commit -m "feat(frontend): ScoreSegmentSettings component + embed in SchoolSettingsPage"
```

---

## Task 13: 全量测试 + 收尾

**Files:** 无新增

- [ ] **Step 1: 运行全量后端测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: 全部 PASS，预期新增 ~20 tests

- [ ] **Step 2: 运行全量前端测试**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
Expected: 全部 PASS

- [ ] **Step 3: 验证新增路由数**

Run: `cd C:/Users/Administrator/edu-cloud && python -c "from edu_cloud.api.app import create_app; app = create_app(); print(len([r for r in app.routes if hasattr(r, 'path')]))" 2>/dev/null || echo "manual check needed"`

预期：原 164 路由 + 7 新增 = ~171 路由

- [ ] **Step 4: 最终 Commit（如有遗漏修复）**

```bash
git add -A && git status
# 如有未提交文件，按需 commit
```

**审查清单:**
- ✓ 全量后端测试通过
- ✓ 全量前端测试通过
- ✓ 新增路由可达
- ✓ 侧栏显示分析报告 / 成绩趋势
- ✓ Alembic migration 可执行
