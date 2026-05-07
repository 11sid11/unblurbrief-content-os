from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

try:
    from scrapling.fetchers import Fetcher
except ImportError as exc:
    raise SystemExit("Scrapling is missing. Run: python -m pip install -r requirements.txt") from exc

IST = timezone(timedelta(hours=5, minutes=30))
ROOT_DIR = Path(__file__).resolve().parent
SOURCES_FILE = ROOT_DIR / "sources.json"
OUTPUT_DIR = ROOT_DIR / "output"
JSON_OUTPUT = OUTPUT_DIR / "unblurbrief_sources.json"
CSV_OUTPUT = OUTPUT_DIR / "unblurbrief_sources.csv"
PIB_ALL_OUTPUT = OUTPUT_DIR / "pib_all_releases.json"
RESEARCH_OUTPUT = OUTPUT_DIR / "research_cache.json"
PIB_DEBUG_HTML = OUTPUT_DIR / "pib_debug_allRel_snapshot.html"
PIB_DEBUG_LINKS = OUTPUT_DIR / "pib_debug_links.json"

MONTH_NAME_TO_NUM = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


@dataclass
class SourceConfig:
    name: str
    url: str
    article_selector: str = ""
    title_selector: str = ""
    link_selector: str = ""
    category: str = "General"
    max_items: int = 25
    delay_seconds: float = 1.0
    source_type: str = "html"
    trust_role: str = "discovery_only"
    days_back: int = 1
    fallback_days_back: int = 2
    min_newsworthiness_score: int = 20


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(v) for v in value if v)
    return " ".join(str(value).replace("\n", " ").replace("\t", " ").split()).strip()


def clean_url(value: Any) -> str:
    return html.unescape(clean_text(value))


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def load_sources(path: Path) -> list[SourceConfig]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("sources.json must contain one JSON array.")
    sources: list[SourceConfig] = []
    for item in raw:
        source_type = item.get("source_type", "html")
        if source_type == "html":
            for key in ["article_selector", "title_selector", "link_selector"]:
                if not item.get(key):
                    raise ValueError(f"HTML source missing {key}: {item}")
        elif source_type not in {"rss", "pib_all_releases"}:
            raise ValueError(f"Unsupported source_type {source_type}: {item}")
        sources.append(SourceConfig(
            name=item["name"], url=item["url"], article_selector=item.get("article_selector", ""),
            title_selector=item.get("title_selector", ""), link_selector=item.get("link_selector", ""),
            category=item.get("category", "General"), max_items=int(item.get("max_items", 25)),
            delay_seconds=float(item.get("delay_seconds", 1.0)), source_type=source_type,
            trust_role=item.get("trust_role", "discovery_only"),
            days_back=int(item.get("days_back", 1)),
            fallback_days_back=int(item.get("fallback_days_back", 2)),
            min_newsworthiness_score=int(item.get("min_newsworthiness_score", 35)),
        ))
    return sources


def classify_priority(title: str) -> str:
    text = title.lower()
    high = ["killed","injured","dead","death","war","strike","missile","explosion","ceasefire","sanctions","election","prime minister","president","attack","crash","fire","evacuates","intercepts","espionage","fraud","scam","ban","suspends","revokes","inflation","gdp","growth outlook","rate"]
    medium = ["agreement","summit","launches","announces","approves","signs","reports","orders","expels","holds","passes","production","ministry","government","policy","regulation","penalty","mou","board meeting","fast-track","investor protection","platform","scheme","mission","forecast"]
    if any(k in text for k in high):
        return "High"
    if any(k in text for k in medium):
        return "Medium"
    return "Low"


def suggest_content_angle(title: str) -> str:
    text = title.lower()
    if any(w in text for w in ["rbi","reserve bank","monetary penalty","co-operative bank","payment services","inflation","gdp","growth outlook"]):
        return "Banking/economy update"
    if any(w in text for w in ["sebi","securities","investor","trading","aif","stock","market","niveshak","broker"]):
        return "Markets/regulation update"
    if any(w in text for w in ["isro","pslv","gslv","satellite","mission","eos","nvs","space","nasa"]):
        return "Science/space update"
    if any(w in text for w in ["killed","injured","explosion","crash","fire","suicide","bombing","shooting"]):
        return "Breaking incident explainer"
    if any(w in text for w in ["war","strike","missile","ceasefire","military","navy","drone","intercepted","iran","israel"]):
        return "Geopolitics explainer"
    if any(w in text for w in ["election","parliament","prime minister","president","motion of no confidence","mamata","banerjee"]):
        return "Politics explainer"
    if any(w in text for w in ["energy","minerals","oil","gas","trade","critical minerals","free trade agreement","fta"]):
        return "Economy/resources explainer"
    if any(w in text for w in ["vaccine","covid","biotechnology","health","who","outbreak","virus"]):
        return "Science/health update"
    if any(w in text for w in ["summit","agreement","diplomats","foreign minister","embassy"]):
        return "International relations update"
    return "General current affairs"


