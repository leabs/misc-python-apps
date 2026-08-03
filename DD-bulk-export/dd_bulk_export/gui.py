"""Tkinter front end for previewing and saving NERIS dictionary exports."""

from __future__ import annotations

import csv
import hashlib
import io
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from .csv_io import (
    OutputExistsError,
    UnsafeOutputError,
    read_template,
    validate_output_path,
    write_merged_csv,
)
from .models import BatchScrapeResult, CSV_COLUMNS
from .scraper import (
    InvalidNerisUrl,
    NerisScraper,
    ScrapeCancelled,
    normalize_start_urls,
)


def default_paths(app_directory: Path) -> tuple[Path, Path]:
    template = app_directory / "dd-test-template.csv"
    output = app_directory / "dd-test-template__export.csv"
    return template, output


def _path_signature(path: str) -> str:
    return str(Path(path).expanduser().resolve(strict=False)).casefold()


def _file_signature(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).expanduser().open("rb") as handle:
        for chunk in iter(lambda: handle.read(128 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DdBulkExportApp:
    """Fixed-schema scrape, preview, and save workflow."""

    POLL_INTERVAL_MS = 100

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("NERIS DD Bulk Export")
        self.root.geometry("1100x720")
        self.root.minsize(820, 560)

        app_directory = Path(__file__).resolve().parents[1]
        template, output = default_paths(app_directory)
        self.template_var = tk.StringVar(value=str(template))
        self.output_var = tk.StringVar(value=str(output))
        self.status_var = tk.StringVar(value="Ready to scrape.")

        self._messages: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._cancel_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._busy = False
        self._closing = False
        self._result: BatchScrapeResult | None = None
        self._result_signature: tuple[tuple[str, ...], str, str] | None = None

        self._build_layout()
        self.template_var.trace_add("write", self._input_changed)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(self.POLL_INTERVAL_MS, self._poll_messages)

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(3, weight=1)

        input_frame = ttk.LabelFrame(self.root, text="Export inputs", padding=12)
        input_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        input_frame.columnconfigure(1, weight=1)

        ttk.Label(input_frame, text="NERIS URLs\n(one per line)").grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=4
        )
        self.url_entry = ScrolledText(input_frame, height=5, wrap="none")
        self.url_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=4)
        self.url_entry.bind("<KeyRelease>", self._input_changed)

        ttk.Label(input_frame, text="Template CSV").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=4
        )
        self.template_entry = ttk.Entry(
            input_frame, textvariable=self.template_var
        )
        self.template_entry.grid(row=1, column=1, sticky="ew", pady=4)
        self.template_button = ttk.Button(
            input_frame, text="Browse…", command=self._choose_template
        )
        self.template_button.grid(row=1, column=2, padx=(8, 0), pady=4)

        ttk.Label(input_frame, text="New output CSV").grid(
            row=2, column=0, sticky="w", padx=(0, 10), pady=4
        )
        self.output_entry = ttk.Entry(input_frame, textvariable=self.output_var)
        self.output_entry.grid(row=2, column=1, sticky="ew", pady=4)
        self.output_button = ttk.Button(
            input_frame, text="Browse…", command=self._choose_output
        )
        self.output_button.grid(row=2, column=2, padx=(8, 0), pady=4)

        actions = ttk.Frame(self.root, padding=(12, 6))
        actions.grid(row=1, column=0, sticky="ew")
        actions.columnconfigure(3, weight=1)
        self.scrape_button = ttk.Button(
            actions, text="Preview / Scrape", command=self._start_scrape
        )
        self.scrape_button.grid(row=0, column=0, padx=(0, 8))
        self.save_button = ttk.Button(
            actions, text="Save output", command=self._save, state="disabled"
        )
        self.save_button.grid(row=0, column=1, padx=(0, 8))
        self.stop_button = ttk.Button(
            actions, text="Stop", command=self._stop, state="disabled"
        )
        self.stop_button.grid(row=0, column=2)
        ttk.Label(actions, textvariable=self.status_var).grid(
            row=0, column=3, sticky="e"
        )

        separator = ttk.Separator(self.root)
        separator.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 6))

        notebook = ttk.Notebook(self.root)
        notebook.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))

        preview_frame = ttk.Frame(notebook, padding=8)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.preview_text = tk.Text(
            preview_frame,
            wrap="none",
            font=("TkFixedFont", 9),
            state="disabled",
        )
        self.preview_text.grid(row=0, column=0, sticky="nsew")
        preview_y_scroll = ttk.Scrollbar(
            preview_frame,
            orient="vertical",
            command=self.preview_text.yview,
        )
        preview_y_scroll.grid(row=0, column=1, sticky="ns")
        preview_x_scroll = ttk.Scrollbar(
            preview_frame,
            orient="horizontal",
            command=self.preview_text.xview,
        )
        preview_x_scroll.grid(row=1, column=0, sticky="ew")
        self.preview_text.configure(
            yscrollcommand=preview_y_scroll.set,
            xscrollcommand=preview_x_scroll.set,
        )
        notebook.add(preview_frame, text="Preview")

        log_frame = ttk.Frame(notebook, padding=8)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = ScrolledText(log_frame, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        notebook.add(log_frame, text="Progress / errors")

    def _choose_template(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose the baseline CSV",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            initialdir=str(Path(self.template_var.get()).expanduser().parent),
        )
        if selected:
            self.template_var.set(selected)
            current_output = Path(selected).with_name(
                f"{Path(selected).stem}__export.csv"
            )
            self.output_var.set(str(current_output))

    def _choose_output(self) -> None:
        selected = filedialog.asksaveasfilename(
            title="Choose a new output CSV",
            defaultextension=".csv",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            initialdir=str(Path(self.output_var.get()).expanduser().parent),
            initialfile=Path(self.output_var.get()).name,
        )
        if selected:
            self.output_var.set(selected)

    def _input_changed(self, *_args: object) -> None:
        if self._result is not None:
            self._result = None
            self._result_signature = None
            self.save_button.configure(state="disabled")
            self.status_var.set("Inputs changed; scrape again to refresh the preview.")
            self._set_preview("")

    def _url_text(self) -> str:
        if hasattr(self, "url_entry"):
            return self.url_entry.get("1.0", "end-1c")
        return self.url_var.get()  # compatibility for isolated unit-test apps

    def _current_signature(self) -> tuple[tuple[str, ...], str, str]:
        return (
            normalize_start_urls(self._url_text()),
            _path_signature(self.template_var.get()),
            _file_signature(self.template_var.get()),
        )

    def _start_scrape(self) -> None:
        if self._busy:
            return
        try:
            normalized_urls = normalize_start_urls(self._url_text())
            template = read_template(self.template_var.get())
            validate_output_path(
                template.path,
                self.output_var.get(),
                allow_existing=True,
            )
            signature = (
                normalized_urls,
                _path_signature(str(template.path)),
                template.sha256,
            )
        except (InvalidNerisUrl, ValueError, OSError) as exc:
            messagebox.showerror("Cannot start export", str(exc), parent=self.root)
            self._append_log(f"ERROR: {exc}")
            return

        self._result = None
        self._result_signature = None
        self._cancel_event = threading.Event()
        self._set_busy(True)
        self._set_preview("")
        self.status_var.set(f"Scraping URL 1 of {len(normalized_urls)}…")
        self._append_log(
            f"Starting {len(normalized_urls)}-URL batch. Template contains "
            f"{len(template.rows)} existing rows."
        )
        cancel_event = self._cancel_event
        self._worker = threading.Thread(
            target=self._scrape_worker,
            args=(normalized_urls, signature, cancel_event),
            name="neris-dd-scraper",
            daemon=True,
        )
        self._worker.start()

    def _scrape_worker(
        self,
        normalized_urls: tuple[str, ...],
        signature: tuple[tuple[str, ...], str, str],
        cancel_event: threading.Event,
    ) -> None:
        try:
            results = []
            total = len(normalized_urls)
            for index, normalized_url in enumerate(normalized_urls, start=1):
                if cancel_event.is_set():
                    raise ScrapeCancelled("Batch stopped by user.")
                self._messages.put(("progress", (index, total, normalized_url)))
                try:
                    result = NerisScraper().scrape(
                        normalized_url,
                        progress=lambda message, i=index, n=total: self._messages.put(
                            ("log", f"URL {i}/{n}: {message}")
                        ),
                        cancel_event=cancel_event,
                    )
                except ScrapeCancelled:
                    raise
                except Exception as exc:
                    raise RuntimeError(
                        f"URL {index}/{total} failed ({normalized_url}): {exc}"
                    ) from exc
                if cancel_event.is_set():
                    raise ScrapeCancelled("Scrape stopped by user.")
                results.append(result)
                self._messages.put(
                    ("log", f"URL {index}/{total} complete: {len(result.rows)} rows.")
                )
            result = BatchScrapeResult(tuple(results))
            if cancel_event.is_set():
                self._messages.put(("cancelled", "Scrape stopped by user."))
            else:
                self._messages.put(("result", (result, signature)))
        except ScrapeCancelled as exc:
            self._messages.put(("cancelled", str(exc)))
        except Exception as exc:  # boundary: surface worker failures to the GUI
            self._messages.put(("error", str(exc)))

    def _stop(self) -> None:
        if self._busy:
            self._cancel_event.set()
            self.stop_button.configure(state="disabled")
            self.status_var.set("Stopping after the current browser action…")
            self._append_log("Stop requested.")

    def _save(self) -> None:
        if self._result is None or self._result_signature is None:
            messagebox.showinfo(
                "Scrape first",
                "Run Preview / Scrape before saving an output.",
                parent=self.root,
            )
            return
        try:
            if self._current_signature() != self._result_signature:
                raise ValueError("URL or template changed; scrape again before saving.")
            output = validate_output_path(
                self.template_var.get(),
                self.output_var.get(),
                allow_existing=True,
            )
            overwrite = output.exists()
            if overwrite and not messagebox.askyesno(
                "Replace existing output?",
                f"The output already exists:\n\n{output}\n\nReplace that output file? "
                "The template will remain untouched.",
                parent=self.root,
            ):
                self._append_log("Save cancelled; existing output was not replaced.")
                return

            summary = write_merged_csv(
                self.template_var.get(),
                output,
                self._result.rows,
                overwrite=overwrite,
                expected_template_sha256=self._result_signature[2],
            )
        except (ValueError, OSError, OutputExistsError, UnsafeOutputError) as exc:
            messagebox.showerror("Could not save output", str(exc), parent=self.root)
            self._append_log(f"ERROR: {exc}")
            return

        self.status_var.set(f"Saved {summary.total_rows} rows.")
        self._append_log(
            f"Saved {summary.scraped_rows} scraped rows above "
            f"{summary.template_rows} existing rows: {summary.output_path}"
        )
        messagebox.showinfo(
            "Export saved",
            f"Saved {summary.total_rows} data rows to:\n\n{summary.output_path}",
            parent=self.root,
        )

    def _poll_messages(self) -> None:
        try:
            while True:
                kind, payload = self._messages.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "progress":
                    index, total, url = payload
                    self.status_var.set(f"Scraping URL {index} of {total}…")
                    self._append_log(f"URL {index}/{total}: {url}")
                elif kind == "result":
                    result, signature = payload
                    self._handle_result(result, signature)
                elif kind == "cancelled":
                    self._set_busy(False)
                    self.status_var.set("Scrape stopped.")
                    self._append_log(str(payload))
                elif kind == "error":
                    self._set_busy(False)
                    self.status_var.set("Scrape failed.")
                    self._append_log(f"ERROR: {payload}")
                    if not self._closing:
                        messagebox.showerror(
                            "Scrape failed", str(payload), parent=self.root
                        )
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(self.POLL_INTERVAL_MS, self._poll_messages)

    def _handle_result(
        self,
        result: BatchScrapeResult,
        signature: tuple[tuple[str, ...], str, str],
    ) -> None:
        self._set_busy(False)
        if self._closing or self._cancel_event.is_set():
            self.status_var.set("Scrape stopped.")
            self._append_log("Completed scrape discarded after a stop request.")
            return
        try:
            current_signature = self._current_signature()
        except (InvalidNerisUrl, ValueError, OSError):
            current_signature = None
        if current_signature != signature:
            self.status_var.set("Inputs changed; discarded the stale scrape preview.")
            self._append_log("Completed scrape was discarded because inputs changed.")
            return

        self._result = result
        self._result_signature = signature
        self.save_button.configure(state="normal")
        self.status_var.set(
            f"Preview ready: {len(result.source_urls)} URLs, {len(result.rows)} rows."
        )
        self._set_preview(self._format_preview(result))

    def _format_preview(self, result: BatchScrapeResult) -> str:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(
            stream,
            fieldnames=CSV_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(row.as_dict() for row in result.rows[:25])
        remaining = len(result.rows) - 25
        suffix = f"\n… {remaining} more scraped rows …\n" if remaining > 0 else ""
        return (
            f"Scraped {len(result.rows)} rows from {len(result.source_urls)} URL(s): "
            f"{result.term_count} terms and {result.value_count} values "
            f"across {result.pages_visited} page(s).\n"
            "The saved CSV will put all scraped rows above every template row.\n\n"
            f"{stream.getvalue()}{suffix}"
        )

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        input_state = "disabled" if busy else "normal"
        for widget in (
            self.url_entry,
            self.template_entry,
            self.output_entry,
            self.template_button,
            self.output_button,
        ):
            widget.configure(state=input_state)
        self.scrape_button.configure(state="disabled" if busy else "normal")
        self.stop_button.configure(state="normal" if busy else "disabled")
        if busy or self._result is None:
            self.save_button.configure(state="disabled")

    def _set_preview(self, content: str) -> None:
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", tk.END)
        if content:
            self.preview_text.insert(tk.END, content)
        self.preview_text.configure(state="disabled")

    def _append_log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        if self._closing:
            return
        if self._busy:
            if not messagebox.askyesno(
                "Close while scraping?",
                "A scrape is running. Stop it and close the app?",
                parent=self.root,
            ):
                return
            self._closing = True
            self._cancel_event.set()
            self.stop_button.configure(state="disabled")
            self.status_var.set("Stopping browser before closing…")
            self._append_log("Close requested; waiting for browser cleanup.")
            self.root.after(self.POLL_INTERVAL_MS, self._finish_close)
            return
        self.root.destroy()

    def _finish_close(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            self.root.after(self.POLL_INTERVAL_MS, self._finish_close)
            return
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    DdBulkExportApp(root)
    root.mainloop()
