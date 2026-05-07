from __future__ import annotations

import base64
import json
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from canva_oauth import get_valid_canva_access_token

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "workflow_config.json"

CANVA_API_BASE = "https://api.canva.com/rest/v1"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tiff", ".tif", ".heic"}


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
    data = load_json(CONFIG_FILE, {})
    if not isinstance(data, dict):
        data = {}
    return data


def canva_token() -> str:
    return get_valid_canva_access_token()


def canva_headers(json_content: bool = True) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {canva_token()}"}
    if json_content:
        headers["Content-Type"] = "application/json"
    return headers


def request_json(method: str, path: str, **kwargs) -> dict[str, Any]:
    url = f"{CANVA_API_BASE}{path}"
    response = requests.request(method, url, timeout=60, **kwargs)
    if response.status_code == 204:
        return {"status_code": 204}
    try:
        payload = response.json()
    except Exception:
        payload = {"raw_text": response.text}
    if not response.ok:
        raise RuntimeError(f"Canva API error {response.status_code} for {method} {path}: {payload}")
    return payload


def create_folder(name: str, parent_folder_id: str = "uploads") -> dict[str, Any]:
    payload = {
        "name": name[:255],
        "parent_folder_id": parent_folder_id or "uploads",
    }
    return request_json("POST", "/folders", headers=canva_headers(), json=payload)


def move_folder_item(item_id: str, to_folder_id: str) -> dict[str, Any]:
    payload = {
        "item_id": item_id,
        "to_folder_id": to_folder_id,
    }
    return request_json("POST", "/folders/move", headers=canva_headers(), json=payload)


def upload_asset(file_path: Path, display_name: str | None = None, poll_timeout_seconds: int = 180) -> dict[str, Any]:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Asset not found: {file_path}")
    if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError(f"Unsupported image file type for Canva asset upload: {file_path.suffix}")

    name = (display_name or file_path.name)[:50]
    name_base64 = base64.b64encode(name.encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Bearer {canva_token()}",
        "Content-Type": "application/octet-stream",
        "Asset-Upload-Metadata": json.dumps({"name_base64": name_base64}),
    }

    with file_path.open("rb") as f:
        response = requests.post(f"{CANVA_API_BASE}/asset-uploads", headers=headers, data=f, timeout=120)

    try:
        job_payload = response.json()
    except Exception:
        job_payload = {"raw_text": response.text}

    if not response.ok:
        raise RuntimeError(f"Canva asset upload start failed {response.status_code}: {job_payload}")

    job = job_payload.get("job", job_payload)
    job_id = job.get("id") or job.get("job_id") or job_payload.get("id")
    if not job_id:
        raise RuntimeError(f"Could not find upload job id in response: {job_payload}")

    return poll_asset_upload(job_id, timeout_seconds=poll_timeout_seconds)


def poll_asset_upload(job_id: str, timeout_seconds: int = 180) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_payload: dict[str, Any] = {}

    while time.time() < deadline:
        payload = request_json("GET", f"/asset-uploads/{job_id}", headers=canva_headers(json_content=False))
        last_payload = payload
        job = payload.get("job", payload)
        status = str(job.get("status", "")).lower()

        if status in {"success", "succeeded", "completed", "complete"}:
            asset = (
                job.get("asset")
                or job.get("result", {}).get("asset")
                or payload.get("asset")
                or payload.get("result", {}).get("asset")
            )
            asset_id = None
            if isinstance(asset, dict):
                asset_id = asset.get("id")
            asset_id = asset_id or job.get("asset_id") or payload.get("asset_id")
            if not asset_id:
                raise RuntimeError(f"Upload succeeded but no asset id was found: {payload}")
            return {"job_id": job_id, "asset_id": asset_id, "asset": asset or {}, "raw": payload}

        if status in {"failed", "error"}:
            raise RuntimeError(f"Canva asset upload failed: {payload}")

        time.sleep(2)

    raise TimeoutError(f"Timed out waiting for Canva upload job {job_id}. Last payload: {last_payload}")


