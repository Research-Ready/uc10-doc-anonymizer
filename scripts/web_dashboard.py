#!/usr/bin/env python3
"""UC10 Document Anonymizer — Windesheim Research Control Dashboard.

Serves an interactive web control interface on http://localhost:5050.
Features Windesheim branding, academic tabbed interface, real-time status detection,
interactive human-readable entity keys modal, and Excel/CSV export.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

REPO_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_HTML_PATH = STATIC_DIR / "index.html"
INPUT_DIR = REPO_DIR / "input"
OUTPUT_DIR = REPO_DIR / "output"
KEYS_DIR = REPO_DIR / "keys"
TARGETS_FILE = INPUT_DIR / "targets.txt"
LOCAL_COMPOSE = REPO_DIR / "docker-compose.yml"
LEGACY_COMPOSE = Path("/home/chris/Nextcloud/Github/InstallLocalAiPackage/docker/localstack")


def open_in_file_manager(path: Path):
    """Open folder in OS file manager across macOS, Linux, and Windows."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform.startswith("win"):
            os.startfile(str(path))
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:
        print(f"Could not open folder {path}: {exc}")


app = FastAPI(title="Windesheim Document Anonymizer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_EXTS = {".pdf", ".docx", ".txt", ".md"}
IS_PROCESSING = False


def label_to_type(label: str) -> str:
    """Translate label prefix to clear human-readable Dutch entity type."""
    if label.startswith("PERSOON"):
        return "Persoon"
    if label.startswith("ORGANISATIE"):
        return "Doelbedrijf / Organisatie"
    if label.startswith("EMAIL"):
        return "E-mailadres"
    if label.startswith("TELEFOON"):
        return "Telefoonnummer"
    if label.startswith("IBAN"):
        return "IBAN Bankrekening"
    if label.startswith("ID"):
        return "Student-/Medewerker-ID"
    if label.startswith("IP_ADRES"):
        return "IP-adres"
    if label.startswith("DATUM"):
        return "Datum"
    if label.startswith("LOCATIE"):
        return "Locatie"
    if label.startswith("URL"):
        return "Website / URL"
    return "Overige Entiteit"


ANONYMIZER_HEALTH_URL = os.getenv("ANONYMIZER_HEALTH_URL", "http://localhost:5010/health")
DOCLING_HEALTH_URL = os.getenv("DOCLING_HEALTH_URL", "http://localhost:5001/health")
NEO4J_HTTP_URL = os.getenv("NEO4J_HTTP_URL", "http://localhost:7474")


def get_version_info() -> dict[str, Any]:
    """Retrieve version and git tracking details."""
    version_file = REPO_DIR / "VERSION"
    version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "1.0.0"

    commit = "unknown"
    branch = "unknown"
    dirty = False
    try:
        p_c = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_DIR, capture_output=True, text=True, timeout=2,
        )
        if p_c.returncode == 0:
            commit = p_c.stdout.strip()
        p_b = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_DIR, capture_output=True, text=True, timeout=2,
        )
        if p_b.returncode == 0:
            branch = p_b.stdout.strip()
        p_s = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_DIR, capture_output=True, text=True, timeout=2,
        )
        if p_s.returncode == 0 and p_s.stdout.strip():
            dirty = True
    except Exception:
        pass

    return {
        "version": version,
        "commit": commit,
        "branch": branch,
        "dirty": dirty,
    }


