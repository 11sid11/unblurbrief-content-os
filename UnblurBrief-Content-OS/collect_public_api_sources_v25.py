from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTFILE = OUTPUT / "public_api_v25_sources.json"

TECH_KEYWORDS = [
    "ai", "artificial intelligence", "openai", "google", "microsoft", "meta", "apple",
    "semiconductor", "chip", "cybersecurity", "startup", "data", "privacy", "software",
    "developer", "robotics", "cloud", "nvidia", "anthropic"
]
BUSINESS_KEYWORDS = [
    "rbi", "sebi", "market", "stock", "inflation", "gdp", "bank", "business", "economy",
    "rupee", "oil", "trade", "ipo", "earnings", "finance", "monetary", "rate"
]
INDIA_KEYWORDS = [
    "india", "indian", "new delhi", "delhi", "mumbai", "bengaluru", "bangalore", "hyderabad",
    "chennai", "kolkata", "kerala", "odisha", "tamil nadu", "karnataka", "maharashtra",
    "west bengal", "uttar pradesh", "gujarat", "rajasthan", "lok sabha", "rajya sabha",
    "rbi", "reserve bank of india", "sebi", "election commission of india",
    "supreme court of india", "parliament of india", "modi", "narendra modi"
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_json(url: str, timeout: int = 12) -> Any:
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "UnblurBriefContentOS/25"})
    r.raise_for_status()
    return r.json()


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def contains_any(text: str, kws: list[str]) -> bool:
    low = text.lower()
    return any(k in low for k in kws)


def classify(title: str, url: str = "") -> tuple[str, str]:
    text = f"{title} {url}".lower()

    # India requires India-specific entities. Generic words like "election" or
    # "court" are intentionally NOT India triggers because they misclassify
    # US/Europe politics as India news.
    if contains_any(text, INDIA_KEYWORDS):
        return "India", "India-focused explainer"

    if contains_any(text, TECH_KEYWORDS):
        return "Technology", "Tech explainer"

    if contains_any(text, BUSINESS_KEYWORDS):
        return "Business", "Business/economy explainer"

    us_politics = ["democrat", "republican", "senate", "michigan", "california", "texas", "trump", "biden", "us election", "u.s. election", "special election"]
    if contains_any(text, us_politics):
        return "World", "US politics explainer"

    return "Current Affairs", "Explained Simply"


def make_source(provider: str, title: str, url: str, summary: str, category: str, angle: str, priority: str = "Medium", extra: dict | None = None) -> dict[str, Any]:
    item = {
        "source": provider,
        "trust_role": "discovery_only",
        "category": category,
        "title": clean(title),
        "url": url,
        "summary": clean(summary),
        "published": "",
        "scraped_at": now_iso(),
        "priority": priority,
        "content_angle": angle,
        "used_for_post": "No",
        "api_provider": provider.lower().replace(" ", "_"),
        "research_extraction_status": "metadata_only",
        "source_note": "Free public API discovery seed. Verify the original source before publishing.",
    }
    if extra:
        item.update(extra)
    return item


def collect_hacker_news(limit: int = 35) -> list[dict[str, Any]]:
    out = []
    try:
        ids = get_json("https://hacker-news.firebaseio.com/v0/topstories.json")[:120]
        for story_id in ids:
            if len(out) >= limit:
                break
            try:
                s = get_json(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
            except Exception:
                continue
            title = clean(s.get("title", ""))
            url = s.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
            if not title:
                continue
            if not contains_any(title + " " + url, TECH_KEYWORDS + BUSINESS_KEYWORDS + INDIA_KEYWORDS):
                continue
            category, angle = classify(title, url)
            score = int(s.get("score", 0) or 0)
            priority = "High" if score >= 250 else "Medium"
            out.append(make_source(
                "Hacker News API",
                title,
                url,
                f"Hacker News signal with {score} points and {s.get('descendants', 0) or 0} comments. Use as tech/business discovery; verify the linked source.",
                category,
                angle,
                priority,
                {"hn_id": story_id, "hn_score": score, "hn_comments": s.get("descendants", 0) or 0}
            ))
    except Exception as exc:
        out.append(make_source("Hacker News API", "HN API unavailable", "", str(exc), "Technology", "Tech explainer", "Low"))
    return out


def collect_world_bank_india() -> list[dict[str, Any]]:
    indicators = [
        ("NY.GDP.MKTP.CD", "India GDP trend", "Business", "Economy data explainer"),
        ("FP.CPI.TOTL.ZG", "India inflation trend", "Business", "Economy data explainer"),
        ("SP.POP.TOTL", "India population trend", "India", "Exam data explainer"),
        ("NE.EXP.GNFS.CD", "India exports trend", "Business", "Trade explainer"),
        ("BX.KLT.DINV.CD.WD", "India FDI inflows trend", "Business", "Economy data explainer"),
    ]
    out = []
    for code, label, category, angle in indicators:
        try:
            data = get_json(f"https://api.worldbank.org/v2/country/IN/indicator/{code}?format=json&per_page=8")
            rows = data[1] if isinstance(data, list) and len(data) > 1 else []
            values = []
            for r in rows:
                if r.get("value") is not None:
                    values.append(f"{r.get('date')}: {r.get('value')}")
            summary = "Latest World Bank values: " + "; ".join(values[:4]) if values else "World Bank indicator metadata available."
            out.append(make_source(
                "World Bank API",
                label,
                f"https://data.worldbank.org/indicator/{code}?locations=IN",
                summary,
                category,
                angle,
                "Medium",
                {"indicator_code": code, "api_body_text": summary, "trust_role": "data_api", "research_extraction_status": "ok"}
            ))
        except Exception:
            continue
    return out


def collect_wikipedia_current_events() -> list[dict[str, Any]]:
    out = []
    now = datetime.now(timezone.utc)
    page = f"Portal:Current_events/{now.year}_{now.strftime('%B')}_{now.day}"
    try:
        params = {
            "action": "parse",
            "page": page,
            "prop": "wikitext",
            "format": "json",
            "formatversion": "2",
        }
        r = requests.get("https://en.wikipedia.org/w/api.php", params=params, timeout=12, headers={"User-Agent": "UnblurBriefContentOS/25"})
        r.raise_for_status()
        data = r.json()
        text = data.get("parse", {}).get("wikitext", "")
        bullets = []
        for line in text.splitlines():
            line = clean(re.sub(r"\[\[|\]\]|\{\{.*?\}\}", "", line))
            if line.startswith("*") and len(line) > 80:
                bullets.append(line.lstrip("* ").strip())
        for b in bullets[:20]:
            category, angle = classify(b)
            if category in {"India", "Technology", "Business", "Current Affairs"}:
                out.append(make_source(
                    "Wikipedia Current Events API",
                    b[:160],
                    f"https://en.wikipedia.org/wiki/{page.replace(' ', '_')}",
                    b,
                    category,
                    angle,
                    "Medium"
                ))
    except Exception as exc:
        out.append(make_source("Wikipedia Current Events API", "Wikipedia Current Events unavailable", "", str(exc), "Current Affairs", "Explained Simply", "Low"))
    return out


def main() -> int:
    OUTPUT.mkdir(exist_ok=True)
    items = []
    items.extend(collect_hacker_news())
    items.extend(collect_world_bank_india())
    items.extend(collect_wikipedia_current_events())

    # de-dupe by title/url
    seen = set()
    deduped = []
    for item in items:
        key = (item.get("title", "").lower()[:100], item.get("url", ""))
        if key in seen or not item.get("title"):
            continue
        seen.add(key)
        deduped.append(item)

    OUTFILE.write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(deduped)} public API sources to {OUTFILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
