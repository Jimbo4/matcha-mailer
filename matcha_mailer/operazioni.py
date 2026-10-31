"""Le operazioni del mailer: collegano funnel, testi, casella, registro invii e cronologia.

Le usano i comandi (cli.py), che si limitano a leggere gli argomenti e a stampare i risultati.
Qui non si stampa nulla: gli avanzamenti passano da una funzione `log`.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from datetime import date

from matcha_mailer import config as config_mod
from matcha_mailer import calendario, cronologia, google_api, planner, testi
from matcha_mailer.casella import InboxItem, Mailbox, SentCopyError, build_message, classify
from matcha_mailer.funnel import Change, Funnel, open_funnel
from matcha_mailer.planner import Action, Venue, norm
from matcha_mailer.registro import Registry


class OperationError(Exception):
    """Errore da riportare a Jacopo così com'è: dice sempre cosa fare."""


# ------------------------------------------------------------------ testi delle azioni


def render(action: Action, texts: testi.Texts) -> None:
    """Fills subject/body of an action from the templates, unless they were edited by hand."""
    if action.edited or action.kind == "info":
        return
    tpl = texts.get(action.kind)
    v = action.values
    if action.kind in ("mail2", "mail3"):
        first = action.thread_subject or testi.fill(texts.get("mail1").subject, v)
        action.subject = first if first.lower().startswith("re:") else f"Re: {first}"
    else:
        action.subject = testi.fill(tpl.subject, v)
    action.body = testi.fill(tpl.body, v)


def problems(action: Action) -> list[str]:
    """Placeholders still to fill by hand (e.g. {numero_coppie})."""
    return testi.missing_placeholders(action.subject + "\n" + action.body)


def parse_short_names(items: list[str]) -> dict[str, str]:
    """["Locale=Nome breve", ...] -> {norm(locale): "Nome breve"}."""
    out: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise OperationError(f"--nome '{item}': usa il formato \"Nome nel funnel=Nome nella mail\"")
        venue, short = (x.strip() for x in item.split("=", 1))
        if not venue or not short:
            raise OperationError(f"--nome '{item}': servono sia il nome nel funnel sia quello da usare nella mail")
        out[norm(venue)] = short
    return out


def apply_overrides(action: Action, texts: testi.Texts, *, short_name: str = "", values: list[str] | None = None,
                    subject: str | None = None, body_file: str | None = None) -> None:
    """Order: name used in the mail, then {placeholders}, then subject/body written by hand."""
    if short_name:
        action.values["nome_locale"] = short_name
        action.edited = False
        render(action, texts)
    for item in values or []:
        if "=" not in item:
            raise OperationError(f"--valore '{item}': usa il formato nome=valore, es. numero_coppie=12")
        key, val = item.split("=", 1)
        key = key.strip().strip("{}")
        action.subject = action.subject.replace("{" + key + "}", val)
        action.body = action.body.replace("{" + key + "}", val)
        action.edited = True
    if subject:
        action.subject, action.edited = subject, True
    if body_file:
        with open(body_file, encoding="utf-8") as f:
            action.body, action.edited = f.read().strip("\n"), True


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


# ------------------------------------------------------------------ sessione


@dataclass
class ActivationResult:
    planned: list[Venue] = field(default_factory=list)  # can be activated
    refused: list[str] = field(default_factory=list)  # "Locale: motivo"
    written: list[str] = field(default_factory=list)  # names now at "10 - nuovo" (after re-reading the funnel)


