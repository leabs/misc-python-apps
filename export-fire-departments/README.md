# Export Fire Departments

This script downloads the public NERIS fire department layer and writes one
Meilisearch document per line in NDJSON format.

It uses only the Python standard library, so there is nothing to install.

## Run

```bash
cd export-fire-departments
python3 main.py
```

The output is `departments-meilisearch.ndjson` beside the script.

Each line has exactly these fields, in this order:

```json
{"id":"departments-FD01001325","title":"Old Kingston Browntown Volunteer Fire Department","city":"Prattville","state":"AL","excerpt":"Prattville, AL","content":"Old Kingston Browntown Volunteer Fire Department FD01001325 Prattville AL","url":"/departments/FD01001325","source":"departments","sourceLabel":"Departments"}
```

The source is the Department layer (`FeatureServer/0`) from
[NERIS Public Fire Departments](https://hub.arcgis.com/maps/0ac459746be44023a1b33ba00bb5f628/about).
The script snapshots the source IDs, downloads them in batches, and stops
without replacing the output if the ArcGIS ObjectID set changes or any row is
incomplete.

For Meilisearch, this is NDJSON and the primary key is `id`.

## Test

```bash
python3 -m unittest discover -s tests
```
