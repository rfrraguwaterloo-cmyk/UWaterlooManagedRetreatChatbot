"""Create Hugging Face OAuth secrets for Drive request uploads.

Run this locally once with a Google OAuth Desktop client credentials file, then
sign in as the Google account that should own uploaded request folders.

Example:
    python3 -m case_study_pipeline.create_drive_oauth_secrets \
      --credentials-file /path/to/oauth-client.json \
      --space-id UWRFR/UWaterlooRFRChatBot
"""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive"]


def _load_client_config(credentials_file: Path) -> tuple[str, str]:
    data = json.loads(credentials_file.read_text())
    config = data.get("installed") or data.get("web")
    if not config:
        raise ValueError(
            "OAuth credentials file must contain an 'installed' or 'web' client config."
        )
    return config["client_id"], config["client_secret"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Hugging Face Space secrets for Google Drive OAuth uploads."
    )
    parser.add_argument(
        "--credentials-file",
        required=True,
        type=Path,
        help="Google OAuth client JSON file, usually a Desktop app credential.",
    )
    parser.add_argument(
        "--space-id",
        default="UWRFR/UWaterlooRFRChatBot",
        help="Hugging Face Space ID to show in the generated commands.",
    )
    args = parser.parse_args()

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise SystemExit(
            "Google OAuth libraries are not installed. Run: "
            "pip install google-auth-oauthlib google-api-python-client google-auth-httplib2"
        ) from exc

    credentials_file = args.credentials_file.expanduser().resolve()
    client_id, client_secret = _load_client_config(credentials_file)

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    if not creds.refresh_token:
        raise SystemExit(
            "Google did not return a refresh token. In Google Account permissions, "
            "remove this app's previous access, then rerun with prompt=consent."
        )

    print("\nAdd these secrets to Hugging Face:")
    print(
        "hf spaces secrets add "
        f"{shlex.quote(args.space_id)} "
        f"-s GOOGLE_OAUTH_CLIENT_ID={shlex.quote(client_id)}"
    )
    print(
        "hf spaces secrets add "
        f"{shlex.quote(args.space_id)} "
        f"-s GOOGLE_OAUTH_CLIENT_SECRET={shlex.quote(client_secret)}"
    )
    print(
        "hf spaces secrets add "
        f"{shlex.quote(args.space_id)} "
        f"-s GOOGLE_OAUTH_REFRESH_TOKEN={shlex.quote(creds.refresh_token)}"
    )
    print("\nThen restart the Space:")
    print(f"hf spaces restart {shlex.quote(args.space_id)}")


if __name__ == "__main__":
    main()
