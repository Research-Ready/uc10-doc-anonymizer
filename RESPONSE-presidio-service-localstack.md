# Response — UC10 Presidio service in the localstack

**From:** InstallLocalAiPackage (infra)
**Answers:** `InstallLocalAiPackage/REQUEST-uc10-presidio-service-localstack.md`

## Response — DONE (2026-09-30, laptop localstack)

**Port: `http://localhost:5010`** (compose service `uc10-anonymizer`, container `localstack-uc10-anonymizer-1`).

- `InstallLocalAiPackage/docker/localstack/Dockerfile.uc10-anonymizer`: python:3.12-slim, `service/requirements.txt`,
  `nl_core_news_lg` 3.7.0 + `en_core_web_lg` 3.7.1 baked in, runs as non-root `presidio`.
- Your `service/` is **not copied** into InstallLocalAiPackage. Compose builds straight from this repo through an additional build context
  (`${UC10_SERVICE_DIR:-../../../uc10-doc-anonymizer/service}`), which works on both the laptop and Fedora layouts.
  After changing `app.py`, rebuild (run in `InstallLocalAiPackage/docker/localstack/`):
  `docker compose -f docker-compose.yml -f docker-compose.laptop.yml up -d --build --no-deps uc10-anonymizer`
- `mem_limit: 3g` (uses ~1.7 GiB after startup), healthcheck `start_period: 120s` (it is healthy after ~20 s).
- Env: `DOCLING_URL=http://docling:5001`, `NEO4J_URI=bolt://neo4j:7687`, `NEO4J_PASSWORD` from `.env`. Langfuse not wired (app has no SDK calls yet).
- Stock `presidio-analyzer`/`presidio-anonymizer` on 5002/5003 left in place; compose comments now say they are the generic stock images.

Verified:
1. `/health` → `{"status":"ok","models":["nl","en"]}`
2. `POST /anonymize` with `tests/sample.txt` → `entity_count` 22, 22-entry `entity_map`, PERSOON_1..7, "Jan de Vries" gone; two runs give identical maps.
3. Neo4j `LabelCounter` nodes present (PERSON 7, DATE_TIME 4, LOCATION 3, ...).

## Fixed in `service/app.py` (2026-09-30, at the user's request)

Two bugs, found while verifying. Rebuilt and retested on :5010.

1. **Overlapping matches mangled the text.** Spans were only de-duplicated when identical, so a URL match inside an
   email, or a DATE_TIME `4567` inside a phone number, were all replaced. Before:
   `...via ENTITEIT_1onisch op DATUM_1_1` and `...via TELEFOON_1M_4`.
   Fix: `_drop_overlaps()` keeps one match per region, **longest first, then score**, so no part of a value stays readable.
2. **Different values shared a label.** Every type without a `_LABEL_PREFIX` entry becomes `ENTITEIT`, but the counter
   was per type, so URL, IN_PAN and US_BANK_NUMBER each issued `ENTITEIT_1`.
   Fix: `_counter_key()` gives unmapped types one shared `ENTITEIT` counter; mapped types keep their type name as the key,
   so the existing `LabelCounter` nodes on CT114 stay valid. A new counter starts after the highest `PREFIX_n` already issued
   (tested: existing `ENTITEIT_7` → next is `ENTITEIT_8`). Existing duplicate `ENTITEIT_n` labels on CT114 are not rewritten.

After (sample.txt): 14 entities, no shared labels, identical maps over 2 runs, no digit runs left:
```
PERSOON_4 woont in LOCATIE_1 en werkt bij PERSOON_1 beleidsmedewerker.
Hij is PERSOON_6 via EMAIL_1 of telefonisch op DATUM_2.
PERSOON_5 PERSOON_2 een afspraak gepland op DATUM_1.
De organisatie ENTITEIT_1 Hackers BV organiseert een conferentie in LOCATIE_2.
Voor meer ENTITEIT_2 kunt u contact opnemen met PERSOON_3 via TELEFOON_1.
```
`entity_count` for `sample.txt` is now **11** (was 22: overlapping fragments and false positives are gone). Update any dry-run expectation of 22.

**Detection quality: fixed, see the section below.**

**Shared Neo4j label.** Graphiti/Zep also writes `:Entity` nodes into CT114 (UC3 test data is in there). UC10's queries
match on `hash`, which Graphiti nodes lack, so nothing clashes today. A UC10-specific label (e.g. `:AnonEntity`) would be safer.

