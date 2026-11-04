"""UC10 Document Anonymizer — Multi-format Document Handler."""

from __future__ import annotations

import io
import logging
import zipfile

import fitz
from lxml import etree

try:
    from service.data.wordlists import _TARGET_PREFIX
    from service.formatters.docx import docx_paragraph_texts, docx_part_texts, anonymize_docx
    from service.formatters.pdf import anonymize_pdf, pdf_lines, pdf_page_text
    from service.processors.text import replacement_patterns
except ImportError:
    try:
        from data.wordlists import _TARGET_PREFIX
        from formatters.docx import docx_paragraph_texts, docx_part_texts, anonymize_docx
        from formatters.pdf import anonymize_pdf, pdf_lines, pdf_page_text
        from processors.text import replacement_patterns
    except ImportError:
        from .docx import docx_paragraph_texts, docx_part_texts, anonymize_docx
        from .pdf import anonymize_pdf, pdf_lines, pdf_page_text
        from data.wordlists import _TARGET_PREFIX
        from processors.text import replacement_patterns

log = logging.getLogger("presidio-service")


def source_texts(data: bytes, suffix: str) -> list[str]:
    """Extract raw text strings from source document parts."""
    if suffix == "pdf":
        return [pdf_page_text(page)[0] for page in fitz.open(stream=data, filetype="pdf")]
    z = zipfile.ZipFile(io.BytesIO(data))
    return [
        t
        for n in z.namelist()
        if n.endswith(".xml")
        for t in docx_part_texts(etree.fromstring(z.read(n)))
    ]


def file_text(data: bytes, suffix: str) -> str:
    """Extract document's own textual stream for a secondary detection pass."""
    if suffix == "pdf":
        return "\n".join(
            line
            for page in fitz.open(stream=data, filetype="pdf")
            for line in pdf_lines(page)
        )
    z = zipfile.ZipFile(io.BytesIO(data))
    return "\n".join(
        "".join(t.text or "" for t in elems)
        for n in z.namelist()
        if n.startswith("word/") and n.endswith(".xml")
        for _, elems in docx_paragraph_texts(etree.fromstring(z.read(n)), "t")
    )


def unmatched_entities(data: bytes, suffix: str, entity_map: dict[str, str]) -> list[str]:
    """Find originals detected in Docling markdown that are absent from raw file text."""
    texts = source_texts(data, suffix)
    return sorted(
        original
        for original, label in entity_map.items()
        if not label.startswith(_TARGET_PREFIX)
        and not any(p.search(t) for p, _, _ in replacement_patterns({original: label}) for t in texts)
    )


def anonymize_document(
    data: bytes, filename: str, entity_map: dict[str, str]
) -> tuple[bytes | None, list[str], list[str]]:
    """Sanitize document in place, returning (document_bytes, leak_problems, unmatched_entities)."""
    patterns = replacement_patterns(entity_map)
    suffix = filename.lower().rsplit(".", 1)[-1]
    if suffix not in ("docx", "pdf"):
        return None, [f"no same-format output for .{suffix}"], []
    try:
        unmatched = unmatched_entities(data, suffix, entity_map)
        if suffix == "docx":
            out, problems = anonymize_docx(data, patterns)
        elif suffix == "pdf":
            out, problems = anonymize_pdf(data, patterns)
    except Exception as exc:
        log.exception("Same-format output failed for %s", filename)
        return None, [f"could not rewrite document: {exc}"], []

    if unmatched:
        log.warning("%s: %d detected value(s) not found in the file itself.", filename, len(unmatched))
    if problems:
        log.warning("Not returning %s: %d original value(s) still in document.", filename, len(problems))
        return None, problems, unmatched
    return out, [], unmatched
