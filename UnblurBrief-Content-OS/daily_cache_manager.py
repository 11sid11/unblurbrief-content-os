from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
CACHE_ROOT = ROOT / "daily_source_cache"

FILES_TO_CACHE = [
    "unblurbrief_sources.json",
    "unblurbrief_sources.csv",
    "pib_all_releases.json",
    "public_api_v25_sources.json",
    "research_cache.json",
]


def today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cache_dir_for(day: str | None = None) -> Path:
    return CACHE_ROOT / (day or today_key())


def latest_cache_dir() -> Path | None:
    if not CACHE_ROOT.exists():
        return None
    dirs = [p for p in CACHE_ROOT.iterdir() if p.is_dir()]
    if not dirs:
        return None
    dirs.sort(key=lambda p: p.name, reverse=True)
    return dirs[0]


def save_today_cache() -> dict[str, Any]:
    OUTPUT.mkdir(exist_ok=True)
    target = cache_dir_for()
    target.mkdir(parents=True, exist_ok=True)

    copied = []
    missing = []
    for name in FILES_TO_CACHE:
        src = OUTPUT / name
        if src.exists():
            shutil.copy2(src, target / name)
            copied.append(name)
        else:
            missing.append(name)

    manifest = {
        "cache_date": today_key(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "copied_files": copied,
        "missing_files": missing,
        "note": "Use REBUILD_FROM_TODAY_CACHE.bat or REBUILD_FROM_LATEST_CACHE.bat to regenerate candidates without pulling APIs/scrapers again."
    }
    save_json(target / "cache_manifest.json", manifest)
    print(f"Saved daily source cache: {target}")
    print(f"Copied: {', '.join(copied) if copied else 'none'}")
    if missing:
        print(f"Missing: {', '.join(missing)}")
    return manifest


def restore_cache(day: str | None = None, latest: bool = False) -> dict[str, Any]:
    if latest:
        source = latest_cache_dir()
        if source is None:
            raise FileNotFoundError("No cache folders found in daily_source_cache.")
    else:
        source = cache_dir_for(day)

    if not source.exists():
        raise FileNotFoundError(f"Cache folder not found: {source}")

    OUTPUT.mkdir(exist_ok=True)
    restored = []
    missing = []
    for name in FILES_TO_CACHE:
        src = source / name
        if src.exists():
            shutil.copy2(src, OUTPUT / name)
            restored.append(name)
        else:
            missing.append(name)

    manifest = {
        "restored_from": str(source),
        "restored_at": datetime.now().isoformat(timespec="seconds"),
        "restored_files": restored,
        "missing_files": missing,
    }
    save_json(OUTPUT / "last_cache_restore.json", manifest)
    print(f"Restored source cache from: {source}")
    print(f"Restored: {', '.join(restored) if restored else 'none'}")
    if missing:
        print(f"Cache did not contain: {', '.join(missing)}")
    return manifest


def status() -> dict[str, Any]:
    today = cache_dir_for()
    latest = latest_cache_dir()
    payload = {
        "today": str(today),
        "today_exists": today.exists(),
        "latest": str(latest) if latest else "",
        "latest_exists": bool(latest),
        "cache_root": str(CACHE_ROOT),
    }
    if today.exists():
        payload["today_files"] = sorted([p.name for p in today.iterdir() if p.is_file()])
    if latest and latest.exists():
        payload["latest_files"] = sorted([p.name for p in latest.iterdir() if p.is_file()])
    print(json.dumps(payload, indent=2))
    return payload


def main() -> int:
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "save-today":
        save_today_cache()
    elif cmd == "restore-today":
        restore_cache()
    elif cmd == "restore-latest":
        restore_cache(latest=True)
    elif cmd == "status":
        status()
    else:
        print("Commands: save-today | restore-today | restore-latest | status")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
