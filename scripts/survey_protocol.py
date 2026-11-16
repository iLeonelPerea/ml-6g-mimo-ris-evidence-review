#!/usr/bin/env python3
"""Search terms, journals, areas, criteria, and shared helpers of the review."""
import csv
import html
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

A = ('("machine learning" OR "deep learning" OR "neural network" OR "reinforcement learning" OR '
     '"federated learning" OR "learning-based" OR "deep unfolding" OR "graph neural" OR "transformer" OR '
     '"generative" OR "diffusion model" OR "language model" OR "meta-learning" OR '
     '"artificial intelligence" OR "data-driven" OR "autoencoder" OR "convolutional" OR "LSTM")')
B = '("MIMO" OR "multiple-input multiple-output" OR "multi-antenna" OR "multiple antennas" OR "antenna array")'
C = ('("reconfigurable intelligent surface" OR "intelligent reflecting surface" OR "RIS" OR "IRS" OR '
     '"metasurface" OR "large intelligent surface" OR "STAR-RIS")')
D1 = ('("MIMO detection" OR "MIMO detector" OR "signal detection" OR "symbol detection" OR "data detection" OR '
      '"multiuser detection" OR "multi-user detection" OR "decoding" OR "demodulation" OR "demodulator" OR '
      '"equalization" OR "equalizer")')
D2 = ('("channel estimation" OR "channel estimator" OR "CSI feedback" OR "CSI compression" OR "channel feedback" OR '
      '"channel prediction" OR "CSI prediction" OR "channel modeling" OR "channel modelling" OR '
      '"channel generation" OR "CSI acquisition")')
D3 = ('("beamforming" OR "precoding" OR "precoder" OR "beam training" OR "beam prediction" OR '
      '"beam selection" OR "beam management")')
D4 = '("OTFS" OR "orthogonal time frequency space" OR "delay-Doppler")'
D5 = ('("integrated sensing and communication" OR "integrated sensing and communications" OR "ISAC" OR '
      '"dual-function radar" OR "joint radar and communication" OR "joint communication and sensing")')
D6 = '("satellite" OR "non-terrestrial" OR "high-altitude platform" OR "UAV" OR "unmanned aerial vehicle")'
D7 = '("beam" OR "beamforming" OR "precoding" OR "power allocation" OR "power control" OR "resource allocation")'
D8 = '("over-the-air" OR "AirComp" OR "analog aggregation")'
SEARCH = f'({A} AND ({C} OR ({B} AND ({D1} OR {D2} OR {D3})) OR {D4} OR {D5} OR ({D6} AND {D7}))) OR ("federated" AND {D8})'

AREAS = {1: ("DET", "MIMO detection"), 2: ("CSI", "Channel estimation and feedback"),
         3: ("BF-RIS", "Beamforming and RIS configuration"), 4: ("OTFS", "OTFS for high mobility"),
         5: ("ISAC", "ISAC"), 6: ("NTN", "NTN"), 7: ("OTA-FL", "Federated learning over the air")}

JOURNALS = {
    "S90422530": "IEEE Journal on Selected Areas in Communications",
    "S63459445": "IEEE Transactions on Wireless Communications",
    "S196647941": "IEEE Transactions on Communications",
    "S168680287": "IEEE Transactions on Signal Processing",
    "S42167783": "IEEE Journal of Selected Topics in Signal Processing",
    "S10936095": "IEEE Transactions on Vehicular Technology",
    "S2484188435": "IEEE Transactions on Cognitive Communications and Networking",
    "S4387283721": "IEEE Transactions on Machine Learning in Communications and Networking",
    "S4210192662": "IEEE Transactions on Green Communications and Networking",
    "S2480266640": "IEEE Internet of Things Journal",
    "S69141925": "IEEE Transactions on Mobile Computing",
    "S4210202420": "IEEE Open Journal of the Communications Society",
    "S2500830676": "IEEE Wireless Communications Letters",
    "S147316732": "IEEE Communications Letters",
}
FROM_DATE = "2024-01-01"
BASE_FILTER = f"from_publication_date:{FROM_DATE},language:en,type:article"
FILTER = BASE_FILTER + ",primary_location.source.id:" + "|".join(JOURNALS)

