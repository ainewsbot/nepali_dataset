"""Exact and near-duplicate removal.

The tier-1 sources are all CommonCrawl derivatives with massive mutual
overlap; without near-dedup the corpus would triple-count the same news
articles. Exact dedup hashes normalized text; near-dedup uses MinHash LSH
over word 5-gram shingles.
"""

from __future__ import annotations

import hashlib
import re

from datasketch import MinHash, MinHashLSH

_WS = re.compile(r"\s+")
# strip punctuation including the Devanagari danda ।/॥ (inside the block, so
# the keep-range alone would retain it)
_NON_WORD = re.compile(r"[।॥]|[^\wऀ-ॿ ]+")


def _canonical(text: str) -> str:
    """Aggressive canonical form for duplicate detection only (never stored):
    lowercase, strip punctuation, collapse whitespace."""
    return _WS.sub(" ", _NON_WORD.sub(" ", text.lower())).strip()


def exact_key(text: str) -> str:
    return hashlib.sha1(_canonical(text).encode()).hexdigest()


class ExactDeduper:
    def __init__(self):
        self._seen: set[str] = set()

    def is_duplicate(self, text: str) -> bool:
        key = exact_key(text)
        if key in self._seen:
            return True
        self._seen.add(key)
        return False


class NearDeduper:
    """MinHash-LSH near-duplicate detector; single-pass, keeps first seen."""

    def __init__(self, threshold: float = 0.8, num_perm: int = 128, shingle_size: int = 5):
        self.num_perm = num_perm
        self.shingle_size = shingle_size
        self._lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self._count = 0

    def _minhash(self, text: str) -> MinHash:
        words = _canonical(text).split()
        m = MinHash(num_perm=self.num_perm)
        if len(words) < self.shingle_size:
            for w in words:
                m.update(w.encode())
            return m
        for i in range(len(words) - self.shingle_size + 1):
            m.update(" ".join(words[i : i + self.shingle_size]).encode())
        return m

    def is_duplicate(self, text: str) -> bool:
        m = self._minhash(text)
        if self._lsh.query(m):
            return True
        self._count += 1
        self._lsh.insert(f"d{self._count}", m)
        return False


class Deduper:
    """Exact check first (cheap), then near-duplicate check."""

    def __init__(self, near_threshold: float = 0.8):
        self.exact = ExactDeduper()
        self.near = NearDeduper(threshold=near_threshold)
        self.exact_hits = 0
        self.near_hits = 0

    def is_duplicate(self, text: str) -> bool:
        if self.exact.is_duplicate(text):
            self.exact_hits += 1
            return True
        if self.near.is_duplicate(text):
            self.near_hits += 1
            return True
        return False
