"""Farm needs: what each build sheet lacks to reach its intent, with the expected gain.

`run` writes profile/todo/needs.json, syncs profile/todo/state.json and regenerates the sheets' "To fetch"
section. `extra_needs` adds the Aegis Shopping List items the player is missing (build `aegis`, see shopping.py).
"""
import dataclasses
import itertools
from pathlib import Path

from shell.engines.builds import inventory, optimize, sheet as sheet_mod
from shell.engines.builds.inventory import Piece, base_stats
from shell.engines.builds.stats import ARCHETYPES, CAP, SLOTS, STATS, fragment_stats
from shell.engines.todo import shopping, state as state_mod

W_SETS, W_MINS, W_PRIO = 0.4, 0.3, 0.3   # weights of a build's score (sum = 1)
MIN_GAIN = 0.005                          # score gain under which a better piece is not a need
GAP_SCORE = {"weapon": 0.10, "catalyst": 0.10, "upgrade": 0.05}   # flat gain of the unquantified gaps
GAP_LABELS = {"weapon": "Weapon", "catalyst": "Catalyst", "upgrade": "Upgrade"}
VIRTUAL_ENERGY = 11
TIE_EPS = 1e-9                            # score difference under which two options are tied
AEGIS_KEEP = ("aegis/",)


@dataclasses.dataclass
class Ctx:
    slug: str      # sheet file name, without extension
    intent: dict
    frag: dict     # fragment stat bonuses
    costs: dict    # mod energy costs
    cls: str


def need_id(kind, *parts):
    return "/".join([kind, *("-" if x is None else str(x) for x in parts)])


def virtual_piece(slot, set_name, archetype, tertiary, cls):
    """Ideal tier 5 legendary piece, masterworked: 30 / 25 / 20 on primary / secondary / tertiary, 5 elsewhere.

    Without tuning (`tuned=None`), to be cautious: a real tier 5 piece has a tuning stat, which can add up to +5
    per piece. Gains computed with these pieces are therefore a lower bound."""
    primary, secondary = ARCHETYPES[archetype]
    if tertiary in (primary, secondary):
        raise ValueError(f"tertiary {tertiary} is already primary or secondary of {archetype}")
    stats = dict.fromkeys(STATS, 5)
    stats.update({primary: 30, secondary: 25, tertiary: 20})
    name = (f"{slot} {set_name or 'legendary'} {cls} — {archetype} ({primary}/{secondary}), "
            f"tertiary {tertiary}")
    return Piece(item_id=need_id("armor", cls, slot, set_name, archetype, tertiary), name=name, slot=slot,
                 tier=5, exotic=False, stats=stats, energy=VIRTUAL_ENERGY, tuned=None, set=set_name,
                 masterwork_todo=False, location=cls, locked=True)


def set_counts(combo):
    """{set: pieces} of the combination's legendaries."""
    out = {}
    for p in combo:
        if not p.exotic and p.set:
            out[p.set] = out.get(p.set, 0) + 1
    return out


def score(combo, res, intent):
    """Score between 0 and 1: intent sets reached, minimums reached, priority stats (weighted by rank, relative
    to the cap)."""
    st = intent.get("stats", {})
    mins, prio = st.get("minimums", {}), st.get("priority", [])
    req = {e["set"]: e["pieces"] for e in intent.get("sets", []) if e["pieces"] > 0}
    have = set_counts(combo)
    sets = sum(min(have.get(s, 0), n) for s, n in req.items()) / sum(req.values()) if req else 1.0
    total_min = sum(mins.values())
    minimums = min(max(1 - sum(res.deficit.values()) / total_min, 0.0), 1.0) if total_min else 1.0
    weights = list(range(len(prio), 0, -1))
    priorities = (sum(w * min(max(res.totals[s], 0), CAP) / CAP for w, s in zip(weights, prio)) / sum(weights)
                  if prio else 1.0)
    return W_SETS * sets + W_MINS * minimums + W_PRIO * priorities


def merge(needs):
    """One entry per id (sorted by id); the builds of duplicates are concatenated."""
    by_id = {}
    for n in needs:
        if n["id"] in by_id:
            by_id[n["id"]]["builds"].extend(n["builds"])
        else:
            by_id[n["id"]] = {**n, "builds": list(n["builds"])}
    return [by_id[i] for i in sorted(by_id)]


def _rate(combo, ctx):
    """(score, mods.Result) of a combination, or None if the utility mods do not fit."""
    res = optimize.evaluate(combo, ctx.frag, ctx.intent, ctx.costs, ctx.cls)
    return None if res is None else (score(combo, res, ctx.intent), res)


def _stat_diff(before, after):
    """Change of the effective stats (clamped to 0..200) between two results."""
    out = {}
    for s in STATS:
        d = min(max(after.totals[s], 0), CAP) - min(max(before.totals[s], 0), CAP)
        if d:
            out[s] = d
    return out


