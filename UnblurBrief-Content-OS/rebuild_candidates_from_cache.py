from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from daily_cache_manager import restore_cache

ROOT = Path(__file__).resolve().parent


def run_step(name: str, script: str) -> None:
    print("\n" + "-" * 64)
    print(name)
    print("-" * 64)
    subprocess.check_call([sys.executable, script], cwd=ROOT)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "today"

    try:
        if mode == "latest":
            restore_cache(latest=True)
        else:
            restore_cache()

        # No scrapers. No source APIs. No news pulls.
        run_step("STEP 1 — Generate candidates from cached sources", "generate_post_candidates.py")
        run_step("STEP 2 — Enrich cached candidates with classifier/scoring + dynamic slides", "enrich_candidates_v25.py")

        print("\nDONE")
        print("Rebuilt candidates from saved cache without pulling new data.")
        print("Now run OPEN_EXISTING_OS.bat to open the app.")
        return 0

    except subprocess.CalledProcessError as exc:
        print("\nA rebuild step failed.")
        print(f"Exit code: {exc.returncode}")
        return exc.returncode or 1
    except Exception as exc:
        print("\nCache rebuild failed:")
        print(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
