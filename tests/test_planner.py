from datetime import date

from matcha_mailer import planner
from matcha_mailer.planner import Venue

TODAY = date(2026, 10, 12)  # Monday


def kinds(actions):
    return {a.venue.name: (a.kind, a.selectable) for a in actions}


def test_first_name():
    assert planner.first_name("Mario (titolare)") == "Mario"
    assert planner.first_name("Davide / Giuseppe (titolari)") == "Davide"
    assert planner.first_name("R. Casina (da verificare)") == ""
    assert planner.first_name("Massimo Rossi (da verificare)") == ""
    assert planner.first_name("") == ""
    assert planner.first_name("valentina") == "Valentina"


def test_mobile_number():
    assert planner.mobile_number("345 402 0762") == "393454020762"
    assert planner.mobile_number("+39 345 402 0762") == "393454020762"
    assert planner.mobile_number("02 3663 8456") == ""
    assert planner.mobile_number("") == ""


def test_plan_rules():
    vs = [
        Venue("Nuovo", email="a@a.it", probability="10 - nuovo", last_action="Chiamata"),
        Venue("Da visitare", email="b@b.it", probability="10 - nuovo", last_action="TODO: da visitare"),
        Venue("Senza mail", probability="10 - nuovo", last_action="Chiamata"),
        Venue("Attesa", email="c@c.it", probability="10 - nuovo", mail_step="1", mail_next="15/10/2026"),
        Venue("Follow", email="d@d.it", probability="10 - nuovo", mail_step="1", mail_next="12/10/2026"),
        Venue("Breakup", email="e@e.it", probability="10 - nuovo", mail_step="2", mail_next="01/10/2026"),
        Venue("Finito", email="f@f.it", probability="10 - nuovo", mail_step="3"),
        Venue("Stop", email="g@g.it", probability="10 - nuovo", mail_step="stop"),
        Venue("Risposto", email="h@h.it", probability="10 - nuovo", mail_step="1", mail_next="01/10/2026"),
        Venue("Curioso mail", email="i@i.it", probability="50 - curioso", last_action="Di persona"),
        Venue("Curioso wa", phone="345 111 2233", probability="50 - curioso"),
        Venue("Curioso fisso", phone="02 1234 5678", probability="50 - curioso"),
        Venue("Curioso fatto", email="l@l.it", probability="50 - curioso", mail_step="4"),
        Venue("Firmato", email="m@m.it", probability="90 - firmato intento"),
        Venue("Perso", email="n@n.it", probability="00 - perso"),
    ]
    acts = planner.plan(vs, TODAY, replied={"risposto"})
    k = kinds(acts)
    assert k["Nuovo"] == ("mail1", True)
    assert k["Attesa"] == ("info", False)
    assert k["Follow"] == ("mail2", True)
    assert k["Breakup"] == ("mail3", True)
    assert k["Risposto"] == ("info", False)
    assert k["Curioso mail"] == ("mail4", True)
    assert k["Curioso wa"] == ("whatsapp", True)
    assert k["Curioso fisso"] == ("info", False)
    for absent in ("Da visitare", "Senza mail", "Finito", "Stop", "Curioso fatto", "Firmato", "Perso"):
        assert absent not in k
    assert acts[0].values["n_locali"] == "1"
    wa = next(a for a in acts if a.kind == "whatsapp")
    assert wa.selected is False  # WhatsApp is never bulk-selected


def test_when_we_met():
    assert planner.when_we_met(Venue("Bar", last_action="Di persona", last_contacted="28/09/2026")) == "da Bar il 28/09"
    assert planner.when_we_met(Venue("Bar", last_action="Chiamata")) == "al telefono"
    assert planner.when_we_met(Venue("Bar", last_action="Di persona")) == "da Bar nei giorni scorsi"


def test_next_due_and_note():
    assert planner.next_due("mail1", date(2026, 10, 9), 4, 6) == "15/10/2026"
    assert planner.next_due("mail3", date(2026, 10, 9), 4, 6) == ""
    n1 = planner.merge_note("Lasciato nostro numero, in attesa", "Email 1 inviata il 12/10/2026")
    assert n1 == "Lasciato nostro numero, in attesa, Email 1 inviata il 12/10/2026"
    n2 = planner.merge_note(n1, "Email 2 inviata il 16/10/2026")
    assert n2 == "Lasciato nostro numero, in attesa, Email 2 inviata il 16/10/2026"
    n3 = planner.merge_note(n2, "Email 3 (break up) inviata il 26/10/2026")
    assert n3.endswith("in attesa, Email 3 (break up) inviata il 26/10/2026")
    assert planner.merge_note("", "Email 1 inviata il 12/10/2026") == "Email 1 inviata il 12/10/2026"


def test_lost_venues_only_on_request():
    vs = [
        Venue("Perso Bar", email="p@p.it", probability="00 - perso", last_action="Di persona"),
        Venue("Perso senza mail", probability="00 - perso"),
        Venue("Perso stop", email="s@s.it", probability="00 - perso", mail_step="stop"),
        Venue("Perso in corso", email="c@c.it", probability="00 - perso", mail_step="1", mail_next="12/10/2026"),
        Venue("Perso risposto", email="r@r.it", probability="00 - perso", mail_step="2", mail_next="01/10/2026"),
    ]
    k = kinds(planner.plan(vs, TODAY, replied={"perso risposto"}))
    assert "Perso Bar" not in k  # never proposed without a request
    assert k["Perso in corso"] == ("mail2", True)  # already revived: the sequence goes on
    assert k["Perso risposto"] == ("info", False)

    acts = planner.plan(vs, TODAY, revive={"perso BAR"})
    a = next(a for a in acts if a.venue.name == "Perso Bar")
    assert (a.kind, a.selectable, a.selected, a.lost) == ("mail1", True, True, True)
    assert a.label.endswith("(locale perso)")
    assert "Perso senza mail" not in kinds(acts) and "Perso stop" not in kinds(acts)

    shown = planner.plan(vs, TODAY, show_lost=True)
    a = next(a for a in shown if a.venue.name == "Perso Bar")
    assert (a.kind, a.selectable, a.selected) == ("mail1", True, False)  # listed, never pre-selected


def test_explain_says_what_to_do():
    lost = Venue("Perso", email="p@p.it", probability="00 - perso", notes="Già visitato")
    assert "--riattiva" in planner.explain(lost) and "Già visitato" in planner.explain(lost)
    assert "manca la mail" in planner.explain(Venue("X", probability="00 - perso"))
    assert "manca la mail" in planner.explain(Venue("X", probability="10 - nuovo"))
    assert "TODO" in planner.explain(Venue("X", email="x@x.it", probability="10 - nuovo", last_action="TODO: da visitare"))
    assert "stop" in planner.explain(Venue("X", email="x@x.it", probability="10 - nuovo", mail_step="stop"))
    assert "firmato" in planner.explain(Venue("X", email="x@x.it", probability="90 - firmato intento"))
    assert "10 - nuovo" in planner.explain(Venue("X", email="x@x.it", probability=""))
