from matcha_mailer import config, texts


def load():
    return texts.load_texts(config.TEXTS_PATH)


def test_all_sections_present():
    t = load()
    for key in ("mail1", "mail2", "mail3", "mail4", "whatsapp"):
        assert t.get(key).body.strip(), key
    assert t.get("mail1").subject == "Partnership {nome_locale} x Matcha"
    assert t.get("mail4").subject
    assert "#38A096" in t.signature_html and "Matcha" in t.signature_html
    assert "CMO & Co-founder" in t.signature_text


def test_meta_lines_not_in_body():
    t = load()
    for key in ("mail1", "mail2", "mail3", "mail4", "whatsapp"):
        body = t.get(key).body
        assert "**Oggetto" not in body and "**Quando" not in body and "---" not in body


def test_fill_fallbacks():
    out = texts.fill("Ciao {nome},\nlocali partner in zona {zona}.", {"nome": "", "zona": ""})
    assert out == "Ciao,\nlocali partner della tua zona."
    out = texts.fill("Ciao {nome}, {nome_locale} {numero_coppie}", {"nome": "Anna", "nome_locale": "Bar"})
    assert out == "Ciao Anna, Bar {numero_coppie}"
    assert texts.missing_placeholders(out) == ["numero_coppie"]


def test_signature_before_ps():
    body = "Ciao,\nriga.\n\n- uno\n- due\n\nJacopo\n\nPS: rispondi stop."
    html = texts.to_html(body, "<b>FIRMA</b>")
    assert html.index("FIRMA") < html.index("PS: rispondi")
    assert html.count("<li") == 2 and "<ul" in html
    text = texts.to_text(body, "FIRMA")
    assert text.index("FIRMA") < text.index("PS:")


def test_ordered_list_and_escaping():
    html = texts.to_html("1. firma <qui>;\n2. chiamami", "")
    assert "<ol" in html and "&lt;qui&gt;" in html
