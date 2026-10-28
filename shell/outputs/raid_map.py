"""Schematic SVG map of one floor of a raid encounter: rooms as labelled boxes, spots the guides locate as markers
with their callout names. Spots without a position are not drawn (the page lists them)."""
from html import escape

W, H = 400, 300  # the encounter grid is 0-100 on both axes


def _x(v):
    return round(v * W / 100, 1)


def _y(v):
    return round(v * H / 100, 1)


def svg(enc: dict, floor_id: str, names: dict, highlight: set[str]) -> str:
    floor = next(f for f in enc["floors"] if f["id"] == floor_id)
    out = [f'<svg viewBox="0 0 {W} {H + 24}" xmlns="http://www.w3.org/2000/svg" role="img" '
           f'aria-label="{escape(floor["name"])} map">',
           f'<text x="4" y="14" class="floor">{escape(floor["name"])}</text>',
           f'<g transform="translate(0 20)"><rect class="area" x="0" y="0" width="{W}" height="{H}"/>']
    for r in floor.get("rooms", []):
        out.append(f'<rect class="room" x="{_x(r["x"])}" y="{_y(r["y"])}" width="{_x(r["w"])}" '
                   f'height="{_y(r["h"])}"/><text class="room-name" x="{_x(r["x"]) + 4}" y="{_y(r["y"]) + 12}">'
                   f'{escape(r["name"])}</text>')
    for s in enc["spots"]:
        if s.get("floor") != floor_id or s.get("pos") is None:
            continue
        x, y = _x(s["pos"][0]), _y(s["pos"][1])
        cls = "spot hl" if s["id"] in highlight else "spot"
        # labels point away from the centre so neighbours across a divider don't collide; near an edge, inward
        left = 20 < s["pos"][0] < 50 or s["pos"][0] > 80
        tx, anchor = (x - 9, "end") if left else (x + 9, "start")
        out.append(f'<g class="{cls}"><circle cx="{x}" cy="{y}" r="6"/>'
                   f'<text x="{tx}" y="{y + 4}" text-anchor="{anchor}">'
                   f'{escape(names.get(s["id"], s["name"]))}</text></g>')
    out.append(f'<text class="note" x="{W - 4}" y="{H - 6}" text-anchor="end">'
               f'Schematic — positions from the guides</text></g></svg>')
    return "".join(out)
