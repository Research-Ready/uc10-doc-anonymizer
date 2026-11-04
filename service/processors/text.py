"""UC10 Document Anonymizer — NLP and Text Processing Engine.

Handles text sanitization, language routing (NL/EN), spaCy NER chunking,
post-processing filters (overlap pruning, surname extensions, common-word drops),
citation protection, and Docling integration.
"""

from __future__ import annotations

import base64
import html
import logging
import re
import time
from typing import Any, List, Tuple

import httpx
try:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult
except ImportError:
    AnalyzerEngine = Any
    class RecognizerResult:
        RECOGNIZER_NAME_KEY = "recognizer_name"
        def __init__(self, entity_type, start, end, score, **kwargs):
            self.entity_type = entity_type
            self.start = start
            self.end = end
            self.score = score
            self.recognition_metadata = kwargs.get("recognition_metadata", {})
            self.analysis_explanation = kwargs.get("analysis_explanation")

try:
    from service.data.wordlists import (
        DETECTED_ENTITIES,
        SUPPORTED_LANGUAGES,
        _ALL_EN,
        _ANALYZE_CHUNK,
        _ANALYZE_ENTITIES,
        _BRAND_WORDS,
        _CITE_PART,
        _CODE,
        _COMMON_EN,
        _COMMON_FREQ,
        _COMMON_WORDS,
        _CONNECTORS,
        _DATE_SHAPE,
        _EN_WORDS,
        _GENERIC_ACRONYMS,
        _MD_ESCAPE,
        _MONTHS,
        _NAME_TAIL,
        _NAME_TOKEN,
        _NAME_WORDS,
        _NARRATIVE,
        _NL_WORDS,
        _ORG_TAIL,
        _PAREN,
        _PARTICLES,
        _REF_HEADING,
        _SECTION_END,
        _TABLE_RULE,
        _TARGET_PREFIX,
        _TECH_TERM,
        _WORD,
    )
except ImportError:
    from data.wordlists import (
        DETECTED_ENTITIES,
        SUPPORTED_LANGUAGES,
        _ALL_EN,
        _ANALYZE_CHUNK,
        _ANALYZE_ENTITIES,
        _BRAND_WORDS,
        _CITE_PART,
        _CODE,
        _COMMON_EN,
        _COMMON_FREQ,
        _COMMON_WORDS,
        _CONNECTORS,
        _DATE_SHAPE,
        _EN_WORDS,
        _GENERIC_ACRONYMS,
        _MD_ESCAPE,
        _MONTHS,
        _NAME_TAIL,
        _NAME_TOKEN,
        _NAME_WORDS,
        _NARRATIVE,
        _NL_WORDS,
        _ORG_TAIL,
        _PAREN,
        _PARTICLES,
        _REF_HEADING,
        _SECTION_END,
        _TABLE_RULE,
        _TARGET_PREFIX,
        _TECH_TERM,
        _WORD,
    )

log = logging.getLogger("presidio-service")


def guess_language(text: str) -> str | None:
    """'nl' or 'en' by function-word count; None when undecided."""
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    nl = sum(w in _NL_WORDS for w in words)
    en = sum(w in _EN_WORDS for w in words)
    if nl == en:
        return None
    return "nl" if nl > en else "en"


def plain_for_ner(text: str) -> tuple[str, list[int]]:
    """Markdown as the NER should see it, plus the original index of every character."""
    out: list[str] = []
    index: list[int] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        is_table = line.lstrip().startswith("|")
        if is_table and _TABLE_RULE.match(line.strip()):
            out.append("\n")
            index.append(pos + len(line) - 1)
            pos += len(line)
            continue
        heading = re.match(r"#{1,6}[ \t]+", line)
        i = heading.end() if heading else 0
        while i < len(line):
            if line.startswith("**", i) or line.startswith("__", i):
                i += 2
                continue
            ch = "\n" if is_table and line[i] == "|" else line[i]
            out.append(ch)
            index.append(pos + i)
            i += 1
        pos += len(line)
    return "".join(out), index


def is_ner(r: RecognizerResult) -> bool:
    """True for a spaCy NER guess; rule-based recognizers win ties against it."""
    meta = r.recognition_metadata or {}
    return meta.get(RecognizerResult.RECOGNIZER_NAME_KEY) == "SpacyRecognizer"


