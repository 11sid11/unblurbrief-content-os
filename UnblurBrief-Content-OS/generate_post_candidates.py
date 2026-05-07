from __future__ import annotations

import json
import hashlib
from random import Random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


IST = timezone(timedelta(hours=5, minutes=30))
ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
DATA = ROOT / "data"
INPUT = OUTPUT / "unblurbrief_sources.json"
RESEARCH = OUTPUT / "research_cache.json"
CANDIDATES = OUTPUT / "top_post_candidates.json"
PROMPTS = OUTPUT / "unblurbrief_post_prompts.md"
USED = DATA / "used_sources.json"
PIB_ALL_RELEASES = OUTPUT / "pib_all_releases.json"

GENERIC_BOILERPLATE = [
    "comprehensive, up-to-date news coverage, aggregated from sources all over the world by google news",
    "full coverage",
    "view full coverage",
    "coverage, aggregated from sources",
]

HIGH_RISK_KEYWORDS = [
    "politics", "election", "vote", "result", "government", "parliament", "minister",
    "war", "conflict", "strike", "missile", "killed", "injured", "crime", "fraud",
    "court", "legal", "policy", "rbi", "sebi", "inflation", "gdp", "rate",
    "health", "outbreak", "vaccine", "death", "casualty",
]

OFFICIAL_TRUST_ROLES = {"primary_official", "publisher_api", "manual_verified", "verified_extracted_article", "extracted_article"}
DISCOVERY_ROLES = {"discovery_only", "discovery_crosscheck", "discovery_api"}

INDIA_CONTENT_TERMS = [
    "india", "indian", "new delhi", "government of india", "union government",
    "indian ministry", "ministry of", "rbi", "reserve bank of india", "sebi",
    "isro", "lok sabha", "rajya sabha", "supreme court of india",
    "election commission of india", "parliament of india", "niti aayog",
]


def normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def load(path: Path, fallback: Any):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save_json(data, path: Path):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def contains_any(text: str, keywords: list[str]) -> bool:
    text = text.lower()
    return any(k in text for k in keywords)


def content_blob(item: dict[str, Any]) -> str:
    return " ".join([
        normalize(item.get("title")),
        normalize(item.get("summary")),
        normalize(item.get("api_body_text")),
        normalize(item.get("article_text")),
        normalize(item.get("excerpt")),
    ]).lower()


def is_pib_item(item: dict[str, Any]) -> bool:
    source = normalize(item.get("source") or item.get("source_name")).lower()
    return item.get("source_type") == "pib_all_releases" or "pib delhi all releases" in source


def pib_score_value(item: dict[str, Any]) -> int:
    try:
        return int(float(item.get("pib_newsworthiness_score", 0) or 0))
    except Exception:
        return 0


def pib_priority_label(item: dict[str, Any]) -> str:
    label = normalize(item.get("pib_priority_label")).lower()
    if label in {"strong", "usable", "routine"}:
        return label
    score = pib_score_value(item)
    if score >= 70:
        return "strong"
    if score >= 55:
        return "usable"
    return "routine"


def pib_priority_rank(item: dict[str, Any]) -> int:
    return {"strong": 2, "usable": 1, "routine": 0}.get(pib_priority_label(item), 0)


def pib_release_record(item: dict[str, Any], research_by_url: dict[str, Any], recommended_urls: set[str]) -> dict[str, Any]:
    url = normalize(item.get("url"))
    research = research_by_url.get(url, {}) if isinstance(research_by_url, dict) else {}
    if not isinstance(research, dict):
        research = {}
    article_text = normalize(item.get("article_text") or item.get("api_body_text") or research.get("excerpt"))
    record: dict[str, Any] = {
        "title": normalize(item.get("title")),
        "url": url,
        "source": normalize(item.get("source") or item.get("source_name") or "PIB Delhi All Releases - English"),
        "source_name": normalize(item.get("source_name") or item.get("source")),
        "source_url": normalize(item.get("source_url")),
        "source_type": normalize(item.get("source_type") or "pib_all_releases"),
        "trust_role": normalize(item.get("trust_role") or "primary_official"),
        "category_lane": normalize(item.get("category_lane") or "India"),
        "ministry": normalize(item.get("ministry")),
        "published": normalize(item.get("published")),
        "scraped_at": normalize(item.get("scraped_at")),
        "pib_newsworthiness_score": normalize(item.get("pib_newsworthiness_score")),
        "pib_score_reasons": normalize(item.get("pib_score_reasons") or item.get("pib_filter_reasons")),
        "pib_priority_label": pib_priority_label(item),
        "extraction_status": normalize(item.get("research_extraction_status") or research.get("status")),
        "recommended_candidate": url in recommended_urls,
        "score": item.get("score", ""),
        "reliability_state": item.get("reliability_state", ""),
        "reliability_score": item.get("reliability_score", ""),
        "content_prompt": item.get("content_prompt", ""),
    }
    if article_text:
        record["article_text"] = article_text
    return record


def update_pib_all_releases(items: list[dict[str, Any]], top: list[dict[str, Any]], research_by_url: dict[str, Any]) -> None:
    pib_items = [item for item in items if is_pib_item(item)]
    recommended_urls = {normalize(item.get("url")) for item in top if is_pib_item(item)}
    records = [pib_release_record(item, research_by_url, recommended_urls) for item in pib_items]
    records.sort(key=lambda x: (x.get("recommended_candidate", False), int(float(x.get("pib_newsworthiness_score") or 0))), reverse=True)
    save_json(records, PIB_ALL_RELEASES)
    hidden_routine = sum(1 for r in records if r.get("pib_priority_label") == "routine" and not r.get("recommended_candidate"))
    print(f"pib_saved_to_pib_all_releases_json: {len(records)}")
    print(f"pib_added_to_top_candidates: {len(recommended_urls)}")
    print(f"pib_hidden_as_routine: {hidden_routine}")


def is_high_risk_topic(item: dict[str, Any]) -> bool:
    combined = " ".join([item.get("title", ""), item.get("category", ""), item.get("content_angle", ""), item.get("priority", "")]).lower()
    return contains_any(combined, HIGH_RISK_KEYWORDS) or item.get("priority") == "High"


def is_generic_boilerplate(text: str) -> bool:
    lower = normalize(text).lower()
    return any(bp in lower for bp in GENERIC_BOILERPLATE)


def duplicate_ratio(facts: list[str]) -> float:
    if not facts:
        return 1.0
    normalized = [normalize(f).lower()[:160] for f in facts if normalize(f)]
    if not normalized:
        return 1.0
    return 1 - (len(set(normalized)) / len(normalized))


