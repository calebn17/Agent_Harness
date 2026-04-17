"""harness init — scaffold harness in a project from a template."""

import shutil
import stat
import subprocess
from pathlib import Path

from scripts.common import HARNESS_DIR, PROJECT_ROOT
from scripts.sync_map import scan_full

TEMPLATES_DIR = HARNESS_DIR / "templates"

# Agent config files and the line to inject
AGENT_CONFIGS = {
    "CLAUDE.md": "Read .agent-harness/context/bootstrap.md for project context before each task.",
    ".cursorrules": "Read .agent-harness/context/bootstrap.md for project context before each task.",
    "AGENTS.md": "Read .agent-harness/context/bootstrap.md for project context before each task.",
}

POST_COMMIT_HOOK = """\
# Agent Harness: incremental codebase map update
ROOT=$(git rev-parse --show-toplevel)
changed_dirs=$(git diff-tree --no-commit-id --name-only -r HEAD | cut -d/ -f1 | sort -u | tr '\\n' ' ')
if [ -n "$changed_dirs" ]; then
  cd "$ROOT"
  PYTHONPATH="$ROOT/.agent-harness" python3 .agent-harness/scripts/sync_map.py --only $changed_dirs
fi
"""

POST_MERGE_HOOK = """\
# Agent Harness: incremental codebase map update on merge
ROOT=$(git rev-parse --show-toplevel)
changed_dirs=$(git diff-tree --no-commit-id --name-only -r HEAD@{1} HEAD | cut -d/ -f1 | sort -u | tr '\\n' ' ')
if [ -n "$changed_dirs" ]; then
  cd "$ROOT"
  PYTHONPATH="$ROOT/.agent-harness" python3 .agent-harness/scripts/sync_map.py --only $changed_dirs
fi
"""

POST_CHECKOUT_HOOK = """\
# Agent Harness: staleness check after branch switch
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
PYTHONPATH="$ROOT/.agent-harness" python3 .agent-harness/scripts/sync_map.py --staleness-check
"""


def _install_git_hook(hook_name: str, content: str):
    hooks_dir = PROJECT_ROOT / ".git" / "hooks"
    if not hooks_dir.exists():
        print(f"  Warning: .git/hooks not found, skipping {hook_name} hook")
        return
    hook_path = hooks_dir / hook_name
    # Append to existing hook or create new
    if hook_path.exists():
        existing = hook_path.read_text()
        if "Agent Harness" in existing:
            return  # already installed
        hook_path.write_text(existing.rstrip() + "\n\n" + content)
    else:
        hook_path.write_text("#!/bin/bash\n" + content)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)
    print(f"  Installed {hook_name} hook")


def _wire_agent_config(config_file: str, line: str):
    path = PROJECT_ROOT / config_file
    if path.exists():
        content = path.read_text()
        if "bootstrap.md" in content:
            return  # already wired
        path.write_text(content + f"\n\n{line}\n")
        print(f"  Updated {config_file}")
    else:
        path.write_text(f"{line}\n")
        print(f"  Created {config_file}")


def init_project(project_type: str = "python"):
    template_dir = TEMPLATES_DIR / project_type
    if not template_dir.exists():
        print(f"Template '{project_type}' not found. Available: {[t.name for t in TEMPLATES_DIR.iterdir() if t.is_dir()]}")
        return

    print(f"Initializing harness for {project_type} project...")

    # 1. Create directory structure
    dirs = [
        HARNESS_DIR / "context" / "detail",
        HARNESS_DIR / "memory" / "entries",
        HARNESS_DIR / "rules",
        HARNESS_DIR / "logs",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print("  Created directory structure")

    # 2. Copy template files
    # conventions.yaml → rules/conventions.yaml; config.yaml → config.yaml
    for template_file in template_dir.iterdir():
        if template_file.name == "conventions.yaml":
            dest = HARNESS_DIR / "rules" / "conventions.yaml"
        else:
            dest = HARNESS_DIR / template_file.name
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(template_file, dest)
            print(f"  Copied {template_file.name} → {dest.relative_to(HARNESS_DIR)}")
        else:
            print(f"  Skipped {template_file.name} (already exists)")

    # 3. Full codebase map scan
    print("  Running initial codebase map scan...")
    scan_full()

    # 4. Install git hooks
    _install_git_hook("post-commit", POST_COMMIT_HOOK)
    _install_git_hook("post-merge", POST_MERGE_HOOK)
    _install_git_hook("post-checkout", POST_CHECKOUT_HOOK)

    # 5. Generate first bootstrap
    from scripts.gen_bootstrap import generate_bootstrap
    generate_bootstrap(role="coder")

    # 6. Auto-wire agent config files
    for config_file, line in AGENT_CONFIGS.items():
        _wire_agent_config(config_file, line)

    print(f"\nHarness initialized for {project_type}.")
    print("Run 'harness prep --role <role>' before each session.")
    print("Roles: planner (Opus), coder (Sonnet/Composer2), reviewer (Codex)")
