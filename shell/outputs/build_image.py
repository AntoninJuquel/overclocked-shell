"""PNG and HTML exports of a build sheet, made from its PDF so all three look the same.

HTML: one self-contained file, the PNG with a clickable zone over each linked icon (no selectable text).
"""
import base64
import html as html_lib
import io

import pypdfium2

SCALE = 2.5  # 180 dpi: about 2100 px wide
PAGE_W, PAGE_H = 297, 210  # A4 landscape, mm


def png(pdf: bytes) -> bytes:
    """The PDF's first page as a PNG."""
    out = io.BytesIO()
    pypdfium2.PdfDocument(pdf)[0].render(scale=SCALE).to_pil().save(out, "PNG")
    return out.getvalue()


def html(image: bytes, boxes: list[tuple], title: str) -> str:
    """Page showing `image`, with a link over each box (x, y, width, label, url), in mm on the A4 page."""
    src = base64.b64encode(image).decode()
    zones = "".join(
        f'<a href="{html_lib.escape(url)}" title="{html_lib.escape(label)}" aria-label="{html_lib.escape(label)}" '
        f'target="_blank" rel="noopener" style="left:{x / PAGE_W:.3%};top:{y / PAGE_H:.3%};'
        f'width:{w / PAGE_W:.3%};height:{w / PAGE_H:.3%}"></a>'
        for x, y, w, label, url in boxes)
    name = html_lib.escape(title)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}</title>
<style>
body {{ margin: 0; background: #111; }}
main {{ position: relative; max-width: 100vw; width: fit-content; margin: auto; }}
img {{ display: block; max-width: 100%; height: auto; }}
a {{ position: absolute; }}
a:hover, a:focus {{ outline: 2px solid #e9cf55; }}
</style></head>
<body><main><img src="data:image/png;base64,{src}" alt="{name}">{zones}</main></body></html>
"""
