"""Bungie app settings from the install-root .env; real environment variables win."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from shell.core import paths

DEFAULT_REDIRECT = "https://localhost:7777/callback"
REQUIRED = ("BUNGIE_API_KEY", "BUNGIE_CLIENT_ID", "BUNGIE_CLIENT_SECRET")


class SettingsError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    api_key: str
    client_id: str
    client_secret: str
    redirect_url: str
    language: str = "en"  # Bungie manifest language for names shown to the player (en, fr, de, es, es-mx, it, ja, ko, pl, pt-br, ru, zh-chs, zh-cht)


def load_settings(env_file: Path | None = None) -> Settings:
    env_file = env_file or paths.env_file()
    values = {**(dotenv_values(env_file) if env_file.exists() else {}), **os.environ}
    missing = [k for k in REQUIRED if not values.get(k)]
    if missing:
        raise SettingsError(f"Missing {', '.join(missing)} in {env_file} (see .env.example).")
    return Settings(
        api_key=values["BUNGIE_API_KEY"],
        client_id=values["BUNGIE_CLIENT_ID"],
        client_secret=values["BUNGIE_CLIENT_SECRET"],
        redirect_url=values.get("BUNGIE_REDIRECT_URL") or DEFAULT_REDIRECT,
        language=(values.get("SHELL_LANGUAGE") or "en").strip().lower(),
    )