@dataclass
class Session:
    cfg: config_mod.Config
    funnel: Funnel
    google: object  # google AuthorizedSession (Docs, Drive)
    texts: testi.Texts
    mailbox: Mailbox | None = None
    registry: Registry = field(default_factory=Registry)
    _letter: bytes | None = field(default=None, repr=False)
    venues: list = field(default_factory=list, repr=False)  # last funnel read, used to explain missing actions

    @classmethod
    def connect(cls, cfg: config_mod.Config) -> "Session":
        creds = google_api.get_credentials(cfg.client_secret, cfg.token_path)
        gc, auth_session = google_api.clients(creds)
        funnel = open_funnel(gc, cfg.funnel_id, cfg.funnel_sheet)
        return cls(cfg, funnel, auth_session, testi.load_texts(config_mod.TEXTS_PATH))

    # ----------------------------------------------------------- piano del giorno
    def build_plan(self, today: date, revive: set[str] | None = None) -> tuple[list[Action], list[str]]:
        """revive: names of "00 - perso" venues Jacopo asked to contact anyway."""
        warnings: list[str] = []
        missing = self.funnel.missing_mailer_columns()
        if missing:
            warnings.append("Nel funnel mancano le colonne: " + ", ".join(missing))
        venues = self.funnel.load()
        self.venues = venues
        replied: set[str] = set()
        if self.mailbox:
            candidates = [
                (v.name, v.email, v.mail_thread)
                for v in venues
                if v.prob_code in ("10", "00") and (v.mail_step or "").strip() in ("1", "2")
            ]
            try:
                replied = self.mailbox.replied_venues(candidates, today)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Controllo risposte non riuscito ({exc}): i follow up restano da verificare a mano")
        actions = planner.plan(venues, today, replied, self.cfg.letter_pdf_link, revive)
        sent = self.registry.already_sent()
        first = self.registry.first_mail()
        for a in actions:
            when = sent.get((a.venue.name.lower(), a.kind))
            if a.selectable and when:
                # sent before but the funnel was not updated: never propose it twice
                a.status = f"Già inviata il {when} (registro locale): aggiorna il funnel"
                a.kind, a.selectable = "info", False
            m1 = first.get(a.venue.name.lower())
            if m1 and a.kind in ("mail2", "mail3"):
                a.thread_subject = m1.subject
                if m1.name_in_mail:
                    a.values["nome_locale"] = m1.name_in_mail
            render(a, self.texts)
        return actions, warnings

    def find(self, actions: list[Action], name: str, revived: bool = False) -> Action:
        """The action for a venue today. When there is none, explains why and what to do."""
        target = norm(name)
        exact = [a for a in actions if a.selectable and norm(a.venue.name) == target]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            raise OperationError(f"'{name}': più righe con lo stesso nome nel funnel, non procedo. "
                                 "Rinomina o elimina una delle due righe nel funnel, poi rilancia.")
        waiting = [a for a in actions if not a.selectable and norm(a.venue.name) == target]
        if waiting:
            raise OperationError(f"'{waiting[0].venue.name}': nessuna azione da fare oggi ({waiting[0].status})")
        rows = [v for v in self.venues if norm(v.name) == target]
        if len(rows) > 1:
            raise OperationError(f"'{name}': più righe con lo stesso nome nel funnel, non procedo. "
                                 "Rinomina o elimina una delle due righe nel funnel, poi rilancia.")
        if rows:
            raise OperationError(f"'{rows[0].name}': nessuna azione da fare oggi: {planner.explain(rows[0], revived)}")
        similar = sorted(v.name for v in self.venues if target and target in norm(v.name))
        hint = f" Forse intendevi: {', '.join(similar)}." if similar else ""
        raise OperationError(
            f"'{name}' non è nel funnel.{hint} Se è un locale nuovo, aggiungi una riga nel funnel con "
            "Nome attività, Zona e Mail, poi usa `attiva`."
        )

    # ----------------------------------------------------------- invio
    def letter_pdf(self) -> bytes:
        if self._letter is None:
            self._letter = google_api.export_pdf(self.google, self.cfg.letter_doc_id)
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
            text=testi.to_text(action.body, t.signature_text),
            html=testi.to_html(action.body, t.signature_html),
            in_reply_to="" if test else (action.venue.mail_thread if action.kind in ("mail2", "mail3") else ""),
            attachment=attachment,
            unsubscribe=action.kind in ("mail1", "mail2", "mail3"),
        )

    def send_test(self, action: Action) -> None:
        self.mailbox.send(self._message(action, test=True))

    def send(self, action: Action, today: date) -> tuple[list[Change], str]:
        """Sends one mail and updates the funnel row (found by name). Returns (changes, warning)."""
        msg = self._message(action, test=False)
        warning = ""
        try:
            self.mailbox.send(msg)
        except SentCopyError as exc:
            warning = f"inviata, ma copia in Inviati non salvata ({exc})"
        msgid = msg["Message-ID"]
        name_used = action.values.get("nome_locale", "")
        self.registry.add(today, action.venue.name, action.kind, msg["To"], action.subject, msgid,
                          name_used if name_used and name_used != action.venue.name else "")
        try:
            changes = self.funnel.update_by_name(action.venue.name, self._funnel_changes(action, today, msgid))
        except Exception as exc:  # noqa: BLE001
            changes = []
            warning = (warning + "; " if warning else "") + f"inviata ma funnel NON aggiornato ({exc})"
        return changes, warning

    def mark_whatsapp_sent(self, action: Action, today: date) -> list[Change]:
        self.registry.add(today, action.venue.name, action.kind, planner.mobile_number(action.venue.phone), "", "")
        return self.funnel.update_by_name(action.venue.name, self._funnel_changes(action, today, ""))

    def _funnel_changes(self, action: Action, today: date, msgid: str) -> dict[str, str]:
        v = action.venue
        when = calendario.fmt(today)
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
            cronologia.append_history(self.google, self.cfg.history_doc_id, calendario.fmt(today), title, bullets)

    # ----------------------------------------------------------- funnel: candidati e attivazione
    def candidates(self, zone: str = "", include_outside: bool = False) -> list[Venue]:
        """Venues with an email and an empty Probabilità, never worked on: they can get `attiva`."""
        venues = self.funnel.load()
        self.venues = venues
        return [v for v in venues
                if not planner.activation_problem(v)
                and (include_outside or planner.in_milan(v))
                and (not zone or norm(zone) == norm(v.zone))]

    def activate(self, names: list[str], today: date, confirm: bool) -> ActivationResult:
        """Sets Probabilità "10 - nuovo" (row found by name) only for venues that pass every check.
        Without confirm nothing is written. After writing, re-reads the funnel and logs the history."""
        res = ActivationResult()
        by_name: dict[str, list[Venue]] = {}
        for v in self.funnel.load():
            by_name.setdefault(norm(v.name), []).append(v)
        for name in names:
            rows = by_name.get(norm(name), [])
            if len(rows) != 1:
                res.refused.append(f"{name}: {len(rows)} righe con questo nome nel funnel, non scrivo")
                continue
            why = planner.activation_problem(rows[0])
            if why:
                res.refused.append(f"{rows[0].name}: {why}, non scrivo")
                continue
            res.planned.append(rows[0])
        if not confirm or not res.planned:
            return res
        bullets = []
        for v in res.planned:
            changes = self.funnel.update_by_name(v.name, {"probability": planner.NEW_PROBABILITY})
            if changes:
                bullets.append(cronologia.describe(changes, "attivato per la sequenza a freddo"))
        after = {norm(v.name): v for v in self.funnel.load()}
        for v in res.planned:
            now = after.get(norm(v.name))
            if now and now.probability == planner.NEW_PROBABILITY:
                res.written.append(v.name)
            else:
                res.refused.append(f"{v.name}: dopo la scrittura la Probabilità risulta "
                                   f"\"{now.probability if now else 'riga non trovata'}\", controlla il funnel")
        self.write_history(today, f"Mailer: {len(bullets)} locali attivati (Probabilità 10 - nuovo)", bullets)
        return res

    # ----------------------------------------------------------- casella
    def inbox(self, since: date) -> list[InboxItem]:
        """Every mail received since the given day, classified and linked to venues. Changes nothing."""
        ids = self.registry.message_ids()
        emails = {v.email.strip().lower(): v.name for v in self.funnel.load() if v.email.strip()}
        items = [classify(folder, raw, self.cfg.sender_email, ids, emails)
                 for folder, raw in self.mailbox.read_inbox(since)]
        return [i for i in items if i]