def create_design_from_asset(asset_id: str, title: str, width: int = 1080, height: int = 1350) -> dict[str, Any]:
    payload = {
        "type": "type_and_asset",
        "design_type": {
            "type": "custom",
            "width": int(width),
            "height": int(height),
        },
        "asset_id": asset_id,
        "title": title[:255] or "UnblurBrief carousel",
    }
    return request_json("POST", "/designs", headers=canva_headers(), json=payload)


def latest_post_folder() -> Path:
    cfg = load_config()
    root = Path(str(cfg.get("generated_posts_folder", "")))
    if not root.exists():
        raise FileNotFoundError(f"Generated posts folder not found: {root}")
    folders = [p for p in root.iterdir() if p.is_dir()]
    if not folders:
        raise FileNotFoundError(f"No post folders found in: {root}")
    folders.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return folders[0]


def slide_files(post_folder: Path) -> list[Path]:
    slides_dir = post_folder / "slides"
    if not slides_dir.exists():
        raise FileNotFoundError(f"Slides folder not found: {slides_dir}")
    files = [p for p in slides_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    files.sort(key=lambda p: p.name.lower())
    if not files:
        raise FileNotFoundError(f"No slide images found in: {slides_dir}")
    return files


def send_latest_post_to_canva(open_url_callback=None) -> dict[str, Any]:
    cfg = load_config()
    if not cfg.get("canva_enabled", False):
        raise RuntimeError("Canva integration is disabled. Set canva_enabled to true in workflow_config.json.")

    post_folder = latest_post_folder()
    files = slide_files(post_folder)
    title_path = post_folder / "copy" / "carousel_title.txt"
    title = title_path.read_text(encoding="utf-8").strip() if title_path.exists() else post_folder.name
    title = title or post_folder.name

    exports_dir = post_folder / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    folder_id = None
    folder_response = None
    if cfg.get("canva_create_folder", True):
        folder_response = create_folder(post_folder.name[:255], cfg.get("canva_parent_folder_id", "uploads"))
        folder = folder_response.get("folder", folder_response)
        folder_id = folder.get("id") if isinstance(folder, dict) else None

    uploaded_assets = []
    for i, file_path in enumerate(files, start=1):
        upload = upload_asset(file_path, display_name=f"{post_folder.name}_slide_{i:02d}{file_path.suffix.lower()}")
        asset_id = upload["asset_id"]
        move_response = None
        if folder_id and cfg.get("canva_move_assets_to_folder", True):
            try:
                move_response = move_folder_item(asset_id, folder_id)
            except Exception as exc:
                move_response = {"warning": str(exc)}
        uploaded_assets.append({
            "slide": i,
            "file": str(file_path),
            "asset_id": asset_id,
            "upload": upload,
            "move_response": move_response,
        })

    design_response = None
    edit_url = ""
    view_url = ""
    if cfg.get("canva_create_design", True) and uploaded_assets:
        design_response = create_design_from_asset(
            uploaded_assets[0]["asset_id"],
            title=f"UnblurBrief - {title}",
            width=int(cfg.get("canva_design_width", 1080)),
            height=int(cfg.get("canva_design_height", 1350)),
        )
        design = design_response.get("design", design_response)
        urls = design.get("urls", {}) if isinstance(design, dict) else {}
        edit_url = urls.get("edit_url", "")
        view_url = urls.get("view_url", "")

    result = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "post_folder": str(post_folder),
        "title": title,
        "canva_folder_id": folder_id,
        "folder_response": folder_response,
        "uploaded_assets": uploaded_assets,
        "design_response": design_response,
        "edit_url": edit_url,
        "view_url": view_url,
        "note": "Canva API can upload all assets and create/open a design using the first slide. Add the remaining uploaded slide assets as pages manually unless you later use a template/autofill workflow.",
    }

    save_json(exports_dir / "canva_api_result.json", result)
    if edit_url:
        (exports_dir / "canva_design_link.txt").write_text(edit_url, encoding="utf-8")
        if cfg.get("canva_open_design_after_create", True):
            if open_url_callback:
                open_url_callback(edit_url)
            else:
                webbrowser.open(edit_url)

    return result


if __name__ == "__main__":
    result = send_latest_post_to_canva()
    print(json.dumps(result, ensure_ascii=False, indent=2))
