"""harness map commands."""

from pathlib import Path
from scripts.common import HARNESS_DIR, load_config
from scripts.sync_map import scan_full

DETAIL_DIR = HARNESS_DIR / "context" / "detail"


def map_drill(module: str):
    cfg = load_config()
    cap = cfg.get("budgets", {}).get("map_drill_chars", 1600)

    # Normalize: strip leading ./ or /
    module = module.strip("/").lstrip("./")
    # Try exact match first, then prefix match
    candidates = list(DETAIL_DIR.glob(f"map-{module.replace('/', '-')}*.md"))
    candidates = [c for c in candidates if c.name != "map-root.md"]

    if not candidates:
        print(f"No map found for '{module}'. Try: harness map rebuild")
        return

    content = candidates[0].read_text()
    if len(content) > cap:
        content = content[:cap] + f"\n[truncated — {len(content) - cap} chars omitted]"
    print(content)


def map_rebuild():
    scan_full()
    print("Map rebuilt.")
