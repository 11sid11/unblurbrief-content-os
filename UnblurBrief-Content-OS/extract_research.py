from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup

try:
    from scrapling.fetchers import Fetcher
except Exception:
    Fetcher = None

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
CANDIDATES = OUTPUT / "top_post_candidates.json"
SOURCES = OUTPUT / "unblurbrief_sources.json"
RESEARCH = OUTPUT / "research_cache.json"
OVERRIDES = ROOT / "manual_overrides"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(v) for v in value if v)
    return " ".join(str(value).replace("\n", " ").replace("\t", " ").split()).strip()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", clean(text).lower()).strip("-")[:80] or "manual-article"


def load(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save(data, path: Path):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def facts(text: str):
    sentences = re.split(r"(?<=[.!?])\s+", clean(text))
    out = []
    for s in sentences:
        s = clean(s)
        if 40 <= len(s) <= 300:
            out.append(s)
        if len(out) >= 10:
            break
    return out


def manual_override_path(item: dict[str, Any]) -> Path:
    # Make it discoverable for the user: put files named by source/article slug in manual_overrides.
    title_slug = slug(item.get("title", ""))
    return OVERRIDES / f"{title_slug}.txt"


def get_manual_override(item: dict[str, Any]) -> str:
    OVERRIDES.mkdir(exist_ok=True)
    p = manual_override_path(item)
    if p.exists():
        return clean(p.read_text(encoding="utf-8"))
    return ""


def fetch_html(url: str):
    warnings = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        r.raise_for_status()
        return r.text, r.url, "requests", warnings
    except Exception as exc:
        warnings.append(f"requests failed: {exc}")
    if Fetcher is not None:
        try:
            page = Fetcher.get(url)
            html = str(getattr(page, "text", "") or getattr(page, "html", "") or getattr(page, "body", "") or page)
            return html, url, "scrapling", warnings
        except Exception as exc:
            warnings.append(f"scrapling failed: {exc}")
    return "", url, "none", warnings


def trafilatura_extract(html: str, url: str):
    result = {"method": "trafilatura", "text": "", "title": "", "author": "", "published_date": ""}
    try:
        meta = trafilatura.extract_metadata(html, default_url=url)
        if meta:
            result["title"] = clean(getattr(meta, "title", "") or "")
            result["author"] = clean(getattr(meta, "author", "") or "")
            result["published_date"] = clean(getattr(meta, "date", "") or "")
    except Exception:
        pass
    try:
        result["text"] = clean(trafilatura.extract(html, url=url, include_comments=False, include_tables=False, favor_precision=True, output_format="txt") or "")
    except Exception:
        pass
    return result


def jsonld_extract(soup: BeautifulSoup):
    bodies, title, author, date = [], "", "", ""
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ", strip=True)
        try:
            data = json.loads(raw)
        except Exception:
            continue
        nodes = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            typ = node.get("@type", "")
            typ_text = " ".join(typ).lower() if isinstance(typ, list) else str(typ).lower()
            if not any(x in typ_text for x in ["article", "newsarticle", "blogposting"]):
                continue
            title = title or clean(node.get("headline") or node.get("name") or "")
            date = date or clean(node.get("datePublished") or node.get("dateModified") or "")
            body = clean(node.get("articleBody") or node.get("description") or "")
            if body:
                bodies.append(body)
    return {"method": "json-ld", "text": clean(" ".join(bodies)), "title": title, "author": author, "published_date": date}


def meta_extract(soup: BeautifulSoup):
    parts = []
    title = clean(soup.title.get_text(" ", strip=True)) if soup.title else ""
    for attrs in [{"name": "description"}, {"property": "og:description"}, {"name": "twitter:description"}]:
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            parts.append(clean(tag.get("content")))
    return {"method": "meta", "text": clean(" ".join(parts)), "title": title, "author": "", "published_date": ""}


def paragraph_extract(soup: BeautifulSoup):
    for tag in soup(["script", "style", "noscript", "svg", "form", "nav", "footer", "header", "aside"]):
        tag.decompose()
    article = soup.find("article")
    container = article if article else max(soup.find_all(["main", "section", "div"]), key=lambda t: len(t.get_text(" ", strip=True)), default=soup)
    paras, seen = [], set()
    for p in container.find_all(["p", "li"]):
        text = clean(p.get_text(" ", strip=True))
        key = text[:120].lower()
        if len(text.split()) >= 8 and key not in seen:
            seen.add(key)
            paras.append(text)
    title = clean(soup.title.get_text(" ", strip=True)) if soup.title else ""
    return {"method": "paragraphs", "text": "\n".join(paras[:24]), "title": title, "author": "", "published_date": ""}


def best(extractions, rss_summary: str):
    valid = [(len(e.get("text", "").split()), e) for e in extractions if clean(e.get("text", ""))]
    if valid:
        valid.sort(key=lambda x: x[0], reverse=True)
        return valid[0][1]
    if rss_summary:
        return {"method": "rss-summary", "text": rss_summary, "title": "", "author": "", "published_date": ""}
    return {"method": "none", "text": "", "title": "", "author": "", "published_date": ""}


def fetch_article(item: dict[str, Any], rss_summary: str = "", rss_published: str = ""):
    url = item.get("url", "")
    manual_text = get_manual_override(item)
    api_body_text = clean(item.get("api_body_text", ""))
    if api_body_text and len(api_body_text.split()) >= 80:
        return {
            "status": "ok",
            "method": "publisher-api-body",
            "fetch_method": "api_payload",
            "original_url": item.get("url", ""),
            "resolved_url": item.get("url", ""),
            "domain": urlparse(item.get("url", "")).netloc,
            "title": item.get("title", ""),
            "author": "",
            "published_date": item.get("published", ""),
            "excerpt": api_body_text[:4500],
            "key_facts": facts(api_body_text),
            "warnings": ["Publisher API article body was used."],
        }

    existing_article_text = clean(item.get("article_text", ""))
    if existing_article_text and len(existing_article_text.split()) >= 80:
        return {
            "status": "ok",
            "method": "existing-item-article-text",
            "fetch_method": "local_item_payload",
            "original_url": item.get("url", ""),
            "resolved_url": item.get("url", ""),
            "domain": urlparse(item.get("url", "")).netloc,
            "title": item.get("title", ""),
            "author": "",
            "published_date": item.get("published", ""),
            "excerpt": existing_article_text[:4500],
            "key_facts": facts(existing_article_text),
            "warnings": ["Existing article_text stored on the selected item was used."],
        }

    if manual_text:
        return {
            "status": "ok",
            "method": "manual-article-text",
            "fetch_method": "manual_override",
            "original_url": url,
            "resolved_url": url,
            "domain": urlparse(url).netloc,
            "title": item.get("title", ""),
            "author": "",
            "published_date": rss_published,
            "excerpt": manual_text[:4500],
            "key_facts": facts(manual_text),
            "warnings": ["Manual article text override was used."],
            "manual_override_file": str(manual_override_path(item)),
        }

    html, resolved, fetch_method, warnings = fetch_html(url)
    if not html:
        text = clean(rss_summary)
        return {"status": "summary_only" if text else "failed", "method": "rss-summary" if text else "none", "fetch_method": fetch_method, "original_url": url, "resolved_url": resolved, "domain": urlparse(resolved).netloc, "title": "", "author": "", "published_date": rss_published, "excerpt": text[:3500], "key_facts": facts(text), "warnings": warnings}
    soup = BeautifulSoup(html, "lxml")
    extractions = [trafilatura_extract(html, resolved), jsonld_extract(soup), meta_extract(soup), paragraph_extract(soup)]
    picked = best(extractions, rss_summary)
    text = clean(picked.get("text", ""))
    word_count = len(text.split())
    status = "ok" if word_count >= 80 else "partial" if word_count >= 20 else "summary_only" if text else "empty"
    if status != "ok":
        warnings.append("Extraction is incomplete; source check recommended.")
    return {
        "status": status, "method": picked.get("method", "unknown"), "fetch_method": fetch_method,
        "original_url": url, "resolved_url": resolved, "domain": urlparse(resolved).netloc,
        "title": clean(picked.get("title", "")), "author": clean(picked.get("author", "")),
        "published_date": clean(picked.get("published_date", "")) or rss_published,
        "excerpt": text[:3500], "key_facts": facts(text), "warnings": warnings,
    }


def main() -> int:
    OUTPUT.mkdir(exist_ok=True)
    OVERRIDES.mkdir(exist_ok=True)
    candidates = load(CANDIDATES, [])
    sources = load(SOURCES, [])
    cache = load(RESEARCH, {})
    source_by_url = {s.get("url", ""): s for s in sources}
    if not candidates:
        print("No candidates found. Run generate_post_candidates.py first.")
        return 1
    for item in candidates:
        url = item.get("url")
        if not url:
            continue
        manual_text = get_manual_override(item)
        if not manual_text and url in cache and cache[url].get("status") in {"ok", "partial", "summary_only"}:
            print(f"Cached: {item.get('title')}")
            continue
        source_item = source_by_url.get(url, {})
        print(f"Extracting: {item.get('title')}")
        cache[url] = fetch_article(item, source_item.get("summary", "") or item.get("summary", ""), source_item.get("published", "") or item.get("published", ""))
    save(cache, RESEARCH)
    print("\nDone.")
    print(f"Research cache: {RESEARCH}")
    print(f"Manual overrides folder: {OVERRIDES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
