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
    return wanted


def resolve(api, title, year):
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
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for (title, year), url in pool.map(work, todo):
            if url:
                existing[(norm(title), year)] = [title, year, url]
                done += 1
            elif url is None:
                failed += 1
            else:
                missing += 1
    MAP.write_text(json.dumps(sorted(existing.values()), separators=(",", ":")), encoding="utf-8")
    print(f"resolved {done}, no poster found {missing}, failed (re-run) {failed}; total in map {len(existing)}")
    print(f"wrote {MAP} ({MAP.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    sys.exit(main())
