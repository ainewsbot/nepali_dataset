import json
from pathlib import Path

import pytest

from nepali_corpus.filtering import QualityFilter, devanagari_ratio, nepali_score, normalize

FIXTURES = Path(__file__).parent / "fixtures"


def _texts(name):
    with open(FIXTURES / name, encoding="utf-8") as f:
        return [json.loads(line)["text"] for line in f if line.strip()]


NEPALI = _texts("nepali_sample.jsonl")
HINDI = _texts("contaminants.jsonl")[0]
ENGLISH = _texts("contaminants.jsonl")[1]
TOO_SHORT = _texts("contaminants.jsonl")[2]


@pytest.mark.parametrize("text", NEPALI)
def test_accepts_real_nepali(text):
    result = QualityFilter().check(text)
    assert result.ok, f"rejected genuine Nepali: {result.reason}"
    assert result.nepali_score > 0.5


def test_rejects_hindi():
    result = QualityFilter().check(HINDI)
    assert not result.ok
    assert result.reason == "not_nepali"
    assert result.nepali_score < 0


def test_rejects_english():
    result = QualityFilter().check(ENGLISH)
    assert not result.ok
    assert result.reason == "not_devanagari"


def test_rejects_too_short():
    result = QualityFilter().check(TOO_SHORT)
    assert not result.ok
    assert result.reason == "too_short"


def test_devanagari_ratio_bounds():
    assert devanagari_ratio("") == 0.0
    assert devanagari_ratio("hello") == 0.0
    assert devanagari_ratio("नेपाल") == 1.0


def test_nepali_score_neutral_without_markers():
    assert nepali_score("१२३४ ॐ") == 0.0


def test_rejects_digit_soup():
    text = ("९८४१२३४५६७ " * 40) + "नेपाल छ पनि हरू भने अनि गर्छ हुन्छ भयो"
    result = QualityFilter().check(text)
    assert not result.ok
    assert result.reason == "too_many_digits"


def test_normalize_collapses_whitespace_keeps_devanagari():
    out = normalize("\u0928\u0947\u092a\u093e\u0932\t\t\u0930\u093e\u092e\u094d\u0930\u094b   \u0926\u0947\u0936 \u0939\u094b\u0964\n\n\n\n\u0927\u0928\u094d\u092f\u0935\u093e\u0926\u0964")
    assert "\t" not in out
    assert "  " not in out
    assert "\n\n\n" not in out
    assert out.startswith("\u0928\u0947\u092a\u093e\u0932 \u0930\u093e\u092e\u094d\u0930\u094b \u0926\u0947\u0936 \u0939\u094b\u0964")


def test_normalize_strips_control_chars():
    assert "\x00" not in normalize("\u0928\u0947\u092a\u093e\u0932\x00\x08 \u0930\u093e\u092e\u094d\u0930\u094b")
