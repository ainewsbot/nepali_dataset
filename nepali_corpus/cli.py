"""Command-line interface.

  python -m nepali_corpus.cli sources                 # list registry
  python -m nepali_corpus.cli collect fineweb2 --limit 10000
  python -m nepali_corpus.cli collect --tier 1        # all priority-1 sources
  python -m nepali_corpus.cli report                  # corpus totals + rights partition
"""

from __future__ import annotations

import argparse
import json
import sys

from .pipeline import collect, corpus_report
from .registry import load_registry


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nepali_corpus")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sources", help="list registered sources")

    c = sub.add_parser("collect", help="collect, filter and dedup sources")
    c.add_argument("names", nargs="*", help="registry source names")
    c.add_argument("--tier", type=int, help="collect all sources at this priority")
    c.add_argument("--limit", type=int, help="max documents per source (for testing)")

    sub.add_parser("report", help="aggregate corpus report with rights partition")

    args = p.parse_args(argv)

    if args.cmd == "sources":
        for name, s in load_registry().items():
            print(f"{name:32} p{s.get('priority', '?')} {s.get('access', 'manual'):10} "
                  f"redist={s.get('redistributable', '?'):8} {s.get('est_size', '')}")
        return 0

    if args.cmd == "collect":
        names = list(args.names)
        if args.tier is not None:
            names += [n for n, s in load_registry().items()
                      if s.get("priority") == args.tier and s.get("access") != "manual"
                      and n not in names]
        if not names:
            print("nothing to collect: pass source names or --tier", file=sys.stderr)
            return 2
        stats = collect(names, limit=args.limit)
        for s in stats:
            print(json.dumps(s.to_json(), ensure_ascii=False))
        return 0

    if args.cmd == "report":
        print(json.dumps(corpus_report(), ensure_ascii=False, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
