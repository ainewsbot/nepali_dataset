# Datasheet: Nepali text corpus

## Purpose

Improve the ability of AI language models to reliably and accurately produce
Nepali text. Nepali is severely under-resourced relative to its ~32M speakers;
existing multilingual corpora contain a few GB of heavily-overlapping,
noisy Nepali. This corpus aggregates everything collectable, cleaned and
deduplicated, with per-document provenance.

## Collection policy and rights

The operating policy is **collect everything, sort rights later**. Concretely:

- Nothing is excluded from *collection* on license grounds.
- Every document carries `source`, `url`, `license`, and `redistributable`
  (yes / no / unknown) inherited from `sources/registry.yaml` (or per-row
  metadata when the source provides it).
- `python -m nepali_corpus.cli report` partitions the corpus by rights at any
  time. **Only the `redistributable: yes` partition may be published** (e.g.
  to Hugging Face Hub); the rest is for internal training use pending a
  rights review, and jurisdiction-specific legal advice applies.
- Crawled news content is copyrighted and always tagged `redistributable: no`.
  The crawler respects robots.txt, identifies itself, and rate-limits.

## Scope decisions

- **Language**: Devanagari Nepali only. Hindi, Sanskrit, Maithili, Bhojpuri
  and Romanized (Latin-script) Nepali are treated as contaminants and
  filtered out. Revisit if a colloquial/dialogue register is needed.
- **Registers covered** (via registry tiers): web text, edited news, an
  encyclopedia, classic literature, legal/government formal register,
  ASR transcripts (colloquial).

## Processing

1. Unicode NFC normalization, whitespace/control-char cleanup.
2. Language ID: ≥50% Devanagari characters AND Nepali-marker score ≥0.1
   (closed-class function words distinguishing Nepali from Hindi).
3. Quality: length bounds, digit-ratio cap, degenerate-word check.
   Rejections are logged with reasons under `data/rejected/` for auditing.
4. Dedup: exact (SHA1 of punctuation-stripped canonical form), then MinHash
   LSH near-dedup (word 5-gram shingles, Jaccard threshold 0.8), shared
   across all sources in a run — keep-first by collection order.

## Known limitations

- Marker-based language ID is precise but crude; very short or heavily
  code-mixed documents are rejected. A fastText classifier fine-tuned for
  Nepali-vs-Hindi is a planned upgrade.
- The wikitext stripper is regex-based (best-effort); prefer the pre-cleaned
  HF Wikipedia mirror when available.
- No PII scrubbing yet — required before any public release of crawled
  partitions.
