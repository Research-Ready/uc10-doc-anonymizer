"""UC10 dry-run test — prints PASS/FAIL per step, writes test-results/ JSON, exits 1 on any failure."""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import httpx

DOCLING_URL = os.getenv("DOCLING_URL", "http://localhost:5001")
SERVICE_URL = os.getenv("SERVICE_URL", "http://localhost:5010")

TESTS = Path(__file__).resolve().parent
RESULTS_DIR = TESTS.parent / "test-results"
SAMPLE_TEXT = "Jan de Vries woont in Amsterdam. Bel hem op 06-12345678."

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

# Every person-identifying value in tests/interview.md, plus the target company (passed as target);
# none may be readable in the anonymized DOCX/PDF. Independent of the service's entity map, so it also
# catches values detection missed. Places and dates are out of scope and stay readable.
INTERVIEW_TARGETS = ["ValueChain Hackers BV"]
INTERVIEW_PII = ["Jan", "Vries", "devries", "12345678", "Fatima", "El-Amin", "Pieter", "Janssen", "123 4567",
                 "Sanne", "Bakker", "ValueChain", "Hackers"]

# A label with text glued on, left by overlapping replacements: DATUM_1_1, ENTITEIT_1onisch.
_GLUED_LABEL = re.compile(r"\b[A-Z_]+_\d+(?=[A-Za-z_])")

steps: list[dict] = []


def check(step: int, label: str, ok: bool, detail: str = "") -> None:
    tag = PASS if ok else FAIL
    suffix = f"  ({detail})" if detail else ""
    print(f"  Step {step}: {tag}  {label}{suffix}")
    steps.append({"step": step, "name": label, "passed": ok, "detail": detail})


def load_input(path: Path | None) -> tuple[bytes, str]:
    if path and path.exists():
        return path.read_bytes(), path.name
    fallback = TESTS / "sample.txt"
    if fallback.exists():
        return fallback.read_bytes(), fallback.name
    return SAMPLE_TEXT.encode(), "inline.txt"


def anonymize(content: bytes, filename: str) -> dict:
    r = httpx.post(f"{SERVICE_URL}/anonymize", files={"file": (filename, content)},
                   params={"project_id": "dry-run"}, timeout=300)
    r.raise_for_status()
    return r.json()


def check_clean(step: int, name: str, result: dict) -> None:
    """No original value readable and no half-replaced labels in the output."""
    text = result.get("anonymized_text", "")
    leaked = [orig for orig in result.get("entity_map", {}) if orig in text]
    glued = _GLUED_LABEL.findall(text)
    detail = f"leaked={leaked} glued={glued}" if leaked or glued else f"{result.get('entity_count', 0)} entities"
    check(step, f"{name}: no originals or fragments left", not leaked and not glued, detail)


def check_document(step: int, path: Path, expected_map: dict) -> None:
    """A DOCX/PDF goes through Docling (no fallback) and gives the same entities as the plain text."""
    name = path.suffix.lstrip(".").upper()
    if not path.exists():
        check(step, f"{name} via Docling", False, f"{path.name} missing")
        return
    try:
        result = anonymize(path.read_bytes(), path.name)
    except Exception as exc:
        check(step, f"{name} via Docling", False, str(exc))
        return
    via = result.get("extracted_with")
    check(step, f"{name} via Docling", via == "docling", f"extracted_with={via}")
    check_clean(step, name, result)
    same = result.get("entity_map") == expected_map
    check(step, f"{name}: same entity map as sample.txt", same,
          f"{result.get('entity_count', 0)} entities" if same else
          f"differs: {sorted(set(result.get('entity_map', {})) ^ set(expected_map))}")


def _document_text(data: bytes, suffix: str) -> str:
    """All text in the file, read with other tools than the service uses."""
    if suffix == ".docx":
        z = zipfile.ZipFile(io.BytesIO(data))
        parts = [z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith((".xml", ".rels"))]
        return "\n".join(re.sub(r"<[^>]+>", "", part) + part for part in parts)  # text and attributes
    tmp = RESULTS_DIR / "_check.pdf"
    RESULTS_DIR.mkdir(exist_ok=True)
    tmp.write_bytes(data)
    try:
        text = subprocess.run(["pdftotext", str(tmp), "-"], capture_output=True, text=True, check=True).stdout
        text += subprocess.run(["pdfinfo", str(tmp)], capture_output=True, text=True, check=True).stdout
    finally:
        tmp.unlink()
    return text + data.decode("latin-1")  # raw bytes: link URIs


