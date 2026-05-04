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
