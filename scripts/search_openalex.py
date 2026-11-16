#!/usr/bin/env python3
"""Runs the search on OpenAlex and saves every record with a manifest."""
import datetime as dt
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from survey_protocol import FILTER, ROOT, SEARCH

API = "https://api.openalex.org/works"
SELECT = ("id,doi,title,publication_date,publication_year,type,language,primary_location,open_access,"
          "best_oa_location,abstract_inverted_index,authorships")
PER_PAGE = 100
PAUSE = 1.1
budget = {"used": 0, "remaining": "?"}


def get(params):
    url = API + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "uaslp-survey-search/1.0"}
    if os.environ.get("OPENALEX_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["OPENALEX_API_KEY"]
    for attempt in range(6):
        time.sleep(PAUSE)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=180) as r:
                data = json.load(r)
                budget["used"] += int(r.headers.get("X-RateLimit-Credits-Used") or 0)
                budget["remaining"] = r.headers.get("X-RateLimit-Remaining", "?")
                return data
        except urllib.error.HTTPError as e:
            wait = int(e.headers.get("Retry-After") or 0)
            if e.code == 429 and (e.headers.get("X-RateLimit-Remaining") == "0" or wait > 60):
                raise SystemExit(f"OpenAlex: the daily budget is used up; it resets at midnight UTC ({wait} s)")
            if e.code == 429 or e.code >= 500:
                time.sleep(max(wait, 2 ** attempt))
                continue
            raise SystemExit(f"OpenAlex HTTP {e.code}: {e.read().decode(errors='replace')[:500]}")
    raise SystemExit("OpenAlex: no answer after 6 attempts")


def count(query, flt):
    return get({"search.title_and_abstract": query, "filter": flt, "per-page": 1, "select": "id"})["meta"]["count"]


def search(query, flt):
    works, n, page = [], None, 1
    while True:
        d = get({"search.title_and_abstract": query, "filter": flt, "select": SELECT, "sort": "doi",
                 "per-page": PER_PAGE, "page": page})
        if n is None:
            n = d["meta"]["count"]
            if n > 10_000:
                raise SystemExit(f"{n:,} records: paging by page number stops at 10,000")
        works += d["results"]
        if not d["results"] or len(works) >= n:
            return n, works
        page += 1


def fetch():
    today = dt.date.today().isoformat()
    out = ROOT / "data" / "search" / f"openalex_{today}"
    if out.exists():
        raise SystemExit(f"{out.relative_to(ROOT)} already exists; a search is never overwritten")
    pages = -(-count(SEARCH, FILTER) // PER_PAGE)
    need = pages * budget["used"]
    if budget["remaining"].isdigit() and int(budget["remaining"]) < need:
        raise SystemExit(f"the search needs about {need} credits and {budget['remaining']} are left today")
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    n, works = search(SEARCH, FILTER)
    unique = len({w["id"] for w in works})
    out.mkdir(parents=True)
    with open(out / "records.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(w, ensure_ascii=False) + "\n" for w in works)
    manifest = {"database": "OpenAlex", "endpoint": API, "started_utc": started,
                "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "query": SEARCH, "filter": FILTER, "select": SELECT, "per_page": PER_PAGE,
                "paging": "page number, sort=doi", "count": n, "saved": len(works), "unique": unique,
                "credits_used": budget["used"], "python": sys.version.split()[0],
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with open(out / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"OpenAlex reports {n:,}, saved {len(works):,} ({unique:,} unique) in {out.relative_to(ROOT)}; "
          f"credits used {budget['used']}, left today {budget['remaining']}")
    if len(works) != n or unique != len(works):
        print("WARNING, the counts do not match; run the search again on another day")
        sys.exit(1)


if __name__ == "__main__":
    fetch()
