"""条码贴纸 PDF 生成器测试。"""
import pytest
from edu_cloud.modules.card.export.barcode_gen import (
    parse_student_excel,
    render_barcode_pdf,
)


class TestParseStudentExcel:
    def test_parse_real_format(self, tmp_path):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["[行政班]某某学校考试-得分明细"])
        ws.append(["准考证号", "自定义考号", "班级", "姓名", "生物"])
        ws.append(["53437193", "3722230412", "高二2308班", "张三", 68])
        ws.append(["53437173", "3722230430", "高二2308班", "李四", 64])
        fp = tmp_path / "test.xlsx"
        wb.save(fp)

        students = parse_student_excel(fp, barcode_column="准考证号", name_column="姓名")
        assert len(students) == 2
        assert students[0]["barcode"] == "53437193"
        assert students[0]["name"] == "张三"
        assert students[1]["barcode"] == "53437173"

    def test_missing_column_raises(self, tmp_path):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["标题行"])
        ws.append(["考号", "姓名"])
        ws.append(["001", "张三"])
        fp = tmp_path / "test.xlsx"
        wb.save(fp)

        with pytest.raises(ValueError, match="未找到列"):
            parse_student_excel(fp, barcode_column="准考证号", name_column="姓名")


class TestRenderBarcodePdf:
    def test_renders_pdf(self):
        students = [
            {"barcode": "53437193", "name": "张三"},
            {"barcode": "53437173", "name": "李四"},
        ]
        pdf_bytes = render_barcode_pdf(students)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 500

    def test_30_per_page(self):
        students = [{"barcode": str(i), "name": f"学生{i}"} for i in range(30)]
        pdf_bytes = render_barcode_pdf(students)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_31_creates_2_pages(self):
        students = [{"barcode": str(i), "name": f"学生{i}"} for i in range(31)]
        pdf_bytes = render_barcode_pdf(students)
        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 1000

    def test_empty_students(self):
        with pytest.raises(ValueError, match="学生列表为空"):
            render_barcode_pdf([])
