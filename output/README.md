# output/

Per input file, named after the original with people and the target company masked
(`Thesis Eva Jansen - Acme.pdf` becomes `Thesis PERSOON_1 - ORGANISATIE_1_anon.pdf`):

- `<name>_anon.pdf`: the anonymized PDF. The original text is redacted (removed, not covered) and the label
  is written in its place, in the original size and colour where it fits; links and metadata are cleared.
- `<name>/<name>_anon.docx` / `.txt` / `.md` for non-PDF input (DOCX: text replaced inside the Word file,
  styles and tables kept; author and comment names removed).

Anonymized: people and the target company (`input/targets.txt`). Everything else stays readable, including
published references ("(Yin, 2018)"); the target company is masked there too.

The keys (which original became which label) are in `keys/`, not here, so this folder can be shared.
If any original value is still in a written DOCX/PDF, no document is written and the script reports FAIL.
Scanned PDFs (text only in images) are refused for the same reason.
Everything here except this README is kept out of git.
