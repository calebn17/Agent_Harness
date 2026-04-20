"""Shared utilities for harness scripts."""

import fcntl
import os
from pathlib import Path
from datetime import date
import yaml

HARNESS_DIR = Path(__file__).parent.parent.resolve()
PROJECT_ROOT = HARNESS_DIR.parent.parent
LOCK_FILE = HARNESS_DIR / ".lock"
CONFIG_FILE = HARNESS_DIR / "config.yaml"

_config_cache = None


def load_config() -> dict:
    global _config_cache
    if _config_cache is None:
        with open(CONFIG_FILE) as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


def acquire_lock():
    """Acquire exclusive flock on .lock. Returns open file descriptor — caller must close."""
    fd = open(LOCK_FILE, "w")
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def release_lock(fd):
    fcntl.flock(fd, fcntl.LOCK_UN)
    fd.close()


def today_str() -> str:
    return date.today().isoformat()


def load_memory_index() -> dict:
    index_path = HARNESS_DIR / "memory" / "index.yaml"
    if not index_path.exists():
        return {"entries": []}
    with open(index_path) as f:
        data = yaml.safe_load(f)
    return data or {"entries": []}


def save_memory_index(index: dict):
    index_path = HARNESS_DIR / "memory" / "index.yaml"
    with open(index_path, "w") as f:
        yaml.dump(index, f, default_flow_style=False, allow_unicode=True)
