# Architecture

## What is anonymized

Two things, decided 2026-10-01:

1. **People**: names (full names, and a surname used on its own later), plus what identifies a person
   directly: email address, phone number, student or employee number, bank account (IBAN).
2. **The target company**: the organisation the research was done for, named by the user in
   `input/targets.txt` (one company per line, other names of the same company after `|`).

Everything else stays readable: other organisations, software (ERP, PLM), places, dates, job titles, and
published references (the reference list and author-year citations like "(Yin, 2018)"). The target company
is masked there too, because a cited company report would give it away.

## Data flow (local stack)

```
input/<name>.pdf|docx + input/targets.txt
        |
        v
scripts/anonymize_folder.py  ──POST /anonymize?document=true&targets=…──>  uc10-anonymizer (127.0.0.1:5010)
                                                                              |
  1. Docling (docling:5001, async API, pdf_backend pypdfium2, no OCR)  <──────+  PDF/DOCX → markdown
  2. Detection on the markdown (Presidio + spaCy nl_core_news_lg / en_core_web_lg)
       - markdown stripped for the NER (bold markers, one table cell per line), offsets mapped back
       - per-line language routing; long texts analysed in 50k-character chunks
       - organisations and places are detected only to win overlaps against wrong person guesses,
         then dropped; common words, defined abbreviations and respondent codes are not names
       - reference section and citations are protected
  3. Second detection pass on the file's own text (PDF text layer / Word paragraphs):
       Docling sometimes writes text differently ("22-06-2026" became a list item)
  4. Target company names (all given aliases), surnames of detected full names
  5. Labels from Neo4j (neo4j:7687): hash(type|value) → PERSOON_n / ID_n / ORGANISATIE_n, global and stable
  6. Rewrite the original file:
       DOCX: text replaced inside the Word XML across runs (body, tables, headers, footers, footnotes,
             comments, tracked changes, field codes, hyperlinks); author properties and comment authors removed
       PDF:  text redacted with PyMuPDF (removed, not covered), label drawn in an embedded font in the
             original size and colour; PII links, comments, forms, bookmarks, metadata, attachments and
             the structure tree removed
  7. Read-back check: if any original is still in the written file, no document is returned
        |
        v
output/<name with people and target masked>_anon.pdf        (non-PDF input: output/<name>/)
keys/<name>.<ext>.entity_map.json, keys/done.json           (the key; personal data, not shared)
```

## Privacy design

- The service connects only to Docling and Neo4j. During a 46-page run, every connection of the anonymizer
  and Docling stayed inside the local Docker network. Host ports are bound to 127.0.0.1.
- Not yet enforced: the containers can reach the internet. Network isolation is requested in
  `InstallLocalAiPackage/REQUEST-uc10-network-isolation.md`.
- Neo4j stores a SHA-256 hash, the label and the type; never the original value.
- The entity map reverses the anonymization, so it is personal data: it is written to `keys/`, apart from
  `output/`, and kept out of git.
- The repo folder is in Nextcloud, so `input/`, `output/` and `keys/` are synced to the Nextcloud server.
- Users get a Dutch one-pager on this: `output/Onepager - lokaal anonimiseren.pdf` (source `docs/onepager-lokaal.html`).

## Service

- `service/app.py`, FastAPI; localstack container `uc10-anonymizer` (Dockerfile in InstallLocalAiPackage builds
  from this repo's `service/`). Rebuild after a change:
  `docker compose -f docker-compose.yml -f docker-compose.laptop.yml up -d --build --no-deps uc10-anonymizer`
- Dependencies: presidio 2.2.356, spaCy 3.7.6 with `nl_core_news_lg` 3.7.0 and `en_core_web_lg` 3.7.1,
  PyMuPDF 1.26.4 (AGPL: fine internally, decide before distributing), pymupdf-fonts, lxml, pyspellchecker.
- Memory: 3 GB limit, ~1.7 GB in use (both LG models; 1.5 GB OOM-kills them).

## Labels

| Type | Example | Label |
|---|---|---|
| Person | Jan de Vries, later "De Vries" | PERSOON_1 |
| Target company | Acme Trailers, acmetrailers.nl | ORGANISATIE_1 |
| Student / employee number | S1234567 | ID_1 |
| Email address | jan@example.nl | EMAIL_1 |
| Phone number | 06-12345678 | TELEFOON_1 |
| Bank account | NL91ABNA0417164300 | IBAN_1 |

Labels are global and stable: the same value of the same type gets the same label in every document.

## Tests

- `tests/dry_run.py`: service health, anonymize, consistency, DOCX and PDF through Docling, same-format
  output checked with independent tools; writes `test-results/dry_run_*.json`.
- `tests/eval_detection.py`: fictional NL/EN/mixed texts; counts leaks (people and target company still
  readable) and false positives (anything else masked). 2026-10-01: 0 leaks of 44, 0 false positives.

## Phase 2 — role-aware labels (future work)

Interview transcripts distinguish speakers. A later version could emit `INTERVIEWER_1` and `RESPONDENT_1`
instead of `PERSOON_n`, by parsing speaker turns before detection.
