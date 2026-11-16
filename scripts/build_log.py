#!/usr/bin/env python3
"""Builds the screening log from the OpenAlex export."""
import argparse
import csv
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

from survey_protocol import DECISIONS, LOG_FIELDS, ROOT, dedup, from_openalex, outside_filter, sort_key


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", help="folder written by search_openalex.py fetch")
    parser.add_argument("--out", default=str(ROOT / "data"), help="folder of the log (default data/)")
    args = parser.parse_args(argv)
    log, summary_path = Path(args.out) / "screening_log.csv", Path(args.out) / "search" / "log_summary.json"
    for p in (log, summary_path):
        if p.exists():
            raise SystemExit(f"{p} already exists and may hold decisions; it is never overwritten")
    with open(Path(args.export) / "records.jsonl", encoding="utf-8") as f:
        records = [from_openalex(json.loads(line)) for line in f]
    unique, same_title = dedup(records)
    shared = {doi for dois in same_title for doi in dois}
    rows = []
    for r in sorted(unique, key=sort_key):
        flags = (["outside_filter"] if outside_filter(r) else []) + (["same_title_other_doi"] if r["doi"] in shared else [])
        rows.append({**{f: r.get(f, "") for f in LOG_FIELDS}, "flags": " ".join(flags), **{f: "" for f in DECISIONS}})
    summary = {"built_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "export": str(args.export),
               "identified": len(records), "duplicates_removed": len(records) - len(unique), "to_screen": len(rows),
               "flags": dict(Counter(f for r in rows for f in r["flags"].split())),
               "same_title_other_doi": same_title, "python": sys.version.split()[0]}
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        w.writeheader()
        w.writerows(rows)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=1)
    print(f"identified {len(records):,}, duplicates removed {summary['duplicates_removed']:,}, to screen {len(rows):,}; "
          f"flags {summary['flags']}")
    print("written:", log, summary_path, sep="\n  ")
    return summary


if __name__ == "__main__":
    main()