def _swap(combo, new_pieces):
    by_slot = {p.slot: p for p in new_pieces}
    return tuple(by_slot.get(p.slot, p) for p in combo)


def _options(slot, set_name, cls):
    """Every virtual piece of a slot: 12 archetypes × 4 tertiaries, deterministic order.
    List of (archetype, tertiary, piece)."""
    return [(arch, t, virtual_piece(slot, set_name, arch, t, cls))
            for arch, pair in sorted(ARCHETYPES.items()) for t in STATS if t not in pair]


def _rate_options(combo, slot, set_name, ctx, fixed=()):
    """Rates each virtual option of `slot` (with the `fixed` pieces in place). Returns
    (best rating (score, res) or None, piece of the best option, tied (archetypes, tertiaries))."""
    rated = []
    for arch, t, v in _options(slot, set_name, ctx.cls):
        r = _rate(_swap(combo, [*fixed, v]), ctx)
        if r is not None:
            rated.append((r, arch, t, v))
    if not rated:
        return None, None, None
    top = max(r[0] for r, *_ in rated)
    tied = [(r, arch, t, v) for r, arch, t, v in rated if r[0] >= top - TIE_EPS]
    return tied[0][0], tied[0][3], _tie_target(tied)


def _tie_target(tied):
    """(sorted archetypes, sorted tertiaries or None) of the tied options; None when every possible tertiary of
    the kept archetypes is tied."""
    archs = sorted({arch for _, arch, _, _ in tied})
    pairs = {(arch, t) for _, arch, t, _ in tied}
    every = all((arch, t) in pairs for arch in archs for t in STATS if t not in ARCHETYPES[arch])
    return archs, None if every else sorted({t for _, _, t, _ in tied})


def _armor_need(slot, set_name, ties, ctx, gain, stats, effects):
    archs, terts = ties
    label = (f"{slot} {set_name or 'legendary'} {ctx.cls} — {' or '.join(archs)}, "
             f"tertiary {' or '.join(terts) if terts else 'any'}")
    return {"id": need_id("armor", ctx.cls, slot, set_name, "+".join(archs), "+".join(terts) if terts else "*"),
            "kind": "armor", "label": label,
            "target": {"class": ctx.cls, "slot": slot, "set": set_name, "archetypes": archs, "tertiaries": terts},
            "builds": [{"build": ctx.slug,
                        "gain": {"stats": stats, "effects": effects, "score": round(gain, 4)}}]}


def _kept_set(piece, combo, intent):
    """The piece's set if the intent asks for it and removing the piece would break the set, else None."""
    req = {e["set"]: e["pieces"] for e in intent.get("sets", [])}
    if piece.set in req and set_counts(combo).get(piece.set, 0) <= req[piece.set]:
        return piece.set
    return None


def slot_upgrades(combo, ctx):
    """Per legendary slot: the best virtual piece (of the current piece's set if the intent needs it), if it
    gains at least MIN_GAIN. Tied options are all listed in the target."""
    base = _rate(combo, ctx)
    if base is None:
        return []
    out = []
    for cur in combo:
        if cur.exotic:
            continue
        set_name = _kept_set(cur, combo, ctx.intent)
        r, _, ties = _rate_options(combo, cur.slot, set_name, ctx)
        if r and r[0] - base[0] >= MIN_GAIN:
            out.append(_armor_need(cur.slot, set_name, ties, ctx, r[0] - base[0], _stat_diff(base[1], r[1]), []))
    return out


def _best_virtual_set(combo, slots, set_name, ctx):
    """Virtual pieces of the set on `slots`: coordinate ascent (each slot takes its best option, the others
    fixed), two passes. Returns ((score, res) or None, {slot: piece})."""
    current = {s: _options(s, set_name, ctx.cls)[0][2] for s in slots}
    best = _rate(_swap(combo, current.values()), ctx)
    for _ in range(2):
        for s in slots:
            for _a, _t, v in _options(s, set_name, ctx.cls):
                trial = {**current, s: v}
                r = _rate(_swap(combo, trial.values()), ctx)
                if r and (best is None or r[0] > best[0]):
                    best, current = r, trial
    return best, current


def _lot_ties(combo, pieces, set_name, ctx):
    """{slot: tied (archetypes, tertiaries)} for each piece of the lot, the others fixed."""
    out = {}
    for slot in pieces:
        others = [v for s, v in pieces.items() if s != slot]
        out[slot] = _rate_options(combo, slot, set_name, ctx, fixed=others)[2]
    return out


