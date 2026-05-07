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

NEWSAPI_ENDPOINT = "https://newsapi.org/v2/top-headlines"

REQUESTS = [
    ("NewsAPI - India", {"country": "in", "pageSize": 50}),
    ("NewsAPI - Business", {"country": "in", "category": "business", "pageSize": 30}),
    ("NewsAPI - Science", {"language": "en", "category": "science", "pageSize": 30}),
    ("NewsAPI - Technology", {"language": "en", "category": "technology", "pageSize": 30}),
]


def fetch_newsapi(source_name: str, params: dict, api_key: str) -> list[dict]:
    final_params = dict(params)
    final_params["apiKey"] = api_key
    print(f"Fetching NewsAPI: {source_name}")

    try:
        r = requests.get(NEWSAPI_ENDPOINT, params=final_params, timeout=25)
        r.raise_for_status()
        payload = r.json()
    except Exception as exc:
        print(f"NewsAPI failed for {source_name}: {exc}")
        return []

    articles = payload.get("articles", []) if isinstance(payload, dict) else []
    items: list[dict] = []

    for article in articles:
        title = clean(article.get("title", ""))
        url = clean(article.get("url", ""))
        description = clean(article.get("description", ""))
        content = clean(article.get("content", ""))
        published = clean(article.get("publishedAt", ""))
        source = article.get("source", {}) if isinstance(article.get("source", {}), dict) else {}
        publisher = clean(source.get("name", ""))

        if not title or not url:
            continue

        items.append(
            make_item(
                source=source_name,
                trust_role="discovery_api",
                category=publisher or source_name,
                title=title,
                url=url,
                summary=description or content,
                published=published,
                extra={
                    "api_provider": "newsapi",
                    "publisher": publisher,
                    "image_url": clean(article.get("urlToImage", "")),
                    "api_content_snippet": content,
                },
            )
        )

    print(f"Found {len(items)} NewsAPI item(s).")
    return items


def main() -> int:
    keys = load_api_keys()
    api_key = keys.get("newsapi_key", "")

    if not api_key:
        print(f"NewsAPI key not found. Add newsapi_key in {API_KEYS_FILE}. Skipping.")
        return 0

    existing = load_sources()
    new_items: list[dict] = []

    for source_name, params in REQUESTS:
        new_items.extend(fetch_newsapi(source_name, params, api_key))

    existing, added = dedupe_extend(existing, new_items)
    save_sources(existing)

    print(f"NewsAPI added: {added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
