"""candidati, attiva, --nome (nome breve nella mail) e registro invii."""

import csv

from conftest import row

from matcha_mailer import cli
from matcha_mailer.registro import FIELDS, Registry


def add_candidates(sheet):
    sheet.values += [
        ["Wine Bar Nuovo", "Via E 5, Milano", "Isola", "", "", "vino@nuovo.it", "", "", "", ""],
        ["Bar Lontano", "Via F 6, Monza", "Monza", "", "", "bar@lontano.it", "", "", "", ""],
        ["Senza Mail", "Via G 7, Milano", "Isola", "", "", "", "", "", "", ""],
        ["Da Visitare", "Via H 8, Milano", "Isola", "", "", "dv@dv.it", "", "TODO: da visitare", "", ""],
        ["Cocktail Lungo Nome - Bistrot", "Via I 9, Milano", "Navigli", "", "", "c@lungo.it", "", "", "", ""],
    ]


def test_candidati_only_milan_with_mail_and_empty_probability(env, capsys):
    add_candidates(env["sheet"])
    assert env["run"]("candidati") == 0
    out = capsys.readouterr().out
    assert "Wine Bar Nuovo" in out and "Cocktail Lungo Nome - Bistrot" in out
    assert "Bar Lontano" not in out and "Senza Mail" not in out and "Da Visitare" not in out
    assert "Bar Uno" not in out  # already "10 - nuovo"
    assert env["run"]("candidati", "--anche-fuori-milano") == 0
    assert "Bar Lontano" in capsys.readouterr().out
    assert env["run"]("candidati", "--zona", "navigli") == 0
    out = capsys.readouterr().out
    assert "Cocktail Lungo" in out and "Wine Bar Nuovo" not in out


def test_attiva_needs_conferma_and_checks_every_row(env, capsys):
    add_candidates(env["sheet"])
    n = len(env["sheet"].writes)
    assert env["run"]("attiva", "wine bar nuovo", "Senza Mail", "Bar Uno", "Non Esiste") == cli.NEEDS_CONFIRM
    out = capsys.readouterr().out
    assert "OK  Wine Bar Nuovo" in out and "NIENTE MODIFICATO" in out
    assert "Senza Mail: manca la mail" in out and "Bar Uno: Probabilità già" in out and "Non Esiste: 0 righe" in out
    assert len(env["sheet"].writes) == n

    assert env["run"]("attiva", "Wine Bar Nuovo", "--conferma") == 0
    assert row(env["sheet"], "Wine Bar Nuovo")[6] == "10 - nuovo"
    title, bullets = env["history"][-1]
    assert "attivati" in title and bullets == ['Wine Bar Nuovo: Probabilitá: vuoto → "10 - nuovo" (attivato per la sequenza a freddo)']
    assert env["run"]("attiva", "Wine Bar Nuovo", "--conferma") == cli.ERROR  # second time: already 10
    capsys.readouterr()
    assert env["run"]("stato") == 0
    assert "Wine Bar Nuovo | Isola | Mail 1" in capsys.readouterr().out


def test_attiva_refuses_duplicate_names(env, capsys):
    add_candidates(env["sheet"])
    env["sheet"].values.append(["Wine Bar Nuovo", "Via Z, Milano", "", "", "", "z@z.it", "", "", "", ""])
    assert env["run"]("attiva", "Wine Bar Nuovo", "--conferma") == cli.ERROR
    assert "2 righe" in capsys.readouterr().out and env["history"] == []


def test_short_name_in_mail1_and_kept_for_mail2(env, capsys):
    add_candidates(env["sheet"])
    env["sheet"].values[-1][6] = "10 - nuovo"
    full = "Cocktail Lungo Nome - Bistrot"
    assert env["run"]("anteprima", full, "--nome", f"{full}=Cocktail Lungo") == 0
    out = capsys.readouterr().out
    assert "Oggetto: Partnership Cocktail Lungo x Matcha" in out and "Nome del locale nella mail: Cocktail Lungo" in out
    assert env["run"]("invia", full, "Bar Uno", "--nome", f"{full}=Cocktail Lungo", "--conferma") == 0
    subjects = sorted(m["Subject"] for m in env["mb"].sent)
    assert subjects == ["Partnership Bar Uno x Matcha", "Partnership Cocktail Lungo x Matcha"]
    first = Registry(env["tmp"] / "invii.csv").first_mail()
    assert first[full.lower()].name_in_mail == "Cocktail Lungo" and first["bar uno"].name_in_mail == ""

    r = row(env["sheet"], full)
    r[12] = "01/10/2026"  # Mail 2 due now
    actions, _ = env["session"].build_plan(env["session"].registry.first_day())
    a = next(x for x in actions if x.venue.name == full)
    assert a.kind == "mail2" and a.subject == "Re: Partnership Cocktail Lungo x Matcha"
    assert a.values["nome_locale"] == "Cocktail Lungo"


def test_short_name_must_match_a_named_venue(env, capsys):
    assert env["run"]("invia", "Bar Uno", "--nome", "Pub Due=Pub") == cli.ERROR
    assert "--nome" in capsys.readouterr().out and env["mb"].sent == []
    assert env["run"]("invia", "Bar Uno", "--nome", "senza uguale") == cli.ERROR


def test_registry_adds_new_column_to_old_file(tmp_path):
    path = tmp_path / "invii.csv"
    path.write_text("data,ora,locale,azione,destinatario,oggetto,message_id\n"
                    "20/10/2026,17:00,Bar Uno,mail1,a@b.it,Partnership Bar Uno x Matcha,<1@m.it>\n", encoding="utf-8")
    from datetime import date

    reg = Registry(path)
    reg.add(date(2026, 10, 21), "Pub Due", "mail1", "p@d.it", "Partnership Pub x Matcha", "<2@m.it>", "Pub")
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0].keys()) == FIELDS and rows[0]["nome_in_mail"] == "" and rows[1]["nome_in_mail"] == "Pub"
    assert reg.message_ids() == {"1@m.it": "Bar Uno", "2@m.it": "Pub Due"}
    assert reg.sent_this_week(date(2026, 10, 21)) == 2
