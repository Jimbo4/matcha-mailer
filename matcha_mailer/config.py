"""Percorsi del progetto e lettura di locale/config.ini.

Tutto ciò che è di questo PC (configurazione, credenziali, registro invii, richieste ed esiti)
sta in locale/, che non va su GitHub. Nel repo restano solo codice, testi, test e documentazione.
"""

from __future__ import annotations

import configparser
import shutil
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXTS_PATH = ROOT / "testi_email.md"
CONFIG_EXAMPLE = ROOT / "config.example.ini"

LOCALE_DIR = ROOT / "locale"
CONFIG_PATH = LOCALE_DIR / "config.ini"
SECRETS_DIR = LOCALE_DIR / "segreti"
REGISTRY_DIR = LOCALE_DIR / "registro"
REQUESTS_DIR = LOCALE_DIR / "richieste"
RESULTS_DIR = LOCALE_DIR / "esiti"
DRAFTS_DIR = LOCALE_DIR / "bozze"  # testi modificati per --testo-file
ARCHIVE_DIR = LOCALE_DIR / "archivio"

REGISTRY_PATH = REGISTRY_DIR / "invii.csv"
REQUEST_PATH = REQUESTS_DIR / "da_eseguire.txt"


@dataclass
class Config:
    sender_email: str
    sender_name: str
    cc: list[str]
    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int
    sent_folder: str
    funnel_id: str
    funnel_sheet: str
    history_doc_id: str
    letter_doc_id: str
    letter_filename: str
    client_secret: Path
    token_path: Path
    days_mail_2: int
    days_mail_3: int
    weekly_limit: int
    reply_lookback_days: int
    pause_min: float = 5.0
    pause_max: float = 30.0

    @property
    def letter_pdf_link(self) -> str:
        return f"https://docs.google.com/document/d/{self.letter_doc_id}/export?format=pdf"


class ConfigMissing(Exception):
    pass


def load_config(path: Path = CONFIG_PATH) -> Config:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        if CONFIG_EXAMPLE.exists():
            shutil.copy(CONFIG_EXAMPLE, path)
        raise ConfigMissing(
            "Ho creato locale/config.ini dal modello. Inserisci gli ID dei tre file Drive (funnel, cronologia, "
            "lettera_intenti_v2: la parte dell'URL tra /d/ e /edit), poi rilancia. Dettagli nel README, Installazione."
        )
    cp = configparser.ConfigParser(inline_comment_prefixes=(";",))
    cp.read(path, encoding="utf-8")

    def get(section: str, key: str, default: str = "") -> str:
        return cp.get(section, key, fallback=default).strip()

    cfg = Config(
        sender_email=get("mittente", "email"),
        sender_name=get("mittente", "nome"),
        cc=[c.strip() for c in get("mittente", "cc").split(",") if c.strip()],
        smtp_host=get("aruba", "smtp_host", "smtps.aruba.it"),
        smtp_port=int(get("aruba", "smtp_port", "465")),
        imap_host=get("aruba", "imap_host", "imaps.aruba.it"),
        imap_port=int(get("aruba", "imap_port", "993")),
        sent_folder=get("aruba", "cartella_inviati"),
        funnel_id=get("google", "funnel_id"),
        funnel_sheet=get("google", "funnel_foglio", "Sheet1"),
        history_doc_id=get("google", "cronologia_doc_id"),
        letter_doc_id=get("google", "lettera_doc_id"),
        letter_filename=get("google", "lettera_nome_file", "Lettera d'intenti Matcha.pdf"),
        client_secret=SECRETS_DIR / "credentials.json",
        token_path=SECRETS_DIR / "token.json",
        days_mail_2=int(get("sequenza", "giorni_mail_2", "4")),
        days_mail_3=int(get("sequenza", "giorni_mail_3", "6")),
        weekly_limit=int(get("sequenza", "soglia_settimanale", "20")),
        reply_lookback_days=int(get("sequenza", "giorni_controllo_risposte", "60")),
        pause_min=float(get("sequenza", "pausa_min_secondi", "5")),
        pause_max=float(get("sequenza", "pausa_max_secondi", "30")),
    )
    missing = [
        name
        for name, value in [
            ("mittente.email", cfg.sender_email),
            ("google.funnel_id", cfg.funnel_id),
            ("google.cronologia_doc_id", cfg.history_doc_id),
            ("google.lettera_doc_id", cfg.letter_doc_id),
        ]
        if not value or value.startswith("<")
    ]
    if missing:
        raise ConfigMissing(
            "In locale/config.ini mancano: " + ", ".join(missing)
            + ". Sostituisci i valori tra < > (per i file Drive: la parte dell'URL tra /d/ e /edit)."
        )
    return cfg
