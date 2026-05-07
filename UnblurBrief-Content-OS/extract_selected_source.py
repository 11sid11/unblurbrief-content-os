from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from extract_research import (
    CANDIDATES,
    OUTPUT,
    RESEARCH,
    SOURCES,
    fetch_article,
    load,
    save,
)

ROOT = Path(__file__).resolve().parent

PIB_ALL_RELEASES = OUTPUT / "pib_all_releases.json"


def reliability_details(state: str, publishable: bool, score: int, note: str, result: dict[str, Any]) -> tuple[list[str], list[str]]:
    word_count = len(clean(result.get("excerpt")).split())
    facts = result.get("key_facts") if isinstance(result.get("key_facts"), list) else []
    fact_count = len([f for f in facts if clean(f)])
    reasons = [note, f"Extraction status: {clean(result.get('status')) or 'unknown'}.", f"Extraction method: {clean(result.get('method')) or 'unknown'}.", f"Article text available: {word_count} words.", f"Key facts extracted: {fact_count}."]
    missing: list[str] = []
    if not publishable:
        if word_count < 250:
            missing.append("Full article text below 250 words.")
        if fact_count < 3:
            missing.append("Fewer than 3 key facts extracted.")
    return reasons, missing


def update_list_item(path: Path, updated: dict[str, Any]) -> bool:
    url = clean(updated.get("url"))
    rows = load(path, [])
    if not isinstance(rows, list):
        rows = []
    changed = False
    for i, row in enumerate(rows):
        if isinstance(row, dict) and clean(row.get("url")) == url:
            merged = dict(row)
            merged.update(updated)
            rows[i] = merged
            changed = True
            break
    if not changed:
        rows.insert(0, updated)
        changed = True
    save(rows, path)
    return changed


def maybe_add_to_top_candidates(updated: dict[str, Any]) -> bool:
    label = clean(updated.get("pib_priority_label")).lower()
    state = clean(updated.get("reliability_state")).lower()
    if clean(updated.get("source_type")) != "pib_all_releases":
        return False
    if label not in {"strong", "usable"}:
        return False
    if state not in {"verified", "usable_with_caution"}:
        return False
    top = load(CANDIDATES, [])
    if not isinstance(top, list):
        top = []
    url = clean(updated.get("url"))
    updated = dict(updated)
    updated["recommended_candidate"] = True
    replaced = False
    for i, row in enumerate(top):
        if isinstance(row, dict) and clean(row.get("url")) == url:
            merged = dict(row)
            merged.update(updated)
            top[i] = merged
            replaced = True
            break
    if not replaced:
        top.insert(0, updated)
    save(top, CANDIDATES)
    return True


def build_verified_item(item: dict[str, Any], result: dict[str, Any], state: str, publishable: bool, score: int, note: str, cache: dict[str, Any]) -> dict[str, Any]:
    item = dict(item)
    reasons, missing = reliability_details(state, publishable, score, note, result)
    item["research_available"] = True
    item["research_extraction_status"] = result.get("status", "")
    item["extraction_method"] = result.get("method", "")
    item["article_text"] = result.get("excerpt", "")
    item["key_facts"] = result.get("key_facts", [])
    item["reliability_state"] = state
    item["reliability_score"] = max(int(float(item.get("reliability_score", 0) or 0)), score)
    item["reliability_reasons"] = reasons
    item["reliability_missing"] = missing
    item["is_publishable_source"] = publishable
    item["trust_role"] = "verified_extracted_article" if state == "verified" else "extracted_article" if publishable else item.get("trust_role", "primary_official")
    item["source_verification_note"] = note
    item.setdefault("source", item.get("source_name") or "PIB Delhi All Releases - English")
    item.setdefault("source_name", item.get("source") or "PIB Delhi All Releases - English")
    item.setdefault("source_type", "pib_all_releases" if "pib.gov.in" in clean(item.get("url")) else item.get("source_type", ""))
    item.setdefault("category", "India")
    item.setdefault("category_lane", "India")
    item.setdefault("priority", "High" if clean(item.get("pib_priority_label")).lower() == "strong" else "Medium")
    item.setdefault("content_angle", "India official current-affairs update")

    # Reuse the local enrich/prompt builder. This does not call external APIs.
    try:
        from enrich_candidates_v25 import enrich_item, seed_to_candidate
        seeded = seed_to_candidate(item, 0)
        seeded.update(item)
        item = enrich_item(seeded, cache)
        item["research_available"] = True
        item["reliability_reasons"] = reasons
        item["reliability_missing"] = missing
        item["source_verification_note"] = note
    except Exception as exc:
        item["content_prompt"] = item.get("content_prompt", "") or f"Source verified but prompt regeneration failed: {exc}"
    return item


