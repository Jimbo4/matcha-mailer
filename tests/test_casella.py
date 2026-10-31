"""Classificazione della casella (comando casella) e secondo tentativo SMTP."""

import smtplib
from email.message import EmailMessage

import pytest

from matcha_mailer import casella
from matcha_mailer.casella import Mailbox, NotSentError, UncertainSendError, classify

IDS = {"179@matchadating.it": "Bar Uno"}
EMAILS = {"info@baruno.it": "Bar Uno", "pubdue@gmail.com": "Pub Due"}


def mail(sender, subject, body="", **headers):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = sender, "jacopo@matchadating.it", subject
    m["Date"] = "Tue, 20 Oct 2026 17:07:10 +0200"
    for k, v in headers.items():
        m[k.replace("_", "-")] = v
    m.set_content(body)
    return m


def kind(m):
    item = classify("INBOX", m.as_bytes(), "jacopo@matchadating.it", IDS, EMAILS)
    return (item.kind, item.venues) if item else None


def test_apple_mail_stop_and_reply():
    assert kind(mail("info@baruno.it", "stop", "Mail ha inviato questo messaggio per annullare l’iscrizione a “stop”.")) \
        == ("stop", ["Bar Uno"])
    assert kind(mail("pubdue@gmail.com", "Re: Partnership", "Ci interessa, chiamami")) == ("risposta", ["Pub Due"])
    assert kind(mail("altro@baruno.it", "Re: Partnership", "Sono il socio")) == ("risposta", ["Bar Uno"])  # same domain
    assert kind(mail("pubdue@gmail.com", "Re: Partnership", "Non vogliamo essere contattati")) == ("stop", ["Pub Due"])


def test_dmarc_own_copies_and_others():
    assert kind(mail("noreply-dmarc-support@google.com", "Report domain: matchadating.it Submitter: google.com")) \
        == ("dmarc", [])
    assert kind(mail("dmarcreport@microsoft.com", "[Preview] Report Domain: matchadating.it Submitter: x")) == ("dmarc", [])
    assert kind(mail("Jacopo <jacopo@matchadating.it>", "Partnership Bar Uno x Matcha")) is None
    assert kind(mail("amico@gmail.com", "ciao", "come va?")) == ("altro", [])


def report(report_type, inner_type, original):
    m = EmailMessage()
    m["From"], m["Subject"] = "feedback@provider.com", "report"
    m.set_content("human readable part")
    m.make_mixed()
    m.replace_header("Content-Type", f'multipart/report; report-type={report_type}')
    status = EmailMessage()
    status.set_content("Feedback-Type: abuse\n", subtype="plain")
    status.replace_header("Content-Type", inner_type)
    m.attach(status)
    orig = EmailMessage()
    orig.set_content(original, subtype="plain")
    orig.replace_header("Content-Type", "text/rfc822-headers")
    m.attach(orig)
    return m


def test_spam_report_and_bounce_are_linked_to_venue():
    arf = report("feedback-report", "message/feedback-report", "Message-ID: <179@matchadating.it>\nTo: info@baruno.it")
    assert kind(arf) == ("spam", ["Bar Uno"])
    dsn = (b"From: MAILER-DAEMON@aruba.it\r\nSubject: Undelivered Mail\r\nMIME-Version: 1.0\r\n"
           b'Content-Type: multipart/report; report-type=delivery-status; boundary="b"\r\n\r\n'
           b"--b\r\nContent-Type: text/plain\r\n\r\nNon consegnata\r\n"
           b"--b\r\nContent-Type: message/delivery-status\r\n\r\nFinal-Recipient: rfc822; pubdue@gmail.com\r\n\r\n"
           b"--b--\r\n")
    item = classify("INBOX", dsn, "jacopo@matchadating.it", IDS, EMAILS)
    assert (item.kind, item.venues) == ("rimbalzo", ["Pub Due"])


def test_casella_command_groups_and_suggests_stop(env, capsys):
    raw = mail("info@baruno.it", "stop", "annullare l'iscrizione").as_bytes()
    env["mb"].inbox = [("INBOX", raw), ("INBOX", mail("noreply@dmarc.yahoo.com", "Report Domain: x").as_bytes())]
    assert env["run"]("casella", "--dal", "19/10/2026") == 0
    out = capsys.readouterr().out
    assert "## Richieste di non essere contattati (1)" in out and "locale: Bar Uno" in out
    assert "## Report DMARC" in out and 'segna "Bar Uno" stop --conferma' in out
    assert env["sheet"].writes == []  # reading changes nothing


