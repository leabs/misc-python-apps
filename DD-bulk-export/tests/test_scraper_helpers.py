from __future__ import annotations

import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import sync_playwright

import dd_bulk_export.scraper as scraper_module
from dd_bulk_export.scraper import (
    InvalidNerisUrl,
    NerisScraper,
    ScrapeError,
    build_term_row,
    build_value_row,
    module_parts_from_badges,
    normalize_start_url,
    normalize_start_urls,
    source_sheet_name,
)


BATTERY_URL = (
    "https://neris.fsri.org/data-dictionary"
    "?page=9&pageSize=25&module=incident-analysis-battery-incident#term"
)


@pytest.mark.parametrize(
    "url",
    [
        "http://neris.fsri.org/data-dictionary?module=core-entity",
        "https://evil.example/data-dictionary?module=core-entity",
        "https://neris.fsri.org/other?module=core-entity",
        "https://neris.fsri.org/data-dictionary",
        "https://neris.fsri.org/data-dictionary?module=core-entity&module=core-station",
        "https://user@neris.fsri.org/data-dictionary?module=core-entity",
        "https://neris.fsri.org:444/data-dictionary?module=core-entity",
        "https://neris.fsri.org:notaport/data-dictionary?module=core-entity",
        "https://neris.fsri.org/data-dictionary?module=core-entity&pageSize=zero",
        "https://neris.fsri.org/data-dictionary?module=core-entity&pageSize=0",
    ],
)
def test_url_validation_rejects_unsafe_or_incomplete_urls(url: str) -> None:
    with pytest.raises(InvalidNerisUrl):
        normalize_start_url(url)


def test_start_url_is_normalized_to_page_one() -> None:
    normalized = normalize_start_url(BATTERY_URL)
    parts = urlsplit(normalized)
    query = parse_qs(parts.query)
    assert parts.scheme == "https"
    assert parts.netloc == "neris.fsri.org"
    assert parts.path == "/data-dictionary"
    assert not parts.fragment
    assert query["module"] == ["incident-analysis-battery-incident"]
    assert query["page"] == ["1"]
    assert query["pageSize"] == ["25"]


def test_missing_page_size_defaults_to_100() -> None:
    normalized = normalize_start_url(
        "https://neris.fsri.org/data-dictionary?module=core-entity"
    )
    assert parse_qs(urlsplit(normalized).query)["pageSize"] == ["100"]


def test_supplied_positive_page_size_is_preserved() -> None:
    normalized = normalize_start_url(
        "https://neris.fsri.org/data-dictionary"
        "?module=core-entity&page=9&pageSize=501"
    )
    query = parse_qs(urlsplit(normalized).query)
    assert query["page"] == ["1"]
    assert query["pageSize"] == ["501"]


def test_empty_optional_filters_are_removed() -> None:
    normalized = normalize_start_url(
        "https://neris.fsri.org/data-dictionary"
        "?module=core-entity&search=&expanded=&page=1&pageSize=5"
    )
    query = parse_qs(urlsplit(normalized).query, keep_blank_values=True)
    assert "search" not in query
    assert "expanded" not in query


def test_url_list_ignores_blanks_and_preserves_order() -> None:
    core = "https://neris.fsri.org/data-dictionary?module=core-entity"
    battery = "https://neris.fsri.org/data-dictionary?module=incident-analysis-battery-incident"
    assert normalize_start_urls(f"\n {battery}\n\n{core}\n") == (
        normalize_start_url(battery),
        normalize_start_url(core),
    )


def test_url_list_rejects_normalized_duplicates_with_lines() -> None:
    first = "https://neris.fsri.org/data-dictionary?module=core-entity&page=9"
    second = "https://neris.fsri.org/data-dictionary?page=1&pageSize=100&module=core-entity"
    with pytest.raises(InvalidNerisUrl, match=r"line 2.*line 1"):
        normalize_start_urls(f"{first}\n{second}")


def test_url_list_reports_invalid_line_before_browser_work() -> None:
    valid = "https://neris.fsri.org/data-dictionary?module=core-entity"
    with pytest.raises(InvalidNerisUrl, match="URL on line 2"):
        normalize_start_urls(f"{valid}\nhttps://evil.example/")


