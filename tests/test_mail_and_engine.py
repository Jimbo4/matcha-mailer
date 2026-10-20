from datetime import date

from matcha_mailer import engine, google_api, planner, texts
from matcha_mailer.funnel import Funnel
from matcha_mailer.mailbox import SentCopyError, build_message, search_criteria

TODAY = date(2026, 10, 12)


class FakeMailbox:
    def __init__(self, fail_copy=False):
        self.sent = []
        self.fail_copy = fail_copy

    def replied_venues(self, candidates, today):
        return set()

    def send(self, msg):
        self.sent.append(msg)
        if self.fail_copy:
            raise SentCopyError("cartella non trovata")


def make_session(cfg, sheet, mailbox, monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "LOG_PATH", tmp_path / "invii.csv")
    s = engine.Session(cfg, Funnel(sheet), None, texts.load_texts(engine.config_mod.TEXTS_PATH), mailbox)
    s._letter = b"%PDF-1.4 fake"
    return s


def test_build_message_headers():
    msg = build_message(sender_name="Jacopo", sender_email="jacopo@matchadating.it", to="a@b.it",
                        cc=["info@matchadating.it"], subject="Re: Partnership", text="t", html="<p>t</p>",
                        in_reply_to="<x@matchadating.it>", unsubscribe=True)
    assert msg["In-Reply-To"] == "<x@matchadating.it>" and msg["Cc"] == "info@matchadating.it"
    assert msg["List-Unsubscribe"] == "<mailto:jacopo@matchadating.it?subject=stop>"
    assert msg["Message-ID"].endswith("@matchadating.it>")
    assert msg.get_content_type() == "multipart/alternative"


def test_search_criteria():
    c = search_criteria("pub@gmail.com", "<id@matchadating.it>", "01-Oct-2026")
    assert ["SINCE", "01-Oct-2026", "FROM", '"@gmail.com"'] not in c
    assert ["HEADER", "In-Reply-To", '"<id@matchadating.it>"'] in c
    c2 = search_criteria("info@baruno.it", "", "01-Oct-2026")
    assert ["SINCE", "01-Oct-2026", "FROM", '"@baruno.it"'] in c2


def test_send_mail1_updates_funnel(cfg, sheet, monkeypatch, tmp_path):
    mb = FakeMailbox()
    s = make_session(cfg, sheet, mb, monkeypatch, tmp_path)
    actions, _ = s.build_plan(TODAY)
    a = next(x for x in actions if x.venue.name == "Bar Uno")
    assert a.kind == "mail1" and a.subject == "Partnership Bar Uno x Matcha"
    assert a.body.startswith("Ciao Mario,")
    changes, warn = s.send(a, TODAY)
    assert warn == ""
    msg = mb.sent[0]
    assert msg["To"] == "info@baruno.it" and msg["Cc"] == "info@matchadating.it"
    html = msg.get_body(("html",)).get_content()
    assert "Jacopo Marcolini" in html and "#38A096" in html
    row = next(r for r in sheet.values if r[0] == "Bar Uno")
    assert row[7] == "Email automatica 1" and row[8] == "12/10/2026" and row[10] == "1"
    assert row[12] == "16/10/2026" and row[13] == msg["Message-ID"]
    assert row[9] == "Lasciato nostro numero, in attesa, Email automatica 1 inviata il 12/10/2026"
    bullet = engine.describe(changes, "Mail 1 inviata")
    assert bullet.startswith("Bar Uno: ") and '"Chiamata" → "Email automatica 1"' in bullet
    assert engine.sent_this_week(TODAY) == 1


def test_mail2_threads_on_mail1(cfg, sheet, monkeypatch, tmp_path):
    sheet.values[2] += ["1", "06/10/2026", "12/10/2026", "<abc@matchadating.it>"]
    mb = FakeMailbox()
    s = make_session(cfg, sheet, mb, monkeypatch, tmp_path)
    actions, _ = s.build_plan(TODAY)
    a = next(x for x in actions if x.venue.name == "Pub Due")
    assert a.kind == "mail2" and a.subject == "Re: Partnership Pub Due x Matcha"
    assert "{domani}" not in a.body
    s.send(a, TODAY)
    assert mb.sent[0]["In-Reply-To"] == "<abc@matchadating.it>"


def test_mail4_attachment_and_sent_copy_warning(cfg, sheet, monkeypatch, tmp_path):
    sheet.values[3][5] = "anna@bartre.it"
    mb = FakeMailbox(fail_copy=True)
    s = make_session(cfg, sheet, mb, monkeypatch, tmp_path)
    actions, _ = s.build_plan(TODAY)
    a = next(x for x in actions if x.venue.name == "Bar Tre")
    assert a.kind == "mail4" and "da Bar Tre il 28/09" in a.body
    changes, warn = s.send(a, TODAY)
    assert "Inviati" in warn
    att = [p for p in mb.sent[0].iter_attachments()]
    assert att and att[0].get_filename() == "Lettera.pdf"
    row = next(r for r in sheet.values if r[0] == "Bar Tre")
    assert row[10] == "4" and row[7] == "Email automatica lettera d'intenti"


