#!/usr/bin/env python3
"""Fill backend/cache-seed/poster_map.json with poster URLs (text only, no images).

Run this on the machine that has your API keys (your VPS) while the full app
is running there. It scans the bundled catalogues for every
/api/poster?title=...&year=... link, asks the running backend to resolve each
one (/api/poster/resolve), and merges the results into poster_map.json.

    python3 scripts/build_poster_map.py --api http://127.0.0.1:8000

Then commit backend/cache-seed/poster_map.json and push to GitHub.
Standard library only; safe to re-run (already-resolved titles are skipped).
"""
import argparse, json, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "backend" / "cache-seed"
MAP = SEED / "poster_map.json"
LINK = re.compile(r"/api/poster\?([^\"'\\\s]+)")


def norm(text):
    return re.sub(r"[^a-z0-9]+", "", str(text or "").casefold())


def collect():
    wanted = {}
    for path in SEED.rglob("*.json"):
        if path.name == "poster_map.json":
            continue
        for query in LINK.findall(path.read_text(encoding="utf-8")):
            q = urllib.parse.parse_qs(query.replace("&amp;", "&"))
            title = (q.get("title") or [""])[0].strip()
            year = (q.get("year") or [""])[0].strip()
            if title:
                wanted.setdefault((norm(title), year), (title, year))
    print(f"Scanned catalogue JSON files under {SEED}; found {len(wanted)} unique poster title/year keys", flush=True)
    return wanted


# Canonical title fallbacks for common release-name variants. Each fallback is
# deliberately year-scoped to avoid matching a different film with the same name.
TITLE_FALLBACKS = {
    ("avp alien vs predator", "2004"): ["Alien vs Predator", "Alien vs. Predator"],
    ("ultimate avengers 2", "2006"): ["Ultimate Avengers 2: Rise of the Panther", "Ultimate Avengers 2"],
    ("thunderbolts a k a the new avengers", "2025"): ["Thunderbolts", "The New Avengers"],
    ("batman the dark knight rises", "2012"): ["The Dark Knight Rises"],
    ("interstellar imax", "2014"): ["Interstellar"],
    ("the nightmare before christmas 3d", "1993"): ["The Nightmare Before Christmas"],
    ("coraline e la porta magica", "2009"): ["Coraline"],
    ("jawan extended cut", "2023"): ["Jawan"],
    ("wandavision season 1 s01", "2021"): ["WandaVision"],
    ("wandavision s01ep01 02 1080p dual audio", "2021"): ["WandaVision"],
    ("wandavision s01ep07 1080p dual audio", "2021"): ["WandaVision"],
    ("loki season 1 s01", "2021"): ["Loki"],
    ("dilwale dulhania le jayenge hindi movie sub ita", "1995"): ["Dilwale Dulhania Le Jayenge"],
    ("pany lust stories 3", "2026"): ["Lust Stories 3"],
    ("dhurandhar the revenge raw amp undekha", "2026"): ["Dhurandhar: The Revenge", "Dhurandhar The Revenge"],
    ("dhurandhar the revenge raw and undekha", "2026"): ["Dhurandhar: The Revenge", "Dhurandhar The Revenge"],
    ("aphics dhurandhar the revenge", "2026"): ["Dhurandhar: The Revenge", "Dhurandhar The Revenge"],
    ("ftware ikka", "2026"): ["Ikka"],
}


def resolve_one(api, title, year):
    url = api.rstrip("/") + "/api/poster/resolve?" + urllib.parse.urlencode({"title": title, "year": year})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=25) as response:
                found = json.load(response).get("url") or ""
                return found if found.startswith("http") else ""
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return ""
        except Exception:
            pass
        time.sleep(1 + attempt)
    return None  # transient failure; retry on next run


def resolve(api, title, year):
    # First try the catalogue's exact title. Only if it has no result, try
    # explicit canonical aliases for this exact title/year pair.
    found = resolve_one(api, title, year)
    if found is None or found:
        return found
    key = (re.sub(r"[^a-z0-9]+", " ", str(title or "").casefold()).strip(), str(year or "").strip())
    for alias in TITLE_FALLBACKS.get(key, []):
        found = resolve_one(api, alias, year)
        if found is None or found:
            return found
    return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="URL of your running backend")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--refresh", action="store_true", help="re-resolve titles already in the map")
    args = parser.parse_args()

    existing = {}
    if MAP.exists():
        for title, year, url in json.loads(MAP.read_text(encoding="utf-8")):
            existing[(norm(title), year)] = [title, year, url]

    todo = [v for k, v in collect().items() if args.refresh or k not in existing]
    print(f"{len(existing)} already mapped, {len(todo)} to resolve")

    def work(item):
        return item, resolve(args.api, *item)

    done = missing = failed = 0
    missing_items = []
    failed_items = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for (title, year), url in pool.map(work, todo):
            if url:
                existing[(norm(title), year)] = [title, year, url]
                done += 1
                print(f"[FOUND] {title} ({year}): {url}", flush=True)
            elif url is None:
                failed += 1
                failed_items.append((title, year))
                print(f"[ERROR] {title} ({year}): resolver request failed after retries; will retry next run", flush=True)
            else:
                missing += 1
                missing_items.append((title, year))
                print(f"[NO POSTER] {title} ({year}): resolver returned no URL", flush=True)
    MAP.write_text(json.dumps(sorted(existing.values()), separators=(",", ":")), encoding="utf-8")
    print(f"resolved {done}, no poster found {missing}, failed (re-run) {failed}; total in map {len(existing)}")
    report = ROOT / "poster_map_failures.txt"
    lines = ["NO POSTER FOUND"]
    lines.extend(f"{title}\t{year}" for title, year in missing_items)
    lines.extend(["", "REQUEST ERRORS (safe to retry)"])
    lines.extend(f"{title}\t{year}" for title, year in failed_items)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote failure report {report}")
    print(f"wrote {MAP} ({MAP.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    sys.exit(main())
