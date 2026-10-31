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
