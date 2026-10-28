import json

import pytest

from shell.engines.builds.snapshot import read_snapshot


def test_reads_rows_and_time(isolated_dirs):
    folder = isolated_dirs / "profile" / "inventory"
    folder.mkdir(parents=True)
    (folder / "armor.json").write_text(json.dumps([{"itemId": "1"}]), encoding="utf-8")
    rows, taken = read_snapshot("armor")
    assert rows == [{"itemId": "1"}] and taken[:4].isdigit() and "T" in taken


def test_missing_snapshot_asks_for_refresh():
    with pytest.raises(FileNotFoundError, match="Call refresh_inventory first"):
        read_snapshot("weapons")
