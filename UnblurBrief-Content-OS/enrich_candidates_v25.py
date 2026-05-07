
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
CANDIDATES = OUTPUT / "top_post_candidates.json"
INPUT = OUTPUT / "unblurbrief_sources.json"
PUBLIC_SOURCES = OUTPUT / "public_api_v25_sources.json"
RESEARCH = OUTPUT / "research_cache.json"
PIB_ALL_RELEASES = OUTPUT / "pib_all_releases.json"

INDIA_TERMS = [
    "india", "indian", "new delhi", "government of india", "union government",
    "indian ministry", "ministry of", "delhi", "mumbai", "bengaluru", "bangalore", "hyderabad",
    "chennai", "kolkata", "kerala", "odisha", "tamil nadu", "karnataka", "maharashtra",
    "west bengal", "uttar pradesh", "gujarat", "rajasthan", "lok sabha", "rajya sabha",
    "rbi", "reserve bank of india", "sebi", "election commission of india",
    "supreme court of india", "parliament of india", "isro", "niti aayog",
    "narendra modi", "modi government"
]
TECH_TERMS = [
    "ai", "artificial intelligence", "openai", "anthropic", "google", "microsoft", "meta", "apple",
    "xai", "cybersecurity", "cyber", "semiconductor", "chip", "nvidia", "startup", "data privacy",
    "software", "developer", "cloud", "robotics", "llm"
]
BUSINESS_TERMS = [
    "rbi", "reserve bank of india", "sebi", "inflation", "gdp", "market", "stock", "bank",
    "business", "economy", "rupee", "oil", "trade", "ipo", "earnings", "finance", "monetary",
    "rate cut", "rate hike", "tariff", "exports", "fdi"
]
US_POLITICS_TERMS = [
    "democrat", "democrats", "republican", "republicans", "senate", "michigan", "california",
    "texas", "trump", "biden", "u.s.", "us election", "special election", "congressional district"
]
LOW_VALUE_TERMS = [
    "celebrity", "movie", "film", "bollywood", "hollywood", "cricket", "football", "tennis",
    "fashion", "dating", "horoscope", "lottery", "viral video"
]
EXAM_VALUE_TERMS = [
    "rbi", "sebi", "supreme court of india", "parliament", "lok sabha", "rajya sabha",
    "gdp", "inflation", "world bank", "imf", "election commission of india", "policy",
    "regulation", "national security", "cybersecurity", "climate", "trade", "budget"
]
TRUST_BONUS = {
    "publisher_api": 24, "official_api": 24, "data_api": 20, "manual": 22,
    "manual-article-text": 24, "verified_extracted_article": 24, "extracted_article": 18,
    "primary_official": 24, "rss": 5, "discovery_only": -16,
    "aggregator": -20, "metadata_only": -18,
}
SOURCE_BONUS = {
    "Guardian - India": 16, "Guardian": 16, "World Bank API": 15,
    "Hacker News API": 8, "Wikipedia Current Events API": 4, "GDELT": 3,
    "PIB Delhi All Releases - English": 15,
}
CATEGORY_BONUS = {"India": 30, "Technology": 24, "Business": 24, "World": 12, "Current Affairs": 8}


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def text_blob(item: dict[str, Any]) -> str:
    return " ".join([
        clean(item.get("title")), clean(item.get("summary")), clean(item.get("category")),
        clean(item.get("content_angle")), clean(item.get("url")), clean(item.get("source")),
    ]).lower()


def content_blob(item: dict[str, Any]) -> str:
    facts = item.get("key_facts") or item.get("extracted_key_facts") or []
    facts_text = " ".join(clean(f) for f in facts if clean(f)) if isinstance(facts, list) else clean(facts)
    return " ".join([
        clean(item.get("title")),
        clean(item.get("summary")),
        clean(item.get("api_body_text")),
        clean(item.get("article_text")),
        clean(item.get("excerpt")),
        facts_text,
    ]).lower()


def contains_phrase(text: str, phrase: str) -> bool:
    p = phrase.lower().strip()
    if not p:
        return False
    if len(p) <= 3:
        return bool(re.search(rf"\b{re.escape(p)}\b", text))
    return p in text


def contains_any(text: str, terms: list[str]) -> bool:
    return any(contains_phrase(text, t) for t in terms)


def is_pib_item(item: dict[str, Any]) -> bool:
    source = clean(item.get("source") or item.get("source_name")).lower()
    return item.get("source_type") == "pib_all_releases" or "pib delhi all releases" in source


