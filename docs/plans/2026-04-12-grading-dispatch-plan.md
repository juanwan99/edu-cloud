# 阅卷调度全流程改造实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将阅卷调度页面改造为全流程调度中心，串通 分割→选择题判分→AI 阅卷→教师校对 的完整链路。

**Architecture:** 扩展现有 pipeline_service 增加选择题识别，新增科目阅卷状态聚合 API，重写前端页面为以考试为主维度的科目列表。

**Tech Stack:** FastAPI + SQLAlchemy (async) / Vue 3 + Naive UI / OpenCV fillmark / pytest + Vitest

**Design:** `docs/plans/2026-04-12-grading-dispatch-design.md`

---

## Contract Pack

```yaml
contract_pack:
  invariants:
    - id: INV-001
      statement: "选择题判分结果与 scan/router.py upload_objective 的判分逻辑完全一致（大小写不敏感、排序不敏感）"
      verification: pending_test
      test_ref: tests/test_services_exam/test_objective_grading.py::TestGradeObjectiveAnswer

    - id: INV-002
      statement: "choice_group 到 Question 的映射必须通过 (group_id, 组内行号) 精确定位，不依赖全局枚举顺序"
      verification: pending_test
      test_ref: tests/test_api_exam/test_pipeline_save_objective.py::TestBuildPipelineSaveObjectiveFn

    - id: INV-003
      statement: "dispatch/status 的 ready 阶段判定条件与 POST /grading/tasks 的前置校验一致（需主观题 + Rubric + 主观题 StudentAnswer）"
      verification: pending_test
      test_ref: tests/test_api_exam/test_dispatch_status.py::TestDispatchStatus

    - id: INV-004
      statement: "pipeline 多科目队列串行执行，stop 传播到整个队列而非仅当前科目"
      verification: pending_test
      test_ref: tests/test_services_exam/test_pipeline_queue.py::TestPipelineQueue

    - id: INV-005
      statement: "ExamDetailPage 扫描 tab 移除后，前端路由和已有 Vitest 不出现回归"
      verification: pending_test
      test_ref: frontend/src/__tests__/router.test.js

  counter_examples:
    - id: CE-001
      description: "选择题 question_index 使用全局 enumerate 而非 group-scoped 映射，导致多题组时写错 question_id"
      tests_that_still_pass: "test_correct_single, test_incorrect_single（单组场景下碰巧正确）"
      mitigation: "build_pipeline_save_objective_fn 的映射 key 为 (group_id, row_index) 二元组，测试覆盖多题组场景"

    - id: CE-002
      description: "dispatch/status 用 answer_count>0 判 ready，但科目只有选择题答案时用户点 AI 阅卷得到 400"
      tests_that_still_pass: "test_idle_stage（空数据场景通过）"
      mitigation: "ready 判定改为检查 subjective_answer_count>0 且 has_rubric，与 create_grading_task 前置校验共享逻辑"

    - id: CE-003
      description: "GradingTask status=failed 被 else 分支折叠成 done，用户看不到失败状态"
      tests_that_still_pass: "test_ready_stage_after_answers（不涉及 GradingTask）"
      mitigation: "新增 failed 阶段，dispatch/status 显式处理 GradingTask.status=failed"

  risk_modules:
    - module: "src/edu_cloud/modules/scan/pipeline_service.py"
      reason: "新增选择题识别 + 多科目队列，核心 IO 路径变更"
    - module: "src/edu_cloud/modules/scan/pipeline_router.py"
      reason: "HTTP 入口接入队列语义，start/progress/stop 行为变更"
    - module: "src/edu_cloud/modules/grading/router.py"
      reason: "新增 public API GET /grading/dispatch/status"
    - module: "src/edu_cloud/modules/scan/objective_grading.py"
      reason: "新增共享判分函数，替代 router 内联逻辑"
    - module: "frontend/src/pages/GradingDispatchPage.vue"
      reason: "全新页面替代旧 GradingTasksPage"

  test_debt:
    - item: "GradingDispatchPage Vitest 组件测试"
      reason: "Vue SFC 测试依赖 API mock 和 Naive UI 环境，需要在实现完成后根据实际组件结构编写"
      deadline: "Task 7 完成后 1 天内"
```

---

### Task 1: 选择题判分共享函数

**Files:**
- Create: `src/edu_cloud/modules/scan/objective_grading.py`
- Create: `tests/test_services_exam/test_objective_grading.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_services_exam/test_objective_grading.py
"""选择题判分共享函数测试。"""
import pytest
from edu_cloud.modules.scan.objective_grading import grade_objective_answer


class TestGradeObjectiveAnswer:
    def test_correct_single(self):
        score, is_correct = grade_objective_answer("A", "A", 3.0)
        assert is_correct is True
        assert score == 3.0

    def test_incorrect_single(self):
        score, is_correct = grade_objective_answer("B", "A", 3.0)
        assert is_correct is False
        assert score == 0.0

    def test_correct_multi_order_insensitive(self):
        score, is_correct = grade_objective_answer("CA", "AC", 5.0)
        assert is_correct is True
        assert score == 5.0

    def test_incorrect_multi(self):
        score, is_correct = grade_objective_answer("AB", "AC", 5.0)
        assert is_correct is False
        assert score == 0.0

    def test_empty_detected(self):
        score, is_correct = grade_objective_answer("", "A", 3.0)
        assert is_correct is False
        assert score == 0.0

    def test_empty_correct(self):
        score, is_correct = grade_objective_answer("A", "", 3.0)
        assert is_correct is False
        assert score == 0.0

    def test_both_empty(self):
        score, is_correct = grade_objective_answer("", "", 3.0)
        assert is_correct is True
        assert score == 3.0

    def test_case_insensitive(self):
        score, is_correct = grade_objective_answer("a", "A", 3.0)
        assert is_correct is True
        assert score == 3.0

    def test_none_detected(self):
        score, is_correct = grade_objective_answer(None, "A", 3.0)
        assert is_correct is False
        assert score == 0.0

    def test_none_correct(self):
        score, is_correct = grade_objective_answer("A", None, 3.0)
        assert is_correct is False
        assert score == 0.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_objective_grading.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'edu_cloud.modules.scan.objective_grading'`

- [ ] **Step 3: 实现**

```python
# src/edu_cloud/modules/scan/objective_grading.py
"""选择题判分共享函数 — pipeline 和 router 共用。"""


def grade_objective_answer(
    detected_answer: str | None,
    correct_answer: str | None,
    max_score: float,
) -> tuple[float, bool]:
    """比对检测答案与标准答案，返回 (score, is_correct)。

    - 大小写不敏感
    - 多选题顺序不敏感（按字符排序比对）
    - detected 或 correct 为 None 视为空字符串
    """
    detected = (detected_answer or "").upper()
    correct = (correct_answer or "").upper()
    is_correct = sorted(detected) == sorted(correct)
    score = max_score if is_correct else 0.0
    return score, is_correct
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_objective_grading.py -v`
Expected: 10 passed

