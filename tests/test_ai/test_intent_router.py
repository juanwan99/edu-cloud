"""Tests for IntentRouter + EntityExtractor."""
import pytest


# --- Entity extraction ---

def test_extract_subject():
    from edu_cloud.ai.entity_extractor import EntityExtractor
    result = EntityExtractor.extract("数学考了多少分")
    assert result["subject"] == "math"


def test_extract_class():
    from edu_cloud.ai.entity_extractor import EntityExtractor
    result = EntityExtractor.extract("3班语文成绩")
    assert result["class_ref"] == "3"


def test_extract_student():
    from edu_cloud.ai.entity_extractor import EntityExtractor
    result = EntityExtractor.extract("小明同学最近怎么样")
    assert result["student_ref"] == "小明"


def test_extract_nothing():
    from edu_cloud.ai.entity_extractor import EntityExtractor
    result = EntityExtractor.extract("你好")
    assert not result


# --- Intent routing ---

def test_route_post_exam():
    from edu_cloud.ai.intent_router import IntentRouter
    router = IntentRouter()
    intent = router.classify("这次考试分析出来了吗", available_workflows=["post_exam_analysis"])
    assert intent.workflow == "post_exam_analysis"
    assert intent.mode == "workflow"


def test_route_profile():
    from edu_cloud.ai.intent_router import IntentRouter
    router = IntentRouter()
    intent = router.classify("学情画像看看学习情况", available_workflows=["student_profile"])
    assert intent.workflow == "student_profile"


def test_route_free_mode():
    from edu_cloud.ai.intent_router import IntentRouter
    router = IntentRouter()
    intent = router.classify("帮我出一套数学试卷", available_workflows=[])
    assert intent.workflow is None
    assert intent.mode == "free"


def test_route_low_confidence():
    from edu_cloud.ai.intent_router import IntentRouter
    router = IntentRouter()
    intent = router.classify("看看情况", available_workflows=["post_exam_analysis", "student_profile"])
    assert intent.confidence < 0.8 or intent.needs_clarification


def test_route_with_entities():
    from edu_cloud.ai.intent_router import IntentRouter
    router = IntentRouter()
    intent = router.classify("3班数学成绩分析报告")
    assert intent.entities is not None
    assert intent.entities.get("subject") == "math"
    assert intent.entities.get("class_ref") == "3"
