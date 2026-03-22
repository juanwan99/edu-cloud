from edu_cloud.ai.anonymizer import Anonymizer


def test_anonymize_names():
    anon = Anonymizer()
    text = "张三的数学成绩是 135 分，李四的是 120 分"
    names = ["张三", "李四"]
    result = anon.anonymize(text, names)
    assert "张三" not in result
    assert "李四" not in result
    assert "S001" in result
    assert "S002" in result


def test_deanonymize():
    anon = Anonymizer()
    anon.anonymize("张三考了满分", ["张三"])
    result = anon.deanonymize("S001考了满分")
    assert "张三" in result
    assert "S001" not in result


def test_anonymize_dict():
    anon = Anonymizer()
    data = {"name": "张三", "score": 135, "comment": "张三表现优秀"}
    names = ["张三"]
    result = anon.anonymize_data(data, names)
    assert result["name"] == "S001"
    assert result["comment"] == "S001表现优秀"
    assert result["score"] == 135


def test_anonymizer_reset():
    anon = Anonymizer()
    anon.anonymize("张三", ["张三"])
    anon.reset()
    assert len(anon._map) == 0
