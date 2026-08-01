"""Strict template reading and safe, atomic CSV output writing."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import CSV_COLUMNS, DictionaryRow


class CsvTemplateError(ValueError):
    """Raised when the selected template does not have the required schema."""


class UnsafeOutputError(ValueError):
    """Raised when an output path could overwrite or corrupt user data."""


class OutputExistsError(FileExistsError):
    """Raised when an existing output was not explicitly approved."""


class OutputWriteError(OSError):
    """Raised when the completed temporary output cannot be installed safely."""


@dataclass(frozen=True, slots=True)
class TemplateCsv:
    path: Path
    rows: tuple[dict[str, str], ...]
    sha256: str


@dataclass(frozen=True, slots=True)
class WriteSummary:
    output_path: Path
    scraped_rows: int
    template_rows: int

    @property
    def total_rows(self) -> int:
        return self.scraped_rows + self.template_rows


def _normalized_path(path: Path) -> str:
    return os.path.normcase(str(path.expanduser().resolve(strict=False)))


def _paths_identify_same_file(first: Path, second: Path) -> bool:
    if _normalized_path(first) == _normalized_path(second):
        return True
    try:
        return first.exists() and second.exists() and os.path.samefile(first, second)
    except OSError:
        return False


def read_template(path: str | Path) -> TemplateCsv:
    """Read one byte snapshot while enforcing the exact header and row width."""

    template_path = Path(path).expanduser()
    if not template_path.is_file():
        raise CsvTemplateError(f"Template CSV does not exist: {template_path}")

    try:
        raw_bytes = template_path.read_bytes()
        decoded = raw_bytes.decode("utf-8-sig")
        with io.StringIO(decoded, newline="") as handle:
            reader = csv.DictReader(handle)
            actual_header = tuple(reader.fieldnames or ())
            if actual_header != CSV_COLUMNS:
                expected = ",".join(CSV_COLUMNS)
                actual = ",".join(actual_header) if actual_header else "<missing>"
                raise CsvTemplateError(
                    "Template header does not match the required 11-column schema. "
                    f"Expected: {expected}. Found: {actual}."
                )

            rows: list[dict[str, str]] = []
            for line_number, raw_row in enumerate(reader, start=2):
                if None in raw_row or any(value is None for value in raw_row.values()):
                    raise CsvTemplateError(
                        f"Template row {line_number} has more or fewer than 11 fields."
                    )
                rows.append({column: raw_row[column] for column in CSV_COLUMNS})
    except UnicodeDecodeError as exc:
        raise CsvTemplateError("Template CSV must be UTF-8 encoded.") from exc
    except csv.Error as exc:
        raise CsvTemplateError(f"Template CSV could not be parsed: {exc}") from exc

    return TemplateCsv(
        path=template_path.resolve(),
        rows=tuple(rows),
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
    )


def validate_output_path(
    template_path: str | Path,
    output_path: str | Path,
    *,
    allow_existing: bool,
) -> Path:
    """Validate that output is a separate CSV in an existing directory."""

    template = Path(template_path)
    output = Path(output_path).expanduser()
    if not str(output).strip():
        raise UnsafeOutputError("Choose a separate output CSV path.")
    if output.suffix.casefold() != ".csv":
        raise UnsafeOutputError("Output filename must end in .csv.")
    if _paths_identify_same_file(template, output):
        raise UnsafeOutputError("Output must not overwrite the selected template CSV.")
    if not output.parent.is_dir():
        raise UnsafeOutputError(f"Output directory does not exist: {output.parent}")
    if output.exists() and output.is_dir():
        raise UnsafeOutputError(f"Output path is a directory: {output}")
    if output.exists() and not allow_existing:
        raise OutputExistsError(f"Output already exists: {output}")
    return output.resolve(strict=False)


def write_merged_csv(
    template_path: str | Path,
    output_path: str | Path,
    scraped_rows: Iterable[DictionaryRow],
    *,
    overwrite: bool = False,
    expected_template_sha256: str | None = None,
) -> WriteSummary:
    """Write header + scraped rows + original rows without touching the template."""

    template = read_template(template_path)
    if (
        expected_template_sha256 is not None
        and template.sha256 != expected_template_sha256
    ):
        raise CsvTemplateError(
            "Template CSV changed since the preview was created; scrape again "
            "before saving."
        )
    output = validate_output_path(
        template.path,
        output_path,
        allow_existing=overwrite,
    )
    rows = tuple(scraped_rows)
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            writer = csv.DictWriter(
                handle,
                fieldnames=CSV_COLUMNS,
                extrasaction="raise",
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(row.as_dict() for row in rows)
            writer.writerows(template.rows)
            handle.flush()
            os.fsync(handle.fileno())

        if overwrite:
            os.replace(temporary_path, output)
            temporary_path = None
        elif os.name == "nt":
            try:
                # Windows os.rename is atomic on a volume and never replaces dst.
                # Unlike hard links, it also works on exFAT and common shares.
                os.rename(temporary_path, output)
            except FileExistsError as exc:
                raise OutputExistsError(f"Output already exists: {output}") from exc
            except OSError as exc:
                raise OutputWriteError(
                    f"Could not install the completed output safely: {exc}"
                ) from exc
            temporary_path = None
        else:
            try:
                os.link(temporary_path, output)
            except FileExistsError as exc:
                raise OutputExistsError(f"Output already exists: {output}") from exc
            except OSError as exc:
                raise OutputWriteError(
                    "Could not install the completed output without risking an "
                    f"overwrite: {exc}"
                ) from exc
            temporary_path.unlink()
            temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return WriteSummary(
        output_path=output,
        scraped_rows=len(rows),
        template_rows=len(template.rows),
    )
