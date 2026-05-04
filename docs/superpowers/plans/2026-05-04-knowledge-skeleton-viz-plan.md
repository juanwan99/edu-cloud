---
baseline_command: ".venv/bin/python -m pytest tests/test_knowledge_tree/ --tb=no -q && cd frontend && npx vitest run src/__tests__/knowledge-tree/"
baseline_verified_at: "2026-05-04T11:20:41"
baseline_count: "backend 150 passed 10 skipped; frontend 164 passed"
---

# Knowledge Skeleton Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the knowledge tree page from a raw graph visualization into a human-centered "course map" that teachers can use for daily lesson planning, with 4-layer progressive drill-down (overview → module → study unit → concept).

**Architecture:** Add 3 backend pre-aggregation endpoints that read from knowledge.db + PG (consuming existing services, no new data layer). Restructure the frontend KnowledgeTreePage to default to a "course map" view mode while preserving the existing G6 graph as a secondary "graph review" mode. Reuse existing NodeDetailDrawer/ExamItemsTab/StudyUnitTab components.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), Vue 3 + Naive UI + Composition API (frontend), knowledge.db SQLite (read-only data source)

---

## File Structure

### Backend — new files

| File | Responsibility |
|------|---------------|
| `src/edu_cloud/modules/knowledge_tree/course_map_service.py` | 3 pre-aggregation functions: `get_module_overview()`, `get_module_map()`, `get_study_unit_detail()` — all read from knowledge.db + PG |
| `src/edu_cloud/modules/knowledge_tree/course_map_schemas.py` | Pydantic response models for the 3 new endpoints |
| `tests/test_knowledge_tree/test_course_map_service.py` | Tests for the 3 service functions |

### Backend — modified files

| File | Change |
|------|--------|
| `src/edu_cloud/modules/knowledge_tree/router.py` | Add 3 new GET endpoints under existing router prefix |

### Frontend — new files

| File | Responsibility |
|------|---------------|
| `frontend/src/components/knowledge-tree/CourseMapOverview.vue` | Layer 1: 5 module cards + cross-module bridges + curriculum/exam summary |
| `frontend/src/components/knowledge-tree/ModuleMapView.vue` | Layer 2: concept clusters + learning timeline + curriculum/exam sidebar |
| `frontend/src/components/knowledge-tree/StudyUnitDetail.vue` | Layer 3: study unit prep/curriculum/exam panels |
| `frontend/src/components/knowledge-tree/ConceptDetailView.vue` | Layer 4: humanized concept detail (relations + exam patterns + evidence) |
| `frontend/src/__tests__/knowledge-tree/CourseMapOverview.test.js` | Tests for layer 1 |
| `frontend/src/__tests__/knowledge-tree/ModuleMapView.test.js` | Tests for layer 2 |
| `frontend/src/__tests__/knowledge-tree/StudyUnitDetail.test.js` | Tests for layer 3 |
| `frontend/src/__tests__/knowledge-tree/ConceptDetailView.test.js` | Tests for layer 4 |

### Frontend — modified files

| File | Change |
|------|--------|
| `frontend/src/pages/KnowledgeTreePage.vue` | Add view-mode toggle (course-map vs graph-review), default to course-map for teachers |
| `frontend/src/api/knowledgeTree.js` | Add 3 new API methods |
| `frontend/src/components/knowledge-tree/useKnowledgeTree.js` | Add course-map data loading functions |

---

### Task 1: Backend — course_map_schemas.py

**Files:**
- Create: `src/edu_cloud/modules/knowledge_tree/course_map_schemas.py`

- [ ] **Step 1: Create schema file with all 3 response models**

