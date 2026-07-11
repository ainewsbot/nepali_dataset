"""Downloaders, keyed by the registry's `access` field.

Each downloader is a generator of Document objects; the pipeline handles
filtering, dedup and storage. To add a new access method, register it here.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..schema import Document


def iter_source(source: dict, limit: int | None = None) -> Iterator[Document]:
    access = source.get("access")
    if access == "hf":
        from .hf_datasets import iter_hf
        yield from iter_hf(source, limit)
    elif access == "wikimedia":
        from .wikimedia import iter_wikimedia
        yield from iter_wikimedia(source, limit)
    elif access == "news":
        from .news_sitemap import iter_news
        yield from iter_news(source, limit)
    elif access == "local":
        from .local_files import iter_local
        yield from iter_local(source, limit)
    else:
        raise ValueError(
            f"source {source['name']!r} has access={access!r}; "
            "manual sources need a bespoke collection step (see registry notes)"
        )
