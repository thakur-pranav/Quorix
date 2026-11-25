"""Breadth-first website crawler (SPEC sections 5.1 to 5.3).

BFS with a deque (O(1) popleft; list.pop(0) is O(n), SPEC section 9 #4), a `seen` set, same-site
links only, robots.txt, the SSRF guard on every request and redirect hop, a polite delay, and a
size cap per page.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.ingest.ssrf import UnsafeURLError, assert_public_url

logger = logging.getLogger(__name__)

SKIP_EXTENSIONS = (
    ".pdf", ".zip", ".gz", ".tar", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".json", ".xml", ".mp3", ".mp4", ".mov", ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx",
)  # fmt: skip
SKIP_PATH_SEGMENTS = frozenset(
    {"login", "logout", "signin", "sign-in", "signup", "sign-up", "register", "cart",
     "checkout", "account", "accounts"}
)  # fmt: skip
NOISE_TAGS = ("nav", "header", "footer", "aside", "script", "style", "noscript", "form", "iframe")
REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})


class CrawlError(Exception):
    """The crawl could not start (unsafe start URL, or robots.txt forbids everything)."""


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    html: str  # the page's main content only, still HTML so the chunker can see the headings


@dataclass(frozen=True)
class _Fetched:
    url: str  # final URL, after redirects
    status: int
    content_type: str
    text: str


# --- URL helpers ----------------------------------------------------------------------------


def site_key(url: str) -> str:
    """`https://www.docs.example.com/x` -> `docs.example.com` (www. ignored, SPEC 5.1)."""
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def normalize_link(base: str, href: str) -> str | None:
    """Absolute http(s) URL without the #fragment, or None if it isn't a web link."""
    absolute, _fragment = urldefrag(urljoin(base, href.strip()))
    parts = urlsplit(absolute)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None  # mailto:, javascript:, tel:, ...
    return absolute


def is_crawlable_path(url: str) -> bool:
    path = urlsplit(url).path.lower()
    if path.endswith(SKIP_EXTENSIONS):
        return False
    segments = {segment for segment in path.split("/") if segment}
    return not (segments & SKIP_PATH_SEGMENTS)  # whole segments: /accounting is fine, /account isn't


def section_prefix(url: str) -> str:
    """The path a crawl must stay under. "" means the whole site.

    `/en/billing` -> `/en/billing`; `/help/` -> `/help`; `/help/index.html` -> `/help`.
    """
    path = urlsplit(url).path or "/"
    last_segment = path.rsplit("/", 1)[-1]
    if "." in last_segment:  # a file name, e.g. index.html: its folder is the section
        path = path.rsplit("/", 1)[0]
    return path.rstrip("/")


def in_section(url: str, prefix: str) -> bool:
    """Segment-aware: prefix `/en/billing` matches `/en/billing/x`, not `/en/billing-faq`."""
    path = urlsplit(url).path
    return not prefix or path == prefix or path.startswith(prefix + "/")


# --- HTML -----------------------------------------------------------------------------------