def pib_score_value(item: dict[str, Any]) -> int:
    try:
        return int(float(item.get("pib_newsworthiness_score", 0) or 0))
    except Exception:
        return 0


def pib_priority_label(item: dict[str, Any]) -> str:
    label = clean(item.get("pib_priority_label")).lower()
    if label in {"strong", "usable", "routine"}:
        return label
    score = pib_score_value(item)
    if score >= 70:
        return "strong"
    if score >= 55:
        return "usable"
    return "routine"


def classify(item: dict[str, Any]) -> str:
    if is_pib_item(item):
        return "India"

    text = text_blob(item)
    content = content_blob(item)
    cat = clean(item.get("category")).lower()

    # Hard rule: India lane only with India-specific content or explicit PIB handling.
    # Generic source/category labels like "Guardian - India" do not count.
    if contains_any(content, INDIA_TERMS):
        return "India"

    if contains_any(content, US_POLITICS_TERMS):
        return "World"

    if "technology" in cat or "tech" in cat or contains_any(text, TECH_TERMS):
        return "Technology"

    if "business" in cat or "economy" in cat or contains_any(text, BUSINESS_TERMS):
        return "Business"

    if any(w in cat for w in ["world", "international", "politics", "foreign"]):
        return "World"

    fallback = clean(item.get("category")) or "Current Affairs"
    if "india" in fallback.lower():
        return "Current Affairs"
    return fallback


def count_facts(item: dict[str, Any]) -> int:
    facts = item.get("key_facts") or item.get("extracted_key_facts") or []
    n = len([f for f in facts if clean(f)]) if isinstance(facts, list) else 0
    body = clean(item.get("api_body_text") or item.get("article_text") or item.get("excerpt") or item.get("summary"))
    words = len(body.split())
    if words > 900: n += 7
    elif words > 600: n += 5
    elif words > 300: n += 3
    elif words > 120: n += 2
    elif words > 50: n += 1
    return n


def recency_score(item: dict[str, Any]) -> int:
    raw = clean(item.get("published") or item.get("published_at") or item.get("date"))
    if not raw:
        return 0
    try:
        if raw.endswith("Z"):
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            try:
                dt = datetime.fromisoformat(raw)
            except Exception:
                dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600
        if age_hours <= 24: return 16
        if age_hours <= 72: return 12
        if age_hours <= 168: return 7
        if age_hours <= 720: return 2
        return -4
    except Exception:
        return 0



def apply_research_to_item(item: dict[str, Any], research_by_url: dict[str, Any]) -> dict[str, Any]:
    url = clean(item.get("url"))
    research = research_by_url.get(url) if isinstance(research_by_url, dict) else None
    if not isinstance(research, dict):
        return item

    status = clean(research.get("status")).lower()
    method = clean(research.get("method")).lower()
    excerpt = clean(research.get("excerpt"))
    facts = research.get("key_facts") if isinstance(research.get("key_facts"), list) else []
    word_count = len(excerpt.split())
    fact_count = len([f for f in facts if clean(f)])

    if excerpt:
        item["article_text"] = excerpt
        item["key_facts"] = facts
        item["research_extraction_status"] = status
        item["extraction_method"] = method
        item["source_verification_note"] = f"Research cache applied: {status}, {method}, {word_count} words, {fact_count} facts."

    if status == "ok" and word_count >= 250 and fact_count >= 3:
        item["trust_role"] = "verified_extracted_article"
        item["reliability_state"] = "verified"
        item["is_publishable_source"] = True
        item["reliability_score"] = max(int(float(item.get("reliability_score", 0) or 0)), 86)
    elif status == "ok" and word_count >= 80:
        item["trust_role"] = "extracted_article"
        item["reliability_state"] = "usable_with_caution"
        item["is_publishable_source"] = True
        item["reliability_score"] = max(int(float(item.get("reliability_score", 0) or 0)), 68)

    return item


def source_reliability_defaults(item: dict[str, Any]) -> dict[str, Any]:
    trust = clean(item.get("trust_role")) or "discovery_only"
    if trust in {"publisher_api", "data_api", "official_api", "manual", "manual-article-text", "verified_extracted_article", "extracted_article"} or item.get("api_body_text") or item.get("article_text"):
        if trust == "verified_extracted_article":
            state = item.get("reliability_state") or "verified"
            score = item.get("reliability_score", 86)
        elif trust == "extracted_article":
            state = item.get("reliability_state") or "usable_with_caution"
            score = item.get("reliability_score", 72)
        else:
            state = item.get("reliability_state") or "usable_with_caution"
            score = item.get("reliability_score", 78 if trust == "data_api" else 82)
        publishable = item.get("is_publishable_source", True)
    else:
        state = item.get("reliability_state") or "source_check_required"
        score = item.get("reliability_score", 35)
        publishable = item.get("is_publishable_source", False)

    item["reliability_state"] = state
    item["reliability_score"] = score
    item["is_publishable_source"] = publishable
    return item