# ------------------------------------------------------------------ SMTP


class FakeSMTP:
    script = []  # one entry per connection: "ok", "drop" (connection closed) or "auth"
    sent = []
    fail_send = None

    def __init__(self, host, port, context=None, timeout=None):
        step = FakeSMTP.script.pop(0)
        if step == "drop":
            raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
        self.step = step

    def login(self, user, pw):
        if self.step == "auth":
            raise smtplib.SMTPAuthenticationError(535, b"bad")

    def send_message(self, msg, to_addrs=None):
        if FakeSMTP.fail_send:
            raise FakeSMTP.fail_send
        FakeSMTP.sent.append(msg)

    def quit(self):
        pass


@pytest.fixture
def smtp(monkeypatch, cfg):
    FakeSMTP.script, FakeSMTP.sent, FakeSMTP.fail_send = [], [], None
    monkeypatch.setattr(casella.smtplib, "SMTP_SSL", FakeSMTP)
    waits = []
    mb = Mailbox(cfg, "pw", sleep=waits.append, retry_waits=(20, 40))
    mb.save_to_sent = lambda msg: None
    return mb, waits


def test_dropped_connection_is_retried(smtp):
    mb, waits = smtp
    FakeSMTP.script = ["drop", "drop", "ok"]
    mb.send(EmailMessage())
    assert len(FakeSMTP.sent) == 1 and waits == [20, 40]


def test_gives_up_after_retries_and_says_not_sent(smtp):
    mb, waits = smtp
    FakeSMTP.script = ["drop", "drop", "drop"]
    with pytest.raises(NotSentError):
        mb.send(EmailMessage())
    assert FakeSMTP.sent == []


def test_wrong_password_is_not_retried(smtp):
    mb, waits = smtp
    FakeSMTP.script = ["auth"]
    with pytest.raises(smtplib.SMTPAuthenticationError):
        mb.send(EmailMessage())
    assert waits == []


def test_error_during_delivery_is_uncertain_and_not_retried(smtp):
    mb, waits = smtp
    FakeSMTP.script = ["ok"]
    FakeSMTP.fail_send = smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
    with pytest.raises(UncertainSendError, match="potrebbe essere partita"):
        mb.send(EmailMessage())
    assert waits == [] and FakeSMTP.script == []


def test_own_follow_up_copies_never_count_as_replies():
    from matcha_mailer.casella import search_criteria

    crit = search_criteria("info@baruno.it", "<1@matchadating.it>", "19-Oct-2026", "Jacopo@matchadating.it")
    assert crit and all(c[-3:] == ["NOT", "FROM", '"jacopo@matchadating.it"'] for c in crit)
    assert ["HEADER", "In-Reply-To", '"<1@matchadating.it>"', "NOT", "FROM", '"jacopo@matchadating.it"'] in crit


def test_casella_does_not_suggest_stop_twice(env, capsys):
    from conftest import row

    r = row(env["sheet"], "Bar Uno")
    r[7] = "STOP"
    env["mb"].inbox = [("INBOX", mail("info@baruno.it", "stop", "stop").as_bytes())]
    assert env["run"]("casella", "--dal", "19/10/2026") == 0
    out = capsys.readouterr().out
    assert "(già STOP nel funnel)" in out and "Da segnare come stop" not in out


# ------------------------------------------------------------------ risposte automatiche e lettura leggera

NIKS_LIKE = "Grazie per aver contattato il locale.\nVi risponderemo al più presto.\n\nOrari di apertura: 18-02"


