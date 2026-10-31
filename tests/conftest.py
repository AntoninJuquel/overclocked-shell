import pytest


@pytest.fixture(autouse=True)
def english_outputs(monkeypatch):
    """Tests render in English whatever SHELL_LANGUAGE the install's .env sets (the environment wins over it)."""
    monkeypatch.setenv("SHELL_LANGUAGE", "en")
