# nepali_dataset

A pipeline for building the largest possible corpus of written Nepali, to
improve how reliably AI models produce Nepali text.

**Policy: collect everything, sort rights later.** Every document permanently
carries its source, URL, license and a `redistributable` flag, so the corpus
can be partitioned by rights at any time without re-collecting anything. See
[docs/DATASHEET.md](docs/DATASHEET.md) before redistributing any of it.

## Layout

```
sources/registry.yaml    every known source of Nepali text: size, license, access method
nepali_corpus/           the pipeline
  downloaders/           hf (HuggingFace streaming), wikimedia (XML dumps),
                         news (polite sitemap crawler), local (files/PDF extractions)
  filtering.py           Devanagari + Nepali-vs-Hindi language ID, quality filters
  dedup.py               exact (SHA1) + near (MinHash LSH) deduplication
  pipeline.py            source -> filter -> dedup -> sharded jsonl.zst + manifests
data/                    output (gitignored — the corpus never lives in git)
  clean/<source>/        accepted documents, zstd-compressed JSONL shards
  rejected/<source>      rejected docs with reasons (audit trail)
  manifests/<source>     per-source stats + rights info
```

## Usage

```bash
pip install -r requirements.txt

python -m nepali_corpus.cli sources              # list the registry
python -m nepali_corpus.cli collect fineweb2 --limit 10000   # trial run
python -m nepali_corpus.cli collect --tier 1     # all priority-1 sources, cross-deduped
python -m nepali_corpus.cli report               # corpus totals, partitioned by rights
```

Notes:
- Collect overlapping sources **in one run** — dedup state is shared across
  the run, so priority order determines which copy of a duplicate survives.
- Gated HF datasets (CulturaX, OSCAR) need `HF_TOKEN` set and accepted terms
  on the hub.
- Collection needs ordinary internet access to huggingface.co,
  dumps.wikimedia.org and the news sites in the registry.

## Why the filter is Nepali-specific

Nepali shares Devanagari with Hindi, Sanskrit, Maithili and Bhojpuri, and
generic language ID confuses them constantly. The filter requires documents to
be mostly Devanagari **and** to score as Nepali on closed-class function words
(छ/छन्/हरू/पनि/भयो… vs Hindi है/हैं/नहीं/में…) that are frequent in exactly one
language. Scope decision: Devanagari Nepali only — Romanized Nepali and sister
languages are excluded (they'd be corpus contamination for this purpose).

## Document schema

```json
{"id": "…", "text": "…", "source": "fineweb2", "url": "…",
 "license": "ODC-By 1.0", "redistributable": "yes",
 "lang_score": 0.93, "collected_at": "…", "meta": {}}
```

## Tests

```bash
python -m pytest tests/
```

The suite exercises the full pipeline offline on genuine Nepali fixtures plus
Hindi/English/near-duplicate contaminants.