- [ ] **Step 5: 提交**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/modules/scan/objective_grading.py tests/test_services_exam/test_objective_grading.py
git commit -m "feat: 选择题判分共享函数 grade_objective_answer"
```

**审查清单:**
- ✓ 单选正确/错误
- ✓ 多选顺序不敏感
- ✓ 空答案/None 边界
- ✓ 大小写不敏感
- ✗ 传入非字符串类型（int）→ 应报错或兜底

**边界条件:**
- 空字符串 vs 空字符串 → (max_score, True)
- None vs "A" → (0.0, False)
- "CA" vs "AC" → (max_score, True)

**测试契约:**
1. 单选正确判分
   - 入口: `grade_objective_answer("A", "A", 3.0)`
   - 反例: 错误实现会忽略大小写或不做排序——test_case_insensitive 捕获
   - 边界: None / 空串 / 多选
   - 回归: N/A
   - 命令: `pytest tests/test_services_exam/test_objective_grading.py::TestGradeObjectiveAnswer::test_correct_single -v`

---

### Task 2: pipeline_service 扩展选择题识别

**Files:**
- Modify: `src/edu_cloud/modules/scan/pipeline_service.py`
- Create: `tests/test_services_exam/test_pipeline_objective.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_services_exam/test_pipeline_objective.py
"""pipeline_service 选择题识别扩展测试。"""
import pytest
import numpy as np
from pathlib import Path
from PIL import Image
from unittest.mock import patch, MagicMock
from dataclasses import dataclass, field


@pytest.fixture
def fake_scan_dir(tmp_path):
    for i in range(2):
        img = Image.new("RGB", (200, 150), (255, 255, 255))
        img.save(tmp_path / f"STU{i+1:04d}A.png")
    return str(tmp_path)


@pytest.fixture
def template_with_choice_group():
    return {
        "image_size": {"width": 200, "height": 150},
        "anchors": [],
        "regions": [
            {"id": "Q01", "name": "1题", "type": "subjective",
             "rect": {"x1": 10, "y1": 10, "x2": 90, "y2": 70}, "score": 5},
            {"id": "OBJ01", "name": "选择题组1", "type": "choice_group",
             "rect": {"x1": 100, "y1": 10, "x2": 190, "y2": 70},
             "cols": 4, "rows": 2, "labels": ["A", "B", "C", "D"],
             "multi_select": False, "qg_indexno": 1},
        ],
        "barcode_region": None,
    }


class TestProcessOneImageWithObjective:
    def test_choice_group_recognized(self, fake_scan_dir, template_with_choice_group, tmp_path):
        from edu_cloud.modules.scan.pipeline_service import process_one_image

        # Mock recognize_choice_group 返回固定结果
        mock_result = MagicMock()
        mock_result.question_results = [
            {"question": 1, "selected": ["A"], "all_ratios": {"A": 0.8, "B": 0.05, "C": 0.03, "D": 0.01}, "anomaly": False},
            {"question": 2, "selected": ["C"], "all_ratios": {"A": 0.02, "B": 0.04, "C": 0.75, "D": 0.01}, "anomaly": False},
        ]

        with patch("edu_cloud.modules.scan.pipeline_service.recognize_choice_group", return_value=mock_result):
            result = process_one_image(
                Path(fake_scan_dir) / "STU0001A.png",
                template_with_choice_group,
                str(tmp_path),
            )

        assert "objective_results" in result
        assert len(result["objective_results"]) == 1  # 1 个 choice_group
        group = result["objective_results"][0]
        assert group["group_id"] == "OBJ01"
        assert len(group["answers"]) == 2
        assert group["answers"][0]["detected_answer"] == "A"
        assert group["answers"][1]["detected_answer"] == "C"

    def test_no_choice_group_returns_empty(self, fake_scan_dir, tmp_path):
        from edu_cloud.modules.scan.pipeline_service import process_one_image

        template = {
            "image_size": {"width": 200, "height": 150},
            "anchors": [],
            "regions": [
                {"id": "Q01", "type": "subjective", "rect": {"x1": 10, "y1": 10, "x2": 90, "y2": 70}},
            ],
            "barcode_region": None,
        }
        result = process_one_image(Path(fake_scan_dir) / "STU0001A.png", template, str(tmp_path))
        assert result.get("objective_results", []) == []


class TestRunPipelineWithObjectiveFn:
    async def test_save_objective_fn_called(self, fake_scan_dir, template_with_choice_group, tmp_path):
        from edu_cloud.modules.scan.pipeline_service import run_pipeline

        mock_result = MagicMock()
        mock_result.question_results = [
            {"question": 1, "selected": ["A"], "all_ratios": {"A": 0.8}, "anomaly": False},
        ]

        saved_objectives = []

        async def mock_save_objective(**kwargs):
            saved_objectives.append(kwargs)

        with patch("edu_cloud.modules.scan.pipeline_service.recognize_choice_group", return_value=mock_result):
            await run_pipeline(
                image_dir=fake_scan_dir,
                template=template_with_choice_group,
                output_dir=str(tmp_path / "out"),
                exam_id="e1",
                subject_id="s1",
                school_id="sc1",
                side="A",
                pipeline_id="test_obj_fn",
                save_objective_fn=mock_save_objective,
            )

        # 2 images × 1 choice_group × 1 question = 2 calls
        assert len(saved_objectives) == 2
        assert all(s["exam_id"] == "e1" for s in saved_objectives)
        assert all("detected_answer" in s for s in saved_objectives)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_pipeline_objective.py -v`
Expected: FAIL — `objective_results` 不存在 / `save_objective_fn` 参数不存在

- [ ] **Step 3: 修改 pipeline_service.py — process_one_image 增加选择题识别**

在 `pipeline_service.py` 顶部增加 import：

```python
from .vision import detect_anchors, crop_region, read_barcode, recognize_choice_group
```

在 `process_one_image()` 函数末尾（`return` 之前），在主观题裁切循环后增加：

```python
    # 选择题识别
    objective_results = []
    choice_groups = [r for r in template.get("regions", []) if r.get("type") == "choice_group"]
    if choice_groups:
        gray = np.array(img.convert("L"))
        for group in choice_groups:
            try:
                rect = group["rect"]
                scaled_rect = {
                    "x1": int(rect["x1"] * sx),
                    "y1": int(rect["y1"] * sy),
                    "x2": int(rect["x2"] * sx),
                    "y2": int(rect["y2"] * sy),
                }
                gr = recognize_choice_group(
                    gray,
                    region=scaled_rect,
                    rows=group.get("rows", 1),
                    cols=group.get("cols", 4),
                    labels=group.get("labels", ["A", "B", "C", "D"]),
                    multi_select=group.get("multi_select", False),
                    group_id=group.get("id", ""),
                )
                answers = []
                for qr in gr.question_results:
                    selected = qr["selected"]
                    detected = "".join(selected) if selected else ""
                    answers.append({
                        "question": qr["question"],
                        "detected_answer": detected,
                        "fill_ratios": qr["all_ratios"],
                        "anomaly": qr["anomaly"],
                    })
                objective_results.append({
                    "group_id": group.get("id", ""),
                    "answers": answers,
                })
            except Exception as e:
                errors.append(f"ChoiceGroup {group.get('id', '?')}: {e}")
