#!/usr/bin/env python3
"""Prints the aggregate numbers of the review from the included works of the charting form."""
import re
import statistics as st

from survey_protocol import AREAS, CRITERIA, ROOT, THRESHOLD, read_csv

rows = [r for r in read_csv(ROOT / "data" / "assistant" / "ft_results.csv") if r["decision"] == "include"]
YEARS = sorted({int(r["year"]) for r in rows})


def count(rs, q): return sum(int(r[q]) for r in rs)
def mean(rs): return st.mean(int(r["score"]) for r in rs)


def show(name, rs):
    crit = "  ".join(f"Q{i + 1}={count(rs, q):3d} ({100 * count(rs, q) / len(rs):5.1f}%)" for i, q in enumerate(CRITERIA))
    print(f"{name:36s} n={len(rs):4d}  mean={mean(rs):.2f}  {crit}  score>={THRESHOLD}: "
          f"{sum(int(r['score']) >= THRESHOLD for r in rs)}")


show("All areas", rows)
for area in sorted(AREAS, key=lambda a: -mean([r for r in rows if r["area"] == str(a)])):
    show(AREAS[area][1], [r for r in rows if r["area"] == str(area)])
ris, other = [r for r in rows if r["ris"] == "1"], [r for r in rows if r["ris"] == "0"]
show("With RIS", ris)
show("Without RIS", other)
for year in YEARS:
    show(f"Published in {year}", [r for r in rows if int(r["year"]) == year])
print("Score histogram:", {s: sum(int(r["score"]) == s for r in rows) for s in range(6)})
gap = {f"Q{i + 1}": round(count(other, q) / len(other) - count(ris, q) / len(ris), 3) for i, q in enumerate(CRITERIA)}
print("RIS gap by criterion (points of mean score):", gap, "total", round(mean(other) - mean(ris), 3))

best = [r for r in rows if int(r["score"]) >= THRESHOLD]
rest = [r for r in rows if int(r["score"]) < THRESHOLD]
print("Best-supported works among those meeting each criterion:",
      {f"Q{i + 1}": f"{count(best, q)} of {count(rows, q)}" for i, q in enumerate(CRITERIA)},
      "| the rest meeting it:", {f"Q{i + 1}": f"{100 * count(rest, q) / len(rest):.0f}%" for i, q in enumerate(CRITERIA)})
SOURCES = {"3GPP models or QuaDRiGa": (r"3gpp|\bcdl|\btdl|38\.901|38\.811|36\.777|\bscm\b|spatial channel model|quadriga|"
                                       r"\buma\b|\bumi\b|\beva\b|\betu\b"),
           "DeepMIMO": r"deepmimo", "COST 2100": r"cost[ -]?2100|csinet", "DeepSense 6G": r"deepsense"}
best_q1 = [r for r in best if r["q1"] == "1"]
print("Sources of the best-supported works on a standard or measured channel:",
      {name: sum(bool(re.search(p, r["data_channel"], re.I)) for r in best_q1) for name, p in SOURCES.items()},
      "| any of these:", f"{sum(bool(re.search('|'.join(SOURCES.values()), r['data_channel'], re.I)) for r in best_q1)} of {len(best_q1)}")
APPROACHES = {
    "reinforcement learning": (r"reinforcement|\bdrl\b|\bmarl\b|\brl\b|q-network|\bdqn|\bddqn|\bd3qn|ddpg|\btd3\b|\bppo\b|"
                               r"actor-critic|\bsac\b|bandit|mappo|maddpg|q-learning|qmix|qtran|\ba2c\b|\ba3c\b"),
    "a Transformer": r"transformer|\bvit\b|swin|conformer",
    "a generative model": (r"diffusion(?! graph)|ddpm|ddim|score-based|score network|langevin|flow matching|flow-matching|"
                           r"normalizing flow|\bgans?\b|\bwgan|\bcgan|dcgan|\bvaes?\b|vq-vae|variational autoencoder|generative"),
    "a graph network": (r"\bgnns?\b|graph neural|graph attention|graph convolution|\bgcn|\bgat\b|graph network|graph transformer|"
                        r"hypergraph|heterogeneous graph|graph-based neural|graph learning"),
}
for name, pattern in APPROACHES.items():
    show(f"Method uses {name}", [r for r in rows if re.search(pattern, r["method"], re.I)])
rl = [r for r in rows if re.search(APPROACHES["reinforcement learning"], r["method"], re.I)]
both = [r for r in rows if r["preprint_marks"]]
print("Graded on both versions:", len(both), "| marks that agree:",
      f"{sum(p == a for r in both for p, a in zip(r['preprint_marks'], r['assistant_marks']))} of {5 * len(both)}",
      "| reach the threshold only on the published version:",
      sum(int(r["preprint_score"]) < THRESHOLD <= r["assistant_marks"].count("1") for r in both),
      "| fall below it:", sum(int(r["preprint_score"]) >= THRESHOLD > r["assistant_marks"].count("1") for r in both))
fixed = [(i, r) for r in rows for i, q in enumerate(CRITERIA) if r["assistant_marks"][i] != r[q]]
print("Marks corrected by the author:",
      {f"Q{i + 1} from {a} to {1 - a}": sum(j == i and int(r["assistant_marks"][i]) == a for j, r in fixed)
       for i in sorted({i for i, _ in fixed}) for a in (1, 0)},
      "| best-supported on the marks of the assistant:", sum(r["assistant_marks"].count("1") >= THRESHOLD for r in rows),
      "| after the corrections:", sum(int(r["score"]) >= THRESHOLD for r in rows))
show("Method without reinforcement learning", [r for r in rows if r not in rl])
print("Reinforcement learning by area:",
      {AREAS[a][0]: f"{sum(r['area'] == str(a) for r in rl)} of {sum(r['area'] == str(a) for r in rows)}" for a in AREAS},
      "| with a RIS:", f"{sum(r['ris'] == '1' for r in rl)} of {len(ris)}")
