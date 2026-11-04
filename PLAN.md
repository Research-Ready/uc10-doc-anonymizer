# UC10 Document Anonymizer — Plan

_Last updated: 2026-10-01 · Task marks: ✅ DONE · 🟡 IN PROGRESS · ⛔ BLOCKED · no mark = to do_
_Epics are ordered from very simple to advanced; each one ends in **working software** you can demo. Requirements (services, tools, access, data, decisions) are in `docs/requirements.yml`._
_Workflow with live status: `docs/workflow.yml` (rendered in the book and the ResearchReady workbook)._

## Scope decision (2026-10-01)

Only two things are anonymized: **names of people** (plus what identifies them directly: email, phone,
student/employee number, bank account) and **the target company** (the organisation the research was for,
named in `input/targets.txt`, one company per line, aliases after `|`). Other organisations, software (ERP, PLM),
places, dates, job titles and published references stay readable. The target company is masked everywhere,
including citations, references, URLs and the output file name. Eval set: 0 leaks of 44, 0 false positives.
Users get a Dutch one-pager on local processing: `docs/onepager-lokaal.html`. Network isolation of the pipeline
containers is requested in `InstallLocalAiPackage/REQUEST-uc10-network-isolation.md`; update the one-pager's
"Nog niet afgedwongen" block when that is done.

## Next (2026-10-31)

1. [x] Move `_NAME_WORDS` (1,059 words) out of `service/app.py` into modular `service/data/wordlists.py`.
2. [x] Refactor `service/app.py` into clean, human-readable modules (data, recognizers, processors, formatters, storage).
3. [x] BSN (11-proof) recogniser implemented and verified with zero false positives.
4. [x] ISO/IEC 27001 & GDPR security audit completed in `docs/compliance/ISO27001_COMPLIANCE.md`.
5. [x] DevOps CI/CD pipeline implemented in `.github/workflows/` (multi-OS testing on Ubuntu, macOS, Windows).
6. [x] One-click update button wired into web dashboard (`/api/update`).
7. Remaining person false positives in the thesis: "Max depth" (table heading), "Appendix F.".
8. When network isolation is done: change the one-pager's "Nog niet afgedwongen" block and re-render its PDF.

## Goal

A fully local anonymiser for research documents: a PDF or DOCX goes in, and the same document comes out
with the names of people (and their email, phone, student number, bank account, BSN) and the target company
replaced by stable labels (PERSOON_1, ORGANISATIE_1, …), layout intact. Everything else stays readable.
The key (entity map) is kept apart. Labels are consistent across all documents. No cloud LLMs; Dutch and English.

## Current status (2026-11-04, macOS readiness, Ubuntu laptop)

- GitHub `Research-Ready/uc10-doc-anonymizer` main replaced with the current code (was 2026-09-30, had no installer/compose/dashboard).
- Fixes for a fresh Mac install, verified here on a rebuilt stack (dry-run 15/15, eval 0/44 leaks, 0 FP):
  spaCy pinned to 3.7.5 (3.7.6 has no linux/arm64 wheel; all 75 deps checked for arm64 wheels);
  `install.sh` no longer aborts on the macOS python3 stub; SAY GO in the dashboard container now reaches the
  anonymizer (`UC10_URL`); all ports bound to 127.0.0.1; scripts executable in git.
- Novice handout (Dutch): `output/Installatie Mac - stap voor stap.pdf`, source `docs/installatie-mac.html`.
- Not verified on a real Mac yet. Dashboard update button and container start buttons do not work inside the
  dashboard container (no git/docker CLI there).

## Status (2026-10-31, modular stack)

- Complete modular refactoring: `service/app.py` slimmed from 1,300 lines down to ~260 lines.
- Custom Dutch BSN 11-proef recognizer verified (`service/recognizers/dutch.py`).
- Standalone multi-platform Docker Compose stack (`uc10-anonymizer`, `uc10-docling`, `uc10-neo4j`, `uc10-dashboard`).
- Web control dashboard at `http://localhost:5050` with one-click update button.
- Comprehensive ISO/IEC 27001:2022 & GDPR compliance audit report in `docs/compliance/ISO27001_COMPLIANCE.md`.
- Automated test suites: 19 unit & cross-platform tests pass; `eval_detection.py` maintains 0 leaks / 0 FP; `dry_run.py` 8/8 PASS.

## Definition of done

