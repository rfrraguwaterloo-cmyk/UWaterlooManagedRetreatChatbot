"""
sheets_logger.py — Log user queries and responses to Google Sheets.

Reads credentials from the GOOGLE_SERVICE_ACCOUNT_JSON environment variable
(set as a secret in HuggingFace Spaces, or locally via .env).

Logs each row: timestamp, query, answer, questionnaire context, case studies used.
Fails silently so logging errors never break the app for users.
"""

import json
import os
from datetime import datetime, timezone


SHEET_ID = "1zfTGkuvlwRdLcOSvPJLxo7ULHgeOYP4y2bfl3j09ZyA"
SHEET_TAB = "Query Log"

HEADERS = [
    "Timestamp (UTC)",
    "Query",
    "Answer",
    "Questionnaire Context",
    "Case Studies Used",
    "Model",
]


def _get_sheet():
    """Authenticate and return the worksheet, or None if credentials unavailable."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not creds_json:
            return None

        creds_dict = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SHEET_ID)

        # Get or create the tab
        try:
            sheet = spreadsheet.worksheet(SHEET_TAB)
        except gspread.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(title=SHEET_TAB, rows=1000, cols=10)
            sheet.append_row(HEADERS)

        return sheet
    except Exception as e:
        print(f"[sheets_logger] Could not connect to Google Sheets: {e}")
        return None


def log_query(
    query: str,
    answer: str,
    chunks: list[dict],
    questionnaire_answers: dict | None = None,
    model: str = "claude",
) -> None:
    """Log a query/answer pair to Google Sheets. Fails silently."""
    try:
        sheet = _get_sheet()
        if sheet is None:
            return

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        case_ids = ", ".join(sorted({c["metadata"].get("case_id", "") for c in chunks if c.get("metadata")}))
        context_str = "; ".join(f"{k}: {v}" for k, v in (questionnaire_answers or {}).items())

        sheet.append_row([
            timestamp,
            query,
            answer[:2000],  # truncate very long answers
            context_str,
            case_ids,
            model,
        ])
    except Exception as e:
        print(f"[sheets_logger] Failed to log row: {e}")