def test_url_list_has_no_five_url_cap() -> None:
    urls = "\n".join(
        f"https://neris.fsri.org/data-dictionary?module=core-module-{index}"
        for index in range(6)
    )
    assert len(normalize_start_urls(urls)) == 6


def test_multiword_module_badge_maps_without_naive_url_split() -> None:
    assert module_parts_from_badges(
        ["Incident Analysis-Battery Incident"],
        "incident-analysis-battery-incident",
    ) == ("incident-analysis", "battery-incident")
    assert module_parts_from_badges(["Core Entity"], "core-entity") == (
        "core",
        "entity",
    )


def test_matching_badge_is_selected_when_term_has_multiple_modules() -> None:
    assert module_parts_from_badges(
        ["Core-Entity", "Incident Analysis-Battery Incident"],
        "incident-analysis-battery-incident",
    ) == ("incident-analysis", "battery-incident")


def test_single_rendered_module_is_authoritative_without_a_whitelist() -> None:
    assert module_parts_from_badges(
        ["Incident Analysis-Consumer Products"],
        "incident-aanlysis-consumer-products",
        "Consumer Products - Consumer Product Type",
    ) == ("incident-analysis", "consumer-products")


def test_term_and_value_mapping_match_fixed_csv_semantics() -> None:
    term = build_term_row(
        title="Battery Incident - Battery Cell",
        description="The specific cell type.",
        term_id="Battery-Incident-Battery-Cell",
        module="incident-analysis",
        submodule="battery-incident",
    )
    value = build_value_row(
        parent_title=term.term_or_value_name,
        parent_id=term.term_id,
        label="POUCH_POLYMER",
        description="Pouch Polymer",
        definition="A flexible laminate battery.",
        value_id="Battery-Incident-Battery-Cell-POUCH_POLYMER",
        module=term.module,
        submodule=term.submodule,
    )
    assert term.row_type == "term"
    assert term.record_id == term.term_id
    assert value.row_type == "value"
    assert value.record_id == value.parent_term_id == term.term_id
    assert value.parent_term_name == term.term_or_value_name
    assert value.term_or_value_name.endswith(" - POUCH_POLYMER")
    assert value.source_sheet == "incident_analysis_battery_incident_terms"
    assert source_sheet_name("core", "entity") == "core_entity_terms"


class _FakeNextLink:
    def __init__(self, *, disabled: bool, href: str) -> None:
        self.disabled = disabled
        self.href = href

    @property
    def first(self) -> "_FakeNextLink":
        return self

    def count(self) -> int:
        return 1

    def get_attribute(self, name: str) -> str | None:
        if name == "aria-disabled":
            return "true" if self.disabled else "false"
        if name == "href":
            return self.href
        return None


class _MissingLocator:
    @property
    def first(self) -> "_MissingLocator":
        return self

    def count(self) -> int:
        return 0


class _FakePage:
    url = (
        "https://neris.fsri.org/data-dictionary"
        "?module=core-entity&page=1&pageSize=1"
    )

    def __init__(self, link: _FakeNextLink) -> None:
        self.link = link

    def locator(self, _selector: str) -> _FakeNextLink:
        return self.link


def test_disabled_next_link_is_not_followed() -> None:
    page = _FakePage(_FakeNextLink(disabled=True, href="?module=core-entity&page=1"))
    assert NerisScraper()._next_page_url(page, "core-entity") is None  # type: ignore[arg-type]


def test_missing_next_link_fails_closed() -> None:
    page = _FakePage(_MissingLocator())  # type: ignore[arg-type]
    with pytest.raises(ScrapeError, match="next-page control is missing"):
        NerisScraper()._next_page_url(page, "core-entity")  # type: ignore[arg-type]


def test_enabled_next_link_is_validated_and_followed() -> None:
    page = _FakePage(
        _FakeNextLink(
            disabled=False,
            href="?module=core-entity&page=2&pageSize=1",
        )
    )
    assert NerisScraper()._next_page_url(page, "core-entity") == (
        "https://neris.fsri.org/data-dictionary"
        "?module=core-entity&page=2&pageSize=1"
    )


