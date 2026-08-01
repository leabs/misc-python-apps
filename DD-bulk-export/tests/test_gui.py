from __future__ import annotations

import queue
import threading
from pathlib import Path

import pytest

import dd_bulk_export.gui as gui_module
from dd_bulk_export.gui import (
    BATTERY_FIXTURE_URL,
    DdBulkExportApp,
    _file_signature,
    default_paths,
)
from dd_bulk_export.launcher import _local_python
from dd_bulk_export.models import ScrapeResult
from dd_bulk_export.csv_io import TemplateCsv, WriteSummary
from dd_bulk_export.scraper import build_term_row
from dd_bulk_export.scraper import normalize_start_url


def test_gui_defaults_use_separate_template_and_output_paths(tmp_path: Path) -> None:
    template, output = default_paths(tmp_path)
    assert template == tmp_path / "dd-test-template.csv"
    assert output == tmp_path / "dd-test-template__export.csv"
    assert template != output
    assert "incident-analysis-battery-incident" in normalize_start_url(
        BATTERY_FIXTURE_URL
    )


def _result() -> ScrapeResult:
    row = build_term_row(
        title="Battery Incident - Product Type",
        description="Product type.",
        term_id="Battery-Incident-Product-Type",
        module="incident-analysis",
        submodule="battery-incident",
    )
    return ScrapeResult(
        source_url=normalize_start_url(BATTERY_FIXTURE_URL),
        rows=(row,),
        pages_visited=1,
        term_count=1,
        value_count=0,
        accordion_count=0,
    )


class _Var:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class _Widget:
    def __init__(self) -> None:
        self.state = ""

    def configure(self, **options: str) -> None:
        if "state" in options:
            self.state = options["state"]


def _bare_app() -> DdBulkExportApp:
    app = object.__new__(DdBulkExportApp)
    app._messages = queue.Queue()
    app._cancel_event = threading.Event()
    app._closing = False
    app._busy = True
    app._result = None
    app._result_signature = None
    return app


def test_worker_queues_success_without_touching_tk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _result()

    class FakeScraper:
        def scrape(self, _url: str, *, progress, cancel_event) -> ScrapeResult:
            progress("working")
            assert not cancel_event.is_set()
            return result

    monkeypatch.setattr(gui_module, "NerisScraper", FakeScraper)
    app = _bare_app()
    signature = (result.source_url, "template", "digest")

    app._scrape_worker(result.source_url, signature, app._cancel_event)

    assert app._messages.get_nowait() == ("log", "working")
    assert app._messages.get_nowait() == ("result", (result, signature))


def test_stop_result_race_discards_completed_worker_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _result()

    class FakeScraper:
        def scrape(self, _url: str, *, progress, cancel_event) -> ScrapeResult:
            cancel_event.set()
            return result

    monkeypatch.setattr(gui_module, "NerisScraper", FakeScraper)
    app = _bare_app()
    signature = (result.source_url, "template", "digest")

    app._scrape_worker(result.source_url, signature, app._cancel_event)

    assert app._messages.get_nowait() == (
        "cancelled",
        "Scrape stopped by user.",
    )


def test_stale_result_is_not_enabled_for_save() -> None:
    app = _bare_app()
    app.status_var = _Var()
    app.save_button = _Widget()
    logs: list[str] = []
    app._append_log = logs.append  # type: ignore[method-assign]
    app._set_busy = lambda _busy: None  # type: ignore[method-assign]
    app._current_signature = lambda: (  # type: ignore[method-assign]
        "different",
        "template",
        "digest",
    )
    signature = (_result().source_url, "template", "digest")

    app._handle_result(_result(), signature)

    assert app._result is None
    assert app.save_button.state != "normal"
    assert "discarded" in logs[-1]


def test_template_content_signature_changes_after_external_edit(
    tmp_path: Path,
) -> None:
    template = tmp_path / "template.csv"
    template.write_text("one", encoding="utf-8")
    before = _file_signature(template)
    template.write_text("two", encoding="utf-8")
    assert _file_signature(template) != before


def test_existing_output_requires_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "existing.csv"
    output.write_text("existing", encoding="utf-8")
    result = _result()
    signature = (result.source_url, "template", "digest")
    app = _bare_app()
    app._result = result
    app._result_signature = signature
    app._current_signature = lambda: signature  # type: ignore[method-assign]
    app.template_var = _Var(str(tmp_path / "template.csv"))
    app.output_var = _Var(str(output))
    app.root = object()  # type: ignore[assignment]
    app.status_var = _Var()
    logs: list[str] = []
    app._append_log = logs.append  # type: ignore[method-assign]
    monkeypatch.setattr(gui_module, "validate_output_path", lambda *_args, **_kwargs: output)
    monkeypatch.setattr(gui_module.messagebox, "askyesno", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        gui_module,
        "write_merged_csv",
        lambda *_args, **_kwargs: pytest.fail("writer must not run"),
    )

    app._save()

    assert output.read_text(encoding="utf-8") == "existing"
    assert "not replaced" in logs[-1]