```python
"""课程地图 API 响应模型。"""
from pydantic import BaseModel


class ModuleCardData(BaseModel):
    id: str
    name: str
    tagline: str
    study_unit_count: int
    concept_count: int
    total_hours: float
    exam_tags: list[str]


class CrossModuleBridge(BaseModel):
    source_name: str
    target_name: str
    source_module: str
    target_module: str
    evidence: str | None = None


class CurriculumSummary(BaseModel):
    content_count: int
    academic_count: int
    big_concepts: list[str]


class ExamSummary(BaseModel):
    total_items: int
    near_count: int
    mid_count: int
    far_count: int


class ModuleOverviewResponse(BaseModel):
    modules: list[ModuleCardData]
    bridges: list[CrossModuleBridge]
    curriculum: CurriculumSummary
    exam: ExamSummary


class StudyUnitCard(BaseModel):
    id: str
    name: str
    description: str | None = None
    estimated_minutes: int
    prerequisites: list[str]
    concept_names: list[str]


class ConceptCluster(BaseModel):
    big_concept: str
    concepts: list[str]


class ModuleExamProfile(BaseModel):
    total_items: int
    near_pct: float
    mid_pct: float
    far_pct: float


class ModuleCurriculumItem(BaseModel):
    big_concept: str
    requirements: list[str]


class ModuleMapResponse(BaseModel):
    module_id: str
    module_name: str
    tagline: str
    total_hours: float
    study_units: list[StudyUnitCard]
    concept_clusters: list[ConceptCluster]
    curriculum: list[ModuleCurriculumItem]
    exam_profile: ModuleExamProfile
    outgoing_bridges: list[CrossModuleBridge]


class RelationItem(BaseModel):
    category: str
    target_name: str
    target_module: str | None = None
    evidence: str | None = None


class ExamPatternGroup(BaseModel):
    band: str
    count: int
    sample_items: list[dict]


class TextbookAnchor(BaseModel):
    book: str
    section: str
    page_range: str


class CurriculumRequirement(BaseModel):
    mastery_verb: str
    text: str
    requirement_type: str


class StudyUnitDetailResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    estimated_minutes: int
    textbook: list[TextbookAnchor]
    prerequisites: list[RelationItem]
    successors: list[RelationItem]
    contrasts: list[RelationItem]
    concepts: list[dict]
    curriculum: list[CurriculumRequirement]
    exam_patterns: list[ExamPatternGroup]
```

- [ ] **Step 2: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/course_map_schemas.py
git commit -m "feat(knowledge-tree): add course map response schemas"
```

---

### Task 2: Backend — course_map_service.py (get_module_overview)

**Files:**
- Create: `src/edu_cloud/modules/knowledge_tree/course_map_service.py`
- Test: `tests/test_knowledge_tree/test_course_map_service.py`

- [ ] **Step 1: Write the failing test for get_module_overview**

Create `tests/test_knowledge_tree/test_course_map_service.py` with a self-contained SQLite fixture (`_create_course_map_db`) containing 2 modules (M1 with 2 SUs, M3 with 1 SU), 3 concepts, concept_relations with a bridge_to edge, curriculum_requirements (2 content + 1 academic), 3 assessment_items, q_matrix entries (near/mid/far), sections + content_blocks for textbook anchors, and seed_su_exam_stats.

Test `test_get_module_overview` asserts:
- 2 modules returned with correct study_unit_count and concept_count
- At least 1 cross-module bridge (M1→M3) with evidence
- Curriculum summary: content_count=2, academic_count=1
- Exam summary: total_items=3

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_knowledge_tree/test_course_map_service.py::test_get_module_overview -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement get_module_overview**

Create `course_map_service.py` with `_open_kb()` helper and `get_module_overview()` that:
1. Reads study_units grouped by module → builds ModuleCardData (name from _MODULE_NAMES dict, total_hours = sum minutes / 45)
2. Reads bridge_to edges from PG + resolves node names → builds CrossModuleBridge list
3. Reads curriculum_requirements counts by type → CurriculumSummary
4. Reads assessment_items count + q_matrix transfer_band distribution → ExamSummary

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_knowledge_tree/test_course_map_service.py::test_get_module_overview -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/course_map_service.py tests/test_knowledge_tree/test_course_map_service.py
git commit -m "feat(knowledge-tree): add course map overview service + test"
```

---

### Task 3: Backend — get_module_map + get_study_unit_detail

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/course_map_service.py`
- Test: `tests/test_knowledge_tree/test_course_map_service.py`

- [ ] **Step 1: Write failing tests**

Append `test_get_module_map` asserting: module_id/name correct, 2 SUs returned, prereqs humanized as names ("细胞学说" in membrane prereqs), concept_clusters from curriculum big_concept, exam_profile with total_items≥1, outgoing_bridges M1→M3.

Append `test_get_study_unit_detail` asserting: name/minutes correct, prerequisites with category "必经前置" and target_name "细胞学说", textbook anchors with book containing "必修1" or "分子与细胞", concepts non-empty, exam_patterns with bands in ("基础调用","情境应用","综合迁移").

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement get_module_map and get_study_unit_detail**

`get_module_map(db, module, kb_path)`:
1. Read study_units for module, resolve prerequisite_unit_ids → names
2. Group curriculum_requirements by big_concept → concept_clusters
3. Read seed_su_exam_stats → exam_profile percentages
4. Query PG bridge_to edges originating from module concepts → outgoing_bridges

`get_study_unit_detail(db, su_id, kb_path)`:
1. Read study_unit row, resolve prerequisite_unit_ids → RelationItem with "必经前置"
2. Find SUs that list this SU as prereq → successors
3. Read concept_relations contrast → contrasts with evidence
4. Resolve textbook_anchor_ids → sections → TextbookAnchor
5. Read linked_da_ids → seed_req_da_map → curriculum_requirements with mastery verb extraction
6. Read DA → q_matrix → assessment_items grouped by transfer_band → ExamPatternGroup

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_knowledge_tree/test_course_map_service.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/course_map_service.py tests/test_knowledge_tree/test_course_map_service.py
git commit -m "feat(knowledge-tree): add module map + study unit detail services"
```