def assessSourceReliability(item: dict[str, Any], research_by_url: dict[str, Any]) -> dict[str, Any]:
    url = item.get("url", "")
    research = research_by_url.get(url)
    title = normalize(item.get("title", ""))
    summary = normalize(item.get("summary", ""))
    trust_role = item.get("trust_role", "discovery_only")
    high_risk = is_high_risk_topic(item)

    reasons: list[str] = []
    missing: list[str] = []
    verification_tasks = [
        "Open the original source URL.",
        "Confirm the article body text.",
        "Verify all numbers, names, claims, dates, and quotes.",
        "Check whether the source is primary, credible, or syndicated.",
        "Check whether the topic is politically sensitive or high-risk.",
    ]

    if trust_role in DISCOVERY_ROLES:
        reasons.append(f"Source role is {trust_role}; this is a discovery/cross-check lead, not a production source by itself.")

    if not research:
        return {"state":"source_check_required","score":0,"high_risk":high_risk,"trust_role":trust_role,"reasons":reasons+["Article extraction has not been run yet."],"missing":["actual article body","confirmed claims","key numbers/data","named parties/entities","quotes/statements","context/background","consequences/next steps"],"verification_tasks":verification_tasks}

    status = normalize(research.get("status", "")).lower()
    method = normalize(research.get("method", "")).lower()
    warnings = [normalize(w).lower() for w in research.get("warnings", [])]
    excerpt = normalize(research.get("excerpt", ""))
    facts = [normalize(f) for f in research.get("key_facts", []) if normalize(f)]
    word_count = len(excerpt.split())
    fact_word_count = sum(len(f.split()) for f in facts)
    combined_text = " ".join([excerpt, " ".join(facts), summary]).lower()

    # V28.2: strong single-source extraction should become publishable and feed the prompt.
    if status == "ok" and method not in {"meta", "rss-summary", "none", "unknown"} and word_count >= 250 and len(facts) >= 3:
        return {
            "state": "verified",
            "score": 86,
            "high_risk": high_risk,
            "trust_role": "verified_extracted_article",
            "reasons": [f"Strong article extraction available via {method}: {word_count} words and {len(facts)} key facts."],
            "missing": [],
            "verification_tasks": verification_tasks,
        }

    score = 100

    if trust_role in DISCOVERY_ROLES:
        score -= 30
    elif trust_role in OFFICIAL_TRUST_ROLES:
        score += 10

    if method in {"manual-article-text", "publisher-api-body"}:
        score += 25
        reasons.append("Manual full article text override is available.")

    if status in {"failed", "empty"}:
        score -= 100
        reasons.append(f"Extraction status is {status}.")
    elif status in {"summary_only"}:
        score -= 70
        reasons.append("Only RSS/meta summary was extracted.")
    elif status in {"partial"}:
        score -= 45
        reasons.append("Extraction status is partial.")
    elif status not in {"ok"}:
        score -= 50
        reasons.append(f"Extraction status is unclear: {status or 'missing'}.")

    if method in {"meta", "rss-summary", "none", "unknown"}:
        score -= 45
        reasons.append(f"Extraction method is {method or 'missing'}, not a full article-body extraction.")

    if any("source check" in w or "incomplete" in w or "partial" in w for w in warnings):
        score -= 35
        reasons.append("Extractor warning indicates incomplete/source-check-needed extraction.")

    if word_count < 80:
        score -= 45
        reasons.append(f"Extracted body is too short ({word_count} words).")
    elif word_count < 180:
        score -= 20
        reasons.append(f"Extracted body is short ({word_count} words).")

    if fact_word_count < 40:
        score -= 25
        reasons.append("Extracted key facts are too thin.")

    if is_generic_boilerplate(combined_text):
        score -= 70
        reasons.append("Extracted text contains generic aggregator boilerplate instead of article facts.")

    if duplicate_ratio(facts) > 0.45:
        score -= 20
        reasons.append("Extracted facts look duplicated or repetitive.")

    if high_risk:
        score -= 10
        reasons.append("Topic is high-risk, so stricter reliability threshold applies.")

    missing_candidates = [
        ("actual article body", word_count < 180 or method in {"meta", "rss-summary", "none", "unknown"}),
        ("confirmed claims", fact_word_count < 40),
        ("key numbers/data", True),
        ("named parties/entities", True),
        ("quotes/statements", True),
        ("context/background", word_count < 250),
        ("consequences/next steps", word_count < 250),
    ]
    missing = [name for name, condition in missing_candidates if condition]

    if status in {"failed", "empty"}:
        state = "failed"
    else:
        verified_threshold = 75 if not high_risk else 85
        caution_threshold = 55 if not high_risk else 70
        if method in {"manual-article-text", "publisher-api-body"} and word_count >= 180:
            verified_threshold -= 15
            caution_threshold -= 15
        if trust_role in DISCOVERY_ROLES and method not in {"manual-article-text", "publisher-api-body"}:
            # Discovery sources can only publish if we actually got a strong article body.
            verified_threshold += 10
            caution_threshold += 10
        if score >= verified_threshold:
            state = "verified"
        elif score >= caution_threshold:
            state = "usable_with_caution"
        else:
            state = "source_check_required"

    return {"state":state,"score":max(0,min(100,score)),"high_risk":high_risk,"trust_role":trust_role,"reasons":reasons or ["Extraction appears article-level enough for this risk category."],"missing":missing,"verification_tasks":verification_tasks}


def isPublishableSource(assessment: dict[str, Any]) -> bool:
    return assessment.get("state") in {"verified", "usable_with_caution"}


def choose_post_format(item):
    title = item.get("title", "").lower()
    angle = item.get("content_angle", "").lower()
    category = item.get("category", "").lower()
    if "banking" in angle or "economy" in angle or "markets" in angle or "regulation" in angle:
        return "Exam Lens"
    if "geopolitics" in angle:
        return "Explained Simply"
    if angle == "politics explainer":
        return "What Happened?"
    if "science" in angle or "space" in angle or "health" in angle:
        return "Why It Matters"
    if any(w in title for w in ["killed","injured","fire","explosion","crash","attack"]):
        return "What Happened?"
    if "india" in category:
        return "Why It Matters"
    return "Explained Simply"


def slide_structure(fmt):
    return {
        "What Happened?": "1. Hook\n2. What happened\n3. Who/what is involved\n4. Why it matters\n5. What to watch next / takeaway",
        "Why It Matters": "1. Hook\n2. The update\n3. Why it matters\n4. Broader context\n5. Key takeaway",
        "Exam Lens": "1. Current affairs in 60 seconds\n2. Institution involved\n3. Decision/action\n4. Static context\n5. Remember this",
        "Explained Simply": "1. The issue, simplified\n2. Background\n3. Latest development\n4. Why people/countries/markets care\n5. Bottom line",
    }.get(fmt, "1. The issue, simplified\n2. Background\n3. Latest development\n4. Why people/countries/markets care\n5. Bottom line")


def score(item, used_urls):
    title = normalize(item.get("title", ""))
    url = normalize(item.get("url", ""))
    source = normalize(item.get("source", ""))
    category = normalize(item.get("category", ""))
    priority = normalize(item.get("priority", ""))
    angle = normalize(item.get("content_angle", ""))
    trust = normalize(item.get("trust_role", "discovery_only"))
    combined = f"{title} {url} {source} {category} {angle}".lower()
    content = content_blob(item)
    value = 0
    if url in used_urls or item.get("used_for_post", "").lower() == "yes":
        value -= 100
    value += {"High": 40, "Medium": 25, "Low": 5}.get(priority, 0)
    if trust in OFFICIAL_TRUST_ROLES:
        value += 25
    elif trust == "discovery_crosscheck":
        value += 10
    if angle in ["Geopolitics explainer","Banking/economy update","Markets/regulation update","Politics explainer"]:
        value += 25
    if angle in ["Science/space update","Science/health update","Economy/resources explainer","International relations update"]:
        value += 20
    if "Breaking incident explainer" in angle:
        value += 10
    if contains_any(content, INDIA_CONTENT_TERMS):
        value += 20
    if contains_any(combined, ["reuters","apnews","bbc","thehindu","rbi.org.in","sebi.gov.in","isro.gov.in","pib.gov.in","dw.com","france24","business standard"]):
        value += 15
    if contains_any(combined, ["quote of the day","horoscope","zodiac","where to watch","stream","box office","celebrity","recipe","fashion","viral video","meme"]):
        value -= 40
    if contains_any(combined, ["cricket","football","hockey","world cup","tennis","ipl","match"]):
        value -= 30
    if len(title.split()) < 7:
        value -= 20
    if len(title) > 250:
        value -= 10
    if "monetary penalty" in combined:
        value -= 35
    if is_pib_item(item):
        label = pib_priority_label(item)
        pib_score = pib_score_value(item)
        if label == "strong":
            value += 35
        elif label == "usable":
            value += 18
        else:
            value -= 35
        value += max(-15, min(25, round((pib_score - 55) / 2)))
    return value