```

在顶部增加 `import numpy as np`。

修改返回值，增加 `"objective_results": objective_results`。

- [ ] **Step 4: 修改 pipeline_service.py — run_pipeline 增加 save_objective_fn**

在 `run_pipeline` 函数签名增加参数 `save_objective_fn=None`。

在处理每张图片的循环中（`if save_answer_fn:` 块之后），增加：

```python
                # 保存选择题结果到数据库
                if save_objective_fn and result.get("objective_results"):
                    for group in result["objective_results"]:
                        for ans in group["answers"]:
                            await save_objective_fn(
                                exam_id=exam_id,
                                subject_id=subject_id,
                                student_id=result["student_id"],
                                group_id=group["group_id"],
                                row_index=ans["question"],
                                detected_answer=ans["detected_answer"],
                                fill_ratios=ans["fill_ratios"],
                                anomaly=ans["anomaly"],
                                school_id=school_id,
                            )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_pipeline_objective.py tests/test_services_exam/test_scan_pipeline.py -v`
Expected: 全部 passed（含旧测试回归）

- [ ] **Step 6: 提交**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/modules/scan/pipeline_service.py tests/test_services_exam/test_pipeline_objective.py
git commit -m "feat: pipeline_service 扩展选择题识别 + save_objective_fn"
```

**审查清单:**
- ✓ 有 choice_group 时 recognize_choice_group 被调用
- ✓ 无 choice_group 时 objective_results 为空列表
- ✓ save_objective_fn 被正确调用
- ✗ recognize_choice_group 抛异常时不中断整个流水线

**边界条件:**
- 模板无 choice_group regions → objective_results=[]
- recognize_choice_group 抛异常 → 记入 errors，不中断
- 多个 choice_group → 每个独立识别

**测试契约:**
1. 有 choice_group 时识别结果正确返回
   - 入口: `process_one_image(path, template_with_choice_group, output_dir)`
   - 反例: 如果跳过 choice_group 遍历，objective_results 为空——test_choice_group_recognized 捕获
   - 边界: 无 choice_group / 识别异常 / 多 group
   - 回归: N/A
   - 命令: `pytest tests/test_services_exam/test_pipeline_objective.py::TestProcessOneImageWithObjective::test_choice_group_recognized -v`
2. save_objective_fn 被正确调用
   - 入口: `run_pipeline(..., save_objective_fn=mock)`
   - 反例: 如果 run_pipeline 不调用 save_objective_fn，mock 调用计数为 0
   - 边界: 无 choice_group 时不调用 / 多 group 时多次调用
   - 回归: N/A
   - 命令: `pytest tests/test_services_exam/test_pipeline_objective.py::TestRunPipelineWithObjectiveFn -v`

---

### Task 3: pipeline_router 构造 save_objective_fn

**Files:**
- Modify: `src/edu_cloud/modules/scan/pipeline_router.py`
- Create: `tests/test_api_exam/test_pipeline_save_objective.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api_exam/test_pipeline_save_objective.py
"""pipeline save_objective_fn 工厂测试。"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def mock_session_factory():
    """构造 mock async session factory。"""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.add = MagicMock()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def factory():
        yield mock_session

    return factory, mock_session


class TestBuildPipelineSaveObjectiveFn:
    async def test_save_objective_single_group(self, mock_session_factory):
        """单题组：(group_id, row_index) 精确映射到 question_id。"""
        factory, mock_session = mock_session_factory
        from edu_cloud.modules.scan.pipeline_router import build_pipeline_save_objective_fn

        # choice_group regions: qg_indexno=1 表示从第 1 题开始
        regions = [
            {"id": "OBJ01", "type": "choice_group", "qg_indexno": 1, "rows": 2},
        ]
        # questions: 按 group_id + 组内序号映射
        questions_by_group = {
            "OBJ01": [
                {"id": "q-obj-1", "row_index": 1, "correct_answer": "A", "max_score": 3.0},
                {"id": "q-obj-2", "row_index": 2, "correct_answer": "C", "max_score": 3.0},
            ],
        }

        save_fn = build_pipeline_save_objective_fn(
            regions=regions,
            questions_by_group=questions_by_group,
            exam_id="e1",
            subject_id="s1",
            school_id="sc1",
            _session_factory=factory,
        )

        await save_fn(
            exam_id="e1", subject_id="s1", student_id="stu1",
            group_id="OBJ01", row_index=1,
            detected_answer="A", fill_ratios={"A": 0.8, "B": 0.05},
            anomaly=False, school_id="sc1",
        )

        assert mock_session.add.call_count == 1
        added = mock_session.add.call_args[0][0]
        assert added.question_id == "q-obj-1"
        assert added.detected_answer == "A"
        assert added.score == 3.0

    async def test_save_objective_multi_group_no_cross_contamination(self, mock_session_factory):
        """多题组：OBJ01 row 1 和 OBJ02 row 1 映射到不同 question。
        反例防护 CE-001：全局枚举会把两个 row 1 写到同一个 question。"""
        factory, mock_session = mock_session_factory
        from edu_cloud.modules.scan.pipeline_router import build_pipeline_save_objective_fn

        regions = [
            {"id": "OBJ01", "type": "choice_group", "qg_indexno": 1, "rows": 1},
            {"id": "OBJ02", "type": "choice_group", "qg_indexno": 2, "rows": 1},
        ]
        questions_by_group = {
            "OBJ01": [{"id": "q-1", "row_index": 1, "correct_answer": "A", "max_score": 3.0}],
            "OBJ02": [{"id": "q-5", "row_index": 1, "correct_answer": "B", "max_score": 5.0}],
        }

        save_fn = build_pipeline_save_objective_fn(
            regions=regions, questions_by_group=questions_by_group,
            exam_id="e1", subject_id="s1", school_id="sc1",
            _session_factory=factory,
        )

        # OBJ01 row 1
        await save_fn(exam_id="e1", subject_id="s1", student_id="stu1",
                       group_id="OBJ01", row_index=1, detected_answer="A",
                       fill_ratios={}, anomaly=False, school_id="sc1")
        # OBJ02 row 1
        await save_fn(exam_id="e1", subject_id="s1", student_id="stu1",
                       group_id="OBJ02", row_index=1, detected_answer="B",
                       fill_ratios={}, anomaly=False, school_id="sc1")

        assert mock_session.add.call_count == 2
        first = mock_session.add.call_args_list[0][0][0]
        second = mock_session.add.call_args_list[1][0][0]
        assert first.question_id == "q-1"
        assert second.question_id == "q-5"

    async def test_orphan_group_skipped(self, mock_session_factory):
        """group_id 找不到映射时 skip 不报错。"""
        factory, mock_session = mock_session_factory
        from edu_cloud.modules.scan.pipeline_router import build_pipeline_save_objective_fn

        save_fn = build_pipeline_save_objective_fn(
            regions=[], questions_by_group={},
            exam_id="e1", subject_id="s1", school_id="sc1",
            _session_factory=factory,
        )
        await save_fn(exam_id="e1", subject_id="s1", student_id="stu1",
                       group_id="UNKNOWN", row_index=1, detected_answer="A",
                       fill_ratios={}, anomaly=False, school_id="sc1")
        assert mock_session.add.call_count == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api_exam/test_pipeline_save_objective.py -v`