# ------------------------------------------------------------------ operazioni composte


def send_batch(session: Session, actions: list[Action], today: date, log=print,
               sleep=time.sleep) -> tuple[int, list[str]]:
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
        if a.lost and a.kind == "mail1":
            extra += "; locale \"00 - perso\" riattivato su richiesta, Probabilità invariata"
        bullets.append(cronologia.describe(changes, extra) or f"{a.venue.name}: {extra}")
    try:
        session.write_history(today, f"Mailer: {ok} mail inviate", bullets)
        if bullets:
            log("Cronologia aggiornata.")
    except Exception as exc:  # noqa: BLE001
        log(f"Attenzione: cronologia non aggiornata ({exc}). Gli invii sono in locale/registro/invii.csv")
    return ok, failed


def register_whatsapp(session: Session, action: Action, today: date) -> None:
    changes = session.mark_whatsapp_sent(action, today)
    bullet = cronologia.describe(changes, "WhatsApp con lettera d'intenti inviato") or f"{action.venue.name}: WhatsApp inviato"
    session.write_history(today, "Mailer: WhatsApp inviato", [bullet])


STEP_NOTES = {"stop": "ha chiesto di non essere più contattato", "risposta": "ha risposto, sequenza chiusa"}


def close_sequence(session: Session, venue_name: str, value: str, today: date) -> list[Change]:
    """Sets 'Mail step' to stop/risposta for a venue (found by name) and logs it.
    For stop, 'Ultima azione fatta' becomes STOP too, so the venue stands out in the funnel."""
    if value not in STEP_NOTES:
        raise OperationError("Valore ammesso: stop oppure risposta")
    fields = {"mail_step": value, "mail_next": ""}  # no next mail: the sequence is closed
    if value == "stop":
        fields["last_action"] = planner.STOP_VALUE
    changes = session.funnel.update_by_name(venue_name, fields)
    session.write_history(today, "Mailer: sequenza chiusa",
                          [cronologia.describe(changes, STEP_NOTES[value]) or f"{venue_name}: Mail step già \"{value}\""])
    return changes
