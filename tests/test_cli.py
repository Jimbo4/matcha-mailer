from dataclasses import replace
from datetime import date

import pytest

from matcha_mailer import cli, engine, texts
from matcha_mailer.funnel import Funnel

TODAY = date(2026, 10, 19)  # Monday


class FakeMailbox:
    def __init__(self):
        self.sent = []

    def replied_venues(self, candidates, today):
        return set()

    def check_login(self):
        pass

    def send(self, msg):
        self.sent.append(msg)


@pytest.fixture
def env(cfg, sheet, monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "LOG_PATH", tmp_path / "invii.csv")
    sheet.values.append(["Firmato", "", "Isola", "", "", "f@f.it", "90 - firmato intento", "Lettera firmata", "", ""])
    mb = FakeMailbox()
    history = []
    s = engine.Session(cfg, Funnel(sheet), None, texts.load_texts(engine.config_mod.TEXTS_PATH), mb)
    s._letter = b"%PDF fake"
    s.write_history = lambda today, title, bullets: history.append((title, bullets))
    sleeps = []

    def run(*argv, config=cfg):
        return cli.run(list(argv), connect=lambda c, need_mailbox: s, today=TODAY, cfg=config,
                       sleep=sleeps.append)

    return {"run": run, "mb": mb, "sheet": sheet, "history": history, "sleeps": sleeps, "cfg": cfg}


def row(sheet, name):
    return next(r for r in sheet.values if r[0] == name)


def test_stato_lists_due_actions(env, capsys):
    assert env["run"]("stato") == 0
    out = capsys.readouterr().out
    assert "Bar Uno | Isola | Mail 1" in out and "Pub Due" in out and "WhatsApp" in out


def test_anteprima_shows_mail_with_signature(env, capsys):
    assert env["run"]("anteprima", "bar uno") == 0
    out = capsys.readouterr().out
    assert "Oggetto: Partnership Bar Uno x Matcha" in out
    assert "Ciao Mario," in out and "CMO & Co-founder" in out
    assert "A: info@baruno.it" in out and "Cc: info@matchadating.it" in out


def test_invia_without_conferma_sends_nothing(env, capsys):
    before = [list(r) for r in env["sheet"].values]
    assert env["run"]("invia", "Bar Uno") == cli.NEEDS_CONFIRM
    assert env["mb"].sent == [] and env["sheet"].values == before
    assert "NESSUNA MAIL INVIATA" in capsys.readouterr().out


def test_invia_con_conferma(env, capsys):
    assert env["run"]("invia", "Bar Uno", "--conferma") == 0
    assert len(env["mb"].sent) == 1 and env["mb"].sent[0]["To"] == "info@baruno.it"
    r = row(env["sheet"], "Bar Uno")
    assert r[7] == "Email 1" and r[10] == "1" and r[12] == "23/10/2026"
    assert env["history"] and env["history"][0][0] == "Mailer: 1 mail inviate"


def test_unknown_venue_gives_hint(env, capsys):
    assert env["run"]("invia", "Bar", "--conferma") == cli.ERROR
    out = capsys.readouterr().out
    assert "Forse intendevi" in out and "Bar Uno" in out
    assert env["mb"].sent == []


def test_weekly_threshold_needs_explicit_flag(env, capsys):
    low = replace(env["cfg"], weekly_limit=0)
    assert env["run"]("invia", "Bar Uno", "--conferma", config=low) == cli.NEEDS_CONFIRM
    assert env["mb"].sent == []
    assert env["run"]("invia", "Bar Uno", "--conferma", "--oltre-soglia", config=low) == 0
    assert len(env["mb"].sent) == 1


def test_two_venues_pause_between(env):
    assert env["run"]("invia", "Bar Uno", "Pub Due", "--conferma") == 0
    assert len(env["mb"].sent) == 2 and len(env["sleeps"]) == 1 and 5 <= env["sleeps"][0] <= 30


def test_placeholder_must_be_filled(env, sheet, capsys):
    sheet.values[2] += ["2", "08/10/2026", "16/10/2026", "<t@matchadating.it>"]  # Pub Due due for mail 3
    assert env["run"]("invia", "Pub Due", "--conferma") == cli.ERROR
    assert env["mb"].sent == []
    assert env["run"]("invia", "Pub Due", "--valore", "numero_coppie=12", "--conferma") == 0
    body = env["mb"].sent[0].get_body(("plain",)).get_content()
    assert "12 coppie" in body and env["mb"].sent[0]["Subject"].startswith("Re: ")


def test_whatsapp_flow(env, capsys):
    assert env["run"]("whatsapp", "Bar Tre") == cli.NEEDS_CONFIRM
    assert "https://wa.me/393451112233" in capsys.readouterr().out
    assert env["run"]("whatsapp", "Bar Tre", "--inviato") == 0
    assert row(env["sheet"], "Bar Tre")[10] == "WA"


def test_segna_requires_confirmation(env):
    assert env["run"]("segna", "Bar Uno", "risposta") == cli.NEEDS_CONFIRM
    assert len(row(env["sheet"], "Bar Uno")) <= 10 or row(env["sheet"], "Bar Uno")[10] == ""
    assert env["run"]("segna", "Bar Uno", "risposta", "--conferma") == 0
    assert row(env["sheet"], "Bar Uno")[10] == "risposta"
    assert env["history"][-1][0] == "Mailer: sequenza chiusa"


def test_custom_subject_and_body_file(env, tmp_path):
    f = tmp_path / "testo.txt"
    f.write_text("Ciao Mario,\ntesto personalizzato.\n\nJacopo", encoding="utf-8")
    assert env["run"]("invia", "Bar Uno", "--oggetto", "Oggetto su misura", "--testo-file", str(f), "--conferma") == 0
    msg = env["mb"].sent[0]
    assert msg["Subject"] == "Oggetto su misura"
    assert "testo personalizzato" in msg.get_body(("plain",)).get_content()


def test_missing_signed_count_blocks_send(env, sheet, capsys):
    sheet.values.pop()  # no signed venue: {n_locali} cannot be filled
    assert env["run"]("invia", "Bar Uno", "--conferma") == cli.ERROR
    assert env["mb"].sent == [] and "n_locali" in capsys.readouterr().out