def plausible(r: RecognizerResult, text: str) -> bool:
    """Drop guesses that cannot identify anyone (e.g. durations, single-letter initials)."""
    span = text[r.start:r.end].strip()
    if r.entity_type == "DATE_TIME":
        lower = span.lower()
        return bool(_DATE_SHAPE.search(span)) or (
            any(c.isdigit() for c in span) and any(m in lower for m in _MONTHS)
        )
    if r.entity_type == "URL" and "://" not in span and not span.lower().startswith("www."):
        host = span.split("/")[0]
        return host[:1].isalpha() and host.rsplit(".", 1)[-1].islower()
    if not is_ner(r):
        return True
    if r.entity_type == "PERSON":
        content = [w for w in _WORD.findall(span) if w.lower() not in _CONNECTORS]
        if len(content) == 1 and content[0].isupper() and len(content[0]) > 1:
            return False
    if r.entity_type in ("PERSON", "ORGANIZATION", "LOCATION"):
        return len(span) >= 2 and any(c.isupper() for c in span)
    return True


def trim_person(results: list[RecognizerResult], text: str) -> list[RecognizerResult]:
    """Cut trailing organisation parts from names (e.g. 'Priya Ramdin van TNO')."""
    for r in results:
        if r.entity_type == "PERSON":
            m = _ORG_TAIL.search(text[r.start:r.end])
            if m and m.start() > 0:
                r.end = r.start + m.start()
    return results


def split_lines(results: list[RecognizerResult], text: str) -> list[RecognizerResult]:
    """Ensure entities do not span lines, splitting multi-line spans."""
    out = []
    for r in results:
        if "\n" not in text[r.start:r.end]:
            out.append(r)
            continue
        for m in re.finditer(r"[^\n]+", text[r.start:r.end]):
            piece = m.group()
            start = r.start + m.start() + (len(piece) - len(piece.lstrip()))
            end = r.start + m.end() - (len(piece) - len(piece.rstrip()))
            if end > start:
                out.append(
                    RecognizerResult(
                        r.entity_type,
                        start,
                        end,
                        r.score,
                        analysis_explanation=r.analysis_explanation,
                        recognition_metadata=r.recognition_metadata,
                    )
                )
    return out


def extend_names(results: list[RecognizerResult], text: str) -> list[RecognizerResult]:
    """Extend PERSON spans over following capitalised surname tokens."""
    for r in results:
        if r.entity_type == "PERSON":
            m = _NAME_TAIL.match(text, r.end)
            if m:
                r.end = m.end()
    return results


def load_common_words() -> None:
    """Load Dutch and English frequency lists to identify common non-name words."""
    try:
        from spellchecker import SpellChecker
        for lang in ("en", "nl"):
            freq = SpellChecker(language=lang, distance=1).word_frequency.dictionary
            common = {w for w, n in freq.items() if n >= _COMMON_FREQ}
            _COMMON_WORDS.update(common)
            if lang == "en":
                _COMMON_EN.update(common)
                _ALL_EN.update(freq)
    except Exception as exc:
        log.warning("Could not load spellchecker dictionary (%s)", exc)


def dictionary_word(word: str) -> bool:
    """True if word is in common dictionaries and not a known protected name/brand."""
    w = word.lower()
    if len(w) == 1 or w in _GENERIC_ACRONYMS:
        return True
    if w in _BRAND_WORDS:
        return False
    if w in _COMMON_WORDS:
        return True
    if w.startswith("un") and w[2:] in _COMMON_WORDS:
        return True
    if "is" in w and w.replace("isation", "visualization").replace("ise", "ize") in _ALL_EN:
        return True
    return any(w[:i] in _COMMON_EN and w[i:] in _COMMON_EN for i in range(3, len(w) - 2))


def lowercase_vocabulary(text: str) -> set[str]:
    prose = re.sub(r"\S*(?:@|/|\w\.\w)\S*", " ", text)
    return {w for w in _WORD.findall(prose) if w.islower()}


def defined_acronyms(text: str, vocab: set[str]) -> set[str]:
    found = set()
    for m in re.finditer(r"\(([a-z]?[A-Z]{2,6})s?\)", text):
        acronym = m.group(1).upper()
        words = _WORD.findall(text[max(0, m.start() - 120):m.start()])[-8:]
        for k in range(1, len(words) + 1):
            tail = words[-k:]
            content = [w for w in tail if w.lower() not in _CONNECTORS]
            if acronym in ("".join(w[0] for w in tail).upper(), "".join(w[0] for w in content).upper()):
                if content and all(w.lower() in vocab for w in content):
                    found.add(acronym)
                break
    return found