def test_fresh_output_save_calls_writer_and_updates_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "new.csv"
    template = tmp_path / "template.csv"
    result = _result()
    signature = (result.source_url, "template", "digest")
    app = _bare_app()
    app._result = result
    app._result_signature = signature
    app._current_signature = lambda: signature  # type: ignore[method-assign]
    app.template_var = _Var(str(template))
    app.output_var = _Var(str(output))
    app.root = object()  # type: ignore[assignment]
    app.status_var = _Var()
    logs: list[str] = []
    app._append_log = logs.append  # type: ignore[method-assign]
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(gui_module, "validate_output_path", lambda *_args, **_kwargs: output)

    def fake_write(template_arg, output_arg, rows_arg, *, overwrite):
        calls.append((template_arg, output_arg, tuple(rows_arg), overwrite))
        return WriteSummary(output, scraped_rows=1, template_rows=76)

    monkeypatch.setattr(gui_module, "write_merged_csv", fake_write)
    monkeypatch.setattr(gui_module.messagebox, "showinfo", lambda *_args, **_kwargs: None)

    app._save()

    assert calls == [(str(template), output, result.rows, False)]
    assert app.status_var.get() == "Saved 77 rows."
    assert "76 existing rows" in logs[-1]


def test_start_scrape_wires_validated_inputs_to_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template_path = tmp_path / "template.csv"
    template_path.write_text("fixture", encoding="utf-8")
    output_path = tmp_path / "output.csv"
    app = _bare_app()
    app._busy = False
    app.url_var = _Var(BATTERY_FIXTURE_URL)
    app.template_var = _Var(str(template_path))
    app.output_var = _Var(str(output_path))
    app.root = object()  # type: ignore[assignment]
    app.status_var = _Var()
    app._set_busy = lambda busy: setattr(app, "_busy", busy)  # type: ignore[method-assign]
    app._set_preview = lambda _content: None  # type: ignore[method-assign]
    app._append_log = lambda _message: None  # type: ignore[method-assign]
    monkeypatch.setattr(
        gui_module,
        "read_template",
        lambda _path: TemplateCsv(template_path.resolve(), tuple()),
    )
    monkeypatch.setattr(gui_module, "validate_output_path", lambda *_args, **_kwargs: output_path)

    class FakeThread:
        def __init__(self, *, target, args, name, daemon) -> None:
            self.target = target
            self.args = args
            self.name = name
            self.daemon = daemon
            self.started = False

        def start(self) -> None:
            self.started = True

    monkeypatch.setattr(gui_module.threading, "Thread", FakeThread)

    app._start_scrape()

    assert app._busy
    assert app._worker.started  # type: ignore[union-attr]
    assert app._worker.args[0] == normalize_start_url(BATTERY_FIXTURE_URL)  # type: ignore[union-attr]
    assert app._worker.name == "neris-dd-scraper"  # type: ignore[union-attr]


def test_poll_messages_dispatches_completed_result() -> None:
    app = _bare_app()
    result = _result()
    signature = (result.source_url, "template", "digest")
    handled: list[tuple[ScrapeResult, tuple[str, str, str]]] = []
    app._messages.put(("result", (result, signature)))
    app._handle_result = lambda value, value_signature: handled.append(  # type: ignore[method-assign]
        (value, value_signature)
    )

    class PollRoot:
        def winfo_exists(self) -> bool:
            return False

    app.root = PollRoot()  # type: ignore[assignment]
    app._poll_messages()
    assert handled == [(result, signature)]


class _Root:
    def __init__(self) -> None:
        self.destroyed = False
        self.callbacks: list[object] = []

    def after(self, _delay: int, callback) -> None:
        self.callbacks.append(callback)

    def destroy(self) -> None:
        self.destroyed = True


class _Worker:
    def __init__(self, alive: bool) -> None:
        self.alive = alive

    def is_alive(self) -> bool:
        return self.alive


def test_close_waits_for_browser_worker_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _bare_app()
    app.root = _Root()  # type: ignore[assignment]
    app.stop_button = _Widget()
    app.status_var = _Var()
    app._worker = _Worker(alive=True)  # type: ignore[assignment]
    app._append_log = lambda _message: None  # type: ignore[method-assign]
    monkeypatch.setattr(gui_module.messagebox, "askyesno", lambda *_args, **_kwargs: True)

    app._on_close()

    assert app._closing
    assert app._cancel_event.is_set()
    assert not app.root.destroyed
    app._worker.alive = False  # type: ignore[union-attr]
    app._finish_close()
    assert app.root.destroyed


def test_local_venv_launcher_path_matches_platform(tmp_path: Path) -> None:
    path = _local_python(tmp_path)
    assert path.name in {"python", "python.exe"}
    assert ".venv" in path.parts
