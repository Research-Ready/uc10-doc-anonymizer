"""UC10 Document Anonymizer — PDF Redaction Formatter.

In-place PDF redaction using PyMuPDF (fitz). Applies true vector redaction annotations
(removing underlying characters rather than merely covering them), maintains visual typography
with font substitution/squeezing, and strips all author metadata and structure trees.
"""

from __future__ import annotations

import re
from typing import Any

import fitz

try:
    from service.data.wordlists import _LABEL_CHARS, _TARGET_PREFIX
    from service.processors.text import (
        blank,
        find_spans,
        leaks,
        protect_per_block,
    )
except ImportError:
    from data.wordlists import _LABEL_CHARS, _TARGET_PREFIX
    from processors.text import (
        blank,
        find_spans,
        leaks,
        protect_per_block,
    )


def pdf_page_text(page: Any) -> tuple[str, list[Any]]:
    """Extract page text with character bounding rects and baseline origins."""
    chars: list[str] = []
    rects: list[Any] = []
    for block in page.get_text("rawdict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                for ch in span["chars"]:
                    chars.append(ch["c"])
                    rects.append((fitz.Rect(ch["bbox"]), ch["origin"][1], span))
            chars.append(" ")
            rects.append(None)
        chars.append("\n")
        rects.append(None)
    return "".join(chars), rects


def label_font(doc: Any, page: Any, span: dict, fonts: dict[str, Any]) -> Any:
    """Use the document's embedded font if it contains required label glyphs, else Noto Sans."""
    name = span["font"]
    if name not in fonts:
        fonts[name] = None
        for xref, _, _, basefont, _, _ in page.get_fonts():
            if basefont.split("+", 1)[-1] != name:
                continue
            try:
                buffer = doc.extract_font(xref)[3]
                font = fitz.Font(fontbuffer=buffer) if buffer else None
            except Exception:
                font = None
            if font and all(font.has_glyph(ord(c)) for c in _LABEL_CHARS):
                fonts[name] = font
            break
        if fonts[name] is None:
            fonts[name] = fitz.Font("notosbo" if span["flags"] & 16 else "notos")
    return fonts[name]


def room_right(text: str, rects: list, end: int, box: Any, page: Any) -> float:
    """Calculate maximum right boundary available for the replacement label."""
    for j in range(end, len(rects)):
        if rects[j] is None:
            return max(box.x1, page.rect.x1 - 36)
        if not text[j].isspace():
            return max(box.x1, rects[j][0].x0 - rects[j][2]["size"] * 0.25)
    return box.x1


def draw_label(
    page: Any, box: Any, baseline: float, span: dict, label: str, room: float, fonts: dict
) -> None:
    """Draw replacement label matching font color, squeezing/shrinking dynamically if needed."""
    font = label_font(page.parent, page, span, fonts)
    size = span["size"]
    natural = font.text_length(label, fontsize=size)
    fit = (room - box.x0) / natural if natural else 1.0
    squeeze = min(1.0, max(0.55, fit))
    shrink = min(1.0, max(0.4, fit / squeeze))
    c = span["color"]
    writer = fitz.TextWriter(
        page.rect,
        color=((c >> 16 & 255) / 255, (c >> 8 & 255) / 255, (c & 255) / 255),
    )
    writer.append((box.x0, baseline), label, font=font, fontsize=size * shrink)
    writer.write_text(page, morph=(fitz.Point(box.x0, baseline), fitz.Matrix(squeeze, 1)))


def pdf_lines(page: Any) -> list[str]:
    """Extract individual text lines directly from page blocks."""
    return [
        "".join(ch["c"] for span in line["spans"] for ch in span["chars"])
        for block in page.get_text("rawdict")["blocks"]
        if block["type"] == 0
        for line in block["lines"]
    ]


def pdf_object_text(obj: str) -> str:
    """Extract string literals and UTF-16 hex values from raw PDF objects."""
    decoded = re.findall(r"\((?:\\.|[^\\)])*\)", obj)
    for m in re.finditer(r"<FEFF([0-9A-Fa-f]+)>", obj):
        try:
            decoded.append(bytes.fromhex(m.group(1)).decode("utf-16-be", "replace"))
        except ValueError:
            pass
    return "\n".join(decoded)


def anonymize_pdf(data: bytes, patterns: list) -> tuple[bytes, list[str]]:
    """Perform true vector redaction on PDF bytes, returning sanitized PDF and leaks."""
    doc = fitz.open(stream=data, filetype="pdf")
    problems: list[str] = []
    fonts: dict[str, Any] = {}
    page_protect = protect_per_block([pdf_page_text(page)[0] for page in doc])

    for page in doc:
        for link in page.get_links():
            if any(p.search(link.get("uri") or "") for p, _, _ in patterns):
                page.delete_link(link)
        for annot in list(page.annots()):
            page.delete_annot(annot)
        for widget in list(page.widgets()):
            page.delete_widget(widget)

        text, rects = pdf_page_text(page)
        if len(text.strip()) < 20 and page.get_images():
            problems.append(f"page {page.number + 1} is a scanned image; text in images cannot be removed")

        labels: list[tuple[Any, float, dict, str, float]] = []
        for start, end, label in find_spans(text, patterns, page_protect[page.number]):
            lines: list[list[Any]] = [[]]
            for r in rects[start:end]:
                if r is None:
                    lines.append([])
                else:
                    lines[-1].append(r)
            for i, line in enumerate(l for l in lines if l):
                box = fitz.Rect(line[0][0])
                for r, _, _ in line[1:]:
                    box |= r
                band = fitz.Rect(
                    box.x0 + 0.2, box.y0 + box.height * 0.3, box.x1 - 0.2, box.y1 - box.height * 0.3
                )
                page.add_redact_annot(band, fill=False)
                if i == 0:
                    labels.append((box, line[0][1], line[0][2], label, room_right(text, rects, end, box, page)))
        page.apply_redactions()
        for box, baseline, span, label, room in labels:
            draw_label(page, box, baseline, span, label, room, fonts)

    # Clean catalog, structure tree, metadata and fonts
    doc.set_metadata({})
    doc.del_xml_metadata()
    doc.set_toc([])
    doc.subset_fonts()
    for name in doc.embfile_names():
        doc.embfile_del(name)
    catalog = doc.pdf_catalog()
    for key in ("StructTreeRoot", "MarkInfo", "Names", "OpenAction"):
        doc.xref_set_key(catalog, key, "null")
    out = doc.tobytes(garbage=4, deflate=True, clean=True)

    # Verification read-back
    check = fitz.open(stream=out, filetype="pdf")
    pages = [pdf_page_text(page)[0] for page in check]
    texts = [blank(t, prot) for t, prot in zip(pages, protect_per_block(pages))]
    problems += leaks(pages, [p for p in patterns if p[2].startswith(_TARGET_PREFIX)])
    texts += [link.get("uri") or "" for page in check for link in page.get_links()]
    texts += [v for v in check.metadata.values() if v]
    texts += [pdf_object_text(check.xref_object(x)) for x in range(1, check.xref_length())]
    return out, problems + leaks(texts, patterns)
