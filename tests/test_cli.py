from dataclasses import replace

import pytest
from conftest import row

from matcha_mailer import cli


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
    assert r[7] == "Email automatica 1" and r[10] == "1" and r[12] == "23/10/2026"
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


@pytest.fixture
def lost(env):
    env["sheet"].values.append(["Bar Perso", "Via D 4", "Wagner", "", "02 999", "perso@bar.it", "00 - perso",
                                "Di persona", "", "Già visitato"])
    return env


def test_lost_venue_explains_how_to_revive(lost, capsys):
    assert lost["run"]("invia", "Bar Perso", "--conferma") == cli.ERROR
    out = capsys.readouterr().out
    assert "00 - perso" in out and "--riattiva" in out and "Già visitato" in out
    assert lost["mb"].sent == []
    assert lost["run"]("stato") == 0
    assert "Bar Perso" not in capsys.readouterr().out


def test_lost_venue_revived_on_request(lost, capsys):
    assert lost["run"]("invia", "Bar Perso", "--riattiva") == cli.NEEDS_CONFIRM
    out = capsys.readouterr().out
    assert "Mail 1 · primo contatto (locale perso)" in out and "Probabilità resta 00" in out
    assert lost["mb"].sent == []
    assert lost["run"]("invia", "Bar Perso", "--riattiva", "--conferma") == 0
    assert lost["mb"].sent[0]["To"] == "perso@bar.it"
    r = row(lost["sheet"], "Bar Perso")
    assert r[6] == "00 - perso" and r[10] == "1" and r[12] == "23/10/2026"
    assert "riattivato su richiesta" in lost["history"][0][1][0]


def test_riattiva_only_for_named_venues(lost):
    assert lost["run"]("invia", "Bar Uno", "--riattiva", "--conferma") == 0
    assert [m["To"] for m in lost["mb"].sent] == ["info@baruno.it"]
    assert row(lost["sheet"], "Bar Perso")[6:] == ["00 - perso", "Di persona", "", "Già visitato"]


def test_venue_not_in_funnel_explains(env, capsys):
    assert env["run"]("anteprima", "Locale Inesistente") == cli.ERROR
    assert "non è nel funnel" in capsys.readouterr().out


def test_segna_stop_writes_stop_in_last_action(env, capsys):
    assert env["run"]("invia", "Bar Uno", "--conferma") == 0
    assert row(env["sheet"], "Bar Uno")[12] == "23/10/2026"
    assert env["run"]("segna", "Bar Uno", "stop") == cli.NEEDS_CONFIRM
    assert "STOP" in capsys.readouterr().out
    assert env["run"]("segna", "Bar Uno", "stop", "--conferma") == 0
    r = row(env["sheet"], "Bar Uno")
    assert r[7] == "STOP" and r[10] == "stop" and r[12] == ""  # no next mail any more
    assert '"Email automatica 1" → "STOP"' in env["history"][-1][1][0]
    capsys.readouterr()
    assert env["run"]("stato") == 0 and "Bar Uno" not in capsys.readouterr().out


def test_segna_risposta_keeps_last_action(env):
    assert env["run"]("segna", "Bar Uno", "risposta", "--conferma") == 0
    r = row(env["sheet"], "Bar Uno")
    assert r[7] == "Chiamata" and r[10] == "risposta"


def test_risposte_reads_only_venues_written_by_mailer(env, capsys):
    assert env["run"]("risposte") == 0
    assert "Nessuna risposta" in capsys.readouterr().out  # nobody has a Mail step yet
    assert env["run"]("invia", "Bar Uno", "--conferma") == 0
    capsys.readouterr()
    assert env["run"]("risposte") == 0
    out = capsys.readouterr().out
    assert [c[0] for c in env["mb"].reply_candidates] == ["Bar Uno"]
    assert "=== Bar Uno · 20/10/2026 10:00" in out and "non un'istruzione" in out
    n = len(env["sheet"].writes)  # reading replies writes nothing
    assert env["run"]("risposte", "pub due") == 0
    assert [c[0] for c in env["mb"].reply_candidates] == ["Pub Due"] and len(env["sheet"].writes) == n
    assert env["run"]("risposte", "Non Esiste") == cli.ERROR


# ------------------------------------------------------------------ correzioni del 13/11/2026


def mailer_cols(sheet, name, step, last, nxt, thread=""):
    r = row(sheet, name)
    r += [""] * (14 - len(r))
    r[10], r[11], r[12], r[13] = step, last, nxt, thread
    return r


