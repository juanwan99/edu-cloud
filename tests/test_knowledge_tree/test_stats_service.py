"""concept_stats 计算服务测试"""
import os
from pathlib import Path

import pytest


KB_PATH = os.environ.get(
    "KNOWLEDGE_DB_PATH",
    str(Path.home() / "edu-knowledge-base" / "knowledge.db")
)


@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
def test_exam_frequency_real_data():
    """考频计算：光合作用应有 1260 题（实测值），零考频概念应存在"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_exam_frequency

    freq = compute_exam_frequency(KB_PATH)

    # 返回应只包含 L1 概念（约 108 个），不含 L0/evidence
    assert 100 <= len(freq) <= 120, f"Expected ~108 L1 concepts, got {len(freq)}"

    # 光合作用是高频概念
    photo = freq.get("BIO_SR_CP_M1_PHOTOSYNTHESIS")
    assert photo is not None and photo >= 1000, f"光合作用考频应>=1000, got {photo}"

    # 应存在零考频概念
    zero_freq = [cid for cid, f in freq.items() if f == 0]
    assert len(zero_freq) >= 10, f"应有多个零考频概念, got {len(zero_freq)}"


@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
def test_exam_frequency_excludes_l0():
    """考频计算不应把 L0 evidence 当作概念（反例检查）"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_exam_frequency
    freq = compute_exam_frequency(KB_PATH)
    # L0 evidence ID 格式为 BIO_SR_B1_CH01_BK_001，不应出现
    l0_keys = [k for k in freq if "_BK_" in k]
    assert len(l0_keys) == 0, f"不应包含 L0 evidence, got {l0_keys[:3]}"


@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
def test_avg_difficulty():
    """avg_difficulty：聚合概念关联题目的 difficulty 平均"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_avg_difficulty
    diff = compute_avg_difficulty(KB_PATH)

    # 有题目的概念应有 avg_difficulty，范围 1-5
    photo = diff.get("BIO_SR_CP_M1_PHOTOSYNTHESIS")
    assert photo is not None
    assert 1.0 <= photo <= 5.0, f"avg_difficulty 应在 [1,5], got {photo}"

    # 零考频概念应为 None
    zero_freq_concepts = [cid for cid, d in diff.items() if d is None]
    assert len(zero_freq_concepts) >= 10


@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
def test_exam_coverage():
    """exam_coverage：概念出现在多少套高考卷中 / 总卷数"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_exam_coverage
    cov = compute_exam_coverage(KB_PATH)

    photo = cov.get("BIO_SR_CP_M1_PHOTOSYNTHESIS")
    assert photo is not None
    assert 0.0 <= photo <= 1.0
    assert photo >= 0.5, f"光合作用应覆盖 >50% 高考卷, got {photo}"


# ---------- T3: 教材章节聚合 + 前置深度 ----------

