"""UC10 Document Anonymizer — Presidio & spaCy FastAPI Service.

A clean, modular, production-grade local anonymization service.
Decomposed into dedicated subpackages:
- service.data: Wordlists, acronyms, brand dictionaries, and regex patterns
- service.recognizers: Custom Dutch Presidio recognizers (BSN 11-proef, TitledName)
- service.processors: NLP chunking, overlap pruning, surname unification, citation shields
- service.formatters: In-place PDF & DOCX vector redaction and formatting preservation
- service.storage: Neo4j cross-document entity registry with in-memory fallback
"""

from __future__ import annotations

import base64
import logging
import os
import re
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# Ensure both /app and /app/service are on sys.path for Docker & native compatibility
_SERVICE_DIR = Path(__file__).resolve().parent
_REPO_DIR = _SERVICE_DIR.parent
for _p in (str(_SERVICE_DIR), str(_REPO_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NerModelConfiguration, NlpEngineProvider

try:
    from service.data.wordlists import (
        DETECTED_ENTITIES,
        SUPPORTED_LANGUAGES,
        _ANALYZE_ENTITIES,
    )
    from service.formatters import anonymize_document, file_text
    from service.processors.text import (
        analyze_text,
        docling_to_markdown,
        drop_common_words,
        drop_overlaps,
        extend_names,
        find_spans,
        in_scope,
        inside,
        load_common_words,
        plain_for_ner,
        protected_spans,
        replacement_patterns,
        surnames,
    )
    from service.recognizers.dutch import setup_custom_recognizers
    from service.storage.registry import (
        close_neo4j_driver,
        get_neo4j_driver,
        resolve_label,
    )
except ImportError:
    from data.wordlists import (
        DETECTED_ENTITIES,
        SUPPORTED_LANGUAGES,
        _ANALYZE_ENTITIES,
    )
    from formatters import anonymize_document, file_text
    from processors.text import (
        analyze_text,
        docling_to_markdown,
        drop_common_words,
        drop_overlaps,
        extend_names,
        find_spans,
        in_scope,
        inside,
        load_common_words,
        plain_for_ner,
        protected_spans,
        replacement_patterns,
        surnames,
    )
    from recognizers.dutch import setup_custom_recognizers
    from storage.registry import (
        close_neo4j_driver,
        get_neo4j_driver,
        resolve_label,
    )

log = logging.getLogger("presidio-service")
logging.basicConfig(level=logging.INFO)

DOCLING_URL: str = os.getenv("DOCLING_URL", "http://localhost:5001")
DOCLING_TIMEOUT: int = int(os.getenv("DOCLING_TIMEOUT", "1800"))
PORT: int = int(os.getenv("PORT", "5002"))

analyzer: AnalyzerEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    global analyzer

    log.info("Loading spaCy Dutch & English models...")
    ner_config = NerModelConfiguration(
        labels_to_ignore=[
            lbl for lbl in NerModelConfiguration().labels_to_ignore if lbl not in ("ORG", "ORGANIZATION")
        ]
    )
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [
                {"lang_code": "nl", "model_name": "nl_core_news_lg"},
                {"lang_code": "en", "model_name": "en_core_web_lg"},
            ],
            "ner_model_configuration": ner_config.to_dict(),
        }
    )
    nlp_engine = provider.create_engine()

    registry = RecognizerRegistry(supported_languages=SUPPORTED_LANGUAGES)
    registry.load_predefined_recognizers(nlp_engine=nlp_engine, languages=SUPPORTED_LANGUAGES)

    # Register custom Dutch BSN 11-proof, TitledName, Date, and Org recognizers
    setup_custom_recognizers(registry, SUPPORTED_LANGUAGES)

    analyzer = AnalyzerEngine(
        nlp_engine=nlp_engine,
        registry=registry,
        supported_languages=SUPPORTED_LANGUAGES,
    )

    load_common_words()
    log.info("Presidio engines and custom recognizers initialized successfully.")

    get_neo4j_driver()
    yield
    close_neo4j_driver()