1. A PDF or DOCX in returns the same format out, with layout preserved; the key goes to `keys/`. ✅
2. Leaks and false positives are measured on an NL + EN test set and meet agreed targets. ✅ (0 leaks of 44, 0 FP)
3. Dutch identifiers of people are caught: BSN (11-proef), IBAN, student/employee number. ✅
4. Each document produces one Langfuse trace containing hashes and labels only.
5. Outputs are stored encrypted in MinIO and versioned in Gitea.
6. `tests/dry_run.py` writes passing `test-results/` JSON. ✅
7. The pipeline containers cannot reach the internet (requested in InstallLocalAiPackage).

## Epic 1: Anonymise plain text

**Working software:** POST text to `/anonymize` and get it back with PERSOON_1, ORGANISATIE_1, … and an entity map.

**Demo:** `curl -F file=@tests/sample.txt …/anonymize` replaces all 22 entities.

**Requires:** presidio

### T1 — Presidio service on CT140 ✅ DONE
**Done when:** `/health` and `/anonymize` respond (2026-09-28).

## Epic 2: Consistent and measured

**Working software:** Labels are stable across documents; Dutch identifiers are caught; precision and recall are reported on every dry-run.

**Demo:** Run the evaluation set: per-type precision/recall in test-results/ JSON; the same name gets the same label in two files.

**Requires:** presidio, neo4j · Dutch recognisers, evaluation set

### T2 — Stable labels with global consistency ✅ DONE
**Done when:** the same input always gets the same label across uploads (Neo4j `LabelCounter`).

### T6 — Dutch identifier recognisers
**What:** Presidio pattern recognisers for BSN (with 11-proof), IBAN, postcode, KvK, licence plate.
**Done when:** each type is detected in the test set.

### T7 — Evaluation set and metrics
**First real document (2026-09-30):** a 46-page English master's thesis (PDF, plus a DOCX made from it).
Author, student number, supervisors and submission date are all removed from both outputs. Findings:
- Heavy over-masking by the English NER: capitalised terms become ORGANISATIE/PERSOON ("Bill of Materials",
  "Submission", "Second"), journal names and cited authors in the reference list too. Safe but hurts readability.
  Decided 2026-09-30: **published references stay readable.** The reference section (heading up to the next
  heading/appendix) and author-year citations ("(Yin, 2018)", "Eisenhardt (1989)") are not detected or replaced;
  appendices are. Thesis: 669 → 177 masked values. Eval case `cite-en` guards this.
- Over-masking of title-case words fixed 2026-09-30 (thesis: 177 → 59 masked values):
  - an NER guess whose every word also occurs in lowercase in the same document is a common word
    ("Submission", "Engineering", "Planning & Control"); emails/URLs don't count, and a word that is part of a
    detected full name stays a name ("Volgens Bakker" after "Jan Bakker"); rule-based results are never dropped;
  - abbreviations the document defines from common words ("Enterprise Resource Planning (ERP)"), technical
    terms like eBOM/mBOM, and respondent codes (R1–R11) stay readable;
  - surnames used on their own get the full name's label ("De Vries said" → PERSOON_3);
  - written-out dates in both languages are a pattern rule now ("12 May 2026" on a line without context was missed).
  Eval cases `title-words` and `nl-surname-words` guard this. Still masked on purpose: interviewee job titles
  (quasi-identifiers in a single-company case). Still over-masked: single title words that never occur in lowercase
  in the document ("Master", "Submission") and concepts like "Bill of Materials" when "bill" never does.
  Known trade-off: an organisation whose name is only common words ("Beter Wonen") is left readable unless a
  rule catches it ("Stichting Beter Wonen", "... BV").
- Text in images (the university logo) is not touched.
- Hyphenation at PDF line breaks: Docling joins the word, the file keeps the hyphen; reported as
  "not found in the file" (6 values in the thesis, none personal data).
- Docling needs ~6 s per page on CPU (OCR off): 4-5 minutes for the thesis.
- File names hold names too ("Thesis Eva Jansen - Voorbeeldbedrijf.pdf"). Decided 2026-09-30: output is
  `output/<name>_anon.pdf` (the original name, readable, by choice); non-PDF outputs in `output/<name>/`;
  entity maps (the keys) in `keys/`, apart from `output/` so that folder can be shared.
