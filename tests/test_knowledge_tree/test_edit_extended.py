"""编辑 API 扩展测试（F003: update_node 新字段 + set_review_status + reorder）。"""
import pytest
from datetime import datetime

from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptBigConceptMap


async def _seed_edit_data(db):
    now = datetime.now()
    # BigConcept
    db.add(ConceptGraphNode(
        id="BC_M1_C1", name="大概念1", knowledge_level="L1",
        primary_module="M1", node_type="big_concept", synced_at=now,
    ))
    # Concepts
    for i, cid in enumerate(["CP_M1_A", "CP_M1_B", "CP_M1_C"]):
        db.add(ConceptGraphNode(
            id=cid, name=f"概念{chr(65+i)}", knowledge_level="L1",
            primary_module="M1", node_type="concept", synced_at=now,
            review_status="ai_draft", difficulty=3, bloom_level="understand",
            display_order=i,
        ))
    await db.flush()
    # Map
    for cid in ["CP_M1_A", "CP_M1_B", "CP_M1_C"]:
        db.add(ConceptBigConceptMap(concept_id=cid, big_concept_id="BC_M1_C1", is_primary=True))
    # A concept in different BigConcept
    db.add(ConceptGraphNode(
        id="CP_M2_D", name="概念D", knowledge_level="L1",
        primary_module="M2", node_type="concept", synced_at=now,
        review_status="ai_draft", display_order=0,
    ))
    await db.commit()


class TestUpdateConceptFields:
    """契约 1: update_node 支持新字段。"""

    @pytest.mark.asyncio
    async def test_update_difficulty_bloom(self, db):
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        applied = await apply_edits(db, [{
            "op": "update_node", "id": "CP_M1_A",
            "fields": {"difficulty": 5, "bloom_level": "analyze"},
        }])
        assert applied == 1
        node = await db.get(ConceptGraphNode, "CP_M1_A")
        assert node.difficulty == 5
        assert node.bloom_level == "analyze"

    @pytest.mark.asyncio
    async def test_update_aliases_json(self, db):
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        await apply_edits(db, [{
            "op": "update_node", "id": "CP_M1_A",
            "fields": {"aliases_json": '["别名1", "别名2"]'},
        }])
        node = await db.get(ConceptGraphNode, "CP_M1_A")
        assert node.aliases_json == '["别名1", "别名2"]'

    @pytest.mark.asyncio
    async def test_update_display_order(self, db):
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        await apply_edits(db, [{
            "op": "update_node", "id": "CP_M1_A",
            "fields": {"display_order": 99},
        }])
        node = await db.get(ConceptGraphNode, "CP_M1_A")
        assert node.display_order == 99

    @pytest.mark.asyncio
    async def test_update_disallowed_fields_filtered(self, db):
        """node_type/id 等不在白名单的字段被静默过滤。"""
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        applied = await apply_edits(db, [{
            "op": "update_node", "id": "CP_M1_A",
            "fields": {"node_type": "big_concept", "id": "HACKED"},
        }])
        assert applied == 0  # no valid fields → no update
        node = await db.get(ConceptGraphNode, "CP_M1_A")
        assert node.node_type == "concept"

    @pytest.mark.asyncio
    async def test_review_status_not_in_whitelist(self, db):
        """review_status 不在 _NODE_UPDATABLE，必须通过 set_review_status。"""
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        await apply_edits(db, [{
            "op": "update_node", "id": "CP_M1_A",
            "fields": {"review_status": "published"},
        }])
        node = await db.get(ConceptGraphNode, "CP_M1_A")
        assert node.review_status == "ai_draft", "review_status should NOT be updatable via update_node"


class TestSetReviewStatus:
    """契约 2: set_review_status 状态机 + 审计字段。"""

    @pytest.mark.asyncio
    async def test_valid_transition(self, db):
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        applied = await apply_edits(db, [{
            "op": "set_review_status", "id": "CP_M1_A",
            "status": "teacher_reviewed", "user_id": "U001",
        }])
        assert applied == 1
        node = await db.get(ConceptGraphNode, "CP_M1_A")
        assert node.review_status == "teacher_reviewed"
        assert node.reviewed_by == "U001"
        assert node.reviewed_at is not None

    @pytest.mark.asyncio
    async def test_invalid_transition_rejected(self, db):
        """ai_draft → published 不合法。"""
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        applied = await apply_edits(db, [{
            "op": "set_review_status", "id": "CP_M1_A",
            "status": "published", "user_id": "U001",
        }])
        assert applied == 0
        node = await db.get(ConceptGraphNode, "CP_M1_A")
        assert node.review_status == "ai_draft"

    @pytest.mark.asyncio
    async def test_nonexistent_node(self, db):
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        applied = await apply_edits(db, [{
            "op": "set_review_status", "id": "NONEXISTENT",
            "status": "teacher_reviewed", "user_id": "U001",
        }])
        assert applied == 0


