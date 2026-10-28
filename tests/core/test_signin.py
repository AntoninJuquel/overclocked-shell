import ssl

import pytest

from shell.core.signin import parse_callback, self_signed_cert


def test_parse_callback_ok():
    assert parse_callback("/callback?code=abc&state=xyz", "/callback", "xyz") == "abc"


@pytest.mark.parametrize("path", [
    "/callback?code=abc&state=bad",
    "/other?code=abc&state=xyz",
    "/callback?state=xyz",
])
def test_parse_callback_rejects(path):
    with pytest.raises(ValueError):
        parse_callback(path, "/callback", "xyz")


def test_self_signed_cert_loads(tmp_path):
    cert, key = self_signed_cert(tmp_path)
    ssl.create_default_context(ssl.Purpose.CLIENT_AUTH).load_cert_chain(cert, key)
