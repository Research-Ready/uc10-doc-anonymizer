"""Anonymize every document in input/ and write the results to output/.

Anonymized: names of people (and their email, phone, student number, bank account), and the target
company: the organisation the research was for, named in input/targets.txt (one company per line,
other names of the same company after "|": "Acme | Acme BV | acme.nl"). Everything else stays readable.

Per input file <name>.<ext> (<anon> = <name> with people and target company masked):
  output/<anon>_anon.pdf                the anonymized PDF (layout kept)          (PDF input)
  output/<anon>/<anon>_anon.<ext>       the anonymized DOCX/TXT/MD                (other input)
  keys/<name>.<ext>.entity_map.json     original -> label: the key that reverses the anonymization.
  keys/done.json                        which input became which output (holds the original names)
Keys are kept apart from output/, so output/ can be shared as a whole.

For DOCX/PDF the service checks the written file; if any original value is still in it,
no document is written and the file is reported as FAIL.
Files already done (output newer than input) are skipped; --force redoes them.
Usage: python3 scripts/anonymize_folder.py [--input DIR] [--output DIR] [--keys DIR] [--force]
UC10_URL overrides the service URL (default http://localhost:5010).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
SERVICE_URL = os.getenv("UC10_URL", "http://localhost:5010")
SUPPORTED = {".txt", ".md", ".docx", ".pdf"}


def read_targets(input_dir: Path) -> list[str]:
    path = input_dir / "targets.txt"
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def anonymize_name(stem: str, entity_map: dict[str, str], targets: dict[str, str]) -> str:
    """The file name with people and the target company masked, longest original first. Targets
    also when they don't occur in the text ("Thesis ... - Voorbeeldbedrijf.pdf"), in any capitalisation."""
    names = {o: l for o, l in entity_map.items() if l.startswith(("PERSOON_", "ORGANISATIE_", "ID_"))}
    for original in sorted({**names, **targets}, key=len, reverse=True):
        label = targets.get(original) or names[original]
        parts = [p for p in original.split() if p]
        if not parts:
            continue
        body = r"[\s_-]*".join(re.escape(part) for part in parts)
        stem = re.sub(rf"(?<![a-zA-Z0-9]){body}(?![a-zA-Z0-9])", label, stem, flags=re.IGNORECASE)
    return stem


def output_path(src: Path, name: str, output: Path) -> Path:
    anon = f"{name}_anon{src.suffix.lower()}"
    return output / anon if src.suffix.lower() == ".pdf" else output / name / anon


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=REPO / "input")
    parser.add_argument("--output", type=Path, default=REPO / "output")
    parser.add_argument("--keys", type=Path, default=REPO / "keys")
    parser.add_argument("--force", action="store_true", help="redo files that already have output")
    args = parser.parse_args()

    files = sorted(p for p in args.input.iterdir()
                   if p.is_file() and p.suffix.lower() in SUPPORTED and p.name not in ("README.md", "targets.txt"))
    if not files:
        print(f"No {', '.join(sorted(SUPPORTED))} files in {args.input}")
        return
    targets = read_targets(args.input)
    if not targets:
        print("  note  no input/targets.txt: the target company is not masked")
    targets_file = args.input / "targets.txt"
    targets_mtime = targets_file.stat().st_mtime if targets_file.exists() else 0

    args.keys.mkdir(parents=True, exist_ok=True)
    done_file = args.keys / "done.json"
    try:
        done = json.loads(done_file.read_text())
    except (OSError, ValueError):
        done = {}

    failed = 0
    for src in files:
        prev = args.output / done.get(src.name, "\0")
        raw_target_in_prev = any(t.lower() in prev.name.lower() for company in targets for t in company.split("|") if t.strip())
        if not args.force and prev.exists() and prev.stat().st_mtime >= src.stat().st_mtime and prev.stat().st_mtime >= targets_mtime and not raw_target_in_prev:
            print(f"  skip  {src.name}  (already done)")
            continue
        try:
            r = httpx.post(f"{SERVICE_URL}/anonymize", files={"file": (src.name, src.read_bytes())},
                           params={"document": "true", "targets": ",".join(targets)}, timeout=3600)
            r.raise_for_status()
            result = r.json()
        except Exception as exc:
            print(f"  FAIL  {src.name}  ({exc})")
            failed += 1
            continue

        name = anonymize_name(src.stem, result["entity_map"], result.get("targets") or {})
        out_doc = output_path(src, name, args.output)
        out_map = args.keys / f"{src.name}.entity_map.json"
        out_doc.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() in (".docx", ".pdf"):
            if not result.get("document_base64"):
                print(f"  FAIL  {src.name}  (no document: {'; '.join(result.get('document_problems') or [])})")
                failed += 1
                continue
            out_doc.write_bytes(base64.b64decode(result["document_base64"]))
        else:
            out_doc.write_text(result["anonymized_text"], encoding="utf-8")
        out_map.write_text(json.dumps(result["entity_map"], ensure_ascii=False, indent=2), encoding="utf-8")
        done[src.name] = str(out_doc.relative_to(args.output))
        done_file.write_text(json.dumps(done, ensure_ascii=False, indent=2), encoding="utf-8")

        note = ""
        unmatched = result.get("document_unmatched") or []
        is_fallback = result.get("extracted_with") == "fallback"
        if is_fallback:
            note += "  WARNING: Docling failed, layout lost"
        if unmatched:
            note += f"\n        CHECK {len(unmatched)} value(s) not found in the file: {unmatched}"

        if unmatched or is_fallback:
            print(f"  WARN  {src.name} -> {out_doc.relative_to(args.output)}  {result['entity_count']} entities via "
                  f"{result.get('extracted_with')}{note}")
            failed += 1
        else:
            print(f"  ok    {src.name} -> {out_doc.relative_to(args.output)}  {result['entity_count']} entities via "
                  f"{result.get('extracted_with')}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