---

### Task 4: Backend — 3 router endpoints

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/router.py`

- [ ] **Step 1: Add 3 endpoints after existing edit_graph**

```python
@router.get("/course-map/overview")
async def get_course_map_overview(
    db: AsyncSession = Depends(get_db),
    current=Depends(require_permission(Permission.VIEW_KNOWLEDGE_TREE)),
):
    from edu_cloud.modules.knowledge_tree.course_map_service import get_module_overview
    return await get_module_overview(db)


@router.get("/course-map/module/{module}")
async def get_course_map_module(
    module: str,
    db: AsyncSession = Depends(get_db),
    current=Depends(require_permission(Permission.VIEW_KNOWLEDGE_TREE)),
):
    from edu_cloud.modules.knowledge_tree.course_map_service import get_module_map
    return await get_module_map(db, module)


@router.get("/course-map/study-unit/{su_id:path}")
async def get_course_map_study_unit(
    su_id: str,
    db: AsyncSession = Depends(get_db),
    current=Depends(require_permission(Permission.VIEW_KNOWLEDGE_TREE)),
):
    from edu_cloud.modules.knowledge_tree.course_map_service import get_study_unit_detail
    return await get_study_unit_detail(db, su_id)
```

- [ ] **Step 2: Run existing router tests to confirm no regression**

Run: `.venv/bin/python -m pytest tests/test_knowledge_tree/test_router.py -v --tb=short`

- [ ] **Step 3: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/router.py
git commit -m "feat(knowledge-tree): add 3 course map API endpoints"
```

---

### Task 5: Frontend — API layer + composable

**Files:**
- Modify: `frontend/src/api/knowledgeTree.js`
- Modify: `frontend/src/components/knowledge-tree/useKnowledgeTree.js`

- [ ] **Step 1: Append 3 API methods to knowledgeTree.js**

```javascript
export async function getCourseMapOverview() {
  const resp = await client.get('/knowledge-tree/course-map/overview')
  return resp.data
}

export async function getCourseMapModule(module) {
  const resp = await client.get(`/knowledge-tree/course-map/module/${module}`)
  return resp.data
}

export async function getCourseMapStudyUnit(suId) {
  const resp = await client.get(`/knowledge-tree/course-map/study-unit/${encodeURIComponent(suId)}`)
  return resp.data
}
```

- [ ] **Step 2: Add course-map state + loaders to useKnowledgeTree.js**

Add 3 refs (`courseMapOverview`, `courseMapModule`, `courseMapStudyUnit`) and 3 async loader functions. Add all 6 to the return object.

