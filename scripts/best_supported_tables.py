#!/usr/bin/env python3
"""Writes the table of each area with its included works of highest score, as LaTeX."""
import argparse
from pathlib import Path

from survey_protocol import AREAS, CRITERIA, ROOT, read_csv

TABLES = {1: ("det", "MIMO detection"),
          2: ("csi", "channel estimation and feedback"),
          3: ("bf", "beamforming and RIS configuration"),
          4: ("otfs", "OTFS for high mobility"),
          5: ("isac", "ISAC"),
          6: ("ntn", "NTN"),
          7: ("fl", "federated learning over the air")}
COLUMNS = "P{0.85cm}P{2.8cm}P{5.6cm}P{3.7cm}C{0.47cm}C{0.47cm}C{0.47cm}C{0.47cm}C{0.47cm}C{0.9cm}"
HEADER = ("\\rowcolor{TableHeaderBand}\n\\textbf{Ref.} & \\textbf{Method} & \\textbf{Function} & \\textbf{Channel or data} & "
          + " & ".join(f"\\textbf{{Q{i}}}" for i in range(1, 6)) + " & \\textbf{Score} \\\\")
CAP = 30


def ranked(area, results, dates):
    return sorted((r for r in results if r["decision"] == "include" and r["area"] == str(area)),
                  key=lambda r: (-int(r["score"]), -int(dates[r["doi"].lower()].replace("-", "")), r["doi"]))


def problems(results, cells, dates):
    included = {r["doi"]: r for r in results if r["decision"] == "include"}
    out = [f"{d}: included, without a publication date in the screening log" for d in included
           if not dates.get(d.lower())]
    if out:
        return out
    shown = {r["doi"] for area in AREAS for r in ranked(area, results, dates)[:CAP]}
    seen = set()
    for c in cells:
        if c["doi"] in seen:
            out.append(f"{c['doi']}: more than one row in the cells")
        seen.add(c["doi"])
        r = included.get(c["doi"])
        if r is None:
            out.append(f"{c['doi']}: a row in the cells, but the readings do not include it")
        elif c["area"] != r["area"]:
            out.append(f"{c['doi']}: area {c['area']} in the cells, {r['area']} in the readings")
        elif r["best"] != "1" and c["doi"] not in shown:
            out.append(f"{c['doi']}: a row in the cells for a work below the threshold that no table shows")
        out += [f"{c['doi']}: empty {k}" for k in ("method", "function", "data") if not c[k].strip()]
    out += [f"{d}: best-supported, without a row in the cells" for d, r in included.items()
            if r["best"] == "1" and d not in seen]
    out += [f"{d}: shown in the table of its area, without a row in the cells" for d in sorted(shown)
            if d not in seen and included[d]["best"] != "1"]
    return out


def citation_orders(path):
    orders = {area: {} for area in AREAS}
    for r in read_csv(path):
        order = orders[int(r["area"])]
        order[r["key"]] = len(order)
    return orders


def caption_count(what, n_rows, n_best_rows, n_best, n_included):
    if n_best > CAP:
        return f"The {n_rows} best-supported works on {what} with the highest scores, of {n_best} in total."
    if n_best_rows == n_rows:
        return f"The {n_rows} best-supported works on {what}." if n_rows > 1 else f"The only best-supported work on {what}."
    best = {0: "none of them best-supported", 1: "one of them best-supported"}.get(n_best_rows,
                                                                                    f"{n_best_rows} of them best-supported")
    if n_rows == 1:
        return f"The only work on {what}, which is not best-supported."
    if n_included > CAP:
        return f"The {n_rows} works on {what} with the highest scores, of {n_included} in total, {best}."
    return f"The {n_rows} works on {what}, {best}."


def table(area, cells, results, order, dates):
    name, what = TABLES[area]
    grade = {r["doi"]: r for r in results}
    cell = {c["doi"]: c for c in cells}
    ranking = ranked(area, results, dates)
    rank = {r["doi"]: i for i, r in enumerate(ranking)}
    rows = sorted((cell[r["doi"]] for r in ranking[:CAP]), key=lambda c: (order.get(c["key"], len(order)), rank[c["doi"]]))
    which = caption_count(what, len(rows), sum(grade[c["doi"]]["best"] == "1" for c in rows),
                          sum(r["best"] == "1" for r in ranking), len(ranking))
    caption = (f"{which} Columns Q1 to Q5 are the criteria of Table~\\ref{{tab:rubric}}, with a check mark when met "
               "and a cross when not.")
    lines = ["% Written by scripts/best_supported_tables.py from the readings and data/best_supported_cells.csv; run the",
             "% script instead of editing this file.",
             "\\begin{table*}[!tp]", "\\centering", "\\footnotesize\\setlength{\\tabcolsep}{2.5pt}",
             f"\\caption{{{caption}}}", f"\\label{{tab:{name}}}",
             f"\\begin{{tabular}}{{{COLUMNS}}}", "\\toprule", HEADER, "\\midrule"]
    for c in rows:
        g = grade[c["doi"]]
        marks = " & ".join("\\yes" if g[q] == "1" else "\\no" for q in CRITERIA)
        lines.append(f"\\cite{{{c['key']}}} & {c['method']} & {c['function']} & {c['data']} & {marks} & {g['score']} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table*}", ""]
    return "\n".join(lines), len(rows), [c["key"] for c in rows if c["key"] not in order]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default=str(ROOT / "data" / "assistant" / "ft_results.csv"))
    parser.add_argument("--cells", default=str(ROOT / "data" / "best_supported_cells.csv"))
    parser.add_argument("--order", default=str(ROOT / "data" / "citation_order.csv"))
    parser.add_argument("--log", default=str(ROOT / "data" / "screening_log.csv"))
    parser.add_argument("--out", default=str(ROOT / "figures"))
    args = parser.parse_args(argv)
    results, cells = read_csv(args.results), read_csv(args.cells)
    dates = {r["doi"].lower(): r["publication_date"] for r in read_csv(args.log)}
    orders = citation_orders(args.order)
    bad = problems(results, cells, dates)
    if bad:
        for m in bad:
            print("ERROR", m)
        raise SystemExit(f"{len(bad)} problems in the cells; nothing written")
    tables = {area: table(area, cells, results, orders[area], dates) for area in AREAS}
    Path(args.out).mkdir(parents=True, exist_ok=True)
    for area, (text, n, uncited) in tables.items():
        (Path(args.out) / f"tab_{TABLES[area][0]}.tex").write_text(text, encoding="utf-8")
        if uncited:
            print(f"{AREAS[area][0]}: {len(uncited)} of its {n} rows are not cited in its section and follow the cited "
                  "ones from the highest score down")
    best = {area: sum(r["best"] == "1" for r in ranked(area, results, dates)) for area in AREAS}
    shown = {area: sum(r["best"] == "1" for r in ranked(area, results, dates)[:CAP]) for area in AREAS}
    written = ", ".join(f"{AREAS[area][0]} {n} ({shown[area]} of its {best[area]} best-supported, {n - shown[area]} below)"
                        for area, (_, n, _) in tables.items())
    print(f"rows in the tables by area: {written}; "
          f"{sum(n for _, n, _ in tables.values())} rows written to {args.out}/tab_*.tex")


if __name__ == "__main__":
    main()