Expected: FAIL — `build_pipeline_save_objective_fn` 不存在

- [ ] **Step 3: 实现 build_pipeline_save_objective_fn**

在 `pipeline_router.py` 中，`build_pipeline_save_answer_fn` 之后新增：

```python
def build_pipeline_save_objective_fn(
    regions: list[dict],
    questions_by_group: dict[str, list[dict]],
    exam_id: str,
    subject_id: str,
    school_id: str,
    _session_factory=None,
) -> Callable[..., Awaitable[None]]:
    """构造 pipeline 的 save_objective_fn 闭包 — 选择题判分 + 写 StudentAnswer。

    INV-002: 映射 key 为 (group_id, row_index) 二元组，不依赖全局枚举。
    """
    from edu_cloud.modules.scan.objective_grading import grade_objective_answer

    session_factory = _session_factory or db_mod.async_session

    # 构建 (group_id, row_index) → question dict 的映射
    question_lookup: dict[tuple[str, int], dict] = {}
    for group_id, q_list in (questions_by_group or {}).items():
        for q in q_list:
            row_idx = q.get("row_index")
            if row_idx is not None:
                question_lookup[(group_id, row_idx)] = q

    async def save_objective(
        exam_id: str,
        subject_id: str,
        student_id: str,
        group_id: str,
        row_index: int,
        detected_answer: str,
        fill_ratios: dict,
        anomaly: bool,
        school_id: str,
    ) -> None:
        q = question_lookup.get((group_id, row_index))
        if not q:
            logger.warning(
                "pipeline_orphan_objective: group=%s, row_index=%d not in lookup, skip",
                group_id, row_index,
            )
            return

        correct_answer = q.get("correct_answer", "")
        max_score = q.get("max_score", 0.0)
        score, _ = grade_objective_answer(detected_answer, correct_answer, max_score)

        async with session_factory() as db2:
            db2.add(StudentAnswer(
                exam_id=exam_id,
                subject_id=subject_id,
                student_id=student_id,
                question_id=q["id"],
                detected_answer=detected_answer,
                score=score,
                fill_ratios=fill_ratios or None,
                is_anomaly=anomaly,
                school_id=school_id,
            ))
            try:
                await db2.commit()
            except IntegrityError:
                await db2.rollback()
                logger.debug(
                    "pipeline_duplicate_objective: student=%s question=%s already exists, skip",
                    student_id, q["id"],
                )

    return save_objective
```

- [ ] **Step 4: 修改 start_pipeline 端点接入 save_objective_fn**

在 `pipeline_router.py` 的 `start_pipeline` 函数中，`build_pipeline_save_answer_fn` 调用之后，新增：

```python
    # 构造选择题 save_objective_fn（INV-002: 按 group_id + row_index 映射）
    # F010 修复：不用 q_iter 全局消费，而是通过 Question 上的 group_ref 字段显式关联
    # 当前 Question 表没有 group_ref 字段，使用 choice_group region 中的 question_ids 列表
    # （由 publish_service.publish_card_atomic 在发布答题卡时写入）
    choice_regions = [r for r in regions_for_factory if r.get("type") == "choice_group"]

    questions_by_group: dict[str, list[dict]] = {}
    for cr in choice_regions:
        gid = cr.get("id", "")
        # region 中 question_ids 是发布答题卡时写入的有序列表
        q_ids = cr.get("question_ids", [])
        if not q_ids:
            continue
        group_questions = (await db.execute(
            select(Question).where(
                Question.id.in_(q_ids),
                Question.school_id == school_id,
            )
        )).scalars().all()
        # 按 question_ids 列表顺序排列（保持与模板 row 的对应关系）
        q_by_id = {q.id: q for q in group_questions}
        group_qs = []
        for row_idx, qid in enumerate(q_ids, 1):
            q = q_by_id.get(qid)
            if q:
                group_qs.append({
                    "id": q.id, "row_index": row_idx,
                    "correct_answer": q.correct_answer, "max_score": q.max_score,
                })
        questions_by_group[gid] = group_qs

    save_objective_fn = build_pipeline_save_objective_fn(
        regions=regions_for_factory,
        questions_by_group=questions_by_group,
        exam_id=subject.exam_id,
        subject_id=req.subject_id,
        school_id=school_id,
    )
```

并在 `run_pipeline` 调用中增加 `save_objective_fn=save_objective_fn`。

需要在文件顶部增加 `from edu_cloud.modules.exam.models import Question`（如果还没有的话，检查已有 import）。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api_exam/test_pipeline_save_objective.py tests/test_services_exam/test_pipeline_objective.py -v`
Expected: 全部 passed

- [ ] **Step 6: 提交**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/modules/scan/pipeline_router.py tests/test_api_exam/test_pipeline_save_objective.py
git commit -m "feat: pipeline_router 选择题判分 save_objective_fn 接入"
```

**审查清单:**
- ✓ save_objective_fn 通过 (group_id, row_index) 精确映射到 question_id
- ✓ 多题组场景下不会交叉污染（CE-001 防护）
- ✓ 找不到对应 question 时 warning + skip
- ✓ 重复写入时 IntegrityError 静默

**测试契约:**
1. 单题组精确映射
   - 入口: `save_fn(group_id="OBJ01", row_index=1, ...)`
   - 反例: 全局枚举映射会把不同 group 的 row 1 写到同一个 question——test_multi_group 捕获
   - 边界: orphan group / 多题组 / 空映射
   - 回归: N/A
   - 命令: `pytest tests/test_api_exam/test_pipeline_save_objective.py::TestBuildPipelineSaveObjectiveFn::test_save_objective_single_group -v`
2. 多题组不交叉污染
   - 入口: `save_fn(group_id="OBJ01", row_index=1)` + `save_fn(group_id="OBJ02", row_index=1)`
   - 反例: 全局 question_index 映射下两次调用写到同一个 question_id——assertion 检查 q-1 vs q-5
   - 边界: 2 组各 1 题 / qg_indexno 不从 1 开始
   - 回归: N/A
   - 命令: `pytest tests/test_api_exam/test_pipeline_save_objective.py::TestBuildPipelineSaveObjectiveFn::test_save_objective_multi_group_no_cross_contamination -v`

**边界条件:**
- orphan group_id（映射中不存在）→ skip 不报错
- 空 questions_by_group → 所有 save 调用都 skip
- IntegrityError（重复写入）→ rollback + debug 日志

---

### Task 4: pipeline 多科目串行队列 + HTTP 入口接入

