"""Polite sitemap-driven crawler for Nepali news sites.

Discovers article URLs from /sitemap.xml (following sitemap indexes),
respects robots.txt, rate-limits requests, and extracts article text with
trafilatura when available (strongly recommended) or a paragraph-density
heuristic otherwise.

Crawled news content is copyrighted — documents are tagged
redistributable=no from the registry and segregated by the rights manifest.
"""

from __future__ import annotations

import re
import time
import urllib.robotparser
from collections.abc import Iterator
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import requests

from ..schema import Document

USER_AGENT = "nepali-corpus-bot/0.1 (research corpus collection; contact via repo issues)"
REQUEST_DELAY_S = 1.5
_LOC = re.compile(r"<loc>\s*(.*?)\s*</loc>")


class _Session:
    def __init__(self, base_url: str):
        self.http = requests.Session()
        self.http.headers["User-Agent"] = USER_AGENT
        self.base = base_url.rstrip("/")
        self.robots = urllib.robotparser.RobotFileParser()
        try:
            r = self.http.get(urljoin(self.base, "/robots.txt"), timeout=30)
            self.robots.parse(r.text.splitlines() if r.ok else [])
        except requests.RequestException:
            self.robots.parse([])
        self._last = 0.0

    def allowed(self, url: str) -> bool:
        return self.robots.can_fetch(USER_AGENT, url)

    def get(self, url: str) -> str | None:
        wait = REQUEST_DELAY_S - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        try:
            r = self.http.get(url, timeout=30)
            return r.text if r.ok else None
        except requests.RequestException:
            return None


def _sitemap_urls(session: _Session, sitemap_url: str, seen: set[str], depth: int = 0) -> Iterator[str]:
    if depth > 3 or sitemap_url in seen:
        return
    seen.add(sitemap_url)
    body = session.get(sitemap_url)
    if not body:
        return
    locs = _LOC.findall(body)
    is_index = "<sitemapindex" in body
    for loc in locs:
        if is_index or loc.endswith((".xml", ".xml.gz")):
            yield from _sitemap_urls(session, loc, seen, depth + 1)
        else:
            yield loc


def _extract_text(html: str, url: str) -> str:
    try:
        import trafilatura
        return trafilatura.extract(html, url=url, favor_recall=True) or ""
    except ImportError:
        pass
    # fallback: paragraph-density heuristic
    paras = re.findall(r"(?s)<p[^>]*>(.*?)</p>", html)
    cleaned = [re.sub(r"<[^>]+>", " ", p) for p in paras]
    cleaned = [re.sub(r"\s+", " ", p).strip() for p in cleaned]
    return "\n\n".join(p for p in cleaned if len(p) > 60)


def iter_news(source: dict, limit: int | None = None) -> Iterator[Document]:
    base = source["base_url"]
    session = _Session(base)
    sitemap = source.get("sitemap_url", urljoin(base + "/", "sitemap.xml"))

    count = 0
    for url in _sitemap_urls(session, sitemap, seen=set()):
        if limit is not None and count >= limit:
            break
        if urlparse(url).netloc != urlparse(base).netloc or not session.allowed(url):
            continue
        html = session.get(url)
        if not html:
            continue
        text = _extract_text(html, url)
        if not text:
            continue
        count += 1
        yield Document(
            text=text,
            source=source["name"],
            url=url,
            license=str(source.get("license", "copyrighted")),
            redistributable=str(source.get("redistributable", "no")),
        )
