"""知识树 API 请求/响应模型。"""

from pydantic import BaseModel


class GraphNodeResponse(BaseModel):
    id: str
    name: str
    level: str
    module: str
    big_concept_id: str | None = None
    aliases: list[str] = []
    review_status: str | None = None
    difficulty: int | None = None
    bloom_level: str | None = None
    # v2 新增
    description: str | None = None
    hard_in_count: int = 0
    hard_out_count: int = 0
    external_hard_refs: dict | None = None  # {in: [{id,name,module}], out: [...]}
    # v3 新增：合并 concept_stats 投影（Phase 1）
    exam_frequency: int = 0
    exam_coverage: float = 0.0
    # avg_difficulty: transfer_band 认知难度代理（near=2.0/mid=3.0/far=4.0），零考频概念为 None
    avg_difficulty: float | None = None
    importance_score: float = 0.0
    textbook_chapters: list = []  # [{book, chapter, section, title}]
    study_unit_id: str | None = None
    estimated_minutes: int | None = None
    prerequisite_depth: int = 0
    # planning_weight: MCU 映射覆盖率 ~24/108，多数概念为 None（前端着色模式 fallback）
    planning_weight: dict | None = None


class GraphEdgeResponse(BaseModel):
    id: int | None = None  # edge PK，审查操作需要
    source: str
    target: str
    type: str
    strength: float
    # v2 新增
    confidence: float = 1.0
    review_status: str | None = None


class InnerGraphResponse(BaseModel):
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]


class BigConceptNav(BaseModel):
    id: str
    name: str
    concept_ids: list[str]


class ModuleNav(BaseModel):
    id: str
    name: str
    big_concepts: list[BigConceptNav]


class GraphResponse(BaseModel):
    navigation: list[ModuleNav]
    graph: InnerGraphResponse


class ConceptMasteryItem(BaseModel):
    concept_id: str
    mastery: float
    state: str  # solid/fragile/weak/unseen
    da_count: int


class ModuleMasteryItem(BaseModel):
    module: str
    mastery: float


class MasteryResponse(BaseModel):
    student_id: str
    concept_mastery: list[ConceptMasteryItem]
    module_mastery: list[ModuleMasteryItem]


class ExamItem(BaseModel):
    id: str
    exam_id: str | None = None
    # assessment_items.question_number 真实 schema 为 INTEGER（Pydantic strict 拒绝 int→str 协转）
    question_number: int | None = None
    question_type: str | None = None
    stem: str | None = None
    answer: str | None = None
    score: float | None = None
    options: str | None = None
    explanation: str | None = None
    module_tag: str | None = None


class ExamItemsResponse(BaseModel):
    total: int
    items: list[ExamItem]
    page: int
    page_size: int


class ModuleStatsItem(BaseModel):
    concepts: int
    edges: int
    avg_freq: float
    exam_coverage: float


class StatsOverviewResponse(BaseModel):
    total_concepts: int
    total_edges: int
    exam_freq_distribution: dict[str, int]  # {high, mid, low, zero}
    module_stats: dict[str, ModuleStatsItem]


class EditOperation(BaseModel):
    op: str  # add_node/remove_node/update_node/add_edge/remove_edge/update_edge/set_review_status/reorder
    id: str | None = None
    source: str | None = None
    target: str | None = None
    type: str | None = None
    name: str | None = None
    level: str | None = None
    module: str | None = None
    description: str | None = None
    strength: float | None = None
    fields: dict | None = None
    status: str | None = None  # for set_review_status
    user_id: str | None = None  # for set_review_status
    edge_id: int | None = None  # for set_review_status on edge
    big_concept_id: str | None = None  # for reorder
    concept_ids: list[str] | None = None  # for reorder


class EditRequest(BaseModel):
    operations: list[EditOperation]


class EditResponse(BaseModel):
    success: bool
    applied: int
