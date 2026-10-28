import copy
import json

import pytest

from shell.engines import raids

GUIDES = {"grindout", "shacknews", "overgear"}
ENC = {
    "raid": "deep-stone-crypt", "encounter": "crypt-security", "name": "Crypt Security",
    "sources": [{"guide": "grindout", "updated": "2026-07-20"}, {"guide": "shacknews", "updated": "2026-02-01"}],
    "floors": [{"id": "upper", "name": "Upstairs", "rooms": [{"id": "hall", "name": "Hall", "x": 0, "y": 0,
                                                               "w": 100, "h": 100}]},
               {"id": "basement", "name": "Basement", "rooms": []}],
    "spots": [{"id": "terminal", "name": "Augment terminal", "kind": "terminal", "floor": "upper", "room": "hall",
               "pos": [20, 50], "pos_source": "shacknews image 3", "sources": ["shacknews"]},
              {"id": "panel-l1", "name": "Panel 1 (left)", "kind": "panel", "floor": "basement", "pos": None,
               "pos_source": None, "sources": ["shacknews"]}],
    "roles": [{"id": "scanner", "name": "Scanner", "count": 1}, {"id": "operator", "name": "Operator", "count": 1},
              {"id": "adds", "name": "Add clear", "count": 4}],
    "phases": [{"id": "panels", "name": "Panels", "summary": "Shoot the called panels.",
                "steps": {"scanner": ["Call the lit panels."], "operator": ["Shoot them."]},
                "spots": ["terminal", "panel-l1"], "sources": ["grindout"]}],
    "conflicts": ["Shacknews numbers 5 panels per side; Grindout does not number them."], "gaps": [],
}


def bad(**changes):
    enc = copy.deepcopy(ENC)
    for path, value in changes.items():
        target = enc
        *keys, last = path.split("__")
        for k in keys:
            target = target[int(k)] if k.isdigit() else target[k]
        if value is KeyError:
            del target[last if not last.isdigit() else int(last)]
        else:
            target[int(last) if last.isdigit() else last] = value
    return raids.check(enc, GUIDES)


def test_valid_encounter():
    assert raids.check(ENC, GUIDES) == []


@pytest.mark.parametrize("changes,problem", [
    ({"phases": KeyError}, "missing key: phases"),
    ({"phases": []}, "phases: none"),
    ({"spots__1__id": "terminal"}, "duplicate spot id: terminal"),
    ({"roles__2__count": 3}, "roles: counts sum to 5, not 6"),
    ({"phases__0__steps__suppressor": ["x"]}, "phase panels: steps for unknown role suppressor"),
    ({"phases__0__spots": ["nope"]}, "phase panels: unknown spot nope"),
    ({"spots__0__floor": "attic"}, "spot terminal: unknown floor attic"),
    ({"spots__0__room": "vault"}, "spot terminal: unknown room vault"),
    ({"spots__1__pos": [10, 10]}, "spot panel-l1: position without pos_source"),
    ({"spots__0__pos": [120, 10]}, "spot terminal: position out of 0-100"),
    ({"spots__0__kind": "pillar?"}, "spot terminal: unknown kind pillar?"),
    ({"spots__0__sources": []}, "spot terminal: no source"),
    ({"phases__0__sources": ["reddit"]}, "phase panels: unknown guide reddit"),
    ({"sources__0__guide": "reddit"}, "sources: unknown guide reddit"),
])
def test_rules(changes, problem):
    assert problem in bad(**changes)


def test_names_apply_renames():
    assert raids.names(ENC, {"panel-l1": "left 1", "gone": "x"}) == {"terminal": "Augment terminal",
                                                                      "panel-l1": "left 1"}


@pytest.fixture
def profile(tmp_path, monkeypatch):
    from shell.core import paths
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    return tmp_path / "profile"


def test_load_and_slugs(profile):
    with pytest.raises(FileNotFoundError, match="raid-companion"):
        raids.load("deep-stone-crypt", "crypt-security")
    with pytest.raises(ValueError, match="slug"):
        raids.load("../secrets", "x")
    raids.folder("deep-stone-crypt").mkdir(parents=True)
    (raids.folder("deep-stone-crypt") / "crypt-security.json").write_text(json.dumps(ENC), encoding="utf-8")
    assert raids.load("deep-stone-crypt", "crypt-security")["name"] == "Crypt Security"
    assert raids.encounters("deep-stone-crypt") == ["crypt-security"]


def test_renames_round_trip_and_orphans(profile):
    raids.folder("deep-stone-crypt").mkdir(parents=True)
    (raids.folder("deep-stone-crypt") / "crypt-security.json").write_text(json.dumps(ENC), encoding="utf-8")
    assert raids.save_rename("deep-stone-crypt", "panel-l1", "left 1") == {"panel-l1": "left 1"}
    raids.save_rename("deep-stone-crypt", "gone", "x")
    assert raids.load_renames("deep-stone-crypt") == {"panel-l1": "left 1", "gone": "x"}
    assert raids.orphan_renames("deep-stone-crypt") == ["rename for unknown spot gone ignored"]
    assert raids.save_rename("deep-stone-crypt", "gone", None) == {"panel-l1": "left 1"}