@pytest.mark.parametrize(
    ("href", "message"),
    [
        ("?module=core-entity&page=3&pageSize=1", "expected page 2"),
        ("?module=core-entity&page=2&pageSize=5", "page size"),
    ],
)
def test_next_link_must_advance_one_page_without_resizing(
    href: str, message: str
) -> None:
    page = _FakePage(_FakeNextLink(disabled=False, href=href))
    with pytest.raises(ScrapeError, match=message):
        NerisScraper()._next_page_url(page, "core-entity")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "href",
    [
        "?module=core-entity&search=station&page=2&pageSize=1",
        "?module=core-entity&page=2&pageSize=1",
    ],
)
def test_next_link_must_preserve_search_filter(href: str) -> None:
    page = _FakePage(_FakeNextLink(disabled=False, href=href))
    page.url = (
        "https://neris.fsri.org/data-dictionary"
        "?module=core-entity&search=entity&page=1&pageSize=1"
    )
    with pytest.raises(ScrapeError, match="changed the active filters"):
        NerisScraper()._next_page_url(page, "core-entity")  # type: ignore[arg-type]


def test_next_link_may_drop_non_filtering_expanded_state() -> None:
    page = _FakePage(
        _FakeNextLink(
            disabled=False,
            href="?module=core-entity&page=2&pageSize=1",
        )
    )
    page.url = (
        "https://neris.fsri.org/data-dictionary"
        "?module=core-entity&expanded=Entity-NERIS-ID&page=1&pageSize=1"
    )
    assert NerisScraper()._next_page_url(page, "core-entity") == (
        "https://neris.fsri.org/data-dictionary"
        "?module=core-entity&page=2&pageSize=1"
    )


def test_cross_origin_next_link_is_rejected() -> None:
    page = _FakePage(
        _FakeNextLink(
            disabled=False,
            href="https://evil.example/data-dictionary?module=core-entity&page=2",
        )
    )
    with pytest.raises(InvalidNerisUrl, match="host"):
        NerisScraper()._next_page_url(page, "core-entity")  # type: ignore[arg-type]


class _Collection:
    def __init__(self, *items: object) -> None:
        self.items = items

    @property
    def first(self) -> object:
        return self.items[0]

    def count(self) -> int:
        return len(self.items)

    def nth(self, index: int) -> object:
        return self.items[index]

    def all_inner_texts(self) -> list[str]:
        return [item.inner_text() for item in self.items]  # type: ignore[attr-defined]


class _Text:
    def __init__(self, text: str) -> None:
        self.text = text

    def inner_text(self) -> str:
        return self.text

    def count(self) -> int:
        return 1


class _Paragraph:
    def __init__(self, label: str, value: str) -> None:
        self.label = label
        self.value = value

    def locator(self, selector: str) -> _Collection:
        assert selector == "span"
        return _Collection(_Text(self.label))

    def inner_text(self) -> str:
        return f"{self.label} {self.value}"


class _Content:
    def __init__(self, description: str, definition: str) -> None:
        self.paragraphs = (
            _Paragraph("Description:", description),
            _Paragraph("Definition:", definition),
        )

    def wait_for(self, **_kwargs: object) -> None:
        return None

    def locator(self, selector: str) -> _Collection:
        assert selector == "p"
        return _Collection(*self.paragraphs)


class _Button:
    def __init__(self, label: str) -> None:
        self.label = label
        self.expanded = "false"
        self.click_count = 0

    def get_attribute(self, name: str) -> str | None:
        return self.expanded if name == "aria-expanded" else None

    def click(self) -> None:
        self.click_count += 1
        self.expanded = "true"

    def locator(self, selector: str) -> _Collection:
        assert selector == "span"
        return _Collection(_Text(self.label))


class _ValueItem:
    def __init__(
        self, value_id: str, label: str, description: str, definition: str
    ) -> None:
        self.value_id = value_id
        self.button = _Button(label)
        self.content = _Content(description, definition)

    def wait_for(self, **_kwargs: object) -> None:
        return None

    def get_attribute(self, name: str) -> str | None:
        return self.value_id if name == "id" else None

    def locator(self, selector: str) -> _Collection:
        if selector == ":scope > h3 > button[aria-expanded]":
            return _Collection(self.button)
        if selector == ":scope > div[role='region']":
            return _Collection(self.content)
        raise AssertionError(f"Unexpected value-item selector: {selector}")


class _ValueTerm:
    def __init__(self, *items: _ValueItem) -> None:
        self.items = items

    def locator(self, selector: str) -> _Collection:
        assert selector == scraper_module.VALUE_ITEM_SELECTOR
        return _Collection(*self.items)


