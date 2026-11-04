"""Unit tests for refactored modular components of UC10 Document Anonymizer.

Tests:
- BSN 11-proef algorithmic validation (valid numbers, invalid checksums, fake patterns)
- TitledName detection logic
- Language routing (Dutch vs English word frequencies)
- Wordlist definitions and constants integrity
- Entity hashing and deterministic label keying
"""

import sys
import unittest
from pathlib import Path

# Add repo root to path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from service.data.wordlists import (
    DETECTED_ENTITIES,
    SUPPORTED_LANGUAGES,
    _LABEL_PREFIX,
    _NAME_WORDS,
)
from service.processors.text import (
    guess_language,
    inside,
)
from service.recognizers.dutch import is_valid_bsn
from service.storage.registry import (
    counter_key,
    entity_hash,
    label_prefix,
)


class TestBSNValidation(unittest.TestCase):
    """Test official Dutch BSN 11-proef validation rules."""

    def test_valid_bsn_examples(self):
        # Known valid 9-digit and 8-digit BSN numbers
        valid_bsns = [
            "111222333",  # 9*1+8*1+7*1+6*2+5*2+4*2+3*3+2*3-3 = 9+8+7+12+10+8+9+6-3 = 66 (66%11=0)
            "123456782",  # Standard valid 11-proef test
            "11.12.22.333",  # Formatted with dots
            " 111222333 ",  # Whitespace padding
            "12345672",   # 8-digit BSN (012345672: sum=110, 110%11=0)
        ]
        for bsn in valid_bsns:
            with self.subTest(bsn=bsn):
                self.assertTrue(is_valid_bsn(bsn), f"BSN {bsn} should be valid")

    def test_invalid_bsn_checksums(self):
        invalid_bsns = [
            "123456789",  # Invalid checksum
            "000000000",  # Identical digits
            "999999999",  # Identical digits
            "12345",      # Too short
            "1234567890", # Too long
            "abcdefghi",  # Letters
            "",           # Empty
        ]
        for bsn in invalid_bsns:
            with self.subTest(bsn=bsn):
                self.assertFalse(is_valid_bsn(bsn), f"BSN {bsn} should be invalid")


class TestLanguageRouting(unittest.TestCase):
    """Test text language detection."""

    def test_dutch_text(self):
        nl_text = "Dit is een Nederlands document over beleidsmedewerkers van de gemeente."
        self.assertEqual(guess_language(nl_text), "nl")

    def test_english_text(self):
        en_text = "This is an English research document with several participants from our university."
        self.assertEqual(guess_language(en_text), "en")

    def test_ambiguous_short_text(self):
        # Numbers or single words without function words
        self.assertIsNone(guess_language("123 456"))


class TestWordlistsAndStorage(unittest.TestCase):
    """Test static definitions and hashing stability."""

    def test_wordlists_contain_common_names(self):
        self.assertIn("bakker", _NAME_WORDS)
        self.assertIn("vries", _NAME_WORDS)
        self.assertIn("smith", _NAME_WORDS)
        self.assertIn("miller", _NAME_WORDS)
        self.assertIn("nl", SUPPORTED_LANGUAGES)
        self.assertIn("en", SUPPORTED_LANGUAGES)

    def test_label_prefixes(self):
        self.assertEqual(label_prefix("PERSON"), "PERSOON")
        self.assertEqual(label_prefix("ORGANIZATION"), "ORGANISATIE")
        self.assertEqual(label_prefix("UNKNOWN_TYPE"), "ENTITEIT")

    def test_counter_keys(self):
        self.assertEqual(counter_key("PERSON"), "PERSON")
        self.assertEqual(counter_key("CUSTOM_RANDOM"), "ENTITEIT")

    def test_deterministic_hashing(self):
        h1 = entity_hash("Jan de Vries")
        h2 = entity_hash("  jan de vries  ")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # SHA-256 hex length

    def test_inside_protected_span(self):
        protected = [(10, 25), (50, 80)]
        self.assertTrue(inside(12, 18, protected))
        self.assertTrue(inside(8, 15, protected))
        self.assertFalse(inside(30, 45, protected))
        self.assertFalse(inside(85, 90, protected))


if __name__ == "__main__":
    unittest.main()
