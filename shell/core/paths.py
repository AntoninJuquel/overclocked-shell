"""Install-root paths: the MCP server may be launched from any folder (user-scope registration)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def profile_dir() -> Path:
    return ROOT / "profile"


def cache_dir() -> Path:
    return ROOT / "cache"


def env_file() -> Path:
    return ROOT / ".env"
