"""Casella Aruba: invio SMTP, copia in Posta inviata, lettura delle risposte e della casella intera.

La lettura apre le cartelle in sola lettura e usa BODY.PEEK: nessuna mail viene segnata come letta.
"""

from __future__ import annotations

import email
import html
import imaplib
import re
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from email import policy
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parseaddr, parsedate_to_datetime

FREE_MAIL = {
    "gmail.com", "googlemail.com", "libero.it", "hotmail.com", "hotmail.it", "outlook.com",
    "outlook.it", "live.com", "live.it", "yahoo.com", "yahoo.it", "icloud.com", "me.com",
    "tiscali.it", "alice.it", "virgilio.it", "tin.it", "fastwebnet.it", "email.it", "msn.com",
}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def build_message(
    *,
    sender_name: str,
    sender_email: str,
    to: str,
    cc: list[str],
    subject: str,
    text: str,
    html: str,
    in_reply_to: str = "",
    attachment: tuple[str, bytes] | None = None,
    unsubscribe: bool = False,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((sender_name, sender_email))
    msg["To"] = to
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    domain = sender_email.split("@")[-1]
    msg["Message-ID"] = make_msgid(domain=domain)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    if unsubscribe:
        msg["List-Unsubscribe"] = f"<mailto:{sender_email}?subject=stop>"
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    if attachment:
        name, data = attachment
        msg.add_attachment(data, maintype="application", subtype="pdf", filename=name)
    return msg


class SentCopyError(Exception):
    """La mail è partita ma la copia in Posta inviata non è stata salvata."""


class NotSentError(Exception):
    """Aruba non ha accettato la connessione o il login: la mail non è partita, si può riprovare."""


class UncertainSendError(Exception):
    """Errore durante la consegna ad Aruba: la mail potrebbe essere partita. Non riprovare senza controllare."""


class Mailbox:
    def __init__(self, cfg, password: str, sleep=time.sleep, retry_waits: tuple[float, ...] = (20, 40)):
        self.cfg = cfg
        self.password = password
        self.sleep = sleep
        self.retry_waits = retry_waits
        self._sent_folder: str | None = cfg.sent_folder or None

    # ------------------------------------------------------------- smtp
    def _smtp(self, timeout: int = 60) -> smtplib.SMTP_SSL:
        """Connection + login, retried when Aruba drops the connection (nothing has been sent yet)."""
        waits = list(self.retry_waits)
        while True:
            try:
                s = smtplib.SMTP_SSL(self.cfg.smtp_host, self.cfg.smtp_port,
                                     context=ssl.create_default_context(), timeout=timeout)
                s.login(self.cfg.sender_email, self.password)
                return s
            except smtplib.SMTPAuthenticationError:
                raise
            except (smtplib.SMTPException, OSError) as exc:
                if not waits:
                    raise NotSentError(f"Aruba non accetta la connessione ({exc}); mail non inviata") from exc
                self.sleep(waits.pop(0))

    def check_login(self) -> None:
        with self._smtp(timeout=30):
            pass

    def send(self, msg: EmailMessage) -> None:
        rcpts = [a.strip() for f in ("To", "Cc") for a in (msg.get(f) or "").split(",") if a.strip()]
        s = self._smtp()
        try:
            s.send_message(msg, to_addrs=rcpts)
        except smtplib.SMTPRecipientsRefused as exc:
            raise NotSentError(f"destinatario rifiutato da Aruba ({exc})") from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise UncertainSendError(
                f"errore durante la consegna ad Aruba ({exc}): la mail potrebbe essere partita. "
                "Controlla in Posta inviata o la copia in Cc prima di riprovare"
            ) from exc
        finally:
            try:
                s.quit()
            except Exception:
                pass
        try:
            self.save_to_sent(msg)
        except Exception as exc:  # the mail is sent anyway: just report it
            raise SentCopyError(str(exc)) from exc

    # ------------------------------------------------------------- imap
    def _imap(self) -> imaplib.IMAP4_SSL:
        m = imaplib.IMAP4_SSL(self.cfg.imap_host, self.cfg.imap_port, ssl_context=ssl.create_default_context())
        m.login(self.cfg.sender_email, self.password)
        return m

    @staticmethod
    def _folders(m: imaplib.IMAP4_SSL) -> list[tuple[str, str]]:
        """(flags, name) of every folder."""
        out = []
        typ, data = m.list()
        for raw in data or []:
            line = raw.decode(errors="ignore") if isinstance(raw, bytes) else str(raw)
            mm = re.match(r'\((?P<flags>[^)]*)\)\s+"?[^"\s]*"?\s+(?P<name>.+)$', line)
            if mm:
                out.append((mm.group("flags"), mm.group("name").strip().strip('"')))
        return out

    def _find_sent_folder(self, m: imaplib.IMAP4_SSL) -> str:
        if self._sent_folder:
            return self._sent_folder
        folders = self._folders(m)
        for flags, name in folders:
            if "\\Sent" in flags:
                self._sent_folder = name
                return name
        for _, name in folders:
            if "sent" in name.lower() or "inviat" in name.lower():
                self._sent_folder = name
                return name
        self._sent_folder = "INBOX.Sent"
        return self._sent_folder

    def save_to_sent(self, msg: EmailMessage) -> None:
        m = self._imap()
        try:
            folder = self._find_sent_folder(m)
            m.append(_quote(folder), "\\Seen", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        finally:
            m.logout()

    def replied_venues(self, candidates: list[tuple[str, str, str]], today: date) -> set[str]:
        """candidates: (venue name, venue email, our Message-ID). Returns lower-cased names that wrote back.
        Only searches headers, nothing is opened or marked as read."""
        if not candidates:
            return set()
        since = imap_date(today - timedelta(days=self.cfg.reply_lookback_days))
        found: set[str] = set()
        m = self._imap()
        try:
            m.select("INBOX", readonly=True)
            for name, venue_email, msgid in candidates:
                for criteria in search_criteria(venue_email, msgid, since):
                    typ, data = m.search(None, *criteria)
                    if typ == "OK" and data and data[0].split():
                        found.add(name.lower())
                        break
        finally:
            m.logout()
        return found

    def read_replies(self, candidates: list[tuple[str, str, str]], today: date) -> list["Reply"]:
        """Same search as replied_venues, but also reads each reply. Mails sent by us are skipped."""
        if not candidates:
            return []
        since = imap_date(today - timedelta(days=self.cfg.reply_lookback_days))
        out: list[Reply] = []
        m = self._imap()
        try:
            m.select("INBOX", readonly=True)
            for name, venue_email, msgid in candidates:
                nums: list[bytes] = []
                for criteria in search_criteria(venue_email, msgid, since):
                    typ, data = m.search(None, *criteria)
                    if typ == "OK" and data:
                        nums += [n for n in data[0].split() if n not in nums]
                for num in nums:
                    raw = _fetch(m, num)
                    if not raw:
                        continue
                    r = parse_reply(name, raw)
                    if r.sender.lower() != self.cfg.sender_email.lower():
                        out.append(r)
        finally:
            m.logout()
        out.sort(key=lambda r: r.venue.lower())
        return out

    def read_inbox(self, since: date) -> list[tuple[str, bytes]]:
        """(folder, raw message) for every mail since the given day in INBOX and in the spam folder."""
        out: list[tuple[str, bytes]] = []
        m = self._imap()
        try:
            names = [n for _, n in self._folders(m)]
            targets = ["INBOX"] + [n for n in names if re.search(r"spam|junk|indesiderat", n, re.I)]
            for folder in targets:
                typ, _ = m.select(_quote(folder), readonly=True)
                if typ != "OK":
                    continue
                typ, data = m.search(None, "SINCE", imap_date(since))
                for num in (data[0].split() if typ == "OK" and data and data[0] else []):
                    raw = _fetch(m, num)
                    if raw:
                        out.append((folder, raw))
        finally:
            m.logout()
        return out


# ------------------------------------------------------------------ helpers


def _quote(folder: str) -> str:
    return f'"{folder}"' if " " in folder else folder


def _fetch(m: imaplib.IMAP4_SSL, num: bytes) -> bytes | None:
    typ, data = m.fetch(num, "(BODY.PEEK[])")
    if typ != "OK":
        return None
    return next((part[1] for part in data or [] if isinstance(part, tuple)), None)


def imap_date(d: date) -> str:
    return f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year}"


def search_criteria(email: str, msgid: str, since: str) -> list[list[str]]:
    email = (email or "").strip().lower()
    out: list[list[str]] = []
    if email:
        out.append(["SINCE", since, "FROM", f'"{email}"'])
        domain = email.split("@")[-1]
        if domain and domain not in FREE_MAIL:
            out.append(["SINCE", since, "FROM", f'"@{domain}"'])
    if msgid:
        out.append(["HEADER", "In-Reply-To", f'"{msgid}"'])
        out.append(["HEADER", "References", f'"{msgid}"'])
    return out


@dataclass
class Reply:
    venue: str
    sender: str
    when: str  # "gg/mm/aaaa hh:mm"
    subject: str
    text: str  # without the quoted original


_QUOTE_START = re.compile(
    r"^(>|-{2,}\s*(original message|messaggio originale)|(il|on)\b.*\b(ha scritto|wrote)\s*:|"
    r"(da|from)\s*:.*@|inviato da |sent from )",
    re.IGNORECASE,
)


def strip_quoted(text: str) -> str:
    """Keeps only what the venue wrote: stops at the quoted original mail or the phone signature."""
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if _QUOTE_START.match(line.strip()):
            break
        lines.append(line.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", "", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", s)
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def body_text(msg) -> str:
    body = msg.get_body(preferencelist=("plain", "html"))
    if body is None:
        return ""
    try:
        text = body.get_content()
    except Exception:
        return ""
    return _html_to_text(text) if body.get_content_type() == "text/html" else text


def _when(msg) -> str:
    try:
        return parsedate_to_datetime(msg["Date"]).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(msg["Date"] or "")


def parse_reply(venue: str, raw: bytes) -> Reply:
    msg = email.message_from_bytes(raw, policy=policy.default)
    return Reply(venue, parseaddr(str(msg["From"] or ""))[1], _when(msg), str(msg["Subject"] or ""),
                 strip_quoted(body_text(msg)))


# ------------------------------------------------------------------ whole inbox (comando casella)

KINDS = {
    "stop": "Richieste di non essere contattati",
    "spam": "Segnalazioni di spam",
    "rimbalzo": "Mail non consegnate (rimbalzi)",
    "risposta": "Risposte dei locali",
    "altro": "Altre mail",
    "dmarc": "Report DMARC (solo statistiche di autenticazione, nessun destinatario)",
}
_STOP_WORDS = re.compile(
    r"^\s*(stop|unsubscribe|annulla(re)? (l'|l’)?iscrizione|cancellami|disiscrivi|rimuovi)", re.IGNORECASE)
_STOP_PHRASES = re.compile(
    r"annullare l[’']iscrizione|non (voglio|vogliamo) (più )?essere contattat|non contattateci|"
    r"non scriveteci più|rimuovete(mi|ci)", re.IGNORECASE)


@dataclass
class InboxItem:
    folder: str
    kind: str
    when: str
    sender: str
    subject: str
    venues: list[str] = field(default_factory=list)
    text: str = ""


def _report_type(msg) -> str:
    """'feedback-report' (segnalazione spam), 'delivery-status' (rimbalzo) or ''."""
    for part in msg.walk():
        ct = part.get_content_type()
        if ct == "multipart/report":
            return (part.get_param("report-type") or "").lower()
        if ct == "message/feedback-report":
            return "feedback-report"
        if ct == "message/delivery-status":
            return "delivery-status"
    return ""


def _all_text(raw: bytes, msg) -> str:
    """Raw message plus every decoded part (attachments included), lower-cased, for matching."""
    blob = [raw.decode("utf-8", errors="ignore")]
    for part in msg.walk():
        if part.is_multipart():
            continue
        try:
            payload = part.get_payload(decode=True)
        except Exception:
            payload = None
        if payload:
            blob.append(payload.decode("utf-8", errors="ignore"))
    return "\n".join(blob).lower()


def classify(folder: str, raw: bytes, own_email: str, message_ids: dict[str, str],
             venue_emails: dict[str, str]) -> InboxItem | None:
    """message_ids: our Message-ID (lower, no <>) -> venue. venue_emails: venue email (lower) -> venue.
    Returns None for mails sent by us (copies in Cc)."""
    msg = email.message_from_bytes(raw, policy=policy.default)
    sender = parseaddr(str(msg["From"] or ""))[1].lower()
    if sender == own_email.lower():
        return None
    subject = str(msg["Subject"] or "")
    text = re.sub(r"\s+", " ", strip_quoted(body_text(msg))).strip()
    blob = _all_text(raw, msg)
    by_id = {v for k, v in message_ids.items() if k and k in blob}
    from_venue = venue_emails.get(sender, "")
    if not from_venue and "@" in sender:
        domain = sender.split("@")[-1]
        if domain not in FREE_MAIL:
            from_venue = next((v for e, v in venue_emails.items() if e.endswith("@" + domain)), "")
    by_addr = {v for e, v in venue_emails.items() if e and e in blob}
    report = _report_type(msg)

    if re.match(r"^\s*(\[preview\]\s*)?report domain:", subject, re.I) or "dmarc" in sender:
        kind, venues = "dmarc", []
    elif report == "feedback-report" or "abuse" in sender.split("@")[0]:
        kind, venues = "spam", sorted(by_id or by_addr)
    elif report == "delivery-status" or re.match(r"^(mailer-daemon|postmaster)@", sender):
        kind, venues = "rimbalzo", sorted(by_id or by_addr)
    elif (from_venue or by_id) and (_STOP_WORDS.match(subject) or _STOP_WORDS.match(text) or _STOP_PHRASES.search(text)):
        kind, venues = "stop", sorted({from_venue} - {""} or by_id)
    elif from_venue or by_id:
        kind, venues = "risposta", sorted({from_venue} - {""} or by_id)
    else:
        kind, venues = "altro", []
    return InboxItem(folder, kind, _when(msg), sender, subject, venues, text[:400])