**Files:**
- Modify: `src/edu_cloud/modules/scan/pipeline_service.py`
- Modify: `src/edu_cloud/modules/scan/pipeline_router.py`
- Create: `tests/test_services_exam/test_pipeline_queue.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_services_exam/test_pipeline_queue.py
"""pipeline 多科目串行队列测试（INV-004）。"""
import pytest
import asyncio
import os
from PIL import Image


@pytest.fixture
def two_subject_dirs(tmp_path):
    dir_a = tmp_path / "yuwen"
    dir_b = tmp_path / "shuxue"
    dir_a.mkdir()
    dir_b.mkdir()
    for d in [dir_a, dir_b]:
        for i in range(2):
            Image.new("RGB", (200, 150), (255, 255, 255)).save(d / f"STU{i+1:04d}A.png")
    return str(dir_a), str(dir_b)


@pytest.fixture
def simple_template():
    return {
        "image_size": {"width": 200, "height": 150},
        "anchors": [],
        "regions": [
            {"id": "Q01", "type": "subjective", "rect": {"x1": 10, "y1": 10, "x2": 90, "y2": 70}},
        ],
        "barcode_region": None,
    }


class TestPipelineQueue:
    async def test_queue_runs_both_subjects_producing_output(self, two_subject_dirs, simple_template, tmp_path):
        """入队两个科目后 run_queue 执行，两个输出目录都有切图文件。
        反例：如果 run_queue 只执行第一个就停了，第二个目录为空。"""
        from edu_cloud.modules.scan.pipeline_service import enqueue_pipeline, run_queue
        dir_a, dir_b = two_subject_dirs
        out_a, out_b = str(tmp_path / "out_a"), str(tmp_path / "out_b")

        enqueue_pipeline(image_dir=dir_a, template=simple_template,
                         output_dir=out_a, exam_id="e1", subject_id="s_yuwen",
                         school_id="sc1", side="A")
        enqueue_pipeline(image_dir=dir_b, template=simple_template,
                         output_dir=out_b, exam_id="e1", subject_id="s_shuxue",
                         school_id="sc1", side="A")

        results = await run_queue()

        assert len(results) == 2
        assert results[0]["processed"] == 2
        assert results[1]["processed"] == 2
        # 两个输出目录都有内容
        assert len(os.listdir(out_a)) > 0, "yuwen output dir should have files"
        assert len(os.listdir(out_b)) > 0, "shuxue output dir should have files"

    async def test_stop_halts_entire_queue(self, simple_template, tmp_path):
        """stop 传播到整个队列，不只停当前科目。
        反例：如果 stop 只停当前科目但队列继续取下一个。"""
        from edu_cloud.modules.scan.pipeline_service import (
            enqueue_pipeline, run_queue, request_stop, get_progress,
        )
        # 创建 3 个科目目录，每个 20 张图
        dirs = []
        for name in ["subj_a", "subj_b", "subj_c"]:
            d = tmp_path / name
            d.mkdir()
            for i in range(20):
                Image.new("RGB", (200, 150), (255, 255, 255)).save(d / f"STU{i+1:04d}A.png")
            dirs.append(str(d))

        for i, d in enumerate(dirs):
            enqueue_pipeline(image_dir=d, template=simple_template,
                             output_dir=str(tmp_path / f"out_{i}"),
                             exam_id="e1", subject_id=f"s{i}", school_id="sc1", side="A")

        async def stop_soon():
            await asyncio.sleep(0.01)
            request_stop()

        asyncio.create_task(stop_soon())
        results = await run_queue()

        # stop 后不应该继续处理后续科目
        total_processed = sum(r["processed"] for r in results)
        assert total_processed < 60, f"Expected <60 total processed, got {total_processed}"

    async def test_each_subject_uses_own_save_fn(self, two_subject_dirs, simple_template, tmp_path):
        """F014 回归：每个科目使用自己的 save_fn，不共享。
        反例：如果 run_queue 共享首个科目的 save_fn，第二个科目的 saved_by 仍为 'fn_a'。"""
        from edu_cloud.modules.scan.pipeline_service import enqueue_pipeline, run_queue
        dir_a, dir_b = two_subject_dirs

        saved_by_a = []
        saved_by_b = []

        async def save_fn_a(**kwargs):
            saved_by_a.append(kwargs.get("subject_id"))

        async def save_fn_b(**kwargs):
            saved_by_b.append(kwargs.get("subject_id"))

        enqueue_pipeline(
            save_answer_fn=save_fn_a,
            image_dir=dir_a, template=simple_template,
            output_dir=str(tmp_path / "out_a"),
            exam_id="e1", subject_id="s_yuwen", school_id="sc1", side="A",
        )
        enqueue_pipeline(
            save_answer_fn=save_fn_b,
            image_dir=dir_b, template=simple_template,
            output_dir=str(tmp_path / "out_b"),
            exam_id="e1", subject_id="s_shuxue", school_id="sc1", side="A",
        )

        await run_queue()

        # 第一个科目的 save 都用 fn_a，第二个用 fn_b
        assert len(saved_by_a) > 0, "fn_a should have been called for yuwen"
        assert len(saved_by_b) > 0, "fn_b should have been called for shuxue"
        assert all(s == "s_yuwen" for s in saved_by_a)
        assert all(s == "s_shuxue" for s in saved_by_b)

    async def test_progress_shows_current_subject_and_queue(self, two_subject_dirs, simple_template, tmp_path):
        """进度包含 current_subject_id 和 queue_remaining。"""
        from edu_cloud.modules.scan.pipeline_service import enqueue_pipeline, run_queue, get_progress
        dir_a, dir_b = two_subject_dirs

        enqueue_pipeline(image_dir=dir_a, template=simple_template,
                         output_dir=str(tmp_path / "out_a"),
                         exam_id="e1", subject_id="s_yuwen", school_id="sc1", side="A")
        enqueue_pipeline(image_dir=dir_b, template=simple_template,
                         output_dir=str(tmp_path / "out_b"),
                         exam_id="e1", subject_id="s_shuxue", school_id="sc1", side="A")

        await run_queue()
        progress = get_progress()
        assert progress["queue_remaining"] == 0
        assert "current_subject_id" in progress
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_pipeline_queue.py -v`
Expected: FAIL — `enqueue_pipeline` / `run_queue` 不存在

- [ ] **Step 3: 实现队列机制（pipeline_service.py）**

在 `pipeline_service.py` 中新增：

```python
# 多科目队列（F009 修复：每个队列项携带自己的 save_fn）
_queue: list[dict] = []
_queue_stopped: bool = False  # F013: 独立 stop 标志，不复用 _running


def enqueue_pipeline(
    save_answer_fn=None,
    save_objective_fn=None,
    **pipeline_kwargs,
) -> int:
    """将一个科目加入切割队列，返回队列长度。
    每个科目携带自己的 save_fn，不与其他科目共享。"""
    _queue.append({
        "pipeline_kwargs": pipeline_kwargs,
        "save_answer_fn": save_answer_fn,
        "save_objective_fn": save_objective_fn,
    })
    return len(_queue)


async def run_queue() -> list[dict]:
    """依次执行队列中所有科目的切割。INV-004: stop 传播到整个队列。

    F013 修复：不能用 `not _running` 判断 stop，因为 run_pipeline 正常结束
    也会在 finally 中复位 _running=False。改用独立的 _queue_stopped 标志，
    由 request_stop 同时设置。
    """
    global _queue_stopped
    _queue_stopped = False
    results = []
    while _queue:
        if _queue_stopped:
            _queue.clear()
            break
        item = _queue.pop(0)
        result = await run_pipeline(
            save_answer_fn=item["save_answer_fn"],
            save_objective_fn=item["save_objective_fn"],
            **item["pipeline_kwargs"],
        )
        results.append(result)
    return results
```

