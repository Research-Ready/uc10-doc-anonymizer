# Requirements

<!-- Generated from docs/requirements.yml by ResearchReady/workbook/scripts/workflows.py --write-repos. Edit the YAML, not this file. -->

Live service status from the ResearchReady probe (2026-09-30T22:05). ✅ up / available · ⚠️ partial · ❔ not probed (internal only or no public route) · ❌ down / broken · ⏳ missing · ❓ open decision.

## Shared services

| Item | Status | Needed for | Note |
|---|---|---|---|
| presidio — anonymisation service (uc10-anonymizer, localstack :5010; CT140 when the server is back) | ❔ not probed | Epic 1 | CT140 |
| neo4j — global label registry | ❔ not probed | Epic 2 | CT114 · https://neo4j.research-ready.nl |
| docling — layout-aware parsing | ❔ not probed | Epic 3 | CT107 · https://docling.research-ready.nl |
| langfuse — audit trace (hashes only) | ❔ not probed | Epic 4 | CT112 · https://langfuse.research-ready.nl |
| minio — encrypted storage | ❔ not probed | Epic 4 | CT103 · https://minio.research-ready.nl |
| gitea — versioned output | ❔ not probed | Epic 4 | CT200 · https://gitea.research-ready.nl |
| openwebui — researcher entry point (tool) | ❔ not probed | Epic 5 | CT106 · https://openwebui.research-ready.nl |
| n8n — researcher entry point (webhook) | ❔ not probed | Epic 5 | CT104 · https://n8n.research-ready.nl |

## Tools & code

| Item | Status | Needed for | Note |
|---|---|---|---|
| Presidio FastAPI service (service/app.py) | ✅ available | Epic 1 |  |
| spaCy nl_core_news_lg + en_core_web_lg | ✅ available | Epic 1 |  |
| Identifiers of people: IBAN, student/employee number | ✅ available | Epic 2 |  |
| BSN recogniser (11-proof) | ⏳ missing | Epic 2 |  |
| Same-format output: DOCX XML rewrite, PDF redaction (PyMuPDF), read-back check | ✅ available | Epic 3 |  |
| Evaluation script (tests/eval_detection.py: leaks and false positives) | ✅ available | Epic 2 |  |
| Folder workflow (scripts/anonymize_folder.py: input/ → output/ + keys/) | ✅ available | Epic 5 |  |
| Dutch one-pager for users on local processing | ✅ available | Epic 5 |  |
| Network isolation of the pipeline containers (requested) | ⏳ missing | Epic 4 |  |

## Access & keys

| Item | Status | Needed for | Note |
|---|---|---|---|
| Neo4j password | ✅ available | Epic 2 |  |
| MinIO bucket doc-anonymizer with SSE | ⏳ missing | Epic 4 |  |
| Langfuse project keys for UC10 | ⏳ missing | Epic 4 |  |

## Data

| Item | Status | Needed for | Note |
|---|---|---|---|
| Sample text (tests/sample.txt) | ✅ available | Epic 1 |  |
| NL + EN evaluation set (11 texts; target 20 documents) | ⚠️ partial | Epic 2 |  |
| Sample PDF / DOCX with tables and headings (tests/interview.*, a real thesis) | ✅ available | Epic 3 |  |

## Decisions & external actions

| Item | Status | Needed for | Note |
|---|---|---|---|
| Scope: people and the target company only (decided 2026-10-01) | ✅ available | Epic 2 |  |
| Published references stay readable (decided 2026-09-30) | ✅ available | Epic 2 |  |
| Accuracy targets | ❓ open decision | Epic 2 |  |
| Researcher entry point beyond the folder: upload page / OpenWebUI tool / n8n | ❓ open decision | Epic 5 |  |
| Entity-map retention | ❓ open decision | Epic 4 |  |
