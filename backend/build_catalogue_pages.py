#!/usr/bin/env python3
"""Pre-split bundled catalogues into small gzipped pages (run at image build).

Parsing the multi-MB catalogue files on a 0.1 CPU free instance takes many
seconds, so the first page view used to be slow. This script does that work
once at build time: cache-seed/pages/<key>/<n>.json.gz holds each page of 18
titles (all torrent rows of a title stay together), ready to be sent as-is.
"""
import gzip, json, re, sys
from pathlib import Path

SEED = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "cache-seed")
PAGE_SIZE = 18
SOURCES = {
    "marvel": "marvel_catalogue.json",
    "marvel-hindi": "marvel_hindi_catalogue.json",
    "dc-live-action": "dc_live_action_catalogue.json",
    "dc-live-action-hindi": "dc_live_action_hindi_catalogue.json",
    "dc-animated": "dc_animated_catalogue.json",
    "classics": "classics_catalogue.json",
}


def group_key(item, index=0):
    """Return a stable title key, without collapsing unrelated untitled rows."""
    title = re.sub(r"[^a-z0-9]+", "", str(
        item.get("catalogueTitle") or item.get("marvelCatalogueTitle")
        or item.get("mediaTitle") or item.get("title") or "").casefold())
    if title:
        return title

    # Some legacy rows have no display title but still carry a stable media/release ID.
    for field in ("tmdbId", "tmdb_id", "movieId", "movie_id", "imdbId", "imdb_id",
                  "infoHash", "info_hash", "magnet", "id"):
        value = str(item.get(field) or "").strip().casefold()
        if value:
            return field + ":" + value

    # Never group every malformed row under the same empty-string key.
    return "__untitled_row_" + str(index)


def main():
    for key, name in SOURCES.items():
        path = SEED / name
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = [r for r in payload.get("results", []) if isinstance(r, dict)]
        groups = {}
        for index, row in enumerate(rows):
            groups.setdefault(group_key(row, index), []).append(row)
        keys = list(groups)
        total_pages = max(1, -(-len(keys) // PAGE_SIZE))
        out = SEED / "pages" / key
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("*.json.gz"):
            old.unlink()
        for page in range(1, total_pages + 1):
            page_rows = [r for k in keys[(page - 1) * PAGE_SIZE: page * PAGE_SIZE] for r in groups[k]]
            envelope = {
                "status": "ready", "builtAt": payload.get("builtAt"),
                "completed": int(payload.get("titlesQueried") or 0),
                "total": int(payload.get("titlesQueried") or 0),
                "resultCount": len(rows), "movieCount": len(keys), "refreshing": False,
                "results": page_rows, "page": page, "pageSize": PAGE_SIZE,
                "totalPages": total_pages, "totalMovies": len(keys),
            }
            (out / f"{page}.json.gz").write_bytes(gzip.compress(
                json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9))
        print(f"{key}: {len(keys)} titles -> {total_pages} pages")


if __name__ == "__main__":
    main()
