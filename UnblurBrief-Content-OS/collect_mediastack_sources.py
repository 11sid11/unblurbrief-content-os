from __future__ import annotations

import requests

from api_common import (
    API_KEYS_FILE,
    clean,
    dedupe_extend,
    load_api_keys,
    load_sources,
    make_item,
    save_sources,
)

MEDIASTACK_ENDPOINT = "http://api.mediastack.com/v1/news"

REQUESTS = [
    ("Mediastack - India", {"countries": "in", "languages": "en", "limit": 50, "sort": "published_desc"}),
    ("Mediastack - Business", {"countries": "in", "languages": "en", "categories": "business", "limit": 30, "sort": "published_desc"}),
    ("Mediastack - World", {"languages": "en", "categories": "general", "limit": 50, "sort": "published_desc"}),
    ("Mediastack - Science/Tech", {"languages": "en", "categories": "science,technology", "limit": 30, "sort": "published_desc"}),
]


def fetch_mediastack(source_name: str, params: dict, api_key: str) -> list[dict]:
    final_params = dict(params)
    final_params["access_key"] = api_key
    print(f"Fetching Mediastack: {source_name}")

    try:
        r = requests.get(MEDIASTACK_ENDPOINT, params=final_params, timeout=25)
        r.raise_for_status()
        payload = r.json()
    except Exception as exc:
        print(f"Mediastack failed for {source_name}: {exc}")
        return []

    articles = payload.get("data", []) if isinstance(payload, dict) else []
    items: list[dict] = []

    for article in articles:
        title = clean(article.get("title", ""))
        url = clean(article.get("url", ""))
        description = clean(article.get("description", ""))
        published = clean(article.get("published_at", ""))
        publisher = clean(article.get("source", ""))

        if not title or not url:
            continue

        items.append(
            make_item(
                source=source_name,
                trust_role="discovery_api",
                category=clean(article.get("category", "")) or publisher or source_name,
                title=title,
                url=url,
                summary=description,
                published=published,
                extra={
                    "api_provider": "mediastack",
                    "publisher": publisher,
                    "image_url": clean(article.get("image", "")),
                    "country": clean(article.get("country", "")),
                    "language": clean(article.get("language", "")),
                },
            )
        )

    print(f"Found {len(items)} Mediastack item(s).")
    return items


def main() -> int:
    keys = load_api_keys()
    api_key = keys.get("mediastack_key", "")

    if not api_key:
        print(f"Mediastack key not found. Add mediastack_key in {API_KEYS_FILE}. Skipping.")
        return 0

    existing = load_sources()
    new_items: list[dict] = []

    for source_name, params in REQUESTS:
        new_items.extend(fetch_mediastack(source_name, params, api_key))

    existing, added = dedupe_extend(existing, new_items)
    save_sources(existing)

    print(f"Mediastack added: {added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