def make_item(source: SourceConfig, title: str, url: str, scraped_at: str, summary: str = "", published: str = "") -> dict[str, str]:
    return {
        "source": source.name,
        "source_name": source.name,
        "source_url": source.url,
        "source_type": source.source_type,
        "trust_role": source.trust_role,
        "category": source.category,
        "title": title,
        "url": url,
        "summary": summary,
        "published": published,
        "scraped_at": scraped_at,
        "priority": classify_priority(title),
        "content_angle": suggest_content_angle(title),
        "used_for_post": "No",
    }


def is_pib_item(item: dict[str, Any]) -> bool:
    source = clean_text(item.get("source") or item.get("source_name")).lower()
    return item.get("source_type") == "pib_all_releases" or "pib delhi all releases" in source


def pib_release_record(
    item: dict[str, Any],
    research_by_url: dict[str, Any] | None = None,
    recommended_urls: set[str] | None = None,
) -> dict[str, Any]:
    url = clean_text(item.get("url"))
    research = (research_by_url or {}).get(url, {}) if isinstance(research_by_url, dict) else {}
    if not isinstance(research, dict):
        research = {}

    article_text = clean_text(item.get("article_text") or item.get("api_body_text") or research.get("excerpt"))
    record: dict[str, Any] = {
        "title": clean_text(item.get("title")),
        "url": url,
        "source": clean_text(item.get("source") or item.get("source_name") or "PIB Delhi All Releases - English"),
        "source_name": clean_text(item.get("source_name") or item.get("source")),
        "source_url": clean_text(item.get("source_url")),
        "source_type": clean_text(item.get("source_type") or "pib_all_releases"),
        "trust_role": clean_text(item.get("trust_role") or "primary_official"),
        "category_lane": clean_text(item.get("category_lane") or "India"),
        "ministry": clean_text(item.get("ministry")),
        "published": clean_text(item.get("published")),
        "scraped_at": clean_text(item.get("scraped_at")),
        "pib_newsworthiness_score": clean_text(item.get("pib_newsworthiness_score")),
        "pib_score_reasons": clean_text(item.get("pib_score_reasons") or item.get("pib_filter_reasons")),
        "pib_priority_label": clean_text(item.get("pib_priority_label") or "routine"),
        "extraction_status": clean_text(item.get("research_extraction_status") or research.get("status")),
        "recommended_candidate": bool(recommended_urls and url in recommended_urls),
    }
    if article_text:
        record["article_text"] = article_text
    return record