class _ModuleLabel(_Text):
    def __init__(self, badge: str) -> None:
        super().__init__("modules:")
        self.badge = badge

    def locator(self, selector: str) -> _Collection:
        assert selector == "xpath=following-sibling::*"
        return _Collection(_Text(self.badge))


class _ModuleSpans(_Collection):
    def filter(self, **_kwargs: object) -> "_ModuleSpans":
        return self


class _FullTerm(_ValueTerm):
    def __init__(self, *items: _ValueItem) -> None:
        super().__init__(*items)
        self.outer_button = _Button("Values")

    def get_attribute(self, name: str) -> str | None:
        return "Parent" if name == "id" else None

    def get_by_role(self, role: str, *, name: str, exact: bool) -> _Collection:
        assert (role, name, exact) == ("button", "Values", True)
        return _Collection(self.outer_button)

    def locator(self, selector: str):
        if selector == ":scope > h2":
            return _Collection(_Text("Parent"))
        if selector == ":scope > div.prose":
            return _Collection(_Text("Parent description"))
        if selector == "span":
            return _ModuleSpans(_ModuleLabel("Core Entity"))
        if selector == ":scope > div > button[aria-expanded]":
            return _Collection(self.outer_button)
        return super().locator(selector)


class _TermWithoutDescription(_FullTerm):
    def locator(self, selector: str):
        if selector == ":scope > div.prose":
            return _MissingLocator()
        return super().locator(selector)


class _TermPage:
    def __init__(self, term: _FullTerm) -> None:
        self.term = term

    def locator(self, selector: str) -> _Collection:
        assert selector == scraper_module.TERM_SELECTOR
        return _Collection(self.term)


def test_nested_accordion_scrape_clicks_and_maps_every_value() -> None:
    first = _ValueItem(
        "Parent-ONE",
        "ONE",
        "First, description",
        "First definition\nsecond line",
    )
    second = _ValueItem("Parent-TWO", "TWO", "Café", "Second definition")
    outer_button = _Button("Values")

    rows = NerisScraper()._scrape_values(  # type: ignore[arg-type]
        _ValueTerm(first, second),
        outer_button,
        parent_title="Parent",
        parent_id="Parent",
        module="core",
        submodule="entity",
        seen_value_ids=set(),
        cancel_event=threading.Event(),
    )

    assert outer_button.click_count == 1
    assert first.button.click_count == second.button.click_count == 1
    assert [row.term_id for row in rows] == ["Parent-ONE", "Parent-TWO"]
    assert rows[0].description == "First, description"
    assert rows[0].value_definition == "First definition\nsecond line"
    assert rows[1].description == "Café"


def test_outer_accordion_gets_one_bounded_hydration_retry() -> None:
    item = _ValueItem("Parent-ONE", "ONE", "Description", "Definition")
    attempts = 0

    class FlakyFirst:
        def wait_for(self, **kwargs: object) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise scraper_module.PlaywrightTimeoutError("not hydrated")
            item.wait_for(**kwargs)

    class FlakyCollection(_Collection):
        @property
        def first(self) -> object:
            return FlakyFirst()

    class FlakyTerm(_ValueTerm):
        def locator(self, selector: str) -> _Collection:
            assert selector == scraper_module.VALUE_ITEM_SELECTOR
            return FlakyCollection(item)

    outer_button = _Button("Available choices")
    rows = NerisScraper()._scrape_values(  # type: ignore[arg-type]
        FlakyTerm(item),
        outer_button,
        parent_title="Parent",
        parent_id="Parent",
        module="incident-analysis",
        submodule="consumer-products",
        seen_value_ids=set(),
        cancel_event=threading.Event(),
    )

    assert attempts == 2
    assert outer_button.click_count == 3
    assert [row.term_id for row in rows] == ["Parent-ONE"]


