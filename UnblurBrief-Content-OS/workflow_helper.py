from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "workflow_config.json"
OUTPUT_DIR = ROOT / "output"
CANDIDATES_FILE = OUTPUT_DIR / "top_post_candidates.json"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> dict[str, Any]:
    defaults = {
        "brave_exe": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        "brave_profile_directory": "Profile 2",
        "chatgpt_url": "https://chatgpt.com",
        "canva_url": "https://www.canva.com",
        "download_folder": r"C:\UnblurBrief\ChatGPT Slides",
        "generated_posts_folder": r"C:\UnblurBrief\Generated Posts",
        "move_files": True,
        "expected_slide_count": 5,
    }
    data = load_json(CONFIG_FILE, {})
    if isinstance(data, dict):
        defaults.update(data)
    return defaults


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\n", " ").replace("\t", " ").split()).strip()


def slugify(text: str, max_len: int = 70) -> str:
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_len].strip("-") or "unblurbrief-post"


def get_candidate(index: int = 0) -> dict[str, Any]:
    candidates = load_json(CANDIDATES_FILE, [])
    if not isinstance(candidates, list) or not candidates:
        return {}
    if index < 0 or index >= len(candidates):
        index = 0
    return candidates[index]


def make_post_id(candidate: dict[str, Any] | None = None, title: str | None = None) -> str:
    base_title = title or (candidate or {}).get("title", "") or "unblurbrief-post"
    return f"{datetime.now().strftime('%Y-%m-%d_%H%M')}_{slugify(base_title)}"


def open_brave(url: str) -> None:
    cfg = load_config()
    brave = str(cfg.get("brave_exe", "")).strip()
    profile = str(cfg.get("brave_profile_directory", "")).strip()

    if brave and Path(brave).exists():
        args = [brave]
        if profile:
            args.append(f"--profile-directory={profile}")
        args.append(url)
        subprocess.Popen(args)
    else:
        print(f"Brave executable not found: {brave}")
        print("Opening with default browser instead.")
        webbrowser.open(url)


def latest_image_files(folder: Path, count: int = 5) -> list[Path]:
    if not folder.exists():
        raise FileNotFoundError(f"Download folder does not exist: {folder}")
    files = [
        p for p in folder.iterdir()
        if p.is_file()
        and p.suffix.lower() in IMAGE_EXTENSIONS
        and not p.name.endswith(".crdownload")
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:count]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or "", encoding="utf-8")


def package_latest_slides(candidate_index: int = 0, copy_instead_of_move: bool | None = None, count: int | None = None, candidate_override: dict[str, Any] | None = None) -> Path:
    cfg = load_config()
    candidate = candidate_override if isinstance(candidate_override, dict) and candidate_override else get_candidate(candidate_index)
    count = int(count or candidate.get("recommended_slide_count") or cfg.get("expected_slide_count", 5))
    download_folder = Path(str(cfg.get("download_folder", "")))
    generated_root = Path(str(cfg.get("generated_posts_folder", "")))
    move_files = bool(cfg.get("move_files", True))
    if copy_instead_of_move is not None:
        move_files = not copy_instead_of_move

    post_id = make_post_id(candidate)
    post_dir = generated_root / post_id
    slides_dir = post_dir / "slides"
    copy_dir = post_dir / "copy"
    source_dir = post_dir / "source"
    exports_dir = post_dir / "exports"

    for d in [slides_dir, copy_dir, source_dir, exports_dir]:
        d.mkdir(parents=True, exist_ok=True)

    files = latest_image_files(download_folder, count=count)
    if len(files) < count:
        raise RuntimeError(f"Found only {len(files)} image file(s) in {download_folder}. Expected {count}.")

    # Oldest among the latest 5 becomes slide_01. This matches normal sequential downloads.
    ordered = sorted(files, key=lambda p: p.stat().st_mtime)
    imported = []

    for i, src in enumerate(ordered, start=1):
        dest = slides_dir / f"slide_{i:02d}{src.suffix.lower()}"
        if dest.exists():
            dest.unlink()

        if move_files:
            shutil.move(str(src), str(dest))
            action = "moved"
        else:
            shutil.copy2(src, dest)
            action = "copied"

        imported.append({
            "slide": i,
            "source_file": str(src),
            "saved_as": str(dest),
            "action": action,
        })

    title = clean_text(candidate.get("title", ""))
    source_url = clean_text(candidate.get("url", ""))

    write_text(copy_dir / "caption_hashtags.txt", "")
    write_text(copy_dir / "carousel_title.txt", title)
    write_text(copy_dir / "slide_copy.md", "")
    write_text(source_dir / "source_url.txt", source_url)
    write_text(source_dir / "candidate_source.json", json.dumps(candidate, ensure_ascii=False, indent=2) if candidate else "{}")

    manifest = {
        "post_id": post_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "title": title,
        "source_url": source_url,
        "download_folder": str(download_folder),
        "post_folder": str(post_dir),
        "slides_folder": str(slides_dir),
        "expected_slide_count": count,
        "imported_files": imported,
        "canva_next_steps": [
            "Open Canva.",
            "Create an Instagram carousel/post design.",
            "Upload slide_01 onward from the slides folder.",
            "Review the post manually.",
            "Schedule through Canva Content Planner."
        ]
    }
    save_json(exports_dir / "canva_upload_manifest.json", manifest)

    print("\nPost packaged successfully.")
    print(f"Post folder: {post_dir}")
    print(f"Slides folder: {slides_dir}")
    return post_dir


