"""Detection-quality check for the UC10 service: leaks and false positives.

Seed for T7 (not the 20-document evaluation set). Texts are fictional; cases
starting with "h-" were written after tuning and never tuned against.
Usage: python3 tests/eval_detection.py [-v]   (UC10_URL overrides the service URL)

Leak  = an expected PII string still (partly) readable in the output.
FP    = an entity_map key that overlaps no expected/optional string.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

URL = os.getenv("UC10_URL", "http://localhost:5010") + "/anonymize"

# (name, text, must be masked, may be masked[, target companies])
# Scope (2026-10-01): people and their direct identifiers, plus the named target company. Everything
# else (other organisations, places, dates, cited authors) must stay readable: masking it is a FP.
CASES = [
    ("nl-sample", Path(__file__).with_name("sample.txt").read_text(),
     ["Jan de Vries", "jan.devries@gemeente-utrecht.nl", "06-12345678", "Fatima El-Amin", "Pieter Janssen",
      "+31 20 123 4567", "ValueChain Hackers BV"],
     [], ["ValueChain Hackers BV"]),
    ("nl-contact",
     "Op 3 januari 2025 sprak onderzoeker Sanne Bakker met mevrouw De Groot van de Rabobank in Eindhoven.\n"
     "Zij is bereikbaar op 0612345678 of via s.bakker@tue.nl. Meer informatie staat op www.tue.nl.\n"
     "Het rekeningnummer is NL91ABNA0417164300.\n",
     ["Sanne Bakker", "De Groot", "0612345678", "s.bakker@tue.nl", "NL91ABNA0417164300"],
     []),
    ("nl-interview",
     "Interviewer: Hoe lang werkt u al bij Philips?\n"
     "Respondent: Sinds 2019. Mijn leidinggevende, Mohammed Yilmaz, woont in Den Haag.\n"
     "Interviewer: Dank u wel. Kunt u iets vertellen over het project?\n"
     "Respondent: Ja, samen met Lisa van den Berg van de Universiteit Utrecht.\n",
     ["Philips", "Mohammed Yilmaz", "Lisa van den Berg"],
     [], ["Philips"]),
    ("en-contact",
     "On 12 March 2024, Sarah Johnson from Unilever met Tom Evans in London.\n"
     "Contact her at sarah.johnson@unilever.com or +44 20 7946 0958.\n",
     ["Sarah Johnson", "Tom Evans", "sarah.johnson@unilever.com", "+44 20 7946 0958"],
     []),
    ("mixed",
     "Samenvatting: Anna de Wit van Heineken presenteerde de resultaten in Groningen.\n\n"
     "Summary: The follow-up call with David Miller of Siemens is planned in Berlin.\n",
     ["Anna de Wit", "Heineken", "David Miller"],
     [], ["Heineken"]),
]

# Held-out cases.
CASES += [
 ("h-nl-email", "Beste Kees,\nZoals besproken stuur ik je het verslag van het overleg met Marieke Jansen (Achmea) van dinsdag 4 februari.\nZij vroeg of Gert-Jan van Leeuwen van Stichting Wonen Delft ook kon aansluiten. Bel haar gerust op 010-4567890.\nMet vriendelijke groet,\nThijs Vermeulen\nAdviseur, Arcadis Nederland B.V., Arnhem\n",
  ["Kees", "Marieke Jansen", "Achmea", "Gert-Jan van Leeuwen", "010-4567890", "Thijs Vermeulen"], [], ["Achmea"]),
 ("h-nl-interview", "I: Wat was uw rol bij het project in Zwolle?\nR: Ik werkte samen met dr. Van Dijk en met Priya Ramdin van TNO. We hadden overleg in het stadhuis.\nI: En de financiering?\nR: Die kwam van het ministerie, via de heer Bos. Mijn e-mailadres is p.ramdin@tno.nl als u vragen heeft.\n",
  ["Van Dijk", "Priya Ramdin", "Bos", "p.ramdin@tno.nl"], []),
 ("h-en-report", "The pilot at Maastricht University Medical Center was led by Prof. Karen O'Neill.\nParticipants met weekly with Ahmed Hassan from Deloitte in Utrecht until 30 June 2023.\nQuestions can be sent to research-office@mumc.nl or by phone on +31 43 387 6543.\n",
  ["Karen O'Neill", "Ahmed Hassan", "research-office@mumc.nl", "+31 43 387 6543"], []),
]

# Published references stay readable, except the target company: a cited company report gives it away.
CASES += [
 ("cite-en",
  "Case studies suit how-questions (Yin, 2018). As Eisenhardt (1989) and Miles and Huberman (1994) argue, "
  "cases need several sources (Chen et al., 2019; Lu & Xu, 2020, pp. 3-5; Acme Trailers, 2023).\n"
  "The planner at Acme Trailers, Sanne Bakker, was interviewed on 3 March 2025.\n"
  "References\n"
  "Acme Trailers. (2023). Annual report 2023. https://www.acmetrailers.nl/report\n"
  "Eisenhardt, K. M. (1989). Building theories from case study research. Academy of Management Review, 14(4), 532-550.\n"
  "Yin, R. K. (2018). Case study research and applications. SAGE Publications.\n"
  "Appendix A. Interview transcript\n"
  "Mark de Jong works with Sanne Bakker in Groningen.\n",
  ["Sanne Bakker", "Mark de Jong", "Acme Trailers", "acmetrailers"], [], ["Acme Trailers | AcmeTrailers"]),
]

# Title-case common words, software and other organisations are not masked. The trap: Dutch surnames
# that are also words ("Bakker" = baker) must stay masked as names.
CASES += [
 ("title-words",
  "Master Thesis\nAuthor: Lisa Brouwer\nStudent number: S1234567\nSubmission date: 12 May 2026\n"
  "The Product Configurator Specialist (R3) explained the Engineering Bill of Materials (eBOM) and how "
  "the ERP system from SAP and the PLM system support planning. As a product configurator specialist, the author "
  "of the bill of materials handles each submission; the master data sits in enterprise resource planning.\n",
  ["Lisa Brouwer", "S1234567"], []),
 ("nl-surname-words",
  "Jan Bakker werkt als bakker bij Visser Bouw BV in Zwolle. Een visser ving daar vis.\n"
  "Volgens Bakker is de bouw in Zwolle vertraagd.\n",
  ["Jan Bakker"], ["Bakker"]),
 ("dictionary-orgs",
  "Master Thesis\nSubmission date: 3 June 2026\nThe Board approved the Bill of Materials.\n"
  "Interviews were held at Shell in Rotterdam and at Bakker Logistiek in Venlo.\n",
  ["Bakker Logistiek"], [], ["Bakker Logistiek"]),
]

def post(text: str, targets: list[str]) -> dict:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"t.txt\"\r\n"
            f"Content-Type: text/plain\r\n\r\n{text}\r\n--{boundary}--\r\n").encode()
    url = URL + "?" + urllib.parse.urlencode({"targets": ",".join(targets)})
    req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return json.load(urllib.request.urlopen(req, timeout=120))


def leaked(expected: str, out: str) -> bool:
    # Any 4+ char word of the value still present counts as a (partial) leak.
    parts = [p for p in re.split(r"[\s@.+\-]", expected) if len(p) >= 4 and not p.isupper()] or [expected]
    return any(p in out for p in parts)


total_exp = total_leak = total_fp = 0
for name, text, expected, optional, *rest in CASES:
    r = post(text, rest[0] if rest else [])
    out, emap = r["anonymized_text"], r["entity_map"]
    leaks = [e for e in expected if leaked(e, out)]
    known = expected + optional
    fps = [f"{k}→{v}" for k, v in emap.items() if not any(k in e or e in k for e in known)]
    total_exp += len(expected); total_leak += len(leaks); total_fp += len(fps)
    print(f"== {name}: leaks {len(leaks)}/{len(expected)}  FP {len(fps)}")
    for l in leaks: print("   LEAK", l)
    for f in fps: print("   FP  ", f)
    if "-v" in sys.argv: print("   " + out.replace("\n", "\n   "))
print(f"TOTAL leaks {total_leak}/{total_exp}  FP {total_fp}")
sys.exit(1 if total_leak or total_fp else 0)
