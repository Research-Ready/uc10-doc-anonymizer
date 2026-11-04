# Standalone Installer and Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package `uc10-doc-anonymizer` with a standalone Docker Compose configuration and cross-platform automated installer scripts for macOS, Linux, and Windows.

**Architecture:** Create a root `docker-compose.yml` and `service/Dockerfile` so the repository builds and runs independently. Decouple hardcoded directory paths in Python scripts and shell launchers. Provide unified `install.sh` and `install.ps1`/`install.bat` scripts that check dependencies, generate secure `.env`, build local containers, and verify end-to-end service readiness.

**Tech Stack:** Docker, Docker Compose, Python 3 (FastAPI, Uvicorn, httpx), Bash / POSIX shell, PowerShell.

**Spec:** `docs/superpowers/specs/2026-10-13-standalone-installer-and-bundling-spec.md`

## Global Constraints
- Zero reliance on external repositories (e.g. `InstallLocalAiPackage`) for standalone operation.
- Backward compatibility: keep working if invoked from existing localstack configurations.
- Cross-platform: Support macOS (`open`), Linux (`xdg-open`), and Windows.
- Keep all personal data completely local; no cloud API calls.

## Review Focus
1. Docker daemon not running when installer executes -> Must display clear, actionable guidance instead of crashing.
2. Missing Docker or Docker Compose -> Must explain how to install Docker Desktop / Docker CE.
3. Missing `.env` / unconfigured Neo4j credentials -> Installer must auto-generate a strong random password so zero manual setup is required.
4. macOS vs Linux shell differences -> Must use POSIX-compliant bash syntax and auto-detect `open` vs `xdg-open`.
5. Port conflicts (e.g. port 5010, 5001, or 7687 already in use) -> Installer must check and warn.

---

### Task 1: Standalone Docker Configuration
**Files:**
- Create: `service/Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] Step 1.1: Write `service/Dockerfile` with Python 3.12-slim, baked spaCy LG wheels (`nl_core_news_lg` 3.7.0 and `en_core_web_lg` 3.7.1), dependencies from `requirements.txt`, and non-root `presidio` user.
- [ ] Step 1.2: Write root `docker-compose.yml` declaring `uc10-anonymizer`, `docling`, and `neo4j`.
- [ ] Step 1.3: Write `.env.example` with template environment variables.
- [ ] Step 1.4: Verify compose file syntax with `docker compose config`.

### Task 2: Decouple Hardcoded Paths in Existing Scripts
**Files:**
- Modify: `scripts/web_dashboard.py`
- Modify: `dashboard.sh`
- Modify: `go.sh`

- [ ] Step 2.1: Update `scripts/web_dashboard.py` to resolve `docker-compose.yml` relative to `REPO_DIR`, with graceful fallback to `InstallLocalAiPackage` if present.
- [ ] Step 2.2: Update `dashboard.sh` to use `$SCRIPT_DIR` for compose execution, and detect macOS `open` vs Linux `xdg-open`.
- [ ] Step 2.3: Update `go.sh` to use `$SCRIPT_DIR` for compose execution, and detect macOS `open` vs Linux `xdg-open`.
- [ ] Step 2.4: Verify `python3 -m py_compile scripts/web_dashboard.py` passes and bash syntax checks pass (`bash -n go.sh`, `bash -n dashboard.sh`).

### Task 3: Cross-Platform Installer Scripts
**Files:**
- Create: `install.sh`
- Create: `install.ps1`
- Create: `install.bat`

- [ ] Step 3.1: Write `install.sh` for macOS and Linux (Docker checks, Python checks, `.env` auto-generation with random password, folder creation, container pull/build, and permissions).
- [ ] Step 3.2: Write `install.ps1` and `install.bat` for Windows users with Docker Desktop.
- [ ] Step 3.3: Set executable permissions on all shell scripts (`chmod +x install.sh go.sh dashboard.sh scripts/*.sh`).
- [ ] Step 3.4: Test `install.sh --dry-run` or test execution of checks.

### Task 4: Documentation and Final Verification
**Files:**
- Create: `docs/installation.md`
- Modify: `README.md`

- [ ] Step 4.1: Write comprehensive installation and quick-start instructions in `docs/installation.md` (macOS, Linux, Windows).
- [ ] Step 4.2: Update `README.md` with the new one-line installation guide (`./install.sh`).
- [ ] Step 4.3: Verify test suites (`tests/dry_run.py` and `tests/eval_detection.py`) against the running services.
