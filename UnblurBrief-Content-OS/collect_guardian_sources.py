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

GUARDIAN_ENDPOINT = "https://content.guardianapis.com/search"

QUERIES = [
    ("Guardian - World Affairs", "world politics OR geopolitics OR diplomacy"),
    ("Guardian - Economy", "economy OR inflation OR central bank OR markets"),
    ("Guardian - Climate/Science", "climate OR science OR technology OR health"),
    ("Guardian - India", "India politics OR India economy OR India government"),
]


def fetch_guardian(query_name: str, query: str, api_key: str) -> list[dict]:
    params = {
        "api-key": api_key,
        "q": query,
        "show-fields": "headline,trailText,bodyText,shortUrl,thumbnail",
        "page-size": "20",
        "order-by": "newest",
        "lang": "en",
    }
    print(f"Fetching Guardian API: {query_name}")

    try:
        r = requests.get(GUARDIAN_ENDPOINT, params=params, timeout=25)
        r.raise_for_status()
        payload = r.json()
    except Exception as exc:
        print(f"Guardian API failed for {query_name}: {exc}")
        return []

    response = payload.get("response", {}) if isinstance(payload, dict) else {}
    results = response.get("results", []) if isinstance(response, dict) else []

    items: list[dict] = []
    for article in results:
        fields = article.get("fields", {}) if isinstance(article, dict) else {}
        title = clean(fields.get("headline") or article.get("webTitle", ""))
        url = clean(article.get("webUrl") or fields.get("shortUrl", ""))
        body_text = clean(fields.get("bodyText", ""))
        summary = clean(fields.get("trailText", ""))
        published = clean(article.get("webPublicationDate", ""))
        section = clean(article.get("sectionName", query_name))

        if not title or not url:
            continue

        # Guardian API can give article body text, so store it in summary plus API fields.
        # extract_research.py can still extract via URL, while reliability gets strong context from cached article body if later added.
        items.append(
            make_item(
                source=query_name,
                trust_role="publisher_api",
                category=section or query_name,
                title=title,
                url=url,
                summary=summary or body_text[:700],
                published=published,
                extra={
                    "api_provider": "guardian",
                    "api_body_text": body_text[:5000],
                    "image_url": clean(fields.get("thumbnail", "")),
                },
            )
        )

    print(f"Found {len(items)} Guardian item(s).")
    return items


def main() -> int:
    keys = load_api_keys()
    api_key = keys.get("guardian_api_key", "")

    if not api_key:
        print(f"Guardian API key not found. Add guardian_api_key in {API_KEYS_FILE}. Skipping.")
        return 0

    existing = load_sources()
    new_items: list[dict] = []

    for query_name, query in QUERIES:
        new_items.extend(fetch_guardian(query_name, query, api_key))

    existing, added = dedupe_extend(existing, new_items)
    save_sources(existing)

    print(f"Guardian added: {added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
