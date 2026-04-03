from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import zipfile

from quick_cms_add.xlsx_reader import XlsxWorkbook


def build_test_workbook(path: Path) -> None:
    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
"""
    shared_strings_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="6" uniqueCount="6">
  <si><t>value</t></si>
  <si><t>description</t></si>
  <si><t>definition</t></si>
  <si><t>MALE</t></si>
  <si><t>Male</t></si>
  <si><t>A male definition.</t></si>
</sst>
"""
    sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c>
      <c r="B1" t="s"><v>1</v></c>
      <c r="C1" t="s"><v>2</v></c>
    </row>
    <row r="2">
      <c r="A2" t="s"><v>3</v></c>
      <c r="B2" t="s"><v>4</v></c>
      <c r="C2" t="s"><v>5</v></c>
    </row>
  </sheetData>
</worksheet>
"""

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "")
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        archive.writestr("xl/sharedStrings.xml", shared_strings_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


class XlsxWorkbookTests(unittest.TestCase):
    def test_reads_rows_from_xlsx(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook_path = Path(temp_dir) / "test.xlsx"
            build_test_workbook(workbook_path)

            with XlsxWorkbook(workbook_path) as workbook:
                headers, rows = workbook.read_sheet("Sheet1")

        self.assertEqual(headers, ["value", "description", "definition"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].row_number, 2)
        self.assertEqual(
            rows[0].values,
            {
                "value": "MALE",
                "description": "Male",
                "definition": "A male definition.",
            },
        )


if __name__ == "__main__":
    unittest.main()
