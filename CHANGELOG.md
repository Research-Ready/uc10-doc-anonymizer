# Changelog

All notable changes to the **UC10 Document Anonymizer** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-31

### Added
- **Dutch BSN Recognition**: Added `BSNRecognizer` with official 11-proef modulo validation (`service/recognizers/dutch.py`).
- **Web Dashboard One-Click Update**: `/api/update/status` and `/api/update/run` with UI self-update button and container restart.
- **Docker Compose Web Dashboard**: Containerized `uc10-dashboard` serving the UI on port 5050.
- **ISO/IEC 27001 Compliance Audit**: Complete Annex A mapping and data protection control documentation (`docs/compliance/ISO27001_COMPLIANCE.md`).
- **DevOps CI/CD Pipelines**: Automated GitHub Actions workflows for multi-OS testing (Linux, Windows, macOS) and container release packaging (`.github/workflows/ci.yml`, `.github/workflows/release.yml`).
- **Cross-Platform Verification Suite**: `tests/test_cross_platform.py` and unit test suite for modular components (`tests/test_modular_components.py`).

### Changed
- **Architectural Refactoring**: Decomposed 1,300-line monolithic `service/app.py` into focused subpackages:
  - `service/data/wordlists.py`: Static dictionaries, acronyms, and regex patterns.
  - `service/recognizers/dutch.py`: Dutch BSN and TitledName recognizers.
  - `service/storage/registry.py`: Neo4j entity store with in-memory fallback.
  - `service/processors/text.py`: NLP chunking, language routing, overlap elimination, and citation protection.
  - `service/formatters/`: In-place DOCX (`docx.py`) and PDF (`pdf.py`) vector redaction.
- **Improved Launchers**: Updated `install.sh`, `install.ps1`, `install.bat`, `go.sh`, and `dashboard.sh` with robust cross-platform detection for macOS (Apple Silicon arm64 & Intel), Linux, and Windows.

### Security
- Complete offline data boundary: Zero external cloud API calls or telemetry.
- Cryptographic isolation of re-identification keys (`keys/`) from anonymized deliverables (`output/`).