def test_outer_accordion_double_hydration_failure_fails_closed() -> None:
    item = _ValueItem("Parent-ONE", "ONE", "Description", "Definition")

    class NeverHydrates:
        def wait_for(self, **_kwargs: object) -> None:
            raise scraper_module.PlaywrightTimeoutError("still empty")

    class EmptyCollection(_Collection):
        @property
        def first(self) -> object:
            return NeverHydrates()

    class EmptyTerm(_ValueTerm):
        def locator(self, selector: str) -> _Collection:
            assert selector == scraper_module.VALUE_ITEM_SELECTOR
            return EmptyCollection()

    outer_button = _Button("Available choices")
    with pytest.raises(ScrapeError, match="did not render its entries"):
        NerisScraper()._scrape_values(  # type: ignore[arg-type]
            EmptyTerm(item),
            outer_button,
            parent_title="Battery Incident - Incident Indoor Outdoor",
            parent_id="Battery-Incident-Incident-Indoor-Outdoor",
            module="incident-analysis",
            submodule="battery-incident",
            seen_value_ids=set(),
            cancel_event=threading.Event(),
        )

    assert outer_button.click_count == 3


def test_nested_accordion_gets_one_bounded_interaction_retry() -> None:
    item = _ValueItem("Parent-ONE", "ONE", "Description", "Definition")
    attempts = 0

    class FlakyContent(_Content):
        def wait_for(self, **kwargs: object) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise scraper_module.PlaywrightTimeoutError("still closed")
            super().wait_for(**kwargs)

    item.content = FlakyContent("Description", "Definition")
    rows = NerisScraper()._scrape_values(  # type: ignore[arg-type]
        _ValueTerm(item),
        _Button("Values"),
        parent_title="Incident Actions and Tactics",
        parent_id="Incident-Actions-and-Tactics",
        module="core",
        submodule="incident",
        seen_value_ids=set(),
        cancel_event=threading.Event(),
    )

    assert attempts == 2
    assert item.button.click_count == 3
    assert [row.term_id for row in rows] == ["Parent-ONE"]


def test_nested_accordion_double_interaction_failure_fails_closed() -> None:
    item = _ValueItem("Parent-ONE", "ONE", "Description", "Definition")

    class NeverVisible(_Content):
        def wait_for(self, **_kwargs: object) -> None:
            raise scraper_module.PlaywrightTimeoutError("still closed")

    item.content = NeverVisible("Description", "Definition")
    with pytest.raises(ScrapeError, match="did not reveal its details"):
        NerisScraper()._scrape_values(  # type: ignore[arg-type]
            _ValueTerm(item),
            _Button("Values"),
            parent_title="Incident Actions and Tactics",
            parent_id="Incident-Actions-and-Tactics",
            module="core",
            submodule="incident",
            seen_value_ids=set(),
            cancel_event=threading.Event(),
        )

    assert item.button.click_count == 3


@pytest.mark.parametrize("missing_label", ["Description:", "Definition:"])
def test_nested_value_requires_both_rendered_fields(missing_label: str) -> None:
    item = _ValueItem("Parent-ONE", "ONE", "Description", "Definition")
    item.content.paragraphs = tuple(
        paragraph
        for paragraph in item.content.paragraphs
        if paragraph.label != missing_label
    )

    with pytest.raises(ScrapeError, match="missing its rendered"):
        NerisScraper()._scrape_values(  # type: ignore[arg-type]
            _ValueTerm(item),
            _Button("Values"),
            parent_title="Parent",
            parent_id="Parent",
            module="core",
            submodule="entity",
            seen_value_ids=set(),
            cancel_event=threading.Event(),
        )


def test_page_scrape_discovers_outer_values_and_orders_term_before_values() -> None:
    value = _ValueItem("Parent-ONE", "ONE", "Description", "Definition")
    term = _FullTerm(value)

    rows, term_count, value_count, accordion_count = NerisScraper()._scrape_page(  # type: ignore[arg-type]
        _TermPage(term),
        module_filter="core-entity",
        seen_term_ids=set(),
        seen_value_ids=set(),
        progress=lambda _message: None,
        cancel_event=threading.Event(),
    )

    assert term.outer_button.click_count == 1
    assert [row.term_id for row in rows] == ["Parent", "Parent-ONE"]
    assert (term_count, value_count, accordion_count) == (1, 1, 1)


def test_page_scrape_requires_rendered_term_description() -> None:
    with pytest.raises(ScrapeError, match="missing its description field"):
        NerisScraper()._scrape_page(  # type: ignore[arg-type]
            _TermPage(_TermWithoutDescription()),
            module_filter="core-entity",
            seen_term_ids=set(),
            seen_value_ids=set(),
            progress=lambda _message: None,
            cancel_event=threading.Event(),
        )


