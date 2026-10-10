"""Reads and updates the "Matcha - Funnel Vendita" sheet.

Safety rules:
- columns are found by header name, never by position;
- rows are found by venue name, re-reading the sheet right before every write
  (the sheet gets re-sorted), never by a cached row number;
- a name that matches zero or more than one row is never written;
- only the cells that change are written, and the old values are returned for the history log.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from gspread.utils import rowcol_to_a1

from matcha_mailer.planner import Venue

COLUMNS = {
    "name": "Nome attività",
    "address": "Luogo attività o sede",
    "zone": "Zona",
    "contact": "Referente",
    "phone": "Cellulare",
    "email": "Mail",
    "probability": "Probabilitá",
    "last_action": "Ultima azione fatta",
    "last_contacted": "Last contacted",
    "notes": "Note",
    "mail_step": "Mail step",
    "mail_last_sent": "Mail ultimo invio",
    "mail_next": "Mail prossimo invio",
    "mail_thread": "Mail thread",
}
MAILER_COLUMNS = ["mail_step", "mail_last_sent", "mail_next", "mail_thread"]


class FunnelError(Exception):
    pass


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.casefold().split())


@dataclass
class Change:
    venue: str
    column: str
    old: str
    new: str


class Funnel:
    def __init__(self, worksheet):
        self.ws = worksheet

    # ---------------------------------------------------------------- read
    def _header_map(self, header: list[str]) -> dict[str, int]:
        idx = {norm(h): i for i, h in enumerate(header) if h.strip()}
        out = {}
        for key, title in COLUMNS.items():
            if norm(title) in idx:
                out[key] = idx[norm(title)]
        required = ["name", "email", "probability", "last_action", "last_contacted", "notes"]
        missing = [COLUMNS[k] for k in required if k not in out]
        if missing:
            raise FunnelError("Nel funnel non trovo le colonne: " + ", ".join(missing))
        return out

    def load(self) -> list[Venue]:
        values = self.ws.get_all_values()
        if not values:
            raise FunnelError("Il funnel è vuoto")
        cols = self._header_map(values[0])
        venues = []
        for row in values[1:]:
            def cell(key: str) -> str:
                i = cols.get(key)
                return row[i].strip() if i is not None and i < len(row) else ""

            if not cell("name"):
                continue
            venues.append(
                Venue(
                    name=cell("name"),
                    zone=cell("zone"),
                    contact=cell("contact"),
                    phone=cell("phone"),
                    email=cell("email"),
                    probability=cell("probability"),
                    last_action=cell("last_action"),
                    last_contacted=cell("last_contacted"),
                    notes=cell("notes"),
                    mail_step=cell("mail_step"),
                    mail_last_sent=cell("mail_last_sent"),
                    mail_next=cell("mail_next"),
                    mail_thread=cell("mail_thread"),
                )
            )
        return venues

    def missing_mailer_columns(self) -> list[str]:
        header = self.ws.row_values(1)
        present = {norm(h) for h in header}
        return [COLUMNS[k] for k in MAILER_COLUMNS if norm(COLUMNS[k]) not in present]

    def add_mailer_columns(self) -> list[str]:
        """Adds the missing mailer headers after the last used header cell. Returns what was added."""
        header = self.ws.row_values(1)
        missing = self.missing_mailer_columns()
        if not missing:
            return []
        last = max((i for i, h in enumerate(header) if h.strip()), default=-1)
        start_col = last + 2  # 1-based column after the last used header
        needed = start_col + len(missing) - 1
        if needed > self.ws.col_count:
            self.ws.add_cols(needed - self.ws.col_count)
        data = [
            {"range": rowcol_to_a1(1, start_col + i), "values": [[title]]}
            for i, title in enumerate(missing)
        ]
        self.ws.batch_update(data, value_input_option="RAW")
        return missing

    # ---------------------------------------------------------------- write
    def update_by_name(self, venue_name: str, changes: dict[str, str]) -> list[Change]:
        """changes: {column key: new value}. Re-reads the sheet and writes only the differing cells."""
        values = self.ws.get_all_values()
        cols = self._header_map(values[0])
        unknown = [k for k in changes if k not in cols]
        if unknown:
            raise FunnelError("Colonne mancanti nel funnel: " + ", ".join(COLUMNS.get(k, k) for k in unknown))

        target = norm(venue_name)
        matches = [
            i for i, row in enumerate(values[1:], start=2)
            if cols["name"] < len(row) and norm(row[cols["name"]]) == target
        ]
        if len(matches) != 1:
            raise FunnelError(
                f"'{venue_name}': trovate {len(matches)} righe con questo nome, non scrivo nulla"
            )
        row_no = matches[0]
        row = values[row_no - 1]

        data, diff = [], []
        for key, new in changes.items():
            col = cols[key]
            old = row[col] if col < len(row) else ""
            if old == new:
                continue
            data.append({"range": rowcol_to_a1(row_no, col + 1), "values": [[new]]})
            diff.append(Change(venue_name, COLUMNS[key], old, new))
        if data:
            self.ws.batch_update(data, value_input_option="RAW")
        return diff


def open_funnel(gc, spreadsheet_id: str, sheet_name: str) -> Funnel:
    sh = gc.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(sheet_name)
    except Exception:
        ws = sh.sheet1
    return Funnel(ws)
