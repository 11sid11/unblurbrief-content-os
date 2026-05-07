from __future__ import annotations

import argparse, base64, json, re, shutil, zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
EXPORT_ROOT = ROOT / "canva_review_packs"

def norm(t): return " ".join(str(t or "").split()).strip()
def slug(t): return re.sub(r"[^a-z0-9]+","-",norm(t).lower()).strip("-")[:80] or "unblurbrief-post"
def write(p,c): p.write_text(c or "", encoding="utf-8")
def decode_data_url(data_url):
    header, encoded = data_url.split(",",1)
    mime = header.split(";")[0].replace("data:","").lower()
    ext = {"image/png":".png","image/jpeg":".jpg","image/jpg":".jpg","image/webp":".webp"}.get(mime,".png")
    return base64.b64decode(encoded), ext

def fields(data: dict[str, Any]):
    cand = data.get("candidate", {}) if isinstance(data.get("candidate"), dict) else {}
    tracker = data.get("tracker", {}) if isinstance(data.get("tracker"), dict) else {}
    pkg = tracker.get("package", {}) if isinstance(tracker.get("package"), dict) else {}
    return {
        "title": norm(pkg.get("carouselTitle") or pkg.get("title") or cand.get("title") or data.get("title") or "UnblurBrief Post"),
        "url": norm(cand.get("url") or data.get("source_url") or data.get("url") or ""),
        "caption": pkg.get("caption") or data.get("caption") or "",
        "hashtags": pkg.get("hashtags") or data.get("hashtags") or "",
        "image_prompt": pkg.get("imagePrompt") or data.get("image_prompt") or "",
        "verification": pkg.get("verification") or data.get("verification") or "",
        "slide_copy": pkg.get("slideCopy") or data.get("slide_copy") or "",
        "visual_direction": pkg.get("visualDirection") or data.get("visual_direction") or "",
        "images": tracker.get("images") if isinstance(tracker.get("images"), list) else data.get("images", []),
        "candidate": cand,
    }

def create_pack(package_json: Path, slide_paths=None):
    data = json.loads(package_json.read_text(encoding="utf-8"))
    f = fields(data)
    folder = EXPORT_ROOT / f"{datetime.now().strftime('%Y-%m-%d_%H-%M')}_{slug(f['title'])}"
    slides = folder / "slides"
    slides.mkdir(parents=True, exist_ok=True)
    for name, key in [("caption.txt","caption"),("hashtags.txt","hashtags"),("image_prompt.txt","image_prompt"),("verification_checklist.txt","verification"),("slide_copy.txt","slide_copy"),("visual_direction.txt","visual_direction"),("source_url.txt","url")]:
        write(folder/name, f[key])
    write(folder/"source.json", json.dumps({"title":f["title"],"source_url":f["url"],"candidate":f["candidate"]}, ensure_ascii=False, indent=2))
    write(folder/"canva_upload_instructions.txt", f"""Canva Upload Instructions

1. Open Canva.
2. Open UnblurBrief / Ready for Review.
3. Upload files from the slides folder.
4. Review the carousel.
5. Use caption.txt and hashtags.txt.
6. Check verification_checklist.txt.
7. Schedule/publish using Canva Content Planner.

Source:
{f['url']}
""")
    count = 0
    for i, img in enumerate((f.get("images") or [])[:5], 1):
        if not img: continue
        try:
            b, ext = decode_data_url(str(img))
            (slides/f"slide_{i}{ext}").write_bytes(b)
            count += 1
        except Exception:
            pass
    for i, raw in enumerate(slide_paths or [], 1):
        src = Path(raw)
        if src.exists():
            shutil.copy2(src, slides/f"slide_{i}{src.suffix or '.png'}")
            count += 1
    if count == 0:
        write(slides/"NO_SLIDES_FOUND.txt", "No slide images found. Add slide_1.png ... slide_5.png here before uploading to Canva.")
    zip_path = folder.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in folder.rglob("*"):
            z.write(p, p.relative_to(folder))
    print(f"Canva Review Pack created:\n{zip_path}")
    return zip_path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package_json")
    parser.add_argument("--slides", nargs="*", default=[])
    args = parser.parse_args()
    create_pack(Path(args.package_json), args.slides)
if __name__ == "__main__":
    main()