def test_supplied_consumer_products_fixture_is_dom_driven() -> None:
    fixture = Path(__file__).parent / "fixtures" / "otherpage.html"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(fixture.resolve().as_uri())
            rows, terms, values, accordions = NerisScraper()._scrape_page(
                page,
                module_filter="incident-aanlysis-consumer-products",
                seen_term_ids=set(),
                seen_value_ids=set(),
                progress=lambda _message: None,
                cancel_event=threading.Event(),
            )
        finally:
            browser.close()

    assert (terms, values, accordions) == (1, 1, 1)
    assert [row.term_id for row in rows] == [
        "Consumer-Products-Product-Contribution",
        "Consumer-Products-Product-Contribution-IGNITION",
    ]
    assert {(row.module, row.submodule) for row in rows} == {
        ("incident-analysis", "consumer-products")
    }
    assert rows[1].value_definition == "The product contributed to ignition."


class _PlaywrightContext:
    def __enter__(self) -> object:
        return object()

    def __exit__(self, *_args: object) -> None:
        return None


class _LoopPage:
    def __init__(self) -> None:
        self.url = ""

    def set_default_timeout(self, _timeout: int) -> None:
        return None


class _LoopBrowser:
    def __init__(self) -> None:
        self.page = _LoopPage()
        self.closed = False

    def new_page(self, **_kwargs: object) -> _LoopPage:
        return self.page

    def close(self) -> None:
        self.closed = True


def _install_loop_fakes(
    monkeypatch: pytest.MonkeyPatch, scraper: NerisScraper
) -> _LoopBrowser:
    browser = _LoopBrowser()
    monkeypatch.setattr(scraper_module, "sync_playwright", _PlaywrightContext)
    monkeypatch.setattr(
        scraper,
        "_launch_browser",
        lambda _playwright: (browser, "Fake browser"),
    )
    monkeypatch.setattr(
        scraper,
        "_navigate",
        lambda page, url: setattr(page, "url", url),
    )

    def fake_scrape_page(page: _LoopPage, **_kwargs: object):
        page_number = parse_qs(urlsplit(page.url).query)["page"][0]
        row = build_term_row(
            title=f"Term {page_number}",
            description="",
            term_id=f"Term-{page_number}",
            module="core",
            submodule="entity",
        )
        return [row], 1, 0, 0

    monkeypatch.setattr(scraper, "_scrape_page", fake_scrape_page)
    return browser


def test_scrape_loop_collects_two_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    scraper = NerisScraper()
    browser = _install_loop_fakes(monkeypatch, scraper)

    def next_page(page: _LoopPage, _module: str) -> str | None:
        page_number = parse_qs(urlsplit(page.url).query)["page"][0]
        if page_number == "1":
            return page.url.replace("page=1", "page=2")
        return None

    monkeypatch.setattr(scraper, "_next_page_url", next_page)
    result = scraper.scrape(
        "https://neris.fsri.org/data-dictionary"
        "?module=core-entity&page=9&pageSize=1"
    )

    assert result.pages_visited == 2
    assert result.term_count == 2
    assert [row.term_id for row in result.rows] == ["Term-1", "Term-2"]
    assert browser.closed


def test_scrape_loop_rejects_navigation_to_a_different_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scraper = NerisScraper()
    browser = _install_loop_fakes(monkeypatch, scraper)
    monkeypatch.setattr(
        scraper,
        "_navigate",
        lambda page, url: setattr(page, "url", url.replace("page=1", "page=2")),
    )

    with pytest.raises(ScrapeError, match="changed the requested page URL"):
        scraper.scrape(
            "https://neris.fsri.org/data-dictionary"
            "?module=core-entity&page=1&pageSize=1"
        )

    assert browser.closed


def test_scrape_loop_rejects_pagination_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scraper = NerisScraper()
    browser = _install_loop_fakes(monkeypatch, scraper)
    monkeypatch.setattr(
        scraper,
        "_next_page_url",
        lambda page, _module: page.url,
    )

    with pytest.raises(ScrapeError, match="already visited"):
        scraper.scrape(
            "https://neris.fsri.org/data-dictionary"
            "?module=core-entity&page=1&pageSize=1"
        )
    assert browser.closed
