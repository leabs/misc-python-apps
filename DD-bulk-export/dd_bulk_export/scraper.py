"""Playwright scraper for rendered NERIS data-dictionary pages."""

from __future__ import annotations

import re
import threading
import unicodedata
from collections.abc import Callable, Sequence
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from .models import DictionaryRow, ScrapeResult

try:
    from playwright.sync_api import (
        Browser,
        Error as PlaywrightError,
        Locator,
        Page,
        Playwright,
        TimeoutError as PlaywrightTimeoutError,
        sync_playwright,
    )
except ImportError:  # pragma: no cover - exercised only before dependencies install
    Browser = Locator = Page = Playwright = Any  # type: ignore[misc,assignment]
    PlaywrightError = PlaywrightTimeoutError = RuntimeError  # type: ignore[assignment]
    sync_playwright = None


NERIS_HOST = "neris.fsri.org"
NERIS_PATH = "/data-dictionary"
DEFAULT_PAGE_SIZE = "100"
MAX_PAGE_SIZE = 500
TERM_SELECTOR = "li[id].pt-8"
VALUE_ITEM_SELECTOR = (
    "div[data-orientation='vertical'][id]:has(> h3 > button[aria-expanded])"
)
ProgressCallback = Callable[[str], None]


class ScrapeError(RuntimeError):
    """Raised when live content cannot be captured or validated."""


class InvalidNerisUrl(ValueError):
    """Raised when a URL is not the supported public dictionary endpoint."""


class ScrapeCancelled(ScrapeError):
    """Raised after the user asks an active scrape to stop."""


def _clean_text(value: str | None) -> str:
    """Normalize browser text while retaining meaningful line boundaries."""

    if not value:
        return ""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    output: list[str] = []
    previous_blank = False
    for line in normalized.split("\n"):
        cleaned = re.sub(r"[\t\f\v ]+", " ", line).strip()
        if cleaned:
            output.append(cleaned)
            previous_blank = False
        elif output and not previous_blank:
            output.append("")
            previous_blank = True
    while output and not output[-1]:
        output.pop()
    return "\n".join(output)


def _slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode(
        "ascii", "ignore"
    ).decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")


def _validated_parts(url: str) -> tuple[Any, list[tuple[str, str]], str]:
    candidate = url.strip()
    if not candidate:
        raise InvalidNerisUrl("Enter a NERIS data-dictionary URL.")

    parts = urlsplit(candidate)
    if parts.scheme.casefold() != "https":
        raise InvalidNerisUrl("NERIS URL must use https://.")
    try:
        port = parts.port
    except ValueError as exc:
        raise InvalidNerisUrl("NERIS URL contains an invalid port.") from exc
    if parts.username or parts.password or port not in {None, 443}:
        raise InvalidNerisUrl("NERIS URL cannot include credentials or a custom port.")
    if (parts.hostname or "").casefold() != NERIS_HOST:
        raise InvalidNerisUrl(f"URL host must be {NERIS_HOST}.")
    if parts.path.rstrip("/") != NERIS_PATH:
        raise InvalidNerisUrl(f"URL path must be {NERIS_PATH}.")

    query = parse_qsl(parts.query, keep_blank_values=True)
    module_values = [value.strip() for key, value in query if key == "module"]
    if len(module_values) != 1 or not module_values[0]:
        raise InvalidNerisUrl("URL must contain exactly one non-empty module value.")
    return parts, query, module_values[0]


def normalize_start_url(url: str) -> str:
    """Validate a public NERIS URL and force a complete scrape to start at page 1."""

    parts, query, _ = _validated_parts(url)
    page_sizes = [value for key, value in query if key == "pageSize"]
    if len(page_sizes) > 1:
        raise InvalidNerisUrl("URL can contain at most one pageSize value.")
    page_size = page_sizes[0].strip() if page_sizes else DEFAULT_PAGE_SIZE
    try:
        numeric_page_size = int(page_size)
    except ValueError as exc:
        raise InvalidNerisUrl("pageSize must be a positive integer.") from exc
    if numeric_page_size < 1:
        raise InvalidNerisUrl("pageSize must be a positive integer.")
    numeric_page_size = min(numeric_page_size, MAX_PAGE_SIZE)

    normalized_query = [
        (key, value)
        for key, value in query
        if key not in {"page", "pageSize"}
        and not (key in {"search", "expanded"} and not value.strip())
    ]
    normalized_query.extend((("page", "1"), ("pageSize", str(numeric_page_size))))
    return urlunsplit(
        ("https", NERIS_HOST, NERIS_PATH, urlencode(normalized_query), "")
    )


