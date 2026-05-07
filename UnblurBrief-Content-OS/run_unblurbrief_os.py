from __future__ import annotations

import importlib.util
import json
import os
import socket
import shlex
import subprocess
import sys
import time
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread


ROOT = Path(__file__).resolve().parent
REQUIREMENTS = ROOT / "requirements.txt"


WORKFLOW_CONFIG = ROOT / "workflow_config.json"


def load_workflow_config() -> dict:
    defaults = {
        "brave_exe": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        "brave_profile_directory": "Profile 2",
    }
    if WORKFLOW_CONFIG.exists():
        try:
            data = json.loads(WORKFLOW_CONFIG.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                defaults.update(data)
        except Exception:
            pass
    return defaults


def open_url(url: str) -> None:
    cfg = load_workflow_config()
    brave = str(cfg.get("brave_exe", "")).strip()
    profile = str(cfg.get("brave_profile_directory", "")).strip()

    if brave and Path(brave).exists():
        args = [brave]
        if profile:
            args.append(f"--profile-directory={profile}")
        args.append(url)
        subprocess.Popen(args)
        print(f"Opened in Brave using profile: {profile or 'default'}")
    else:
        print("Brave not found in workflow_config.json. Opening with default browser instead.")
        webbrowser.open(url)

REQUIRED_MODULES = {
    "feedparser": "feedparser",
    "requests": "requests",
    "bs4": "beautifulsoup4",
    "lxml": "lxml",
    "trafilatura": "trafilatura",
    "scrapling": "scrapling",
}


def print_header() -> None:
    print("\n" + "=" * 64)
    print("UNBLURBRIEF CONTENT OS — V27 DAILY SOURCE CACHE")
    print("=" * 64)
    print("This will:")
    print("1. Check/install Python dependencies")
    print("2. Scrape sources")
    print("3. Rank post candidates")
    print("4. Extract article/research context")
    print("5. Apply source reliability gate")
    print("6. Regenerate prompts safely")
    print("7. Add public API candidates from HN, World Bank, Wikipedia")
    print("8. Apply dynamic 3–6 slide recommendation")
    print("9. Save today source/research cache")
    print("10. Start localhost and open the console")
    print("=" * 64 + "\n")


def missing_modules() -> list[str]:
    return [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]


def install_requirements() -> None:
    missing = missing_modules()
    if not missing:
        print("Dependencies OK.")
        return

    print(f"Missing dependencies: {', '.join(missing)}")
    print("Installing requirements. This may take a few minutes the first time...\n")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)], cwd=ROOT)


def run_step(name: str, command: str) -> None:
    print("\n" + "-" * 64)
    print(name)
    print("-" * 64)
    # Allows commands like "daily_cache_manager.py save-today"
    # while still using the current Python interpreter.
    args = shlex.split(command)
    subprocess.check_call([sys.executable, *args], cwd=ROOT)


def find_open_port(start: int = 8000, limit: int = 20) -> int:
    for port in range(start, start + limit):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("Could not find an open localhost port.")