class TestPublishedAutoRollback:
    """契约 3a: published 概念被内容修改后自动回退 ai_draft。"""

    @pytest.mark.asyncio
    async def test_content_change_triggers_rollback(self, db):
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        # First set to published (ai_draft → teacher_reviewed → published)
        await apply_edits(db, [
            {"op": "set_review_status", "id": "CP_M1_A", "status": "teacher_reviewed", "user_id": "U001"},
        ])
        await apply_edits(db, [
            {"op": "set_review_status", "id": "CP_M1_A", "status": "published", "user_id": "U001"},
        ])
        node = await db.get(ConceptGraphNode, "CP_M1_A")
        assert node.review_status == "published"

        # Modify name (content field) → should rollback to ai_draft
        await apply_edits(db, [{
            "op": "update_node", "id": "CP_M1_A",
            "fields": {"name": "新名称"},
        }])
        await db.refresh(node)
        assert node.review_status == "ai_draft"
        assert node.reviewed_by is None

    @pytest.mark.asyncio
    async def test_display_order_no_rollback(self, db):
        """display_order 非内容字段，不触发回退。"""
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        await apply_edits(db, [
            {"op": "set_review_status", "id": "CP_M1_A", "status": "teacher_reviewed", "user_id": "U001"},
        ])
        await apply_edits(db, [
            {"op": "set_review_status", "id": "CP_M1_A", "status": "published", "user_id": "U001"},
        ])

        await apply_edits(db, [{
            "op": "update_node", "id": "CP_M1_A",
            "fields": {"display_order": 10},
        }])
        node = await db.get(ConceptGraphNode, "CP_M1_A")
        assert node.review_status == "published", "display_order change should not trigger rollback"

    @pytest.mark.asyncio
    async def test_ai_draft_no_rollback(self, db):
        """ai_draft 状态修改内容不触发回退（已经是 ai_draft）。"""
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        await apply_edits(db, [{
            "op": "update_node", "id": "CP_M1_A",
            "fields": {"name": "修改后"},
        }])
        node = await db.get(ConceptGraphNode, "CP_M1_A")
        assert node.review_status == "ai_draft"


class TestReorder:
    """契约 4: reorder 操作 + big_concept_id 作用域验证。"""

    @pytest.mark.asyncio
    async def test_reorder_basic(self, db):
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        applied = await apply_edits(db, [{
            "op": "reorder", "big_concept_id": "BC_M1_C1",
            "concept_ids": ["CP_M1_C", "CP_M1_A", "CP_M1_B"],
        }])
        assert applied == 1
        c = await db.get(ConceptGraphNode, "CP_M1_C")
        a = await db.get(ConceptGraphNode, "CP_M1_A")
        b = await db.get(ConceptGraphNode, "CP_M1_B")
        assert c.display_order == 0
        assert a.display_order == 1
        assert b.display_order == 2

    @pytest.mark.asyncio
    async def test_reorder_cross_bc_ignored(self, db):
        """R3-F004: 不属于指定 BigConcept 的 ID 被忽略。"""
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        await apply_edits(db, [{
            "op": "reorder", "big_concept_id": "BC_M1_C1",
            "concept_ids": ["CP_M2_D", "CP_M1_A"],  # CP_M2_D not in BC_M1_C1
        }])
        d = await db.get(ConceptGraphNode, "CP_M2_D")
        assert d.display_order == 0, "CP_M2_D should not be reordered (not in BC_M1_C1)"
        a = await db.get(ConceptGraphNode, "CP_M1_A")
        assert a.display_order == 1  # index 1 in the list

    @pytest.mark.asyncio
    async def test_reorder_empty_list(self, db):
        await _seed_edit_data(db)
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        applied = await apply_edits(db, [{
            "op": "reorder", "big_concept_id": "BC_M1_C1",
            "concept_ids": [],
        }])
        assert applied == 1  # operation counts as applied even with empty list