def get_docker_status() -> dict[str, Any]:
    """Check status of containers and health endpoints with complete veracity."""
    services = {
        "anonymizer": {
            "name": "UC10 Anonymizer (Presidio + spaCy)",
            "port": 5010,
            "container": "uc10-anonymizer",
            "url": ANONYMIZER_HEALTH_URL,
            "status": "stopped",
            "critical": True,
            "detail": "Service niet bereikbaar",
        },
        "docling": {
            "name": "Docling Document Parser",
            "port": 5001,
            "container": "uc10-docling",
            "url": DOCLING_HEALTH_URL,
            "status": "stopped",
            "critical": False,
            "detail": "Service niet bereikbaar",
        },
        "neo4j": {
            "name": "Neo4j Entity Registry",
            "port": 7687,
            "container": "uc10-neo4j",
            "url": NEO4J_HTTP_URL,
            "status": "stopped",
            "critical": False,
            "detail": "Service niet bereikbaar",
        },
        "chainforge": {
            "name": "ChainForge LLM Evaluator",
            "port": 8000,
            "container": "Lokaal proces",
            "url": "http://127.0.0.1:8000",
            "status": "stopped",
            "critical": False,
            "detail": "Niet actief (startbaar via knop)",
        },
    }

    # Test HTTP health endpoints
    for key, svc in services.items():
        try:
            r = httpx.get(svc["url"], timeout=1.5)
            if r.status_code == 200:
                try:
                    data = r.json()
                    if key == "anonymizer":
                        backend_services = data.get("services", {})
                        if data.get("status") == "degraded":
                            svc["status"] = "degraded"
                            degraded_parts = [f"{s}: {st}" for s, st in backend_services.items() if st != "connected"]
                            svc["detail"] = f"Gedegradeerd ({', '.join(degraded_parts) if degraded_parts else 'status degraded'})"
                        else:
                            svc["status"] = "healthy"
                            svc["detail"] = f"spaCy: {', '.join(data.get('models', []))} | Neo4j: {backend_services.get('neo4j', 'ok')}"
                    elif key == "neo4j":
                        svc["status"] = "healthy"
                        svc["detail"] = f"Bolt 7687 / HTTP 7474 (Cluster {data.get('neo4j_version', '5.x')})"
                    elif key == "chainforge":
                        svc["status"] = "healthy"
                        svc["detail"] = "Prompt & Model Evaluatie Actief (poort 8000)"
                    else:
                        svc["status"] = "healthy"
                        svc["detail"] = "HTTP 200 OK"
                except Exception:
                    if key == "chainforge":
                        svc["status"] = "stopped"
                        svc["detail"] = "Niet actief (startbaar via knop)"
                    else:
                        svc["status"] = "healthy"
                        svc["detail"] = "HTTP 200 OK"
            else:
                if key == "chainforge":
                    svc["status"] = "stopped"
                    svc["detail"] = "Niet actief (startbaar via knop)"
                else:
                    svc["status"] = "degraded"
                    svc["detail"] = f"HTTP {r.status_code}"
        except Exception:
            svc["status"] = "stopped"
            svc["detail"] = "Niet actief (startbaar via knop)" if key == "chainforge" else "Service verbinding mislukt"

    # Query docker ps to get real container state
    try:
        proc = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True, timeout=3,
        )
        if proc.returncode == 0:
            lines = proc.stdout.strip().splitlines()
            for line in lines:
                parts = line.split("\t")
                if not parts:
                    continue
                c_name = parts[0]
                c_status = parts[1] if len(parts) > 1 else ""
                for svc in services.values():
                    if svc["container"] == c_name or svc["container"] in c_name or c_name in svc["container"]:
                        svc["docker_status"] = c_status
    except Exception:
        pass

    for svc in services.values():
        if "docker_status" not in svc:
            if svc["container"] == "Lokaal proces":
                svc["docker_status"] = "Niet actief"
            elif svc.get("status") == "healthy":
                svc["docker_status"] = "Actief"  # no docker CLI here (e.g. inside the dashboard container)
            else:
                svc["docker_status"] = "Niet gestart (offline)"

    global IS_PROCESSING
    anon_ok = services["anonymizer"]["status"] == "healthy"
    docling_ok = services["docling"]["status"] == "healthy"
    neo4j_ok = services["neo4j"]["status"] == "healthy"

    if IS_PROCESSING:
        overall = "orange"
        overall_label = "Documenten Verwerken..."
        overall_desc = "De pijplijn is actief bezig met anonimiseren."
    elif not anon_ok:
        overall = "red"
        overall_label = "Kritieke Service Offline"
        overall_desc = "De UC10 Anonymizer engine (poort 5010) reageert niet."
    elif not docling_ok or not neo4j_ok:
        overall = "yellow"
        overall_label = "Actief (Fallback Modus)"
        missing = []
        if not docling_ok: missing.append("Docling (platgetekste fallback)")
        if not neo4j_ok: missing.append("Neo4j (in-memory register)")
        overall_desc = f"Operationeel met fallback: {', '.join(missing)}."
    else:
        overall = "green"
        overall_label = "Alle Systemen Operationeel"
        overall_desc = "Docling, spaCy NL/EN en Neo4j register zijn gezond."

    return {
        "services": services,
        "overall": overall,
        "overall_label": overall_label,
        "overall_desc": overall_desc,
    }


