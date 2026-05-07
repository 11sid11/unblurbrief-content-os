from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30))
ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
SOURCES_FILE = OUTPUT / "unblurbrief_sources.json"
API_KEYS_FILE = ROOT / "api_keys.json"


def clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\n", " ").replace("\t", " ").split()).strip()


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_sources() -> list[dict[str, Any]]:
    data = load_json(SOURCES_FILE, [])
    return data if isinstance(data, list) else []


def save_sources(items: list[dict[str, Any]]) -> None:
    save_json(SOURCES_FILE, items)


def load_api_keys() -> dict[str, str]:
    data = load_json(API_KEYS_FILE, {})
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v).strip() for k, v in data.items()}


def classify_priority(title: str) -> str:
    text = title.lower()
    high = [
        "killed", "injured", "dead", "death", "war", "strike", "missile",
        "explosion", "ceasefire", "sanctions", "election", "prime minister",
        "president", "attack", "crash", "fire", "evacuates", "intercepts",
        "espionage", "fraud", "scam", "ban", "suspends", "revokes",
        "inflation", "gdp", "growth outlook", "rate", "court", "policy",
    ]
    medium = [
        "agreement", "summit", "launches", "announces", "approves", "signs",
        "reports", "orders", "expels", "holds", "passes", "production",
        "ministry", "government", "regulation", "penalty", "mou", "mission",
        "forecast", "report", "study", "climate", "technology",
    ]
    if any(k in text for k in high):
        return "High"
    if any(k in text for k in medium):
        return "Medium"
    return "Low"


def suggest_content_angle(title: str) -> str:
    text = title.lower()
    if any(w in text for w in ["rbi", "reserve bank", "central bank", "inflation", "gdp", "growth outlook", "rate cut", "rate hike"]):
        return "Banking/economy update"
    if any(w in text for w in ["sebi", "securities", "investor", "trading", "stock", "market", "broker"]):
        return "Markets/regulation update"
    if any(w in text for w in ["isro", "satellite", "mission", "space", "nasa", "moon", "mars"]):
        return "Science/space update"
    if any(w in text for w in ["killed", "injured", "explosion", "crash", "fire", "suicide", "bombing", "shooting"]):
        return "Breaking incident explainer"
    if any(w in text for w in ["war", "strike", "missile", "ceasefire", "military", "navy", "drone", "intercepted", "iran", "israel", "russia", "china", "ukraine"]):
        return "Geopolitics explainer"
    if any(w in text for w in ["election", "parliament", "prime minister", "president", "minister", "government"]):
        return "Politics explainer"
    if any(w in text for w in ["energy", "minerals", "oil", "gas", "trade", "critical minerals", "free trade agreement", "fta"]):
        return "Economy/resources explainer"
    if any(w in text for w in ["vaccine", "covid", "biotechnology", "health", "who", "outbreak", "virus", "disease"]):
        return "Science/health update"
    if any(w in text for w in ["summit", "agreement", "diplomats", "foreign minister", "embassy", "united nations"]):
        return "International relations update"
    if any(w in text for w in ["climate", "weather", "emissions", "environment"]):
        return "Environment/climate update"
    return "General current affairs"


def dedupe_extend(existing: list[dict[str, Any]], new_items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen_urls = {clean(i.get("url", "")) for i in existing if clean(i.get("url", ""))}
    seen_titles = {clean(i.get("title", "")).lower()[:180] for i in existing if clean(i.get("title", ""))}
    added = 0
    for item in new_items:
        url = clean(item.get("url", ""))
        title_key = clean(item.get("title", "")).lower()[:180]
        if not url or not title_key:
            continue
        if url in seen_urls or title_key in seen_titles:
            continue
        existing.append(item)
        seen_urls.add(url)
        seen_titles.add(title_key)
        added += 1
    return existing, added


def make_item(
    source: str,
    trust_role: str,
    category: str,
    title: str,
    url: str,
    summary: str = "",
    published: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = datetime.now(IST).isoformat(timespec="seconds")
    item: dict[str, Any] = {
        "source": source,
        "trust_role": trust_role,
        "category": category,
        "title": clean(title),
        "url": clean(url),
        "summary": clean(summary),
        "published": clean(published),
        "scraped_at": now,
        "priority": classify_priority(title),
        "content_angle": suggest_content_angle(title),
        "used_for_post": "No",
    }
    if extra:
        item.update(extra)
    return item
