"""End-to-end: registry source -> download -> filter -> dedup -> shards + manifests."""

import io
import json
from pathlib import Path

import yaml
import zstandard

from nepali_corpus import pipeline, registry
from nepali_corpus.pipeline import collect, corpus_report

FIXTURES = Path(__file__).parent / "fixtures"


def _test_registry(tmp_path):
    reg = {
        "sources": {
            "fixture-nepali": {
                "type": "manual", "access": "local", "path": str(FIXTURES / "nepali_sample.jsonl"),
                "license": "CC0", "redistributable": "yes", "priority": 1,
            },
            "fixture-mixed": {
                "type": "manual", "access": "local", "path": str(FIXTURES / "contaminants.jsonl"),
                "license": "copyrighted", "redistributable": "no", "priority": 2,
            },
        }
    }
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(reg), encoding="utf-8")
    return path


def _read_shards(directory):
    docs = []
    for shard in sorted(directory.glob("*.jsonl.zst")):
        with open(shard, "rb") as f, zstandard.ZstdDecompressor().stream_reader(f) as r:
            for line in io.TextIOWrapper(r, encoding="utf-8"):
                docs.append(json.loads(line))
    return docs


def test_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "REGISTRY_PATH", _test_registry(tmp_path))
    data_dir = tmp_path / "data"

    stats = collect(["fixture-nepali", "fixture-mixed"], data_dir=data_dir, progress=False)

    # source 1: all five genuine Nepali docs accepted
    s1 = stats[0]
    assert s1.accepted == 5 and s1.duplicates == 0 and not s1.rejected

    # source 2: hindi + english + short rejected; exact & near dupes of source 1 caught
    s2 = stats[1]
    assert s2.rejected == {"not_nepali": 1, "not_devanagari": 1, "too_short": 1}
    assert s2.duplicates == 2
    assert s2.accepted == 0

    # accepted docs carry provenance + license + lang score
    docs = _read_shards(data_dir / "clean" / "fixture-nepali")
    assert len(docs) == 5
    for d in docs:
        assert d["source"] == "fixture-nepali"
        assert d["license"] == "CC0"
        assert d["redistributable"] == "yes"
        assert d["lang_score"] > 0.5
        assert d["url"].startswith("https://example.com/")
        assert d["id"]

    # manifests + rights partition
    report = corpus_report(data_dir)
    assert report["total"]["accepted"] == 5
    assert report["by_rights"]["yes"]["accepted"] == 5
    assert report["by_rights"]["no"]["accepted"] == 0
    assert report["by_rights"]["no"]["sources"] == 1

    # rejection audit trail exists
    assert (data_dir / "rejected" / "fixture-mixed.jsonl.zst").exists()


def test_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "REGISTRY_PATH", _test_registry(tmp_path))
    stats = collect(["fixture-nepali"], limit=2, data_dir=tmp_path / "data", progress=False)
    assert stats[0].seen == 2


def test_cross_source_dedup_keeps_first(tmp_path, monkeypatch):
    """Collecting the same source twice in one run yields zero new docs."""
    monkeypatch.setattr(registry, "REGISTRY_PATH", _test_registry(tmp_path))
    from nepali_corpus.dedup import Deduper
    deduper = Deduper()
    collect(["fixture-nepali"], data_dir=tmp_path / "d1", deduper=deduper, progress=False)
    stats = collect(["fixture-nepali"], data_dir=tmp_path / "d2", deduper=deduper, progress=False)
    assert stats[0].accepted == 0
    assert stats[0].duplicates == 5