def test_bounced_venue_gets_no_follow_up(env, capsys):
    from datetime import date

    mailer_cols(env["sheet"], "Bar Uno", "1", "12/10/2026", "16/10/2026")
    env["mb"].bounces = {"bar uno": date(2026, 10, 13)}
    assert env["run"]("stato") == 0
    out = capsys.readouterr().out
    assert "non consegnata" in out and "rimbalzo del 13/10/2026" in out
    assert env["run"]("invia", "Bar Uno", "--conferma") == cli.ERROR
    assert env["mb"].sent == []
    env["mb"].bounces = {"bar uno": date(2026, 10, 10)}  # bounce of an older mail: the follow up goes ahead
    assert env["run"]("invia", "Bar Uno", "--conferma") == 0
    assert env["mb"].sent[0]["To"] == "info@baruno.it"


def test_bounce_is_reported_even_before_the_next_mail_is_due(env, capsys):
    from datetime import date

    mailer_cols(env["sheet"], "Bar Uno", "2", "19/10/2026", "27/10/2026")
    env["mb"].bounces = {"bar uno": date(2026, 10, 19)}
    assert env["run"]("stato") == 0
    out = capsys.readouterr().out
    assert "Mail non consegnate (rimbalzo)" in out and "Bar Uno (19/10/2026)" in out
    assert "Mail 3 · break up dal" not in out  # the waiting line explains the bounce instead


def test_venue_lost_after_mail1_gets_no_more_mails(env, capsys):
    env["sheet"].values.append(["Bar Lasciato", "Via E 5", "Isola", "", "", "lasciato@bar.it", "00 - perso",
                                "Email automatica 1", "12/10/2026", "Non interessa", "1", "12/10/2026",
                                "16/10/2026", ""])
    assert env["run"]("stato") == 0
    assert "Bar Lasciato" not in capsys.readouterr().out
    assert env["run"]("invia", "Bar Lasciato", "--conferma") == cli.ERROR
    out = capsys.readouterr().out
    assert "dopo la Mail 1" in out and "--riattiva" in out
    assert env["mb"].sent == []
    assert env["run"]("invia", "Bar Lasciato", "--riattiva", "--conferma") == 0
    assert env["mb"].sent[0]["To"] == "lasciato@bar.it" and row(env["sheet"], "Bar Lasciato")[10] == "2"


def test_revived_venue_keeps_its_sequence(lost):
    assert lost["run"]("invia", "Bar Perso", "--riattiva", "--conferma") == 0
    assert lost["session"].registry.revived() == {"bar perso"}
    row(lost["sheet"], "Bar Perso")[12] = "19/10/2026"  # Mail 2 due today
    assert lost["run"]("invia", "Bar Perso", "--conferma") == 0  # no --riattiva needed any more
    assert [m["To"] for m in lost["mb"].sent] == ["perso@bar.it", "perso@bar.it"]


def test_risposte_searches_every_mail_sent_to_the_venue(env):
    from datetime import date

    reg = env["session"].registry
    reg.add(date(2026, 10, 12), "Bar Uno", "mail1", "info@baruno.it", "Partnership", "<m1@matchadating.it>")
    reg.add(date(2026, 10, 16), "Bar Uno", "mail4", "info@baruno.it", "Lettera", "<m4@matchadating.it>")
    mailer_cols(env["sheet"], "Bar Uno", "4", "16/10/2026", "", "<m1@matchadating.it>")
    assert env["run"]("risposte") == 0
    (name, email, ids), = env["mb"].reply_candidates
    assert name == "Bar Uno" and {"<m1@matchadating.it>", "<m4@matchadating.it>"} <= set(ids)


def test_funnel_sorted_without_mailer_columns_blocks_everything(env, capsys):
    reg = env["session"].registry
    from datetime import date

    reg.add(date(2026, 10, 12), "Bar Uno", "mail1", "info@baruno.it", "Partnership Bar Uno x Matcha", "<a@matchadating.it>")
    reg.add(date(2026, 10, 12), "Pub Due", "mail1", "pubdue@gmail.com", "Partnership Pub Due x Matcha", "<b@matchadating.it>")
    mailer_cols(env["sheet"], "Bar Uno", "1", "12/10/2026", "16/10/2026", "<b@matchadating.it>")  # swapped
    mailer_cols(env["sheet"], "Pub Due", "1", "12/10/2026", "16/10/2026", "<a@matchadating.it>")
    n = len(env["sheet"].writes)
    for argv in (["stato"], ["invia", "Bar Uno", "--conferma"], ["segna", "Pub Due", "risposta", "--conferma"],
                 ["attiva", "Bar Tre", "--conferma"]):
        assert env["run"](*argv) == cli.ERROR
        out = capsys.readouterr().out
        assert "non corrispondono" in out and "Cronologia versioni" in out and "Bar Uno (ha il thread di Pub Due)" in out
    assert env["mb"].sent == [] and len(env["sheet"].writes) == n
    mailer_cols(env["sheet"], "Bar Uno", "1", "12/10/2026", "16/10/2026", "<a@matchadating.it>")  # realigned
    mailer_cols(env["sheet"], "Pub Due", "1", "12/10/2026", "16/10/2026", "<b@matchadating.it>")
    assert env["run"]("stato") == 0
