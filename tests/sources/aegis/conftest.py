import json

import pytest


@pytest.fixture(autouse=True)
def isolated_aegis_dir(tmp_path, monkeypatch):
    """Tests never read the real cache/aegis/: they write their data in tmp_path/cache/aegis."""
    from shell.sources.aegis import lookup
    monkeypatch.setattr(lookup, "DATA", tmp_path / "cache" / "aegis")
    monkeypatch.setattr(lookup, "_warned", False)
    return tmp_path / "cache" / "aegis"


def write_aegis(data_dir, sheet, slug, rows, tab=None):
    """Writes <aegis dir>/<sheet>/<slug>.json with these rows (each row must have `_name`)."""
    path = data_dir / sheet / f"{slug}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"sheet": sheet, "tab": tab or slug, "updated": None, "fetched": "2026-10-09", "hidden_rows": 0,
           "columns": [], "groups": {}, "legend": {}, "rows": [{"_section": "", **r} for r in rows]}
    path.write_text(json.dumps(doc), encoding="utf-8")
