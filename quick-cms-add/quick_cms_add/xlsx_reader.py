from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

CELL_REF_RE = re.compile(r"([A-Z]+)(\d+)")


@dataclass(frozen=True)
class SheetRow:
    row_number: int
    values: dict[str, str]


@dataclass(frozen=True)
class SheetInfo:
    name: str
    path: str


class WorkbookError(RuntimeError):
    """Raised when an XLSX workbook cannot be read."""


class XlsxWorkbook:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise WorkbookError(f"Workbook does not exist: {self.path}")
        if self.path.suffix.lower() != ".xlsx":
            raise WorkbookError("Only .xlsx files are supported.")
        self._archive = zipfile.ZipFile(self.path)
        self._shared_strings = self._load_shared_strings()
        self._sheets = self._load_sheets()

    def close(self) -> None:
        self._archive.close()

    def __enter__(self) -> "XlsxWorkbook":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def sheet_names(self) -> list[str]:
        return [sheet.name for sheet in self._sheets]

    def read_sheet(
        self,
        sheet_name: str | None = None,
        *,
        header_row: int = 1,
    ) -> tuple[list[str], list[SheetRow]]:
        sheet = self._pick_sheet(sheet_name)
        root = self._read_xml(sheet.path)
        rows = root.findall("./main:sheetData/main:row", NS)
        parsed_rows: list[tuple[int, dict[int, str]]] = []
        for fallback_row_number, row in enumerate(rows, start=1):
            row_number = int(row.attrib.get("r", str(fallback_row_number)))
            parsed_rows.append((row_number, self._parse_row_cells(row)))

        header_cells = next(
            (cells for row_number, cells in parsed_rows if row_number == header_row),
            None,
        )
        if header_cells is None:
            raise WorkbookError(
                f"Header row {header_row} was not found in sheet '{sheet.name}'."
            )

        ordered_header_indexes = sorted(
            col_idx for col_idx, value in header_cells.items() if value.strip()
        )
        headers = [header_cells[col_idx].strip() for col_idx in ordered_header_indexes]
        if not headers:
            raise WorkbookError(f"Sheet '{sheet.name}' does not contain any headers.")

        mapped_rows: list[SheetRow] = []
        for row_number, raw_cells in parsed_rows:
            if row_number <= header_row:
                continue
            values = {
                header_cells[col_idx].strip(): raw_cells.get(col_idx, "").strip()
                for col_idx in ordered_header_indexes
                if header_cells.get(col_idx, "").strip()
            }
            if any(value for value in values.values()):
                mapped_rows.append(SheetRow(row_number=row_number, values=values))

        return headers, mapped_rows

    def _pick_sheet(self, sheet_name: str | None) -> SheetInfo:
        if not self._sheets:
            raise WorkbookError("Workbook does not contain any sheets.")
        if sheet_name is None:
            return self._sheets[0]
        for sheet in self._sheets:
            if sheet.name == sheet_name:
                return sheet
        raise WorkbookError(f"Sheet '{sheet_name}' was not found.")

    def _load_shared_strings(self) -> list[str]:
        if "xl/sharedStrings.xml" not in self._archive.namelist():
            return []
        root = self._read_xml("xl/sharedStrings.xml")
        return [self._extract_string_item(item) for item in root.findall("main:si", NS)]

    def _load_sheets(self) -> list[SheetInfo]:
        workbook = self._read_xml("xl/workbook.xml")
        rels = self._read_xml("xl/_rels/workbook.xml.rels")
        rel_map = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in rels.findall("pkgrel:Relationship", NS)
        }
        sheets: list[SheetInfo] = []
        for sheet in workbook.findall("./main:sheets/main:sheet", NS):
            rel_id = sheet.attrib.get(f"{{{NS['rel']}}}id")
            if rel_id is None or rel_id not in rel_map:
                continue
            target = rel_map[rel_id]
            sheet_path = posixpath.normpath(posixpath.join("xl", target))
            sheets.append(SheetInfo(name=sheet.attrib["name"], path=sheet_path))
        return sheets

    def _read_xml(self, archive_path: str) -> ET.Element:
        try:
            data = self._archive.read(archive_path)
        except KeyError as exc:
            raise WorkbookError(f"Missing workbook part: {archive_path}") from exc
        return ET.fromstring(data)

    def _parse_row_cells(self, row: ET.Element) -> dict[int, str]:
        cells: dict[int, str] = {}
        for cell in row.findall("main:c", NS):
            ref = cell.attrib.get("r")
            if not ref:
                continue
            match = CELL_REF_RE.fullmatch(ref)
            if not match:
                continue
            column_name = match.group(1)
            cells[column_to_index(column_name)] = self._cell_value(cell)
        return cells

    def _cell_value(self, cell: ET.Element) -> str:
        cell_type = cell.attrib.get("t")
        value = cell.find("main:v", NS)
        inline_string = cell.find("main:is", NS)

        if cell_type == "inlineStr" and inline_string is not None:
            return self._extract_inline_string(inline_string)
        if cell_type == "s" and value is not None and value.text:
            shared_index = int(value.text)
            if 0 <= shared_index < len(self._shared_strings):
                return self._shared_strings[shared_index]
            return ""
        if cell_type == "b" and value is not None and value.text is not None:
            return "TRUE" if value.text == "1" else "FALSE"
        if value is not None and value.text is not None:
            return value.text
        return ""

    def _extract_string_item(self, item: ET.Element) -> str:
        text_nodes = item.findall(".//main:t", NS)
        return "".join(node.text or "" for node in text_nodes)

    def _extract_inline_string(self, inline_string: ET.Element) -> str:
        text_nodes = inline_string.findall(".//main:t", NS)
        return "".join(node.text or "" for node in text_nodes)


def column_to_index(column_name: str) -> int:
    value = 0
    for character in column_name:
        value = (value * 26) + (ord(character.upper()) - 64)
    return value
