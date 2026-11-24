"""Crawler tests against a fake website (httpx.MockTransport) and fake DNS. No network."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from app.ingest import ssrf
from app.ingest.crawler import (
    CrawlError,
    crawl,
    extract_main_html,
    is_crawlable_path,
    normalize_link,
    site_key,
)

SITE = "https://docs.example.com"


def page(body: str, title: str = "Page") -> str:
    return (
        f"<html><head><title>{title}</title></head><body>"
        "<nav><a href='/'>Home</a><a href='/guide'>Guide</a></nav>"
        f"<main>{body}</main>"
        "<footer>Copyright <a href='/legal'>Legal</a></footer>"
        "</body></html>"
    )


FAKE_SITE: dict[str, tuple[int, dict[str, str], str]] = {
    "/robots.txt": (200, {"content-type": "text/plain"}, "User-agent: *\nDisallow: /private\n"),
    "/": (
        200,
        {"content-type": "text/html; charset=utf-8"},
        page(
            "<h1>Welcome</h1><p>Start here.</p>"
            "<a href='/guide#install'>Guide again</a>"
            "<a href='/private/secret'>Private</a>"
            "<a href='/login'>Log in</a>"
            "<a href='/manual.pdf'>PDF</a>"
            "<a href='https://other.example.org/'>Elsewhere</a>"
            "<a href='mailto:help@example.com'>Mail</a>"
            "<a href='/moved'>Moved</a>"
            "<a href='/to-internal'>Sneaky</a>"
            "<a href='/logo'>Logo</a>",
            title="Home",
        ),
    ),
    "/guide": (200, {"content-type": "text/html"}, page("<h1>Guide</h1><a href='/guide/deep'>Deep</a>")),
    "/guide/deep": (200, {"content-type": "text/html"}, page("<h1>Deep</h1><a href='/guide/deeper'>x</a>")),
    "/guide/deeper": (200, {"content-type": "text/html"}, page("<h1>Deeper</h1>")),
    "/legal": (200, {"content-type": "text/html"}, page("<h1>Legal</h1>")),
    "/moved": (301, {"location": "/new-home"}, ""),
    "/new-home": (200, {"content-type": "text/html"}, page("<h1>New home</h1>")),
    "/to-internal": (302, {"location": "http://169.254.169.254/latest/meta-data/"}, ""),
    "/logo": (200, {"content-type": "image/png"}, "PNG"),
}


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    def resolve(host: str, _port: int) -> list[str]:
        if host in ("docs.example.com", "www.docs.example.com", "other.example.org"):
            return ["93.184.216.34"]
        return [host]  # IP literals resolve to themselves

    monkeypatch.setattr(ssrf, "_resolve", resolve)


def make_client(
    routes: dict[str, tuple[int, dict[str, str], str]], log: list[str] | None = None
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if log is not None:
            log.append(str(request.url))
        if request.url.host != "docs.example.com":
            return httpx.Response(500)  # must never be reached for internal hosts
        status, headers, body = routes.get(request.url.path, (404, {}, "not found"))
        return httpx.Response(status, headers=headers, text=body)

    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


no_sleep: Callable[[float], None] = lambda _seconds: None  # noqa: E731


def crawled_paths(client: httpx.Client, **kwargs: int) -> list[str]:
    pages = crawl(f"{SITE}/", client=client, sleep=no_sleep, **kwargs)
    return [httpx.URL(p.url).path for p in pages]


# --- Helpers --------------------------------------------------------------------------------


def test_site_key_ignores_www_and_case() -> None:
    assert site_key("https://WWW.Docs.Example.com/x") == "docs.example.com"


def test_normalize_link_drops_fragment_and_non_web_links() -> None:
    assert normalize_link(f"{SITE}/a/", "b#top") == f"{SITE}/a/b"
    assert normalize_link(SITE, "mailto:x@y.z") is None
    assert normalize_link(SITE, "javascript:alert(1)") is None


@pytest.mark.parametrize(
    ("path", "ok"),
    [("/docs/billing", True), ("/accounting", True), ("/login", False), ("/en/account/x", False),
     ("/manual.PDF", False), ("/app.js", False)],
)  # fmt: skip
def test_is_crawlable_path(path: str, ok: bool) -> None:
    assert is_crawlable_path(f"{SITE}{path}") is ok


def test_extract_main_html_drops_noise_but_keeps_menu_links() -> None:
    title, main, hrefs = extract_main_html(page("<h2>Refunds</h2><script>x()</script>", "T"))
    assert title == "T"
    assert "<h2>Refunds</h2>" in main
    assert "script" not in main and "Copyright" not in main and "<nav" not in main
    assert "/guide" in hrefs and "/legal" in hrefs  # nav and footer links still discovered


def test_extract_main_html_falls_back_to_article_then_body() -> None:
    assert "<article>" in extract_main_html("<body><article><p>A</p></article></body>")[1]
    assert "Plain" in extract_main_html("<body><p>Plain</p></body>")[1]


# --- Crawl ----------------------------------------------------------------------------------


def test_crawl_is_breadth_first_and_filtered() -> None:
    log: list[str] = []
    paths = crawled_paths(make_client(FAKE_SITE, log))

    # BFS: the home page, then everything one click away, then two clicks, ...
    assert paths[0] == "/"
    assert paths.index("/guide") < paths.index("/guide/deep") < paths.index("/guide/deeper")
    assert "/new-home" in paths  # same-site redirect followed
    assert "/legal" in paths  # found via the footer, even though the footer text was dropped

    fetched = {httpx.URL(u).path for u in log}
    assert "/private/secret" not in fetched  # robots.txt
    assert "/login" not in fetched and "/manual.pdf" not in fetched  # filters
    assert not any("other.example.org" in u for u in log)  # other site
    assert not any("169.254.169.254" in u for u in log)  # SSRF via redirect: never requested
    assert "/logo" not in paths  # not text/html
    assert paths.count("/guide") == 1  # seen-set dedupes "/guide" and "/guide#install"


def test_crawl_respects_depth_and_page_limits() -> None:
    assert "/guide/deep" not in crawled_paths(make_client(FAKE_SITE), max_depth=1)
    assert len(crawled_paths(make_client(FAKE_SITE), max_pages=2)) == 2


def test_crawl_sleeps_between_requests() -> None:
    sleeps: list[float] = []
    crawl(f"{SITE}/", client=make_client(FAKE_SITE), sleep=sleeps.append, max_pages=3)
    assert sleeps and all(s == pytest.approx(0.4) for s in sleeps)


def test_internal_start_url_is_refused() -> None:
    with pytest.raises(CrawlError, match="internal"):
        crawl("http://127.0.0.1:8000/", client=make_client(FAKE_SITE), sleep=no_sleep)


def test_missing_robots_txt_means_allowed() -> None:
    routes = {k: v for k, v in FAKE_SITE.items() if k != "/robots.txt"}  # 404
    assert "/" in crawled_paths(make_client(routes), max_pages=1)


def test_robots_txt_server_error_means_disallowed() -> None:
    routes = {**FAKE_SITE, "/robots.txt": (503, {}, "")}
    with pytest.raises(CrawlError, match="robots"):
        crawled_paths(make_client(routes))


def test_oversized_page_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "crawl_max_page_bytes", 50)
    assert crawled_paths(make_client(FAKE_SITE)) == []
