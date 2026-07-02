from io import BytesIO

from django.test import SimpleTestCase
from openpyxl import load_workbook

from apps.reporting.exporters import ReportColumn, TabularReport, export_report


class ReportExportTests(SimpleTestCase):
    def report(self):
        return TabularReport(
            title="Demo",
            filename="demo",
            sheet_name="Datos",
            columns=(
                ReportColumn("Nombre", "name", width=20),
                ReportColumn("Total", lambda row: row.total, width=12),
            ),
            rows=[
                type("Row", (), {"name": "Alicia", "total": 10})(),
                type("Row", (), {"name": "Bruno", "total": 20})(),
            ],
        )

    def test_csv_export_contains_headers_and_rows(self):
        response = export_report(self.report(), "csv")

        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        body = response.content.decode("utf-8-sig")
        self.assertIn("Nombre,Total", body)
        self.assertIn("Alicia,10", body)

    def test_xlsx_export_generates_workbook(self):
        response = export_report(self.report(), "xlsx")

        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        workbook = load_workbook(BytesIO(response.content))
        sheet = workbook["Datos"]
        self.assertEqual(sheet["A1"].value, "Nombre")
        self.assertEqual(sheet["A2"].value, "Alicia")
        self.assertEqual(sheet["B3"].value, 20)

    def test_pdf_export_generates_pdf(self):
        response = export_report(self.report(), "pdf")

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
