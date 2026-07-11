"""Language identification and quality filtering for Nepali text.

The hard problem: Nepali shares Devanagari with Hindi, Sanskrit, Maithili and
Bhojpuri, and off-the-shelf language identifiers confuse them constantly. We
discriminate with closed-class function words that are frequent in exactly one
language — verb endings and particles, not content words. A document must both
be mostly Devanagari AND score as Nepali against the marker lists.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
WORD_RE = re.compile(r"[ऀ-ॿ]+")

# Function words / verb forms frequent in Nepali and rare-to-absent in Hindi.
# Copulas (छ-forms), past auxiliaries (थियो/भयो), infinitives in -नु,
# plural हरू, and particles like पनि/अनि/भने/लागि/तर.
NEPALI_MARKERS = frozenset("""
छ छन् छु छौं छौ छिन् छैन छैनन् हुन् हुन्छ हुँदैन भयो भएको भएका भएकी हुने
थियो थिए थिइन् थिएन गर्छ गर्छन् गर्ने गरेको गरेका गरी गर्दै गर्न गर्नु गर्नुभयो
भन्ने भनेका भनी भने पनि अनि तर लागि हरू हरु यो त्यो कुनै आफ्नो उनी उनले
नेपाल नेपाली रहेको रहेका पाइन्छ गरिएको गरिने हुनुहुन्छ सक्छ सक्ने दिए लिएर
अघि पछि माथि मुनि जस्तै अर्को एउटा दुई हामी हाम्रो तपाईं
""".split())

# Function words frequent in Hindi and rare-to-absent in Nepali.
HINDI_MARKERS = frozenset("""
है हैं हूँ हूं था थी थे नहीं में से और यह वह इस उस किया करना करता करती करते
हुआ हुई हुए रहा रही रहे गया गयी गई लिए वाले वाला वाली अपने अपना अपनी
कोई कुछ हमें उन्हें इन्हें आपको मुझे तुम मैं हम आप जब तब क्यों कैसे साथ
भारत हिंदी सकता सकती सकते चाहिए गए कहा जाता जाती जाते
""".split())


@dataclass
class FilterResult:
    ok: bool
    reason: str          # "" when ok
    devanagari_ratio: float
    nepali_score: float  # in [-1, 1]; >0 leans Nepali, <0 leans Hindi/other


def devanagari_ratio(text: str) -> float:
    """Fraction of non-space characters in the Devanagari block."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if "ऀ" <= c <= "ॿ") / len(chars)


def nepali_score(text: str) -> float:
    """(nepali_hits - hindi_hits) / (nepali_hits + hindi_hits) over marker words.

    Returns 0.0 when no markers are found (short or ambiguous text).
    """
    ne = hi = 0
    for w in WORD_RE.findall(text):
        if w in NEPALI_MARKERS:
            ne += 1
        elif w in HINDI_MARKERS:
            hi += 1
    total = ne + hi
    if total == 0:
        return 0.0
    return (ne - hi) / total


class QualityFilter:
    """Cheap, deterministic document filter. Tuned to be permissive — the
    policy is collect everything — so it only rejects documents that are
    clearly not usable Nepali prose. Every rejection carries a reason so
    thresholds can be audited from the pipeline's rejection log.
    """

    def __init__(
        self,
        min_chars: int = 120,
        max_chars: int = 1_500_000,
        min_devanagari_ratio: float = 0.5,
        min_nepali_score: float = 0.1,
        max_digit_ratio: float = 0.3,
        min_mean_word_len: float = 1.5,
        max_mean_word_len: float = 14.0,
    ):
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.min_devanagari_ratio = min_devanagari_ratio
        self.min_nepali_score = min_nepali_score
        self.max_digit_ratio = max_digit_ratio
        self.min_mean_word_len = min_mean_word_len
        self.max_mean_word_len = max_mean_word_len

    def check(self, text: str) -> FilterResult:
        text = normalize(text)
        n = len(text)
        dr = devanagari_ratio(text)
        ns = nepali_score(text)

        if n < self.min_chars:
            return FilterResult(False, "too_short", dr, ns)
        if n > self.max_chars:
            return FilterResult(False, "too_long", dr, ns)
        if dr < self.min_devanagari_ratio:
            return FilterResult(False, "not_devanagari", dr, ns)
        if ns < self.min_nepali_score:
            return FilterResult(False, "not_nepali", dr, ns)

        digits = sum(c.isdigit() for c in text)
        if digits / n > self.max_digit_ratio:
            return FilterResult(False, "too_many_digits", dr, ns)

        words = text.split()
        mean_wl = sum(len(w) for w in words) / max(len(words), 1)
        if not (self.min_mean_word_len <= mean_wl <= self.max_mean_word_len):
            return FilterResult(False, "degenerate_words", dr, ns)

        return FilterResult(True, "", dr, ns)


def normalize(text: str) -> str:
    """NFC-normalize, unify whitespace, drop control chars. Keeps Devanagari
    digits and punctuation (।) intact — they are part of the language."""
    text = unicodedata.normalize("NFC", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Cc" or c in "\n\t")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
