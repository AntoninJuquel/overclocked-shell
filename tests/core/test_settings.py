import pytest

from shell.core.settings import SettingsError, load_settings

VARS = ("BUNGIE_API_KEY", "BUNGIE_CLIENT_ID", "BUNGIE_CLIENT_SECRET", "BUNGIE_REDIRECT_URL", "SHELL_LANGUAGE")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in VARS:
        monkeypatch.delenv(k, raising=False)


def test_loads_from_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text("BUNGIE_API_KEY=k\nBUNGIE_CLIENT_ID=1\nBUNGIE_CLIENT_SECRET=s\n")
    s = load_settings(env)
    assert (s.api_key, s.client_id, s.client_secret) == ("k", "1", "s")
    assert s.redirect_url == "https://localhost:7777/callback"
    assert s.language == "en"


def test_language_from_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text("BUNGIE_API_KEY=k\nBUNGIE_CLIENT_ID=1\nBUNGIE_CLIENT_SECRET=s\nSHELL_LANGUAGE= FR \n")
    assert load_settings(env).language == "fr"


def test_environment_wins_over_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("BUNGIE_API_KEY=k\nBUNGIE_CLIENT_ID=1\nBUNGIE_CLIENT_SECRET=s\n")
    monkeypatch.setenv("BUNGIE_API_KEY", "from-env")
    assert load_settings(env).api_key == "from-env"


def test_missing_values_are_named(tmp_path):
    env = tmp_path / ".env"
    env.write_text("BUNGIE_API_KEY=k\n")
    with pytest.raises(SettingsError) as e:
        load_settings(env)
    assert "BUNGIE_CLIENT_ID" in str(e.value) and "BUNGIE_CLIENT_SECRET" in str(e.value)
    assert str(env) in str(e.value)


def test_missing_file_is_named(tmp_path):
    env = tmp_path / ".env"
    with pytest.raises(SettingsError, match="BUNGIE_API_KEY"):
        load_settings(env)
