# DD Bulk Export

DD Bulk Export is a small Tkinter app that captures a complete NERIS
data-dictionary module and adds it to an existing fixed-schema CSV.

The scraper opens every outer **Values** accordion and every nested value
accordion, follows enabled next-page links, and collects both base terms and
their Description/Definition value details. Saving creates a separate CSV with:

1. the exact 11-column template header;
2. all newly scraped rows; and
3. every original template row below them.

The selected template is never opened for writing. Existing output files are
only replaced after an explicit GUI confirmation. If the template changes
after a preview, saving is rejected until a fresh scrape is completed.

## Install on Windows

From this directory:

```powershell
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

The reported Python version must be 3.10 or newer.

The explicit browser install is recommended. If it has not been run, the app
also tries an installed Google Chrome and then Microsoft Edge.

## Run

```powershell
python app.py
```

The repository's root app picker can also launch this directory through its
`main.py` compatibility entry point. Both launchers automatically use this
directory's `.venv` when it exists, even if the picker itself uses another
Python interpreter.

In the app:

1. Paste any public `https://neris.fsri.org/data-dictionary` URL containing a
   `module` query value.
2. Choose the baseline CSV. The supplied `dd-test-template.csv` is selected by
   default.
3. Choose a different `.csv` output path.
4. Select **Preview / Scrape** and review the counts and first rows.
5. Select **Save output**.

The app always normalizes the starting page to page 1, uses the URL's requested
page size up to NERIS's 500-row maximum, and follows the site's enabled Next
link until the module is complete. Use **Stop** to cancel between browser
actions.

## Test

Install the development requirements, then run the package suite:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

The live browser fixture is opt-in so routine tests remain deterministic:

```powershell
python -m pytest --run-live
```

## Output schema

The column order is fixed to the supplied template:

```text
term or value name,description,value_definition,module,submodule,type,parent_term_id,parent_term_name,record_id,term_id,source_sheet
```

For a base term, `record_id` and `term_id` are the stable NERIS term ID. For a
nested value, `record_id` and `parent_term_id` are the parent term ID while
`term_id` is the nested value's stable ID. The CSV `type` column is `term` or
`value`; it is intentionally not the website's field datatype.

## Limitation

This app reads the rendered public NERIS page. A future NERIS markup or
accessibility-label change may require selector updates; failures stop before
any output is written and are shown in the progress/error log.