def slide_count_for(item: dict[str, Any]) -> int:
    category = classify(item)
    reliability = clean(item.get("reliability_state")).lower()
    trust_role = clean(item.get("trust_role")).lower()
    facts = count_facts(item)
    text = text_blob(item)

    if trust_role in {"discovery_only", "aggregator", "metadata_only"} or reliability == "source_check_required":
        return 3
    if facts >= 11:
        return 6
    if category in {"India", "Technology", "Business"} and facts >= 6:
        return 5
    if contains_any(text, EXAM_VALUE_TERMS) and facts >= 4:
        return 5
    if facts >= 4:
        return 4
    return 3


def structure_for(n: int) -> list[str]:
    return {
        3: ["What happened", "Why it matters", "Bottom line"],
        4: ["The issue, simplified", "Background", "Latest development", "Bottom line"],
        5: ["The issue, simplified", "Background", "Latest development", "Why people/countries/markets care", "Bottom line"],
        6: ["Hook", "What happened", "Background", "Key details", "Why it matters", "What to watch next"],
    }.get(n, ["What happened", "Why it matters", "Bottom line"])


def score_item(item: dict[str, Any]) -> tuple[int, dict[str, int]]:
    text = text_blob(item)
    content = content_blob(item)
    category = classify(item)
    trust = clean(item.get("trust_role")) or "discovery_only"
    source = clean(item.get("source"))
    reliability_state = clean(item.get("reliability_state"))
    reliability_score = int(float(item.get("reliability_score", 0) or 0))
    facts = count_facts(item)
    breakdown: dict[str, int] = {}

    def add(k: str, v: int):
        breakdown[k] = breakdown.get(k, 0) + int(v)

    add("base", 40)
    add("category_relevance", CATEGORY_BONUS.get(category, 6))
    add("trust_role", TRUST_BONUS.get(trust, -8 if trust else -10))
    add("source_quality", SOURCE_BONUS.get(source, 0))
    add("reliability", max(-22, min(22, round((reliability_score - 50) / 2))))
    add("fact_depth", min(18, facts * 3))
    add("recency", recency_score(item))

    if clean(item.get("api_body_text") or item.get("article_text") or item.get("excerpt")):
        add("article_body_available", 12)
    if contains_any(text, EXAM_VALUE_TERMS):
        add("exam_value", 12)
    if is_pib_item(item) or contains_any(content, INDIA_TERMS):
        add("india_specific", 12)
    if contains_any(text, TECH_TERMS) and category == "Technology":
        add("tech_relevance", 7)
    if contains_any(text, BUSINESS_TERMS) and category == "Business":
        add("business_relevance", 7)
    if reliability_state == "source_check_required":
        add("source_check_penalty", -18)
    if contains_any(text, LOW_VALUE_TERMS):
        add("low_value_penalty", -25)
    if category == "World" and contains_any(text, US_POLITICS_TERMS):
        add("foreign_politics_corrected", 3)
    if is_pib_item(item):
        pib_score = pib_score_value(item)
        label = pib_priority_label(item)
        add("pib_newsworthiness", max(-30, min(30, round((pib_score - 55) / 2))))
        if label == "strong":
            add("pib_priority", 18)
        elif label == "usable":
            add("pib_priority", 8)
        else:
            add("pib_priority", -35)

    previous = int(float(item.get("score", 0) or 0))
    if previous:
        add("previous_score_limited", max(-5, min(10, round((previous - 70) / 10))))

    total = max(0, min(100, sum(breakdown.values())))
    if is_pib_item(item):
        label = pib_priority_label(item)
        cap = 100 if label == "strong" else 84 if label == "usable" else 54
        if total > cap:
            add("pib_priority_cap", cap - total)
            total = cap
    return total, breakdown


