"""UC10 Document Anonymizer — DOCX Document Redaction Formatter.

In-place OpenXML Word document redaction preserving styles, tables, and typography.
Applies entity replacements across runs and cleans author metadata.
"""

from __future__ import annotations

import io
import zipfile
from typing import Any

from lxml import etree

try:
    from service.data.wordlists import _PERSON_ATTRS, _TARGET_PREFIX, _W
    from service.processors.text import (
        blank,
        find_spans,
        leaks,
        protect_per_block,
    )
except ImportError:
    from data.wordlists import _PERSON_ATTRS, _TARGET_PREFIX, _W
    from processors.text import (
        blank,
        find_spans,
        leaks,
        protect_per_block,
    )


def docx_paragraph_texts(root: Any, tag: str) -> list[tuple[Any, list[Any]]]:
    """Extract paragraph text elements, keeping nested text boxes separate."""
    out = []
    for p in root.iter(f"{{{_W}}}p"):
        elems = [t for t in p.iter(f"{{{_W}}}{tag}") if next(t.iterancestors(f"{{{_W}}}p"), None) is p]
        if elems:
            out.append((p, elems))
    return out


def rewrite_elements(elems: list[Any], patterns: list, protect: list = ()) -> None:
    """Replace spans across run boundaries without corrupting Word XML formatting."""
    pieces = [t.text or "" for t in elems]
    owner = [i for i, piece in enumerate(pieces) for _ in piece]
    text = "".join(pieces)
    spans = find_spans(text, patterns, protect)
    if not spans:
        return
    new = [""] * len(elems)
    pos = 0
    for start, end, label in spans:
        for i in range(pos, start):
            new[owner[i]] += text[i]
        new[owner[start]] += label
        pos = end
    for i in range(pos, len(text)):
        new[owner[i]] += text[i]
    for t, value in zip(elems, new):
        t.text = value
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def docx_part_texts(root: Any, should_blank: bool = True) -> list[str]:
    """Extract text from DOCX XML part, optionally blanking protected citation areas."""
    body = ["".join(t.text or "" for t in elems) for _, elems in docx_paragraph_texts(root, "t")]
    texts = [blank(t, prot) for t, prot in zip(body, protect_per_block(body))] if should_blank else body
    texts += [
        "".join(t.text or "" for t in elems)
        for tag in ("delText", "instrText")
        for _, elems in docx_paragraph_texts(root, tag)
    ]
    texts += [v for el in root.iter() for v in el.attrib.values()]
    own = {f"{{{_W}}}{tag}" for tag in ("t", "delText", "instrText")}
    texts += [el.text for el in root.iter() if el.text and el.tag not in own]
    texts += [el.tail for el in root.iter() if el.tail]
    return texts


def anonymize_docx(data: bytes, patterns: list) -> tuple[bytes, list[str]]:
    """In-place anonymization of DOCX bytes, returning sanitized bytes and detected leaks."""
    src = zipfile.ZipFile(io.BytesIO(data))
    out_buf = io.BytesIO()
    check_texts: list[str] = []
    raw_texts: list[str] = []
    with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            raw = src.read(item.filename)
            name = item.filename
            if name.endswith((".xml", ".rels")):
                root = etree.fromstring(raw)
                if name.startswith("word/"):
                    paras = docx_paragraph_texts(root, "t")
                    protect = protect_per_block(["".join(t.text or "" for t in elems) for _, elems in paras])
                    for (_, elems), prot in zip(paras, protect):
                        rewrite_elements(elems, patterns, prot)
                    for tag in ("delText", "instrText"):
                        for _, elems in docx_paragraph_texts(root, tag):
                            rewrite_elements(elems, patterns)
                if name.startswith("docProps/"):
                    for el in root.iter():
                        if etree.QName(el).localname in {"creator", "lastModifiedBy", "Company", "Manager"}:
                            el.text = ""
                        elif el.text:
                            rewrite_elements([el], patterns)
                for el in root.iter():
                    for key, value in el.attrib.items():
                        local = etree.QName(key).localname
                        if local in _PERSON_ATTRS:
                            el.set(key, "UC10")
                        elif local == "Target" or name.startswith("word/"):
                            spans = find_spans(value, patterns)
                            for start, end, label in reversed(spans):
                                value = value[:start] + label + value[end:]
                            el.set(key, value)
                check_texts += docx_part_texts(root)
                raw_texts += docx_part_texts(root, should_blank=False)
                raw = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            out.writestr(item, raw)
    targets = [p for p in patterns if p[2].startswith(_TARGET_PREFIX)]
    found_leaks = sorted(set(leaks(check_texts, patterns) + leaks(raw_texts, targets)))
    return out_buf.getvalue(), found_leaks