def extract_item_direct(item: dict[str, Any], source_file: str = "", add_to_top: bool = True) -> dict[str, Any]:
    OUTPUT.mkdir(exist_ok=True)
    cache = load(RESEARCH, {})
    if not isinstance(cache, dict):
        cache = {}
    sources = load(SOURCES, [])
    if not isinstance(sources, list):
        sources = []

    item = dict(item or {})
    url = clean(item.get("url"))
    if not url:
        raise RuntimeError("Selected item has no URL to extract.")

    source_by_url = {clean(s.get("url")): s for s in sources if isinstance(s, dict)}
    source_item = source_by_url.get(url, {})
    print(f"Extracting selected source directly: {item.get('title')}")
    result = fetch_article(
        item,
        source_item.get("summary", "") or item.get("summary", ""),
        source_item.get("published", "") or item.get("published", ""),
    )
    cache[url] = result
    save(cache, RESEARCH)

    state, publishable, score, note = extraction_upgrade_state(result)
    updated = build_verified_item(item, result, state, publishable, score, note, cache)

    saved_to_pib = False
    saved_to_top = False
    if source_file == "pib_all_releases" or clean(updated.get("source_type")) == "pib_all_releases" or "pib.gov.in" in url:
        saved_to_pib = update_list_item(PIB_ALL_RELEASES, updated)
        if add_to_top:
            saved_to_top = maybe_add_to_top_candidates(updated)
    else:
        update_list_item(CANDIDATES, updated)
        saved_to_top = True

    payload = {
        "ok": True,
        "source_file": source_file or "direct_item",
        "url": url,
        "title": updated.get("title", ""),
        "extraction_status": result.get("status", ""),
        "extraction_method": result.get("method", ""),
        "word_count": len(clean(result.get("excerpt")).split()),
        "fact_count": len(result.get("key_facts") or []),
        "new_reliability_state": updated.get("reliability_state", state),
        "new_reliability_score": updated.get("reliability_score", score),
        "is_publishable_source": updated.get("is_publishable_source", publishable),
        "note": updated.get("source_verification_note", note),
        "saved_to_pib_all_releases_json": saved_to_pib,
        "added_or_updated_top_post_candidates_json": saved_to_top,
        "warnings": result.get("warnings", []),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def clean(v: Any) -> str:
    return " ".join(str(v or "").replace("\n", " ").replace("\t", " ").split()).strip()


def extraction_upgrade_state(result: dict[str, Any]) -> tuple[str, bool, int, str]:
    status = clean(result.get("status")).lower()
    method = clean(result.get("method")).lower()
    excerpt = clean(result.get("excerpt"))
    facts = result.get("key_facts") if isinstance(result.get("key_facts"), list) else []
    word_count = len(excerpt.split())
    fact_count = len([f for f in facts if clean(f)])

    if status == "ok" and word_count >= 250 and fact_count >= 3:
        return "verified", True, 86, "source extracted successfully and promoted to verified extracted article"

    if status == "ok" and word_count >= 80:
        return "usable_with_caution", True, 68, "short source extraction succeeded; use carefully"

    if status in {"partial", "summary_only"}:
        return "source_check_required", False, 38, "partial extraction only; manual source check still required"

    return "source_check_required", False, 20, "source extraction failed or produced insufficient text"


def run_step(name: str, script: str) -> None:
    print("\n" + "-" * 64)
    print(name)
    print("-" * 64)
    subprocess.check_call([sys.executable, script], cwd=ROOT)


def extract_selected(index: int) -> dict[str, Any]:
    OUTPUT.mkdir(exist_ok=True)
    candidates = load(CANDIDATES, [])
    sources = load(SOURCES, [])
    cache = load(RESEARCH, {})

    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("No candidates found. Run START_HERE.bat first.")
    if index < 0 or index >= len(candidates):
        raise IndexError(f"Candidate index {index} is out of range. Candidate count: {len(candidates)}")

    item = dict(candidates[index])
    url = clean(item.get("url"))
    if not url:
        raise RuntimeError("Selected candidate has no URL to extract.")

    source_by_url = {clean(s.get("url")): s for s in sources if isinstance(s, dict)}
    source_item = source_by_url.get(url, {})

    print(f"Extracting selected source: {item.get('title')}")
    result = fetch_article(
        item,
        source_item.get("summary", "") or item.get("summary", ""),
        source_item.get("published", "") or item.get("published", ""),
    )

    cache[url] = result
    save(cache, RESEARCH)

    state, publishable, score, note = extraction_upgrade_state(result)

    # Update selected candidate immediately so regenerate/enrich has stronger metadata.
    item["research_extraction_status"] = result.get("status", "")
    item["article_text"] = result.get("excerpt", "")
    item["key_facts"] = result.get("key_facts", [])
    item["reliability_state"] = state
    item["is_publishable_source"] = publishable
    item["reliability_score"] = max(int(item.get("reliability_score", 0) or 0), score)
    item["trust_role"] = "verified_extracted_article" if state == "verified" else "extracted_article" if publishable else item.get("trust_role", "discovery_only")
    item["source_verification_note"] = note
    candidates[index] = item
    save(candidates, CANDIDATES)

    # Rebuild from current local files only. No scraper/API pull.
    run_step("STEP 1 — Regenerate candidates using updated research cache", "generate_post_candidates.py")
    run_step("STEP 2 — Re-enrich candidates with classifier/scoring + dynamic slides", "enrich_candidates_v25.py")

    # Try to find selected URL after regeneration.
    updated_candidates = load(CANDIDATES, [])
    updated = next((c for c in updated_candidates if clean(c.get("url")) == url), item) if isinstance(updated_candidates, list) else item

    payload = {
        "ok": True,
        "candidate_index": index,
        "url": url,
        "title": item.get("title", ""),
        "extraction_status": result.get("status", ""),
        "extraction_method": result.get("method", ""),
        "word_count": len(clean(result.get("excerpt")).split()),
        "fact_count": len(result.get("key_facts") or []),
        "new_reliability_state": updated.get("reliability_state", state),
        "new_reliability_score": updated.get("reliability_score", score),
        "is_publishable_source": updated.get("is_publishable_source", publishable),
        "note": updated.get("source_verification_note", note),
        "warnings": result.get("warnings", []),
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Extract one selected UnblurBrief source and rebuild candidates locally.")
    parser.add_argument("--index", type=int, required=True, help="Candidate index from top_post_candidates.json")
    args = parser.parse_args()

    extract_selected(args.index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