def make_prompt(item: dict[str, Any]) -> str:
    n = int(item.get("recommended_slide_count") or 3)
    structure = item.get("recommended_structure") or structure_for(n)
    facts_context = clean(item.get("api_body_text") or item.get("article_text") or item.get("excerpt") or item.get("summary"))
    category = classify(item)
    verified_line = "Use the extracted article/data context inside this prompt as the primary source." if item.get("is_publishable_source") else "This is discovery/metadata only. If details require verification, write “source check required” rather than guessing."
    pib_lines = ""
    if is_pib_item(item):
        pib_lines = f"""- Ministry: {clean(item.get("ministry")) or "not available"}
- PIB priority label: {pib_priority_label(item)}
- PIB newsworthiness score: {pib_score_value(item)}
- PIB score reasons: {clean(item.get("pib_score_reasons") or item.get("pib_filter_reasons"))}
"""

    slides = "\n".join([f"{i+1}. {name}" for i, name in enumerate(structure)])
    slide_sections = "\n\n".join([f"### Slide {i+1}\n[approved slide {i+1} copy]" for i in range(n)])

    return f"""You are creating a premium Instagram carousel text package for **UnblurBrief**.

Brand:
- UnblurBrief is a clean, sharp, non-clickbait news/current-affairs Instagram page.
- Style: minimal, high-trust, modern, concise, exam-aware.
- Tone: neutral, direct, clear, non-sensational.
- Visual identity: flexible high-impact editorial palette, strong image-led visuals, compact @unblurbrief footer.
- Handle: @unblurbrief

Source item:
- Title: {clean(item.get("title"))}
- URL: {clean(item.get("url"))}
- Source: {clean(item.get("source"))}
- Source role: {clean(item.get("trust_role"))}
- Category: {category}
- Priority: {clean(item.get("priority"))}
- Content angle: {clean(item.get("content_angle"))}
- Recommended slide count: {n}
{pib_lines}

Research / context:
{facts_context or "source check required"}

Task:
Create the finished TEXT package for a {n}-slide Instagram carousel. Do not generate images.

Rules:
- {verified_line}
- Do not ask to browse the web.
- Do not invent facts beyond the source item and research context.
- If details require source verification, write “source check required” rather than guessing.
- Do not use political bias.
- Do not sensationalize deaths, war, crime, fire, accidents, or conflict.
- Keep the copy mobile-first.
- Mention @unblurbrief on every slide.
- Make it useful for students and general readers.
- Keep slide copy short enough to fit into designed carousel slides.
- Avoid repeating the same data point across multiple slides.
- Each slide must teach or clarify a different part of the story.
- Use exactly {n} slides.

Use this exact {n}-slide carousel structure:
{slides}

Return the output using EXACTLY these section headings:

## CAROUSEL_TITLE
[title here]

## SLIDE_COPY
{slide_sections}

## VISUAL_DIRECTION
{slide_sections.replace("[approved slide", "[visual direction for slide").replace("copy]", "]")}

## CAPTION
[caption here]

## HASHTAGS
[hashtags here]

## VERIFICATION_CHECKLIST
[checklist here]
"""


def seed_to_candidate(seed: dict[str, Any], idx: int) -> dict[str, Any]:
    item = dict(seed)
    item.setdefault("score", 50)
    item.setdefault("post_format", "Explained Simply")
    item.setdefault("visual_style", "Colorful image-led editorial explainer")
    item.setdefault("visual_elements", "symbolic news visuals, maps, dashboards, cards, timelines, verified-facts panels")
    item.setdefault("image_safety_note", "Use safe symbolic visuals only. Avoid graphic imagery, identifiable real people, or fake logos.")
    item.setdefault("design_route", {"name": "Data Colorburst Brief", "summary": "vivid editorial explainer with strong visual anchor and clean hierarchy"})
    item.setdefault("color_mood", {"name": "Editorial Colorburst", "palette": "deep blue, teal, orange accent, off-white, optional bright contrast"})
    item.setdefault("image_led_style", "symbolic editorial collage or clean illustrated explainer")
    item.setdefault("layout_family", "variable editorial card system")
    item.setdefault("hero_metaphor", "topic-specific symbolic object")
    item.setdefault("slide_flow_pattern", "dynamic story-specific flow")
    return item


def enrich_item(item: dict[str, Any], research_by_url: dict[str, Any] | None = None) -> dict[str, Any]:
    item = apply_research_to_item(item, research_by_url or {})
    item = source_reliability_defaults(item)
    category = classify(item)
    n = slide_count_for(item)
    score, breakdown = score_item(item)

    item["category_lane"] = category
    item["recommended_slide_count"] = n
    item["recommended_structure"] = structure_for(n)
    item["score"] = score
    item["score_breakdown"] = breakdown
    item["classification_note"] = "V26 strict classifier: India lane requires India-specific content terms or explicit PIB handling; source/category labels alone do not count."
    item["content_prompt"] = make_prompt(item)
    return item


