"""Registro locale degli invii (locale/registro/invii.csv): una riga per mail o WhatsApp partito.

Serve a contare le mail della settimana, a non riproporre una mail partita ma non registrata nel funnel,
a collegare le mail in arrivo ai locali (Message-ID) e a ricordare oggetto e nome usati nella Mail 1,
così Mail 2 e Mail 3 restano nello stesso thread e usano lo stesso nome del locale.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from matcha_mailer import calendario, config

# riattivato = "1" when the mail went to a "00 - perso" venue revived by Jacopo (--riattiva): only those
# keep receiving Mail 2 and 3 while marked lost.
FIELDS = ["data", "ora", "locale", "azione", "destinatario", "oggetto", "message_id", "nome_in_mail", "riattivato"]


@dataclass
class Entry:
    day: date | None
    venue: str
    kind: str
    to: str
    subject: str
    message_id: str
    name_in_mail: str
    revived: bool = False


class Registry:
    def __init__(self, path: Path | None = None):
        self.path = path or config.REGISTRY_PATH

    def entries(self) -> list[Entry]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8", newline="") as f:
            return [
                Entry(calendario.parse(r.get("data", "")), r.get("locale", "") or "", r.get("azione", "") or "",
                      r.get("destinatario", "") or "", r.get("oggetto", "") or "", r.get("message_id", "") or "",
                      r.get("nome_in_mail", "") or "", (r.get("riattivato", "") or "").strip() == "1")
                for r in csv.DictReader(f)
            ]

    def _upgrade_header(self) -> None:
        """Adds columns introduced later (e.g. nome_in_mail) to an existing file, keeping every row."""
        with self.path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            header = list(reader.fieldnames or [])
            rows = list(reader)
        if not header or header == FIELDS:
            return
        with self.path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k) or "" for k in FIELDS})

    def add(self, today: date, venue: str, kind: str, to: str, subject: str, message_id: str,
            name_in_mail: str = "", revived: bool = False) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._upgrade_header()
        new = not self.path.exists() or self.path.stat().st_size == 0
        with self.path.open("a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(FIELDS)
            w.writerow([calendario.fmt(today), datetime.now().strftime("%H:%M"), venue, kind, to, subject,
                        message_id, name_in_mail, "1" if revived else ""])

    # ------------------------------------------------------------ queries
    def sent_this_week(self, today: date) -> int:
        week = today.isocalendar()[:2]
        return sum(1 for e in self.entries() if e.day and e.day.isocalendar()[:2] == week and e.kind.startswith("mail"))

    def already_sent(self) -> dict[tuple[str, str], str]:
        """(venue name lower-cased, action kind) -> date (gg/mm/aaaa)."""
        return {(e.venue.lower(), e.kind): calendario.fmt(e.day) if e.day else "" for e in self.entries()}

    def first_mail(self) -> dict[str, Entry]:
        """Venue name lower-cased -> last Mail 1 sent (subject and name used, for Mail 2 and 3)."""
        return {e.venue.lower(): e for e in self.entries() if e.kind == "mail1"}

    def message_ids(self) -> dict[str, str]:
        """Message-ID without <> lower-cased -> venue name."""
        return {e.message_id.strip().strip("<>").lower(): e.venue for e in self.entries() if e.message_id.strip()}

    def ids_by_venue(self) -> dict[str, list[str]]:
        """Venue name lower-cased -> Message-ID of every mail sent to it, oldest first (to find replies)."""
        out: dict[str, list[str]] = {}
        for e in self.entries():
            if e.message_id.strip():
                out.setdefault(e.venue.lower(), []).append(e.message_id.strip())
        return out

    def revived(self) -> set[str]:
        """Lower-cased names of the "00 - perso" venues written to on Jacopo's request (--riattiva)."""
        return {e.venue.lower() for e in self.entries() if e.revived}

    def first_day(self) -> date | None:
        days = [e.day for e in self.entries() if e.day]
        return min(days) if days else None