def normalize_start_urls(text: str) -> tuple[str, ...]:
    """Validate and normalize a newline-delimited, ordered URL batch."""

    candidates = [
        (line_number, line.strip())
        for line_number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]
    if not candidates:
        raise InvalidNerisUrl("Enter at least one NERIS data-dictionary URL.")

    normalized_urls: list[str] = []
    seen: dict[str, int] = {}
    for line_number, candidate in candidates:
        try:
            normalized = normalize_start_url(candidate)
        except InvalidNerisUrl as exc:
            raise InvalidNerisUrl(f"URL on line {line_number}: {exc}") from exc

        identity = _canonical_url(normalized)
        duplicate_line = seen.get(identity)
        if duplicate_line is not None:
            raise InvalidNerisUrl(
                "Duplicate normalized NERIS URL on line "
                f"{line_number}; it matches line {duplicate_line}: {normalized}"
            )
        seen[identity] = line_number
        normalized_urls.append(normalized)

    return tuple(normalized_urls)


def _module_filter(url: str) -> str:
    _, _, module = _validated_parts(url)
    return module


def _pagination_integer(
    query: Sequence[tuple[str, str]], key: str, *, location: str
) -> int:
    values = [value.strip() for query_key, value in query if query_key == key]
    if len(values) != 1:
        raise ScrapeError(
            f"NERIS {location} URL must contain exactly one {key} value."
        )
    try:
        number = int(values[0])
    except ValueError as exc:
        raise ScrapeError(
            f"NERIS {location} URL contains an invalid {key} value."
        ) from exc
    if number < 1:
        raise ScrapeError(
            f"NERIS {location} URL contains an invalid {key} value."
        )
    return number


def _validate_page_url(
    url: str, expected_module: str, *, current_url: str
) -> str:
    """Validate that a pagination target advances one page without resizing."""

    parts, query, module = _validated_parts(url)
    if module != expected_module:
        raise ScrapeError("NERIS pagination changed the selected module unexpectedly.")
    _, current_query, current_module = _validated_parts(current_url)
    if current_module != expected_module:
        raise ScrapeError("NERIS changed the selected module while paginating.")

    current_page = _pagination_integer(current_query, "page", location="current page")
    next_page = _pagination_integer(query, "page", location="next page")
    if next_page != current_page + 1:
        raise ScrapeError(
            "NERIS pagination did not advance sequentially: expected page "
            f"{current_page + 1}, received page {next_page}."
        )

    current_page_size = _pagination_integer(
        current_query, "pageSize", location="current page"
    )
    next_page_size = _pagination_integer(query, "pageSize", location="next page")
    if next_page_size != current_page_size:
        raise ScrapeError("NERIS pagination changed the page size unexpectedly.")

    ignored_filter_keys = {"page", "pageSize", "expanded"}
    current_filters = sorted(
        pair for pair in current_query if pair[0] not in ignored_filter_keys
    )
    next_filters = sorted(pair for pair in query if pair[0] not in ignored_filter_keys)
    if next_filters != current_filters:
        raise ScrapeError("NERIS pagination changed the active filters unexpectedly.")
    return urlunsplit(
        ("https", NERIS_HOST, NERIS_PATH, urlencode(query), "")
    )


def _canonical_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            parts.path.rstrip("/"),
            urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True))),
            "",
        )
    )


def _validate_loaded_page_url(
    loaded_url: str, requested_url: str, expected_module: str
) -> None:
    """Fail if navigation landed on a different dictionary page or filter."""

    _, _, module = _validated_parts(loaded_url)
    if module != expected_module:
        raise ScrapeError("NERIS changed the selected module during navigation.")
    if _canonical_url(loaded_url) != _canonical_url(requested_url):
        raise ScrapeError(
            "NERIS navigation changed the requested page URL unexpectedly; "
            "the scrape stopped to prevent missing rows."
        )