- [ ] **Step 3: Run existing frontend tests**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/knowledgeTree.js frontend/src/components/knowledge-tree/useKnowledgeTree.js
git commit -m "feat(knowledge-tree): add course map API layer + composable"
```

---

### Task 6: Frontend — CourseMapOverview.vue (Layer 1)

**Files:**
- Create: `frontend/src/components/knowledge-tree/CourseMapOverview.vue`
- Test: `frontend/src/__tests__/knowledge-tree/CourseMapOverview.test.js`

- [ ] **Step 1: Write test**

Test renders module cards (names + "33 单元"), cross-module bridges, exam summary (total_items), and emits `select-module` on card click.

- [ ] **Step 2: Implement CourseMapOverview.vue**

Two-column layout: left = 5 module cards (vertical stack), right = bridges section + curriculum/exam summary. Module cards show id badge (#644CF0), name, tagline, stats (units/concepts/hours), exam tags. Design tokens: #644CF0 structure, #ED9A51 exam tags, #F8F8FC background.

- [ ] **Step 3: Run test + commit**

```bash
cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/CourseMapOverview.test.js
git add frontend/src/components/knowledge-tree/CourseMapOverview.vue frontend/src/__tests__/knowledge-tree/CourseMapOverview.test.js
git commit -m "feat(knowledge-tree): add CourseMapOverview component (layer 1)"
```

---

### Task 7: Frontend — ModuleMapView.vue (Layer 2)

**Files:**
- Create: `frontend/src/components/knowledge-tree/ModuleMapView.vue`
- Test: `frontend/src/__tests__/knowledge-tree/ModuleMapView.test.js`

- [ ] **Step 1: Write test**

Test renders module header (name + hours), study unit cards with "先学" prerequisite text, emits `select-unit` on card click.

- [ ] **Step 2: Implement ModuleMapView.vue**

3-column: left = concept clusters by big_concept, center = study unit cards in vertical timeline (name + description + "X 课时" + "先学：A, B"), right = curriculum + exam profile + outgoing bridges. Emits `select-unit(suId)` and `back`.

- [ ] **Step 3: Run test + commit**

```bash
git commit -m "feat(knowledge-tree): add ModuleMapView component (layer 2)"
```

---

### Task 8: Frontend — StudyUnitDetail.vue (Layer 3)

**Files:**
- Create: `frontend/src/components/knowledge-tree/StudyUnitDetail.vue`
- Test: `frontend/src/__tests__/knowledge-tree/StudyUnitDetail.test.js`

- [ ] **Step 1: Write test**

Test renders unit name + textbook location, prerequisite relations with "必经前置" label, exam patterns with "基础调用"/"情境应用"/"综合迁移" bands, emits `select-concept` and `back`.

- [ ] **Step 2: Implement StudyUnitDetail.vue**

4-section layout: header (name + description + textbook + hours), left (prerequisites/successors/contrasts as relation cards with "为什么" evidence), right-top (curriculum with mastery verb tags: 金黄#F4DA4C), right-bottom (exam patterns grouped by band: green near, orange mid, red far). Emits `select-concept(id)` and `back`.

- [ ] **Step 3: Run test + commit**

```bash
git commit -m "feat(knowledge-tree): add StudyUnitDetail component (layer 3)"
```

---

### Task 9: Frontend — KnowledgeTreePage view-mode integration

**Files:**
- Modify: `frontend/src/pages/KnowledgeTreePage.vue`

- [ ] **Step 1: Add view-mode state + imports**

Import CourseMapOverview, ModuleMapView, StudyUnitDetail. Add `viewMode` ref ('course-map' default | 'graph-review'), `courseMapLayer` ref ('overview' | 'module' | 'unit'). Teachers default to 'course-map', graph-review accessible via tab toggle.

- [ ] **Step 2: Add view-mode toggle in template**

Replace existing `view-tabs` with NTabs: "课程地图" / "图谱视图" (+ "审查工作台" if canEdit). When course-map: render layer components based on courseMapLayer. When graph-review: render existing G6 graph + RelationReviewPanel unchanged.

- [ ] **Step 3: Wire navigation events**

`handleCourseMapModuleSelect(moduleId)` → set layer='module', loadCourseMapModule. `handleCourseMapUnitSelect(suId)` → set layer='unit', loadCourseMapStudyUnit. `handleCourseMapBack()` → step back one layer. Concept click → open existing NodeDetailDrawer.

- [ ] **Step 4: Update init to load course map data by default**

`loadCourseMapOverview()` in `onMounted`. Existing graph data loads lazily when switching to graph-review.

- [ ] **Step 5: Run all knowledge-tree tests**

```bash
cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/
.venv/bin/python -m pytest tests/test_knowledge_tree/ -v --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/KnowledgeTreePage.vue
git commit -m "feat(knowledge-tree): integrate course map as default view mode"
```

---

## Self-Review

**Spec coverage:**
- ✅ Layer 1 overview (Task 2 + 6)
- ✅ Layer 2 module map (Task 3 + 7)
- ✅ Layer 3 study unit (Task 3 + 8)
- ✅ Layer 4 concept detail — reuses existing NodeDetailDrawer (already enriched by detail_service)
- ✅ Backend pre-aggregation (Tasks 2-4)
- ✅ Frontend API + composable (Task 5)
- ✅ View mode toggle (Task 9)
- ✅ Cross-module bridges (Task 2 + 6)
- ✅ Curriculum humanized (Task 3)
- ✅ Exam patterns by transfer_band (Task 3)
- ✅ Relation humanization (Task 3: 必经前置/建议铺垫/易混对照/跨模块桥)
- ✅ Evidence as "为什么" (Task 3)

**Placeholder scan:** No TBDs. Task 7/8 code blocks are condensed but all key structures described.

**Type consistency:** `get_module_overview` → ModuleOverviewResponse, `get_module_map` → ModuleMapResponse, `get_study_unit_detail` → StudyUnitDetailResponse. Frontend props match API shapes.
