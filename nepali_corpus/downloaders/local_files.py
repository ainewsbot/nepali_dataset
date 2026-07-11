"""Ingest local files (txt / jsonl / jsonl.zst) as a corpus source.

Used for manually collected material — PDF extractions, archive dumps,
partner deliveries — and for testing the pipeline offline. Registry entries
use access: local with a `path` field (file or directory).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from ..schema import Document


def _iter_lines(path: Path) -> Iterator[str]:
    if path.suffix == ".zst":
        import zstandard
        with open(path, "rb") as f, zstandard.ZstdDecompressor().stream_reader(f) as r:
            import io
            yield from io.TextIOWrapper(r, encoding="utf-8")
    else:
        with open(path, encoding="utf-8") as f:
            yield from f


def iter_local(source: dict, limit: int | None = None) -> Iterator[Document]:
    root = Path(source["path"])
    files = sorted(root.rglob("*")) if root.is_dir() else [root]
    count = 0
    for path in files:
        if not path.is_file() or path.suffix not in (".txt", ".jsonl", ".zst"):
            continue
        if path.suffix == ".txt":
            text = path.read_text(encoding="utf-8")
            if limit is not None and count >= limit:
                return
            count += 1
            yield Document(
                text=text,
                source=source["name"],
                url=str(path),
                license=str(source.get("license", "unknown")),
                redistributable=str(source.get("redistributable", "unknown")),
            )
        else:
            for line in _iter_lines(path):
                line = line.strip()
                if not line:
                    continue
                if limit is not None and count >= limit:
                    return
                row = json.loads(line)
                text = row.get("text", "")
                if not text:
                    continue
                count += 1
                yield Document(
                    text=text,
                    source=source["name"],
                    url=str(row.get("url", path)),
                    license=str(row.get("license", source.get("license", "unknown"))),
                    redistributable=str(row.get("redistributable", source.get("redistributable", "unknown"))),
                    meta=row.get("meta", {}),
                )
