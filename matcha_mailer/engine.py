"""Glue between funnel, texts, mailbox and history log. No UI code here."""

from __future__ import annotations

import csv
import random
import time
from dataclasses import dataclass, field
from datetime import date, datetime

from matcha_mailer import calendar_it, config as config_mod, google_api, planner, texts as texts_mod
from matcha_mailer.funnel import Change, Funnel, open_funnel
from matcha_mailer.mailbox import Mailbox, SentCopyError, build_message
from matcha_mailer.planner import Action

LOG_PATH = config_mod.DATA_DIR / "invii.csv"


def render(action: Action, texts: texts_mod.Texts) -> None:
    """Fills subject/body of an action from the templates, unless the user edited them."""
    if action.edited or action.kind == "info":
        return
    tpl = texts.get(action.kind)
    v = action.values
    if action.kind in ("mail2", "mail3"):
        first = texts_mod.fill(texts.get("mail1").subject, v)
        action.subject = first if first.lower().startswith("re:") else f"Re: {first}"
    else:
        action.subject = texts_mod.fill(tpl.subject, v)
    action.body = texts_mod.fill(tpl.body, v)


def problems(action: Action) -> list[str]:
    """Placeholders still to fill by hand (e.g. {numero_coppie})."""
    return texts_mod.missing_placeholders(action.subject + "\n" + action.body)


def pause_seconds(cfg, rng: random.Random | None = None) -> float:
    """Random pause between two sends, so mails never leave in a burst."""
    lo, hi = sorted((max(0.0, cfg.pause_min), max(0.0, cfg.pause_max)))
    return (rng or random).uniform(lo, hi)


def estimated_minutes(cfg, n: int) -> int:
    """Rough total time for n sends: average pause between them plus ~3 s per send."""
    if n <= 0:
        return 0
    avg = (cfg.pause_min + cfg.pause_max) / 2
    return max(1, round(((n - 1) * avg + n * 3) / 60))


def sent_this_week(today: date) -> int:
    if not LOG_PATH.exists():
        return 0
    year, week, _ = today.isocalendar()
    n = 0
    with LOG_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = calendar_it.parse(row.get("data", ""))
            if d and d.isocalendar()[:2] == (year, week) and row.get("azione", "").startswith("mail"):
                n += 1
    return n


def already_sent() -> dict[tuple[str, str], str]:
    """(venue name lower-cased, action kind) -> date, from the local send log."""
    out: dict[tuple[str, str], str] = {}
    if LOG_PATH.exists():
        with LOG_PATH.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                out[(row.get("locale", "").lower(), row.get("azione", ""))] = row.get("data", "")
    return out


def _log(action: Action, to: str, msgid: str, today: date) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG_PATH.exists()
    with LOG_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["data", "ora", "locale", "azione", "destinatario", "oggetto", "message_id"])
        w.writerow([calendar_it.fmt(today), datetime.now().strftime("%H:%M"), action.venue.name,
                    action.kind, to, action.subject, msgid])


