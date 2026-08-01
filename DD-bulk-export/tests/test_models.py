from __future__ import annotations

import pytest

from dd_bulk_export.models import CSV_COLUMNS, DictionaryRow, ScrapeResult


def make_term() -> DictionaryRow:
    return DictionaryRow(
        term_or_value_name="Battery Incident - Battery Cell",
        description="The specific cell type.",
        value_definition="",
        module="incident-analysis",
        submodule="battery-incident",
        row_type="term",
        parent_term_id="",
        parent_term_name="",
        record_id="Battery-Incident-Battery-Cell",
        term_id="Battery-Incident-Battery-Cell",
        source_sheet="incident_analysis_battery_incident_terms",
    )


def test_row_dict_uses_exact_schema_order() -> None:
    assert tuple(make_term().as_dict()) == CSV_COLUMNS


def test_term_requires_matching_record_and_term_ids() -> None:
    term = make_term()
    with pytest.raises(ValueError, match="same record_id and term_id"):
        DictionaryRow(
            term_or_value_name=term.term_or_value_name,
            description=term.description,
            value_definition="",
            module=term.module,
            submodule=term.submodule,
            row_type="term",
            parent_term_id="",
            parent_term_name="",
            record_id="one",
            term_id="two",
            source_sheet=term.source_sheet,
        )


def test_value_requires_parent_fields() -> None:
    with pytest.raises(ValueError, match="require parent"):
        DictionaryRow(
            term_or_value_name="Parent - VALUE",
            description="Description",
            value_definition="Definition",
            module="core",
            submodule="entity",
            row_type="value",
            parent_term_id="",
            parent_term_name="",
            record_id="Parent",
            term_id="Parent-VALUE",
            source_sheet="core_entity_terms",
        )


def test_scrape_result_validates_row_counts() -> None:
    with pytest.raises(ValueError, match="Row count"):
        ScrapeResult(
            source_url="https://neris.fsri.org/data-dictionary?module=x",
            rows=(make_term(),),
            pages_visited=1,
            term_count=1,
            value_count=1,
            accordion_count=1,
        )
