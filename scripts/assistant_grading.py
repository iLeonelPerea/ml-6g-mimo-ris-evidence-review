#!/usr/bin/env python3
"""Merges the full-text readings of the assistant and the author's corrections into the charting form."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

from assistant_screening import write_csv
from survey_protocol import AREAS, CRITERIA, FORM_FIELDS, LOG_FIELDS, ROOT, THRESHOLD, read_csv, score

FT_REASONS = ["source_type", "survey", "no_learning", "above_phy", "function", "system", "results"]
ITEMS = FORM_FIELDS[FORM_FIELDS.index("ris"):FORM_FIELDS.index("q1")]
GRADE_FIELDS = (["doi", "pdf", "version_read", "ft_decision", "ft_reason", "area"] + ITEMS + CRITERIA
                + [q + "_support" for q in CRITERIA] + ["notes"])
PAGE = re.compile(r"\bp\. ?\d+")
RESULT_FIELDS = (["doi", "title", "journal", "year", "version_read", "pdf", "first_decision", "first_reason",
                  "second_decision", "second_reason", "decision", "reason", "source", "area"] + CRITERIA
                 + ["score", "best", "published_needed", "preprint_marks", "preprint_score", "assistant_marks"]
                 + [q + "_support" for q in CRITERIA] + ITEMS + ["first_notes", "second_notes", "published_notes"])


def check(a):
    keys = set(a)
    p = [f"keys missing {sorted(set(GRADE_FIELDS) - keys)} or not expected {sorted(keys - set(GRADE_FIELDS))}"
         ] if keys != set(GRADE_FIELDS) else []
    if p:
        return p
    if a["version_read"] not in ("published", "preprint"):
        p.append(f"version_read={a['version_read']!r}")
    if a["ft_decision"] == "exclude":
        if a["ft_reason"] not in FT_REASONS:
            p.append(f"ft_reason={a['ft_reason']!r} is not in {FT_REASONS}")
        if a["area"] or any(a[q] for q in CRITERIA):
            p.append("area or marks for an excluded work")
    elif a["ft_decision"] == "include":
        if a["ft_reason"]:
            p.append("ft_reason for an included work")
        if a["area"] not in {str(k) for k in AREAS}:
            p.append(f"area={a['area']!r} is not an area from 1 to 7")
        if a["ris"] not in ("0", "1"):
            p.append(f"ris={a['ris']!r}")
        p += [f"{q}={a[q]!r} is not 1 or 0" for q in CRITERIA if a[q] not in ("0", "1")]
        p += [f"{q}_support cites no page" for q in CRITERIA if not PAGE.search(a[q + "_support"])]
    else:
        p.append(f"ft_decision={a['ft_decision']!r}")
    return p


def load(folder):
    return {a["doi"]: a for a in (json.loads(f.read_text(encoding="utf-8")) for f in sorted(Path(folder).glob("*.json")))}


def wrong_pdf(a):
    return a["ft_decision"] == "exclude" and not a["ft_reason"]


def final(first, second):
    if first["ft_decision"] == "include":
        return "include", "", "first"
    if wrong_pdf(first):
        return "wrong_pdf", "", "first"
    if second is None:
        return "pending", first["ft_reason"], "first"
    if second["ft_decision"] == "include":
        return "include", "", "second"
    if wrong_pdf(second):
        return "wrong_pdf", "", "second"
    return "exclude", min(first["ft_reason"], second["ft_reason"], key=FT_REASONS.index), "both"


def corrections(path):
    fixes, bad = {}, []
    for c in read_csv(path):
        where = f"correction {c['doi']} {c['criterion']}"
        if c["criterion"] not in CRITERIA:
            bad.append(f"{where}: the criterion is not one of {CRITERIA}")
            continue
        if (c["assistant"], c["author"]) not in (("0", "1"), ("1", "0")):
            bad.append(f"{where}: the marks {c['assistant']!r} and {c['author']!r} are not a change between 1 and 0")
        if not c["reason"].strip() or not PAGE.search(c["passage"]):
            bad.append(f"{where}: without a reason or without a passage that cites a page")
        if (c["doi"], c["criterion"]) in fixes:
            bad.append(f"{where}: repeated")
        fixes[(c["doi"], c["criterion"])] = c
    return fixes, bad


def pdf_name(path):
    p = Path(path)
    return f"{p.parent.name}/{p.name}" if p.parent.name == "published" else p.name


def merge(args):
    first, second = load(args.first), load(args.second)
    published, published_second = load(args.published), load(args.published_second)
    bad = [f"{d}: {m}" for d, a in [*first.items(), *second.items(), *published.items(), *published_second.items()]
           for m in check(a) if not (wrong_pdf(a) and m.startswith("ft_reason="))]
    bad += [f"{d}: second reading of a work that the first reading does not exclude" for d in second
            if d not in first or first[d]["ft_decision"] != "exclude"]
    bad += [f"{d}: grading on the published version of a work that was not read as a preprint" for d in published
            if d not in first or first[d]["version_read"] != "preprint"]
    bad += [f"{d}: grading in {args.published} that does not read the published version" for d, a in published.items()
            if a["version_read"] != "published"]
    bad += [f"{d}: second reading of a published version that its grading does not exclude" for d in published_second
            if d not in published or published[d]["ft_decision"] != "exclude"]
    if bad:
        for m in bad:
            print("ERROR", m)
        raise SystemExit(f"{len(bad)} problems in the answers; nothing written")
    fixes, wrong = corrections(args.corrections)
    log_rows = read_csv(args.log)
    log = {r["doi"]: r for r in log_rows}
    rows = []
    for doi, a in sorted(first.items()):
        b = second.get(doi)
        decision, reason, source = final(a, b)
        g = b if source == "second" else a
        preprint_marks = preprint_score = ""
        if doi in published:
            if decision == "include":
                preprint_marks, preprint_score = "".join(g[q] for q in CRITERIA), score(g)
            decision, reason, source = final(published[doi], published_second.get(doi))
            g = published_second[doi] if source == "second" else published[doi]
            source = "published_" + source
        marks = {q: g[q] for q in CRITERIA} if decision == "include" else {q: "" for q in CRITERIA}
        support = {q: g[q + "_support"] if decision == "include" else "" for q in CRITERIA}
        assistant_marks = "".join(marks.values())
        for q in CRITERIA:
            c = fixes.pop((doi, q), None)
            if c and (decision != "include" or marks[q] != c["assistant"]):
                wrong.append(f"correction {doi} {q}: the reading that holds " + (f"gives {marks[q]}, not {c['assistant']}"
                             if decision == "include" else "does not include the work"))
            elif c:
                marks[q] = c["author"]
                support[q] = f"Corrected by the author ({c['reason']}): {c['passage']}"
        s = score(marks) if decision == "include" else None
        rec = log.get(doi, {})
        rows.append({"doi": doi, "title": rec.get("title", ""), "journal": rec.get("journal", ""), "year": rec.get("year", ""),
                     "version_read": g["version_read"], "pdf": pdf_name(g["pdf"]), "first_decision": a["ft_decision"],
                     "first_reason": a["ft_reason"], "second_decision": b["ft_decision"] if b else "",
                     "second_reason": b["ft_reason"] if b else "", "decision": decision, "reason": reason, "source": source,
                     "area": g["area"] if decision == "include" else "", **marks, "score": "" if s is None else s,
                     "best": "1" if s is not None and s >= THRESHOLD else "",
                     "published_needed": "1" if s is not None and s >= THRESHOLD - 1 and g["version_read"] == "preprint" else "",
                     "preprint_marks": preprint_marks, "preprint_score": preprint_score,
                     "assistant_marks": assistant_marks, **{q + "_support": support[q] for q in CRITERIA},
                     **{i: g[i] for i in ITEMS}, "first_notes": a["notes"], "second_notes": b["notes"] if b else "",
                     "published_notes": g["notes"] if source.startswith("published") else ""})
    wrong += [f"correction {d} {q}: not a work of the readings" for d, q in fixes]
    if wrong:
        for m in wrong:
            print("ERROR", m)
        raise SystemExit(f"{len(wrong)} problems in the corrections of the author; nothing written")
    write_csv(args.out, RESULT_FIELDS, rows)
    held = {r["doi"]: r for r in rows if r["decision"] in ("include", "exclude")}
    for r in log_rows:
        h = held.get(r["doi"])
        if h:
            r.update(ft_retrieved="yes", version_read=h["version_read"], ft_decision=h["decision"], ft_reason=h["reason"],
                     area=h["area"])
    write_csv(args.log, LOG_FIELDS, log_rows)
    inc = [r for r in rows if r["decision"] == "include"]
    print(f"{len(rows)} works read: {dict(Counter(r['decision'] for r in rows))}; written to {args.out}")
    print(f"included {len(inc)}, best-supported {sum(r['best'] == '1' for r in inc)}, "
          f"published version needed {sum(r['published_needed'] == '1' for r in inc)}, "
          f"kept by the second reading {sum(r['source'].endswith('second') for r in rows)}")
    print("best-supported by area:", ", ".join(f"{code} {sum(r['best'] == '1' and r['area'] == str(k) for r in inc)}"
                                               for k, (code, _) in AREAS.items()))
    fixed = [r for r in inc if r["assistant_marks"] != "".join(r[q] for q in CRITERIA)]
    print(f"marks corrected by the author {sum(m != r[q] for r in fixed for m, q in zip(r['assistant_marks'], CRITERIA))} "
          f"in {len(fixed)} works; best-supported on the marks of the assistant "
          f"{sum(r['assistant_marks'].count('1') >= THRESHOLD for r in inc)}")
    both = [r for r in inc if r["preprint_marks"]]
    if both:
        print(f"graded on the preprint and on the published version {len(both)}: "
              + ", ".join(f"Q{i + 1} agree {sum(r['preprint_marks'][i] == r['assistant_marks'][i] for r in both)}"
                          for i in range(len(CRITERIA)))
              + f"; score up {sum(r['assistant_marks'].count('1') > r['preprint_score'] for r in both)}, "
              f"down {sum(r['assistant_marks'].count('1') < r['preprint_score'] for r in both)}")
    print(f"{len(held)} decisions in the full-text columns of {args.log}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", default=str(ROOT / "data" / "assistant" / "ft_first"))
    parser.add_argument("--second", default=str(ROOT / "data" / "assistant" / "ft_second"))
    parser.add_argument("--published", default=str(ROOT / "data" / "assistant" / "ft_published"))
    parser.add_argument("--published-second", default=str(ROOT / "data" / "assistant" / "ft_published_second"))
    parser.add_argument("--corrections", default=str(ROOT / "data" / "assistant" / "author_corrections.csv"))
    parser.add_argument("--out", default=str(ROOT / "data" / "assistant" / "ft_results.csv"))
    parser.add_argument("--log", default=str(ROOT / "data" / "screening_log.csv"))
    merge(parser.parse_args())