def open_generated_posts_folder() -> None:
    folder = Path(str(load_config().get("generated_posts_folder", "")))
    folder.mkdir(parents=True, exist_ok=True)

    if sys.platform.startswith("win"):
        os.startfile(str(folder))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "help"

    try:
        if cmd == "connect-canva":
            from canva_oauth import connect_canva
            result = connect_canva(open_url_callback=open_brave)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif cmd == "check-canva-auth":
            from canva_oauth import canva_auth_status
            print(json.dumps(canva_auth_status(), ensure_ascii=False, indent=2))
        elif cmd == "refresh-canva-token":
            from canva_oauth import refresh_canva_token
            result = refresh_canva_token()
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif cmd == "open-chatgpt":
            open_brave(load_config().get("chatgpt_url", "https://chatgpt.com"))
        elif cmd == "open-canva":
            open_brave(load_config().get("canva_url", "https://www.canva.com"))
        elif cmd == "open-both":
            open_brave(load_config().get("chatgpt_url", "https://chatgpt.com"))
            time.sleep(1)
            open_brave(load_config().get("canva_url", "https://www.canva.com"))
        elif cmd == "package-latest":
            count = int(argv[2]) if len(argv) > 2 and str(argv[2]).isdigit() else None
            index = int(argv[3]) if len(argv) > 3 and str(argv[3]).isdigit() else 0
            package_latest_slides(candidate_index=index, count=count)
        elif cmd == "open-posts-folder":
            open_generated_posts_folder()
        elif cmd == "send-latest-to-canva":
            from canva_client import send_latest_post_to_canva
            result = send_latest_post_to_canva(open_url_callback=open_brave)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif cmd == "package-latest-and-send-canva":
            count = int(argv[2]) if len(argv) > 2 and str(argv[2]).isdigit() else None
            index = int(argv[3]) if len(argv) > 3 and str(argv[3]).isdigit() else 0
            package_latest_slides(candidate_index=index, count=count)
            from canva_client import send_latest_post_to_canva
            result = send_latest_post_to_canva(open_url_callback=open_brave)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif cmd == "config":
            print(json.dumps(load_config(), indent=2))
        else:
            print("""UnblurBrief Workflow Helper

Commands:
  python workflow_helper.py connect-canva
  python workflow_helper.py check-canva-auth
  python workflow_helper.py refresh-canva-token
  python workflow_helper.py open-chatgpt
  python workflow_helper.py open-canva
  python workflow_helper.py open-both
  python workflow_helper.py package-latest [candidate_index]
  python workflow_helper.py open-posts-folder
  python workflow_helper.py send-latest-to-canva
  python workflow_helper.py package-latest-and-send-canva
  python workflow_helper.py config

Edit workflow_config.json first:
  - brave_exe
  - brave_profile_directory
  - download_folder
  - generated_posts_folder
""")
    except Exception as exc:
        print(f"\nERROR: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
