import base64

from shell.outputs import build_image, build_pdf
from tests.outputs.test_build_pdf import resolved_sheet


def page():
    return build_pdf.render(resolved_sheet(), {}, fonts=None)[0]


def test_png_is_the_a4_page():
    data = build_image.png(page())
    assert data.startswith(b"\x89PNG")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    assert width > 2000 and abs(width / height - 297 / 210) < .01


def test_html_embeds_the_image_with_links():
    text = build_image.html(b"png-bytes", [(29.7, 21, 14.85, "A & B", "https://x.test/1?a=1&b=2")], "<Build>")
    assert base64.b64encode(b"png-bytes").decode() in text
    assert "left:10.000%;top:10.000%;width:5.000%;height:7.071%" in text
    assert 'href="https://x.test/1?a=1&amp;b=2"' in text and 'title="A &amp; B"' in text
    assert "<title>&lt;Build&gt;</title>" in text


def test_render_reports_the_link_boxes():
    boxes = []
    build_pdf.render(resolved_sheet(), {}, fonts=None, links={"plug:Feed the Void": "https://x.test/1"}, boxes=boxes,
                     tr=lambda t: t.replace("Feed the Void", "Abysse"))
    assert len(boxes) == 1 and boxes[0][3:] == ("Abysse", "https://x.test/1")