def module_parts_from_badges(
    badges: Sequence[str], module_filter: str
) -> tuple[str, str]:
    """Resolve module/submodule from rendered badges, including multiword names."""

    for raw_badge in badges:
        match = re.match(r"^\s*(.+?)\s*[-–—]\s*(.+?)\s*$", raw_badge)
        if match:
            module = _slugify(match.group(1))
            submodule = _slugify(match.group(2))
        else:
            words = raw_badge.split(maxsplit=1)
            if len(words) != 2:
                continue
            module = _slugify(words[0])
            submodule = _slugify(words[1])
        if not module or not submodule:
            continue
        if f"{module}-{submodule}" == module_filter:
            return module, submodule

    rendered = ", ".join(badges) or "<missing>"
    raise ScrapeError(
        f"Could not map module filter '{module_filter}' to rendered badge(s): {rendered}"
    )


def source_sheet_name(module: str, submodule: str) -> str:
    return f"{module}_{submodule}_terms".replace("-", "_")


def build_term_row(
    *, title: str, description: str, term_id: str, module: str, submodule: str
) -> DictionaryRow:
    return DictionaryRow(
        term_or_value_name=title,
        description=description,
        value_definition="",
        module=module,
        submodule=submodule,
        row_type="term",
        parent_term_id="",
        parent_term_name="",
        record_id=term_id,
        term_id=term_id,
        source_sheet=source_sheet_name(module, submodule),
    )


def build_value_row(
    *,
    parent_title: str,
    parent_id: str,
    label: str,
    description: str,
    definition: str,
    value_id: str,
    module: str,
    submodule: str,
) -> DictionaryRow:
    return DictionaryRow(
        term_or_value_name=f"{parent_title} - {label}",
        description=description,
        value_definition=definition,
        module=module,
        submodule=submodule,
        row_type="value",
        parent_term_id=parent_id,
        parent_term_name=parent_title,
        record_id=parent_id,
        term_id=value_id,
        source_sheet=source_sheet_name(module, submodule),
    )


