from __future__ import annotations

import time
from pathlib import Path

from run_unblurbrief_os import find_open_port, open_url, start_server


ROOT = Path(__file__).resolve().parent
CANDIDATES_FILE = ROOT / "output" / "top_post_candidates.json"


def main() -> int:
    print("\n" + "=" * 64)
    print("UNBLURBRIEF CONTENT OS — OPEN EXISTING SESSION")
    print("=" * 64)
    print("This launcher skips scraping, API collection, research extraction,")
    print("and candidate regeneration.")
    print("")
    print("It only starts the localhost app and opens console.html.")
    print("=" * 64 + "\n")

    if not CANDIDATES_FILE.exists():
        print("WARNING:")
        print(f"Could not find existing candidates file:")
        print(f"{CANDIDATES_FILE}")
        print("")
        print("The app will still open, but Load candidates may fail.")
        print("Run START_HERE.bat once if you need to generate candidates.")
        print("")

    port = find_open_port(8000)
    server = start_server(port)
    url = f"http://localhost:{port}/console.html"

    print("\n" + "=" * 64)
    print("READY — EXISTING SESSION")
    print("=" * 64)
    print(f"Console: {url}")
    print("Opening localhost app in Brave/profile from workflow_config.json...")
    print("")
    print("No APIs are being called by this launcher.")
    print("Keep this window open while using the site.")
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


if __name__ == "__main__":
    raise SystemExit(main())