修改 `request_stop()` 函数，增加 `global _queue_stopped; _queue_stopped = True`。

修改 `PipelineProgress` dataclass 增加 `current_subject_id: str = ""`。

修改 `get_progress` 返回值增加 `"queue_remaining": len(_queue)` 和 `"current_subject_id": p.current_subject_id`。

在 `run_pipeline` 开头设置 `progress.current_subject_id = subject_id`。

- [ ] **Step 4: 修改 pipeline_router.py — start_pipeline 改为入队模式（F002 修复）**

现有 `start_pipeline` 端点直接 `asyncio.create_task(run_pipeline(...))`，运行中再次启动返回 409。改为队列模式：

```python
@router.post("/start")
async def start_pipeline(req, db, current, storage):
    # ... 现有的 subject 验证、模板加载、save_fn 构造 ...

    # 入队（F009 修复：每个科目携带自己的 save_fn）
    from . import pipeline_service
    pipeline_service.enqueue_pipeline(
        save_answer_fn=save_answer_fn,
        save_objective_fn=save_objective_fn,
        image_dir=req.image_dir,
        template=template,
        output_dir=output_dir,
        exam_id=subject.exam_id,
        subject_id=req.subject_id,
        school_id=school_id,
        side=req.side,
    )

    # 如果没有正在运行的队列，启动队列处理
    if not pipeline_service.is_running():
        asyncio.create_task(pipeline_service.run_queue())

    return {"status": "queued", "queue_length": len(pipeline_service._queue) + (1 if pipeline_service.is_running() else 0)}
```

这样多次调用 start 不再 409，而是追加到队列。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_pipeline_queue.py tests/test_services_exam/test_scan_pipeline.py tests/test_api/test_scan_pipeline_api.py -v`
Expected: 全部 passed

- [ ] **Step 6: 提交**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/modules/scan/pipeline_service.py src/edu_cloud/modules/scan/pipeline_router.py tests/test_services_exam/test_pipeline_queue.py
git commit -m "feat: pipeline 多科目串行队列 + HTTP 入口入队模式"
```

**审查清单:**
- ✓ 入队多个科目后依次执行，输出目录有文件
- ✓ stop 传播到整个队列，不只停当前科目
- ✓ progress 返回 queue_remaining 和 current_subject_id
- ✓ HTTP start 端点改为入队模式，不再 409
- ✗ 并发 start 请求的竞态（_lock 保护）

**测试契约:**
1. 两科目串行执行后两个输出目录都有文件
   - 入口: `enqueue_pipeline() × 2 → run_queue()`
   - 反例: 只执行第一个就停了 → 第二个输出目录为空，len(results)=1
   - 边界: 空队列 / 单科目 / stop 中断
   - 回归: N/A
   - 命令: `pytest tests/test_services_exam/test_pipeline_queue.py::TestPipelineQueue::test_queue_runs_both_subjects_producing_output -v`

**边界条件:**
- 空队列 run_queue → 返回空列表
- 单科目入队 → 等价于直接 run_pipeline
- stop 后队列清空 → 后续科目不执行

---

### Task 5: 科目阅卷状态聚合 API

**Files:**
- Modify: `src/edu_cloud/modules/grading/router.py`
- Create: `tests/test_api_exam/test_dispatch_status.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api_exam/test_dispatch_status.py
"""阅卷调度状态聚合 API 测试。"""
import pytest


class TestDispatchStatus:
    async def test_idle_stage(self, client, db_engine, school_fixtures):
        """无 StudentAnswer 时 stage=idle。"""
        exam_id = school_fixtures["exam_id"]
        resp = await client.get(f"/api/v1/grading/dispatch/status?exam_id={exam_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # 至少有一个科目
        assert len(data) > 0
        # 无答卷应为 idle
        for s in data:
            assert s["stage"] == "idle"
            assert "subject_name" in s
            assert "subject_id" in s

    async def test_ready_stage_after_answers(self, client, db_engine, school_fixtures):
        """有 StudentAnswer 但无 GradingTask 时 stage=ready。"""
        exam_id = school_fixtures["exam_id"]
        subject_id = school_fixtures["subject_id"]
        # 插入一条 StudentAnswer
        from edu_cloud.modules.scan.models import StudentAnswer
        from sqlalchemy.ext.asyncio import AsyncSession
        async with db_engine.begin() as conn:
            from sqlalchemy import insert
            await conn.execute(insert(StudentAnswer).values(
                id="sa-test-1",
                exam_id=exam_id,
                subject_id=subject_id,
                student_id="stu1",
                question_id=school_fixtures["subjective_question_id"],
                image_path="/tmp/test.png",
                school_id=school_fixtures["school_id"],
            ))
            await conn.commit()

        resp = await client.get(f"/api/v1/grading/dispatch/status?exam_id={exam_id}")
        assert resp.status_code == 200
        data = resp.json()
        subject_status = next(s for s in data if s["subject_id"] == subject_id)
        assert subject_status["stage"] == "ready"

    async def test_objective_only_not_ready(self, client, db_engine, school_fixtures):
        """F012 回归：只有选择题答案（无 image_path）时不应 ready，应为 idle。
        防护 CE-002：answer_count>0 但无主观题 → 用户点 AI 阅卷得 400。"""
        exam_id = school_fixtures["exam_id"]
        subject_id = school_fixtures["subject_id"]
        from sqlalchemy import insert
        from edu_cloud.modules.scan.models import StudentAnswer
        async with db_engine.begin() as conn:
            await conn.execute(insert(StudentAnswer).values(
                id="sa-obj-only",
                exam_id=exam_id, subject_id=subject_id,
                student_id="stu1",
                question_id=school_fixtures["objective_question_id"],
                detected_answer="A", score=3.0,
                image_path=None,  # 选择题无图片
                school_id=school_fixtures["school_id"],
            ))
            await conn.commit()

        resp = await client.get(f"/api/v1/grading/dispatch/status?exam_id={exam_id}")
        data = resp.json()
        subject_status = next(s for s in data if s["subject_id"] == subject_id)
        assert subject_status["stage"] == "idle", f"Expected idle for objective-only, got {subject_status['stage']}"

    async def test_failed_task_shows_failed_stage(self, client, db_engine, school_fixtures):
        """F012 回归：GradingTask status=failed 必须显示 failed，不能折叠成 done。
        防护 CE-003。"""
        exam_id = school_fixtures["exam_id"]
        subject_id = school_fixtures["subject_id"]
        from sqlalchemy import insert
        from edu_cloud.modules.scan.models import StudentAnswer
        from edu_cloud.modules.grading.models import GradingTask
        async with db_engine.begin() as conn:
            # 先插入主观题答卷
            await conn.execute(insert(StudentAnswer).values(
                id="sa-fail-test",
                exam_id=exam_id, subject_id=subject_id,
                student_id="stu1",
                question_id=school_fixtures["subjective_question_id"],
                image_path="/tmp/test.png",
                school_id=school_fixtures["school_id"],
            ))
            # 插入 failed 的 GradingTask
            await conn.execute(insert(GradingTask).values(
                id="gt-failed",
                subject_id=subject_id, status="failed",
                total=10, completed=0, failed=10,
                created_by=school_fixtures["user_id"],
                school_id=school_fixtures["school_id"],
            ))
            await conn.commit()

        resp = await client.get(f"/api/v1/grading/dispatch/status?exam_id={exam_id}")
        data = resp.json()
        subject_status = next(s for s in data if s["subject_id"] == subject_id)
        assert subject_status["stage"] == "failed", f"Expected failed, got {subject_status['stage']}"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api_exam/test_dispatch_status.py -v`
