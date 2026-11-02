from shell.core import paths
from shell.engines import lexicon
from shell.outputs import build_md


class FakeManifest:
    def __init__(self, tables, version="v1"):
        self.tables, self._version = tables, version

    def table(self, name, keep=True):
        return self.tables.get(name, {})

    def version(self):
        return self._version


def item(name, type_name=None):
    return {"displayProperties": {"name": name}, **({"itemTypeDisplayName": type_name} if type_name else {})}


EN = FakeManifest({"DestinyInventoryItemDefinition": {
    "1": item("Hood of the Great Hunt", "Helmet"), "2": item("Storm Grenade"), "3": item("DECATUR 02", "Auto Rifle"),
    "4": item("Rapid Hit"), "5": item("Rapid Hit"), "6": item("Rapid Hit")},
    "DestinyStatDefinition": {"9": item("Grenade")}})
FR = FakeManifest({"DestinyInventoryItemDefinition": {
    "1": item("Capuche de la Grande Chasse", "Casque"), "2": item("Grenade orageuse"),
    "3": item("DECATUR 02", "Fusil automatique"), "4": item("Coup rapide"), "5": item("Coup rapide"),
    "6": item("Tir rapide")},
    "DestinyStatDefinition": {"9": item("Grenade")}})


def test_build_matches_by_hash_and_keeps_most_frequent():
    terms = lexicon.build(EN, FR)
    assert terms == {"Hood of the Great Hunt": "Capuche de la Grande Chasse", "Helmet": "Casque",
                     "Storm Grenade": "Grenade orageuse", "Auto Rifle": "Fusil automatique",
                     "Rapid Hit": "Coup rapide"}   # same names (DECATUR 02, Grenade) left out


def test_translator_whole_words_longest_first_and_caps():
    tr = lexicon.translator({"Great Hunt": "Grande Chasse", "Hood of the Great Hunt": "Capuche de la Grande Chasse",
                             "Arc Soul": "Âme d'arc", "Arc": "Arc"})
    assert tr("Tenir la Hood of the Great Hunt, l'Arc Soul et Great Hunt") == \
        "Tenir la Capuche de la Grande Chasse, l'Âme d'arc et Grande Chasse"
    assert tr("ARMOR SET BONUS · GREAT HUNT") == "ARMOR SET BONUS · GRANDE CHASSE"
    assert tr("Great Hunter") == "Great Hunter"   # not a whole word
    assert lexicon.translator({})("Great Hunt") == "Great Hunt"


def test_translator_edges():
    tr = lexicon.translator({"Arc": "Arc FR", "Arc Soul": "Âme", "Soul": "Âme seule", "+Grenade": "+Grenade FR"})
    assert tr("_Arc_ Arc1 2Arc Arc") == "_Arc FR_ Arc1 2Arc Arc FR"   # _ does not bound a name (md italics), digits do
    assert tr("Arc Souls") == "Arc FR Souls"   # the longest name fails its bound: the shorter one still applies
    assert tr("Arc Soul Soul") == "Âme Âme seule"
    assert tr("+Grenade") == "+Grenade FR"
    assert tr("") == "" and tr(None) is None
    assert tr("Arc\nSoul") == "Arc FR\nÂme seule"


def test_translator_same_as_a_regex_of_every_name():
    import random
    import re
    terms = {"Arc": "A", "Arc Soul": "B", "Soul": "C", "Soul of Arc": "D", "Ré": "E", "x-y": "F"}
    full = {**{k.upper(): v.upper() for k, v in terms.items()}, **terms}
    names = "|".join(map(re.escape, sorted(full, key=len, reverse=True)))
    pattern = re.compile(rf"(?<![^\W_])(?:{names})(?![^\W_])")
    tr = lexicon.translator(terms)
    rng = random.Random(1)
    pieces = [*full, " ", "_", "1", "é", "of", ",", "\n", "x", "-"]
    for _ in range(2000):
        text = "".join(rng.choice(pieces) for _ in range(rng.randint(1, 8)))
        assert tr(text) == pattern.sub(lambda m: full[m.group(0)], text), text


def test_load_caches_per_language_and_version(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(lexicon, "build", lambda en, local: {"Helmet": "Casque"})
    monkeypatch.setattr("shell.core.manifest.Manifest", lambda *a, **k: None)
    EN.client, EN.root = None, tmp_path / "manifest"
    terms = lexicon.load(EN, "fr")
    assert terms["Helmet"] == "Casque" and terms["Subclass"] == "Sous-classe"   # manifest + labels
    monkeypatch.setattr(lexicon, "build", lambda en, local: 1 / 0)               # cached: not rebuilt
    assert lexicon.load(EN, "fr") == terms == lexicon.cached()
    assert lexicon.current()("Helmet") == "Casque"
    assert lexicon.load(EN, "en") == {} == lexicon.cached()
    assert lexicon.current()("Helmet") == "Helmet"


def test_lookup_reports_unchanged():
    assert lexicon.lookup({"Storm Grenade": "Grenade orageuse"}, ["storm grenade", "DECATUR 02"]) == \
        ({"storm grenade": "Grenade orageuse"}, ["DECATUR 02"])


def test_md_view_in_french():
    s = {"name": "Getaway Buddy", "class": "Warlock", "subclass": {"element": "Prismatic", "super": "Song of Flame",
         "abilities": {"grenade": "Storm Grenade"}}, "intent": {"exotic": {"name": "Getaway Artist"}}}
    md = build_md.render(s, "x.json", tr=lexicon.translator({**lexicon.labels("fr"), "Storm Grenade": "Grenade orageuse"}))
    assert "## Sous-classe" in md and "- Élément: Prismatique" in md and "- grenade: Grenade orageuse" in md
    assert "## Intention" in md and "Vue générée depuis x.json" in md