def set_needs(combo, ctx, set_slots, set_bonus):
    """Virtual pieces that complete the intent sets missing from the combination.

    `set_slots`: {set: {slots that exist for the class}}; `set_bonus`: {set: ["2 pieces: …"]}.
    Sets are handled one after the other: the lot kept for a set is applied to the combination, which is the base
    for the next set, and its slots are no longer available.
    Returns (needs, warnings). A lot of k pieces gives k needs, each with the lot's gain / k."""
    base = _rate(combo, ctx)
    if base is None:
        return [], [f"{ctx.slug}: utility mods impossible on the combination, set needs not generated"]
    out, warnings, taken = [], [], set()
    for entry in ctx.intent.get("sets", []):
        name = entry["set"]
        have = set_counts(combo).get(name, 0)
        k = entry["pieces"] - have
        if k <= 0:
            continue
        slots = [p.slot for p in combo if not p.exotic and p.set != name and p.slot not in taken
                 and p.slot in set_slots.get(name, set())]
        if len(slots) < k:
            warnings.append(f"{ctx.slug}: set {name}: {len(slots)} slot(s) available for {ctx.cls} out of {k} "
                            "needed, need not generated")
            continue
        best = None
        for chosen in itertools.combinations(slots, k):
            r, pieces = _best_virtual_set(combo, chosen, name, ctx)
            if r and (best is None or r[0] > best[0][0]):
                best = (r, pieces)
        if best is None:
            warnings.append(f"{ctx.slug}: set {name}: utility mods impossible with the virtual pieces")
            continue
        gain = best[0][0] - base[0]
        if gain < MIN_GAIN:
            warnings.append(f"{ctx.slug}: set {name}: completing it only gains {gain:+.4f} score "
                            f"(minimum {MIN_GAIN}), need not generated")
            continue
        diff = _stat_diff(base[1], best[0][1])
        bonus = [f"{name} — {b}" for b in set_bonus.get(name, []) if have < int(b.split()[0]) <= entry["pieces"]]
        ties = _lot_ties(combo, best[1], name, ctx)
        lot = {slot: _armor_need(slot, name, ties[slot], ctx, gain / k, diff, []) for slot in best[1]}
        for slot, n in lot.items():
            others = [o["label"] for s, o in lot.items() if s != slot]
            n["builds"][0]["gain"]["effects"] = bonus + (
                [f"lot of {k} pieces, with: {', '.join(others)}"] if others else [])
            out.append(n)
        combo, base = _swap(combo, best[1].values()), best[0]
        taken |= set(best[1])
    return out, warnings


def masterwork_needs(combo, items_by_id, ctx):
    """One need per piece of the combination whose masterwork is to do (tier >= 1, in the snapshot);
    gain = current combination (projected masterwork) against the same piece without masterwork."""
    base = _rate(combo, ctx)
    if base is None:
        return []
    out = []
    for p in combo:
        it = items_by_id.get(p.item_id)
        if not p.masterwork_todo or p.tier < 1 or it is None:
            continue
        before = _rate(_swap(combo, [dataclasses.replace(p, stats=base_stats(it))]), ctx)
        if before is None:
            continue
        out.append({"id": need_id("masterwork", p.item_id), "kind": "masterwork", "label": f"Masterwork: {p.name}",
                    "target": {"itemId": p.item_id, "name": p.name, "slot": p.slot},
                    "builds": [{"build": ctx.slug,
                                "gain": {"stats": _stat_diff(before[1], base[1]), "effects": [],
                                         "score": round(max(base[0] - before[0], 0), 4)}}]})
    return out


def gap_needs(gaps, slug):
    """Needs of the gaps declared in `resolved.gaps` (weapons, catalysts, upgrades), flat gain."""
    return [{"id": need_id(g["kind"], sheet_mod.slug(g["target"])), "kind": g["kind"],
             "label": f"{GAP_LABELS[g['kind']]}: {g['target']}", "target": {"name": g["target"]},
             "builds": [{"build": slug, "gain": {"stats": {}, "effects": list(g.get("effects", [])),
                                                 "score": GAP_SCORE[g["kind"]]}}]}
            for g in gaps]


def set_bonus(sets_by_hash):
    """{set: ["2 pieces: …", "4 pieces: …"]} from the catalog sets."""
    return {v["set"]: v["bonus"] for v in sets_by_hash.values()}


def build_needs(s, slug, items, sets_by_hash, costs, set_slots_for):
    """(needs, warnings, complete) of a validated sheet. `complete` is false when armor needs could not be
    computed: statuses must then not turn done."""
    res = s.get("resolved") or {}
    out = gap_needs(res.get("gaps", []), slug)
    if not res.get("armor"):
        return out, [f"{slug}: no resolved armor, armor needs not computed (run optimize_build)"], True
    try:
        armor, warnings, complete = _armor_needs(s, slug, res, items, sets_by_hash, costs, set_slots_for)
        return out + armor, warnings, complete
    except ValueError as e:   # unknown mod or fragment, missing exotic: the gaps stay valid
        return out, [f"{slug}: {e}"], False