def extract_main_html(html: str) -> tuple[str, str, list[str]]:
    """Return (title, main content HTML, raw hrefs) for one page."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    # Collect links *before* removing nav/header/footer: menus are where most links live.
    hrefs = [str(a["href"]) for a in soup.find_all("a", href=True)]

    for tag in soup(NOISE_TAGS):
        tag.decompose()
    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.body
        or soup
    )
    return title, str(main), hrefs


# --- HTTP -----------------------------------------------------------------------------------


def _fetch(client: httpx.Client, url: str) -> _Fetched | None:
    """GET with manual redirects (SSRF-checked per hop) and a size cap. None if too large."""
    for _hop in range(settings.crawl_max_redirects + 1):
        assert_public_url(url)
        with client.stream("GET", url) as res:
            location = res.headers.get("location")
            if res.status_code in REDIRECT_CODES and location:
                url = urljoin(url, location)
                continue

            body = bytearray()
            for piece in res.iter_bytes():
                body.extend(piece)
                if len(body) > settings.crawl_max_page_bytes:
                    logger.info("skipping %s: larger than %d bytes", url, settings.crawl_max_page_bytes)
                    return None
            return _Fetched(
                url=url,
                status=res.status_code,
                content_type=res.headers.get("content-type", "").lower(),
                text=bytes(body).decode(res.encoding or "utf-8", errors="replace"),
            )
    raise httpx.TooManyRedirects(f"more than {settings.crawl_max_redirects} redirects")


def _load_robots(client: httpx.Client, start_url: str) -> RobotFileParser:
    """robots.txt per RFC 9309: 4xx means no rules; 5xx or unreachable means disallow all."""
    parts = urlsplit(start_url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    parser = RobotFileParser(robots_url)
    try:
        fetched = _fetch(client, robots_url)
    except (UnsafeURLError, httpx.HTTPError):
        fetched = None

    if fetched is None or fetched.status >= 500:
        parser.disallow_all = True
    elif fetched.status >= 400:
        parser.allow_all = True
    else:
        parser.parse(fetched.text.splitlines())
    return parser


# --- Crawl ----------------------------------------------------------------------------------


def crawl(
    start_url: str,
    *,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
    max_pages: int | None = None,
    max_depth: int | None = None,
) -> list[Page]:
    """Breadth-first crawl of one site. Raises CrawlError if the crawl can't start at all."""
    max_pages = settings.crawl_max_pages if max_pages is None else max_pages
    max_depth = settings.crawl_max_depth if max_depth is None else max_depth

    start = normalize_link(start_url, start_url)
    if start is None:
        raise CrawlError("start URL must be http(s)")
    try:
        assert_public_url(start)
    except UnsafeURLError as exc:
        raise CrawlError(str(exc)) from exc

    owns_client = client is None
    if client is None:
        client = httpx.Client(
            headers={"User-Agent": settings.crawl_user_agent},
            timeout=settings.crawl_timeout_seconds,
            follow_redirects=False,  # we follow them ourselves, SSRF-checking each hop
        )
    try:
        robots = _load_robots(client, start)
        if robots.disallow_all:
            raise CrawlError("robots.txt is unreachable or disallows crawling")

        site = site_key(start)
        # Set from the first page's FINAL URL: `slack.com/help` redirects to `/intl/en-in/help`,
        # and a section taken from the typed URL would then exclude every real page.
        section: str | None = None
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        seen: set[str] = {start}
        pages: list[Page] = []

        while queue and len(pages) < max_pages:
            url, depth = queue.popleft()
            if not robots.can_fetch(settings.crawl_user_agent, url):
                continue

            try:
                fetched = _fetch(client, url)
            except (UnsafeURLError, httpx.HTTPError) as exc:
                logger.info("skipping %s: %s", url, exc)
                continue
            finally:
                sleep(settings.crawl_delay_seconds)

            if (
                fetched is None
                or fetched.status != 200
                or "text/html" not in fetched.content_type
                or site_key(fetched.url) != site  # a redirect may have left the site
            ):
                continue
            if section is None:
                section = section_prefix(fetched.url) if settings.crawl_stay_in_section else ""
            elif not in_section(fetched.url, section):
                continue  # a redirect left the section
            seen.add(fetched.url)

            title, main_html, hrefs = extract_main_html(fetched.text)
            pages.append(Page(url=fetched.url, title=title, html=main_html))

            if depth >= max_depth:
                continue
            for href in hrefs:
                link = normalize_link(fetched.url, href)
                if (
                    link is not None
                    and link not in seen
                    and site_key(link) == site
                    and in_section(link, section or "")
                    and is_crawlable_path(link)
                ):
                    seen.add(link)
                    queue.append((link, depth + 1))
        return pages
    finally:
        if owns_client:
            client.close()