Expected: FAIL — 404 路由不存在

- [ ] **Step 3: 实现 dispatch status API**

在 `grading/router.py` 末尾新增：

```python
@router.get("/dispatch/status")
async def get_dispatch_status(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """聚合该考试所有科目的阅卷调度状态。"""
    school_id = current["current_role"].school_id

    # 验证考试归属
    exam = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "Exam not found")

    # 获取所有科目
    subjects = (await db.execute(
        select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    )).scalars().all()

    from edu_cloud.modules.scan import pipeline_service

    result = []
    for subj in subjects:
        # 统计 StudentAnswer
        answer_count = (await db.execute(
            select(func.count(StudentAnswer.id)).where(
                StudentAnswer.subject_id == subj.id,
                StudentAnswer.school_id == school_id,
            )
        )).scalar() or 0

        # 统计选择题（有 detected_answer 的）
        objective_graded = (await db.execute(
            select(func.count(StudentAnswer.id)).where(
                StudentAnswer.subject_id == subj.id,
                StudentAnswer.school_id == school_id,
                StudentAnswer.detected_answer.isnot(None),
            )
        )).scalar() or 0

        # 查 GradingTask
        grading_task = (await db.execute(
            select(GradingTask).where(
                GradingTask.subject_id == subj.id,
                GradingTask.school_id == school_id,
            ).order_by(GradingTask.created_at.desc())
        )).scalar_one_or_none()

        # 统计 AIGradingResult 校对状态
        reviewed = 0
        ai_graded = 0
        ai_failed = 0
        grading_task_id = None
        if grading_task:
            grading_task_id = grading_task.id
            ai_graded = grading_task.completed
            ai_failed = grading_task.failed
            reviewed = (await db.execute(
                select(func.count(AIGradingResult.id)).where(
                    AIGradingResult.task_id == grading_task.id,
                    AIGradingResult.review_status != "pending",
                )
            )).scalar() or 0

        # F011 修复：subjective_total 查询提前到 stage 推导之前
        subjective_total = (await db.execute(
            select(func.count(StudentAnswer.id)).where(
                StudentAnswer.subject_id == subj.id,
                StudentAnswer.school_id == school_id,
                StudentAnswer.image_path.isnot(None),
            )
        )).scalar() or 0

        # 推导 stage（INV-003: ready 条件与 POST /grading/tasks 前置校验一致）
        has_subjective_answers = subjective_total > 0
        subjective_q_ids = (await db.execute(
            select(Question.id).where(
                Question.subject_id == subj.id,
                Question.school_id == school_id,
                Question.question_type == "subjective",
            )
        )).scalars().all()
        has_rubric = False
        if subjective_q_ids:
            rubric_count = (await db.execute(
                select(func.count(Rubric.id)).where(
                    Rubric.question_id.in_(subjective_q_ids),
                    Rubric.school_id == school_id,
                )
            )).scalar() or 0
            has_rubric = rubric_count > 0
        can_ai_grade = has_subjective_answers and has_rubric and len(subjective_q_ids) > 0

        is_cutting = (
            pipeline_service.is_running()
            and pipeline_service.get_progress().get("current_subject_id") == subj.id
        )
        if is_cutting:
            stage = "cutting"
        elif answer_count == 0:
            stage = "idle"
        elif not grading_task and can_ai_grade:
            stage = "ready"
        elif not grading_task:
            stage = "idle"  # 有选择题答案但无主观题/Rubric，不算 ready
        elif grading_task.status == "failed":
            stage = "failed"  # F005: 显式处理 failed，不折叠成 done
        elif grading_task.status in ("pending", "processing"):
            stage = "ai_grading"
        elif grading_task.status == "completed" and reviewed < ai_graded:
            stage = "reviewing"
        else:
            stage = "done"

        result.append({
            "subject_id": subj.id,
            "subject_name": subj.name,
            "stage": stage,
            "scan_images": answer_count,
            "objective_total": objective_graded,  # 简化：已识别数 = 总数
            "objective_graded": objective_graded,
            "subjective_total": subjective_total,
            "ai_graded": ai_graded,
            "ai_failed": ai_failed,
            "reviewed": reviewed,
            "grading_task_id": grading_task_id,
        })

    return result
```

顶部需要确认 `Exam` 已 import（检查现有 import，可能需要加 `from edu_cloud.modules.exam.models import Exam`）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api_exam/test_dispatch_status.py -v`
Expected: passed

- [ ] **Step 5: 提交**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/modules/grading/router.py tests/test_api_exam/test_dispatch_status.py
git commit -m "feat: GET /grading/dispatch/status 科目阅卷状态聚合 API"
```

**审查清单:**
- ✓ idle: 无 StudentAnswer 或只有选择题答案但无主观题/Rubric
- ✓ cutting: pipeline 正在运行且 subject 匹配
- ✓ ready: 有主观题答卷 + 有 Rubric + 无 GradingTask（INV-003）
- ✓ ai_grading: GradingTask pending/processing
- ✓ reviewing: GradingTask completed 但有未校对
- ✓ failed: GradingTask status=failed（F005，不折叠成 done）
- ✓ done: 全部校对完成
- ✗ 多个 GradingTask 时取 created_at 最新的

**测试契约:**
1. 无答卷时 idle
   - 入口: `GET /api/v1/grading/dispatch/status?exam_id=xxx`
   - 反例: 如果不检查 answer_count，默认 stage 可能是 ready——test_idle_stage 捕获
   - 边界: 空考试 / 只有选择题答案
   - 回归: N/A
   - 命令: `pytest tests/test_api_exam/test_dispatch_status.py::TestDispatchStatus::test_idle_stage -v`