def pib_release_record(item: dict[str, Any], recommended_urls: set[str]) -> dict[str, Any]:
    url = clean(item.get("url"))
    article_text = clean(item.get("article_text") or item.get("api_body_text") or item.get("excerpt"))
    record: dict[str, Any] = {
        "title": clean(item.get("title")),
        "url": url,
        "source": clean(item.get("source") or item.get("source_name") or "PIB Delhi All Releases - English"),
        "source_name": clean(item.get("source_name") or item.get("source")),
        "source_url": clean(item.get("source_url")),
        "source_type": clean(item.get("source_type") or "pib_all_releases"),
        "trust_role": clean(item.get("trust_role") or "primary_official"),
        "ministry": clean(item.get("ministry")),
        "published": clean(item.get("published")),
        "scraped_at": clean(item.get("scraped_at")),
        "pib_newsworthiness_score": clean(item.get("pib_newsworthiness_score")),
        "pib_score_reasons": clean(item.get("pib_score_reasons") or item.get("pib_filter_reasons")),
        "pib_priority_label": pib_priority_label(item),
        "extraction_status": clean(item.get("research_extraction_status")),
        "recommended_candidate": url in recommended_urls,
        "score": item.get("score", 0),
        "score_breakdown": item.get("score_breakdown", {}),
        "reliability_state": item.get("reliability_state", ""),
        "reliability_score": item.get("reliability_score", ""),
        "recommended_slide_count": item.get("recommended_slide_count", 3),
        "recommended_structure": item.get("recommended_structure", []),
        "content_prompt": item.get("content_prompt", ""),
    }
    if article_text:
        record["article_text"] = article_text
    return record


def write_pib_all_releases(selected: list[dict[str, Any]], research_by_url: dict[str, Any]) -> list[dict[str, Any]]:
    source_items = load_json(INPUT, [])
    if not isinstance(source_items, list):
        source_items = []
    pib_sources = [dict(item) for item in source_items if is_pib_item(item)]

    if not pib_sources:
        existing = load_json(PIB_ALL_RELEASES, [])
        pib_sources = [dict(item) for item in existing if isinstance(item, dict) and is_pib_item(item)] if isinstance(existing, list) else []

    recommended_urls = {clean(item.get("url")) for item in selected if is_pib_item(item)}
    records = [pib_release_record(enrich_item(item, research_by_url), recommended_urls) for item in pib_sources if clean(item.get("url"))]
    records.sort(key=lambda x: (x.get("recommended_candidate", False), int(float(x.get("pib_newsworthiness_score") or 0)), int(float(x.get("score") or 0))), reverse=True)
    save_json(PIB_ALL_RELEASES, records)

    hidden_routine = sum(1 for item in records if item.get("pib_priority_label") == "routine" and not item.get("recommended_candidate"))
    print(f"pib_valid_releases_collected: {len(records)}")
    print(f"pib_saved_to_pib_all_releases_json: {len(records)}")
    print(f"pib_added_to_top_candidates: {len(recommended_urls)}")
    print(f"pib_hidden_as_routine: {hidden_routine}")
    return records


def main() -> int:
    candidates = load_json(CANDIDATES, [])
    if not isinstance(candidates, list):
        candidates = []

    seeds = load_json(PUBLIC_SOURCES, [])
    if isinstance(seeds, list):
        existing_urls = {clean(c.get("url")) for c in candidates}
        for seed in seeds:
            if clean(seed.get("url")) and clean(seed.get("url")) in existing_urls:
                continue
            candidates.append(seed_to_candidate(seed, len(candidates) + 1))
            existing_urls.add(clean(seed.get("url")))

    research_by_url = load_json(RESEARCH, {})
    if not isinstance(research_by_url, dict):
        research_by_url = {}

    enriched = [enrich_item(dict(c), research_by_url) for c in candidates if clean(c.get("title"))]
    enriched.sort(key=lambda c: int(c.get("score") or 0), reverse=True)

    lane_counts: dict[str, int] = {}
    selected = []
    caps = {"India": 22, "Technology": 18, "Business": 18, "World": 12, "Current Affairs": 10}
    for c in enriched:
        lane = c.get("category_lane", "Current Affairs")
        cap = caps.get(lane, 8)
        if lane_counts.get(lane, 0) >= cap:
            continue
        selected.append(c)
        lane_counts[lane] = lane_counts.get(lane, 0) + 1
        if len(selected) >= 70:
            break

    write_pib_all_releases(selected, research_by_url)
    save_json(CANDIDATES, selected)
    print(f"V26 enriched {len(selected)} candidates.")
    print("Lane counts:", lane_counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
