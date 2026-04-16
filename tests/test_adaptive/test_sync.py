import pytest
from unittest.mock import MagicMock
from edu_cloud.modules.adaptive.sync import build_da_catalog_from_knowledge_db


def test_build_da_catalog_reads_knowledge_db():
    """从 knowledge.db 读�� DA 目录"""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        ("da:bio_sr:001", "蛋白质结构辨析", '["bio_sr:mol_cell:protein_structure"]', None),
        ("da:bio_sr:002", "渗透作用判断", '["bio_sr:mol_cell:osmosis"]', None),
    ]

    result = build_da_catalog_from_knowledge_db(mock_conn)
    assert len(result) == 2
    assert result[0]["da_id"] == "da:bio_sr:001"
    assert result[0]["name"] == "蛋白质结构辨析"


def test_build_da_catalog_empty_db():
    """空数据库返回空列表"""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []
    result = build_da_catalog_from_knowledge_db(mock_conn)
    assert result == []
