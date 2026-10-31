"""Richieste preparate da Claude ed eseguite con Esegui richiesta.bat."""

from datetime import datetime

from conftest import row

from matcha_mailer import cli, richieste


def write_request(env, text):
    path = env["tmp"] / "locale" / "richieste" / "da_eseguire.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_no_request_is_fine(env, capsys):
    assert env["run"]("richiesta") == 0
    assert "Nessuna richiesta" in capsys.readouterr().out


def test_read_only_request_runs_without_asking_and_is_archived(env, capsys):
    path = write_request(env, "# Titolo: Stato di oggi\ncandidati\nstato\n")
    assert env["run"]("richiesta") == 0
    out = capsys.readouterr().out
    assert "[sola lettura] stato" in out and "DA FARE OGGI" in out
    assert not path.exists()
    done = list((path.parent / "eseguite").iterdir())
    results = list((env["tmp"] / "locale" / "esiti").iterdir())
    assert len(done) == 1 and done[0].name.endswith("_stato-di-oggi.txt")
    assert len(results) == 1 and "DA FARE OGGI" in results[0].read_text(encoding="utf-8")


def test_sending_request_asks_and_can_be_cancelled(env, capsys):
    path = write_request(env, '# Titolo: Invio\ninvia "Bar Uno" --conferma\n')
    env["answers"].append("no")
    assert env["run"]("richiesta") == cli.NEEDS_CONFIRM
    assert "[INVIA O MODIFICA]" in capsys.readouterr().out
    assert env["mb"].sent == [] and path.exists()  # still there, nothing done

    env["answers"].append("SI")
    assert env["run"]("richiesta") == 0
    assert len(env["mb"].sent) == 1 and row(env["sheet"], "Bar Uno")[10] == "1"
    assert not path.exists()


def test_invalid_request_runs_nothing(env, capsys):
    path = write_request(env, 'stato\ninvia "Bar Uno" --boh\npassword\npython -m matcha_mailer stato\n')
    assert env["run"]("richiesta") == cli.ERROR
    out = capsys.readouterr().out
    assert "riga 2" in out and "riga 3" in out and "riga 4" in out and "NON eseguita" in out
    assert path.exists() and env["mb"].sent == []


def test_parse_and_modifies():
    title, cmds, errors = richieste.parse('# Titolo: Prova Ù\n\n# commento\nanteprima "L\'Enoteca Esempio"\n'
                                          'invia "A" "B" --testo-file locale\\bozze\\x.txt\n')
    assert title == "Prova Ù" and errors == []
    assert cmds == [["anteprima", "L'Enoteca Esempio"], ["invia", "A", "B", "--testo-file", "locale/bozze/x.txt"]]
    assert richieste.slug(title) == "prova-u"
    p = cli.build_parser()
    assert not cli.modifies(p.parse_args(["invia", "A"]))
    assert cli.modifies(p.parse_args(["invia", "A", "--conferma"]))
    assert cli.modifies(p.parse_args(["prova", "A"]))
    assert cli.modifies(p.parse_args(["whatsapp", "A", "--inviato"]))
    assert not cli.modifies(p.parse_args(["casella"]))


def test_result_names_never_overwrite(tmp_path):
    req = tmp_path / "richieste" / "da_eseguire.txt"
    now = datetime(2026, 11, 2, 9, 30)
    for _ in range(2):
        req.parent.mkdir(parents=True, exist_ok=True)
        req.write_text("# Titolo: Stato\nstato\n", encoding="utf-8")
        assert richieste.execute(req, lambda argv: 0, results_dir=tmp_path / "esiti", now=now) == 0
    names = sorted(p.name for p in (tmp_path / "esiti").iterdir())
    assert names == ["20261102-0930_stato-2.txt", "20261102-0930_stato.txt"]
