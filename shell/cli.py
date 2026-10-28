"""`shell` command: one-time Bungie sign-in, one-time dim-agent import."""
import argparse
import json

from shell.core.auth import OAuth
from shell.core.settings import SettingsError, load_settings
from shell.core.signin import run_signin


def main() -> None:
    parser = argparse.ArgumentParser(prog="shell")
    sub = parser.add_subparsers(dest="group", required=True)
    auth = sub.add_parser("auth", help="Bungie sign-in").add_subparsers(dest="command", required=True)
    auth.add_parser("login", help="sign in through the browser")
    auth.add_parser("status", help="show the sign-in state")
    imp = sub.add_parser("import", help="import data from another tool").add_subparsers(dest="command", required=True)
    imp.add_parser("dim-agent", help="builds and TODO data from a dim-agent folder").add_argument("path")
    args = parser.parse_args()
    if args.group == "import":
        from shell.engines.dim_import import import_dim_agent
        try:
            print(json.dumps(import_dim_agent(args.path), indent=2))
        except ValueError as e:
            raise SystemExit(str(e))
        return

    try:
        settings = load_settings()
    except SettingsError as e:
        raise SystemExit(str(e))
    oauth = OAuth(settings)
    if args.command == "login":
        tokens = run_signin(settings, oauth)
        print(f"Signed in (Bungie.net membership {tokens.membership_id}).")
    else:
        print(json.dumps(oauth.status(), indent=2))
