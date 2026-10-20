"""Decides the next action for every venue in the funnel.

Rules (see README):
- "10 - nuovo" with an email, not "TODO: da visitare": cold sequence Mail 1 -> Mail 2 -> Mail 3.
- "50 - curioso" not yet followed up: Mail 4 (letter of intent) if there is an email,
  otherwise WhatsApp if there is a mobile number, otherwise a reminder to call.
- Anyone who replied (detected in the inbox) leaves the sequence: Jacopo reads the reply.
- "Mail step" = stop / risposta / 3 / 4 / WA means nothing else is sent.
- "00 - perso" is skipped unless Jacopo asks for it (revive / show_lost): then it follows the
  same cold sequence as "10 - nuovo". Its Probabilità stays "00"; Mail 2 and 3 follow from "Mail step".
"""

from __future__ import annotations

import re
import unicodedata
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

# Values the mailer writes in "Ultima azione fatta": they must also be in the funnel's dropdown list.
LAST_ACTION_VALUE = {
    "mail1": "Email automatica 1",
    "mail2": "Email automatica 2",
    "mail3": "Email automatica 3 (break up)",
    "mail4": "Email automatica lettera d'intenti",
    "whatsapp": "WhatsApp automatico lettera d'intenti",
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
    def lost(self) -> bool:
        """Venue marked "00 - perso" in the funnel, contacted only because Jacopo asked for it."""
        return self.venue.prob_code == "00"

    @property
    def label(self) -> str:
        base = ACTION_LABEL.get(self.kind, "")
        return f"{base} (locale perso)" if base and self.lost else base

    @property
    def is_mail(self) -> bool:
        return self.kind.startswith("mail")


# ------------------------------------------------------------------ helpers


def norm(s: str) -> str:
    """Case, accent and space insensitive key used to match venue names."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.casefold().split())


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


def _cold_sequence(v: Venue, step: str, today: date, replied: set[str], values: dict[str, str]) -> Action | None:
    """Mail 1 -> Mail 2 -> Mail 3 for a venue that has an email and is not "TODO: da visitare"."""
    if v.name.lower() in replied and step in ("1", "2"):
        return Action(v, "info", "Ha risposto: leggila tu e dimmi come aggiornare il funnel", False, False, values)
    kind = {"": "mail1", "1": "mail2", "2": "mail3"}.get(step)
    if not kind:
        return None
    if kind != "mail1":
        due = calendar_it.parse(v.mail_next)
        if due and due > today:
            return Action(v, "info", f"{ACTION_LABEL[kind]} dal {calendar_it.fmt(due)}", False, False, values)
    return Action(v, kind, "Da inviare", True, True, values)


def _cold_ok(v: Venue, step: str) -> bool:
    return bool(v.email.strip()) and not (v.last_action or "").upper().startswith("TODO") and step not in CLOSED_STEPS


def plan(
    venues: list[Venue],
    today: date,
    replied: set[str] | None = None,
    letter_link: str = "",
    revive: set[str] | None = None,
    show_lost: bool = False,
) -> list[Action]:
    """replied: lower-cased venue names that answered (from the inbox check).
    revive: venue names (any case) marked "00 - perso" that Jacopo asked to contact anyway: Mail 1 is proposed
    and selected. show_lost: every "00 - perso" venue never written to gets a Mail 1, not selected (window)."""
    replied = replied or set()
    revive = {norm(n) for n in (revive or set())}
    signed = sum(1 for v in venues if v.prob_code == "90")
    actions: list[Action] = []

    for v in venues:
        if not v.name.strip():
            continue
        step = (v.mail_step or "").strip().lower()
        code = v.prob_code
        values = base_values(v, today, signed, letter_link)

        if code == "10" or (code == "00" and step in ("1", "2")):
            # a lost venue already revived keeps going through Mail 2 and Mail 3 by itself
            if not _cold_ok(v, step):
                continue
            a = _cold_sequence(v, step, today, replied, values)
            if a:
                actions.append(a)

        elif code == "00":
            if step or not _cold_ok(v, step):
                continue
            if norm(v.name) in revive:
                actions.append(Action(v, "mail1", "Da inviare (locale perso, su tua richiesta)", True, True, values))
            elif show_lost:
                actions.append(Action(v, "mail1", "Locale perso: spunta per riattivarlo", True, False, values))

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
    actions.sort(key=lambda a: (order.get(a.kind, 9), a.lost, a.venue.name.lower()))
    return actions


STEP_EXPLAIN = {
    "3": "la sequenza è finita (Mail 3 già inviata)",
    "4": "la lettera d'intenti è già stata inviata (Mail step 4)",
    "wa": "la lettera d'intenti è già stata inviata su WhatsApp (Mail step WA)",
    "stop": "ha chiesto di non essere più contattato (Mail step stop): non va riscritto",
    "risposta": "ha già risposto (Mail step risposta): la sequenza è chiusa",
}


def explain(v: Venue, revived: bool = False) -> str:
    """Why a venue has no action today and which operations would give it one, in plain words for Jacopo."""
    step = (v.mail_step or "").strip().lower()
    code = v.prob_code
    prob = (v.probability or "").strip() or "vuota"
    if step in STEP_EXPLAIN:
        return f"{STEP_EXPLAIN[step]}. Per ricominciare da capo svuota a mano 'Mail step' nel funnel."
    if code in ("10", "00") and (v.last_action or "").upper().startswith("TODO"):
        return ("in 'Ultima azione fatta' c'è \"TODO: da visitare\": il mailer non scrive ai locali da visitare. "
                "Per scrivergli comunque cambia 'Ultima azione fatta' nel funnel (es. \"Email\"), poi rilancia.")
    if code in ("10", "00", "50") and not v.email.strip():
        extra = " Con un cellulare puoi usare WhatsApp solo da \"50 - curioso\"." if code != "50" else ""
        return (f"nel funnel manca la mail (Probabilità \"{prob}\"). "
                f"Aggiungila nella colonna 'Mail', poi rilancia.{extra}")
    if code == "00" and not revived:
        why = f" Nota nel funnel: \"{v.notes.strip()}\"." if (v.notes or "").strip() else ""
        return ("è segnato \"00 - perso\" e il mailer lo salta finché non lo chiedi tu." + why +
                " Per scrivergli comunque: aggiungi --riattiva al comando (nella finestra: spunta "
                "\"Mostra anche i persi\"). Riceve la Mail 1 e poi il resto della sequenza; Probabilità resta 00.")
    if code == "90":
        return "ha già firmato la lettera d'intenti (90): nessuna mail della sequenza."
    if code not in ("10", "50", "00"):
        return (f"Probabilità \"{prob}\" non prevista dal mailer. "
                "Imposta \"10 - nuovo\" (sequenza a freddo) o \"50 - curioso\" (lettera d'intenti), poi rilancia.")
    return "nessuna regola della sequenza si applica oggi: controlla Probabilità, Mail, Ultima azione e Mail step."


def next_due(kind: str, sent_on: date, days_mail_2: int, days_mail_3: int) -> str:
    if kind == "mail1":
        return calendar_it.fmt(calendar_it.add_working_days(sent_on, days_mail_2))
    if kind == "mail2":
        return calendar_it.fmt(calendar_it.add_working_days(sent_on, days_mail_3))
    return ""


_NOTE_FRAGMENT = re.compile(
    r",?\s*(?:Email (?:automatica )?(?:[1-4]|3 \(break up\)|lettera d'intenti)|WhatsApp (?:automatico )?lettera d'intenti)"
    r"[^,]*?inviat[ao] il \d{2}/\d{2}/\d{4}",
)


def merge_note(old: str, fragment: str) -> str:
    """Keeps the previous note, replaces any earlier mailer fragment, appends the new one after a comma."""
    base = _NOTE_FRAGMENT.sub("", old or "").strip().rstrip(",").strip()
    return f"{base}, {fragment}" if base else fragment
