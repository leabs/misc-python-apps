#!/usr/bin/env python3
"""Export NERIS fire departments as Meilisearch-ready NDJSON."""

import json
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


QUERY_URL = (
    "https://services5.arcgis.com/lPbcyJOcoLyZmvo6/arcgis/rest/services/"
    "NERIS%20Public%20Fire%20Departments/FeatureServer/0/query"
)
OUTPUT_PATH = Path(__file__).with_name("departments-meilisearch.ndjson")
CHUNK_SIZE = 500
REQUEST_ATTEMPTS = 4
NERIS_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class ExportError(RuntimeError):
    pass


def request_arcgis(**params):
    """POST an ArcGIS query, retrying short-lived failures."""
    request = Request(
        QUERY_URL,
        data=urlencode({**params, "f": "json"}).encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "NERIS fire department exporter",
        },
        method="POST",
    )

    for attempt in range(REQUEST_ATTEMPTS):
        try:
            with urlopen(request, timeout=30) as response:
                body = json.load(response)

            if not isinstance(body, dict):
                raise ExportError("ArcGIS returned an unexpected response")
            if "error" in body:
                raise ExportError(f"ArcGIS error: {body['error']}")

            return body
        except (URLError, TimeoutError, json.JSONDecodeError, ExportError) as error:
            if attempt == REQUEST_ATTEMPTS - 1:
                raise ExportError(f"ArcGIS request failed: {error}") from error
            time.sleep((attempt + 1) * 0.5)


def fetch_object_ids():
    object_ids = request_arcgis(where="1=1", returnIdsOnly="true").get("objectIds")

    if not isinstance(object_ids, list) or not object_ids:
        raise ExportError("ArcGIS returned no object IDs")
    if any(type(object_id) is not int for object_id in object_ids):
        raise ExportError("ArcGIS returned an invalid object ID")
    if len(object_ids) != len(set(object_ids)):
        raise ExportError("ArcGIS returned duplicate object IDs")

    return sorted(object_ids)


def iter_department_rows(object_ids):
    """Fetch the ObjectID snapshot in deterministic POST batches."""
    for offset in range(0, len(object_ids), CHUNK_SIZE):
        requested_ids = object_ids[offset : offset + CHUNK_SIZE]
        response = request_arcgis(
            objectIds=",".join(str(object_id) for object_id in requested_ids),
            outFields="OBJECTID,neris_id,name,city,state",
            returnGeometry="false",
            orderByFields="OBJECTID ASC",
        )

        try:
            rows = sorted(
                (feature["attributes"] for feature in response["features"]),
                key=lambda row: row["OBJECTID"],
            )
        except (KeyError, TypeError) as error:
            raise ExportError(f"Invalid feature chunk at offset {offset}") from error

        if [row["OBJECTID"] for row in rows] != requested_ids:
            raise ExportError(f"Incomplete feature chunk at offset {offset}")

        yield from rows
        print(
            f"Fetched {offset + len(requested_ids):,}/{len(object_ids):,}",
            end="\r",
            flush=True,
        )

    print()


def required_text(row, field):
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ExportError(f"Missing {field} at OBJECTID {row.get('OBJECTID')}")
    return value.strip()


def build_document(row):
    neris_id = required_text(row, "neris_id")
    title = required_text(row, "name")
    city = required_text(row, "city")
    state = required_text(row, "state")

    if not NERIS_ID_PATTERN.fullmatch(neris_id):
        raise ExportError(f"Invalid neris_id at OBJECTID {row.get('OBJECTID')}")

    return {
        "id": f"departments-{neris_id}",
        "title": title,
        "city": city,
        "state": state,
        "excerpt": f"{city}, {state}",
        "content": f"{title} {neris_id} {city} {state}",
        "url": f"/departments/{neris_id}",
        "source": "departments",
        "sourceLabel": "Departments",
    }


def to_ndjson(document):
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n"


def export_departments():
    object_ids = fetch_object_ids()
    document_ids = set()
    print(f"Found {len(object_ids):,} departments")

    with tempfile.TemporaryDirectory(
        dir=OUTPUT_PATH.parent, prefix=".department-export-"
    ) as temp_dir:
        temp_path = Path(temp_dir) / OUTPUT_PATH.name

        with temp_path.open("w", encoding="utf-8", newline="\n") as output_file:
            for row in iter_department_rows(object_ids):
                document = build_document(row)
                if document["id"] in document_ids:
                    raise ExportError(f"Duplicate document id {document['id']}")
                document_ids.add(document["id"])

                output_file.write(to_ndjson(document))

        if fetch_object_ids() != object_ids:
            raise ExportError("Department IDs changed during export; run it again")
        if len(document_ids) != len(object_ids):
            raise ExportError("The export has an unexpected number of documents")

        temp_path.chmod(0o644)
        temp_path.replace(OUTPUT_PATH)

    return len(object_ids)


def main():
    try:
        records = export_departments()
    except (ExportError, OSError) as error:
        print(f"Export failed: {error}", file=sys.stderr)
        return 1

    print(f"Wrote {records:,} departments to {OUTPUT_PATH}")
    print(f"Size: {OUTPUT_PATH.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
