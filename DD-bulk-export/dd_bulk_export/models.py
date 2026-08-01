"""Typed records shared by the scraper, CSV writer, and GUI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


CSV_COLUMNS: Final[tuple[str, ...]] = (
    "term or value name",
    "description",
    "value_definition",
    "module",
    "submodule",
    "type",
    "parent_term_id",
    "parent_term_name",
    "record_id",
    "term_id",
    "source_sheet",
)


@dataclass(frozen=True, slots=True)
class DictionaryRow:
    """One row in the fixed DD bulk-export CSV schema."""

    term_or_value_name: str
    description: str
    value_definition: str
    module: str
    submodule: str
    row_type: str
    parent_term_id: str
    parent_term_name: str
    record_id: str
    term_id: str
    source_sheet: str

    def __post_init__(self) -> None:
        required = {
            "term or value name": self.term_or_value_name,
            "module": self.module,
            "submodule": self.submodule,
            "record_id": self.record_id,
            "term_id": self.term_id,
            "source_sheet": self.source_sheet,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(f"Missing required CSV fields: {', '.join(missing)}")

        if self.row_type not in {"term", "value"}:
            raise ValueError("CSV type must be either 'term' or 'value'.")

        if self.row_type == "term":
            if self.parent_term_id or self.parent_term_name:
                raise ValueError("Term rows cannot have parent fields.")
            if self.record_id != self.term_id:
                raise ValueError("Term rows must use the same record_id and term_id.")
        else:
            if not self.parent_term_id.strip() or not self.parent_term_name.strip():
                raise ValueError("Value rows require parent term fields.")
            if self.record_id != self.parent_term_id:
                raise ValueError("Value record_id must equal parent_term_id.")

    def as_dict(self) -> dict[str, str]:
        """Return this row using the exact template header names and order."""

        return {
            "term or value name": self.term_or_value_name,
            "description": self.description,
            "value_definition": self.value_definition,
            "module": self.module,
            "submodule": self.submodule,
            "type": self.row_type,
            "parent_term_id": self.parent_term_id,
            "parent_term_name": self.parent_term_name,
            "record_id": self.record_id,
            "term_id": self.term_id,
            "source_sheet": self.source_sheet,
        }


@dataclass(frozen=True, slots=True)
class ScrapeResult:
    """Validated result returned after every requested page is scraped."""

    source_url: str
    rows: tuple[DictionaryRow, ...]
    pages_visited: int
    term_count: int
    value_count: int
    accordion_count: int

    def __post_init__(self) -> None:
        if self.pages_visited < 1:
            raise ValueError("A scrape result must include at least one page.")
        if self.term_count < 1:
            raise ValueError("A scrape result must include at least one term.")
        if self.value_count < 0 or self.accordion_count < 0:
            raise ValueError("Scrape counts cannot be negative.")
        if len(self.rows) != self.term_count + self.value_count:
            raise ValueError("Row count does not match term and value counts.")