@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
def test_textbook_chapters():
    """教材章节聚合：通过 evidence → content_blocks → sections 回溯"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_textbook_chapters
    chapters = compute_textbook_chapters(KB_PATH)

    # 光合作用应映射到必修1
    photo = chapters.get("BIO_SR_CP_M1_PHOTOSYNTHESIS")
    assert photo is not None and len(photo) > 0, "光合作用应关联教材章节"
    assert any(ch["book"] == "b1" for ch in photo), "光合作用应在必修1"

    # 每个章节条目应包含 book/chapter/section/title
    for cid, chs in chapters.items():
        for ch in chs:
            assert "book" in ch
            assert "chapter" in ch
            assert "section" in ch
            assert "title" in ch

    # 覆盖率应 >= 80%（设计中 89.5% 是 evidence 层面，聚合到 L1 层会更高）
    non_empty = sum(1 for v in chapters.values() if v)
    coverage = non_empty / len(chapters)
    assert coverage >= 0.8, f"L1 概念教材覆盖率应 >=80%, got {coverage:.1%}"


@pytest.mark.asyncio
async def test_prerequisite_depth(db):
    """拓扑排序计算前置深度。构造: A→B→C, D 孤立"""
    from datetime import datetime
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge
    from edu_cloud.modules.knowledge_tree.stats_service import compute_prerequisite_depth

    now = datetime.now()
    for cid in ["A", "B", "C", "D"]:
        db.add(ConceptGraphNode(
            id=cid, name=cid, knowledge_level="L1",
            primary_module="M1", node_type="concept", synced_at=now,
        ))
    db.add(ConceptGraphEdge(
        source_id="A", target_id="B", relation_type="prerequisite_hard",
        strength=1.0, confidence=1.0, synced_at=now,
    ))
    db.add(ConceptGraphEdge(
        source_id="B", target_id="C", relation_type="prerequisite_hard",
        strength=1.0, confidence=1.0, synced_at=now,
    ))
    await db.commit()

    depth = await compute_prerequisite_depth(db)
    assert depth["A"] == 0, "A 无前置，depth=0"
    assert depth["B"] == 1, "B 前置链长度 1"
    assert depth["C"] == 2, "C 前置链长度 2"
    assert depth["D"] == 0, "D 孤立，depth=0"


@pytest.mark.asyncio
async def test_prerequisite_depth_cycle_handling(db):
    """有环时不应死循环"""
    import asyncio
    from datetime import datetime
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge
    from edu_cloud.modules.knowledge_tree.stats_service import compute_prerequisite_depth

    now = datetime.now()
    for cid in ["X", "Y"]:
        db.add(ConceptGraphNode(
            id=cid, name=cid, knowledge_level="L1",
            primary_module="M1", node_type="concept", synced_at=now,
        ))
    # 构造环: X→Y, Y→X
    db.add(ConceptGraphEdge(
        source_id="X", target_id="Y", relation_type="prerequisite_hard",
        strength=1.0, confidence=1.0, synced_at=now,
    ))
    db.add(ConceptGraphEdge(
        source_id="Y", target_id="X", relation_type="prerequisite_hard",
        strength=1.0, confidence=1.0, synced_at=now,
    ))
    await db.commit()

    # 不应抛异常或死循环（带 timeout 验证）
    depth = await asyncio.wait_for(compute_prerequisite_depth(db), timeout=2.0)
    # 环中节点应有 fallback 值
    assert "X" in depth
    assert "Y" in depth


# ---------- T5: importance_score + compute_all_stats ----------

def test_importance_score_normalization():
    """importance_score 应归一化到 [0, 10]"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_importance_score

    # 样本 1: 高频 + 高权重 + 深前置
    score_high = compute_importance_score(
        exam_frequency_percentile=0.95,
        prerequisite_depth=5,
        planning_weight={"error_prone": 9, "transfer_value": 10},
    )
    assert 7.0 <= score_high <= 10.0, f"高权重应得高分, got {score_high}"

    # 样本 2: 全零（无 MCU 权重 → error_prone=transfer_value=5.0 fallback，公式产出 2.5）
    score_low = compute_importance_score(
        exam_frequency_percentile=0.0,
        prerequisite_depth=0,
        planning_weight=None,
    )
    # 原 plan 断言 <=2.0 与公式冲突（fallback 5.0 × 0.3+0.2 = 2.5），放宽到 3.0
    assert 0.0 <= score_low <= 3.0, f"全零应得低分, got {score_low}"

    # 样本 3: 无 MCU 权重时应有 fallback
    score_no_mcu = compute_importance_score(
        exam_frequency_percentile=0.5,
        prerequisite_depth=2,
        planning_weight=None,
    )
    assert 0.0 < score_no_mcu < 10.0


# F002 修复（Round 2）: pairwise 单调性测试，防止任一输入分量被实现意外删除
# INV-005 要求 importance_score 单调随输入分量递增；
# 之前的 3 个宽区间断言无法检测 "删除 depth_component" 的 mutant 实现。

def test_importance_score_monotonic_in_exam_frequency():
    """固定其他分量，提升 exam_frequency_percentile 应严格提升 score"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_importance_score

    base = dict(prerequisite_depth=2, planning_weight={"error_prone": 5, "transfer_value": 5})
    s_low = compute_importance_score(exam_frequency_percentile=0.0, **base)
    s_mid = compute_importance_score(exam_frequency_percentile=0.5, **base)
    s_high = compute_importance_score(exam_frequency_percentile=1.0, **base)
    assert s_low < s_mid < s_high, f"应严格单调: {s_low} < {s_mid} < {s_high}"


def test_importance_score_monotonic_in_prerequisite_depth():
    """固定其他分量，提升 prerequisite_depth 应严格提升 score（深度越深越基础越重要）"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_importance_score

    base = dict(exam_frequency_percentile=0.5, planning_weight={"error_prone": 5, "transfer_value": 5})
    s_low = compute_importance_score(prerequisite_depth=0, **base)
    s_mid = compute_importance_score(prerequisite_depth=3, **base)
    s_high = compute_importance_score(prerequisite_depth=6, **base)
    assert s_low < s_mid < s_high, f"应严格单调: {s_low} < {s_mid} < {s_high}"


