"""Parses testi_email.md (the single source of the copy) and renders text/HTML bodies.

Expected structure of the Markdown file:

    ## Firma           -> one ```html block and one ```text block
    ## Mail 1 · ...    -> meta bullets ("- **Oggetto:** ..."), then the body, until "---"
    ## Mail 2 · ...
    ## Mail 3 · ...
    ## Mail 4 · ...
    ## WhatsApp · ...
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

PLACEHOLDER = re.compile(r"\{([a-z_0-9]+)\}")
_META = re.compile(r"^-\s+\*\*(?P<key>[^*:]+):?\*\*:?\s*(?P<val>.*)$")
_SECTION = re.compile(r"^##\s+(?P<title>.+?)\s*$")
_FENCE = re.compile(r"^```(?P<lang>\w*)\s*$")
_ORDERED = re.compile(r"^\d+[.)]\s+")


@dataclass
class Template:
    key: str  # mail1 ... mail4, whatsapp
    title: str
    subject: str = ""
    when: str = ""
    attachment: str = ""
    body: str = ""


@dataclass
class Texts:
    templates: dict[str, Template] = field(default_factory=dict)
    signature_html: str = ""
    signature_text: str = ""

    def get(self, key: str) -> Template:
        if key not in self.templates:
            raise KeyError(f"In testi_email.md manca la sezione per '{key}'")
        return self.templates[key]


def _section_key(title: str) -> str | None:
    t = title.lower()
    m = re.match(r"mail\s*(\d)", t)
    if m:
        return f"mail{m.group(1)}"
    if t.startswith("whatsapp"):
        return "whatsapp"
    if t.startswith("firma"):
        return "firma"
    return None


def parse_texts(md: str) -> Texts:
    texts = Texts()
    sections: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    for line in md.splitlines():
        m = _SECTION.match(line)
        if m:
            current = (m.group("title"), [])
            sections.append(current)
        elif current is not None:
            current[1].append(line)

    for title, lines in sections:
        key = _section_key(title)
        if key == "firma":
            _parse_signature(lines, texts)
        elif key:
            texts.templates[key] = _parse_template(key, title, lines)
    return texts


def _parse_signature(lines: list[str], texts: Texts) -> None:
    lang = None
    buf: list[str] = []
    for line in lines:
        m = _FENCE.match(line.strip())
        if m and lang is None:
            lang = m.group("lang") or "text"
            buf = []
        elif m and lang is not None:
            block = "\n".join(buf).strip()
            if lang == "html":
                texts.signature_html = block
            else:
                texts.signature_text = block
            lang = None
        elif lang is not None:
            buf.append(line)


def _parse_template(key: str, title: str, lines: list[str]) -> Template:
    tpl = Template(key=key, title=title)
    body: list[str] = []
    in_meta = True
    for line in lines:
        if line.strip() == "---":
            break
        if in_meta:
            if not line.strip():
                continue
            m = _META.match(line.strip())
            if m:
                k = m.group("key").strip().lower()
                v = m.group("val").strip()
                if k.startswith("oggetto"):
                    tpl.subject = v
                elif k.startswith("quando"):
                    tpl.when = v
                elif k.startswith("allegato"):
                    tpl.attachment = v
                continue
            in_meta = False
        body.append(line.rstrip())
    while body and not body[-1].strip():
        body.pop()
    tpl.body = "\n".join(body)
    return tpl


def load_texts(path: Path) -> Texts:
    return parse_texts(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- rendering


def fill(template: str, values: dict[str, str]) -> str:
    """Replaces {placeholders}. Empty values get sentence-level fallbacks; unknown ones stay visible."""
    out = template
    if not values.get("nome"):
        out = out.replace(" {nome}", "").replace("{nome}", "")
    if not values.get("zona"):
        out = out.replace("in zona {zona}", "della tua zona").replace("{zona}", "")

    def repl(m: re.Match) -> str:
        v = values.get(m.group(1))
        return v if v else m.group(0)

    return PLACEHOLDER.sub(repl, out)


def missing_placeholders(text: str) -> list[str]:
    return sorted(set(PLACEHOLDER.findall(text)))


def split_signature_point(body: str) -> tuple[str, str]:
    """Signature goes after the sign-off and before any PS paragraph."""
    paras = re.split(r"\n\s*\n", body.strip())
    for i, p in enumerate(paras):
        if re.match(r"^\s*P\.?\s?S\b", p, re.IGNORECASE):
            return "\n\n".join(paras[:i]), "\n\n".join(paras[i:])
    return body.strip(), ""


def to_text(body: str, signature_text: str) -> str:
    main, ps = split_signature_point(body)
    parts = [main, "--\n" + signature_text if signature_text else ""]
    if ps:
        parts.append(ps)
    return "\n\n".join(p for p in parts if p) + "\n"


_P = 'style="margin:0 0 12px 0;"'
_LIST = 'style="margin:0 0 12px 0;padding-left:22px;"'


def _para_html(block: str) -> str:
    lines = [ln for ln in block.split("\n")]
    out: list[str] = []
    buf: list[str] = []
    list_kind: str | None = None
    items: list[str] = []

    def flush_buf():
        if buf:
            out.append(f"<p {_P}>" + "<br>".join(html.escape(x) for x in buf) + "</p>")
            buf.clear()

    def flush_list():
        nonlocal list_kind
        if list_kind:
            lis = "".join(f'<li style="margin:0 0 4px 0;">{html.escape(i)}</li>' for i in items)
            out.append(f"<{list_kind} {_LIST}>{lis}</{list_kind}>")
            items.clear()
            list_kind = None

    for ln in lines:
        s = ln.strip()
        if s.startswith("- ") or s.startswith("• "):
            flush_buf()
            if list_kind != "ul":
                flush_list()
                list_kind = "ul"
            items.append(s[2:].strip())
        elif _ORDERED.match(s):
            flush_buf()
            if list_kind != "ol":
                flush_list()
                list_kind = "ol"
            items.append(_ORDERED.sub("", s, count=1))
        else:
            flush_list()
            buf.append(s)
    flush_list()
    flush_buf()
    return "".join(out)


def to_html(body: str, signature_html: str) -> str:
    main, ps = split_signature_point(body)
    blocks = [b for b in re.split(r"\n\s*\n", main) if b.strip()]
    inner = "".join(_para_html(b) for b in blocks)
    if signature_html:
        inner += f'<div style="margin:16px 0 12px 0;">{signature_html}</div>'
    if ps:
        inner += "".join(_para_html(b) for b in re.split(r"\n\s*\n", ps) if b.strip())
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head><body>"
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;">'
        f"{inner}</div></body></html>"
    )
