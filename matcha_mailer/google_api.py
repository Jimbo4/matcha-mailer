"""Accesso a Google: un solo login OAuth (browser) per Sheets (funnel), Docs (cronologia) e Drive (PDF lettera)."""

from __future__ import annotations

from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.readonly",
]


class GoogleSetupMissing(Exception):
    pass


def get_credentials(client_secret: Path, token_path: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception:
            creds = None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None
    if not creds or not creds.valid:
        if not client_secret.exists():
            raise GoogleSetupMissing(
                f"Manca locale/segreti/{client_secret.name}: segui il README, sezione 'Accesso a Google'."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def clients(creds):
    import gspread
    from google.auth.transport.requests import AuthorizedSession

    return gspread.authorize(creds), AuthorizedSession(creds)


def export_pdf(session, doc_id: str) -> bytes:
    r = session.get(
        f"https://www.googleapis.com/drive/v3/files/{doc_id}/export",
        params={"mimeType": "application/pdf"},
        timeout=60,
    )
    r.raise_for_status()
    return r.content
