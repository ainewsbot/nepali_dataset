"""Stream Nepali splits of Hugging Face datasets.

Streaming avoids downloading full multi-hundred-GB multilingual datasets to
get their Nepali slice. Gated datasets (CulturaX, OSCAR) need HF_TOKEN in the
environment and accepted terms on the hub.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..schema import Document

# Field holding the document text, per dataset (default "text").
TEXT_FIELDS = {
    "allenai/madlad-400": "text",
    "uonlp/CulturaX": "text",
    "HuggingFaceFW/fineweb-2": "text",
}
URL_FIELDS = ("url", "URL", "source_url", "uri")


def iter_hf(source: dict, limit: int | None = None) -> Iterator[Document]:
    from datasets import load_dataset

    repo = source["hf_repo"]
    config = source.get("hf_config")
    split = source.get("hf_split", "train")
    text_field = TEXT_FIELDS.get(repo, "text")

    ds = load_dataset(repo, name=config, split=split, streaming=True)

    for i, row in enumerate(ds):
        if limit is not None and i >= limit:
            break
        text = row.get(text_field) or ""
        if not text:
            continue
        url = next((str(row[f]) for f in URL_FIELDS if row.get(f)), "")
        yield Document(
            text=text,
            source=source["name"],
            url=url,
            license=str(source.get("license", "unknown")),
            redistributable=str(source.get("redistributable", "unknown")),
            meta={"hf_repo": repo, "hf_config": config},
        )