def test_funnel_failure_is_reported_not_raised(cfg, sheet, monkeypatch, tmp_path):
    mb = FakeMailbox()
    s = make_session(cfg, sheet, mb, monkeypatch, tmp_path)
    actions, _ = s.build_plan(TODAY)
    a = next(x for x in actions if x.venue.name == "Bar Uno")
    sheet.values.append(["Bar Uno"] + [""] * 9)  # duplicate appears before writing
    changes, warn = s.send(a, TODAY)
    assert changes == [] and "funnel NON aggiornato" in warn and len(mb.sent) == 1


def test_whatsapp_link_from_plan(cfg, sheet, monkeypatch, tmp_path):
    s = make_session(cfg, sheet, FakeMailbox(), monkeypatch, tmp_path)
    actions, _ = s.build_plan(TODAY)
    wa = next(x for x in actions if x.kind == "whatsapp")
    link = planner.whatsapp_link(planner.mobile_number(wa.venue.phone), wa.body)
    assert link.startswith("https://wa.me/393451112233?text=Ciao%20Anna")
    assert "export%3Fformat%3Dpdf" in link


def test_history_requests_reuse_trailing_empty_bullet():
    doc = {"tabs": [{"documentTab": {"body": {"content": [
        {"startIndex": 0, "endIndex": 1, "sectionBreak": {}},
        {"startIndex": 1, "endIndex": 12, "paragraph": {"paragraphStyle": {"namedStyleType": "HEADING_2"},
                                                         "elements": [{"textRun": {"content": "30/09/2026\n"}}]}},
        {"startIndex": 12, "endIndex": 20, "paragraph": {"paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                                                          "elements": [{"textRun": {"content": "testo à\n"}}]}},
        {"startIndex": 20, "endIndex": 21, "paragraph": {"bullet": {}, "elements": [{"textRun": {"content": "\n"}}]}},
    ]}}}]}
    reqs = google_api.build_history_requests(doc, "12/10/2026", "Mailer: 1 mail inviate", ["Bar → ok"])
    ins = reqs[0]["insertText"]
    assert ins["location"]["index"] == 20
    assert ins["text"] == "12/10/2026\nMailer: 1 mail inviate\nBar → ok"
    deleted = [r["deleteParagraphBullets"]["range"] for r in reqs if "deleteParagraphBullets" in r]
    assert deleted == [{"startIndex": 20, "endIndex": 31}, {"startIndex": 31, "endIndex": 54}]
    styles = [r["updateParagraphStyle"]["paragraphStyle"]["namedStyleType"] for r in reqs if "updateParagraphStyle" in r]
    assert styles == ["HEADING_2", "HEADING_3", "NORMAL_TEXT"]
    assert not [r for r in reqs if "createParagraphBullets" in r]  # dash bullets inherited


def test_history_same_day_no_new_date_heading():
    doc = {"body": {"content": [
        {"startIndex": 1, "endIndex": 12, "paragraph": {"paragraphStyle": {"namedStyleType": "HEADING_2"},
                                                         "elements": [{"textRun": {"content": "12/10/2026\n"}}]}},
        {"startIndex": 12, "endIndex": 18, "paragraph": {"elements": [{"textRun": {"content": "testo\n"}}]}},
    ]}}
    reqs = google_api.build_history_requests(doc, "12/10/2026", "Titolo", ["a"])
    assert reqs[0]["insertText"] == {"location": {"index": 17}, "text": "\nTitolo\na"}
    bullets = [r for r in reqs if "createParagraphBullets" in r][0]["createParagraphBullets"]["range"]
    assert bullets == {"startIndex": 25, "endIndex": 27}


def test_sent_but_funnel_not_updated_is_not_proposed_again(cfg, sheet, monkeypatch, tmp_path):
    mb = FakeMailbox()
    s = make_session(cfg, sheet, mb, monkeypatch, tmp_path)
    actions, _ = s.build_plan(TODAY)
    a = next(x for x in actions if x.venue.name == "Bar Uno")
    sheet.values.append(["Bar Uno"] + [""] * 9)  # funnel write will fail
    s.send(a, TODAY)
    sheet.values.pop()
    again = next(x for x in s.build_plan(TODAY)[0] if x.venue.name == "Bar Uno")
    assert again.kind == "info" and not again.selectable and "Già inviata il 12/10/2026" in again.status


def test_pause_between_sends(cfg):
    import random

    rng = random.Random(1)
    values = [engine.pause_seconds(cfg, rng) for _ in range(200)]
    assert min(values) >= 5 and max(values) <= 30 and max(values) - min(values) > 15
    assert engine.estimated_minutes(cfg, 1) == 1
    assert engine.estimated_minutes(cfg, 10) == round((9 * 17.5 + 30) / 60)
