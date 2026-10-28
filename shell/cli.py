"""`shell` command: one-time Bungie sign-in."""
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
    args = parser.parse_args()

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
