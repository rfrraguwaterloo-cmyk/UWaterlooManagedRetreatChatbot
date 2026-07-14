"""
Google Drive upload helper for the RFR case study pipeline.

Uploads pipeline output PDFs to a specified Google Drive folder immediately
after each step writes them to disk. Uses OAuth2 credentials so the pipeline
can run headlessly after a one-time browser authorization.

SETUP (one time per machine)
-----------------------------
1. In Google Cloud Console, create a project, enable the Drive API, and
   create OAuth2 credentials (Desktop app).  Download as credentials.json.
2. Add these two lines to rfr-rag/.env:
       GOOGLE_CREDENTIALS_FILE=/path/to/credentials.json
       GOOGLE_DRIVE_FOLDER_ID=<your-folder-id>
   The folder ID is the last segment of the Drive folder URL.
3. On the very first run the script opens a browser tab for authorization.
   After you approve, a token is saved to ~/.rfr-drive-token.json and all
   subsequent runs are silent — no flags needed.

USAGE IN THE PIPELINE
----------------------
Pass --drive-folder-id <ID> to any pipeline entry point.  The folder ID is
the last segment of the Drive folder's URL, e.g.:
    https://drive.google.com/drive/folders/11vGsMiYTaR2wERyiISjrwBq6akVzzZH6
                                                        ^^^^^^^^^^^^^^^^^^^^^^^^
If --drive-folder-id is omitted, Drive uploads are silently skipped.
If credentials are missing or the upload fails, a warning is printed and
the pipeline continues -- Drive errors never abort a run.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_DEFAULT_TOKEN_FILE = Path.home() / ".rfr-drive-token.json"


class DriveUploader:
    """
    Thin wrapper around the Google Drive v3 API for uploading PDFs.

    Instantiate once per pipeline run and call upload_pdf() after each file
    is written.  Credentials are resolved in this order:
      1. ``credentials_file`` argument
      2. ``GOOGLE_CREDENTIALS_FILE`` environment variable
      3. Already-saved OAuth token at ~/.rfr-drive-token.json (refresh only)
    """

    def __init__(
        self,
        folder_id: str,
        credentials_file: str | Path | None = None,
        token_file: str | Path | None = None,
    ) -> None:
        self.folder_id = folder_id
        self._token_file = Path(token_file) if token_file else _DEFAULT_TOKEN_FILE
        self._service = self._build_service(credentials_file)

    # ------------------------------------------------------------------
    # Internal auth helpers
    # ------------------------------------------------------------------

    def _build_service(self, credentials_file: str | Path | None):
        """Authenticate and return a Drive v3 service object."""
        # Lazy import so the pipeline doesn't crash when google libs are absent
        # and Drive upload wasn't requested.
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise ImportError(
                "Google API client libraries are not installed.\n"
                "Run: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
            ) from exc

        creds: Optional[Credentials] = None

        # 1. Try to load an existing token (saved from a previous auth).
        if self._token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self._token_file), SCOPES)

        # 2. Refresh or re-authorize as needed.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds_path = self._resolve_credentials_file(credentials_file)
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)

            # Persist the (possibly refreshed) token for future runs.
            self._token_file.write_text(creds.to_json())

        return build("drive", "v3", credentials=creds)

    @staticmethod
    def _resolve_credentials_file(credentials_file: str | Path | None) -> Path:
        """Return the credentials.json path, or raise a clear error."""
        if credentials_file:
            path = Path(credentials_file)
            if path.exists():
                return path
            raise FileNotFoundError(f"credentials file not found: {path}")

        env_val = os.getenv("GOOGLE_CREDENTIALS_FILE")
        if env_val:
            path = Path(env_val)
            if path.exists():
                return path
            raise FileNotFoundError(
                f"GOOGLE_CREDENTIALS_FILE points to a missing file: {path}"
            )

        raise FileNotFoundError(
            "No Google OAuth2 credentials file found.\n"
            "Either set GOOGLE_CREDENTIALS_FILE=/path/to/credentials.json in .env,\n"
            "or pass --drive-credentials /path/to/credentials.json at the command line."
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upload_pdf(self, pdf_path: Path, filename: str | None = None) -> str:
        """
        Upload *pdf_path* to self.folder_id.

        Parameters
        ----------
        pdf_path:
            Local path to the PDF file to upload.
        filename:
            Name to give the file in Drive (defaults to pdf_path.name).

        Returns
        -------
        str
            The Drive file ID of the newly created file.
        """
        from googleapiclient.http import MediaFileUpload  # type: ignore[import]

        name = filename or pdf_path.name
        file_metadata = {"name": name, "parents": [self.folder_id]}
        media = MediaFileUpload(str(pdf_path), mimetype="application/pdf", resumable=False)

        result = (
            self._service.files()
            .create(body=file_metadata, media_body=media, fields="id,name")
            .execute()
        )
        drive_id: str = result.get("id", "")
        print(f"  [Drive] Uploaded '{name}' → https://drive.google.com/file/d/{drive_id}/view")
        return drive_id


# ---------------------------------------------------------------------------
# Factory — used by pipeline entry points
# ---------------------------------------------------------------------------

def make_uploader(
    folder_id: str | None = None,
    credentials_file: str | Path | None = None,
    token_file: str | Path | None = None,
) -> Optional["DriveUploader"]:
    """
    Return a DriveUploader if a folder ID is available, else None.

    The folder ID is resolved in this order:
      1. ``folder_id`` argument (e.g. from --drive-folder-id on the CLI)
      2. ``GOOGLE_DRIVE_FOLDER_ID`` environment variable / .env entry

    Failures (missing libs, bad credentials) are caught and printed as
    warnings so the pipeline can continue without Drive uploads.
    """
    resolved_folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not resolved_folder_id:
        return None
    folder_id = resolved_folder_id
    try:
        uploader = DriveUploader(
            folder_id=folder_id,
            credentials_file=credentials_file,
            token_file=token_file,
        )
        print(f"  [Drive] Uploader ready (folder: {folder_id})")
        return uploader
    except Exception as exc:
        print(f"\n  [Drive] Warning: could not initialize uploader — {exc}")
        print("  [Drive] Drive uploads will be skipped for this run.\n")
        return None


def try_upload(uploader: Optional["DriveUploader"], pdf_path: Path | None) -> None:
    """
    Upload *pdf_path* if both *uploader* and *pdf_path* are non-None.

    Errors are caught and printed as warnings — they never propagate to the
    caller, so a transient Drive error can't abort a pipeline run.
    """
    if uploader is None or pdf_path is None:
        return
    try:
        uploader.upload_pdf(pdf_path)
    except Exception as exc:
        print(f"  [Drive] Warning: upload of '{pdf_path.name}' failed — {exc}")