def start_server(port: int) -> ThreadingHTTPServer:
    os.chdir(ROOT)

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _send_json(self, payload, status=200):
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self):
            length = int(self.headers.get("Content-Length", "0") or 0)
            if not length:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                return {}

        def do_POST(self):
            try:
                if self.path == "/api/open-chatgpt":
                    from workflow_helper import open_brave, load_config
                    open_brave(load_config().get("chatgpt_url", "https://chatgpt.com"))
                    self._send_json({"ok": True, "action": "open-chatgpt"})
                    return

                if self.path == "/api/open-canva":
                    from workflow_helper import open_brave, load_config
                    open_brave(load_config().get("canva_url", "https://www.canva.com"))
                    self._send_json({"ok": True, "action": "open-canva"})
                    return

                if self.path == "/api/import-latest-slides":
                    data = self._read_json()
                    count = data.get("count")
                    item = data.get("item") or data.get("candidate")
                    candidate_index = int(data.get("candidate_index", 0) or 0)
                    from workflow_helper import package_latest_slides
                    post_dir = package_latest_slides(
                        candidate_index=candidate_index,
                        count=count,
                        candidate_override=item if isinstance(item, dict) else None,
                    )
                    self._send_json({"ok": True, "action": "import-latest-slides", "post_folder": str(post_dir)})
                    return

                if self.path == "/api/send-latest-post-to-canva":
                    from workflow_helper import open_brave
                    from canva_client import send_latest_post_to_canva
                    result = send_latest_post_to_canva(open_url_callback=open_brave)
                    self._send_json({"ok": True, "action": "send-latest-post-to-canva", "result": result})
                    return

                if self.path == "/api/import-latest-slides-and-send-canva":
                    data = self._read_json()
                    count = data.get("count")
                    item = data.get("item") or data.get("candidate")
                    candidate_index = int(data.get("candidate_index", 0) or 0)
                    from workflow_helper import package_latest_slides, open_brave
                    from canva_client import send_latest_post_to_canva
                    post_dir = package_latest_slides(
                        candidate_index=candidate_index,
                        count=count,
                        candidate_override=item if isinstance(item, dict) else None,
                    )
                    result = send_latest_post_to_canva(open_url_callback=open_brave)
                    self._send_json({"ok": True, "action": "import-latest-slides-and-send-canva", "post_folder": str(post_dir), "result": result})
                    return

                if self.path == "/api/open-generated-posts-folder":
                    from workflow_helper import open_generated_posts_folder
                    open_generated_posts_folder()
                    self._send_json({"ok": True, "action": "open-generated-posts-folder"})
                    return

                if self.path == "/api/cache-status":
                    from daily_cache_manager import status
                    result = status()
                    self._send_json({"ok": True, "action": "cache-status", "result": result})
                    return

                if self.path == "/api/save-today-cache":
                    from daily_cache_manager import save_today_cache
                    result = save_today_cache()
                    self._send_json({"ok": True, "action": "save-today-cache", "result": result})
                    return

                if self.path == "/api/rebuild-from-today-cache":
                    import subprocess, sys
                    subprocess.check_call([sys.executable, "rebuild_candidates_from_cache.py", "today"], cwd=ROOT)
                    self._send_json({"ok": True, "action": "rebuild-from-today-cache"})
                    return

                if self.path == "/api/rebuild-from-latest-cache":
                    import subprocess, sys
                    subprocess.check_call([sys.executable, "rebuild_candidates_from_cache.py", "latest"], cwd=ROOT)
                    self._send_json({"ok": True, "action": "rebuild-from-latest-cache"})
                    return

                if self.path == "/api/extract-selected-source":
                    data = self._read_json()
                    from extract_selected_source import extract_selected, extract_item_direct

                    # Normal top_post_candidates.json verification path.
                    if "candidate_index" in data and data.get("candidate_index") is not None:
                        index = int(data.get("candidate_index", 0) or 0)
                        result = extract_selected(index)
                    else:
                        # Direct source verification path, used for All PIB Releases browse cards
                        # that are not yet present in top_post_candidates.json. This path does
                        # not call Guardian/NewsAPI/Mediastack/GDELT/etc.
                        item = data.get("item") or data.get("candidate") or {}
                        if not isinstance(item, dict):
                            raise RuntimeError("Direct source verification requires an item object.")
                        result = extract_item_direct(
                            item,
                            source_file=str(data.get("source_file", "") or ""),
                            add_to_top=bool(data.get("add_to_top", True)),
                        )

                    self._send_json({"ok": True, "action": "extract-selected-source", "result": result})
                    return


                if self.path == "/api/connect-canva":
                    from workflow_helper import open_brave
                    from canva_oauth import connect_canva
                    result = connect_canva(open_url_callback=open_brave)
                    self._send_json({"ok": True, "action": "connect-canva", "result": result})
                    return

                if self.path == "/api/check-canva-auth":
                    from canva_oauth import canva_auth_status
                    result = canva_auth_status()
                    self._send_json({"ok": True, "action": "check-canva-auth", "result": result})
                    return

                if self.path == "/api/refresh-canva-token":
                    from canva_oauth import refresh_canva_token
                    result = refresh_canva_token()
                    self._send_json({"ok": True, "action": "refresh-canva-token", "result": result})
                    return

                self._send_json({"ok": False, "error": f"Unknown API path: {self.path}"}, status=404)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main() -> int:
    print_header()

    try:
        install_requirements()
        run_step("STEP 1 — Scrape sources", "scrape_sources.py")
        run_step("STEP 2 — Collect GDELT discovery sources", "collect_gdelt_sources.py")
        run_step("STEP 3 — Collect Guardian API sources if key exists", "collect_guardian_sources.py")
        run_step("STEP 4 — Collect NewsAPI sources if key exists", "collect_newsapi_sources.py")
        run_step("STEP 5 — Collect Mediastack sources if key exists", "collect_mediastack_sources.py")
        run_step("STEP 6 — Generate initial candidates", "generate_post_candidates.py")
        run_step("STEP 7 — Extract article/research context", "extract_research.py")
        run_step("STEP 8 — Regenerate candidates with API/reliable source layer", "generate_post_candidates.py")
        run_step("STEP 9 — Collect free public API sources: HN, World Bank, Wikipedia", "collect_public_api_sources_v25.py")
        run_step("STEP 10 — Enrich candidates with category lanes + dynamic slide counts", "enrich_candidates_v25.py")
        run_step("STEP 11 — Save today source/research cache", "daily_cache_manager.py save-today")

        port = find_open_port(8000)
        server = start_server(port)
        url = f"http://localhost:{port}/console.html"

        print("\n" + "=" * 64)
        print("READY")
        print("=" * 64)
        print(f"Console: {url}")
        print("Opening localhost app in Brave now...")
        print("\nKeep this window open while using the site.")
        print("Press CTRL+C here when you are done.")
        print("=" * 64 + "\n")

        open_url(url)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping server...")
            server.shutdown()
            print("Done.")
            return 0

    except subprocess.CalledProcessError as exc:
        print("\nA command failed.")
        print(f"Exit code: {exc.returncode}")
        print("Check the error above, fix it, then run START_HERE.bat again.")
        return exc.returncode or 1
    except Exception as exc:
        print("\nRunner failed:")
        print(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
