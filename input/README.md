# input/

Put documents to anonymize here: `.pdf`, `.docx`, `.txt` or `.md`.

Name the target company (the organisation the research was for) in `targets.txt`, one company per line,
other names of the same company after `|`:

    Acme | Acme BV | acme.nl

Then run, from the repo root:

    python3 scripts/anonymize_folder.py

Anonymized: names of people (and their email, phone, student number, bank account) and the target company.
Everything else stays readable. Results land in `output/`, keys in `keys/`. Files already done are skipped;
add `--force` to redo them. Needs the UC10 service on http://localhost:5010 (localstack `uc10-anonymizer`).

Everything here except this README is kept out of git.
