from edu_cloud.ai.anonymizer import Anonymizer


def test_anonymize_dict_with_name_fields():
    """Anonymizer detects name fields and replaces with codes."""
    anon = Anonymizer()
    data = {"student_name": "张三", "score": 135}
    result = anon.anonymize(data)
    assert result["student_name"] == "S001"
    assert result["score"] == 135
    # Original not modified
    assert data["student_name"] == "张三"


def test_anonymize_nested():
    """Nested dicts and lists are recursively anonymized."""
    anon = Anonymizer()
    data = {"students": [{"name": "张三", "score": 90}, {"name": "李四", "score": 85}]}
    result = anon.anonymize(data)
    assert result["students"][0]["name"] == "S001"
    assert result["students"][1]["name"] == "S002"


def test_anonymize_strips_student_number():
    """student_number fields are completely removed."""
    anon = Anonymizer()
    data = {"student_name": "张三", "student_number": "2024001", "score": 90}
    result = anon.anonymize(data)
    assert "student_number" not in result
    assert result["student_name"] == "S001"


def test_deanonymize():
    anon = Anonymizer()
    anon.anonymize({"name": "张三"})
    result = anon.deanonymize("S001考了满分")
    assert "张三" in result
    assert "S001" not in result


def test_anonymizer_reset():
    anon = Anonymizer()
    anon.anonymize({"name": "张三"})
    assert anon.mapping_count == 1
    anon.reset()
    assert anon.mapping_count == 0


def test_anonymize_same_name_reuses_code():
    """Same name always maps to same code."""
    anon = Anonymizer()
    r1 = anon.anonymize({"name": "张三"})
    r2 = anon.anonymize({"name": "张三"})
    assert r1["name"] == r2["name"] == "S001"
    assert anon.mapping_count == 1