THRESHOLD = 3

REASONS = {
    "system": "single-antenna link without a RIS outside OTFS and NTN",
    "no_learning": "no learned component (recorded as a reference point)",
    "above_phy": "learning above the physical layer (recorded apart)",
    "function": "physical-layer function outside the seven areas",
    "results": "no quantitative results",
    "source_type": "not a research article or letter of the fourteen journals",
    "survey": "survey or tutorial (recorded for context)",
    "period": "published before 2024 by the date of OpenAlex",
    "language": "not in English",
}

LOG_FIELDS = ["doi", "title", "authors", "journal", "year", "publication_date", "abstract", "oa_status",
              "oa_version", "oa_url", "flags", "ta_decision", "ta_reason", "ft_retrieved", "version_read",
              "ft_decision", "ft_reason", "area", "notes"]
DECISIONS = LOG_FIELDS[LOG_FIELDS.index("ta_decision"):]
CRITERIA = ["q1", "q2", "q3", "q4", "q5"]
FORM_FIELDS = (["doi", "title", "journal", "year", "area", "version_read", "ris", "function", "system", "method",
                "data_channel", "test_conditions", "baselines", "metrics", "complexity", "openness"]
               + CRITERIA + [q + "_support" for q in CRITERIA] + ["notes"])


def norm_doi(doi):
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", (doi or "").strip().lower())


def norm_title(title):
    t = html.unescape(re.sub(r"<[^>]+>", " ", title or ""))
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t.lower()).split())


def sort_key(rec):
    return (0, rec["doi"]) if rec["doi"] else (1, norm_title(rec["title"]))


def abstract_text(inverted):
    if not inverted:
        return ""
    words = {i: w for w, positions in inverted.items() for i in positions}
    return " ".join(words[i] for i in sorted(words))


def from_openalex(w):
    src = (w.get("primary_location") or {}).get("source") or {}
    best, oa = w.get("best_oa_location") or {}, w.get("open_access") or {}
    version = best.get("version") or ""
    return {"doi": norm_doi(w.get("doi")), "title": " ".join((w.get("title") or "").split()),
            "abstract": abstract_text(w.get("abstract_inverted_index")),
            "authors": "; ".join((a.get("author") or {}).get("display_name") or "" for a in w.get("authorships") or []),
            "journal": src.get("display_name") or "", "journal_id": (src.get("id") or "").rsplit("/", 1)[-1],
            "publication_date": w.get("publication_date") or "", "year": str(w.get("publication_year") or ""),
            "type": w.get("type") or "", "language": w.get("language") or "",
            "openalex_id": (w.get("id") or "").rsplit("/", 1)[-1], "oa_status": oa.get("oa_status") or "",
            "oa_url": best.get("pdf_url") or best.get("landing_page_url") or "",
            "oa_version": "" if not version else ("published" if version == "publishedVersion" else "preprint")}


def outside_filter(rec):
    return (rec["journal_id"] not in JOURNALS or rec["type"] != "article" or rec["language"] != "en"
            or rec["publication_date"] < FROM_DATE)


def dedup(records):
    unique = {}
    for r in sorted(records, key=lambda r: r["openalex_id"]):
        unique.setdefault(r["doi"] or "title:" + norm_title(r["title"]), r)
    by_title = {}
    for key, r in unique.items():
        if not key.startswith("title:"):
            by_title.setdefault(norm_title(r["title"]), []).append(key)
    for key in [k for k in unique if k.startswith("title:")]:
        if len(by_title.get(key[len("title:"):], [])) == 1:
            del unique[key]
    return list(unique.values()), [sorted(keys) for keys in by_title.values() if len(keys) > 1]


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def score(row):
    marks = [row.get(q, "") for q in CRITERIA]
    return sum(m == "1" for m in marks) if all(m in ("0", "1") for m in marks) else None
