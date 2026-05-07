from __future__ import annotations

"""PIB-only debug runner for UnblurBrief OS.

This script intentionally runs only the PIB Delhi All Releases collector.
It does not call Guardian, NewsAPI, Mediastack, GDELT, public API lanes,
research enrichment, Canva, or candidate generation.
"""

import json
import csv
from pathlib import Path
from typing import Any

import scrape_sources as ss

ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT_DIR / "output"
PIB_ONLY_JSON = OUTPUT_DIR / "pib_only_sources.json"
PIB_ONLY_CSV = OUTPUT_DIR / "pib_only_sources.csv"


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        url = str(item.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(item)
    return out


def _find_pib_sources() -> list[ss.SourceConfig]:
    sources = ss.load_sources(ss.SOURCES_FILE)
    pib_sources = [s for s in sources if s.source_type == "pib_all_releases"]
    if not pib_sources:
        raise SystemExit(
            "No source_type='pib_all_releases' entry found in sources.json. "
            "Add the PIB Delhi All Releases source before running PIB-only debug."
        )
    return pib_sources


def _write_pib_only_debug_outputs(items: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    PIB_ONLY_JSON.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    fieldnames = [
        "source", "source_name", "source_url", "source_type", "trust_role",
        "category", "category_lane", "title", "url", "summary", "published",
        "scraped_at", "priority", "content_angle", "used_for_post", "ministry",
        "pib_newsworthiness_score", "pib_priority_label", "pib_score_reasons",
        "pib_filter_reasons",
    ]
    with PIB_ONLY_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow({k: item.get(k, "") for k in fieldnames})

    print(f"pib_only_sources_json: {PIB_ONLY_JSON}")
    print(f"pib_only_sources_csv:  {PIB_ONLY_CSV}")


def main() -> int:
    print("=" * 72)
    print("UnblurBrief PIB-only debug runner")
    print("This run will NOT call paid/keyed news APIs or Canva.")
    print("=" * 72)

    OUTPUT_DIR.mkdir(exist_ok=True)
    sources = _find_pib_sources()
    print(f"pib_sources_found_in_sources_json: {len(sources)}")
    for src in sources:
        print(f"pib_source: {src.name} | {src.url}")

    items: list[dict[str, Any]] = []
    for source in sources:
        items.extend(ss.scrape_pib_all_releases(source))

    items = _dedupe(items)

    research = ss.load_json(ss.RESEARCH_OUTPUT, {})
    if not isinstance(research, dict):
        research = {}

    records = ss.save_pib_all_releases(items, research_by_url=research)
    _write_pib_only_debug_outputs(items)

    priority_counts: dict[str, int] = {}
    for item in items:
        label = str(item.get("pib_priority_label") or "routine")
        priority_counts[label] = priority_counts.get(label, 0) + 1

    print("=" * 72)
    print("PIB-only run complete.")
    print(f"valid_pib_releases_collected: {len(items)}")
    print(f"pib_saved_to_pib_all_releases_json: {len(records)}")
    print(f"pib_priority_counts: {priority_counts}")
    print(f"pib_all_releases_json: {ss.PIB_ALL_OUTPUT}")
    print(f"pib_debug_snapshot_html: {ss.PIB_DEBUG_HTML}")
    print(f"pib_debug_links_json: {ss.PIB_DEBUG_LINKS}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