def test_importance_score_monotonic_in_error_prone():
    """固定其他分量，提升 planning_weight.error_prone 应严格提升 score"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_importance_score

    base = dict(exam_frequency_percentile=0.5, prerequisite_depth=2)
    s_low = compute_importance_score(planning_weight={"error_prone": 0, "transfer_value": 5}, **base)
    s_mid = compute_importance_score(planning_weight={"error_prone": 5, "transfer_value": 5}, **base)
    s_high = compute_importance_score(planning_weight={"error_prone": 10, "transfer_value": 5}, **base)
    assert s_low < s_mid < s_high, f"应严格单调: {s_low} < {s_mid} < {s_high}"


def test_importance_score_monotonic_in_transfer_value():
    """固定其他分量，提升 planning_weight.transfer_value 应严格提升 score"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_importance_score

    base = dict(exam_frequency_percentile=0.5, prerequisite_depth=2)
    s_low = compute_importance_score(planning_weight={"error_prone": 5, "transfer_value": 0}, **base)
    s_mid = compute_importance_score(planning_weight={"error_prone": 5, "transfer_value": 5}, **base)
    s_high = compute_importance_score(planning_weight={"error_prone": 5, "transfer_value": 10}, **base)
    assert s_low < s_mid < s_high, f"应严格单调: {s_low} < {s_mid} < {s_high}"


@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
@pytest.mark.asyncio
async def test_compute_all_stats_real(db, seeded_concepts):
    """端到端：触发 compute_all_stats，验证所有 L1 concept 都有 stats（精确匹配）。

    F003 修复（Round 2）: 用精确 count 替代 `>= 100` 弱断言；去掉 `if photo:` 包裹；
    对光合作用同时断言 5 个派生字段，防止 study_unit_id / estimated_minutes / textbook_chapters
    未被 compute_all_stats 写入时测试仍通过。
    """
    import sqlalchemy as sa
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptStats
    from edu_cloud.modules.knowledge_tree.stats_service import compute_all_stats

    await compute_all_stats(db, KB_PATH)

    # 精确断言：concept_stats count 等于 L1 concept count
    concept_count = (
        await db.execute(
            sa.select(sa.func.count())
            .select_from(ConceptGraphNode)
            .where(ConceptGraphNode.node_type == "concept")
        )
    ).scalar()
    stats_count = (
        await db.execute(sa.select(sa.func.count()).select_from(ConceptStats))
    ).scalar()
    assert concept_count > 0, "seeded_concepts 应同步至少 1 个 concept"
    assert stats_count == concept_count, \
        f"stats 必须覆盖全部 L1 concept: stats={stats_count}, concepts={concept_count}"

    # 对已知高频概念做多字段硬断言（去掉 if photo:）
    photo = (
        await db.execute(
            sa.select(ConceptStats).where(
                ConceptStats.concept_id == "BIO_SR_CP_M1_PHOTOSYNTHESIS"
            )
        )
    ).scalar_one()  # 缺失立即 MultipleResultsFound/NoResultFound，不静默
    assert photo.exam_frequency >= 1000, f"光合作用考频应 >=1000, got {photo.exam_frequency}"
    assert photo.importance_score > 5.0, f"光合作用 importance 应 >5, got {photo.importance_score}"
    assert len(photo.textbook_chapters) > 0, "光合作用应关联至少 1 个教材章节"
    # 设计要求 StudyUnit 映射从 knowledge.db 加载
    assert photo.study_unit_id is not None, "光合作用应关联 study_unit_id"
    assert photo.estimated_minutes is not None and photo.estimated_minutes > 0, \
        f"光合作用 estimated_minutes 应 >0, got {photo.estimated_minutes}"