app = FastAPI(
    title="UC10 Presidio Document Anonymizer",
    version="1.0.0",
    description="100% Local, offline privacy preserving document anonymization engine.",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    driver = get_neo4j_driver()
    neo4j_ok = driver is not None
    docling_ok = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{DOCLING_URL}/health")
            docling_ok = r.status_code == 200
    except Exception:
        docling_ok = False

    is_healthy = neo4j_ok and docling_ok
    return {
        "status": "ok" if is_healthy else "degraded",
        "models": SUPPORTED_LANGUAGES,
        "services": {
            "neo4j": "connected" if neo4j_ok else "offline",
            "docling": "connected" if docling_ok else "offline",
        },
    }


@app.post("/anonymize")
async def anonymize(
    file: UploadFile = File(...),
    project_id: str = Query("default"),
    document: bool = Query(
        False, description="also return the anonymized file in its original format (DOCX/PDF)"
    ),
    targets: str = Query(
        "",
        description="target companies to mask: comma between companies, | between names ('Acme | Acme BV')",
    ),
):
    t0 = time.monotonic()
    file_bytes = await file.read()
    filename = file.filename or "upload.txt"

    # Step 1: Text extraction via Docling (with fallback to plain text)
    text, extracted_with = await docling_to_markdown(file_bytes, filename, DOCLING_URL, DOCLING_TIMEOUT)
    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from document.")
    log.info("%s: %d characters of text via %s", filename, len(text), extracted_with)

    # Step 2: Presidio NER & rule analysis with per-line language routing
    plain, index = plain_for_ner(text)
    raw_results = analyze_text(analyzer, plain)
    results = in_scope(drop_overlaps(drop_common_words(extend_names(raw_results, plain), plain)))

    # Step 3+4: Resolve stable pseudonym labels (protecting literature citations)
    entity_map: dict[str, str] = {}
    span_labels: list[tuple[int, int, str]] = []

    protect = protected_spans(text)
    results = [r for r in results if not inside(index[r.start], index[r.end - 1] + 1, protect)]
    for r in results:
        original = plain[r.start : r.end].strip()
        if not original:
            continue
        if original not in entity_map:
            entity_map[original] = resolve_label(original, r.entity_type)
        span_labels.append((index[r.start], index[r.end - 1] + 1, entity_map[original]))

    # Step 5: Replace spans in reverse offset order
    anon_text = text
    for start, end, label in sorted(span_labels, key=lambda x: x[0], reverse=True):
        markers = "".join(re.findall(r"\*\*|__", anon_text[start:end]))
        anon_text = anon_text[:start] + label + markers + anon_text[end:]

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    log.info("Anonymized %s: %d entities in %dms", filename, len(results), elapsed_ms)

    entity_count = len(results)
    suffix = filename.lower().rsplit(".", 1)[-1]
    raw_file_text = ""

    # Step 6: Second pass on raw document stream if document generation requested
    if document and suffix in ("docx", "pdf"):
        raw_file_text = file_text(file_bytes, suffix)
        extra: dict[str, str] = {}
        file_protect = protected_spans(raw_file_text)
        for r in in_scope(
            drop_overlaps(
                drop_common_words(
                    extend_names(analyze_text(analyzer, raw_file_text), raw_file_text), raw_file_text
                )
            )
        ):
            if inside(r.start, r.end, file_protect):
                continue
            original = raw_file_text[r.start : r.end].strip()
            if original and original not in entity_map and original not in extra:
                extra[original] = resolve_label(original, r.entity_type)
        if extra:
            spans = find_spans(anon_text, replacement_patterns(extra), protected_spans(anon_text))
            for start, end, label in reversed(spans):
                anon_text = anon_text[:start] + label + anon_text[end:]
            entity_map.update(extra)
            entity_count += len(extra)
            log.info("%s: %d value(s) found only in raw document text.", filename, len(extra))

    # Step 7: Target company masking (global)
    target_labels: dict[str, str] = {}
    target_map: dict[str, str] = {}
    for company in targets.split(","):
        names = [n.strip() for n in company.split("|") if n.strip()]
        if not names:
            continue
        label = resolve_label(names[0], "ORGANIZATION")
        for name in names:
            target_labels[name] = label
            for variant in {name, name.lower(), name.upper(), name.title()}:
                if any(
                    p.search(t)
                    for p, _, _ in replacement_patterns({variant: label})
                    for t in (text, raw_file_text)
                ):
                    target_map[variant] = label
    if target_map:
        spans = find_spans(anon_text, replacement_patterns(target_map))
        for start, end, label in reversed(spans):
            anon_text = anon_text[:start] + label + anon_text[end:]
        entity_map.update(target_map)
        entity_count += len(spans)

    # Step 8: Lone surnames mapped to full person label
    lone_surnames = {
        name: label
        for name, label in surnames(entity_map).items()
        if any(
            p.search(t) for p, _, _ in replacement_patterns({name: label}) for t in (text, raw_file_text)
        )
    }
    if lone_surnames:
        spans = find_spans(anon_text, replacement_patterns(lone_surnames), protected_spans(anon_text))
        for start, end, label in reversed(spans):
            anon_text = anon_text[:start] + label + anon_text[end:]
        entity_map.update(lone_surnames)
        entity_count += len(spans)

    response: dict[str, Any] = {
        "anonymized_text": anon_text,
        "entity_map": entity_map,
        "targets": target_labels,
        "entity_count": entity_count,
        "extracted_with": extracted_with,
    }
    if document and suffix in ("docx", "pdf"):
        doc_bytes, problems, unmatched = anonymize_document(file_bytes, filename, entity_map)
        response["document_base64"] = base64.b64encode(doc_bytes).decode() if doc_bytes else None
        response["document_problems"] = problems
        response["document_unmatched"] = unmatched
    return response