def signature(item):
    title = item.get("title", "").lower()
    angle = item.get("content_angle", "").lower()
    if "iran" in title or "israel" in title or "strait of hormuz" in title:
        return "iran_geopolitics"
    if "inflation" in title or "gdp" in title or "growth outlook" in title:
        return "macro_economy"
    if "election" in title or "chief minister" in title or "mamata" in title:
        return "election_politics"
    if "banking" in angle:
        return "banking_economy"
    if "markets" in angle or "regulation" in angle:
        return "markets_regulation"
    if "science" in angle or "space" in angle:
        return "science_space"
    return f"{item.get('source','')}:{angle}"


def diversify(items, limit=15):
    selected, sig_counts, source_counts = [], {}, {}
    # Prefer publishable + official/manual
    items = sorted(items, key=lambda x: (x.get("is_publishable_source", False), x.get("trust_role") in OFFICIAL_TRUST_ROLES, pib_priority_rank(x) if is_pib_item(x) else 1, x.get("score", 0)), reverse=True)
    for item in items:
        sig = signature(item)
        src = item.get("source", "Unknown")
        if sig_counts.get(sig, 0) >= 2 or source_counts.get(src, 0) >= 5:
            continue
        selected.append(item)
        sig_counts[sig] = sig_counts.get(sig, 0) + 1
        source_counts[src] = source_counts.get(src, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def hook(item):
    angle = item.get("content_angle", "")
    return {
        "Banking/economy update": "A major RBI/economy update just dropped. Here’s the simple version.",
        "Markets/regulation update": "SEBI changed something important. Here’s what it means.",
        "Geopolitics explainer": "This global development could matter more than it looks.",
        "Politics explainer": "A political shift just happened. Here’s the clean breakdown.",
        "Science/space update": "A new science/space update is worth your attention.",
        "Science/health update": "This health/science update needs a simple explanation.",
        "Breaking incident explainer": "Here’s what happened — without the noise.",
    }.get(angle, f"Here’s the simple version: {normalize(item.get('title',''))[:90]}...")


DESIGN_ROUTES = [
    {
        "id": "obsidian_terminal",
        "name": "Obsidian Terminal Briefing",
        "summary": "dark matte terminal-news aesthetic with structured data panels, mono micro-labels, restrained orange state chips, and calm high-trust system UI",
        "typography": "serif-like high-contrast display headline paired with clean sans-serif body and monospaced metadata labels",
        "layout": "layered console panels, left/right information split, strong modular cards, compact interface framing",
        "surface": "16px rounded panels, hairline borders, no heavy shadows, matte dark surfaces, sparse luminous accents",
        "composition": "headline panel first, then stacked supporting modules with clear reading rhythm",
    },
    {
        "id": "editorial_swiss",
        "name": "Editorial Swiss Grid",
        "summary": "type-first editorial system with sharp hierarchy, rational grid alignment, restrained ornament, and high-contrast information blocks",
        "typography": "oversized bold sans-serif headlines, compact supporting text, disciplined spacing, and crisp labels",
        "layout": "asymmetric modular grid, strong margins, zero-to-low radius cards, bold section dividers, print-like clarity",
        "surface": "flat surfaces, minimal effects, border-led separation, bold negative space",
        "composition": "large headline anchor supported by neatly chunked fact modules and disciplined alignment",
    },
    {
        "id": "museum_label",
        "name": "Museum Label Editorial",
        "summary": "premium editorial briefing style with small annotation labels, instrument-panel precision, soft hierarchy, and carefully spaced cards",
        "typography": "elegant display headline with refined body copy and tiny museum-label microtext",
        "layout": "centered content wells, label-like callouts, refined card rhythm, balanced visual restraint",
        "surface": "thin borders, subtle panel contrast, neat chips, airy spacing, no loud decoration",
        "composition": "one hero artifact per slide with surrounding notes and supporting info tags",
    },
    {
        "id": "gallery_product",
        "name": "Gallery Product Briefing",
        "summary": "premium product-page language adapted for news: large clean titles, calm cards, precise spacing, and surface-led depth",
        "typography": "large modern display headlines with understated body copy and clean UI labels",
        "layout": "hero visual centered, stacked information cards, generous whitespace, restrained CTA-like emphasis",
        "surface": "large-radius cards, no shadow dependency, elevation through lighter/darker surfaces only",
        "composition": "single clean visual anchor per slide, surrounded by concise supporting panels",
    },
    {
        "id": "kinetic_portfolio",
        "name": "Kinetic Portfolio News",
        "summary": "bold oversized type, interrupted layouts, tilted info cards, annotation-style microcopy, and more energetic composition while staying brand-safe",
        "typography": "very large condensed headlines paired with compact uppercase metadata and annotation notes",
        "layout": "oversized type as background structure, floating cards, offset elements, interactive-looking composition",
        "surface": "minimal surfaces with one standout card, sparse decorative marks, controlled energy",
        "composition": "hero type dominates, key supporting card cuts across the layout, smaller annotation cues guide the eye",
    },
    {
        "id": "manifesto_monochrome",
        "name": "Manifesto Monochrome",
        "summary": "intellectual manifesto layout with rigorous black/navy surfaces, stark type, hard dividers, and print-like authority",
        "typography": "large authoritative serif or neutral headlines with utilitarian body text",
        "layout": "full-width sections, strict dividers, bold text blocks, spare image use, highly structured editorial rhythm",
        "surface": "flat monochrome planes with orange only as a strategic accent, nearly zero ornament",
        "composition": "statement-led cover, document-like content sections, hard transitions between information groups",
    },
    {
        "id": "institutional_dashboard",
        "name": "Institutional Dashboard",
        "summary": "credible institutional dashboard language with charts, status chips, review panels, and policy-card clarity",
        "typography": "clear UI-first hierarchy with bold dashboard headlines and concise analytical labels",
        "layout": "metrics-first grid, compact cards, panel clusters, process diagrams, and structured information density",
        "surface": "clean dashboard cards, subtle grid texture, modular panels, status-strip accents",
        "composition": "topline signal first, then categorized supporting modules and tracked status elements",
    },
    {
        "id": "atmospheric_gradient",
        "name": "Atmospheric Gradient Briefing",
        "summary": "dark atmospheric gradient environment with floating translucent panels, abstract depth, and premium cinematic restraint",
        "typography": "clean modern sans headlines with softly stacked supporting text and sharp labels",
        "layout": "full-bleed atmospheric background with contained information cards and one central visual metaphor",
        "surface": "glassy overlays, soft luminous gradients, minimal borders, spacious composition",
        "composition": "single atmospheric anchor with a few floating data panels and quiet directional lines",
    },
]


def pick_design_route(item):
    seed_base = f"{normalize(item.get('title',''))}|{normalize(item.get('source',''))}|{normalize(item.get('category',''))}|{datetime.now(IST).strftime('%Y-%m-%d-%H-%M')}"
    seed = int(hashlib.sha256(seed_base.encode('utf-8')).hexdigest()[:12], 16)
    rng = Random(seed)
    route = rng.choice(DESIGN_ROUTES)
    return dict(route)


def route_prompt_block(item):
    route = item.get('design_route') or pick_design_route(item)
    return f"""- Creative route metadata: {route['name']}
- Route summary: {route['summary']}
- Typography language: {route['typography']}
- Layout language: {route['layout']}
- Surface language: {route['surface']}
- Composition behavior: {route['composition']}
- Freshness rule: Do not fall back to the same generic UnblurBrief layout. Use this selected route to make the carousel feel visually fresh while still staying within the UnblurBrief brand system.
- Brand guardrails: keep the UnblurBrief visual identity intact — dark navy/black foundation, white typography, muted orange accents, subtle pixel/document/cursor motif, high-trust news aesthetic.
- Slide distinctness rule: every slide should have a different visual role and should not recycle the same hero device, panel structure, or anchor graphic."""


BRAND_CONSTANTS = {
    "palette": "flexible high-impact editorial palette; do not default to dark navy/black. Use bold, colorful, image-led palettes when appropriate while preserving small UnblurBrief orange/UB identity accents.",
    "tone": "high-trust, concise, exam-aware, non-clickbait editorial tone",
    "motifs": "pixel-grid texture and document/cursor motif used only as subtle micro-texture or small UI detail, not as the main visual identity or hero image",
    "footer": "consistent but compact footer/handle/logo zone for @unblurbrief and UB mark; footer must not dominate the layout",
    "identity": "premium modern news-brief identity with vivid editorial impact, clear hierarchy, symbolic image-led storytelling, and strong mobile readability",
}

LAYOUT_FAMILIES = [
    "Swiss editorial grid",
    "terminal dashboard system",
    "museum-label exhibit",
    "gallery product brief",
    "kinetic poster layout",
    "manifesto statement board",
    "institutional dashboard",
    "atmospheric floating-panel layout",
    "data-sheet revision board",
    "timeline-led explainer",
]

HERO_METAPHORS = [
    "policy memo",
    "map or route system",
    "review gate or checkpoint",
    "comparison panel",
    "timeline strip",
    "signal board",
    "flowchart or pathway",
    "artifact card",
    "status matrix",
    "checklist or revision board",
]

SLIDE_FLOW_PATTERNS = [
    "Poster cover -> source context -> core issue breakdown -> why it matters -> revision takeaway",
    "Hero object -> institution context -> risk or mechanism cards -> process or framework -> exam-summary lockup",
    "Type-led opener -> background grid -> update card -> impact system -> remember-this board",
    "Statement poster -> explainer context -> action panel -> effects map -> final checklist",
    "Anchor visual -> document or source panel -> structured evidence block -> implication pathway -> conclusion card",
]

FORBIDDEN_LAYOUT_PATTERNS = [
    "large pixel document icon at the top as the default hero",
    "the same giant lower-left headline lockup on every cover",
    "identical rounded-card stacks reused across all slides",
    "the same footer-heavy composition dominating every post",
    "recycling the same dashboard/gauge/building template regardless of topic",
    "using the pixel cursor or document motif as the main hero by default",
    "default dark dashboard/terminal look unless the selected color mood explicitly asks for dark",
    "tiny text-heavy infographic panels that look like a report instead of an eye-catching Instagram carousel",
]

COLOR_MOODS = [
    {
        "id": "electric_editorial",
        "name": "Electric Editorial",
        "palette": "electric cobalt, warm orange, off-white, charcoal, and small cyan highlights",
        "background": "bright editorial gradient or split-color backdrop, not plain dark navy",
        "energy": "bold, punchy, premium, highly scroll-stopping",
    },
    {
        "id": "light_institutional",
        "name": "Light Institutional Pop",
        "palette": "warm off-white, ink navy, orange, sky blue, and soft gray",
        "background": "clean light editorial canvas with bold colored blocks and image-led hero",
        "energy": "credible but fresh, Apple/ElevenLabs-like clarity with more color",
    },
    {
        "id": "gradient_spectrum",
        "name": "Gradient Spectrum Brief",
        "palette": "violet, cobalt, cyan, orange, and near-white text",
        "background": "large expressive gradient fields with floating symbolic objects",
        "energy": "modern tech/news, atmospheric, premium, vibrant",
    },
    {
        "id": "poster_pop",
        "name": "Poster Pop Explainer",
        "palette": "cream, black, hot orange, royal blue, and one unexpected accent color",
        "background": "bold poster-like color fields with oversized hero illustration",
        "energy": "magazine-cover energy, simple, loud, memorable",
    },
    {
        "id": "data_colorburst",
        "name": "Data Colorburst",
        "palette": "deep blue, teal, lime/cyan highlights, orange warning chips, white",
        "background": "high-contrast colored dashboard environment, but vivid and image-led",
        "energy": "analytical but alive, more visual than text-heavy",
    },
]

IMAGE_LED_STYLES = [
    "large central 3D symbolic editorial object",
    "bold vector/editorial illustration with dimensional shadows",
    "collage-style cutout object with colored paper layers",
    "isometric scene with one oversized metaphor",
    "cinematic symbolic object on vibrant gradient field",
    "magazine-cover object + minimal annotation labels",
]


def choose_variable_layout_system(item):
    route = item.get('design_route') or pick_design_route(item)
    rid = route.get('id', '')
    route_map = {
        'obsidian_terminal': ['terminal dashboard system','institutional dashboard','data-sheet revision board'],
        'editorial_swiss': ['Swiss editorial grid','timeline-led explainer','manifesto statement board'],
        'museum_label': ['museum-label exhibit','gallery product brief','Swiss editorial grid'],
        'gallery_product': ['gallery product brief','museum-label exhibit','atmospheric floating-panel layout'],
        'kinetic_portfolio': ['kinetic poster layout','manifesto statement board','Swiss editorial grid'],
        'manifesto_monochrome': ['manifesto statement board','Swiss editorial grid','timeline-led explainer'],
        'institutional_dashboard': ['institutional dashboard','terminal dashboard system','data-sheet revision board'],
        'atmospheric_gradient': ['atmospheric floating-panel layout','gallery product brief','timeline-led explainer'],
    }
    choices = route_map.get(rid, LAYOUT_FAMILIES)
    seed_base = f"layout|{normalize(item.get('title',''))}|{normalize(item.get('source',''))}|{normalize(item.get('category',''))}|{datetime.now(IST).strftime('%Y-%m-%d-%H-%M')}"
    seed = int(hashlib.sha256(seed_base.encode('utf-8')).hexdigest()[:12], 16)
    rng = Random(seed)
    return rng.choice(choices)


def choose_hero_metaphor(item):
    title = normalize(item.get('title', '')).lower()
    angle = normalize(item.get('content_angle', '')).lower()
    topic_map = []
    if 'geopolitics' in angle or any(w in title for w in ['war','iran','israel','uae','ceasefire','summit','diplomat']):
        topic_map = ['map or route system','timeline strip','signal board','flowchart or pathway']
    elif 'banking' in angle or any(w in title for w in ['rbi','inflation','economy','bank','market','sebi']):
        topic_map = ['comparison panel','status matrix','policy memo','signal board']
    elif any(w in title for w in ['ai','technology','model','science','space']):
        topic_map = ['review gate or checkpoint','flowchart or pathway','artifact card','status matrix']
    elif any(w in title for w in ['election','government','minister','president','parliament']):
        topic_map = ['signal board','comparison panel','policy memo','timeline strip']
    else:
        topic_map = HERO_METAPHORS
    seed_base = f"hero|{normalize(item.get('title',''))}|{normalize(item.get('source',''))}|{datetime.now(IST).strftime('%Y-%m-%d-%H-%M')}"
    seed = int(hashlib.sha256(seed_base.encode('utf-8')).hexdigest()[:12], 16)
    rng = Random(seed)
    return rng.choice(topic_map)


def choose_slide_flow_pattern(item):
    seed_base = f"flow|{normalize(item.get('title',''))}|{normalize(item.get('source',''))}|{datetime.now(IST).strftime('%Y-%m-%d-%H-%M')}"
    seed = int(hashlib.sha256(seed_base.encode('utf-8')).hexdigest()[:12], 16)
    rng = Random(seed)
    return rng.choice(SLIDE_FLOW_PATTERNS)


def choose_color_mood(item):
    seed_base = f"color|{normalize(item.get('title',''))}|{normalize(item.get('source',''))}|{normalize(item.get('category',''))}|{datetime.now(IST).strftime('%Y-%m-%d-%H-%M')}"
    seed = int(hashlib.sha256(seed_base.encode('utf-8')).hexdigest()[:12], 16)
    rng = Random(seed)
    return dict(rng.choice(COLOR_MOODS))


def choose_image_led_style(item):
    seed_base = f"image-led|{normalize(item.get('title',''))}|{normalize(item.get('source',''))}|{datetime.now(IST).strftime('%Y-%m-%d-%H-%M')}"
    seed = int(hashlib.sha256(seed_base.encode('utf-8')).hexdigest()[:12], 16)
    rng = Random(seed)
    return rng.choice(IMAGE_LED_STYLES)


def color_and_image_prompt_block(item):
    mood = item.get('color_mood') or choose_color_mood(item)
    image_style = item.get('image_led_style') or choose_image_led_style(item)
    return f"""- Color mood: {mood['name']}
- Palette direction: {mood['palette']}
- Background behavior: {mood['background']}
- Energy level: {mood['energy']}
- Image-led style: {image_style}
- Main creative rule: this must be image-led first and text-led second. Use a strong symbolic hero image or illustrated metaphor as the visual center of gravity.
- Color rule: do not default to a mostly dark navy/black interface. Use bright editorial color, gradient, light canvas, vivid blocks, or cinematic color fields based on the selected color mood.
- Readability rule: colorful does not mean cluttered; keep short copy readable with strong contrast and clear type hierarchy.
- Brand rule: keep UB/@unblurbrief present, but make the post feel like a vivid editorial cover, not a dark UI dashboard."""


def brand_constants_prompt_block(item):
    return f"""- Fixed brand constants: preserve only the real UnblurBrief DNA:
  - Palette behavior: {BRAND_CONSTANTS['palette']}
  - Tone: {BRAND_CONSTANTS['tone']}
  - Accent motifs: {BRAND_CONSTANTS['motifs']}
  - Footer system: {BRAND_CONSTANTS['footer']}
  - Identity: {BRAND_CONSTANTS['identity']}
- Important rule: UnblurBrief brand consistency does NOT require a dark theme. Treat brand as a publication identity, not a fixed dark template."""


def variable_layout_engine_prompt_block(item):
    layout_family = item.get('layout_family') or choose_variable_layout_system(item)
    hero_metaphor = item.get('hero_metaphor') or choose_hero_metaphor(item)
    slide_flow = item.get('slide_flow_pattern') or choose_slide_flow_pattern(item)
    forbidden = '; '.join(FORBIDDEN_LAYOUT_PATTERNS)
    return f"""- Variable layout engine: choose and obey these variable composition settings for this post.
- Selected layout family: {layout_family}
- Selected hero metaphor: {hero_metaphor}
- Selected slide-flow pattern: {slide_flow}
- Layout variation rule: the layout family, hero metaphor, and slide flow are the main drivers of visual differentiation and must materially change the composition.
- Motif control rule: pixel/document/cursor motifs may appear only as minor secondary brand cues unless the selected hero metaphor explicitly requires one of them.
- Repetition ban: do NOT use these repeated layout patterns: {forbidden}.
- Composition rule: vary headline placement, spatial rhythm, card geometry, scale contrast, and panel organization based on the selected layout family.
- Hero rule: build the cover and each slide around the selected hero metaphor rather than defaulting to a document card."""


CREATIVE_OS_STYLE_REFERENCES = {
    "obsidian_terminal": "Resend-like obsidian developer-terminal restraint: dark matte surfaces, code/UI precision, hairline borders, structured information panels.",
    "editorial_swiss": "Sociotype and Locomotive-inspired editorial Swiss rigor: type-first hierarchy, strong grid discipline, objective clarity, minimal ornament.",
    "museum_label": "ElevenLabs-inspired museum-label editorial softness: refined labels, calm cards, near-achromatic premium restraint, instrument-panel precision.",
    "gallery_product": "Apple-like gallery product presentation: large clean hero moments, restrained cards, surface-led depth, premium product-page calm.",
    "kinetic_portfolio": "Kai Fox-inspired kinetic portfolio energy: oversized type, interrupted layouts, floating info cards, annotation-style microcopy.",
    "manifesto_monochrome": "Locomotive manifesto-style monochrome authority: stark type, section dividers, intellectual editorial rhythm, sparse high-trust visuals.",
    "institutional_dashboard": "Clean institutional dashboard language: analytic panels, tracked status chips, modular cards, policy/report clarity.",
    "atmospheric_gradient": "Monopo-style atmospheric gradient depth: dark immersive atmosphere, floating translucent panels, abstract depth, restrained futurism.",
}


def design_principles_prompt_block(item):
    route = item.get('design_route') or pick_design_route(item)
    ref = CREATIVE_OS_STYLE_REFERENCES.get(route.get('id', ''), '')
    return f"""- Creative OS style grounding: {ref}
- Human-centered clarity (Don Norman): make every slide self-explanatory, with obvious visual signifiers, clear conceptual grouping, and easy scan paths.
- Universal Principles of Design: apply hierarchy, chunking, alignment, consistency, figure-ground separation, accessibility, and strong signal-to-noise ratio.
- Laws of Simplicity (John Maeda): reduce the non-essential, organize complexity, keep the message fast to grasp, and subtract the obvious while adding the meaningful.
- Don't Make Me Think (Steve Krug): make the main point immediately obvious, remove needless words, and ensure readers can understand each slide at a glance.
- About Face / interaction thinking (Alan Cooper): prioritize the user's goal of quickly understanding the story; reduce excise, keep content progression intentional, and make each slide feel purposeful.
- Hooked, used ethically (Nir Eyal): use a strong but trustworthy hook, a low-friction slide sequence, and rewarding clarity rather than manipulative sensationalism.
- Thinking with Type + Bringhurst: use disciplined typography with strong hierarchy, readable rhythm, appropriate contrast, compact mobile-friendly measure, and elegant spacing.
- Grid Systems (Müller-Brockmann): use a rational modular grid, disciplined alignment, repeatable structure, and intentional asymmetry where useful.
- Brand identity discipline (Wheeler / Airey): keep the UnblurBrief identity coherent, distinctive, and consistent without redesigning the brand each time.
- Creative-process rule (Kleon): remix references thoughtfully; transform and combine influences, do not copy one source literally.
- Execution rule: visual novelty must never reduce readability, credibility, or exam usefulness.
- Mobile-first rule: prioritize scroll-stopping hierarchy first, then readable body copy, then supporting detail.
- Slide-system rule: Slide 1 should hook, Slides 2–4 should progressively clarify, and Slide 5 should resolve with a crisp takeaway.
- Freshness rule: rotate layout systems, composition logic, and typographic emphasis so the feed feels varied, but preserve brand familiarity.
"""



def design_route_variation_spec(item):
    route = item.get('design_route') or pick_design_route(item)
    rid = route.get('id', '')
    specs = {
        "obsidian_terminal": {
            "layout": "Use asymmetric terminal panels, command-line metadata strips, compact diagnostic widgets, and thin technical dividers. Avoid one large centered icon above a headline.",
            "hero": "Hero metaphor should be a system console, audit pipeline, risk matrix, protocol stack, or verification workflow — not a generic document icon.",
            "slides": "Slide 1 = command dashboard; Slide 2 = source/institution panel; Slide 3 = risk matrix; Slide 4 = release pathway; Slide 5 = terminal-style final status card.",
        },
        "editorial_swiss": {
            "layout": "Use a strict Swiss grid, hard alignment, large typographic blocks, numbered sections, and disciplined whitespace. Avoid glowing app-card layouts.",
            "hero": "Hero metaphor should be oversized typography, a grid-led fact board, or a structured editorial index.",
            "slides": "Slide 1 = type-led cover; Slide 2 = two-column institution grid; Slide 3 = three-column checklist; Slide 4 = cause-effect framework; Slide 5 = clean revision index.",
        },
        "museum_label": {
            "layout": "Use artifact-like centerpieces with small label cards, museum caption strips, and refined annotation callouts. Avoid dashboard-heavy repetition.",
            "hero": "Hero metaphor should be a curated artifact: policy file, model capsule, standards plaque, treaty card, evidence tag, or institutional exhibit.",
            "slides": "Slide 1 = exhibit label cover; Slide 2 = institution placard; Slide 3 = annotated risk specimen; Slide 4 = process exhibit; Slide 5 = takeaway label card.",
        },
        "gallery_product": {
            "layout": "Use product-page style hero staging, clean large surfaces, generous spacing, and one premium object per slide. Avoid dense panel clusters.",
            "hero": "Hero metaphor should be a single polished object: sealed AI box, policy device, data slab, institutional card, or release gate.",
            "slides": "Slide 1 = hero object; Slide 2 = clean institution card; Slide 3 = three elegant object tiles; Slide 4 = release-gate product diagram; Slide 5 = comparison card.",
        },
        "kinetic_portfolio": {
            "layout": "Use oversized type-as-background, tilted cards, offset blocks, annotation arrows, and editorial motion energy. Avoid symmetrical icon-on-top templates.",
            "hero": "Hero metaphor should interrupt the typography: floating review stamp, tilted evidence card, marked route line, or punchy annotated object.",
            "slides": "Slide 1 = giant typography with tilted anchor card; Slide 2 = split institution/persona card; Slide 3 = annotated checklist; Slide 4 = route/pathway graphic; Slide 5 = bold conclusion poster.",
        },
        "manifesto_monochrome": {
            "layout": "Use stark manifesto blocks, hard dividers, sparse symbols, and statement-led hierarchy. Avoid decorative tech icons everywhere.",
            "hero": "Hero metaphor should be a bold statement panel, institutional memo, public notice, or black-white-orange rule card.",
            "slides": "Slide 1 = statement poster; Slide 2 = austere authority block; Slide 3 = rule list; Slide 4 = consequence map; Slide 5 = closing manifesto card.",
        },
        "institutional_dashboard": {
            "layout": "Use dashboard logic, but vary cards by slide: matrix, flowchart, status board, comparison panel, timeline. Avoid using the same document card repeatedly.",
            "hero": "Hero metaphor should be a review queue, risk triage board, compliance matrix, or policy-control room.",
            "slides": "Slide 1 = review queue; Slide 2 = institution dashboard; Slide 3 = risk triage matrix; Slide 4 = release checkpoint flow; Slide 5 = final status/timeline.",
        },
        "atmospheric_gradient": {
            "layout": "Use cinematic dark depth, floating translucent panels, abstract orbit/path lines, and one calm focal object. Avoid flat repeated card stacks.",
            "hero": "Hero metaphor should be a floating review gate, glowing model core, abstract map cloud, or suspended evidence frame.",
            "slides": "Slide 1 = atmospheric hero object; Slide 2 = floating context panels; Slide 3 = separated risk or issue orbs; Slide 4 = pathway through depth; Slide 5 = calm final lockup.",
        },
    }
    s = specs.get(rid, specs["institutional_dashboard"])
    return f"""- Route-specific layout construction: {s['layout']}
- Route-specific hero metaphor: {s['hero']}
- Route-specific slide progression: {s['slides']}
- Hard anti-template rule: do NOT use the default repeated template of a large pixel document icon at the top, huge lower-left headline, identical dark rounded cards, and the same footer lockup on every slide.
- Visual novelty requirement: vary scale, composition, hero object, panel structure, and spatial rhythm from slide to slide.
- One-anchor rule: each slide needs exactly one primary visual anchor; supporting elements must not overpower or repeat the previous slide.
- Brand continuity rule: keep @unblurbrief and the UB/logo area consistent, but vary the rest of the composition aggressively within the selected route."""

def topical_visual_base(item):
    title = item.get("title", "").lower()
    angle = item.get("content_angle", "").lower()
    category = item.get("category", "").lower()
    if "banking" in angle or "rbi" in title or "inflation" in title or "growth" in title:
        return "Institution-card layout with RBI/economy dashboard elements"
    if "markets" in angle or "sebi" in title or "investor" in title:
        return "Regulatory briefing layout with document, shield, and investor-protection motifs"
    if "geopolitics" in angle or "war" in title or "iran" in title or "israel" in title:
        return "Map-card explainer with abstract regional map lines, diplomatic markers, and alert chips"
    if angle == "politics explainer" or "election" in title:
        return "Election explainer layout with ballot-card, state-map silhouette, and result-board motifs"
    if "science" in angle or "space" in angle or "technology" in category:
        return "Science briefing layout with satellite/data-grid/circuit motifs"
    if "breaking incident" in angle or any(w in title for w in ["fire","crash","explosion","attack","injured","killed"]):
        return "Safety briefing layout with non-graphic alert icons, timeline cards, and verified-facts panels"
    return "Premium news terminal layout with document cards, pixel grid, and data chips"


def visual_style(item):
    route = item.get("design_route") or pick_design_route(item)
    base = topical_visual_base(item)
    layout_family = item.get("layout_family") or choose_variable_layout_system(item)
    hero_metaphor = item.get("hero_metaphor") or choose_hero_metaphor(item)
    slide_flow = item.get("slide_flow_pattern") or choose_slide_flow_pattern(item)
    color_mood = item.get("color_mood") or choose_color_mood(item)
    image_style = item.get("image_led_style") or choose_image_led_style(item)
    return f"{base}, but make it colorful and image-led. Express it through the {route['name']} route, the {layout_family} composition family, the hero metaphor '{hero_metaphor}', and the color mood {color_mood['name']} ({color_mood['palette']}). Use {image_style} as the dominant visual language. Follow this slide-flow tendency: {slide_flow}. Preserve brand identity without defaulting to a dark dashboard template." 


def visual_elements(item):
    title = item.get("title", "").lower()
    angle = item.get("content_angle", "").lower()
    elements = []
    if "geopolitics" in angle or "iran" in title or "israel" in title or "uae" in title or "fujairah" in title:
        elements += ["abstract regional map","diplomatic route lines","neutral location pins","timeline chips","oil/shipping route icon","verified facts panel"]
    elif angle == "politics explainer" or "election" in title:
        elements += ["ballot box icon","state map silhouette when relevant","vote-count board","neutral podium icon"]
    if "rbi" in title or "inflation" in title or "bank" in title:
        elements += ["RBI-style institutional building silhouette","rupee symbol","inflation gauge","policy document card"]
    if "sebi" in title or "investor" in title or "market" in angle:
        elements += ["SEBI-style regulatory document card","stock chart line","investor shield icon","claim form/document stack"]
    if not elements:
        elements += ["news document card","source-link chip","timeline panel","abstract data grid"]
    out = []
    for e in elements:
        if e not in out:
            out.append(e)
    return ", ".join(out[:7])


def safety(item):
    title = item.get("title", "").lower()
    angle = item.get("content_angle", "").lower()
    if any(k in title or k in angle for k in ["war","strike","missile","killed","injured","death","dead","crash","fire","explosion","attack","shooting","bombing","suicide","violence"]):
        return "Use safe, non-graphic symbolic visuals only. Do not show blood, dead bodies, injuries, weapons firing, explosions in progress, distressed victims, identifiable real people, or photorealistic disaster scenes. Prefer abstract maps, alert icons, document cards, timelines, neutral silhouettes, and verified-facts panels."
    return "Use editorial-safe symbolic visuals. Avoid using real logos unless supplied by the user. Avoid photorealistic depictions of real people. Use icons, silhouettes, maps, data cards, documents, and abstract newsroom elements."


def research_context(item, research_by_url):
    url = item.get("url", "")
    research = research_by_url.get(url, {})
    rss_summary = normalize(item.get("summary", ""))
    rss_published = normalize(item.get("published", ""))
    if not research:
        lines = ["Research extraction status: not_run", "Warning: Article extraction has not been run yet."]
        if rss_summary:
            lines += ["RSS summary available:", rss_summary]
        if rss_published:
            lines.append(f"RSS published/updated: {rss_published}")
        lines.append("Use only the source item and RSS summary. Write “source check required” for details not confirmed.")
        return "\n".join(lines)
    lines = [
        f"Research extraction status: {research.get('status','unknown')}",
        f"Extraction method: {research.get('method','unknown')}",
        f"Fetch method: {research.get('fetch_method','unknown')}",
        f"Resolved URL: {research.get('resolved_url',url)}",
    ]
    if research.get("published_date"):
        lines.append(f"Published/updated date from extractor or RSS: {research.get('published_date')}")
    warnings = research.get("warnings", [])
    if warnings:
        lines.append("Extraction warnings:")
        lines += [f"- {w}" for w in warnings[:5]]
    facts = research.get("key_facts", [])
    if facts:
        lines.append("Extracted key facts:")
        lines += [f"- {f}" for f in facts[:10]]
    excerpt = normalize(research.get("excerpt", ""))
    if excerpt:
        lines += ["Extracted article text / context:", excerpt[:3500]]
    if research.get("status") not in {"ok", "partial"}:
        lines.append("Important: Article extraction was incomplete. Use only the extracted text, RSS summary, title, and source URL. Do not invent missing details. Mark uncertain details as “source check required”.")
    if rss_summary and rss_summary not in excerpt:
        lines += ["RSS summary:", rss_summary[:1000]]
    return "\n".join(lines)


def known_metadata(item):
    return f"""- Title: {normalize(item.get('title',''))}
- Source/feed: {normalize(item.get('source',''))}
- Source role: {normalize(item.get('trust_role','discovery_only'))}
- URL: {normalize(item.get('url',''))}
- Feed/category: {normalize(item.get('category',''))}
- Published date if available: {normalize(item.get('published','')) or 'not available'}
- Suggested angle: {normalize(item.get('content_angle',''))}
"""


def createSourceCheckRequiredBrief(item: dict[str, Any], assessment: dict[str, Any], research_by_url: dict[str, Any]) -> str:
    reasons = "\n".join(f"- {r}" for r in assessment.get("reasons", []))
    missing = "\n".join(f"- {m}" for m in assessment.get("missing", []))
    tasks = "\n".join(f"- {t}" for t in assessment.get("verification_tasks", []))
    manual_slug_hint = item.get("title", "manual-article").lower()
    return f"""You are working for UnblurBrief, a high-trust, non-clickbait current-affairs Instagram page.

SOURCE RELIABILITY STATE:
{assessment.get('state')}

STATUS:
Source check required

REASON:
The extraction did not contain enough article-level facts to safely generate a publishable post.

Reliability reasons:
{reasons}

Known metadata:
{known_metadata(item)}

Research context available:
{research_context(item, research_by_url)}

Missing information:
{missing}

Verification tasks:
{tasks}

Manual override option:
Paste the full article text into the matching file in the manual_overrides folder, then run START_HERE.bat again. This can upgrade the source if the pasted article body is strong enough.

Critical content rule:
Never infer election results, vote counts, political outcomes, casualties, crime details, policy changes, financial numbers, or quotes from a headline alone.

Task:
Return ONLY the following SOURCE CHECK REQUIRED MODE output.
Do not create final slide copy.
Do not create a final caption.
Do not create hashtags.
Do not create an image-generation prompt.
Do not write a publishable carousel.

Use exactly these headings:

## STATUS
Source check required

## REASON
Explain that the extraction did not contain enough article-level facts to safely generate a publishable UnblurBrief post.

## KNOWN_METADATA
List only the known metadata from the source item.

## MISSING_INFORMATION
List the missing article-level facts.

## VERIFICATION_TASKS
List the source-check tasks.

## NON_PUBLISHABLE_OUTLINE_ONLY
Create a 5-slide placeholder structure clearly marked DO NOT PUBLISH.
Use placeholders like:
[confirmed fact needed]
[verified number needed]
[quote/source check required]
Do not invent facts.

## NEXT_ACTION
Ask the user to paste the full article text into manual_overrides or retry extraction with a better method."""


def make_publishable_prompt(item, assessment, research_by_url):
    fmt = item.get("post_format", choose_post_format(item))
    vs = item.get("visual_style", visual_style(item))
    ve = item.get("visual_elements", visual_elements(item))
    sn = item.get("image_safety_note", safety(item))
    reliability = f"""Source reliability state: {assessment.get('state')}
Reliability score: {assessment.get('score')}/100
Source role: {assessment.get('trust_role')}
Reliability notes:
{chr(10).join('- ' + r for r in assessment.get('reasons', []))}
"""
    caution_rule = ""
    if assessment.get("state") == "usable_with_caution":
        caution_rule = "- Source is usable with caution. Keep claims conservative and include source-check notes for any unclear details.\n"
    return f"""You are creating a premium Instagram carousel text package for **UnblurBrief**.

Brand:
- UnblurBrief is a clean, sharp, non-clickbait news/current-affairs Instagram page.
- Style: minimal, high-trust, modern, concise, exam-aware.
- Tone: neutral, direct, clear, non-sensational.
- Visual identity: dark navy/black, white text, orange accent, pixel/document/cursor motif.
- Handle: @unblurbrief

Source reliability:
{reliability}

Source item:
- Title: {normalize(item.get('title',''))}
- URL: {normalize(item.get('url',''))}
- Source feed: {normalize(item.get('source',''))}
- Source role: {normalize(item.get('trust_role','discovery_only'))}
- Category: {normalize(item.get('category',''))}
- Priority: {normalize(item.get('priority',''))}
- Content angle: {normalize(item.get('content_angle',''))}
- Suggested hook: {item.get('hook_suggestion', hook(item))}
- Recommended post format: {fmt}

Research context:
{research_context(item, research_by_url)}

Creative direction system:
{route_prompt_block(item)}

Brand constants:
{brand_constants_prompt_block(item)}

Color + image-led direction:
{color_and_image_prompt_block(item)}

Variable layout engine:
{variable_layout_engine_prompt_block(item)}

Route-specific variation rules:
{design_route_variation_spec(item)}

Design principles to apply:
{design_principles_prompt_block(item)}

Task:
Create the finished TEXT package for a 5-slide Instagram carousel. Do not generate images.

Rules:
- Use the extracted article text and RSS summary inside this prompt as the primary source.
- Do not ask to browse the web.
- Do not invent facts beyond the source item and research context.
{caution_rule}- If details require source verification, write “source check required” rather than guessing.
- Do not use political bias.
- Do not sensationalize deaths, war, crime, fire, accidents, or conflict.
- Keep the copy mobile-first.
- Mention @unblurbrief on every slide.
- Make it useful for students and general readers.
- Keep slide copy short enough to fit into designed carousel slides.
- Avoid repeating the same data point across multiple slides.
- Each slide must teach or clarify a different part of the story.
- Make the visual direction feel fresh and creatively distinct rather than repetitive.
- The visual system should rotate across different editorial/layout approaches while remaining brand-consistent.
- Fixed vs variable rule: preserve only brand constants; vary composition aggressively using the selected color mood, image-led style, layout family, hero metaphor, and slide-flow pattern.
- Eye-catching rule: the visual direction must feel colorful, image-led, and scroll-stopping, not like a dark text-heavy dashboard.
- Avoid generic repeated layouts such as: top-center document icon, same giant headline placement, same bottom footer treatment, identical card stack, or same dashboard panels on every post.
- Never infer election results, vote counts, political outcomes, casualties, crime details, policy changes, financial numbers, or quotes from a headline alone.

Use this exact 5-slide carousel structure:
{slide_structure(fmt)}

App-side design metadata for later image prompt building:
- Design style metadata: {vs}
- Design element metadata: {ve}
- Safety metadata: {sn}
- Creative route metadata: {item.get('design_route', {}).get('name', '')}
- Creative route notes metadata: {item.get('design_route', {}).get('summary', '')}

Return the output using EXACTLY these section headings:

## CAROUSEL_TITLE
[title here]

## SLIDE_COPY
### Slide 1
[approved slide 1 copy]

### Slide 2
[approved slide 2 copy]

### Slide 3
[approved slide 3 copy]

### Slide 4
[approved slide 4 copy]

### Slide 5
[approved slide 5 copy]

## CAPTION
[caption here]

## HASHTAGS
[hashtags here]

## VERIFICATION_CHECKLIST
[checklist here]

## IMAGE_GENERATION_PROMPT
Create a premium 5-slide Instagram carousel visual for UnblurBrief using ONLY the approved slide copy above.

Important:
- Do not rewrite, add, summarize, expand, or invent any text.
- Do not add extra facts, dates, names, numbers, labels, or claims.
- Do not repeat the same data point across multiple slides unless it is explicitly present in the approved slide copy.
- Each slide must have a clearly different visual role.
- Do not reuse the same main graphic on more than one slide.
- Do not place the same map, building, gauge, dashboard, alert chip, policy card, number block, quote card, or route graphic on every slide.
- Use one main visual metaphor per slide.
- Do not use a repeated top-icon + headline + bottom-logo template for every post.
- Do not use the pixel document/cursor motif as the main hero on more than one slide; it should be a subtle brand motif, not the repeated central image.
- Separate fixed from variable design decisions: keep only the brand constants stable and vary the layout family, hero metaphor, and slide-flow pattern.
- Keep the UB/logo and @unblurbrief area consistent, but vary the core layout, hero object, typography scale, card geometry, and composition route.

Brand style:
- UnblurBrief must feel premium, clear, high-trust, and news/editorial.
- Do NOT default to a dark navy/black background. Use the selected color mood and image-led direction.
- Use white or dark typography depending on contrast; mobile readability is mandatory.
- Use muted orange as a brand accent, not as the only color.
- Pixel-grid and document/cursor motifs should be subtle micro-textures, not the repeated main hero.
- Keep compact, consistent footer space for @unblurbrief and the official UB/logo area.
- Include the official UnblurBrief/UB logo only if supplied by the user; otherwise reserve a clean logo placeholder area.

Visual style:
{vs}

Creative route system:
{route_prompt_block(item)}

Brand constants to preserve during image generation:
{brand_constants_prompt_block(item)}

Color + image-led direction:
{color_and_image_prompt_block(item)}

Variable layout engine:
{variable_layout_engine_prompt_block(item)}

Route-specific variation rules:
{design_route_variation_spec(item)}

Design principles to preserve during image generation:
{design_principles_prompt_block(item)}

Use relevant elements:
{ve}

Safety:
{sn}

Required slide-by-slide behavior:
- Slide 1: cover / hook, one anchor visual only
- Slide 2: context / institution / background, different layout from Slide 1
- Slide 3: latest update / action / decision, different main graphic
- Slide 4: why it matters / impact / framework, different main graphic
- Slide 5: takeaway / revision / remember-this card, different main graphic

Required final image output format:
- Generate 5 separate square images, one image per slide.
- Each slide must be a full-size 1:1 Instagram carousel image.
- Do not create one combined preview image.
- Do not create a contact sheet, collage, grid, storyboard, mockup, or Canva/editor preview.
- Do not put multiple slides on one canvas.
- Output separate Slide 1, Slide 2, Slide 3, Slide 4, and Slide 5 images.

Output:
Create the finished 5-slide carousel image set with clear visual hierarchy and clear slide-to-slide progression."""


def make_prompt(item, assessment, research_by_url):
    if not isPublishableSource(assessment):
        return createSourceCheckRequiredBrief(item, assessment, research_by_url)
    return make_publishable_prompt(item, assessment, research_by_url)


def main():
    OUTPUT.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    items = load(INPUT, [])
    if not items:
        raise SystemExit("No sources found. Run scrape_sources.py first.")
    research = load(RESEARCH, {})
    used = set(load(USED, {"used_urls": []}).get("used_urls", []))
    scored = []
    processed = []
    for item in items:
        item = dict(item)
        item["title"] = normalize(item.get("title", ""))
        item["trust_role"] = item.get("trust_role", "discovery_only")
        item["score"] = score(item, used)
        item["post_format"] = choose_post_format(item)
        item["hook_suggestion"] = hook(item)
        item["design_route"] = pick_design_route(item)
        item["layout_family"] = choose_variable_layout_system(item)
        item["hero_metaphor"] = choose_hero_metaphor(item)
        item["slide_flow_pattern"] = choose_slide_flow_pattern(item)
        item["color_mood"] = choose_color_mood(item)
        item["image_led_style"] = choose_image_led_style(item)
        item["visual_style"] = visual_style(item)
        item["visual_elements"] = visual_elements(item)
        item["image_safety_note"] = safety(item)
        assessment = assessSourceReliability(item, research)
        item["reliability_state"] = assessment["state"]
        item["reliability_score"] = assessment["score"]
        item["reliability_high_risk"] = assessment["high_risk"]
        item["reliability_reasons"] = assessment["reasons"]
        item["reliability_missing"] = assessment["missing"]
        item["is_publishable_source"] = isPublishableSource(assessment)
        item["content_prompt"] = make_prompt(item, assessment, research)
        item["research_available"] = item.get("url", "") in research
        processed.append(item)
        if item["score"] >= 20:
            scored.append(item)
    top = diversify(scored, 15)
    save_json(top, CANDIDATES)
    update_pib_all_releases(processed, top, research)
    md = ["# UnblurBrief Top Post Candidates", "", f"Generated at: {datetime.now(IST).isoformat(timespec='seconds')}", "", f"Total candidates selected: {len(top)}", ""]
    for i, item in enumerate(top, 1):
        md += [f"# {i}. {item['title']}", "", f"""## Candidate: {item['title']}

**Score:** {item.get('score','')}  
**Source:** {item.get('source','')}  
**Source role:** {item.get('trust_role','')}  
**Category:** {item.get('category','')}  
**Priority:** {item.get('priority','')}  
**Angle:** {item.get('content_angle','')}  
**Recommended format:** {item.get('post_format','')}  
**Design route:** {item.get('design_route',{}).get('name','')}  
**Layout family:** {item.get('layout_family','')}  
**Hero metaphor:** {item.get('hero_metaphor','')}  
**Slide-flow pattern:** {item.get('slide_flow_pattern','')}  
**Color mood:** {item.get('color_mood',{}).get('name','')}  
**Image-led style:** {item.get('image_led_style','')}  
**URL:** {item.get('url','')}  
**Reliability state:** {item.get('reliability_state','')}  
**Reliability score:** {item.get('reliability_score','')}/100  
**Publishable source:** {item.get('is_publishable_source', False)}  
**Reliability reasons:** {'; '.join(item.get('reliability_reasons', []))}  

### CONTENT PROMPT — use in normal ChatGPT

{item.get('content_prompt','')}
---
"""]
    PROMPTS.write_text("\n".join(md), encoding="utf-8")
    print("Done.")
    print(f"Selected top candidate(s): {len(top)}")
    print(f"JSON: {CANDIDATES}")
    print(f"Markdown prompts: {PROMPTS}")
    counts = {}
    for item in top:
        counts[item.get("reliability_state", "unknown")] = counts.get(item.get("reliability_state", "unknown"), 0) + 1
    print(f"Reliability summary: {counts}")


if __name__ == "__main__":
    main()
