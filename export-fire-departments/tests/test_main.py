import json
import unittest

from main import ExportError, build_document, to_ndjson


SAMPLE_ROW = {
    "OBJECTID": 1,
    "neris_id": "FD01001325",
    "name": "Old Kingston Browntown Volunteer Fire Department",
    "city": "Prattville",
    "state": "AL",
}

SAMPLE_DOCUMENT = {
    "id": "departments-FD01001325",
    "title": "Old Kingston Browntown Volunteer Fire Department",
    "city": "Prattville",
    "state": "AL",
    "excerpt": "Prattville, AL",
    "content": (
        "Old Kingston Browntown Volunteer Fire Department "
        "FD01001325 Prattville AL"
    ),
    "url": "/departments/FD01001325",
    "source": "departments",
    "sourceLabel": "Departments",
}

EXPECTED_KEYS = (
    "id",
    "title",
    "city",
    "state",
    "excerpt",
    "content",
    "url",
    "source",
    "sourceLabel",
)


class BuildDocumentTests(unittest.TestCase):
    def test_matches_requested_sample_and_key_order(self) -> None:
        document = build_document(SAMPLE_ROW)

        self.assertEqual(document, SAMPLE_DOCUMENT)
        self.assertEqual(tuple(document), EXPECTED_KEYS)

    def test_trims_source_values(self) -> None:
        row = {
            **SAMPLE_ROW,
            "neris_id": " FD01001325 ",
            "name": " Old Kingston Browntown Volunteer Fire Department ",
            "city": " Prattville ",
            "state": " AL ",
        }

        self.assertEqual(build_document(row), SAMPLE_DOCUMENT)

    def test_rejects_missing_required_values(self) -> None:
        for field in ("neris_id", "name", "city", "state"):
            with self.subTest(field=field):
                row = {**SAMPLE_ROW, field: " "}
                with self.assertRaisesRegex(ExportError, f"Missing {field}"):
                    build_document(row)

    def test_rejects_invalid_neris_id(self) -> None:
        row = {**SAMPLE_ROW, "neris_id": "FD01/001325"}

        with self.assertRaisesRegex(ExportError, "Invalid neris_id"):
            build_document(row)

    def test_serializes_one_compact_utf8_line(self) -> None:
        document = {**SAMPLE_DOCUMENT, "title": "Montréal Fire Department"}
        line = to_ndjson(document)

        self.assertEqual(json.loads(line), document)
        self.assertTrue(line.endswith("\n"))
        self.assertNotIn(": ", line)
        self.assertIn("Montréal", line)


if __name__ == "__main__":
    unittest.main()
