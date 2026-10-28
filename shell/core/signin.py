"""One-time Bungie sign-in: local HTTPS callback (Bungie requires https redirects) with a self-signed cert."""
import datetime
import ipaddress
import secrets
import ssl
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from shell.core import paths
from shell.core.auth import OAuth, Tokens
from shell.core.settings import Settings


def parse_callback(path: str, expected_path: str, expected_state: str) -> str:
    url = urlparse(path)
    if url.path != expected_path:
        raise ValueError(f"Unexpected path {url.path}")
    query = parse_qs(url.query)
    if query.get("state", [None])[0] != expected_state:
        raise ValueError("State mismatch: ignore this request and sign in again.")
    code = query.get("code", [None])[0]
    if not code:
        raise ValueError("No authorization code in the callback.")
    return code


def self_signed_cert(dir: Path) -> tuple[Path, Path]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName(
            [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .sign(key, hashes.SHA256())
    )
    dir.mkdir(parents=True, exist_ok=True)
    cert_file, key_file = dir / "localhost.crt", dir / "localhost.key"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    return cert_file, key_file


def run_signin(settings: Settings, oauth: OAuth) -> Tokens:
    redirect = urlparse(settings.redirect_url)
    if redirect.scheme != "https" or redirect.hostname not in ("localhost", "127.0.0.1"):
        raise SystemExit(f"BUNGIE_REDIRECT_URL must be https://localhost:<port>/<path>, got {settings.redirect_url}")
    port = redirect.port or 443
    state = secrets.token_urlsafe(16)
    result: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlparse(self.path).path != redirect.path:
                self.send_error(404)
                return
            try:
                result["code"] = parse_callback(self.path, redirect.path, state)
                status, text = 200, "Signed in to Bungie. You can close this tab."
            except ValueError as e:
                result["error"] = str(e)
                status, text = 400, str(e)
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(text.encode())

        def log_message(self, *args):
            pass

    try:
        server = HTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        raise SystemExit(f"Could not listen on port {port} ({e}). Free it or change BUNGIE_REDIRECT_URL "
                         "(and the app's Redirect URL).")
    cert, key = self_signed_cert(paths.profile_dir() / "auth")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)

    url = oauth.authorize_url(state)
    print(f"Opening {url}\nYour browser will warn about the localhost certificate: it was just made on this "
          "machine, choose Advanced > Continue.")
    webbrowser.open(url)
    with server:
        while not result:
            try:
                server.handle_request()
            except ssl.SSLError:
                continue  # browser aborting the handshake over the untrusted cert, it retries
    if "error" in result:
        raise SystemExit(result["error"])
    return oauth.exchange_code(result["code"])
