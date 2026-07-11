import json
from pathlib import Path

from nepali_corpus.dedup import Deduper, ExactDeduper, NearDeduper

FIXTURES = Path(__file__).parent / "fixtures"

with open(FIXTURES / "nepali_sample.jsonl", encoding="utf-8") as f:
    NEPALI = [json.loads(line)["text"] for line in f if line.strip()]
with open(FIXTURES / "contaminants.jsonl", encoding="utf-8") as f:
    CONTAMINANTS = [json.loads(line)["text"] for line in f if line.strip()]

ORIGINAL = NEPALI[0]
EXACT_DUPE = CONTAMINANTS[3]      # byte-identical to ORIGINAL
NEAR_DUPE = CONTAMINANTS[4]       # one word inserted + one sentence appended


def test_exact_dedup():
    d = ExactDeduper()
    assert not d.is_duplicate(ORIGINAL)
    assert d.is_duplicate(EXACT_DUPE)


def test_exact_dedup_ignores_whitespace_and_punct():
    d = ExactDeduper()
    assert not d.is_duplicate("नेपाल राम्रो देश हो।")
    assert d.is_duplicate("नेपाल   राम्रो देश हो")


def test_near_dedup_catches_light_edit():
    d = NearDeduper(threshold=0.8)
    assert not d.is_duplicate(ORIGINAL)
    assert d.is_duplicate(NEAR_DUPE)


def test_near_dedup_keeps_distinct_docs():
    d = NearDeduper(threshold=0.8)
    for text in NEPALI:
        assert not d.is_duplicate(text), "distinct fixture doc flagged as near-dupe"


def test_combined_deduper_counts():
    d = Deduper(near_threshold=0.8)
    assert not d.is_duplicate(ORIGINAL)
    assert d.is_duplicate(EXACT_DUPE)
    assert d.is_duplicate(NEAR_DUPE)
    assert d.exact_hits == 1
    assert d.near_hits == 1
