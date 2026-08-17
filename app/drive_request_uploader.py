"""Google Drive intake uploads for new case study requests.

Preferred hosted auth uses OAuth user credentials for the shared
``rfr.rag.uwaterloo@gmail.com`` account. This avoids service-account Drive
storage quota limits in regular My Drive folders. If OAuth secrets are absent,
the uploader falls back to the older service-account secret.
"""

from __future__ import annotations

import io
import json
import mimetypes
import os
from typing import Any


DEFAULT_REQUESTS_DRIVE_FOLDER_ID = "10n_-uOCT2GXu_G3r1qi5qJr8hHoy-E_y"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def _oauth_env_is_configured() -> bool:
    required = (
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "GOOGLE_OAUTH_REFRESH_TOKEN",
    )
    return all(os.getenv(key) for key in required)


def _drive_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials as OAuthCredentials
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google Drive libraries are not installed. Check requirements.txt."
        ) from exc

    if _oauth_env_is_configured():
        creds = OAuthCredentials(
            token=None,
            refresh_token=os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
            token_uri=os.getenv("GOOGLE_OAUTH_TOKEN_URI", "https://oauth2.googleapis.com/token"),
            client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
            scopes=DRIVE_SCOPES,
        )
        creds.refresh(Request())
        return build("drive", "v3", credentials=creds)

    creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise RuntimeError(
            "Google Drive credentials are not set. Add OAuth secrets "
            "GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, and "
            "GOOGLE_OAUTH_REFRESH_TOKEN, or add GOOGLE_SERVICE_ACCOUNT_JSON "
            "as a Hugging Face Space secret."
        )

    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=DRIVE_SCOPES)
    return build("drive", "v3", credentials=creds)


def _create_folder(service, parent_folder_id: str, name: str) -> dict:
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_folder_id],
    }
    return (
        service.files()
        .create(body=metadata, fields="id,name,webViewLink", supportsAllDrives=True)
        .execute()
    )


def _upload_bytes(
    service,
    parent_folder_id: str,
    filename: str,
    data: bytes,
    mimetype: str | None = None,
) -> dict:
    from googleapiclient.http import MediaIoBaseUpload

    resolved_mimetype = mimetype or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=resolved_mimetype, resumable=False)
    metadata = {"name": filename, "parents": [parent_folder_id]}
    return (
        service.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id,name,webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )


def upload_case_request_to_drive(
    request_folder_name: str,
    request_record: dict,
    uploaded_files: list[Any],
) -> dict:
    parent_folder_id = os.getenv("RFR_REQUESTS_DRIVE_FOLDER_ID", DEFAULT_REQUESTS_DRIVE_FOLDER_ID)
    service = _drive_service()

    folder = _create_folder(service, parent_folder_id, request_folder_name)
    folder_id = folder["id"]

    uploaded = []
    for uploaded_file in uploaded_files:
        file_result = _upload_bytes(
            service,
            folder_id,
            uploaded_file.name,
            uploaded_file.getvalue(),
            getattr(uploaded_file, "type", None),
        )
        uploaded.append(file_result)

    final_record = {
        **request_record,
        "drive_folder_id": folder_id,
        "drive_folder_url": folder.get("webViewLink") or f"https://drive.google.com/drive/folders/{folder_id}",
        "saved_files": [item.get("name", "") for item in uploaded],
        "uploaded_drive_files": uploaded,
    }
    _upload_bytes(
        service,
        folder_id,
        "request.json",
        json.dumps(final_record, indent=2).encode("utf-8"),
        "application/json",
    )

    return final_record
