#!/usr/bin/env python3
"""Writes the PRISMA 2020 flow diagram of the search as a TikZ picture."""
import argparse
import json
from collections import Counter
from pathlib import Path

from survey_protocol import ROOT, THRESHOLD, read_csv

LABELS = {"source_type": "not a research article", "survey": "surveys and tutorials", "no_learning": "without learning",
          "above_phy": "learning above the physical layer", "function": "another physical-layer function",
          "system": "single antenna without a RIS", "results": "without quantitative results",
          "period": "published before 2024", "language": "not in English"}
LINE = 0.42
GAP = 0.7
WIDTH = {"box": 52, "excluded": 72}
CHARS = {"box": 30, "excluded": 42}


def counts(summary, log, results):
    screened = [r for r in log if r["ta_decision"]]
    passed = [r for r in log if r["ta_decision"] in ("include", "uncertain")]
    assessed = [r for r in passed if r["ft_decision"]]
    included = {r["doi"] for r in assessed if r["ft_decision"] == "include"}
    best = sum(1 for r in results if r["doi"] in included and r["score"] and int(r["score"]) >= THRESHOLD)
    not_retrieved = sum(r["ft_retrieved"] == "no" for r in passed)
    return {"identified": summary["identified"], "duplicates": summary["duplicates_removed"],
            "screened": len(screened), "ta_reasons": Counter(r["ta_reason"] for r in screened if r["ta_decision"] == "exclude"),
            "sought": len(passed), "not_retrieved": not_retrieved, "waiting": len(passed) - not_retrieved - len(assessed),
            "assessed": len(assessed), "ft_reasons": Counter(r["ft_reason"] for r in assessed if r["ft_decision"] == "exclude"),
            "included": len(included), "best": best}


def n(x):
    return f"{x:,}"


def reasons(c):
    label = {k: LABELS.get(k, k) for k in c}
    return [f"{label[k][:1].upper() + label[k][1:]}, {n(v)}" for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))]


def rows(text, kind):
    return sum(-(-len(t) // CHARS[kind]) for t in text)


def tikz(c):
    stages = [("identified", ["Records identified in OpenAlex", n(c["identified"])],
               ("duplicates", ["Duplicates removed", n(c["duplicates"])])),
              ("screened", ["Records screened on the title", "and the abstract", n(c["screened"])],
               ("excludedta", [f"Excluded by both runs, {n(sum(c['ta_reasons'].values()))}"] + reasons(c["ta_reasons"]))),
              ("sought", ["Full texts sought", n(c["sought"])],
               ("waiting", [f"Not retrieved, {n(c['not_retrieved'])}", f"Not yet obtained or read, {n(c['waiting'])}"])),
              ("assessed", ["Full texts assessed", n(c["assessed"])],
               ("excludedft", [f"Excluded by both readings, {n(sum(c['ft_reasons'].values()))}"] + reasons(c["ft_reasons"]))),
              ("included", ["Works included", n(c["included"]), f"Best-supported, {n(c['best'])}"], None)]
    lines = ["% Written by scripts/prisma_flow.py from the screening log; run the script instead of editing this file.",
             "\\begin{tikzpicture}[font=\\small, >={Stealth[length=2mm]},",
             "  box/.style={rounded corners=3pt, draw=black, line width=0.6pt, fill=PalSystem, text=white,",
             "    drop shadow={opacity=0.15, shadow xshift=0.6pt, shadow yshift=-0.6pt},",
             f"    align=center, minimum height=9mm, inner sep=3pt, text width={WIDTH['box']}mm}},",
             f"  excluded/.style={{box, draw=PalAlgo, fill=PalAlgoLight, text=PalAlgo, text width={WIDTH['excluded']}mm}}]"]
    y, prev, br = 0.0, None, "\\\\"
    x = (WIDTH["box"] + WIDTH["excluded"]) / 20 + 1.6
    for i, (name, text, side) in enumerate(stages):
        height = max(rows(text, "box"), rows(side[1], "excluded") if side else 0) * LINE
        if prev is not None:
            y -= prev / 2 + GAP + height / 2
        fill = ", fill=PalMeasured" if name == "included" else ""
        lines.append(f"  \\node[box{fill}] ({name}) at (0,{y:.2f}) {{{br.join(text)}}};")
        if side:
            lines.append(f"  \\node[excluded] ({side[0]}) at ({x:.2f},{y:.2f}) {{{br.join(side[1])}}};")
            lines.append(f"  \\draw[->] ({name}.east) -- ({side[0]}.west);")
        if i:
            lines.append(f"  \\draw[->] ({stages[i - 1][0]}.south) -- ({name}.north);")
        prev = height
    lines += ["\\end{tikzpicture}", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", default=str(ROOT / "data" / "search" / "log_summary.json"))
    parser.add_argument("--log", default=str(ROOT / "data" / "screening_log.csv"))
    parser.add_argument("--results", default=str(ROOT / "data" / "assistant" / "ft_results.csv"))
    parser.add_argument("--out", default=str(ROOT / "figures" / "prisma_flow.tex"))
    args = parser.parse_args(argv)
    results = read_csv(args.results) if Path(args.results).exists() else []
    c = counts(json.loads(Path(args.summary).read_text(encoding="utf-8")), read_csv(args.log), results)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(tikz(c), encoding="utf-8")
    print(f"identified {c['identified']}, screened {c['screened']}, excluded {sum(c['ta_reasons'].values())}, "
          f"sought {c['sought']}, not retrieved {c['not_retrieved']}, waiting {c['waiting']}, assessed {c['assessed']}, "
          f"excluded {sum(c['ft_reasons'].values())}, included {c['included']}, best-supported {c['best']}; "
          f"written to {args.out}")


if __name__ == "__main__":
    main()
