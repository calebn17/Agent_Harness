"""Incremental codebase map generator.

Scans directory structure and generates:
- context/detail/map-root.md  (top-level, inlined in bootstrap)
- context/detail/map-<path>.md  (per-module detail, served on demand)

Run modes:
  sync_map.py              → full scan
  sync_map.py --only dir1 dir2  → incremental: only rescan listed dirs
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Self-bootstrap when run directly (e.g., from git hooks)
_scripts_dir = Path(__file__).parent.resolve()
_harness_dir = _scripts_dir.parent
if str(_harness_dir) not in sys.path:
    sys.path.insert(0, str(_harness_dir))

from scripts.common import HARNESS_DIR, PROJECT_ROOT, load_config

DETAIL_DIR = HARNESS_DIR / "context" / "detail"
IGNORE_DIRS = {
    ".git",
    ".agent-harness",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    ".next",
    ".nuxt",
    "DerivedData",
    "*.xcworkspace",
}


def _should_ignore(path: Path) -> bool:
    return path.name in IGNORE_DIRS or path.name.startswith(".")


def _count_files(directory: Path, extensions: Optional[set] = None) -> int:
    count = 0
    for f in directory.rglob("*"):
        if f.is_file():
            if extensions is None or f.suffix in extensions:
                count += 1
    return count


def _summarize_directory(directory: Path, depth: int = 0) -> str:
    """Generate a one-line summary for a directory."""
    name = directory.name
    file_count = _count_files(directory)
    # Try to detect primary language
    py_count = _count_files(directory, {".py"})
    ts_count = _count_files(directory, {".ts", ".tsx"})
    swift_count = _count_files(directory, {".swift"})
    js_count = _count_files(directory, {".js", ".jsx"})

    lang = ""
    if py_count > ts_count and py_count > swift_count:
        lang = "Python"
    elif ts_count > py_count and ts_count > swift_count:
        lang = "TypeScript"
    elif swift_count > 0:
        lang = "Swift"
    elif js_count > 0:
        lang = "JavaScript"

    lang_str = f" [{lang}]" if lang else ""
    return f"{name}/{lang_str} — {file_count} files"


def _generate_module_detail(directory: Path) -> str:
    """Generate detailed map for a single module directory."""
    lines = [f"# {directory.relative_to(PROJECT_ROOT)}\n"]

    # List immediate children with types
    children = sorted(directory.iterdir())
    files = [c for c in children if c.is_file()]
    subdirs = [c for c in children if c.is_dir() and not _should_ignore(c)]

    if subdirs:
        lines.append("## Subdirectories")
        for d in subdirs:
            lines.append(f"- {d.name}/ — {_count_files(d)} files")
        lines.append("")

    if files:
        lines.append("## Files")
        for f in files[:20]:  # cap at 20 files
            lines.append(f"- {f.name}")
        if len(files) > 20:
            lines.append(f"- ... and {len(files) - 20} more")
        lines.append("")

    return "\n".join(lines)


def _path_to_detail_name(path: Path) -> str:
    rel = path.relative_to(PROJECT_ROOT)
    return "map-" + str(rel).replace("/", "-").replace("\\", "-") + ".md"


def scan_full():
    """Full scan of the project tree."""
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)

    # Top-level modules (immediate children of project root)
    top_dirs = [
        d
        for d in sorted(PROJECT_ROOT.iterdir())
        if d.is_dir() and not _should_ignore(d)
    ]

    root_lines = []
    for d in top_dirs:
        root_lines.append(f"- {_summarize_directory(d)}")
        # Generate detail file
        detail_content = _generate_module_detail(d)
        detail_file = DETAIL_DIR / _path_to_detail_name(d)
        detail_file.write_text(detail_content)

    root_map = DETAIL_DIR / "map-root.md"
    root_map.write_text("\n".join(root_lines))
    print(f"Map generated: {len(top_dirs)} top-level modules")


def scan_incremental(dirs: list):
    """Rescan only the listed directories."""
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    updated = []

    for dir_path_str in dirs:
        d = PROJECT_ROOT / dir_path_str
        if not d.exists() or not d.is_dir():
            # Module deleted — remove detail file
            for detail_file in DETAIL_DIR.glob(
                f"map-{dir_path_str.replace('/', '-')}*.md"
            ):
                detail_file.unlink()
                print(f"Removed stale map: {detail_file.name}")
            continue

        detail_content = _generate_module_detail(d)
        detail_file = DETAIL_DIR / _path_to_detail_name(d)
        detail_file.write_text(detail_content)
        updated.append(d.name)

    # Regenerate root map
    root_lines = []
    for detail_file in sorted(DETAIL_DIR.glob("map-*.md")):
        if detail_file.name == "map-root.md":
            continue
        # Read first non-empty line for summary
        content = detail_file.read_text()
        first_line = next((l for l in content.splitlines() if l.strip()), "")
        root_lines.append(first_line.lstrip("# "))

    root_map = DETAIL_DIR / "map-root.md"
    root_map.write_text("\n".join(root_lines))
    print(f"Map updated: {updated}")


def check_staleness():
    """Post-checkout: detect deleted modules, remove stale entries."""
    if not DETAIL_DIR.exists():
        return
    for detail_file in DETAIL_DIR.glob("map-*.md"):
        if detail_file.name == "map-root.md":
            continue
        # Reconstruct path from filename
        rel_path = detail_file.stem.replace("map-", "").replace("-", "/", 1)
        actual = PROJECT_ROOT / rel_path
        if not actual.exists():
            detail_file.unlink()
            print(f"Removed stale map entry: {detail_file.name} (module deleted)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="+", help="Directories to rescan")
    parser.add_argument("--staleness-check", action="store_true")
    args = parser.parse_args()

    if args.staleness_check:
        check_staleness()
    elif args.only:
        scan_incremental(args.only)
    else:
        scan_full()


if __name__ == "__main__":
    main()
