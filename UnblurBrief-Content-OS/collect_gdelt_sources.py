from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

IST = timezone(timedelta(hours=5, minutes=30))
ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
SOURCES_FILE = OUTPUT / "unblurbrief_sources.json"
CSV_FILE = OUTPUT / "unblurbrief_sources.csv"

QUERIES = [
    ("India Current Affairs", "India politics economy government current affairs"),
    ("World Affairs", "geopolitics diplomacy economy conflict"),
    ("Economy", "inflation central bank GDP markets economy"),
    ("Science Technology", "space science technology climate health"),
]

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"


def clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def classify_priority(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["war","strike","missile","election","inflation","gdp","rate","killed","injured","government","minister","sanctions","court"]):
        return "High"
    if any(k in t for k in ["announces","launches","summit","agreement","report","policy","market","trade"]):
        return "Medium"
    return "Low"


def angle(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["rbi","central bank","inflation","gdp","rate","economy"]):
        return "Banking/economy update"
    if any(k in t for k in ["market","stocks","sebi","investor"]):
        return "Markets/regulation update"
    if any(k in t for k in ["war","strike","missile","ceasefire","iran","israel","china","russia","us "]):
        return "Geopolitics explainer"
    if any(k in t for k in ["election","parliament","minister","government"]):
        return "Politics explainer"
    if any(k in t for k in ["space","science","technology","climate","health"]):
        return "Science/health update"
    return "General current affairs"


def load_items() -> list[dict[str, Any]]:
    if not SOURCES_FILE.exists():
        return []
    try:
        data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def fetch_gdelt(query_name: str, query: str, maxrecords: int = 20) -> list[dict[str, Any]]:
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(maxrecords),
        "sort": "hybridrel",
    }
    url = GDELT_ENDPOINT + "?" + urlencode(params)
    print(f"Fetching GDELT: {query_name}")
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "UnblurBriefContentOS/1.0"})
        r.raise_for_status()
        payload = r.json()
    except Exception as exc:
        print(f"GDELT failed for {query_name}: {exc}")
        return []

    scraped_at = datetime.now(IST).isoformat(timespec="seconds")
    articles = payload.get("articles", []) if isinstance(payload, dict) else []
    out = []
    for article in articles:
        title = clean(article.get("title", ""))
        source_url = clean(article.get("url", ""))
        domain = clean(article.get("domain", ""))
        seendate = clean(article.get("seendate", ""))
        if not title or not source_url:
            continue
        out.append({
            "source": f"GDELT - {query_name}",
            "trust_role": "discovery_crosscheck",
            "category": query_name,
            "title": title,
            "url": source_url,
            "summary": clean(article.get("sourcecountry", "")),
            "published": seendate,
            "scraped_at": scraped_at,
            "priority": classify_priority(title),
            "content_angle": angle(title),
            "used_for_post": "No",
            "gdelt_domain": domain,
        })
    print(f"Found {len(out)} GDELT item(s).")
    return out


def save_items(items: list[dict[str, Any]]) -> None:
    SOURCES_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    # CSV is optional here. scrape_sources.py already writes it; this appends JSON-first workflow.
    print(f"Updated JSON: {SOURCES_FILE}")


def main() -> int:
    OUTPUT.mkdir(exist_ok=True)
    items = load_items()
    seen = {i.get("url", "") for i in items}
    added = []
    for name, query in QUERIES:
        for item in fetch_gdelt(name, query):
            if item.get("url") not in seen:
                seen.add(item.get("url"))
                added.append(item)
    items.extend(added)
    save_items(items)
    print(f"GDELT added: {len(added)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