def check_same_format(step: int, path: Path) -> None:
    """The service returns the file in its own format with no PII left in it."""
    name = f"{path.name} out"
    try:
        r = httpx.post(f"{SERVICE_URL}/anonymize", files={"file": (path.name, path.read_bytes())},
                       params={"document": "true", "project_id": "dry-run",
                               "targets": ",".join(INTERVIEW_TARGETS)}, timeout=300)
        r.raise_for_status()
        result = r.json()
    except Exception as exc:
        check(step, name, False, str(exc))
        return
    if not result.get("document_base64"):
        check(step, name, False, f"no document: {result.get('document_problems')}")
        return
    data = base64.b64decode(result["document_base64"])
    try:
        text = _document_text(data, path.suffix)
    except Exception as exc:
        check(step, name, False, f"could not read back: {exc}")
        return
    left = [v for v in INTERVIEW_PII if re.search(rf"(?<!\w){re.escape(v)}(?!\w)", text)]
    check(step, f"{name}: same format, no PII left", not left, f"left={left}" if left else f"{len(data)} bytes")


def write_results(filename: str) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    now = datetime.now()
    out = RESULTS_DIR / f"dry_run_{now:%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps({
        "usecase": "UC10",
        "timestamp": now.isoformat(timespec="seconds"),
        "service_url": SERVICE_URL,
        "input": filename,
        "passed": all(s["passed"] for s in steps),
        "steps": steps,
    }, indent=2), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=None)
    args = parser.parse_args()

    content, filename = load_input(args.input)
    print(f"\nUC10 dry-run  file={filename}  bytes={len(content)}\n")

    # Step 1 — Docling health
    try:
        r = httpx.get(f"{DOCLING_URL}/health", timeout=5)
        check(1, "Docling health", r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as exc:
        check(1, "Docling health", False, str(exc))

    # Step 2 — Presidio service health
    try:
        r = httpx.get(f"{SERVICE_URL}/health", timeout=5)
        ok = r.status_code == 200 and r.json().get("status") == "ok"
        check(2, "Presidio service health", ok, f"HTTP {r.status_code}")
    except Exception as exc:
        check(2, "Presidio service health", False, str(exc))

    # Step 3 — POST /anonymize
    result1: dict = {}
    try:
        result1 = anonymize(content, filename)
        check(3, "POST /anonymize", True, "HTTP 200")
    except Exception as exc:
        check(3, "POST /anonymize", False, str(exc))

    # Step 4 — Assert anonymization happened, cleanly
    if result1:
        anon_text = result1.get("anonymized_text", "")
        entity_count = result1.get("entity_count", 0)
        check(4, "entity_count > 0", entity_count > 0, f"got {entity_count}")
        check(4, '"Jan de Vries" removed', "Jan de Vries" not in anon_text, f"text[:80]={anon_text[:80]!r}")
        check_clean(4, filename, result1)
    else:
        check(4, "entity_count > 0", False, "no result from step 3")
        check(4, '"Jan de Vries" removed', False, "no result from step 3")

    # Step 5 — Consistency: same input → same pseudonyms
    result2: dict = {}
    try:
        result2 = anonymize(content, filename)
    except Exception:
        pass

    if result1 and result2:
        map1 = result1.get("entity_map", {})
        map2 = result2.get("entity_map", {})
        check(5, "Pseudonym consistency (same input → same output)", map1 == map2,
              f"run1={len(map1)} entries  run2={len(map2)} entries")
    else:
        check(5, "Pseudonym consistency", False, "could not get two results")

    # Steps 6-7 — the same sample as DOCX and PDF (only when testing the default sample)
    if filename == "sample.txt" and result1:
        check_document(6, TESTS / "sample.docx", result1.get("entity_map", {}))
        check_document(7, TESTS / "sample.pdf", result1.get("entity_map", {}))
        check_same_format(8, TESTS / "interview.docx")
        check_same_format(8, TESTS / "interview.pdf")

    results_file = write_results(filename)
    failures = [s["name"] for s in steps if not s["passed"]]
    print()
    print(f"  Results: {results_file.relative_to(TESTS.parent)}")
    if failures:
        print(f"  {len(failures)} step(s) FAILED: {', '.join(failures)}")
        sys.exit(1)
    print("  All steps passed.")


if __name__ == "__main__":
    main()