@app.get("/api/status")
async def api_status():
    status_data = get_docker_status()
    return {
        **status_data,
        "input_count": len(list_input_files()),
        "output_count": len(list_output_files()),
    }


@app.post("/api/containers/start")
async def api_start_containers():
    if LOCAL_COMPOSE.exists():
        compose_file = LOCAL_COMPOSE
        work_dir = REPO_DIR
        services_args = []
    elif LEGACY_COMPOSE.exists():
        compose_file = LEGACY_COMPOSE / "docker-compose.yml"
        work_dir = LEGACY_COMPOSE
        services_args = ["neo4j", "docling", "uc10-anonymizer"]
    else:
        raise HTTPException(status_code=500, detail="Geen docker-compose.yml gevonden in projectmap")

    try:
        cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d"] + services_args
        proc = subprocess.run(
            cmd,
            cwd=work_dir, capture_output=True, text=True, timeout=40,
        )
        return {"success": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/chainforge/start")
async def api_start_chainforge():
    """Start or verify ChainForge serve on port 8000."""
    try:
        r = httpx.get("http://127.0.0.1:8000", timeout=1.0)
        if r.status_code == 200:
            return {"status": "running", "url": "http://localhost:8000"}
    except Exception:
        pass

    chainforge_bin = shutil.which("chainforge") or str(Path.home() / ".local" / "bin" / "chainforge")
    if not Path(chainforge_bin).exists() and not shutil.which("chainforge"):
        raise HTTPException(status_code=404, detail="ChainForge binary niet gevonden in PATH of ~/.local/bin")

    cmd = [chainforge_bin, "serve", "--port", "8000", "--host", "127.0.0.1"]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Kon ChainForge niet starten: {exc}")

    for _ in range(12):
        await asyncio.sleep(0.5)
        try:
            r = httpx.get("http://127.0.0.1:8000", timeout=0.5)
            if r.status_code == 200:
                return {"status": "started", "url": "http://localhost:8000"}
        except Exception:
            pass

    return {"status": "started", "url": "http://localhost:8000"}


@app.get("/api/docker-logs/{service}")
async def api_get_docker_logs(service: str):
    container_map = {
        "anonymizer": ["uc10-anonymizer", "localstack-uc10-anonymizer-1"],
        "docling": ["uc10-docling", "localstack-docling-1"],
        "neo4j": ["uc10-neo4j", "localstack-neo4j-1"],
    }
    candidates = container_map.get(service)
    if not candidates:
        raise HTTPException(status_code=400, detail="Onbekende service")
    c_name = candidates[0]
    for c in candidates:
        check = subprocess.run(["docker", "inspect", c], capture_output=True, text=True)
        if check.returncode == 0:
            c_name = c
            break
    try:
        proc = subprocess.run(
            ["docker", "logs", "--tail", "120", c_name],
            capture_output=True, text=True, timeout=5,
        )
        return {"service": service, "container": c_name, "logs": proc.stdout + proc.stderr}
    except Exception as exc:
        return {"service": service, "container": c_name, "logs": f"Fout bij ophalen logs: {exc}"}


def list_input_files() -> list[dict[str, Any]]:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for p in INPUT_DIR.iterdir():
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS and p.name not in ("README.md", "targets.txt"):
            st = p.stat()
            warning = None
            if st.st_size == 0:
                warning = "Leeg bestand (0 bytes)"
            elif st.st_size > 100 * 1024 * 1024:
                warning = "Groot bestand (>100MB)"

            files.append({
                "name": p.name,
                "size": st.st_size,
                "size_human": f"{st.st_size / 1024:.1f} KB" if st.st_size < 1024*1024 else f"{st.st_size / (1024*1024):.2f} MB",
                "mtime": st.st_mtime,
                "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "extension": p.suffix.lower(),
                "warning": warning,
            })
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files


def list_output_files() -> list[dict[str, Any]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    done_file = KEYS_DIR / "done.json"
    done_map = {}
    if done_file.exists():
        try:
            done_map = json.loads(done_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    items = []
    for p in OUTPUT_DIR.iterdir():
        if p.name == "README.md":
            continue
        if p.is_file():
            st = p.stat()
            entity_count = None
            key_name = None
            for orig, rel_out in done_map.items():
                if Path(rel_out).name == p.name or rel_out == p.name:
                    k_file = KEYS_DIR / f"{orig}.entity_map.json"
                    if k_file.exists():
                        key_name = k_file.name
                        try:
                            m = json.loads(k_file.read_text(encoding="utf-8"))
                            entity_count = len(m)
                        except Exception:
                            pass
                    break

            items.append({
                "name": p.name,
                "is_dir": False,
                "size": st.st_size,
                "size_human": f"{st.st_size / 1024:.1f} KB" if st.st_size < 1024*1024 else f"{st.st_size / (1024*1024):.2f} MB",
                "mtime": st.st_mtime,
                "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "entity_count": entity_count,
                "key_file": key_name,
                "extension": p.suffix.lower(),
            })
        elif p.is_dir():
            st = p.stat()
            sub_files = [sf for sf in p.iterdir() if sf.is_file()]
            total_size = sum(sf.stat().st_size for sf in sub_files)
            items.append({
                "name": p.name,
                "is_dir": True,
                "size": total_size,
                "size_human": f"{total_size / 1024:.1f} KB" if total_size < 1024*1024 else f"{total_size / (1024*1024):.2f} MB",
                "mtime": st.st_mtime,
                "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "sub_files": [sf.name for sf in sub_files],
                "entity_count": None,
                "key_file": None,
                "extension": "folder",
            })

    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


@app.get("/api/inputs")
async def api_get_inputs():
    targets = ""
    if TARGETS_FILE.exists():
        raw = TARGETS_FILE.read_text(encoding="utf-8")
        clean_lines = [
            line.strip() for line in raw.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        targets = "\n".join(clean_lines)
    return {
        "files": list_input_files(),
        "targets": targets,
    }


@app.post("/api/upload")
async def api_upload(files: list[UploadFile] = File(...)):
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    uploaded = []
    errors = []
    for f in files:
        if not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext not in SUPPORTED_EXTS:
            errors.append(f"{f.filename}: niet-ondersteund formaat (alleen {', '.join(sorted(SUPPORTED_EXTS))})")
            continue
        dest = INPUT_DIR / Path(f.filename).name
        content = await f.read()
        if len(content) == 0:
            errors.append(f"{f.filename}: bestand is leeg (0 bytes)")
            continue
        dest.write_bytes(content)
        uploaded.append(dest.name)
    return {"uploaded": uploaded, "errors": errors}


@app.post("/api/targets")
async def api_save_targets(targets: str = Form(...)):
    header = (
        "# Target company: the organisation the research was for. One company per line; other names of the\n"
        "# same company after '|', e.g.: Acme | Acme BV | acme.nl\n"
        "# Masked everywhere, also in citations, references, URLs and file names. This file is kept out of git.\n"
    )
    clean_targets = header + targets.strip() + "\n"
    TARGETS_FILE.write_text(clean_targets, encoding="utf-8")
    return {"saved": True}


@app.post("/api/inputs/delete")
async def api_delete_input(filename: str = Form(...)):
    path = INPUT_DIR / Path(filename).name
    if path.exists() and path.is_file() and path.name not in ("README.md", "targets.txt"):
        path.unlink()
        return {"deleted": filename}
    raise HTTPException(status_code=404, detail="Bestand niet gevonden")


@app.get("/api/outputs")
async def api_get_outputs():
    return {"files": list_output_files()}


@app.get("/api/download/output/{filename:path}")
async def api_download_output(filename: str):
    path = (OUTPUT_DIR / filename).resolve()
    if not str(path).startswith(str(OUTPUT_DIR.resolve())) or not path.exists():
        raise HTTPException(status_code=404, detail="Bestand niet gevonden")
    return FileResponse(path, filename=path.name)


@app.get("/api/download/key/{filename:path}")
async def api_download_key(filename: str):
    path = (KEYS_DIR / filename).resolve()
    if not str(path).startswith(str(KEYS_DIR.resolve())) or not path.exists():
        raise HTTPException(status_code=404, detail="Sleutelbestand niet gevonden")
    return FileResponse(path, filename=path.name)


@app.get("/api/key-data/{filename:path}")
async def api_key_data(filename: str):
    """Return parsed human-readable entity mapping entries."""
    path = (KEYS_DIR / filename).resolve()
    if not str(path).startswith(str(KEYS_DIR.resolve())) or not path.exists():
        raise HTTPException(status_code=404, detail="Sleutelbestand niet gevonden")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fout bij lezen sleutel: {exc}")

    entries = []
    for orig, lbl in data.items():
        entries.append({
            "original": orig,
            "label": lbl,
            "type": label_to_type(lbl),
        })

    def sort_key(item):
        parts = item["label"].split("_")
        if len(parts) == 2 and parts[1].isdigit():
            return (parts[0], int(parts[1]))
        return (item["label"], 0)

    entries.sort(key=sort_key)
    return {"filename": filename, "total": len(entries), "entries": entries}


@app.get("/api/download/key-csv/{filename:path}")
async def api_download_key_csv(filename: str):
    """Download entity mapping as clean UTF-8 CSV with BOM for Microsoft Excel."""
    path = (KEYS_DIR / filename).resolve()
    if not str(path).startswith(str(KEYS_DIR.resolve())) or not path.exists():
        raise HTTPException(status_code=404, detail="Sleutelbestand niet gevonden")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fout bij lezen sleutel: {exc}")

    csv_lines = ["\ufeffOriginele Naam / Waarde;Pseudoniem in Document;Soort Gegeven"]
    for orig, lbl in data.items():
        esc_orig = orig.replace('"', '""')
        esc_lbl = lbl.replace('"', '""')
        t = label_to_type(lbl)
        csv_lines.append(f'"{esc_orig}";"{esc_lbl}";"{t}"')

    csv_content = "\r\n".join(csv_lines)
    clean_base = filename.replace(".entity_map.json", "").replace(".json", "")
    csv_filename = f"Sleutel_{clean_base}.csv"

    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{csv_filename}"'},
    )


@app.post("/api/open-folder")
async def api_open_folder(folder: str = Form(...)):
    target = REPO_DIR / folder
    if target.exists() and folder in ("input", "output", "keys"):
        open_in_file_manager(target)
        return {"opened": folder}
    raise HTTPException(status_code=400, detail="Ongeldige map")


@app.get("/api/logo")
async def api_logo():
    logo_path = STATIC_DIR / "windesheim-logo.png"
    if logo_path.exists():
        return FileResponse(logo_path, media_type="image/png")
    alt = Path("/home/chris/Nextcloud/Github/ResearchReady/Actieonderzoek/Template/img/windesheimlogo.png")
    if alt.exists():
        return FileResponse(alt, media_type="image/png")
    raise HTTPException(status_code=404, detail="Logo niet gevonden")


@app.get("/api/run-stream")
async def api_run_stream(force: bool = False):
    """Run anonymize_folder.py and stream output via SSE."""
    global IS_PROCESSING
    IS_PROCESSING = True

    async def event_generator():
        global IS_PROCESSING
        try:
            cmd = ["python3", "-u", str(REPO_DIR / "scripts" / "anonymize_folder.py")]
            if force:
                cmd.append("--force")

            yield f"data: {json.dumps({'type': 'start', 'message': 'Anonimisering gestart...'})}\n\n"
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=REPO_DIR,
            )

            failed_files = []
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip()
                if "FAIL" in text or "WARN" in text:
                    failed_files.append(text)
                yield f"data: {json.dumps({'type': 'log', 'text': text})}\n\n"

            rc = await proc.wait()
            yield f"data: {json.dumps({'type': 'finish', 'code': rc, 'success': (rc == 0 and len(failed_files) == 0), 'failures': failed_files})}\n\n"
        finally:
            IS_PROCESSING = False

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/update/status")
async def api_update_status():
    """Check current version, git tracking, and update readiness."""
    info = get_version_info()
    can_pull = False
    details = "Lokale versie actief (offline mode)"

    try:
        p_r = subprocess.run(
            ["git", "remote"],
            cwd=REPO_DIR, capture_output=True, text=True, timeout=2,
        )
        if p_r.returncode == 0 and "origin" in p_r.stdout:
            can_pull = True
            details = "Verbonden met Git origin repository"
    except Exception as exc:
        details = f"Geen git integratie beschikbaar: {exc}"

    return {
        **info,
        "can_pull": can_pull,
        "status_message": details,
    }


@app.post("/api/update/run")
async def api_update_run():
    """Trigger one-click self-update: pulls latest git changes and restarts docker containers."""
    logs = []
    success = True

    try:
        logs.append("Stap 1: Controleren van updates in Git repository...")
        p_pull = subprocess.run(
            ["git", "pull", "--rebase"],
            cwd=REPO_DIR, capture_output=True, text=True, timeout=15,
        )
        if p_pull.returncode == 0:
            logs.append(f"Git: {p_pull.stdout.strip() or 'Reeds up-to-date.'}")
        else:
            err_msg = (p_pull.stderr or p_pull.stdout).strip()
            logs.append(f"Git melding (lokaal/offline): {err_msg}")

        logs.append("Stap 2: Herstarten en verifiëren van Docker containers...")
        p_up = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=REPO_DIR, capture_output=True, text=True, timeout=30,
        )
        if p_up.returncode == 0:
            logs.append("Docker: Containers herladen.")
        else:
            logs.append(f"Docker waarschuwing: {p_up.stderr.strip()}")

        logs.append("Stap 3: Testen van health endpoint...")
        await asyncio.sleep(2)
        async with httpx.AsyncClient(timeout=4.0) as client:
            try:
                r = await client.get(ANONYMIZER_HEALTH_URL)
                if r.status_code == 200:
                    logs.append("✓ UC10 Anonymizer service is operationeel (HTTP 200).")
                else:
                    logs.append(f"Waarschuwing: health endpoint gaf HTTP {r.status_code}")
            except Exception as exc:
                logs.append(f"Healthcheck melding: {exc}")

    except Exception as exc:
        success = False
        logs.append(f"Fout tijdens bijwerken: {exc}")

    return {
        "success": success,
        "logs": logs,
        "version_info": get_version_info(),
    }


def get_dashboard_html() -> str:
    if INDEX_HTML_PATH.exists():
        return INDEX_HTML_PATH.read_text(encoding="utf-8")
    return "<!DOCTYPE html><html><body><h1>Fout: scripts/static/index.html niet gevonden</h1></body></html>"


HTML_DASHBOARD = get_dashboard_html()


@app.get("/", response_class=HTMLResponse)
async def dashboard_index():
    return HTMLResponse(content=get_dashboard_html())


def main():
    print("=================================================================")
    print(" Windesheim Document Anonymizer — Web Control Dashboard          ")
    print(" URL: http://localhost:5050                                      ")
    print(" 100% Local models (spaCy + Docling) — Zero Cloud API Calls      ")
    print("=================================================================")
    # Native runs stay loopback-only; the container sets DASHBOARD_HOST=0.0.0.0 so the port mapping works.
    uvicorn.run(app, host=os.getenv("DASHBOARD_HOST", "127.0.0.1"), port=5050, log_level="info")


if __name__ == "__main__":
    main()
