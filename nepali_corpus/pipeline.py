"""Orchestration: source -> filter -> dedup -> sharded jsonl.zst + manifests.

Layout under data/:
  data/clean/<source>/shard-00000.jsonl.zst   accepted documents
  data/rejected/<source>.jsonl.zst            rejected docs + reason (audit trail)
  data/manifests/<source>.json                counts, license, rights partition

Dedup state is per-run and shared across the sources of that run, so
collecting overlapping sources together (fineweb2 + culturax + oscar in one
run) automatically cross-deduplicates them; keep-first order = registry
priority order.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import zstandard
from tqdm import tqdm

from .dedup import Deduper
from .downloaders import iter_source
from .filtering import QualityFilter, normalize
from .registry import get_source
from .schema import Document

DATA_DIR = Path("data")
SHARD_DOCS = 50_000


@dataclass
class SourceStats:
    source: str
    license: str = "unknown"
    redistributable: str = "unknown"
    seen: int = 0
    accepted: int = 0
    duplicates: int = 0
    chars: int = 0
    words: int = 0
    rejected: dict = field(default_factory=dict)  # reason -> count

    def to_json(self) -> dict:
        d = self.__dict__.copy()
        # ~4 chars per subword token is a reasonable Devanagari estimate
        d["approx_tokens"] = self.chars // 4
        return d


class _ShardWriter:
    def __init__(self, directory: Path):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self._shard = -1
        self._in_shard = 0
        self._fh = None
        self._writer = None

    def write(self, doc: Document) -> None:
        if self._writer is None or self._in_shard >= SHARD_DOCS:
            self._roll()
        self._writer.write((doc.to_json() + "\n").encode())
        self._in_shard += 1

    def _roll(self) -> None:
        self.close()
        self._shard += 1
        self._in_shard = 0
        self._fh = open(self.dir / f"shard-{self._shard:05d}.jsonl.zst", "wb")
        self._writer = zstandard.ZstdCompressor(level=10).stream_writer(self._fh)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._fh.close()
            self._writer = self._fh = None


def collect(
    source_names: list[str],
    limit: int | None = None,
    data_dir: Path = DATA_DIR,
    qfilter: QualityFilter | None = None,
    deduper: Deduper | None = None,
    progress: bool = True,
) -> list[SourceStats]:
    """Run the full pipeline for the given registry sources, in order."""
    qfilter = qfilter or QualityFilter()
    deduper = deduper or Deduper()
    all_stats = []

    for name in source_names:
        source = get_source(name)
        stats = SourceStats(
            source=name,
            license=str(source.get("license", "unknown")),
            redistributable=str(source.get("redistributable", "unknown")),
        )
        writer = _ShardWriter(data_dir / "clean" / name)
        rej_dir = data_dir / "rejected"
        rej_dir.mkdir(parents=True, exist_ok=True)
        rej_fh = open(rej_dir / f"{name}.jsonl.zst", "wb")
        rej_writer = zstandard.ZstdCompressor(level=10).stream_writer(rej_fh)

        docs = iter_source(source, limit=limit)
        if progress:
            docs = tqdm(docs, desc=name, unit="doc")
        try:
            for doc in docs:
                stats.seen += 1
                doc.text = normalize(doc.text)
                result = qfilter.check(doc.text)
                if not result.ok:
                    stats.rejected[result.reason] = stats.rejected.get(result.reason, 0) + 1
                    rej_writer.write(
                        (json.dumps({"reason": result.reason, "url": doc.url,
                                     "sample": doc.text[:300]}, ensure_ascii=False) + "\n").encode()
                    )
                    continue
                if deduper.is_duplicate(doc.text):
                    stats.duplicates += 1
                    continue
                doc.lang_score = result.nepali_score
                writer.write(doc)
                stats.accepted += 1
                stats.chars += len(doc.text)
                stats.words += len(doc.text.split())
        finally:
            writer.close()
            rej_writer.close()
            rej_fh.close()

        manifest_dir = data_dir / "manifests"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        with open(manifest_dir / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(stats.to_json(), f, ensure_ascii=False, indent=2)
        all_stats.append(stats)

    return all_stats


def corpus_report(data_dir: Path = DATA_DIR) -> dict:
    """Aggregate all manifests into one corpus-level report, partitioned by
    redistribution rights — the 'sort rights later' switchboard."""
    manifests = sorted((data_dir / "manifests").glob("*.json"))
    report = {"sources": [], "total": {"accepted": 0, "chars": 0, "approx_tokens": 0},
              "by_rights": {}}
    for path in manifests:
        m = json.loads(path.read_text(encoding="utf-8"))
        report["sources"].append(m)
        report["total"]["accepted"] += m["accepted"]
        report["total"]["chars"] += m["chars"]
        report["total"]["approx_tokens"] += m["approx_tokens"]
        rights = report["by_rights"].setdefault(
            m["redistributable"], {"sources": 0, "accepted": 0, "approx_tokens": 0})
        rights["sources"] += 1
        rights["accepted"] += m["accepted"]
        rights["approx_tokens"] += m["approx_tokens"]
    return report