def drop_common_words(results: list[RecognizerResult], text: str) -> list[RecognizerResult]:
    vocab = lowercase_vocabulary(text)
    acronyms = defined_acronyms(text, vocab)

    def words(r: RecognizerResult) -> list[str]:
        return [w for w in _WORD.findall(text[r.start:r.end]) if w.lower() not in _CONNECTORS]

    def common(r: RecognizerResult, name_words=frozenset()) -> bool:
        if not is_ner(r) or r.entity_type not in ("PERSON", "ORGANIZATION", "LOCATION"):
            return False
        if _CODE.match(text[r.start:r.end].strip()):
            return True
        dictionary = r.entity_type == "ORGANIZATION"
        tokens = _WORD.findall(text[r.start:r.end])

        def looks_like_name(i: int) -> bool:
            if tokens[i].lower() not in _NAME_WORDS:
                return False
            content = [t for t in tokens if t.lower() not in _CONNECTORS]
            neighbours = tokens[max(0, i - 1):i] + tokens[i + 1:i + 2]
            return len(content) == 1 or any(
                n[0].isupper() and n.lower() not in _CONNECTORS for n in neighbours
            )

        return all(
            (
                w.lower() in vocab
                or w.upper() in acronyms
                or w.upper()[:-1] in acronyms
                or _TECH_TERM.match(w)
                or (dictionary and dictionary_word(w) and not looks_like_name(i))
            )
            and w.lower() not in name_words
            for i, w in enumerate(tokens)
            if w.lower() not in _CONNECTORS
        )

    name_words = {
        w.lower() for r in results if r.entity_type == "PERSON" and not common(r) for w in words(r)
    }
    return [r for r in results if not common(r, name_words)]


def surnames(entity_map: dict[str, str]) -> dict[str, str]:
    """Map standalone surnames to the full name's allocated pseudonym label."""
    out: dict[str, str] = {}
    for original, label in sorted(entity_map.items(), key=lambda kv: len(kv[0])):
        if not label.startswith("PERSOON_"):
            continue
        run: list[str] = []
        for token in original.split():
            if not (_NAME_TOKEN.match(token) or token.lower() in _PARTICLES):
                break
            run.append(token)
        last = max((i for i, t in enumerate(run) if t[0].isupper() and not t.endswith(".")), default=None)
        if last is None or last == 0 or len(run[last]) < 3 or run[last].isupper():
            continue
        first = last
        while first > 0 and run[first - 1].lower() in _PARTICLES:
            first -= 1
        surname = " ".join(run[first:last + 1])
        for variant in {surname, surname[0].upper() + surname[1:]}:
            if variant not in entity_map:
                out.setdefault(variant, label)
    return out


def in_scope(results: list[RecognizerResult]) -> list[RecognizerResult]:
    return [r for r in results if r.entity_type in DETECTED_ENTITIES]


def drop_overlaps(results: list[RecognizerResult]) -> list[RecognizerResult]:
    """Keep one result per region of text: longest span, then rule over NER, then score."""
    kept: list[RecognizerResult] = []
    for r in sorted(
        results, key=lambda r: (-(r.end - r.start), is_ner(r), -r.score, r.start)
    ):
        if all(r.end <= k.start or r.start >= k.end for k in kept):
            kept.append(r)
    return kept


def protected_spans(text: str) -> list[tuple[int, int]]:
    """Identify sections with published literature citations to remain unmasked."""
    text_clean = text.replace("&amp;", "&    ")
    spans: list[tuple[int, int]] = []
    start = None
    pos = 0
    for line in text_clean.splitlines(keepends=True):
        if start is None and _REF_HEADING.match(line.strip()):
            start = pos
        elif start is not None and _SECTION_END.match(line):
            spans.append((start, pos))
            start = None
        pos += len(line)
    if start is not None:
        spans.append((start, len(text_clean)))
    for m in _PAREN.finditer(text_clean):
        if all(_CITE_PART.match(part) for part in m.group(1).split(";")):
            spans.append((m.start(), m.end()))
    spans += [(m.start(), m.end()) for m in _NARRATIVE.finditer(text_clean)]
    return spans


def inside(start: int, end: int, protect: list[tuple[int, int]]) -> bool:
    return any(start < e and end > s for s, e in protect)


def protect_per_block(blocks: list[str]) -> list[list[tuple[int, int]]]:
    spans = protected_spans("\n".join(blocks))
    out, offset = [], 0
    for block in blocks:
        end = offset + len(block)
        out.append(
            [(max(s, offset) - offset, min(e, end) - offset) for s, e in spans if s < end and e > offset]
        )
        offset = end + 1
    return out


def blank(text: str, protect: list[tuple[int, int]]) -> str:
    for s, e in protect:
        text = text[:s] + " " * (e - s) + text[e:]
    return text


