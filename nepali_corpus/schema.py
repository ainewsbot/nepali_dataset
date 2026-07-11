"""Document record shared by every stage of the pipeline.

The corpus policy is "collect everything, sort rights later": that only works
if every document permanently carries its provenance and license, so the
corpus can be partitioned by rights at any time without re-collection.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class Document:
    text: str
    source: str                      # registry key, e.g. "fineweb2"
    url: str = ""                    # original location, if known
    license: str = "unknown"         # license as declared by the source
    redistributable: str = "unknown" # yes | no | unknown
    lang_score: float = 0.0          # Nepali-vs-other Devanagari confidence, set by filter
    collected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    meta: dict = field(default_factory=dict)

    @property
    def doc_id(self) -> str:
        h = hashlib.sha1(f"{self.source}\x00{self.url}\x00{self.text}".encode()).hexdigest()
        return h[:16]

    def to_json(self) -> str:
        d = asdict(self)
        d["id"] = self.doc_id
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> "Document":
        d = json.loads(line)
        d.pop("id", None)
        return cls(**d)
