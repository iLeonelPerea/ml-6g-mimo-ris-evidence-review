#!/usr/bin/env python3
"""Draws the evidence figures of the review from the included works of the charting form."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from survey_protocol import AREAS as AREA_NAMES, CRITERIA, ROOT, read_csv

BLUE, ORANGE, BLACK, GRID, LIGHT_BLUE = "#0072B2", "#D55E00", "#000000", "#BBBBBB", "#D6E4F5"
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)
rows = [r for r in read_csv(ROOT / "data" / "assistant" / "ft_results.csv") if r["decision"] == "include"]
Q = CRITERIA
QLAB = ["Standard\nor measured\nchannel", "Tests in\nnew\nconditions", "Classical\nand learned\nbaselines",
        "Reported\ncomplexity", "Open code\nor data"]
AREAS = [str(k) for k in AREA_NAMES]
ALAB = [name for _, name in AREA_NAMES.values()]

FS = 9
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["cmr10"], "mathtext.fontset": "cm",
    "axes.formatter.use_mathtext": True, "axes.unicode_minus": False,
    "font.size": FS, "axes.labelsize": FS, "xtick.labelsize": FS, "ytick.labelsize": FS, "legend.fontsize": FS,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "hatch.linewidth": 0.5,
})
EDGE = dict(edgecolor=BLACK, linewidth=0.6)
MAP = LinearSegmentedColormap.from_list("survey_blue", ["#FFFFFF", LIGHT_BLUE, BLUE])


def grid(ax):
    ax.yaxis.grid(True, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


def share(rs):
    return [100 * np.mean([int(r[q]) for r in rs]) for q in Q]


def mean(rs):
    return np.mean([int(r["score"]) for r in rs])


areas = [(lab, [r for r in rows if r["area"] == a]) for a, lab in zip(AREAS, ALAB)]
areas.sort(key=lambda x: -mean(x[1]))
groups = areas + [("All areas", rows)]
mat = np.array([share(g) for _, g in groups])
fig, ax = plt.subplots(figsize=(5.9, 3.2))
ax.imshow(mat, cmap=MAP, vmin=0, vmax=100, aspect="auto")
ax.vlines(np.arange(0.5, 4.5), -0.5, len(groups) - 0.5, color="white", lw=1.2)
ax.hlines(np.arange(0.5, len(groups) - 1), -0.5, 4.5, color="white", lw=1.2)
for i in range(mat.shape[0]):
    for j in range(5):
        ax.text(j, i, f"{mat[i, j]:.0f}", ha="center", va="center", color="white" if mat[i, j] >= 80 else "black")
    ax.text(5.1, i, f"{mean(groups[i][1]):.2f}", ha="center", va="center")
ax.text(5.1, -0.62, "Mean\nscore", ha="center", va="bottom")
ax.set_xlim(-0.5, 5.55)
ax.set_xticks(range(5)); ax.set_xticklabels(QLAB)
ax.xaxis.tick_top()
ax.set_yticks(range(len(groups)))
ax.set_yticklabels([f"{lab} ({len(g):,})" for lab, g in groups])
ax.axhline(len(areas) - 0.5, color="black", lw=0.8)
ax.tick_params(length=0)
for s in ax.spines.values():
    s.set_visible(False)
fig.savefig(OUT / "evidence_map.pdf", bbox_inches="tight"); plt.close(fig)

cnt = [sum(1 for r in rows if int(r["score"]) == s) for s in range(6)]
fig, ax = plt.subplots(figsize=(3.0, 1.9))
ax.bar(range(6), cnt, 0.65, color=BLUE, **EDGE)
grid(ax)
for s, c in enumerate(cnt):
    ax.text(s, c + 0.01 * max(cnt), str(c), ha="center", va="bottom", color=BLUE)
ax.set_xticks(range(6)); ax.set_xlabel("Score (criteria met, out of 5)")
ax.set_ylabel("Number of works"); ax.set_ylim(0, 1.12 * max(cnt))
fig.savefig(OUT / "score_hist.pdf", bbox_inches="tight"); plt.close(fig)

ris = [r for r in rows if r["ris"] == "1"]; nris = [r for r in rows if r["ris"] == "0"]
fig, ax = plt.subplots(figsize=(4.8, 2.3))
x = np.arange(5); w = 0.38
ax.bar(x - w / 2, share(nris), w, color=BLUE, **EDGE, label=f"Without RIS ({len(nris)} works)")
ax.bar(x + w / 2, share(ris), w, color=ORANGE, hatch="//", **EDGE,
       label=f"With RIS ({len(ris)} works)")
grid(ax)
for xs, vals, col in ((x - w / 2, share(nris), BLUE), (x + w / 2, share(ris), ORANGE)):
    for xi, v in zip(xs, vals):
        ax.text(xi, v + 1.5, f"{v:.0f}", ha="center", va="bottom", color=col)
ax.set_xticks(x); ax.set_xticklabels(QLAB)
ax.set_ylabel("Works meeting\nthe criterion (%)"); ax.set_ylim(0, 100)
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
fig.savefig(OUT / "ris_compare.pdf", bbox_inches="tight"); plt.close(fig)

periods = [(str(y), y, y) for y in sorted({int(r["year"]) for r in rows})]
pm = [[r for r in rows if lo <= int(r["year"]) <= hi] for _, lo, hi in periods]
fig, ax = plt.subplots(figsize=(3.6, 1.9))
ax.bar(range(len(pm)), [mean(p) for p in pm], 0.55, color=BLUE, **EDGE)
grid(ax)
for i, p in enumerate(pm):
    ax.text(i, mean(p) + 0.06, f"{mean(p):.2f}", ha="center", va="bottom", color=BLUE)
ax.set_xticks(range(len(pm))); ax.set_xticklabels([f"{lab}\n({len(q)} works)" for (lab, _, _), q in zip(periods, pm)])
ax.set_ylabel("Mean score"); ax.set_ylim(0, max(mean(p) for p in pm) + 0.5)
fig.savefig(OUT / "period_scores.pdf", bbox_inches="tight"); plt.close(fig)
print("wrote evidence_map.pdf, score_hist.pdf, ris_compare.pdf, period_scores.pdf in", OUT)