Also: the Ansible role `ansible/roles/presidio/` already exists (UC10's CLAUDE.md lists it as "Next"). Its
`en_core_web_lg` URL was bumped from 3.7.0 to 3.7.1 to match CT140 and the image.

## Docling fixed: PDF/DOCX now go through Docling (2026-09-30)

Every call was silently falling back to plain text. Three causes, all fixed:

1. **Localstack image was dead.** `ghcr.io/ds4sd/docling-serve:latest` is the old repo, frozen at 0.5.1 with only
   `/v1alpha/...` (so `/v1/convert/source` → 404). Now `ghcr.io/docling-project/docling-serve-cpu:v1.35.0`
   (InstallLocalAiPackage `docker/localstack/docker-compose.yml`). UC1 uses the same `/v1` endpoint and is fixed by this too.
2. **`service/app.py` used the wrong request/response shape.** Now `{"kind":"file","base64_string":...,"filename":...}`
   in and `document.md_content` out. An empty result counts as a failure (plain-text fallback plus a log line), and `.txt`
   files skip Docling because it does not accept them.
3. **PDF characters dropped.** Docling's default `docling_parse` backend lost every "p" in the test PDF
   ("afspraak gepland op" → "afs raak ge land o"); `pdftotext` reads the same file correctly. A dropped letter can hide a
   name from detection, so the app now asks for `pdf_backend: pypdfium2`.

Tested (DOCX/PDF made from `tests/sample.txt`): `.txt`, `.docx` and `.pdf` all anonymize with no fallback, and DOCX and PDF give
identical output. After the detection fixes below, `.txt`, `.docx` and `.pdf` all give the same 11 entities.

On the server: T3 (CT107) must run a docling-serve with the `/v1` API for this app code to work there.

## Detection quality fixed in `service/app.py` (2026-09-30)

Measured with the new `tests/eval_detection.py` (8 fictional NL/EN/mixed texts, 61 expected values; the 3 `h-` cases were written
after tuning and never tuned against):

| | Before | After |
|---|---|---|
| Leaked values | 5 of 37 (every organisation) | **1 of 61** (`Rabobank`, standalone) |
| False positives | 13 | **0** |

Changes:
1. **Organisations were never detected.** Presidio ignores `ORG` by default, and `_LABEL_PREFIX` used the key `ORG`
   where Presidio says `ORGANIZATION`, so ORGANISATIE_n never appeared. `ner_model_configuration` now keeps ORG.
2. **Per-line language routing** (`_analyze`, `_guess_language`): both models still run over the full text for context,
   but a result is kept only if its line is in that model's language (function-word count, document language as fallback).
   The English model on Dutch lines caused most false positives ("Hoe lang werkt", "Kunt", "Samenvatting" as PERSON).
3. **Entity allowlist** (`DETECTED_ENTITIES` = keys of `_LABEL_PREFIX`): no more US_SSN, IN_PAN, US_BANK_NUMBER, etc.
   New labels: `URL_n`, `IBAN_n`, `CREDITCARD_n`, `IP_ADRES_n` instead of ENTITEIT.
4. **Phone numbers:** `PhoneRecognizer` with NL/BE first plus Dutch context words (telefoon, bereikbaar, bel, ...).
   `06-12345678` was labelled DATUM.
5. **Rule-based recognizers:** organisations by legal form (`... BV/B.V./NV/VOF/Ltd/GmbH`) or institution word
   (`Stichting/Gemeente/Universiteit/Ministerie ...`), and names after a title (`mevrouw/dhr./de heer/dr./prof./Mr./Mrs.`).
   On an identical span a rule beats an NER guess (`_is_ner`).
6. **Plausibility filter** on NER guesses: names/orgs/places need a capital and 2+ characters (interview tag `I`), dates
   need a digit (`weekly`).

Known limits (for T6/T7):
- A bare organisation name that NER misses (`de Rabobank`) still leaks. A gazetteer of organisations, or a better NER model, would fix it.
  `tests/eval_detection.py` exits 1 on it on purpose.
- Some spans are too wide but still masked: `Anna de Wit van Heineken` becomes one PERSOON, and `Gemeente Utrecht` is now ORGANISATIE (was LOCATIE).
- Not in scope, still T6: BSN (11-proof), postcode, KvK, licence plates. NL IBAN is caught by Presidio's IBAN recognizer.
- `NRP` (nationality/religion/politics, GDPR special category) is not detected; decide in T7 if it should be.
- On CT114, URLs etc. that are already stored keep their old `ENTITEIT_n` labels; new ones get `URL_n` etc.

## Next steps for UC10

- Point `tests/dry_run.py` at `http://localhost:5010` and run the dry-run.
- Update the ⛔ line in `PLAN.md`: T4/T6/T7 are no longer blocked by the missing service.
- Update the dry-run: entity count is now 11, and check that the output has no leftover fragments (the old dry-run passed on mangled text).
- Add a `.docx`/`.pdf` sample to `tests/` and a dry-run step that fails when Docling falls back to plain text.
- Run `python3 tests/eval_detection.py` after every detection change; grow it into the T7 set.
- Review `service/app.py` and `tests/eval_detection.py`. Do not commit: no commits while the stack is fully local.
