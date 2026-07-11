"""Parse Wikimedia XML dumps (newiki, newikisource, newiktionary).

Downloads <wiki>-latest-pages-articles.xml.bz2 from dumps.wikimedia.org and
extracts plain text with a lightweight wikitext stripper. This is a
best-effort cleaner — good enough for LM pretraining text; use the HF
`wikimedia/wikipedia` mirror instead when reachable (it is pre-cleaned).
"""

from __future__ import annotations

import bz2
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

import requests

from ..schema import Document

DUMP_URL = "https://dumps.wikimedia.org/{wiki}/latest/{wiki}-latest-pages-articles.xml.bz2"
CACHE_DIR = Path("data/raw/_dumps")

_MARKUP = [
    (re.compile(r"(?s)<!--.*?-->"), ""),
    (re.compile(r"(?s)\{\{[^{}]*\}\}"), ""),          # templates (applied repeatedly)
    (re.compile(r"(?s)\{\|.*?\|\}"), ""),              # tables
    (re.compile(r"(?s)<ref[^>]*/>|<ref[^>]*>.*?</ref>"), ""),
    (re.compile(r"\[\[(?:[^\[\]|]*\|)?([^\[\]|]*)\]\]"), r"\1"),  # [[a|b]] -> b
    (re.compile(r"\[https?://\S+ ([^\]]*)\]"), r"\1"),
    (re.compile(r"\[https?://\S+\]"), ""),
    (re.compile(r"<[^>]+>"), ""),                      # remaining html tags
    (re.compile(r"'{2,}"), ""),                        # bold/italic quotes
    (re.compile(r"^[=]+ *(.*?) *[=]+ *$", re.M), r"\1"),  # headings
    (re.compile(r"^[*#:;]+ *", re.M), ""),             # list markers
]


def strip_wikitext(text: str) -> str:
    for _ in range(4):  # nested templates
        new = _MARKUP[1][0].sub("", text)
        if new == text:
            break
        text = new
    for pattern, repl in _MARKUP:
        text = pattern.sub(repl, text)
    return text


def _fetch_dump(wiki: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{wiki}-latest-pages-articles.xml.bz2"
    if path.exists():
        return path
    url = DUMP_URL.format(wiki=wiki)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        tmp = path.with_suffix(".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        tmp.rename(path)
    return path


def iter_wikimedia(source: dict, limit: int | None = None) -> Iterator[Document]:
    wiki = source["dump_wiki"]
    dump_path = source.get("dump_path") or _fetch_dump(wiki)  # dump_path: pre-downloaded file

    count = 0
    with bz2.open(dump_path, "rb") as f:
        for _, elem in ET.iterparse(f):
            tag = elem.tag.rsplit("}", 1)[-1]
            if tag != "page":
                continue
            ns = elem.findtext("./{*}ns")
            title = elem.findtext("./{*}title") or ""
            raw = elem.findtext("./{*}revision/{*}text") or ""
            elem.clear()
            if ns != "0" or not raw or raw.lstrip().lower().startswith("#redirect"):
                continue
            if limit is not None and count >= limit:
                break
            count += 1
            yield Document(
                text=strip_wikitext(raw),
                source=source["name"],
                url=f"https://{wiki.replace('wiki', '.wikipedia.org/wiki/', 1)}{title}" if wiki.endswith("wiki") else "",
                license=str(source.get("license", "CC-BY-SA")),
                redistributable=str(source.get("redistributable", "yes")),
                meta={"title": title, "wiki": wiki},
            )
