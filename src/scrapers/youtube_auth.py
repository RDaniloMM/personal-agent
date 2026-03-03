"""YouTube OAuth2 authentication and service builder.

Usage (one-time, on a desktop machine with a browser):
    uv run python -m src.scrapers.youtube_auth

This opens a browser for Google sign-in, then saves the refresh token
to ``profiles/youtube_token.json``.  Copy that file to the server.

The token auto-refreshes; you should only need to re-auth if you
revoke access or the token is explicitly invalidated.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Read-only scope: list subscriptions + playlist items
_SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

# Default paths (overridable)
_DEFAULT_CLIENT_SECRET = Path("client_secret.json")
_DEFAULT_TOKEN = Path("profiles/youtube_token.json")


def authorize(
    client_secret_path: Path = _DEFAULT_CLIENT_SECRET,
    token_path: Path = _DEFAULT_TOKEN,
) -> Credentials:
    """Run the OAuth2 flow (opens browser) and persist the token."""
    token_path.parent.mkdir(parents=True, exist_ok=True)

    creds: Credentials | None = None

    # Try loading existing token
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

    # Refresh or re-auth
    if creds and creds.expired and creds.refresh_token:
        print("Token expired — refreshing…")
        creds.refresh(Request())
    elif not creds or not creds.valid:
        print(f"Starting OAuth2 flow with {client_secret_path} …")
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path), _SCOPES,
        )
        creds = flow.run_local_server(port=0, open_browser=True)

    # Persist token (includes refresh_token for future runs)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"✓ Token saved to {token_path}")
    return creds


def build_youtube_service(
    token_path: Path | str,
    client_secret_path: Path | str | None = None,
):
    """Build an authenticated YouTube Data API v3 service.

    Automatically refreshes expired tokens using the stored refresh_token.
    """
    token_path = Path(token_path)
    creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Persist refreshed token
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


# ── CLI entry point ──────────────────────────────────────────────────────────

def main() -> None:
    """Authorize and test the connection."""
    import argparse

    parser = argparse.ArgumentParser(description="YouTube OAuth2 setup")
    parser.add_argument(
        "--client-secret",
        type=Path,
        default=_DEFAULT_CLIENT_SECRET,
        help="Path to OAuth2 client secret JSON",
    )
    parser.add_argument(
        "--token",
        type=Path,
        default=_DEFAULT_TOKEN,
        help="Path to save the token",
    )
    args = parser.parse_args()

    creds = authorize(args.client_secret, args.token)

    # Quick test: list 3 subscriptions
    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.subscriptions().list(
        part="snippet", mine=True, maxResults=3,
    ).execute()

    subs = resp.get("items", [])
    print(f"\n✓ Authenticated! Found {resp.get('pageInfo', {}).get('totalResults', '?')} subscriptions.")
    for s in subs:
        print(f"  • {s['snippet']['title']}")

    print(f"\nNext steps:")
    print(f"  scp {args.token} danilo@192.168.100.18:~/personal-agent/profiles/")


if __name__ == "__main__":
    main()