def test_auto_reply_detection():
    from matcha_mailer.casella import _parse, is_auto_reply

    assert is_auto_reply(_parse(mail("info@baruno.it", "Re: Partnership", NIKS_LIKE).as_bytes()))
    assert is_auto_reply(_parse(mail("info@baruno.it", "Re: Partnership", "ciao", Auto_Submitted="auto-replied").as_bytes()))
    assert is_auto_reply(_parse(mail("info@baruno.it", "Risposta automatica: Partnership", "").as_bytes()))
    assert not is_auto_reply(_parse(mail("info@baruno.it", "Re: Partnership", "Ci interessa, chiamami domani").as_bytes()))
    assert not is_auto_reply(_parse(mail("info@baruno.it", "Re", "x", Auto_Submitted="no").as_bytes()))
    assert kind(mail("info@baruno.it", "Re: Partnership", NIKS_LIKE)) == ("automatica", ["Bar Uno"])


class FakeIMAP:
    """Minimal IMAP: every search returns every message; fetch records what was downloaded."""

    def __init__(self, messages):
        self.messages = {str(i + 1).encode(): raw for i, raw in enumerate(messages)}
        self.fetched = []

    def login(self, *a):
        pass

    def logout(self):
        pass

    def list(self):
        return "OK", [b'(\\HasNoChildren) "." INBOX', b'(\\HasNoChildren) "." INBOX.SPAM']

    def select(self, folder, readonly=False):
        self.folder = folder
        return "OK", [b"1"]

    def search(self, charset, *criteria):
        return "OK", [b" ".join(self.messages) if self.folder == "INBOX" else b""]

    def fetch(self, num, what):
        raw = self.messages[num]
        head, _, body = raw.partition(b"\r\n\r\n") if b"\r\n\r\n" in raw else raw.partition(b"\n\n")
        self.fetched.append((num, what))
        if what == "(BODY.PEEK[HEADER])":
            data = head + b"\r\n\r\n"
        elif what.startswith("(BODY.PEEK[TEXT]<0."):
            data = body[: int(what.split(".")[2].rstrip(">)"))]
        else:
            data = raw
        return "OK", [(num + b" (BODY[] {%d}" % len(data), data), b")"]


def big_mail():
    m = mail("umberto@matchadating.it", "Newsletter", "Testo della newsletter")
    m.add_attachment(b"x" * 300000, maintype="image", subtype="png", filename="foto.png")
    return m


@pytest.fixture
def imap(monkeypatch, cfg):
    def make(messages):
        fake = FakeIMAP([m.as_bytes() for m in messages])
        monkeypatch.setattr(casella.imaplib, "IMAP4_SSL", lambda *a, **k: fake)
        return Mailbox(cfg, "pw"), fake
    return make


def test_read_inbox_never_downloads_attachments(imap):
    dmarc = mail("noreply-dmarc-support@google.com", "Report domain: matchadating.it Submitter: google.com")
    dmarc.add_attachment(b"z" * 200000, maintype="application", subtype="zip", filename="r.zip")
    own = mail("Jacopo <jacopo@matchadating.it>", "Partnership Bar Uno x Matcha", "copia in Cc")
    mb, fake = imap([dmarc, own, big_mail(), mail("info@baruno.it", "Re: Partnership", "Ci interessa")])
    items = mb.read_inbox(__import__("datetime").date(2026, 10, 19))
    assert len(items) == 3  # own copy skipped
    assert all(what != "(BODY.PEEK[])" for _, what in fake.fetched)  # nothing fetched whole
    assert [w for n, w in fake.fetched if n in (b"1", b"2")] == ["(BODY.PEEK[HEADER])"] * 2  # headers only
    sizes = [len(raw) for _, raw in items]
    assert max(sizes) < 80000  # the 300 KB image never came down
    kinds = [classify(f, raw, "jacopo@matchadating.it", IDS, EMAILS).kind for f, raw in items]
    assert kinds == ["dmarc", "altro", "risposta"]


def test_replied_venues_ignores_auto_replies(imap):
    mb, _ = imap([mail("info@baruno.it", "Re: Partnership", NIKS_LIKE)])
    today = __import__("datetime").date(2026, 10, 31)
    assert mb.replied_venues([("Bar Uno", "info@baruno.it", "<1@matchadating.it>")], today) == set()
    assert mb.auto_replies == {"bar uno"}
    mb, _ = imap([mail("info@baruno.it", "Re: Partnership", NIKS_LIKE), mail("info@baruno.it", "Re: Re:", "Sì, passate")])
    assert mb.replied_venues([("Bar Uno", "info@baruno.it", "<1@matchadating.it>")], today) == {"bar uno"}
