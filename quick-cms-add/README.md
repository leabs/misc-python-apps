# Quick CMS Add

Small macOS helper for importing spreadsheet rows into a Strapi repeatable component.

## What it does

- Reads a local `.xlsx` workbook directly. You do not need to copy from VS Code manually.
- Maps spreadsheet columns to Strapi `title`, `description`, and `definition`.
- Sets the `active` field to `True` for every imported row.
- Clicks `Add an entry` between rows so the next enum entry can be created.

## Current assumptions

- You are on macOS.
- You use a Chromium-based browser supported by AppleScript: `Brave Browser` or `Google Chrome`.
- The Strapi page is already open and shows the Enums section with one empty entry visible.
- The fields on the page are labeled `title`, `description`, `definition`, `source`, and `active`.

## Run

```bash
python3 app.py
```

## Recommended workflow

1. Open the target Strapi record in Brave or Chrome.
2. Scroll so the Enums section is visible and one blank entry is on screen.
3. Start `python3 app.py`.
4. Choose the `.xlsx` file and confirm the sheet and column mappings.
5. Click `Check Strapi Page`.
6. Click `Start Import`.

## Permissions

The first run may require macOS permission for the Python process or terminal app to control your browser.

- System Settings
- Privacy & Security
- Automation

If macOS blocks the browser step, grant permission and run the check again.

## Notes

- This version is intentionally lightweight and dependency-free.
- It only supports `.xlsx`.
- It does not click Strapi save or publish for you.
