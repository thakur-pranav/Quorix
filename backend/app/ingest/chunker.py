"""Turn pages and files into retrievable chunks (SPEC section 5.4).

HTML: split at h1-h4 and keep the heading path ("Billing › Refunds"), so every chunk says
where it came from. Files: split at blank lines, with the file label as the heading path.
Then: merge short same-path sections, window long ones (220 words, 40 overlap), drop stubs.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from app.config import settings

HEADINGS = ("h1", "h2", "h3", "h4")
TEXT_BLOCKS = ("p", "li", "pre", "blockquote", "td", "th", "dd", "dt", "figcaption")
PATH_SEPARATOR = " › "
DEFAULT_PATH = "Introduction"


@dataclass(frozen=True)
class Section:
    heading_path: str
    text: str


@dataclass(frozen=True)
class RawChunk:
    heading_path: str
    text: str
    url: str | None
    word_count: int


# --- Splitting into sections ----------------------------------------------------------------


def link_density(element: Tag, text: str) -> float:
    """Share of the block's words that are link text. 1.0 = pure navigation, 0.0 = prose."""
    total = len(text.split())
    if total == 0:
        return 0.0
    linked = sum(len(a.get_text(" ", strip=True).split()) for a in element.find_all("a"))
    return linked / total


def sections_from_html(html: str) -> list[Section]:
    """Walk headings and text blocks in document order, tracking the heading path."""
    soup = BeautifulSoup(html, "html.parser")
    path: list[str] = []  # path[i] is the current heading at level i + 1 ("" if skipped)
    buffer: list[str] = []
    sections: list[Section] = []

    def flush() -> None:
        body = " ".join(buffer).strip()
        if body:
            label = PATH_SEPARATOR.join(p for p in path if p) or DEFAULT_PATH
            sections.append(Section(heading_path=label, text=body))
        buffer.clear()

    for element in soup.find_all([*HEADINGS, *TEXT_BLOCKS]):
        if not isinstance(element, Tag):
            continue
        if element.name in TEXT_BLOCKS and element.find_parent(TEXT_BLOCKS) is not None:
            continue  # nested block (a <p> inside an <li>): its text is already in the parent
        text = element.get_text(" ", strip=True)
        if not text:
            continue
        if element.name in TEXT_BLOCKS and link_density(element, text) > settings.chunk_max_link_density:
            continue  # a menu or link list: matches many questions loosely, answers none

        if element.name in HEADINGS:
            flush()  # everything so far belongs to the previous heading
            level = int(element.name[1])
            path = path[: level - 1] + [""] * (level - 1 - len(path)) + [text]
        else:
            buffer.append(text)

    flush()
    return sections


def sections_from_plain(text: str, label: str) -> list[Section]:
    """PDF, DOCX and text: headings are unreliable, so split at blank lines."""
    blocks = (" ".join(block.split()) for block in text.split("\n\n"))
    return [Section(heading_path=label, text=block) for block in blocks if block]


# --- Merging, windowing, filtering ----------------------------------------------------------


def _merge_short(sections: list[Section]) -> list[Section]:
    """Merge consecutive same-path sections while the earlier one is still short."""
    merged: list[Section] = []
    for section in sections:
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and previous.heading_path == section.heading_path
            and len(previous.text.split()) < settings.chunk_merge_below_words
        ):
            merged[-1] = Section(previous.heading_path, f"{previous.text} {section.text}")
        else:
            merged.append(section)
    return merged


def _windows(words: list[str], size: int, overlap: int) -> Iterator[list[str]]:
    """Sliding windows of `size` words, each overlapping the previous by `overlap`.

    Stops once a window reaches the end, so the last window is never a duplicate fully
    contained in the one before it.
    """
    step = size - overlap
    start = 0
    while True:
        yield words[start : start + size]
        if start + size >= len(words):
            return
        start += step


def chunk_sections(sections: list[Section], url: str | None = None) -> list[RawChunk]:
    size, overlap = settings.chunk_max_words, settings.chunk_overlap_words
    chunks: list[RawChunk] = []
    for section in _merge_short(sections):
        words = section.text.split()
        pieces = [words] if len(words) <= size else list(_windows(words, size, overlap))
        for piece in pieces:
            if len(piece) >= settings.chunk_min_words:  # a stub of a sentence is index noise
                chunks.append(RawChunk(section.heading_path, " ".join(piece), url, len(piece)))
    return chunks


# --- File parsers (bytes in, plain text out; paragraphs separated by blank lines) ----------


def parse_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages)


def parse_docx(data: bytes) -> str:
    from docx import Document

    document = Document(io.BytesIO(data))
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n\n".join(parts)


def parse_text(data: bytes) -> str:
    return data.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")


PARSERS = {".pdf": parse_pdf, ".docx": parse_docx, ".txt": parse_text, ".md": parse_text}
