"""Aruba mailbox: SMTP sending, copy in the Sent folder, reply detection (headers only)."""

from __future__ import annotations

import imaplib
import re
import smtplib
import ssl
import time
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

FREE_MAIL = {
    "gmail.com", "googlemail.com", "libero.it", "hotmail.com", "hotmail.it", "outlook.com",
    "outlook.it", "live.com", "live.it", "yahoo.com", "yahoo.it", "icloud.com", "me.com",
    "tiscali.it", "alice.it", "virgilio.it", "tin.it", "fastwebnet.it", "email.it", "msn.com",
}


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


class Mailbox:
    def __init__(self, cfg, password: str):
        self.cfg = cfg
        self.password = password
        self._sent_folder: str | None = cfg.sent_folder or None

    # ------------------------------------------------------------- smtp
    def check_login(self) -> None:
        with smtplib.SMTP_SSL(self.cfg.smtp_host, self.cfg.smtp_port, context=ssl.create_default_context(), timeout=30) as s:
            s.login(self.cfg.sender_email, self.password)

    def send(self, msg: EmailMessage) -> None:
        rcpts = [a.strip() for f in ("To", "Cc") for a in (msg.get(f) or "").split(",") if a.strip()]
        with smtplib.SMTP_SSL(self.cfg.smtp_host, self.cfg.smtp_port, context=ssl.create_default_context(), timeout=60) as s:
            s.login(self.cfg.sender_email, self.password)
            s.send_message(msg, to_addrs=rcpts)
        try:
            self.save_to_sent(msg)
        except Exception as exc:  # the mail is sent anyway: just report it
            raise SentCopyError(str(exc)) from exc

    # ------------------------------------------------------------- imap
    def _imap(self) -> imaplib.IMAP4_SSL:
        m = imaplib.IMAP4_SSL(self.cfg.imap_host, self.cfg.imap_port, ssl_context=ssl.create_default_context())
        m.login(self.cfg.sender_email, self.password)
        return m

    def _find_sent_folder(self, m: imaplib.IMAP4_SSL) -> str:
        if self._sent_folder:
            return self._sent_folder
        typ, data = m.list()
        names = []
        for raw in data or []:
            line = raw.decode(errors="ignore") if isinstance(raw, bytes) else str(raw)
            mm = re.match(r'\((?P<flags>[^)]*)\)\s+"?[^"\s]*"?\s+(?P<name>.+)$', line)
            if not mm:
                continue
            name = mm.group("name").strip().strip('"')
            if "\\Sent" in mm.group("flags"):
                self._sent_folder = name
                return name
            names.append(name)
        for cand in names:
            low = cand.lower()
            if "sent" in low or "inviat" in low:
                self._sent_folder = cand
                return cand
        self._sent_folder = "INBOX.Sent"
        return self._sent_folder

    def save_to_sent(self, msg: EmailMessage) -> None:
        m = self._imap()
        try:
            folder = self._find_sent_folder(m)
            quoted = f'"{folder}"' if " " in folder else folder
            m.append(quoted, "\\Seen", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        finally:
            m.logout()

    def replied_venues(self, candidates: list[tuple[str, str, str]], today: date) -> set[str]:
        """candidates: (venue name, venue email, our Message-ID). Returns lower-cased names that wrote back.
        Only searches headers, nothing is opened or marked as read."""
        if not candidates:
            return set()
        since = (today - timedelta(days=self.cfg.reply_lookback_days)).strftime("%d-%b-%Y")
        found: set[str] = set()
        m = self._imap()
        try:
            m.select("INBOX", readonly=True)
            for name, email, msgid in candidates:
                for criteria in search_criteria(email, msgid, since):
                    typ, data = m.search(None, *criteria)
                    if typ == "OK" and data and data[0].split():
                        found.add(name.lower())
                        break
        finally:
            m.logout()
        return found


class SentCopyError(Exception):
    """The mail went out but the copy in 'Sent' could not be saved."""


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
