# UC10 Document Anonymizer — Standalone Packaging & Cross-Platform Installer Spec

## Overview
Transform `uc10-doc-anonymizer` into a completely self-contained, distributable package that can be installed and executed seamlessly on macOS and Linux (with optional Windows support) without depending on external repositories or hardcoded machine paths.

## Requirements

### 1. Standalone Docker Stack
- `service/Dockerfile`:
  - Python 3.12-slim base image.
  - Downloads and pre-bakes `nl_core_news_lg-3.7.0` and `en_core_web_lg-3.7.1` wheels during build so runtime does not require internet or root.
  - Installs dependencies from `service/requirements.txt`.
  - Copies `service/app.py`.
  - Runs as non-root user `presidio` on port 5002 (mapped to 5010 on host).
- `docker-compose.yml` (in repo root):
  - Service `uc10-anonymizer`: builds `./service`, exposes `5010:5002`, memory limit 3g, depends on `docling` and `neo4j`.
  - Service `docling`: `ghcr.io/docling-project/docling-serve-cpu:v1.35.0`, exposes `5001:5001`.
  - Service `neo4j`: `neo4j:5-community`, APOC plugin enabled, exposes `7474:7474` and `127.0.0.1:7687:7687`, data volume `neo4j_data`.
- `.env.example`:
  - `NEO4J_PASSWORD=ChangeMeWithSecurePassword123`
  - `LOCALSTACK_BIND=0.0.0.0`

### 2. Path Decoupling
- Eliminate hardcoded paths (e.g. `/home/chris/...`) across:
  - `scripts/web_dashboard.py` (use `REPO_DIR / "docker-compose.yml"`)
  - `dashboard.sh` (use `$SCRIPT_DIR/docker-compose.yml`)
  - `go.sh` (use `$SCRIPT_DIR/docker-compose.yml`)
- Support macOS open (`open`) alongside Linux (`xdg-open`).

### 3. Installation Scripts
- `install.sh` (macOS + Linux):
  - Checks for `docker` and `docker compose`.
  - Checks for `python3` (>= 3.10) and installs pip requirements for the web dashboard (`fastapi`, `uvicorn`, `httpx`).
  - Generates `.env` with a cryptographic random Neo4j password if not existing.
  - Prepares directory structure (`input/`, `output/`, `keys/`).
  - Pre-pulls and builds Docker images.
  - Sets execution permissions (`chmod +x *.sh scripts/*.sh scripts/*.py`).
  - Verifies container health and reports readiness.
- `install.ps1` & `install.bat` (Windows):
  - PowerShell installer checking Docker Desktop and Python on Windows.

### 4. Verification
- `docker compose config` validates the root compose file.
- `docker compose build uc10-anonymizer` successfully builds.
- Running `./go.sh` and `./dashboard.sh` starts and connects without error.
- All dry-run tests in `tests/dry_run.py` pass.