@dataclass
class Session:
    cfg: config_mod.Config
    funnel: Funnel
    session: object  # google AuthorizedSession
    texts: texts_mod.Texts
    mailbox: Mailbox | None = None
    _letter: bytes | None = field(default=None, repr=False)

    @classmethod
    def connect(cls, cfg: config_mod.Config) -> "Session":
        creds = google_api.get_credentials(cfg.client_secret, cfg.token_path)
        gc, auth_session = google_api.clients(creds)
        funnel = open_funnel(gc, cfg.funnel_id, cfg.funnel_sheet)
        texts = texts_mod.load_texts(config_mod.TEXTS_PATH)
        return cls(cfg, funnel, auth_session, texts)

    def reload_texts(self) -> None:
        self.texts = texts_mod.load_texts(config_mod.TEXTS_PATH)

    # ----------------------------------------------------------- planning
    def build_plan(self, today: date) -> tuple[list[Action], list[str]]:
        warnings: list[str] = []
        missing = self.funnel.missing_mailer_columns()
        if missing:
            warnings.append("Nel funnel mancano le colonne: " + ", ".join(missing))
        venues = self.funnel.load()
        replied: set[str] = set()
        if self.mailbox:
            candidates = [
                (v.name, v.email, v.mail_thread)
                for v in venues
                if v.prob_code == "10" and (v.mail_step or "").strip() in ("1", "2")
            ]
            try:
                replied = self.mailbox.replied_venues(candidates, today)
            except Exception as exc:
                warnings.append(f"Controllo risposte non riuscito ({exc}): i follow up restano da verificare a mano")
        actions = planner.plan(venues, today, replied, self.cfg.letter_pdf_link)
        sent = already_sent()
        for a in actions:
            when = sent.get((a.venue.name.lower(), a.kind))
            if a.selectable and when:
                # sent before but the funnel was not updated: never propose it twice
                a.status = f"Già inviata il {when} (registro locale): aggiorna il funnel"
                a.kind, a.selectable, a.selected = "info", False, False
            render(a, self.texts)
        return actions, warnings

    # ----------------------------------------------------------- sending
    def letter_pdf(self) -> bytes:
        if self._letter is None:
            self._letter = google_api.export_pdf(self.session, self.cfg.letter_doc_id)
        return self._letter

    def _message(self, action: Action, test: bool):
        t = self.texts
        to = self.cfg.sender_email if test else action.venue.email.strip()
        attachment = (self.cfg.letter_filename, self.letter_pdf()) if action.kind == "mail4" else None
        return build_message(
            sender_name=self.cfg.sender_name,
            sender_email=self.cfg.sender_email,
            to=to,
            cc=[] if test else self.cfg.cc,
            subject=("[PROVA] " if test else "") + action.subject,
            text=texts_mod.to_text(action.body, t.signature_text),
            html=texts_mod.to_html(action.body, t.signature_html),
            in_reply_to="" if test else (action.venue.mail_thread if action.kind in ("mail2", "mail3") else ""),
            attachment=attachment,
            unsubscribe=action.kind in ("mail1", "mail2", "mail3"),
        )

    def send_test(self, action: Action) -> None:
        msg = self._message(action, test=True)
        self.mailbox.send(msg)

    def send(self, action: Action, today: date) -> tuple[list[Change], str]:
        """Sends one mail and updates the funnel row (found by name). Returns (changes, warning)."""
        msg = self._message(action, test=False)
        warning = ""
        try:
            self.mailbox.send(msg)
        except SentCopyError as exc:
            warning = f"inviata, ma copia in Inviati non salvata ({exc})"
        msgid = msg["Message-ID"]
        _log(action, msg["To"], msgid, today)
        try:
            changes = self.funnel.update_by_name(action.venue.name, self._funnel_changes(action, today, msgid))
        except Exception as exc:
            changes = []
            warning = (warning + "; " if warning else "") + f"inviata ma funnel NON aggiornato ({exc})"
        return changes, warning

    def mark_whatsapp_sent(self, action: Action, today: date) -> list[Change]:
        _log(action, planner.mobile_number(action.venue.phone), "", today)
        return self.funnel.update_by_name(action.venue.name, self._funnel_changes(action, today, ""))

    def _funnel_changes(self, action: Action, today: date, msgid: str) -> dict[str, str]:
        v = action.venue
        when = calendar_it.fmt(today)
        verb = "inviato" if action.kind == "whatsapp" else "inviata"
        fragment = f"{planner.LAST_ACTION_VALUE[action.kind]} {verb} il {when}"
        changes = {
            "last_action": planner.LAST_ACTION_VALUE[action.kind],
            "last_contacted": when,
            "notes": planner.merge_note(v.notes, fragment),
            "mail_step": planner.STEP_MAIL[action.kind],
            "mail_last_sent": when,
            "mail_next": planner.next_due(action.kind, today, self.cfg.days_mail_2, self.cfg.days_mail_3),
        }
        if action.kind == "mail1":
            changes["mail_thread"] = msgid
        return changes

    def write_history(self, today: date, title: str, bullets: list[str]) -> None:
        if bullets:
            google_api.append_history(self.session, self.cfg.history_doc_id, calendar_it.fmt(today), title, bullets)


def describe(changes: list[Change], extra: str = "") -> str:
    """One history bullet per venue, listing old -> new values so every change can be restored."""
    if not changes:
        return ""
    venue = changes[0].venue
    parts = []
    for c in changes:
        if c.column == "Mail thread":
            parts.append("Mail thread impostato")
            continue
        old = f'"{c.old}"' if c.old else "vuoto"
        parts.append(f'{c.column}: {old} → "{c.new}"')
    text = f"{venue}: " + "; ".join(parts)
    return text + (f" ({extra})" if extra else "")


# ------------------------------------------------------------ shared by window and command line


def send_batch(session: "Session", actions: list[Action], today: date, log=print, sleep=time.sleep) -> tuple[int, list[str]]:
    """Sends the given mail actions one by one (random pause in between), updates the funnel
    and writes one history entry. Returns (sent count, failures)."""
    bullets, ok, failed = [], 0, []
    for i, a in enumerate(actions):
        if i:
            wait = pause_seconds(session.cfg)
            log(f"Pausa di {round(wait)} secondi prima della prossima mail…")
            sleep(wait)
        try:
            changes, warn = session.send(a, today)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{a.venue.name}: {exc}")
            log(f"✗ {a.venue.name}: non inviata ({exc})")
            continue
        ok += 1
        log(f"✓ {a.venue.name}: {a.label} inviata a {a.venue.email}" + (f" ({warn})" if warn else ""))
        extra = f"{a.label} inviata a {a.venue.email}" + (f"; {warn}" if warn else "")
        bullets.append(describe(changes, extra) or f"{a.venue.name}: {extra}")
    try:
        session.write_history(today, f"Mailer: {ok} mail inviate", bullets)
        if bullets:
            log("Cronologia aggiornata.")
    except Exception as exc:  # noqa: BLE001
        log(f"Attenzione: cronologia non aggiornata ({exc}). Dettagli in data/invii.csv")
    return ok, failed


def register_whatsapp(session: "Session", action: Action, today: date) -> None:
    changes = session.mark_whatsapp_sent(action, today)
    bullet = describe(changes, "WhatsApp con lettera d'intenti inviato") or f"{action.venue.name}: WhatsApp inviato"
    session.write_history(today, "Mailer: WhatsApp inviato", [bullet])


STEP_NOTES = {"stop": "ha chiesto di non essere più contattato", "risposta": "ha risposto, sequenza chiusa"}


def close_sequence(session: "Session", venue_name: str, value: str, today: date) -> list[Change]:
    """Sets 'Mail step' to stop/risposta for a venue (found by name) and logs it."""
    if value not in STEP_NOTES:
        raise ValueError("Valore ammesso: stop oppure risposta")
    changes = session.funnel.update_by_name(venue_name, {"mail_step": value})
    session.write_history(today, "Mailer: sequenza chiusa",
                          [describe(changes, STEP_NOTES[value]) or f"{venue_name}: Mail step già \"{value}\""])
    return changes

