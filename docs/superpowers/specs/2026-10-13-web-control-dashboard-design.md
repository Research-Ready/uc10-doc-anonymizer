# Spec — UC10 Document Anonymizer Web Control Dashboard & Documentation

**Date:** 2026-10-13  
**Status:** Approved by User  
**Goal:** Provide an interactive local web control dashboard on `http://localhost:5050` and an exhaustive project `README.md`.

---

## 1. Requirements

1. **The Process:** Visual representation of pipeline stages (Docling extraction -> Presidio NER -> Entity resolution -> In-place document redaction -> Verification). Live progress stream when "SAY GO" is executed.
2. **Docker Status:** Real-time status cards for all localstack containers (`uc10-anonymizer`, `docling`, `neo4j`). Button to auto-start containers if stopped.
3. **Inputs Management:** Direct drag-and-drop file upload to `input/`, list of waiting input files, inline editor for `input/targets.txt`.
4. **Sorted Outputs:** Table of generated files in `output/` sorted by date (newest first) or size, with direct downloads for anonymized files and entity maps (`keys/`), and an "Open in File Manager" button.
5. **README.md:** Exhaustive documentation covering architecture, privacy guarantees (100% offline local models), usage (Web UI, desktop launcher, CLI `go.sh`), targets configuration, and folder layout.

---

## 2. Architecture & Components

* **Dashboard Backend:** `scripts/web_dashboard.py` using FastAPI + Uvicorn on port 5050.
  - Endpoints:
    - `GET /`: Serves the single-page web UI.
    - `GET /api/status`: Returns health & container status for Docker containers (`uc10-anonymizer`, `docling`, `neo4j`).
    - `POST /api/containers/start`: Runs docker compose to start containers if down.
    - `GET /api/inputs`: Lists files in `input/` and contents of `input/targets.txt`.
    - `POST /api/upload`: Uploads files into `input/`.
    - `POST /api/targets`: Saves updated `input/targets.txt`.
    - `POST /api/inputs/delete`: Deletes an input file.
    - `GET /api/outputs`: Lists files in `output/` sorted by mtime, with metadata and entity counts.
    - `GET /api/download/output/{filename}`: Downloads an anonymized document.
    - `GET /api/download/key/{filename}`: Downloads the entity map JSON.
    - `POST /api/open-folder`: Opens `input/` or `output/` in the host file manager using `xdg-open`.
    - `POST /api/run`: Triggers the pipeline (`scripts/anonymize_folder.py`) with optional `--force`, streaming logs to the UI via Server-Sent Events (SSE).
* **Launcher & Desktop Integration:**
  - `scripts/web_dashboard.py` background runner or `./dashboard.sh`.
  - `~/Desktop/Open Anonymizer Web Dashboard.desktop`.
* **README.md:** Complete rewrite and expansion of `README.md`.
