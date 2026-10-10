"""Decides the next action for every venue in the funnel.

Rules (see README):
- "10 - nuovo" with an email, not "TODO: da visitare": cold sequence Mail 1 -> Mail 2 -> Mail 3.
- "50 - curioso" not yet followed up: Mail 4 (letter of intent) if there is an email,
  otherwise WhatsApp if there is a mobile number, otherwise a reminder to call.
- Anyone who replied (detected in the inbox) leaves the sequence: Jacopo reads the reply.
- "Mail step" = stop / risposta / 3 / 4 / WA means nothing else is sent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import quote

from matcha_mailer import calendar_it

# "Mail step" values written by the mailer
STEP_MAIL = {"mail1": "1", "mail2": "2", "mail3": "3", "mail4": "4", "whatsapp": "WA"}
CLOSED_STEPS = {"3", "4", "wa", "stop", "risposta"}

ACTION_LABEL = {
    "mail1": "Mail 1 · primo contatto",
    "mail2": "Mail 2 · follow up",
    "mail3": "Mail 3 · break up",
    "mail4": "Mail 4 · lettera d'intenti",
    "whatsapp": "WhatsApp · lettera d'intenti",
    "info": "",
}

LAST_ACTION_VALUE = {
    "mail1": "Email 1",
    "mail2": "Email 2",
    "mail3": "Email 3 (break up)",
    "mail4": "Email lettera d'intenti",
    "whatsapp": "WhatsApp lettera d'intenti",
}


@dataclass
class Venue:
    name: str
    zone: str = ""
    contact: str = ""
    phone: str = ""
    email: str = ""
    probability: str = ""
    last_action: str = ""
    last_contacted: str = ""
    notes: str = ""
    mail_step: str = ""
    mail_last_sent: str = ""
    mail_next: str = ""
    mail_thread: str = ""

    @property
    def prob_code(self) -> str:
        m = re.match(r"\s*(\d+)", self.probability or "")
        return m.group(1).zfill(2) if m else ""


@dataclass
class Action:
    venue: Venue
    kind: str  # mail1..mail4, whatsapp, info
    status: str = ""  # shown in the "Stato" column
    selectable: bool = True
    selected: bool = True
    values: dict[str, str] = field(default_factory=dict)
    subject: str = ""
    body: str = ""
    edited: bool = False

    @property
    def label(self) -> str:
        return ACTION_LABEL.get(self.kind, "")

    @property
    def is_mail(self) -> bool:
        return self.kind.startswith("mail")


# ------------------------------------------------------------------ helpers


def first_name(contact: str) -> str:
    """'Mario (titolare)' -> 'Mario'. Uncertain or initial-only contacts return ''."""
    c = (contact or "").strip()
    if not c or "verificare" in c.lower():
        return ""
    c = re.split(r"[(/,]", c)[0].strip()
    token = c.split()[0] if c.split() else ""
    if len(token) < 2 or token.endswith(".") or not token.replace("'", "").isalpha():
        return ""
    return token[0].upper() + token[1:]


def mobile_number(phone: str) -> str:
    """Returns an international Italian mobile number for wa.me (e.g. 393451234567) or ''."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0039"):
        digits = digits[4:]
    elif digits.startswith("39") and len(digits) in (11, 12):
        digits = digits[2:]
    if digits.startswith("3") and len(digits) in (9, 10):
        return "39" + digits
    return ""


def whatsapp_link(number: str, text: str) -> str:
    return f"https://wa.me/{number}?text={quote(text)}"


def when_we_met(v: Venue) -> str:
    action = (v.last_action or "").lower()
    d = calendar_it.parse(v.last_contacted)
    if "telefon" in action or "chiamata" in action:
        return "al telefono"
    if d:
        return f"da {v.name} il {d.strftime('%d/%m')}"
    return f"da {v.name} nei giorni scorsi"


def base_values(v: Venue, today: date, signed_count: int, letter_link: str) -> dict[str, str]:
    return {
        "nome": first_name(v.contact),
        "nome_locale": v.name.strip(),
        "zona": v.zone.strip(),
        "n_locali": str(signed_count) if signed_count else "",
        "domani": calendar_it.tomorrow_label(today),
        "quando_ci_siamo_sentiti": when_we_met(v),
        "data_visita": (calendar_it.parse(v.last_contacted) or today).strftime("%d/%m")
        if v.last_contacted
        else "",
        "link_pdf": letter_link,
        "numero_coppie": "",
    }


# ------------------------------------------------------------------ planning


def plan(
    venues: list[Venue],
    today: date,
    replied: set[str] | None = None,
    letter_link: str = "",
) -> list[Action]:
    """replied: lower-cased venue names that answered (from the inbox check)."""
    replied = replied or set()
    signed = sum(1 for v in venues if v.prob_code == "90")
    actions: list[Action] = []

    for v in venues:
        if not v.name.strip():
            continue
        step = (v.mail_step or "").strip().lower()
        code = v.prob_code
        values = base_values(v, today, signed, letter_link)

        if code == "10":
            if not v.email.strip() or (v.last_action or "").upper().startswith("TODO"):
                continue
            if step in CLOSED_STEPS:
                continue
            if v.name.lower() in replied and step in ("1", "2"):
                actions.append(
                    Action(v, "info", "Ha risposto: leggila tu e dimmi come aggiornare il funnel", False, False, values)
                )
                continue
            kind = {"": "mail1", "1": "mail2", "2": "mail3"}.get(step)
            if not kind:
                continue
            if kind != "mail1":
                due = calendar_it.parse(v.mail_next)
                if due and due > today:
                    actions.append(
                        Action(v, "info", f"{ACTION_LABEL[kind]} dal {calendar_it.fmt(due)}", False, False, values)
                    )
                    continue
            actions.append(Action(v, kind, "Da inviare", True, True, values))

        elif code == "50":
            if step in ("4", "wa", "stop", "risposta"):
                continue
            if v.email.strip():
                actions.append(Action(v, "mail4", "Da inviare", True, True, values))
            elif mobile_number(v.phone):
                actions.append(Action(v, "whatsapp", "Apri WhatsApp e invia dal telefono", True, False, values))
            else:
                actions.append(Action(v, "info", "Nessuna mail e solo numero fisso: chiama", False, False, values))

    order = {"mail1": 1, "mail2": 2, "mail3": 3, "mail4": 0, "whatsapp": 4, "info": 9}
    actions.sort(key=lambda a: (order.get(a.kind, 9), a.venue.name.lower()))
    return actions


def next_due(kind: str, sent_on: date, days_mail_2: int, days_mail_3: int) -> str:
    if kind == "mail1":
        return calendar_it.fmt(calendar_it.add_working_days(sent_on, days_mail_2))
    if kind == "mail2":
        return calendar_it.fmt(calendar_it.add_working_days(sent_on, days_mail_3))
    return ""


_NOTE_FRAGMENT = re.compile(
    r",?\s*(?:Email [1-4]|Email 3 \(break up\)|Email lettera d'intenti|WhatsApp lettera d'intenti)"
    r"[^,]*?inviat[ao] il \d{2}/\d{2}/\d{4}",
)


def merge_note(old: str, fragment: str) -> str:
    """Keeps the previous note, replaces any earlier mailer fragment, appends the new one after a comma."""
    base = _NOTE_FRAGMENT.sub("", old or "").strip().rstrip(",").strip()
    return f"{base}, {fragment}" if base else fragment
