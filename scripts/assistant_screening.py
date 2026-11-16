#!/usr/bin/env python3
"""Screening of titles and abstracts: batches for the assistant, merge of its two runs, and the agreed exclusions."""
import argparse
import csv
import json
from pathlib import Path

from survey_protocol import LOG_FIELDS, REASONS, ROOT, read_csv

TA_ORDER = ["source_type", "survey", "no_learning", "above_phy", "function", "system", "results"]
DECISIONS = {"include", "exclude", "uncertain"}
INPUT_FIELDS = ["doi", "title", "journal", "year", "abstract"]
PROPOSAL_FIELDS = ["doi", "title", "batch", "first_decision", "first_reason", "first_function", "first_note",
                   "second_decision", "second_reason", "second_note", "proposal", "proposal_reason"]
REVIEW_FIELDS = ["n", "doi", "title", "journal", "proposal_reason", "first_note", "second_reason", "second_note",
                 "reviewer", "abstract"]


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_csv(path, fields, rows):
    tmp = Path(str(path) + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def batch_files(folder):
    return sorted(Path(folder).glob("batch_*.jsonl"))


def check_answers(answers, expected):
    p, seen = [], [a.get("doi", "") for a in answers]
    if sorted(seen) != sorted(expected):
        missing, extra = set(expected) - set(seen), set(seen) - set(expected)
        dup = len(seen) - len(set(seen))
        p.append(f"{len(missing)} DOIs missing, {len(extra)} not in the batch, {dup} repeated")
    for a in answers:
        if a.get("decision") not in DECISIONS:
            p.append(f"{a.get('doi')}: decision {a.get('decision')!r}")
        elif a["decision"] == "exclude" and a.get("reason") not in TA_ORDER:
            p.append(f"{a.get('doi')}: reason {a.get('reason')!r} is not in {TA_ORDER}")
        elif a["decision"] != "exclude" and a.get("reason"):
            p.append(f"{a.get('doi')}: reason without an exclusion")
    return p


def runs(args):
    out, problems = [], []
    for path in batch_files(args.folder / "ta_input"):
        records = read_jsonl(path)
        first_path, second_path = args.folder / "ta_first" / path.name, args.folder / "ta_second" / path.name
        first = read_jsonl(first_path) if first_path.exists() else None
        second = read_jsonl(second_path) if second_path.exists() else None
        if first is None:
            problems.append(f"{path.name}: no answers of the first run")
        else:
            problems += [f"{path.name}, first run: {m}" for m in check_answers(first, [r["doi"] for r in records])]
            excluded = [a["doi"] for a in first if a.get("decision") == "exclude"]
            if second is None and excluded:
                problems.append(f"{path.name}: no answers of the second run for {len(excluded)} exclusions")
            elif second is not None:
                problems += [f"{path.name}, second run: {m}" for m in check_answers(second, excluded)]
        out.append((path.stem, records, first or [], second or []))
    return out, problems


def cmd_batches(args):
    target = args.folder / "ta_input"
    if target.exists():
        raise SystemExit(f"{target} already exists; the batches are never overwritten")
    rows = read_csv(args.log)
    target.mkdir(parents=True)
    for k in range(args.n):
        part = rows[k::args.n]
        with open(target / f"batch_{k + 1:02d}.jsonl", "w", encoding="utf-8") as f:
            f.writelines(json.dumps({x: r[x] for x in INPUT_FIELDS}, ensure_ascii=False) + "\n" for r in part)
    print(f"{len(rows)} records in {args.n} batches of {len(rows) // args.n} or {-(-len(rows) // args.n)}, in {target}")


def proposal(first, second):
    if first["decision"] != "exclude":
        return first["decision"], ""
    if second is None or second["decision"] != "exclude":
        return "uncertain", ""
    return "exclude", min(first["reason"], second["reason"], key=TA_ORDER.index)


def cmd_merge(args):
    batches, problems = runs(args)
    if problems:
        for m in problems:
            print("ERROR", m)
        raise SystemExit(f"{len(problems)} problems in the answers; nothing written")
    rows, review = [], []
    for name, records, first, second in batches:
        f, s = {a["doi"]: a for a in first}, {a["doi"]: a for a in second}
        for r in records:
            a, b = f[r["doi"]], s.get(r["doi"])
            decision, reason = proposal(a, b)
            rows.append({"doi": r["doi"], "title": r["title"], "batch": name, "first_decision": a["decision"],
                         "first_reason": a.get("reason", ""), "first_function": a.get("function", ""),
                         "first_note": a.get("note", ""), "second_decision": b["decision"] if b else "",
                         "second_reason": b.get("reason", "") if b else "", "second_note": b.get("note", "") if b else "",
                         "proposal": decision, "proposal_reason": reason})
            if decision == "exclude":
                review.append({"doi": r["doi"], "title": r["title"], "journal": r["journal"], "proposal_reason": reason,
                               "first_note": a.get("note", ""), "second_reason": b["reason"],
                               "second_note": b.get("note", ""), "reviewer": "", "abstract": r["abstract"]})
    rows.sort(key=lambda r: r["doi"])
    review.sort(key=lambda r: (TA_ORDER.index(r["proposal_reason"]), r["doi"]))
    for i, r in enumerate(review, 1):
        r["n"] = i
    sheet = args.folder / "ta_exclusions_review.csv"
    if sheet.exists() and any(r["reviewer"] for r in read_csv(sheet)):
        raise SystemExit(f"{sheet} already holds checks of the reviewer; it is never overwritten")
    write_csv(args.folder / "ta_proposals.csv", PROPOSAL_FIELDS, rows)
    write_csv(sheet, REVIEW_FIELDS, review)
    passing = {r["doi"]: r["proposal"] for r in rows if r["proposal"] != "exclude"}
    log = read_csv(args.log)
    filled = 0
    for r in log:
        if r["doi"] in passing and not r["ta_decision"]:
            r["ta_decision"], filled = passing[r["doi"]], filled + 1
    write_csv(args.log, LOG_FIELDS, log)
    count = {d: sum(r["proposal"] == d for r in rows) for d in sorted(DECISIONS)}
    print(f"proposals for {len(rows)} records {count}; both runs agree on {len(review)} exclusions, which the "
          f"reviewer checks in {sheet}")
    print(f"{filled} records that pass to the full text recorded in {args.log}")


def cmd_apply(args):
    sheet = read_csv(args.folder / "ta_exclusions_review.csv")
    allowed = {"ok", "include", "uncertain"} | set(REASONS)
    bad = [r for r in sheet if r["reviewer"].strip() and r["reviewer"].strip() not in allowed]
    for r in bad:
        print(f"ERROR row {r['n']} {r['doi']}: reviewer {r['reviewer']!r} is not ok, include, uncertain, or a reason code")
    if bad:
        raise SystemExit(1)
    checked = {r["doi"]: r for r in sheet if r["reviewer"].strip() or args.agreed}
    log = read_csv(args.log)
    applied = changed = 0
    for r in log:
        c = checked.get(r["doi"])
        if not c or r["ta_decision"]:
            continue
        mark = c["reviewer"].strip() or "ok"
        if mark in ("include", "uncertain"):
            r["ta_decision"], changed = mark, changed + 1
        else:
            r["ta_decision"], r["ta_reason"] = "exclude", c["proposal_reason"] if mark == "ok" else mark
        applied += 1
    write_csv(args.log, LOG_FIELDS, log)
    by_reviewer = sum(1 for r in sheet if r["reviewer"].strip())
    print(f"{by_reviewer} of {len(sheet)} proposed exclusions checked by the reviewer"
          + (f" and {len(checked) - by_reviewer} taken as both runs agreed" if args.agreed else "")
          + f"; {applied} recorded in the log now, of which {changed} pass to the full text")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["batches", "merge", "apply"])
    parser.add_argument("--n", type=int, default=10, help="number of batches")
    parser.add_argument("--agreed", action="store_true", help="apply: record the blank rows as both runs agreed")
    parser.add_argument("--log", default=str(ROOT / "data" / "screening_log.csv"))
    parser.add_argument("--folder", type=Path, default=ROOT / "data" / "assistant")
    args = parser.parse_args()
    {"batches": cmd_batches, "merge": cmd_merge, "apply": cmd_apply}[args.command](args)
