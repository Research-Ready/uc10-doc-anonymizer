"""UC10 Document Anonymizer — Custom Dutch Recognizers.

Includes TitledNameRecognizer (names prefixed with honorifics) and BSNRecognizer
(validates Dutch Burgerservicenummer using the 11-proef modulo check).
"""

from __future__ import annotations

import re
from typing import List, Optional

try:
    from presidio_analyzer import (
        EntityRecognizer,
        Pattern,
        PatternRecognizer,
        RecognizerRegistry,
        RecognizerResult,
    )
    from presidio_analyzer.nlp_engine import NlpArtifacts
    from presidio_analyzer.predefined_recognizers import PhoneRecognizer
except ImportError:
    class EntityRecognizer:
        def __init__(self, *args, **kwargs):
            pass
    class RecognizerResult:
        RECOGNIZER_NAME_KEY = "recognizer_name"
        def __init__(self, entity_type, start, end, score, **kwargs):
            self.entity_type = entity_type
            self.start = start
            self.end = end
            self.score = score
            self.recognition_metadata = kwargs.get("recognition_metadata", {})
    NlpArtifacts = None
    PhoneRecognizer = None
    Pattern = None
    PatternRecognizer = None
    RecognizerRegistry = None

try:
    from service.data.wordlists import (
        _DATE_PATTERNS,
        _ID_PATTERNS,
        _ORG_PATTERNS,
        _PHONE_CONTEXT,
        _PHONE_REGIONS,
        _TITLED_NAME,
    )
except ImportError:
    from data.wordlists import (
        _DATE_PATTERNS,
        _ID_PATTERNS,
        _ORG_PATTERNS,
        _PHONE_CONTEXT,
        _PHONE_REGIONS,
        _TITLED_NAME,
    )


def is_valid_bsn(bsn_candidate: str) -> bool:
    """Validate a Dutch BSN (Burgerservicenummer) using the official 11-proef.

    A valid BSN is an 8 or 9 digit number. If 8 digits, it is left-padded with a '0'.
    The checksum test requires:
    (9*d1 + 8*d2 + 7*d3 + 6*d4 + 5*d5 + 4*d6 + 3*d7 + 2*d8 - 1*d9) % 11 == 0 and > 0.
    """
    clean = re.sub(r"[.\s-]", "", bsn_candidate.strip())
    if not clean.isdigit() or len(clean) not in (8, 9):
        return False
    digits = clean.zfill(9)
    # Check for identical digits (e.g. 000000000, 999999999) which are not real BSNs
    if len(set(digits)) == 1:
        return False
    total = sum(int(digits[i]) * (9 - i) for i in range(8)) - int(digits[8])
    return total > 0 and (total % 11 == 0)


class BSNRecognizer(EntityRecognizer):
    """Recognizer for Dutch BSN numbers with 11-proef mathematical validation."""

    BSN_REGEX = re.compile(r"\b(?:\d{2}[.\s]?\d{2}[.\s]?\d{2}[.\s]?\d{3}|\d{8,9})\b")

    def __init__(self, supported_language: str = "nl"):
        super().__init__(
            supported_entities=["ID_NUMBER"],
            supported_language=supported_language,
            name="DutchBsnRecognizer",
        )

    def load(self) -> None:
        pass

    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: Optional[NlpArtifacts] = None
    ) -> List[RecognizerResult]:
        results: List[RecognizerResult] = []
        for match in self.BSN_REGEX.finditer(text):
            candidate = match.group()
            if is_valid_bsn(candidate):
                results.append(
                    RecognizerResult(
                        entity_type="ID_NUMBER",
                        start=match.start(),
                        end=match.end(),
                        score=0.85,
                        recognition_metadata={
                            RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                            "validation": "11-proef",
                        },
                    )
                )
        return results


class TitledNameRecognizer(EntityRecognizer):
    """Detects names following formal Dutch titles (mevrouw De Groot, dhr. Bakker)."""

    def __init__(self, supported_language: str):
        super().__init__(
            supported_entities=["PERSON"],
            supported_language=supported_language,
            name="TitledNameRecognizer",
        )

    def load(self) -> None:
        pass

    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: Optional[NlpArtifacts] = None
    ) -> List[RecognizerResult]:
        return [
            RecognizerResult(
                "PERSON",
                m.start("name"),
                m.end("name"),
                0.85,
                recognition_metadata={RecognizerResult.RECOGNIZER_NAME_KEY: self.name},
            )
            for m in _TITLED_NAME.finditer(text)
        ]


def setup_custom_recognizers(registry: RecognizerRegistry, supported_languages: list[str]) -> None:
    """Register all custom pattern and rule-based recognizers into the Presidio registry."""
    # Replace default phone recognizer with Dutch-aware context & regions
    try:
        registry.remove_recognizer("PhoneRecognizer")
    except Exception:
        pass

    for lang in supported_languages:
        registry.add_recognizer(
            PhoneRecognizer(
                supported_language=lang,
                supported_regions=_PHONE_REGIONS,
                context=_PHONE_CONTEXT,
            )
        )
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="ORGANIZATION",
                patterns=_ORG_PATTERNS,
                supported_language=lang,
                name="OrgPatternRecognizer",
                global_regex_flags=re.MULTILINE,
            )
        )
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="DATE_TIME",
                patterns=_DATE_PATTERNS,
                supported_language=lang,
                name="DatePatternRecognizer",
                global_regex_flags=re.IGNORECASE | re.MULTILINE,
            )
        )
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="ID_NUMBER",
                patterns=_ID_PATTERNS,
                supported_language=lang,
                name="IdNumberRecognizer",
                global_regex_flags=re.MULTILINE,
            )
        )
        registry.add_recognizer(TitledNameRecognizer(lang))
        registry.add_recognizer(BSNRecognizer(lang))
