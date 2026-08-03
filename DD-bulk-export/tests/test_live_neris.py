from __future__ import annotations

import csv
from pathlib import Path

import pytest

from dd_bulk_export.csv_io import read_template, write_merged_csv
from dd_bulk_export.models import BatchScrapeResult
from dd_bulk_export.scraper import NerisScraper


APP_DIRECTORY = Path(__file__).resolve().parents[1]
BATTERY_FIXTURE_URL = (
    "https://neris.fsri.org/data-dictionary"
    "?page=1&pageSize=100&module=incident-analysis-battery-incident"
)
PAGINATED_BATTERY_URL = (
    "https://neris.fsri.org/data-dictionary"
    "?page=4&pageSize=5&module=incident-analysis-battery-incident"
)
CORE_ENTITY_URL = (
    "https://neris.fsri.org/data-dictionary"
    "?page=1&pageSize=100&module=core-entity"
)
CONSUMER_PRODUCTS_URL = (
    "https://neris.fsri.org/data-dictionary"
    "?page=1&pageSize=100&module=incident-analysis-consumer-products"
)
SHARED_TACTICAL_TIMESTAMPS_URL = (
    "https://neris.fsri.org/data-dictionary"
    "?page=1&pageSize=100&module=shared-tactical-timestamps"
)


@pytest.mark.live
def test_battery_fixture_end_to_end(tmp_path: Path) -> None:
    result = NerisScraper(timeout_ms=30_000).scrape(BATTERY_FIXTURE_URL)

    assert result.pages_visited == 1
    assert result.term_count == 18
    assert result.accordion_count == 3
    assert result.value_count == 17
    assert len(result.rows) == 35

    pouch = next(
        row
        for row in result.rows
        if row.term_id == "Battery-Incident-Battery-Cell-POUCH_POLYMER"
    )
    assert pouch.description == "Pouch Polymer"
    assert "flexible laminate material" in pouch.value_definition
    assert pouch.module == "incident-analysis"
    assert pouch.submodule == "battery-incident"
    assert pouch.parent_term_id == "Battery-Incident-Battery-Cell"

    template_path = APP_DIRECTORY / "dd-test-template.csv"
    template_before = template_path.read_bytes()
    template = read_template(template_path)
    output_path = tmp_path / "battery-export.csv"
    summary = write_merged_csv(template_path, output_path, result.rows)

    assert summary.scraped_rows == 35
    assert summary.template_rows == 76
    assert summary.total_rows == 111
    assert template_path.read_bytes() == template_before
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["term_id"] for row in rows[:35]] == [
        row.term_id for row in result.rows
    ]
    assert rows[35:] == list(template.rows)
    assert "Entity - Coverage Set" in {
        row["term or value name"] for row in rows[35:]
    }


@pytest.mark.live
def test_battery_fixture_follows_enabled_pagination() -> None:
    result = NerisScraper(timeout_ms=30_000).scrape(PAGINATED_BATTERY_URL)

    assert result.source_url.endswith(
        "module=incident-analysis-battery-incident&page=1&pageSize=5"
    )
    assert result.pages_visited == 4
    assert result.term_count == 18
    assert result.accordion_count == 3
    assert result.value_count == 17
    assert len({row.term_id for row in result.rows}) == 35


@pytest.mark.live
def test_core_entity_fixture_and_legacy_template_drift() -> None:
    result = NerisScraper(timeout_ms=30_000).scrape(CORE_ENTITY_URL)

    assert result.pages_visited == 1
    assert result.term_count == 73
    assert result.accordion_count == 14
    assert result.value_count == 138
    assert len(result.rows) == 211
    scraped_names = {row.term_or_value_name for row in result.rows}
    assert "Entity - Station Coverage" not in scraped_names
    assert "Entity - Coverage Set" not in scraped_names
    assert "Entity - Coverage Type" not in scraped_names


@pytest.mark.live
def test_battery_then_core_batch_order_and_merged_counts(tmp_path: Path) -> None:
    battery = NerisScraper(timeout_ms=30_000).scrape(BATTERY_FIXTURE_URL)
    core = NerisScraper(timeout_ms=30_000).scrape(CORE_ENTITY_URL)
    batch = BatchScrapeResult((battery, core))
    template_path = APP_DIRECTORY / "dd-test-template.csv"
    template = read_template(template_path)
    output_path = tmp_path / "batch-export.csv"
    summary = write_merged_csv(template_path, output_path, batch.rows)
    assert [len(battery.rows), len(core.rows), len(batch.rows)] == [35, 211, 246]
    assert summary.total_rows == 322
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["term_id"] for row in rows[:35]] == [row.term_id for row in battery.rows]
    assert [row["term_id"] for row in rows[35:246]] == [row.term_id for row in core.rows]
    assert rows[246:] == list(template.rows)


@pytest.mark.live
def test_consumer_products_exact_supplied_url_is_dom_derived() -> None:
    result = NerisScraper(timeout_ms=30_000).scrape(CONSUMER_PRODUCTS_URL)
    assert {row.term_id for row in result.rows} >= {
        "Consumer-Products-Consumer-Product-Type",
        "Consumer-Products-Product-Contribution-IGNITION",
    }
    assert {(row.module, row.submodule) for row in result.rows} == {
        ("incident-analysis", "consumer-products")
    }


@pytest.mark.live
def test_additional_discovered_shared_module_is_dom_derived() -> None:
    result = NerisScraper(timeout_ms=30_000).scrape(
        SHARED_TACTICAL_TIMESTAMPS_URL
    )
    assert result.rows
    assert {(row.module, row.submodule) for row in result.rows} == {
        ("shared", "tactical-timestamps")
    }
