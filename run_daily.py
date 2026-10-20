"""Daily job: fetch and write new stories, then rebuild public/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import build_site  # noqa: E402
import fetch_news  # noqa: E402

if __name__ == "__main__":
    fetch_news.main()  # exits non-zero on a bad key or retired model, so nothing gets deployed
    build_site.main()