2. 有主观题答卷+Rubric 时 ready
   - 入口: `GET /api/v1/grading/dispatch/status?exam_id=xxx`（插入 StudentAnswer + Rubric 后）
   - 反例: 如果用 answer_count>0 判 ready，只有选择题也会 ready → 用户点 AI 阅卷得 400（CE-002）
   - 边界: 只有选择题答案 / 有主观题但无 Rubric / failed 重试
   - 回归: N/A
   - 命令: `pytest tests/test_api_exam/test_dispatch_status.py::TestDispatchStatus::test_ready_stage_after_answers -v`

**边界条件:**
- 空考试（无科目）→ 返回空列表
- 科目只有选择题答案（无 image_path）→ idle（不是 ready）
- GradingTask failed 状态 → 显示 failed 阶段，可重试

---

### Task 6: 前端 API 层 + 路由更新

**Files:**
- Modify: `frontend/src/api/grading.js`
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: 新增 API 函数**

```javascript
// frontend/src/api/grading.js — 末尾追加
export const getDispatchStatus = (examId) =>
  client.get('/grading/dispatch/status', { params: { exam_id: examId } })
```

- [ ] **Step 2: 修改路由指向新组件**

```javascript
// frontend/src/router/index.js 第 38 行
// 改前:
{ path: 'grading/tasks', name: 'GradingTasks', component: () => import('../pages/GradingTasksPage.vue'), meta: { roles: SCHOOL_ADMIN_ROLES } },
// 改后:
{ path: 'grading/tasks', name: 'GradingDispatch', component: () => import('../pages/GradingDispatchPage.vue'), meta: { roles: SCHOOL_ADMIN_ROLES } },
```

- [ ] **Step 3: 提交**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend/src/api/grading.js frontend/src/router/index.js
git commit -m "feat: 前端 API + 路由指向 GradingDispatchPage"
```

---

### Task 7: GradingDispatchPage.vue 新建

**Files:**
- Create: `frontend/src/pages/GradingDispatchPage.vue`

- [ ] **Step 1: 创建完整页面组件**

参照 mockup v4（`.superpowers/brainstorm/` 中的 `grading-dispatch-v4.html`）和项目现有页面风格（Naive UI 组件 + variables.css 变量）实现完整的 Vue 3 SFC。

关键功能：
- 考试选择器（n-select）→ 调 `listExams` + `getDispatchStatus`
- 扫描目录栏（n-input + 按钮）→ 调 `scanDirectory`
- 科目列表（n-data-table 或手写 grid）→ 复选框 + 阶段标签 + 详情列 + 操作按钮
- 批量操作栏（选中后显示）→ 批量切割 / 批量 AI 阅卷
- 进度轮询（setInterval → `getPipelineProgress`）
- 阶段标签 macaron 色映射
- 操作按钮：切割→`startPipeline`，AI 阅卷→`createTask`，分配校对→`router.push('/marking/assign')`

- [ ] **Step 2: 启动前端 dev server 验证渲染**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vite --port 5273`
浏览器打开 http://localhost:5273/grading/tasks
确认页面渲染正常，考试选择器可用，科目列表展示

- [ ] **Step 3: 提交**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend/src/pages/GradingDispatchPage.vue
git commit -m "feat: GradingDispatchPage 阅卷调度中心页面"
```

---

### Task 8: 移除 ExamDetailPage 扫描 tab + 清理旧页面

**Files:**
- Modify: `frontend/src/pages/ExamDetailPage.vue`
- Delete: `frontend/src/pages/GradingTasksPage.vue`

- [ ] **Step 1: 移除 ExamDetailPage 扫描 tab**

删除 `<n-tab-pane name="scan">` 整个模板块（约第 268-397 行）。

删除 `<script setup>` 中以 `scan` 开头的所有状态变量和函数：
- `scanRootDir`, `scanDirLoading`, `scanFoundSubjects`, `scanSelectedFolder`
- `scanSubjectId`, `scanSide`, `scanTplPath`, `scanTplImporting`
- `scanStarting`, `scanRunning`, `scanPreviewing`, `scanPreviewImage`
- `scanPreviewAnchors`, `scanProgress`, `scanPollTimer`
- `scanSubjectColumns`, `scanImageDir`, `scanProgressPct`
- `handleScanDir`, `handleImportTpl`, `handlePreviewScan`, `handleStartPipeline`, `handleStopPipeline`, `pollProgress`, `stopPolling`

删除 import 中的 `scanDirectory, startPipeline, getPipelineProgress, stopPipeline, previewScan, importTpl` from `'../api/scan'`。

- [ ] **Step 2: 删除 GradingTasksPage.vue**

```bash
git rm frontend/src/pages/GradingTasksPage.vue
```

- [ ] **Step 3: 运行前端测试确认无回归**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
Expected: 全部 passed

- [ ] **Step 4: 提交**

```bash
cd C:/Users/Administrator/edu-cloud
git add frontend/src/pages/ExamDetailPage.vue
git commit -m "refactor: 移除 ExamDetailPage 扫描 tab + 删除 GradingTasksPage"
```

---

### Task 9: scan/router.py 使用共享判分函数 + 回归测试

**Files:**
- Modify: `src/edu_cloud/modules/scan/router.py`

- [ ] **Step 1: 替换 router.py 中的内联判分逻辑**

在 `scan/router.py` 的 `upload_objective` 函数中（约第 376-379 行），将：

```python
        correct = question.correct_answer or ""
        detected = ans.detected_answer or ""
        is_correct = sorted(detected.upper()) == sorted(correct.upper())
        score = question.max_score if is_correct else 0.0
```

替换为：

```python
        from edu_cloud.modules.scan.objective_grading import grade_objective_answer
        score, is_correct = grade_objective_answer(ans.detected_answer, question.correct_answer, question.max_score)
```

同样在 `compat_router.py` 的 `compat_upload_objective` 中（约第 313-315 行），将：

```python
            is_correct = ans.detected_answer == q.correct_answer
            score = q.max_score if is_correct else 0.0
```

替换为：

```python
            from edu_cloud.modules.scan.objective_grading import grade_objective_answer
            score, is_correct = grade_objective_answer(ans.detected_answer, q.correct_answer or "", q.max_score)
```

- [ ] **Step 2: 运行已有测试确认回归**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/ -k "objective" -v`
Expected: 全部 passed

- [ ] **Step 3: 提交**

```bash
cd C:/Users/Administrator/edu-cloud
git add src/edu_cloud/modules/scan/router.py src/edu_cloud/api/compat_router.py
git commit -m "refactor: scan router 使用共享 grade_objective_answer"
```

---

### Task 10: 全量测试 + 前端验证

**Files:** 无新增，纯验证

- [ ] **Step 1: 后端全量测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: 全部 passed，无新增 failure

- [ ] **Step 2: 前端全量测试**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
Expected: 全部 passed

- [ ] **Step 3: 浏览器端到端验证**

启动后端和前端，以教务主任角色登录：
1. 导航到"阅卷调度"
2. 选择一个考试
3. 确认科目列表展示正确的阶段状态
4. 设置扫描目录，点"扫描"确认科目识别
5. 勾选多个科目，确认批量操作栏出现
