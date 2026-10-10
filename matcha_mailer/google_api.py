"""Google access: one OAuth login (browser) for Sheets, Docs (history log) and Drive (letter PDF)."""

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
                f"Manca {client_secret.name} in {client_secret.parent.name}/: segui il README, sezione 'Accesso a Google'."
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


# ------------------------------------------------------------ history log


def _u16(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def _para_text(p: dict) -> str:
    return "".join(e.get("textRun", {}).get("content", "") for e in p.get("elements", []))


def _body(doc: dict) -> dict:
    if "body" in doc:
        return doc["body"]
    return doc["tabs"][0]["documentTab"]["body"]


def build_history_requests(doc: dict, date_str: str, title: str, bullets: list[str]) -> list[dict]:
    """Appends '## date' (if the last H2 is not today), '### title' and one bullet per line,
    matching the existing structure of the history Doc (dash bullets are inherited from the
    last list paragraph when there is one)."""
    content = _body(doc)["content"]
    paragraphs = [c for c in content if "paragraph" in c]
    last_h2 = ""
    for c in paragraphs:
        if c["paragraph"].get("paragraphStyle", {}).get("namedStyleType") == "HEADING_2":
            last_h2 = _para_text(c["paragraph"]).strip()

    lines: list[tuple[str, str]] = []
    if last_h2 != date_str:
        lines.append(("HEADING_2", date_str))
    lines.append(("HEADING_3", title))
    lines += [("BULLET", b) for b in bullets]

    last = paragraphs[-1]
    inherits_bullet = "bullet" in last["paragraph"]
    if _para_text(last["paragraph"]).strip() == "":
        index, prefix = last["startIndex"], ""
    else:
        index, prefix = last["endIndex"] - 1, "\n"

    text = prefix + "\n".join(t for _, t in lines)
    reqs: list[dict] = [{"insertText": {"location": {"index": index}, "text": text}}]

    pos = index + _u16(prefix)
    ranges = []
    for kind, t in lines:
        start, end = pos, pos + _u16(t) + 1
        ranges.append((kind, start, end))
        pos = end

    for kind, start, end in ranges:
        rng = {"startIndex": start, "endIndex": end}
        if kind == "BULLET":
            reqs.append({"updateParagraphStyle": {"range": rng, "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                                                  "fields": "namedStyleType"}})
            continue
        if inherits_bullet:
            reqs.append({"deleteParagraphBullets": {"range": rng}})
        reqs.append({"updateParagraphStyle": {
            "range": rng,
            "paragraphStyle": {"namedStyleType": kind,
                               "indentFirstLine": {"magnitude": 0, "unit": "PT"},
                               "indentStart": {"magnitude": 0, "unit": "PT"}},
            "fields": "namedStyleType,indentFirstLine,indentStart",
        }})
    bullet_ranges = [(s_, e) for k, s_, e in ranges if k == "BULLET"]
    if bullet_ranges and not inherits_bullet:
        reqs.append({"createParagraphBullets": {
            "range": {"startIndex": bullet_ranges[0][0], "endIndex": bullet_ranges[-1][1]},
            "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
        }})
    return reqs


def append_history(session, doc_id: str, date_str: str, title: str, bullets: list[str]) -> None:
    base = f"https://docs.googleapis.com/v1/documents/{doc_id}"
    r = session.get(base, timeout=60)
    r.raise_for_status()
    reqs = build_history_requests(r.json(), date_str, title, bullets)
    r = session.post(base + ":batchUpdate", json={"requests": reqs}, timeout=60)
    r.raise_for_status()
