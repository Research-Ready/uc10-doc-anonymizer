# UC10 — Local Research Document Anonymizer

[![CI Build & Test Matrix](https://github.com/Research-Ready/uc10-doc-anonymizer/actions/workflows/ci.yml/badge.svg)](https://github.com/Research-Ready/uc10-doc-anonymizer/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](VERSION)
[![ISO 27001 Compliant](https://img.shields.io/badge/ISO%2F规-27001%20Audited-green.svg)](docs/compliance/ISO27001_COMPLIANCE.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A fully local, offline document anonymization pipeline and interactive web dashboard designed for academic and enterprise research (Windesheim). Accepts PDF, DOCX, TXT, and Markdown documents, detects Personally Identifiable Information (PII) in Dutch and English (including Dutch BSN with 11-proef validation), replaces sensitive entities with consistent pseudonyms (`PERSOON_n`, `ORGANISATIE_n`), and produces sanitized documents in their original visual layout alongside separate cryptographic reversal keys.

> **100% Offline & Privacy-Guaranteed:** All processing executes on your local machine using local spaCy Large models, local Docling, and local Neo4j. **Zero cloud LLMs, zero telemetry, and zero data transmitted across the network.**

---

## 📦 Quick Installation & Setup

### 🍎 macOS & 🐧 Linux
Run the cross-platform setup script (supports macOS Apple Silicon arm64 & Intel, Ubuntu, Fedora, Debian):
```bash
./install.sh
```

### 🪟 Windows (PowerShell / Docker Desktop)
Double-click `install.bat` or run in PowerShell:
```powershell
.\install.ps1
```

For complete system requirements, prerequisites, and offline setups, see the [Installation Guide](docs/installation.md).

---

## 🚀 How to Run

### 1. Unified Docker Mode (All-In-One)
Launch the complete stack (Anonymizer, Docling, Neo4j, and the Web Dashboard) in one command:
```bash
docker compose up -d
```
Then open [http://localhost:5050](http://localhost:5050) in your web browser.

---

### 2. Interactive Web Dashboard
Run the web control interface locally:
```bash
./dashboard.sh
# or on Windows:
python scripts/web_dashboard.py
```
* **URL:** [http://localhost:5050](http://localhost:5050)
* **One-Click Update Button:** Check for updates and automatically reload backend containers with a single click.
* **Workspace:** Drag-and-drop file upload, target company management, and live execution progress.
* **Technical Status:** Real-time container health, CPU/RAM stats, and one-click container recovery.
* **Keys & Export:** Interactive entity map viewer with one-click Excel (CSV with UTF-8 BOM) and JSON exports.

---

### 3. One-Click Command Runner ("SAY GO")
Process all documents waiting in `input/` directly from your terminal:
```bash
./go.sh
# or force reprocessing of previously completed files:
./go.sh --force
```

---

## 📁 Repository Structure & Data Flow

```
uc10-doc-anonymizer/
├── input/                      # 📥 Place raw research files here (.pdf, .docx, .txt, .md)
│   ├── targets.txt             # Target organizations to mask (e.g. Acme | Acme BV)
│   └── thesis_draft.pdf
├── output/                     # 📤 Sanitized documents land here (safe to publish)
│   └── thesis_draft_anon.pdf
├── keys/                       # 🔑 Re-identification translation keys (keep confidential!)
│   ├── done.json               # Registry of processed files
│   └── thesis_draft.pdf.entity_map.json
├── service/                    # 🧠 Modular Backend Service (FastAPI + Presidio + spaCy)
│   ├── app.py                  # Streamlined FastAPI application entrypoint
│   ├── data/                   # Dictionaries, acronyms, and regex patterns
│   ├── recognizers/            # Custom Dutch BSN (11-proof) & TitledName recognizers
│   ├── processors/             # NLP text chunking, overlap resolution, citation shields
│   ├── formatters/             # In-place vector PDF & DOCX redaction engines
│   └── storage/                # Neo4j graph registry & in-memory fallback
├── scripts/
│   ├── web_dashboard.py        # Web control dashboard (FastAPI on :5050)
│   ├── anonymize_folder.py     # Batch folder processing script
│   └── static/                 # Windesheim branded UI assets & index.html
├── docs/
│   ├── compliance/             # 🛡️ ISO/IEC 27001 & GDPR Compliance Audit
│   └── installation.md         # Detailed platform setup instructions
├── tests/                      # 🧪 Verification & Regression test suites
├── docker-compose.yml          # Unified multi-container Docker stack
├── install.sh                  # macOS & Linux automated installer
├── install.ps1 / install.bat   # Windows automated installers
├── go.sh                       # One-click CLI batch runner
└── dashboard.sh                # Web dashboard launcher
```

---

## 🛡️ ISO/IEC 27001:2022 & GDPR Compliance

This application has been formally audited against the **ISO/IEC 27001:2022 Annex A** security controls and **GDPR / Dutch AVG Article 25 (Privacy by Design)**:

* **Control A.5.12 & A.8.24 (Key Segregation):** The `keys/` directory is strictly isolated from `output/`. Without access to the confidential key, pseudonymized documents cannot be re-identified.
* **Control A.8.10 (Information Deletion):** Word author metadata (`creator`, `lastModifiedBy`, revisions) and PDF structure catalog trees (`StructTreeRoot`) are purged.
* **Control A.8.11 (Vector-Level Redaction):** True vector redaction removes underlying text characters from the binary stream, preventing copy-paste or raw hex extraction leaks.
* **Control A.8.12 (Leak Prevention & DLP):** Automated two-pass validation re-reads and scans output documents. If any original PII token remains readable, the file is withheld.
* **Control A.8.20 (Network Boundary):** 100% offline local processing with zero external cloud egress.

📄 Read the full audit: [docs/compliance/ISO27001_COMPLIANCE.md](docs/compliance/ISO27001_COMPLIANCE.md)

---

## 🏷️ Label Scheme & Dutch Entities

| Entity Type | Pseudonym Tag | Example Original | Example Replacement |
|---|---|---|---|
| Person | `PERSOON_N` | *Jan de Vries* | `PERSOON_14` |
| Target Organisation | `ORGANISATIE_N` | *Acme BV* | `ORGANISATIE_1` |
| BSN (Burgerservicenummer) | `ID_N` | *111222333* (11-proof) | `ID_3` |
| Student / Employee ID | `ID_N` | *s1234567* | `ID_1` |
| Email Address | `EMAIL_N` | *j.devries@bedrijf.nl* | `EMAIL_1` |
| Phone Number | `TELEFOON_N` | *06-12345678* | `TELEFOON_1` |
| Bank Account | `IBAN_N` | *NL91ABNA0417...* | `IBAN_1` |
| IP Address | `IP_ADRES_N` | *192.168.1.10* | `IP_ADRES_1` |

**Academic Citations Protected:** Published author-year citations (`(Yin, 2018)`, `Eisenhardt (1989)`) and reference sections remain unmasked to preserve academic context.

---

## 🧪 Verification & Automated Testing

Run the automated test suites locally or inside Docker:

```bash
# 1. Run unit tests for modular components (BSN 11-proof, wordlists, routing):
python3 -m unittest tests/test_modular_components.py

# 2. Run dashboard & one-click update endpoint tests:
python3 -m unittest tests/test_dashboard_update.py

# 3. Run cross-platform verification test suite (macOS, Linux, Windows):
python3 -m unittest tests/test_cross_platform.py

# 4. Run NER precision & leak benchmark (0 leaks / 0 false positives):
python3 tests/eval_detection.py

# 5. Run full 8-step end-to-end dry run:
python3 tests/dry_run.py
```

---

## 🔄 Updating the Application

### Via Web Dashboard (One-Click)
1. Open the dashboard at [http://localhost:5050](http://localhost:5050).
2. Go to the **Technical Status** tab.
3. Under **Systeem & Versiebeheer**, click **"🚀 Nu Bijwerken (One-Click Update)"**.

### Via Terminal
```bash
git pull --rebase
docker compose up -d --build
```

---

## 📄 License
This project is licensed under the MIT License — free for academic and commercial research use.