- Labels in PDFs: embedded font (the document's own when it has the glyphs, else Noto Sans), original size and colour;
  too wide → squeezed, then shrunk (floor 40 %). Short originals (citations "Yin, 2018", terms like "ETO") still get
  small labels: a 10-15 character label in the space of 2-4 characters.
**What:** 20 annotated documents (NL + EN) with expected entities; script that reports precision/recall per type.
**Done when:** metrics are reported per run and targets are agreed.

### T4 — Dry-run writes JSON results 🟡 IN PROGRESS
**What:** `tests/dry_run.py` writes `test-results/dry_run_YYYYMMDD_HHMMSS.json` with named steps.
**Done when:** the ResearchReady workbook shows UC10's dry-run.
**Status (2026-09-30):** JSON written (13 checks, incl. DOCX + PDF via Docling and a leftover-fragment check). Workbook part ⛔ until the server is back.

## Epic 3: Documents in, documents out

**Working software:** A DOCX or PDF goes in and the same format comes out, anonymised, with headings and tables intact.

**Demo:** Anonymise a DOCX with a table; open the result in Word.

**Requires:** docling, docconvert

### T3 — Restore Docling on CT107
**What:** bring CT107 back (shared with UC1); keep the plain-text fallback.
**Done when:** the dry-run's Docling step passes and layout-aware markdown is used again.

### T5 — Rebuild the document 🟡 IN PROGRESS
**What:** ~~replace spans in the Docling markdown and convert back with docconvert CT122 (DOCX) or render PDF.~~
Changed 2026-09-30: the entity map is applied to the **original file** (`/anonymize?document=true`), so docconvert is not needed.
DOCX: text replaced in the Word XML (body, tables, headers/footers, footnotes, comments, tracked changes, field codes,
hyperlinks); author/company properties and comment authors removed. PDF: text redacted (removed) with PyMuPDF and the
label written in its place; links with PII, comments, form fields, bookmarks, attachments, metadata and the
structure tree removed. The service reads the file back and returns no document if any original is still in it.
**Done when:** a DOCX in gives an anonymised DOCX out with headings and tables intact. ✅ DOCX and PDF (dry-run step 8).
**Still open:** test on real research documents; scanned PDFs are refused (no OCR redaction); a surname hyphenated
across a PDF line break is not matched (the read-back check does not catch that either); PyMuPDF is AGPL (fine for
internal use, decide before distributing).

## Epic 4: Audited and stored

**Working software:** Every document leaves a Langfuse trace with hashes only, and the output is stored encrypted and versioned.

**Demo:** Open the trace (no original values), the MinIO object and the Gitea commit.

**Requires:** langfuse, minio, gitea

### T8 — Langfuse audit trace
**Done when:** one trace per document with a span per entity (type, hash, label — never the original).

### T9 — Encrypted storage in MinIO
**Done when:** output and entity map stored in bucket `doc-anonymizer` with server-side encryption.

### T10 — Versioned output in Gitea
**Done when:** each anonymised document is committed with its entity-map hash.

## Epic 5: Researchers use it

**Working software:** Researchers anonymise files without curl, and interview transcripts keep speaker roles.

**Demo:** A researcher uploads a transcript and gets INTERVIEWER_1 / RESPONDENT_1 labels.

**Requires:** openwebui or n8n

### T11 — Upload entry point
**What:** a simple upload page, or an OpenWebUI tool / n8n webhook, for researchers.
**Done when:** a researcher can anonymise a file without curl.

### T12 — Role-aware labels (phase 2)
**What:** detect speaker turns in interview transcripts and emit INTERVIEWER_1 / RESPONDENT_1.
**Done when:** a transcript keeps who-said-what without names.

## Risks & blockers

| Risk / blocker | Impact | Mitigation |
|---|---|---|
| Missed PII | Personal data leaks into research output | T6 recognisers, T7 metrics, human spot checks |
| Entity map is itself personal data | Re-identification if leaked | Store encrypted (T9); access-restricted; never in Langfuse |
| Docling down | Layout lost | T3; fallback already in place |
| spaCy LG models need 2.5 GB RAM | OOM on CT140 | Keep RAM at 2.5 GB in the Ansible role |

## Open decisions

| # | Question | Options |
|---|----------|---------|
| 1 | Accuracy targets | e.g. recall ≥ 95 % for PERSON / ORG, ≥ 99 % for BSN / IBAN |
| 2 | Entry point for researchers | Upload page / OpenWebUI tool / n8n webhook |
| 3 | Entity-map retention | Keep per project / delete after export |

## Documentation & readiness

### D1 — Quarto book ✅ DONE
`docs/book/` created 2026-09-28 from the README and docs.

### D2 — Colour-coded workflow ✅ DONE
`docs/workflow.yml`.

### D3 — Complete plan ✅ DONE
This file.

### D4 — Expand the README
**Done when:** README explains the problem, pipeline, privacy design and how to run it (≥ 50 lines).

### D5 — Services and recovery runbooks
**Done when:** `docs/services.md` and `docs/recovery.md` exist.

### D6 — Example output
**Done when:** `example_outputs/` holds an anonymised sample and its (synthetic) entity map.

### D7 — Build the book in CI
**Done when:** `.gitea/workflows/render-book.yml` publishes `docs/book/` on push.
