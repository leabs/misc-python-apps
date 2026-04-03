from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from quick_cms_add.strapi_bridge import AutomationError, RowPayload, StrapiBridge
from quick_cms_add.xlsx_reader import SheetRow, WorkbookError, XlsxWorkbook


BROWSERS = ["Brave Browser", "Google Chrome"]
DEFAULT_GEOMETRY = "860x720"


@dataclass(frozen=True)
class ColumnMapping:
    title: str
    description: str
    definition: str
    source: str


class ImportWorker(threading.Thread):
    def __init__(
        self,
        *,
        bridge: StrapiBridge,
        rows: list[SheetRow],
        mapping: ColumnMapping,
        delay_seconds: float,
        progress_queue: queue.Queue[tuple[str, str]],
        stop_event: threading.Event,
    ) -> None:
        super().__init__(daemon=True)
        self.bridge = bridge
        self.rows = rows
        self.mapping = mapping
        self.delay_seconds = delay_seconds
        self.progress_queue = progress_queue
        self.stop_event = stop_event

    def run(self) -> None:
        total = len(self.rows)
        try:
            for index, row in enumerate(self.rows, start=1):
                if self.stop_event.is_set():
                    self.progress_queue.put(("status", "Import stopped."))
                    return

                payload = RowPayload(
                    title=row.values.get(self.mapping.title, ""),
                    description=row.values.get(self.mapping.description, ""),
                    definition=row.values.get(self.mapping.definition, ""),
                    source=row.values.get(self.mapping.source, "") if self.mapping.source else "",
                )
                add_after = index < total
                result = self.bridge.fill_row(payload, add_after=add_after)
                self.progress_queue.put(
                    (
                        "log",
                        f"Imported sheet row {row.row_number} ({index}/{total}): {result.get('row', payload.title)}",
                    )
                )
                if add_after:
                    time.sleep(self.delay_seconds)
        except AutomationError as exc:
            self.progress_queue.put(("error", str(exc)))
            return
        except Exception as exc:  # pragma: no cover - unexpected safety net
            self.progress_queue.put(("error", f"Unexpected failure: {exc}"))
            return

        self.progress_queue.put(("done", f"Imported {total} row(s)."))


class QuickCmsAddApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Quick CMS Add")
        self.geometry(DEFAULT_GEOMETRY)
        self.minsize(760, 680)

        self.workbook_path = tk.StringVar()
        self.sheet_name = tk.StringVar()
        self.browser_name = tk.StringVar(value=BROWSERS[0])
        self.start_row = tk.StringVar(value="2")
        self.delay_seconds = tk.StringVar(value="0.6")
        self.title_column = tk.StringVar()
        self.description_column = tk.StringVar()
        self.definition_column = tk.StringVar()
        self.source_column = tk.StringVar(value="")

        self._headers: list[str] = []
        self._rows: list[SheetRow] = []
        self._workbook: XlsxWorkbook | None = None
        self._progress_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._worker: ImportWorker | None = None
        self._stop_event = threading.Event()
        self._mapping_combos: dict[str, ttk.Combobox] = {}

        self._build_ui()
        self.after(150, self._drain_progress_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        instructions = (
            "Choose the XLSX file, confirm the sheet and column mappings, then open the Strapi page with one empty "
            "Enums entry visible. The importer fills title, description, definition, sets active to True, and clicks "
            "Add an entry between rows."
        )
        instructions_label = ttk.Label(self, text=instructions, wraplength=780, justify="left")
        instructions_label.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))

        file_frame = ttk.LabelFrame(self, text="Workbook")
        file_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=8)
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="File").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        ttk.Entry(file_frame, textvariable=self.workbook_path).grid(
            row=0, column=1, sticky="ew", padx=10, pady=8
        )
        ttk.Button(file_frame, text="Choose…", command=self._choose_workbook).grid(
            row=0, column=2, sticky="ew", padx=(0, 10), pady=8
        )

        ttk.Label(file_frame, text="Sheet").grid(row=1, column=0, sticky="w", padx=10, pady=8)
        self.sheet_combo = ttk.Combobox(file_frame, textvariable=self.sheet_name, state="readonly")
        self.sheet_combo.grid(row=1, column=1, sticky="ew", padx=10, pady=8)
        self.sheet_combo.bind("<<ComboboxSelected>>", lambda _event: self._load_selected_sheet())
        ttk.Button(file_frame, text="Reload", command=self._reload_workbook).grid(
            row=1, column=2, sticky="ew", padx=(0, 10), pady=8
        )

        mapping_frame = ttk.LabelFrame(self, text="Mapping")
        mapping_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
        mapping_frame.columnconfigure(1, weight=1)
        mapping_frame.columnconfigure(3, weight=1)

        self._build_mapping_row(mapping_frame, 0, "Title", self.title_column)
        self._build_mapping_row(mapping_frame, 1, "Description", self.description_column)
        self._build_mapping_row(mapping_frame, 2, "Definition", self.definition_column)
        self._build_mapping_row(mapping_frame, 3, "Source (optional)", self.source_column)

        settings_frame = ttk.LabelFrame(self, text="Import")
        settings_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=8)
        settings_frame.columnconfigure(1, weight=1)
        settings_frame.columnconfigure(3, weight=1)

        ttk.Label(settings_frame, text="Browser").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        ttk.Combobox(
            settings_frame,
            textvariable=self.browser_name,
            values=BROWSERS,
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=10, pady=8)

        ttk.Label(settings_frame, text="Start row").grid(row=0, column=2, sticky="w", padx=10, pady=8)
        ttk.Entry(settings_frame, textvariable=self.start_row, width=8).grid(
            row=0, column=3, sticky="w", padx=10, pady=8
        )

        ttk.Label(settings_frame, text="Delay (seconds)").grid(row=1, column=0, sticky="w", padx=10, pady=8)
        ttk.Entry(settings_frame, textvariable=self.delay_seconds, width=8).grid(
            row=1, column=1, sticky="w", padx=10, pady=8
        )

        button_frame = ttk.Frame(settings_frame)
        button_frame.grid(row=1, column=2, columnspan=2, sticky="e", padx=10, pady=8)
        ttk.Button(button_frame, text="Check Strapi Page", command=self._check_page).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(button_frame, text="Start Import", command=self._start_import).grid(row=0, column=1, padx=4)
        ttk.Button(button_frame, text="Stop", command=self._stop_import).grid(row=0, column=2, padx=(8, 0))

        log_frame = ttk.LabelFrame(self, text="Preview / Log")
        log_frame.grid(row=4, column=0, sticky="nsew", padx=16, pady=(8, 16))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, wrap="word", height=18)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.configure(state="disabled")

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _build_mapping_row(self, parent: ttk.LabelFrame, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=8)
        combo = ttk.Combobox(parent, textvariable=variable, state="readonly")
        combo.grid(row=row, column=1, columnspan=3, sticky="ew", padx=10, pady=8)
        self._mapping_combos[variable._name] = combo

    def _choose_workbook(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose workbook",
            filetypes=[("Excel workbooks", "*.xlsx")],
        )
        if not selected:
            return
        self.workbook_path.set(selected)
        self._reload_workbook()

    def _reload_workbook(self) -> None:
        path = self.workbook_path.get().strip()
        if not path:
            return
        self._close_workbook()
        try:
            self._workbook = XlsxWorkbook(path)
        except WorkbookError as exc:
            self._append_log(f"Workbook error: {exc}")
            messagebox.showerror("Workbook error", str(exc))
            return

        sheet_names = self._workbook.sheet_names
        self.sheet_combo.configure(values=sheet_names)
        if sheet_names:
            self.sheet_name.set(sheet_names[0])
            self._load_selected_sheet()

    def _load_selected_sheet(self) -> None:
        if self._workbook is None:
            return
        try:
            headers, rows = self._workbook.read_sheet(self.sheet_name.get())
        except WorkbookError as exc:
            self._append_log(f"Sheet error: {exc}")
            messagebox.showerror("Sheet error", str(exc))
            return

        self._headers = headers
        self._rows = rows
        self._set_mapping_options(headers)
        self._set_default_mappings(headers)
        self._append_preview()

    def _set_mapping_options(self, headers: list[str]) -> None:
        options = [""] + headers
        for variable in (
            self.title_column,
            self.description_column,
            self.definition_column,
            self.source_column,
        ):
            self._mapping_combos[variable._name].configure(values=options)

    def _set_default_mappings(self, headers: list[str]) -> None:
        if not self.title_column.get():
            self.title_column.set(self._guess_header(headers, ["value", "title", "term"]))
        if not self.description_column.get():
            self.description_column.set(self._guess_header(headers, ["description", "desc"]))
        if not self.definition_column.get():
            self.definition_column.set(self._guess_header(headers, ["definition", "def"]))
        if not self.source_column.get():
            self.source_column.set(self._guess_header(headers, ["source"]))

    def _guess_header(self, headers: list[str], candidates: list[str]) -> str:
        normalized = {header.lower(): header for header in headers}
        for candidate in candidates:
            if candidate in normalized:
                return normalized[candidate]
        for header in headers:
            lowered = header.lower()
            if any(candidate in lowered for candidate in candidates):
                return header
        return ""

    def _append_preview(self) -> None:
        preview_lines = [
            f"Loaded {len(self._rows)} data row(s) from '{self.sheet_name.get()}'.",
            "Headers: " + ", ".join(self._headers),
        ]
        for row in self._rows[:3]:
            preview_lines.append(f"Row {row.row_number}: {row.values}")
        self._replace_log("\n".join(preview_lines))

    def _check_page(self) -> None:
        try:
            bridge = StrapiBridge(self.browser_name.get())
            result = bridge.probe_page()
        except AutomationError as exc:
            self._append_log(f"Strapi page check failed: {exc}")
            messagebox.showerror("Browser automation error", str(exc))
            return
        self._append_log(
            "Strapi page check passed: "
            f"url={result.get('url')} fields={result.get('fields')} addButton={result.get('addButton')}"
        )

    def _start_import(self) -> None:
        if self._worker and self._worker.is_alive():
            messagebox.showinfo("Import running", "An import is already running.")
            return
        try:
            start_row = int(self.start_row.get())
        except ValueError:
            messagebox.showerror("Invalid start row", "Start row must be an integer.")
            return
        try:
            delay_seconds = float(self.delay_seconds.get())
        except ValueError:
            messagebox.showerror("Invalid delay", "Delay must be a number.")
            return
        mapping = self._current_mapping()
        if not mapping:
            return

        selected_rows = [row for row in self._rows if row.row_number >= start_row]
        if not selected_rows:
            messagebox.showinfo("No rows", "There are no rows to import from the selected start row.")
            return

        self._stop_event.clear()
        self._append_log(
            f"Starting import of {len(selected_rows)} row(s) from sheet '{self.sheet_name.get()}' into {self.browser_name.get()}."
        )
        self._worker = ImportWorker(
            bridge=StrapiBridge(self.browser_name.get()),
            rows=selected_rows,
            mapping=mapping,
            delay_seconds=delay_seconds,
            progress_queue=self._progress_queue,
            stop_event=self._stop_event,
        )
        self._worker.start()

    def _stop_import(self) -> None:
        self._stop_event.set()

    def _current_mapping(self) -> ColumnMapping | None:
        required = {
            "Title": self.title_column.get().strip(),
            "Description": self.description_column.get().strip(),
            "Definition": self.definition_column.get().strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            messagebox.showerror("Missing mapping", ", ".join(missing) + " must be mapped.")
            return None
        return ColumnMapping(
            title=required["Title"],
            description=required["Description"],
            definition=required["Definition"],
            source=self.source_column.get().strip(),
        )

    def _drain_progress_queue(self) -> None:
        while True:
            try:
                level, message = self._progress_queue.get_nowait()
            except queue.Empty:
                break

            if level == "error":
                self._append_log(f"Error: {message}")
                messagebox.showerror("Import failed", message)
            elif level == "done":
                self._append_log(message)
                messagebox.showinfo("Import finished", message)
            else:
                self._append_log(message)

        self.after(150, self._drain_progress_queue)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _replace_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("1.0", message + "\n")
        self.log_text.configure(state="disabled")

    def _close_workbook(self) -> None:
        if self._workbook is not None:
            self._workbook.close()
            self._workbook = None

    def _on_close(self) -> None:
        self._stop_event.set()
        self._close_workbook()
        self.destroy()


def run_app() -> None:
    app = QuickCmsAddApp()
    app.mainloop()