def _armor_needs(s, slug, res, items, sets_by_hash, costs, set_slots_for):
    """(armor needs, warnings, complete); raises ValueError if the sheet cannot be computed."""
    intent, sub, cls = s["intent"], s["subclass"], s["class"]
    pieces = inventory.load_pieces(items, cls, intent["exotic"], sets_by_hash, require_exotic=False)
    by_id = {p.item_id: p for lst in pieces.values() for p in lst}
    missing = [a["name"] for a in res["armor"] if a["itemId"] not in by_id]
    if missing or len(res["armor"]) != len(SLOTS):
        what = ", ".join(missing) or "incomplete armor"
        return [], [f"{slug}: resolved pieces missing from the snapshot ({what}): run optimize_build again"], False
    combo = tuple(by_id[a["itemId"]] for a in res["armor"])
    frag = fragment_stats(sub["fragments"], sub["element"], cls) if sub.get("fragments") else {}
    ctx = Ctx(slug, intent, frag, costs, cls)
    if _rate(combo, ctx) is None:
        return [], [f"{slug}: utility mods impossible on the resolved combination: run optimize_build again"], False
    sn, warnings = set_needs(combo, ctx, set_slots_for(cls), set_bonus(sets_by_hash))
    items_by_id = {it["itemId"]: it for it in items}
    return masterwork_needs(combo, items_by_id, ctx) + sn + slot_upgrades(combo, ctx), warnings, True


def aegis_needs(armor, sets_by_hash, weapons):
    """(needs, warnings, complete) of Aegis's Shopping List; a warning only (and incomplete) when it was not
    fetched; incomplete too when weapons were skipped for lack of a snapshot.
    `weapons`: the weapon snapshot, or None when missing."""
    from shell.sources.aegis import config, lookup
    from shell.sources.aegis.names import norm, strip_set
    rows = lookup.rows("endgame", "shopping-list")
    if not rows:
        return [], [f"{shopping.LABEL} missing: call refresh_references(source='aegis') "
                    "(or farm_needs(no_aegis=true))"], False
    slugs = [t.slug for t in config.weapon_tabs()] + ["exotic-weapons"]
    weapon_names = {norm(r["_name"]) for s in slugs for r in lookup.rows("endgame", s)}
    set_names = {strip_set(norm(r["_name"])) for r in lookup.rows("endgame", "set-bonuses")}
    found, warnings, complete = shopping.shopping_needs(rows, armor, weapons, sets_by_hash, weapon_names, set_names)
    if not weapon_names:
        warnings = warnings + ["Aegis weapon tabs missing: Shopping List weapons may be taken for exotic armor "
                               "(call refresh_references(source='aegis'))"]
        complete = False
    return found, warnings, complete


def extra_needs(armor, sets_by_hash, weapons, no_aegis=False):
    """(extra needs, warnings, keep) for `run`: the Aegis needs, and the `aegis/` prefix kept from auto-done
    when the Shopping List was skipped (`no_aegis`) or could not be fully checked."""
    if no_aegis:
        return [], [], AEGIS_KEEP
    found, warnings, complete = aegis_needs(armor, sets_by_hash, weapons)
    return found, warnings, () if complete else AEGIS_KEEP


def run(builds_dir, todo_dir, items, sets_by_hash, costs, set_slots_for, today, extra=(), extra_warnings=(),
        keep=()):
    """Computes the needs of every sheet, writes needs.json, syncs state.json and regenerates the sheets'
    Markdown. Returns the needs.json content.
    `extra`: needs outside the sheets (Aegis Shopping List), added as is.
    `keep`: id prefixes never auto-marked done (needs not computed this time)."""
    found, warnings, complete = list(extra), list(extra_warnings), True
    paths = sorted(Path(builds_dir).glob("*.json"))
    for path in paths:
        try:
            n, w, ok = build_needs(sheet_mod.load(path), path.stem, items, sets_by_hash, costs, set_slots_for)
        except (ValueError, OSError) as e:   # SheetError, unknown fragment or mod, missing exotic
            warnings.append(f"{path.stem}: {e}")
            complete = False
            continue
        found += n
        warnings += w
        complete = complete and ok
    doc = {"date": today, "needs": merge(found), "warnings": warnings}
    todo_dir = Path(todo_dir)
    state_mod.write_json(todo_dir / "needs.json", doc)
    st = state_mod.load(todo_dir / "state.json")
    state_mod.save(todo_dir / "state.json",
                   state_mod.sync(st, [n["id"] for n in doc["needs"]], today, mark_done=complete,
                                   keep=tuple(keep)))
    for path in paths:
        try:
            sheet_mod.save(path, sheet_mod.load(path), needs_dir=todo_dir)
        except (ValueError, OSError):
            pass   # already reported in the warnings
    return doc
