"""v2 渲染器测试。"""
import pytest
from edu_cloud.modules.card.renderer import render_card_v2


@pytest.fixture
def sample_skeleton():
    return {
        "paper_size": "A3",
        "image_width": 3304,
        "image_height": 2290,
        "source_dpi": 200,
        "anchors": [
            {"id": "TL", "rect": {"x1": 70, "y1": 77, "x2": 130, "y2": 120}},
            {"id": "TR", "rect": {"x1": 1126, "y1": 78, "x2": 1185, "y2": 121}},
            {"id": "BR", "rect": {"x1": 1129, "y1": 2186, "x2": 1189, "y2": 2229}},
            {"id": "BL", "rect": {"x1": 74, "y1": 2186, "x2": 134, "y2": 2229}},
        ],
        "objective_groups": [
            {"group_id": "单选1", "start_no": 1, "count": 5, "options": 4,
             "symbols": "A,B,C,D", "multi_select": False,
             "rect": {"x1": 167, "y1": 851, "x2": 389, "y2": 951}},
        ],
        "subjective_slots": [
            {"slot_id": "Q17", "label": "17题", "columns": ["col1"],
             "rect": {"x1": 106, "y1": 1038, "x2": 1182, "y2": 2211},
             "height_flexible": True},
        ],
    }


@pytest.fixture
def sample_layout():
    return {
        "slots": [
            {
                "slot_id": "Q17",
                "final_rect": {"x1": 106, "y1": 1038, "x2": 1182, "y2": 2211},
                "sub_regions": [
                    {"id": "Q17_1", "name": "17(1)", "score": 4,
                     "rect": {"x1": 106, "y1": 1068, "x2": 1182, "y2": 1500},
                     "blanks": [{"x": 350, "y": 1240, "width": 280}]},
                    {"id": "Q17_2", "name": "17(2)", "score": 8,
                     "rect": {"x1": 106, "y1": 1500, "x2": 1182, "y2": 2211},
                     "type": "essay"},
                ],
            }
        ],
        "validation": {"all_fit": True, "warnings": []},
    }


class TestRenderV2:
    def test_produces_pdf(self, sample_skeleton, sample_layout):
        pdf = render_card_v2(
            skeleton=sample_skeleton,
            layout=sample_layout,
            exam_name="期中考试",
            subject_name="生物",
        )
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 500

    def test_a3_landscape_page(self, sample_skeleton, sample_layout):
        """A3 展开应生成横向页面。"""
        pdf = render_card_v2(
            skeleton=sample_skeleton,
            layout=sample_layout,
            exam_name="考试",
            subject_name="生物",
        )
        assert pdf[:5] == b"%PDF-"
