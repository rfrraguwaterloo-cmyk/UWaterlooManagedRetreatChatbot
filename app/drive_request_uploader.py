"""Google Drive intake uploads for new case study requests.

Uses the same GOOGLE_SERVICE_ACCOUNT_JSON secret pattern as sheets_logger.py.
The target Drive folder must be shared with the service account email.
"""

from __future__ import annotations

import io
import json
import mimetypes
import os
from typing import Any


DEFAULT_REQUESTS_DRIVE_FOLDER_ID = "10n_-uOCT2GXu_G3r1qi5qJr8hHoy-E_y"


def _drive_service():
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google Drive libraries are not installed. Check requirements.txt."
        ) from exc

    creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not set. Add it as a Hugging Face Space secret."
        )

    creds_dict = json.loads(creds_json)
    scopes = ["https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
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