class NerisScraper:
    """Capture all terms and nested values from a NERIS dictionary module."""

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = 30_000,
        max_pages: int = 100,
    ) -> None:
        if timeout_ms < 1:
            raise ValueError("timeout_ms must be positive.")
        if max_pages < 1:
            raise ValueError("max_pages must be positive.")
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.max_pages = max_pages

    def scrape(
        self,
        url: str,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> ScrapeResult:
        if sync_playwright is None:
            raise ScrapeError(
                "Playwright is not installed. Run: python -m pip install -r "
                "requirements.txt"
            )

        report = progress or (lambda _message: None)
        cancellation = cancel_event or threading.Event()
        start_url = normalize_start_url(url)
        module_filter = _module_filter(start_url)
        rows: list[DictionaryRow] = []
        seen_term_ids: set[str] = set()
        seen_value_ids: set[str] = set()
        visited_pages: set[str] = set()
        term_count = value_count = accordion_count = 0

        with sync_playwright() as playwright:
            browser, browser_name = self._launch_browser(playwright)
            report(f"Browser: {browser_name} (headless).")
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.set_default_timeout(self.timeout_ms)
                current_url: str | None = start_url

                while current_url is not None:
                    self._raise_if_cancelled(cancellation)
                    canonical = _canonical_url(current_url)
                    if canonical in visited_pages:
                        raise ScrapeError(
                            "Pagination returned to a page already visited; scrape stopped "
                            "to prevent duplicate rows."
                        )
                    if len(visited_pages) >= self.max_pages:
                        raise ScrapeError(
                            f"Pagination exceeded the safety limit of {self.max_pages} pages."
                        )
                    visited_pages.add(canonical)
                    page_number = len(visited_pages)
                    report(f"Opening page {page_number}: {current_url}")
                    self._navigate(page, current_url)
                    _validate_loaded_page_url(
                        page.url,
                        current_url,
                        module_filter,
                    )

                    page_rows, page_terms, page_values, page_accordions = (
                        self._scrape_page(
                            page,
                            module_filter=module_filter,
                            seen_term_ids=seen_term_ids,
                            seen_value_ids=seen_value_ids,
                            progress=report,
                            cancel_event=cancellation,
                        )
                    )
                    rows.extend(page_rows)
                    term_count += page_terms
                    value_count += page_values
                    accordion_count += page_accordions
                    report(
                        f"Page {page_number}: {page_terms} terms, "
                        f"{page_values} values, {page_accordions} Values accordions."
                    )
                    current_url = self._next_page_url(page, module_filter)
            finally:
                browser.close()

        if not rows:
            raise ScrapeError("No data-dictionary terms were found at the selected URL.")
        report(
            f"Scrape complete: {term_count} terms + {value_count} values "
            f"across {len(visited_pages)} page(s)."
        )
        return ScrapeResult(
            source_url=start_url,
            rows=tuple(rows),
            pages_visited=len(visited_pages),
            term_count=term_count,
            value_count=value_count,
            accordion_count=accordion_count,
        )

    def _launch_browser(self, playwright: Playwright) -> tuple[Browser, str]:
        attempts = (
            ("Playwright Chromium", {}),
            ("Google Chrome", {"channel": "chrome"}),
            ("Microsoft Edge", {"channel": "msedge"}),
        )
        errors: list[str] = []
        for name, options in attempts:
            try:
                browser = playwright.chromium.launch(
                    headless=self.headless,
                    **options,
                )
                return browser, name
            except PlaywrightError as exc:
                errors.append(f"{name}: {str(exc).splitlines()[0]}")
        raise ScrapeError(
            "No supported browser could be started. Run 'python -m playwright "
            "install chromium', then try again. Attempts: " + " | ".join(errors)
        )

    def _navigate(self, page: Page, url: str) -> None:
        try:
            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout_ms,
            )
            if response is not None and response.status >= 400:
                raise ScrapeError(
                    f"NERIS returned HTTP {response.status} for {url}."
                )
            page.locator(TERM_SELECTOR).first.wait_for(
                state="visible", timeout=self.timeout_ms
            )
        except PlaywrightTimeoutError as exc:
            raise ScrapeError(
                "Timed out waiting for rendered NERIS data-dictionary terms."
            ) from exc
        except PlaywrightError as exc:
            raise ScrapeError(f"Could not load NERIS data dictionary: {exc}") from exc

    def _scrape_page(
        self,
        page: Page,
        *,
        module_filter: str,
        seen_term_ids: set[str],
        seen_value_ids: set[str],
        progress: ProgressCallback,
        cancel_event: threading.Event,
    ) -> tuple[list[DictionaryRow], int, int, int]:
        term_locators = page.locator(TERM_SELECTOR)
        count = term_locators.count()
        page_rows: list[DictionaryRow] = []
        page_value_count = 0
        page_accordion_count = 0

        for index in range(count):
            self._raise_if_cancelled(cancel_event)
            term = term_locators.nth(index)
            term_id = _clean_text(term.get_attribute("id"))
            title = _clean_text(term.locator(":scope > h2").first.inner_text())
            if not term_id or not title:
                raise ScrapeError(
                    f"Rendered term {index + 1} is missing its stable ID or title."
                )
            if term_id in seen_term_ids:
                raise ScrapeError(f"Duplicate term ID encountered: {term_id}")
            seen_term_ids.add(term_id)

            description_locator = term.locator(":scope > div.prose").first
            if not description_locator.count():
                raise ScrapeError(
                    f"Rendered term '{term_id}' is missing its description field."
                )
            description = _clean_text(description_locator.inner_text())
            badges = self._module_badges(term)
            module, submodule = module_parts_from_badges(badges, module_filter)
            page_rows.append(
                build_term_row(
                    title=title,
                    description=description,
                    term_id=term_id,
                    module=module,
                    submodule=submodule,
                )
            )

            values_button = term.get_by_role("button", name="Values", exact=True)
            if not values_button.count():
                continue
            page_accordion_count += 1
            value_rows = self._scrape_values(
                term,
                values_button.first,
                parent_title=title,
                parent_id=term_id,
                module=module,
                submodule=submodule,
                seen_value_ids=seen_value_ids,
                cancel_event=cancel_event,
            )
            page_rows.extend(value_rows)
            page_value_count += len(value_rows)
            progress(f"Expanded '{title}': {len(value_rows)} nested values.")

        return page_rows, count, page_value_count, page_accordion_count

    def _module_badges(self, term: Locator) -> list[str]:
        module_label = term.locator("span").filter(
            has_text=re.compile(r"^\s*modules:\s*$", re.IGNORECASE)
        ).first
        if not module_label.count():
            raise ScrapeError("A rendered term is missing its modules metadata.")
        badges = [
            _clean_text(text)
            for text in module_label.locator("xpath=following-sibling::*").all_inner_texts()
            if _clean_text(text)
        ]
        if not badges:
            raise ScrapeError("A rendered term has empty modules metadata.")
        return badges

    def _scrape_values(
        self,
        term: Locator,
        values_button: Locator,
        *,
        parent_title: str,
        parent_id: str,
        module: str,
        submodule: str,
        seen_value_ids: set[str],
        cancel_event: threading.Event,
    ) -> list[DictionaryRow]:
        try:
            if values_button.get_attribute("aria-expanded") != "true":
                values_button.click()
            value_items = term.locator(VALUE_ITEM_SELECTOR)
            value_items.first.wait_for(state="visible", timeout=self.timeout_ms)
            count = value_items.count()
        except PlaywrightTimeoutError as exc:
            raise ScrapeError(
                f"Values accordion for '{parent_title}' did not render its entries."
            ) from exc
        except PlaywrightError as exc:
            raise ScrapeError(
                f"Could not expand Values for '{parent_title}': {exc}"
            ) from exc

        rows: list[DictionaryRow] = []
        for index in range(count):
            self._raise_if_cancelled(cancel_event)
            item = value_items.nth(index)
            value_id = _clean_text(item.get_attribute("id"))
            button = item.locator(":scope > h3 > button[aria-expanded]").first
            label = _clean_text(button.locator("span").first.inner_text())
            if not value_id or not label:
                raise ScrapeError(
                    f"A nested value under '{parent_title}' is missing its ID or label."
                )
            if value_id in seen_value_ids:
                raise ScrapeError(f"Duplicate nested value ID encountered: {value_id}")
            seen_value_ids.add(value_id)

            try:
                if button.get_attribute("aria-expanded") != "true":
                    button.click()
                content = item.locator(":scope > div[role='region']").first
                content.wait_for(state="visible", timeout=self.timeout_ms)
            except PlaywrightTimeoutError as exc:
                raise ScrapeError(
                    f"Nested value '{value_id}' did not reveal its details."
                ) from exc
            except PlaywrightError as exc:
                raise ScrapeError(
                    f"Could not expand nested value '{value_id}': {exc}"
                ) from exc

            fields = self._value_fields(content)
            missing_fields = [
                name for name in ("description", "definition") if name not in fields
            ]
            if missing_fields:
                rendered = " and ".join(missing_fields)
                raise ScrapeError(
                    f"Nested value '{value_id}' is missing its rendered "
                    f"{rendered} field(s)."
                )
            rows.append(
                build_value_row(
                    parent_title=parent_title,
                    parent_id=parent_id,
                    label=label,
                    description=fields["description"],
                    definition=fields["definition"],
                    value_id=value_id,
                    module=module,
                    submodule=submodule,
                )
            )
        return rows

    def _value_fields(self, content: Locator) -> dict[str, str]:
        fields: dict[str, str] = {}
        paragraphs = content.locator("p")
        for index in range(paragraphs.count()):
            paragraph = paragraphs.nth(index)
            label_locator = paragraph.locator("span").first
            if not label_locator.count():
                continue
            raw_label = _clean_text(label_locator.inner_text())
            key = raw_label.rstrip(":").casefold()
            if key not in {"description", "definition"}:
                continue
            full_text = _clean_text(paragraph.inner_text())
            if full_text.casefold().startswith(raw_label.casefold()):
                value = full_text[len(raw_label) :].lstrip(" :\n")
            else:
                value = full_text
            fields[key] = _clean_text(value)
        return fields

    def _next_page_url(self, page: Page, module_filter: str) -> str | None:
        next_link = page.locator("a[aria-label='Go to next page']").first
        if not next_link.count():
            raise ScrapeError(
                "NERIS next-page control is missing; the rendered page markup "
                "may have changed."
            )
        if (next_link.get_attribute("aria-disabled") or "").casefold() == "true":
            return None
        href = next_link.get_attribute("href")
        if not href:
            raise ScrapeError("Enabled NERIS next-page control has no destination.")
        return _validate_page_url(
            urljoin(page.url, href),
            module_filter,
            current_url=page.url,
        )

    @staticmethod
    def _raise_if_cancelled(cancel_event: threading.Event) -> None:
        if cancel_event.is_set():
            raise ScrapeCancelled("Scrape stopped by user.")
