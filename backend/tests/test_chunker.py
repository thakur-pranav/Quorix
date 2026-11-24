from __future__ import annotations

import io

import pytest

from app.ingest.chunker import (
    PARSERS,
    Section,
    _windows,
    chunk_sections,
    sections_from_html,
    sections_from_plain,
)


def words(n: int, prefix: str = "w") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


# --- HTML sections and heading paths --------------------------------------------------------

HTML = f"""
<p>{words(20, "intro")}</p>
<h1>Billing</h1>
<p>{words(20, "billing")}</p>
<h2>Refunds</h2>
<p>{words(20, "refund")}</p>
<ul><li><p>{words(20, "nested")}</p></li></ul>
<h3>Timing</h3>
<p>{words(20, "timing")}</p>
<h2>Invoices</h2>
<p>{words(20, "invoice")}</p>
<h1>Account</h1>
<h3>Password</h3>
<p>{words(20, "password")}</p>
"""


def test_heading_paths_follow_the_document_outline() -> None:
    paths = [s.heading_path for s in sections_from_html(HTML)]
    assert paths == [
        "Introduction",  # text before any heading
        "Billing",
        "Billing › Refunds",
        "Billing › Refunds › Timing",
        "Billing › Invoices",  # an h2 closes the previous h2 and its h3
        "Account › Password",  # h1 -> h3 with no h2: no empty segment
    ]


def test_nested_blocks_are_not_duplicated() -> None:
    refunds = next(s for s in sections_from_html(HTML) if s.heading_path == "Billing › Refunds")
    assert refunds.text.count("nested0") == 1


def test_plain_text_splits_at_blank_lines_with_label() -> None:
    sections = sections_from_plain("First   para\nline two.\n\n\n\nSecond para.", "guide.pdf")
    assert sections == [
        Section("guide.pdf", "First para line two."),
        Section("guide.pdf", "Second para."),
    ]


# --- Merge, window, filter ------------------------------------------------------------------


def test_short_same_path_sections_are_merged() -> None:
    sections = [Section("a.pdf", words(10, "x")), Section("a.pdf", words(10, "y"))]
    chunks = chunk_sections(sections)
    assert len(chunks) == 1 and chunks[0].word_count == 20


def test_different_paths_are_not_merged() -> None:
    sections = [Section("A", words(20, "x")), Section("B", words(20, "y"))]
    assert [c.heading_path for c in chunk_sections(sections)] == ["A", "B"]


def test_stubs_under_15_words_are_dropped() -> None:
    assert chunk_sections([Section("A", words(14))]) == []
    assert len(chunk_sections([Section("A", words(15))])) == 1


def test_section_of_220_words_is_one_chunk() -> None:
    chunks = chunk_sections([Section("A", words(220))], url="https://x.test/a")
    assert len(chunks) == 1
    assert chunks[0].word_count == 220 and chunks[0].url == "https://x.test/a"


def test_long_section_uses_overlapping_windows() -> None:
    chunks = chunk_sections([Section("A", words(400))])
    assert [c.word_count for c in chunks] == [220, 220]  # 0-219 and 180-399
    first, second = (c.text.split() for c in chunks)
    assert first[-40:] == second[:40]  # 40-word overlap
    assert second[-1] == "w399"  # nothing lost at the end


def test_no_redundant_tail_window() -> None:
    """The reference emitted a third window (360-399) that the second already contained."""
    windows = list(_windows(words(400).split(), 220, 40))
    assert len(windows) == 2


@pytest.mark.parametrize("n", [221, 399, 401, 1000])
def test_windows_cover_every_word(n: int) -> None:
    covered = {w for window in _windows(words(n).split(), 220, 40) for w in window}
    assert covered == set(words(n).split())


# --- File parsers ---------------------------------------------------------------------------


def _minimal_pdf(text: str) -> bytes:
    """A valid one-page PDF with one line of text, built by hand (no PDF writer needed)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return bytes(out)


def test_parse_pdf() -> None:
    assert "Refunds take five days" in PARSERS[".pdf"](_minimal_pdf("Refunds take five days"))


def test_parse_docx() -> None:
    from docx import Document

    doc = Document()
    doc.add_paragraph("Refunds take five days.")
    doc.add_paragraph("Contact support for help.")
    buffer = io.BytesIO()
    doc.save(buffer)

    text = PARSERS[".docx"](buffer.getvalue())
    assert text == "Refunds take five days.\n\nContact support for help."


def test_parse_text_strips_bom_and_windows_newlines() -> None:
    assert PARSERS[".txt"]("﻿Line one\r\n\r\nLine two".encode()) == "Line one\n\nLine two"