def replacement_patterns(entity_map: dict[str, str]) -> list[tuple[re.Pattern, str, str]]:
    """(regex_pattern, original_text, label), longest original first."""
    pairs: dict[str, str] = {}
    for original, label in entity_map.items():
        for variant in {
            original,
            _MD_ESCAPE.sub(r"\1", original),
            html.unescape(_MD_ESCAPE.sub(r"\1", original)),
        }:
            if variant.strip():
                pairs[variant.strip()] = label
    patterns = []
    for original in sorted(pairs, key=len, reverse=True):
        body = r"\s+".join(re.escape(part) for part in original.split())
        patterns.append((re.compile(rf"(?<!\w){body}(?!\w)"), original, pairs[original]))
    return patterns


def find_spans(
    text: str, patterns: list[tuple[re.Pattern, str, str]], protect: list[tuple[int, int]] = ()
) -> list[tuple[int, int, str]]:
    taken: list[tuple[int, int, str]] = []
    for pattern, _, label in patterns:
        for m in pattern.finditer(text):
            if inside(m.start(), m.end(), protect) and not label.startswith(_TARGET_PREFIX):
                continue
            if all(m.end() <= s or m.start() >= e for s, e, _ in taken):
                taken.append((m.start(), m.end(), label))
    return sorted(taken)


def leaks(texts: list[str], patterns: list[tuple[re.Pattern, str, str]]) -> list[str]:
    return sorted({original for pattern, original, _ in patterns for t in texts if pattern.search(t)})


def analyze_chunk(analyzer: AnalyzerEngine, text: str) -> list[RecognizerResult]:
    doc_lang = guess_language(text) or "nl"
    line_lang: list[tuple[int, int, str]] = [
        (m.start(), m.end(), guess_language(m.group()) or doc_lang)
        for m in re.finditer(r"[^\n]+", text)
    ]

    def lang_at(pos: int) -> str:
        for start, end, lang in line_lang:
            if start <= pos < end:
                return lang
        return doc_lang

    return [
        r
        for lang in SUPPORTED_LANGUAGES
        for r in trim_person(
            split_lines(
                analyzer.analyze(text=text, language=lang, entities=_ANALYZE_ENTITIES), text
            ),
            text,
        )
        if r.entity_type in _ANALYZE_ENTITIES and lang_at(r.start) == lang and plausible(r, text)
    ]


def analyze_text(analyzer: AnalyzerEngine, text: str) -> list[RecognizerResult]:
    """Analyze text in whole-line chunks to keep memory bounded."""
    if len(text) <= _ANALYZE_CHUNK:
        return analyze_chunk(analyzer, text)
    results, start = [], 0
    while start < len(text):
        end = min(len(text), start + _ANALYZE_CHUNK)
        if end < len(text):
            cut = text.rfind("\n", start, end)
            end = cut + 1 if cut > start else end
        for r in analyze_chunk(analyzer, text[start:end]):
            r.start += start
            r.end += start
            results.append(r)
        start = end
    return results


async def docling_to_markdown(
    file_bytes: bytes, filename: str, docling_url: str, timeout: int = 1800
) -> tuple[str, str]:
    """Convert input file (PDF/DOCX) to clean Markdown via Docling service."""
    if filename.lower().endswith((".txt", ".md")):
        return file_bytes.decode("utf-8", errors="replace"), "plain_text"

    b64 = base64.b64encode(file_bytes).decode()
    payload = {
        "options": {"pdf_backend": "pypdfium2", "do_ocr": False},
        "sources": [{"kind": "file", "base64_string": b64, "filename": filename}],
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{docling_url}/v1/convert/source/async", json=payload)
            resp.raise_for_status()
            task_id = resp.json()["task_id"]
            deadline = time.monotonic() + timeout
            while True:
                status = (
                    await client.get(f"{docling_url}/v1/status/poll/{task_id}", params={"wait": 10})
                ).json()
                if status.get("task_status") in ("success", "partial_success", "failure"):
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError(f"Docling task {task_id} not completed after {timeout}s")
            resp = await client.get(f"{docling_url}/v1/result/{task_id}")
            resp.raise_for_status()
            data = resp.json()
            markdown = (data.get("document") or {}).get("md_content") or ""
            if not markdown.strip():
                raise ValueError(
                    f"no markdown returned (status={data.get('status')}, errors={data.get('errors')})"
                )
            return markdown, "docling"
    except Exception as exc:
        log.warning("Docling unreachable (%s) — falling back to plain text UTF-8.", exc)
        return file_bytes.decode("utf-8", errors="replace"), "fallback"
