# Professionalize UC10 Document Anonymizer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform UC10 Document Anonymizer into a professional, modular, production-grade application running through Docker with native Linux, Windows, and macOS support, 100% truthful verification, an ISO 27001 compliance report, a CI/CD build pipeline, and a web dashboard one-click update button.

**Architecture:** Decompose the 1,300-line monolithic `service/app.py` into focused, single-responsibility modules (`service/data/`, `service/recognizers/`, `service/processors/`, `service/formatters/`, and a slim `service/app.py` < 260 LOC). Containerize all components (Presidio, Docling, Neo4j, and the Web Dashboard) in unified Docker Compose configurations with cross-platform native launchers (`.sh`, `.ps1`, `.bat`).

**Tech Stack:** Python 3.10+, FastAPI, Presidio Analyzer, spaCy (Dutch `nl_core_news_lg` + English `en_core_web_lg`), PyMuPDF (fitz), Docling, Neo4j, Docker / Docker Compose, GitHub Actions.

**Spec:** User goal prompt, `CLAUDE.md`, and `PLAN.md`.

---

## Global Constraints

- **Absolute Veracity**: Zero False Completion. Never claim a feature, test, or container is working without real-world execution and evidence.
- **100% Offline / Local Execution**: No external cloud LLM dependencies. All PII processing stays on the local machine.
- **Cross-Platform Parity**: Full functionality on Linux (Fedora/Ubuntu), Windows 10/11 (PowerShell/WSL2), and macOS (Apple Silicon arm64 & Intel x86_64).
- **Separation of Keys**: Output documents (`output/`) and cryptographic entity mappings (`keys/`) must remain strictly isolated.

---

## Tasks

### Task 1: Refactor Monolithic `service/app.py` into Clean, Modular Subpackages ✅
- [x] Step 1: Write unit tests in `tests/test_modular_components.py` testing BSN 11-proof, TitledName recognizer, overlap dropping, and wordlists isolation.
- [x] Step 2: Extract data words into `service/data/wordlists.py`.
- [x] Step 3: Extract custom recognizers into `service/recognizers/dutch.py` including Dutch BSN 11-proof verification.
- [x] Step 4: Extract text processors into `service/processors/text.py`.
- [x] Step 5: Extract document formatters into `service/formatters/pdf.py`, `service/formatters/docx.py`, and `service/formatters/handler.py`.
- [x] Step 6: Extract Neo4j and memory registry into `service/storage/registry.py`.
- [x] Step 7: Refactor `service/app.py` to import from the new modules, reducing lines from ~1,300 to ~260.
- [x] Step 8: Run unit test suites and verify all tests pass (10/10 PASS).
- [x] Step 9: Run `python3 tests/eval_detection.py` and ensure 0 leaks / 0 false positives are preserved (0/44 leaks, 0 FP).
- [x] Step 10: Run `python3 tests/dry_run.py` (8/8 steps PASS).

---

### Task 2: Standardize Docker Compose Stack & Full Containerization ✅
- [x] Step 1: Add the Web Dashboard as a first-class service in `docker-compose.yml` (`uc10-dashboard` on port 5050).
- [x] Step 2: Update `docker-compose.yml` to mount `./service:/app:ro,z`.
- [x] Step 3: Create `scripts/Dockerfile.dashboard` for containerized dashboard execution.
- [x] Step 4: Verify compose configuration using `docker compose config`.

---

### Task 3: One-Click Web Dashboard Update Button ✅
- [x] Step 1: Write test for `/api/update` checking git status, version detection, and pull simulation (`tests/test_dashboard_update.py`).
- [x] Step 2: Implement `/api/update/status` and `/api/update/run` endpoints in `scripts/web_dashboard.py`.
- [x] Step 3: Add UI "Systeem & Versiebeheer" card in `scripts/static/index.html` with real-time status and "Nu Bijwerken (One-Click Update)" button.
- [x] Step 4: Run tests and verify `/api/update` passes (`tests/test_dashboard_update.py` 4/4 PASS).

---

### Task 4: ISO/IEC 27001 & ISO 27000-Family Information Security Compliance Audit ✅
- [x] Step 1: Conduct formal control mapping against ISO/IEC 27001:2022 Annex A (A.5.12, A.5.13, A.5.33, A.8.1, A.8.10, A.8.11, A.8.12, A.8.20, A.8.24, A.8.28) in `docs/compliance/ISO27001_COMPLIANCE.md`.
- [x] Step 2: Document cryptographic separation between `output/` (pseudonymized documents) and `keys/` (re-identification tables).
- [x] Step 3: Detail compliance gap analysis and practical operational safeguards for research institutions.

---

### Task 5: DevOps CI/CD Pipeline & Semantic Versioning ✅
- [x] Step 1: Create `.github/workflows/ci.yml` with multi-OS matrix testing (`ubuntu-latest`, `macos-latest`, `windows-latest`) across Python 3.10, 3.11, and 3.12.
- [x] Step 2: Create `.github/workflows/release.yml` for automated multi-architecture Docker image building (`linux/amd64`, `linux/arm64`) and semantic release packaging.
- [x] Step 3: Add `VERSION` (1.0.0) and `CHANGELOG.md` conforming to Keep a Changelog.

---

### Task 6: Cross-Platform Native Scripts & Comprehensive macOS/Linux/Windows Verification ✅
- [x] Step 1: Implement `tests/test_cross_platform.py` checking macOS path handling, line endings, script permissions, and environment portability (5/5 PASS).
- [x] Step 2: Update `install.sh`, `go.sh`, and `dashboard.sh` with robust macOS Homebrew/Docker Desktop discovery and POSIX compliance.
- [x] Step 3: Update `install.ps1` and `install.bat` with clear Windows execution policy bypass and Docker service verification.
- [x] Step 4: Rewrite `README.md` and `docs/installation.md` into lucid, human-readable instructions with copy-paste commands for Linux, macOS, and Windows.
- [x] Step 5: Run full test suite: 19 unit & platform tests pass, 0/44 leaks / 0 FP, dry-run 8/8 PASS.