def save_pib_all_releases(
    items: list[dict[str, Any]],
    research_by_url: dict[str, Any] | None = None,
    recommended_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    OUTPUT_DIR.mkdir(exist_ok=True)
    pib_items = [item for item in items if is_pib_item(item)]
    records = [pib_release_record(item, research_by_url, recommended_urls) for item in pib_items]
    records.sort(key=lambda x: int(float(x.get("pib_newsworthiness_score") or 0)), reverse=True)
    PIB_ALL_OUTPUT.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved_to_output_pib_all_releases_json: {len(records)}")
    print(f"pib_saved_to_pib_all_releases_json: {len(records)}")
    print(f"pib_all_releases_json: {PIB_ALL_OUTPUT}")
    return records



PIB_NAVIGATION_TEXT = [
    "skip to", "screen reader", "main content", "home", "archive", "photo gallery",
    "video gallery", "contact us", "site map", "website policies", "terms of use",
    "feedback", "help", "accessibility", "press information bureau", "all releases",
]

PIB_MINISTRY_PREFIXES = [
    "ministry of", "department of", "department for", "office of", "prime minister's office", "president's secretariat",
    "vice president's secretariat", "cabinet", "election commission", "niti aayog",
    "comptroller and auditor general", "lok sabha secretariat", "rajya sabha secretariat",
    "pmo",
]


def pib_priority_label(score: int) -> str:
    if score >= 70:
        return "strong"
    if score >= 55:
        return "usable"
    return "routine"


def add_pib_score(reasons: list[str], score: int, amount: int, label: str) -> int:
    reasons.append(f"{label}:{amount:+d}")
    return score + amount


def pib_newsworthiness_score(title: str, ministry: str = "") -> tuple[int, list[str]]:
    text = f"{title} {ministry}".lower()
    score = 35
    reasons: list[str] = ["base:+35 official PIB Delhi English source"]

    if any(k in text for k in ["cabinet approves", "cabinet decision", "cabinet has approved"]):
        score = add_pib_score(reasons, score, 30, "boost:cabinet_decision")
    if any(k in text for k in ["rules", "guidelines", "regulation", "regulations", "notification", "notifies", "notified"]):
        score = add_pib_score(reasons, score, 25, "boost:rules_guidelines_regulation_notification")
    if re.search(r"\b(bill|bills|act|acts|amendment|amendments|amends|amended)\b", text):
        score = add_pib_score(reasons, score, 25, "boost:bill_act_amendment")
    if any(k in text for k in ["national report", "report on", "releases report", "index", "ranking", "rankings", "dataset", "data set"]):
        score = add_pib_score(reasons, score, 22, "boost:national_report_index_ranking_dataset")
    if any(k in text for k in ["gdp", "inflation", "exports", "imports", "procurement", "employment", "economy", "economic", "trade", "fdi"]):
        score = add_pib_score(reasons, score, 20, "boost:economy")
    if any(k in text for k in ["defence", "defense", "space", "satellite", "cyber", "artificial intelligence", " ai ", "telecom", "telecommunication", "energy security"]):
        score = add_pib_score(reasons, score, 20, "boost:strategic_technology_security")
    if "election commission" in text and any(k in text for k in ["election", "bye-election", "bye-elections", "electoral", "voter", "poll", "schedule", "legislative assembly"]):
        score = add_pib_score(reasons, score, 18, "boost:election_commission_procedure")
    if any(k in text for k in ["launches", "launched", "launch of", "rolls out", "rollout"]) and any(k in text for k in ["scheme", "platform", "portal", "initiative", "mission", "programme", "program"]):
        score = add_pib_score(reasons, score, 18, "boost:major_scheme_platform_launch")
    if any(k in text for k in ["agreement", "memorandum of understanding", "mou", "signs", "signed"]) and any(k in text for k in ["strategic", "bilateral", "international", "global", "foreign", "france", "vietnam", "brics", "g20", "asean", "eu", "uk", "united states", "japan", "australia"]):
        score = add_pib_score(reasons, score, 15, "boost:international_agreement_strategic_mou")
    if any(k in text for k in ["national", "nationwide", "all india", "across india"]) and any(k in text for k in ["welfare", "health", "workers", "farmers", "women", "children", "students", "rural", "beneficiaries", "labour", "education", "pension", "insurance"]):
        score = add_pib_score(reasons, score, 12, "boost:national_public_welfare")

    if any(k in text for k in ["photo release", "media advisory", "curtain raiser"]):
        score = add_pib_score(reasons, score, -30, "penalty:photo_release_media_advisory")
    if any(k in text for k in ["greeting", "greetings", "greets", "greeted", "congratulates", "congratulated", "salutes", "salute", "message from", "message on"]):
        score = add_pib_score(reasons, score, -25, "penalty:greeting_message")
    if any(k in text for k in ["visits", "visited", "visit to", "participates", "participated", "attends", "attended"]):
        score = add_pib_score(reasons, score, -22, "penalty:visit_participation_attendance")
    if any(k in text for k in ["addresses", "addressed", "speech", "delivers keynote", "delivers inaugural address"]):
        score = add_pib_score(reasons, score, -20, "penalty:speech_only")
    if any(k in text for k in ["inaugurates", "inaugurated", "conference", "workshop", "seminar", "conclave"]):
        score = add_pib_score(reasons, score, -18, "penalty:event_conference_workshop")
    if any(k in text for k in ["awareness campaign", "celebration", "celebrates", "celebrated", "observance", "observes", "observed"]):
        score = add_pib_score(reasons, score, -15, "penalty:campaign_celebration_observance")
    if "reviews progress" in text and not any(k in text for k in ["approves", "releases", "launches", "guidelines", "rules", "regulation", "report", "action plan", "deadline", "directs", "outcome"]):
        score = add_pib_score(reasons, score, -10, "penalty:vague_reviews_progress")

    return score, reasons


def pib_title_is_release(title: str) -> bool:
    lower = clean_text(title).lower()
    if len(lower) < 8 or len(lower) > 260:
        return False
    return not any(b in lower for b in PIB_NAVIGATION_TEXT)


def normalize_pib_release_url(base_url: str, href: str) -> str:
    raw = clean_url(href).strip().strip("'\"")
    if not raw:
        return ""

    # PIB pages sometimes wrap release URLs inside javascript handlers or iframe links.
    # Pull out the release-shaped fragment before applying urljoin.
    patterns = [
        r"(https?://(?:www\.)?pib\.gov\.in/[^'\"\s<>)]+(?:prid|PRID)[^'\"\s<>)]*)",
        r"((?:\.\./|/)?[^'\"\s<>)]*(?:PressRelease|pressrelease)[^'\"\s<>)]*\.aspx\?[^'\"\s<>)]*(?:prid|PRID)[^'\"\s<>)]*)",
        r"((?:\.\./|/)?[^'\"\s<>)]*(?:Release|release)[^'\"\s<>)]*\.aspx\?[^'\"\s<>)]*(?:prid|PRID)[^'\"\s<>)]*)",
        r"((?:\.\./|/)?[^'\"\s<>)]*(?:PressRelease|pressrelease)[^'\"\s<>)]*\.aspx(?:\?[^'\"\s<>)]*)?)",
        r"((?:\.\./|/)?[^'\"\s<>)]*(?:Release|release)[^'\"\s<>)]*\.aspx(?:\?[^'\"\s<>)]*)?)",
        r"((?:\.\./|/)?[^'\"\s<>)]+\?[^'\"\s<>)]*(?:prid|PRID)=\d+[^'\"\s<>)]*)",
    ]
    for pattern in patterns:
        m = re.search(pattern, raw)
        if m:
            raw = m.group(1)
            break

    return clean_url(urljoin(base_url, raw))


def is_pib_release_url(url: str) -> bool:
    url = clean_url(url)
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    raw = f"{path}?{parsed.query}".lower()
    query = {k.lower(): v for k, v in parse_qs(parsed.query).items()}
    if host and not host.endswith("pib.gov.in"):
        return False
    has_prid = "prid" in query or "prid" in raw
    has_release_pattern = any(part in raw for part in ["pressreleasepage.aspx", "pressreleaseiframepage.aspx", "/pressrelease", "pressrelease", "release"])
    return has_prid or has_release_pattern


def pib_release_candidate_url(url: str) -> bool:
    lower = clean_url(url).lower()
    return "prid" in lower or "pressrelease" in lower or "/release" in lower or "releasepage" in lower


def write_pib_debug_files(html_text: str, debug_links: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    PIB_DEBUG_HTML.write_text(html_text, encoding="utf-8")
    PIB_DEBUG_LINKS.write_text(json.dumps(debug_links, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"pib_debug_snapshot_html: {PIB_DEBUG_HTML}")
    print(f"pib_debug_links_json: {PIB_DEBUG_LINKS}")


def is_pib_ministry_heading(text: str) -> bool:
    lower = clean_text(text).lower().strip(":.- ")
    if not lower or len(lower) > 120:
        return False
    if any(b in lower for b in PIB_NAVIGATION_TEXT):
        return False
    return any(lower == prefix or lower.startswith(prefix + " ") for prefix in PIB_MINISTRY_PREFIXES)


def direct_text(tag: Any) -> str:
    parts = []
    for child in getattr(tag, "children", []):
        if isinstance(child, str):
            parts.append(child)
    return clean_text(" ".join(parts))


def ministry_from_context(a_tag: Any, current_ministry: str) -> str:
    for parent in a_tag.parents:
        if not getattr(parent, "find_all", None):
            continue
        for tag in parent.find_all(["h1", "h2", "h3", "h4", "strong", "b", "span", "div"], recursive=False):
            text = clean_text(direct_text(tag) or tag.get_text(" ", strip=True))
            if is_pib_ministry_heading(text):
                return text
    return current_ministry or "PIB Delhi"


def parse_pib_published_date(soup: BeautifulSoup) -> str:
    # The default All Releases page is date scoped by PIB. If a concrete page date is visible,
    # use it; otherwise mark the scrape date in IST so the downstream recency scorer can work.
    text = clean_text(soup.get_text(" ", strip=True))
    m = re.search(r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\b", text, re.I)
    if m:
        try:
            dt = datetime.strptime(" ".join(m.groups()), "%d %B %Y").replace(tzinfo=IST)
            return dt.isoformat(timespec="seconds")
        except Exception:
            pass
    return datetime.now(IST).isoformat(timespec="seconds")


def pib_displayed_count(html_text: str) -> int | None:
    m = re.search(r"Displaying\s+(\d+)\s+Press Releases", html_text or "", re.I)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def pib_last_updated_date(html_text: str) -> datetime | None:
    text = clean_text(BeautifulSoup(html_text or "", "lxml").get_text(" ", strip=True))
    m = re.search(r"Last Updated On:\s*(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})", text, re.I)
    if not m:
        return None
    day, mon, year = m.groups()
    month = MONTH_NAME_TO_NUM.get(mon.lower())
    if not month:
        return None
    try:
        return datetime(int(year), month, int(day), tzinfo=IST)
    except Exception:
        return None


def pib_form_fields(soup: BeautifulSoup) -> dict[str, str]:
    fields: dict[str, str] = {}
    # Preserve ASP.NET hidden fields such as __VIEWSTATE and __EVENTVALIDATION.
    for tag in soup.find_all(["input", "textarea"]):
        name = tag.get("name")
        if not name:
            continue
        typ = (tag.get("type") or "").lower()
        if typ in {"submit", "button", "image", "file"}:
            continue
        fields[name] = tag.get("value", "")
    # Preserve selected select values, then override date/ministry below.
    for sel in soup.find_all("select"):
        name = sel.get("name")
        if not name:
            continue
        opt = sel.find("option", selected=True) or sel.find("option")
        fields[name] = opt.get("value", "") if opt else ""
    return fields


def post_pib_date(session: requests.Session, source_url: str, base_html: str, target_date: datetime, event_target: str = "ctl00$ContentPlaceHolder1$ddlday") -> requests.Response:
    soup = BeautifulSoup(base_html, "lxml")
    fields = pib_form_fields(soup)
    fields["__EVENTTARGET"] = event_target
    fields["__EVENTARGUMENT"] = ""
    fields["ctl00$ContentPlaceHolder1$ddlMinistry"] = "0"
    fields["ctl00$ContentPlaceHolder1$ddlday"] = str(target_date.day)
    fields["ctl00$ContentPlaceHolder1$ddlMonth"] = str(target_date.month)
    fields["ctl00$ContentPlaceHolder1$ddlYear"] = str(target_date.year)
    fields["ctl00$ContentPlaceHolder1$hydregionid"] = "3"
    fields["ctl00$ContentPlaceHolder1$hydLangid"] = "1"
    fields["ctl00$Bar1$ddlregion"] = "3"
    fields["ctl00$Bar1$ddlLang"] = "1"
    return session.post(
        source_url,
        data=fields,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-IN,en;q=0.9", "Referer": source_url},
        timeout=30,
    )


def post_pib_month_all(session: requests.Session, source_url: str, base_html: str, target_date: datetime) -> requests.Response:
    soup = BeautifulSoup(base_html, "lxml")
    fields = pib_form_fields(soup)
    fields["__EVENTTARGET"] = "ctl00$ContentPlaceHolder1$ddlday"
    fields["__EVENTARGUMENT"] = ""
    fields["ctl00$ContentPlaceHolder1$ddlMinistry"] = "0"
    fields["ctl00$ContentPlaceHolder1$ddlday"] = "0"  # All days in selected month.
    fields["ctl00$ContentPlaceHolder1$ddlMonth"] = str(target_date.month)
    fields["ctl00$ContentPlaceHolder1$ddlYear"] = str(target_date.year)
    fields["ctl00$ContentPlaceHolder1$hydregionid"] = "3"
    fields["ctl00$ContentPlaceHolder1$hydLangid"] = "1"
    fields["ctl00$Bar1$ddlregion"] = "3"
    fields["ctl00$Bar1$ddlLang"] = "1"
    return session.post(
        source_url,
        data=fields,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-IN,en;q=0.9", "Referer": source_url},
        timeout=30,
    )


def scrape_pib_all_releases(source: SourceConfig) -> list[dict[str, str]]:
    print(f"\nScraping PIB all releases: {source.name}")
    scraped_at = datetime.now(IST).isoformat(timespec="seconds")

    session = requests.Session()
    base_headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-IN,en;q=0.9"}
    try:
        response = session.get(source.url, headers=base_headers, timeout=30)
        print(f"fetched_url: {getattr(response, 'url', source.url)}")
        print(f"response_status_code: {getattr(response, 'status_code', '')}")
        print(f"response_html_length: {len(getattr(response, 'text', '') or '')}")
        response.raise_for_status()
    except Exception as exc:
        print(f"Failed to fetch PIB all releases {source.url}: {exc}")
        write_pib_debug_files("", [{
            "title": "",
            "href": source.url,
            "normalized_url": source.url,
            "candidate_release_link": False,
            "accepted": False,
            "rejection_reasons": [f"fetch_failed:{exc}"],
        }])
        return []

    # PIB's allRel.aspx is ASP.NET date-scoped. Early in the day it can select today's
    # date and return "Displaying 0 Press Releases" even when the footer says the portal
    # was last updated yesterday. In that case, post back to the last-updated/yesterday
    # dates, then fall back to "All" days for the current month instead of saving [] only.
    html_text = response.text
    initial_count = pib_displayed_count(html_text)
    print(f"pib_initial_displayed_count: {initial_count if initial_count is not None else 'unknown'}")

    now_ist = datetime.now(IST)
    candidates: list[tuple[str, datetime, bool]] = []
    last_updated = pib_last_updated_date(html_text)
    if last_updated:
        candidates.append(("last_updated_date", last_updated, False))
    candidates.append(("today", now_ist, False))
    for delta in range(1, max(1, source.fallback_days_back) + 1):
        candidates.append((f"today_minus_{delta}", now_ist - timedelta(days=delta), False))
    # Final emergency fallback: all days of month. This prevents the All PIB Releases
    # browser from going empty if the daily postback behaves differently.
    candidates.append(("all_days_current_month", now_ist, True))
    if last_updated and (last_updated.month != now_ist.month or last_updated.year != now_ist.year):
        candidates.append(("all_days_last_updated_month", last_updated, True))

    # Try the initial GET first if it already has releases; otherwise try date fallbacks.
    attempt_logs: list[dict[str, Any]] = []
    selected_html = html_text
    selected_label = "initial_get"
    selected_count = initial_count

    if not initial_count:
        for label, dt, all_month in candidates:
            try:
                if all_month:
                    pr = post_pib_month_all(session, source.url, html_text, dt)
                else:
                    pr = post_pib_date(session, source.url, html_text, dt)
                pr.raise_for_status()
                count = pib_displayed_count(pr.text)
                attempt_logs.append({
                    "label": label,
                    "date": dt.strftime("%Y-%m-%d"),
                    "all_month": all_month,
                    "status_code": pr.status_code,
                    "html_length": len(pr.text or ""),
                    "displayed_count": count,
                })
                print(f"pib_date_attempt: {label} {dt.strftime('%Y-%m-%d')} all_month={all_month} displayed_count={count}")
                if count and count > 0:
                    selected_html = pr.text
                    selected_label = label
                    selected_count = count
                    break
            except Exception as exc:
                attempt_logs.append({"label": label, "date": dt.strftime("%Y-%m-%d"), "all_month": all_month, "error": str(exc)})
                print(f"pib_date_attempt_error: {label} {dt.strftime('%Y-%m-%d')} {exc}")

    print(f"pib_selected_date_strategy: {selected_label}")
    print(f"pib_final_displayed_count: {selected_count if selected_count is not None else 'unknown'}")

    soup = BeautifulSoup(selected_html, "lxml")
    published = parse_pib_published_date(soup)
    raw_items: list[dict[str, str]] = []
    seen: set[str] = set()
    current_ministry = ""
    anchors = soup.find_all("a")
    total_anchor_tags_found = len(anchors)
    candidate_release_links_found = 0
    rejected_links_count = 0
    debug_links: list[dict[str, Any]] = []

    for node in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b", "span", "div", "a"]):
        if node.name != "a":
            text = clean_text(direct_text(node) or node.get_text(" ", strip=True))
            if is_pib_ministry_heading(text):
                current_ministry = text
            continue

        href = clean_url(node.get("href"))
        title = clean_text(node.get_text(" ", strip=True))
        url = normalize_pib_release_url(source.url, href)
        is_candidate = pib_release_candidate_url(url or href)
        if is_candidate:
            candidate_release_links_found += 1

        reject_reasons: list[str] = []
        if not href:
            reject_reasons.append("missing_href")
        if not title:
            reject_reasons.append("missing_title")
        elif not pib_title_is_release(title):
            reject_reasons.append("navigation_or_non_release_title")
        if not url or not is_pib_release_url(url):
            reject_reasons.append("non_release_url")
        if url in seen:
            reject_reasons.append("duplicate_url")

        debug_record = {
            "title": title,
            "href": href,
            "normalized_url": url,
            "candidate_release_link": is_candidate,
            "accepted": False,
            "rejection_reasons": reject_reasons,
            "selected_date_strategy": selected_label,
            "displayed_count": selected_count,
        }
        debug_links.append(debug_record)

        if reject_reasons:
            rejected_links_count += 1
            continue
        seen.add(url)
        ministry = ministry_from_context(node, current_ministry)
        news_score, reasons = pib_newsworthiness_score(title, ministry)
        item = make_item(source, title, url, scraped_at, summary="", published=published)
        item["ministry"] = ministry
        item["category"] = "India"
        item["category_lane"] = "India"
        item["pib_newsworthiness_score"] = str(news_score)
        item["pib_score_reasons"] = "; ".join(reasons)
        item["pib_filter_reasons"] = item["pib_score_reasons"]
        item["pib_priority_label"] = pib_priority_label(news_score)
        item["content_angle"] = "India official current-affairs update"
        item["priority"] = "High" if news_score >= 70 else "Medium" if news_score >= 55 else "Low"
        raw_items.append(item)
        debug_record["accepted"] = True

    raw_items.sort(key=lambda x: int(x.get("pib_newsworthiness_score", "0") or 0), reverse=True)
    items = raw_items
    label_counts: dict[str, int] = {}
    for item in items:
        label = item.get("pib_priority_label", "routine")
        label_counts[label] = label_counts.get(label, 0) + 1
    print(f"total_anchor_tags_found: {total_anchor_tags_found}")
    print(f"candidate_release_links_found: {candidate_release_links_found}")
    print(f"rejected_links_count: {rejected_links_count}")
    print(f"pib_links_found: {candidate_release_links_found}")
    print(f"pib_valid_releases_collected: {len(items)}")
    print(f"valid_pib_releases_collected: {len(items)}")
    print(f"Found {len(items)} valid PIB release item(s). PIB priority counts: {label_counts}")
    if not items:
        debug_links.insert(0, {
            "debug_summary": True,
            "initial_displayed_count": initial_count,
            "selected_date_strategy": selected_label,
            "final_displayed_count": selected_count,
            "attempt_logs": attempt_logs,
            "note": "No direct PIB release anchors found in the selected HTML. This usually means the ASP.NET date fallback did not return a date/month with releases, or PIB changed its release-link markup.",
        })
        write_pib_debug_files(selected_html, debug_links)
    time.sleep(source.delay_seconds)
    return items

def scrape_rss(source: SourceConfig) -> list[dict[str, str]]:
    print(f"\nScraping RSS: {source.name}")
    scraped_at = datetime.now(IST).isoformat(timespec="seconds")
    items = []
    feed = feedparser.parse(source.url)
    for entry in feed.entries[:source.max_items]:
        title = clean_text(getattr(entry, "title", ""))
        url = clean_text(getattr(entry, "link", ""))
        summary = clean_text(getattr(entry, "summary", "") or getattr(entry, "description", ""))
        published = clean_text(getattr(entry, "published", "") or getattr(entry, "updated", ""))
        if title and url and len(title.split()) >= 4:
            items.append(make_item(source, title, url, scraped_at, summary, published))
    print(f"Found {len(items)} item(s).")
    time.sleep(source.delay_seconds)
    return items


def first_text(element: Any, selector: str) -> str:
    try:
        if "::text" in selector:
            return clean_text(element.css(selector).getall())
        return clean_text(element.css(selector).get())
    except Exception:
        return ""


def scrape_html(source: SourceConfig) -> list[dict[str, str]]:
    print(f"\nScraping HTML: {source.name}")
    scraped_at = datetime.now(IST).isoformat(timespec="seconds")
    try:
        page = Fetcher.get(source.url)
    except Exception as exc:
        print(f"Failed to fetch {source.url}: {exc}")
        return []
    items = []
    if "en.wikipedia.org/wiki/Portal:Current_events" in source.url:
        try:
            blocks = page.xpath("//div[contains(@class, 'current-events-content')]//li[not(.//ul)]")
        except Exception as exc:
            print(f"Failed to parse Wikipedia current events: {exc}")
            return []
        for block in blocks[:source.max_items]:
            title = clean_text(block.xpath(".//text()").getall())
            href = block.xpath(".//a[contains(@class, 'external')]/@href").get() or block.xpath(".//a/@href").get()
            href = clean_text(href)
            if not title or not href or len(title.split()) < 8 or len(title) > 700:
                continue
            if any(j in title.lower() for j in ["click here","go back","main page","contents","current events","edit"]):
                continue
            items.append(make_item(source, title, urljoin(source.url, href), scraped_at))
        print(f"Found {len(items)} item(s).")
        time.sleep(source.delay_seconds)
        return items

    try:
        blocks = page.css(source.article_selector)
    except Exception as exc:
        print(f"Invalid selector for {source.name}: {exc}")
        return []
    for block in blocks[:source.max_items]:
        title = first_text(block, source.title_selector)
        href = first_text(block, source.link_selector)
        if not title or not href or len(title.split()) < 5:
            continue
        if any(j in title.lower() for j in ["click here","go back","main page","contents","current events","edit"]):
            continue
        items.append(make_item(source, title, urljoin(source.url, href), scraped_at))
    print(f"Found {len(items)} item(s).")
    time.sleep(source.delay_seconds)
    return items


def dedupe(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen, out = set(), []
    for item in items:
        url = item.get("url", "")
        if url and url not in seen:
            seen.add(url)
            out.append(item)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape UnblurBrief configured sources.")
    parser.add_argument(
        "--only-pib",
        action="store_true",
        help="Run only sources with source_type='pib_all_releases'. This avoids paid/keyed APIs and generic source scraping during PIB debugging.",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    sources = load_sources(SOURCES_FILE)
    if args.only_pib:
        sources = [source for source in sources if source.source_type == "pib_all_releases"]
        print("PIB-only mode enabled. No RSS/HTML/API-discovery sources will be scraped by scrape_sources.py.")
        print(f"pib_sources_found_in_sources_json: {len(sources)}")

    items = []
    for source in sources:
        if source.source_type == "rss":
            items.extend(scrape_rss(source))
        elif source.source_type == "pib_all_releases":
            items.extend(scrape_pib_all_releases(source))
        else:
            items.extend(scrape_html(source))
    items = dedupe(items)
    research = load_json(RESEARCH_OUTPUT, {})
    if not isinstance(research, dict):
        research = {}
    save_pib_all_releases(items, research_by_url=research)

    if not args.only_pib:
        JSON_OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        with CSV_OUTPUT.open("w", encoding="utf-8", newline="") as f:
            fieldnames = ["source","source_name","source_url","source_type","trust_role","category","category_lane","title","url","summary","published","scraped_at","priority","content_angle","used_for_post","ministry","pib_newsworthiness_score","pib_priority_label","pib_score_reasons","pib_filter_reasons"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                writer.writerow({k: item.get(k, "") for k in fieldnames})
        print(f"JSON: {JSON_OUTPUT}")
        print(f"CSV:  {CSV_OUTPUT}")

    print("\nDone.")
    print(f"Total unique item(s): {len(items)}")
    if args.only_pib:
        print(f"PIB all releases JSON: {PIB_ALL_OUTPUT}")
        print(f"PIB debug snapshot HTML: {PIB_DEBUG_HTML}")
        print(f"PIB debug links JSON: {PIB_DEBUG_LINKS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
