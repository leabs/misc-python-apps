from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

from dd_bulk_export.csv_io import (
    CsvTemplateError,
    OutputExistsError,
    UnsafeOutputError,
    read_template,
    validate_output_path,
    write_merged_csv,
)
from dd_bulk_export.models import CSV_COLUMNS, DictionaryRow


APP_DIRECTORY = Path(__file__).resolve().parents[1]


def _write_template(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _template_row(name: str = "Existing, legacy term") -> dict[str, str]:
    return {
        "term or value name": name,
        "description": "Unicode café\nand a second line",
        "value_definition": "",
        "module": "core",
        "submodule": "entity",
        "type": "term",
        "parent_term_id": "",
        "parent_term_name": "",
        "record_id": "Existing-Legacy-Term",
        "term_id": "Existing-Legacy-Term",
        "source_sheet": "core_entity_terms",
    }


def _scraped_row() -> DictionaryRow:
    return DictionaryRow(
        term_or_value_name="Battery Incident - Battery Cell - POUCH_POLYMER",
        description="Pouch, polymer",
        value_definition="Flexible laminate\nwith aluminum.",
        module="incident-analysis",
        submodule="battery-incident",
        row_type="value",
        parent_term_id="Battery-Incident-Battery-Cell",
        parent_term_name="Battery Incident - Battery Cell",
        record_id="Battery-Incident-Battery-Cell",
        term_id="Battery-Incident-Battery-Cell-POUCH_POLYMER",
        source_sheet="incident_analysis_battery_incident_terms",
    )


def test_supplied_template_has_fixed_schema_and_76_rows() -> None:
    template = read_template(APP_DIRECTORY / "dd-test-template.csv")
    assert len(template.rows) == 76
    assert template.rows[0]["term or value name"] == "Entity - NERIS ID"
    assert "Entity - Station Coverage" in {
        row["term or value name"] for row in template.rows
    }


def test_write_prepends_and_preserves_logical_fields(tmp_path: Path) -> None:
    template_path = tmp_path / "template.csv"
    output_path = tmp_path / "output.csv"
    original_row = _template_row()
    _write_template(template_path, [original_row])
    original_bytes = template_path.read_bytes()

    summary = write_merged_csv(template_path, output_path, [_scraped_row()])

    assert summary.scraped_rows == 1
    assert summary.template_rows == 1
    assert summary.total_rows == 2
    assert template_path.read_bytes() == original_bytes
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        assert tuple(reader.fieldnames or ()) == CSV_COLUMNS
    assert rows[0] == _scraped_row().as_dict()
    assert rows[1] == original_row


def test_writer_refuses_template_as_output(tmp_path: Path) -> None:
    template_path = tmp_path / "template.csv"
    _write_template(template_path, [_template_row()])
    with pytest.raises(UnsafeOutputError, match="must not overwrite"):
        write_merged_csv(template_path, template_path, [_scraped_row()])


def test_writer_refuses_a_filesystem_alias_of_template(tmp_path: Path) -> None:
    template_path = tmp_path / "template.csv"
    alias_path = tmp_path / "template-alias.csv"
    _write_template(template_path, [_template_row()])
    alias_path.hardlink_to(template_path)

    with pytest.raises(UnsafeOutputError, match="must not overwrite"):
        write_merged_csv(template_path, alias_path, [_scraped_row()], overwrite=True)


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length path syntax")
def test_writer_refuses_windows_extended_path_alias(tmp_path: Path) -> None:
    template_path = tmp_path / "template.csv"
    _write_template(template_path, [_template_row()])
    extended_alias = Path(f"\\\\?\\{template_path.resolve()}")

    with pytest.raises(UnsafeOutputError, match="must not overwrite"):
        write_merged_csv(
            template_path,
            extended_alias,
            [_scraped_row()],
            overwrite=True,
        )


def test_writer_does_not_silently_replace_existing_output(tmp_path: Path) -> None:
    template_path = tmp_path / "template.csv"
    output_path = tmp_path / "output.csv"
    _write_template(template_path, [_template_row()])
    output_path.write_text("keep me", encoding="utf-8")

    with pytest.raises(OutputExistsError):
        write_merged_csv(template_path, output_path, [_scraped_row()])
    assert output_path.read_text(encoding="utf-8") == "keep me"


def test_explicit_overwrite_replaces_only_output(tmp_path: Path) -> None:
    template_path = tmp_path / "template.csv"
    output_path = tmp_path / "output.csv"
    _write_template(template_path, [_template_row()])
    template_bytes = template_path.read_bytes()
    output_path.write_text("old output", encoding="utf-8")

    write_merged_csv(
        template_path,
        output_path,
        [_scraped_row()],
        overwrite=True,
    )

    assert template_path.read_bytes() == template_bytes
    assert output_path.read_text(encoding="utf-8").startswith(CSV_COLUMNS[0])


def test_template_header_order_is_strict(tmp_path: Path) -> None:
    template_path = tmp_path / "wrong.csv"
    template_path.write_text("description,term or value name\ntext,name\n", encoding="utf-8")
    with pytest.raises(CsvTemplateError, match="does not match"):
        read_template(template_path)


def test_output_must_be_csv_in_existing_directory(tmp_path: Path) -> None:
    template_path = tmp_path / "template.csv"
    _write_template(template_path, [_template_row()])
    with pytest.raises(UnsafeOutputError, match="end in .csv"):
        validate_output_path(template_path, tmp_path / "output.txt", allow_existing=True)
    with pytest.raises(UnsafeOutputError, match="does not exist"):
        validate_output_path(
            template_path,
            tmp_path / "missing" / "output.csv",
            allow_existing=True,
        )
