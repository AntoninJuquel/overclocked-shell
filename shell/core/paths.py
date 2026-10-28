"""Install-root paths: never depend on the launch folder (CLI or MCP server)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def profile_dir() -> Path:
    return ROOT / "profile"


def cache_dir() -> Path:
    return ROOT / "cache"


def env_file() -> Path:
    return ROOT / ".env"
