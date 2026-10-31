"""Richieste preparate da Claude ed eseguite da Jacopo con un doppio clic su "Esegui richiesta.bat".

Serve quando Claude lavora da una sessione cloud collegata al PC: vede i file della cartella ma non può
lanciare il mailer (la password Aruba è nel portachiavi di Windows). Claude scrive i comandi in
locale/richieste/da_eseguire.txt, Jacopo fa doppio clic, l'esito finisce in locale/esiti/.

Formato del file (una riga per comando, stessa sintassi del terminale, percorsi con "/"):

    # Titolo: Lettura casella e stato
    verifica
    casella
    stato

Se almeno un comando invia o modifica (--conferma, --inviato, prova) il mailer mostra l'elenco
e procede solo se Jacopo scrive SI. Dopo l'esecuzione la richiesta viene spostata in
locale/richieste/eseguite/, così non può essere rieseguita per sbaglio.
"""

from __future__ import annotations

import contextlib
import io
import re
import shlex
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

OK, ERROR, NEEDS_CONFIRM = 0, 1, 2
FORBIDDEN = {"richiesta", "password"}


def slug(text: str) -> str:
    s = unicodedata.normalize("NFKD", text or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:50] or "richiesta"


def parse(text: str) -> tuple[str, list[list[str]], list[str]]:
    """Returns (title, commands as argv lists, errors)."""
    from matcha_mailer import cli

    title, commands, errors = "", [], []
    for n, line in enumerate(text.splitlines(), start=1):
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            m = re.match(r"#\s*titolo\s*:\s*(.+)$", s, re.IGNORECASE)
            if m and not title:
                title = m.group(1).strip()
            continue
        try:
            argv = shlex.split(s.replace("\\", "/"))
        except ValueError as exc:
            errors.append(f"riga {n}: {exc} ({s})")
            continue
        if not argv:
            continue
        if argv[0] in ("python", "py") or argv[0].startswith(".venv"):
            errors.append(f"riga {n}: scrivi solo il comando, senza 'python -m matcha_mailer' ({s})")
            continue
        if argv[0] in FORBIDDEN:
            errors.append(f"riga {n}: il comando '{argv[0]}' non si usa in una richiesta")
            continue
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                cli.build_parser().parse_args(argv)
        except SystemExit:
            msg = err.getvalue().strip().splitlines()
            errors.append(f"riga {n}: comando non valido ({msg[-1] if msg else s})")
            continue
        commands.append(argv)
    return title, commands, errors


def describe(argv: list[str]) -> tuple[bool, str]:
    """(modifies?, command line as text)."""
    from matcha_mailer import cli

    args = cli.build_parser().parse_args(argv)
    return cli.modifies(args), " ".join(shlex.quote(a) for a in argv)


class _Tee:
    encoding = "utf-8"

    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            try:
                st.write(s)
            except Exception:
                pass
        return len(s)

    def flush(self):
        for st in self.streams:
            try:
                st.flush()
            except Exception:
                pass


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    i = 2
    while (p := path.with_name(f"{path.stem}-{i}{path.suffix}")).exists():
        i += 1
    return p


def execute(path: Path, runner, ask=input, results_dir: Path | None = None, now: datetime | None = None) -> int:
    """runner(argv) -> exit code (cli.run). ask(prompt) -> answer, used only when something is sent or written."""
    path = Path(path)
    results_dir = results_dir or path.parent.parent / "esiti"
    if not path.exists():
        print(f"Nessuna richiesta da eseguire: manca {path.parent.name}/{path.name}.", flush=True)
        return OK
    title, commands, errors = parse(path.read_text(encoding="utf-8-sig"))
    if errors or not commands:
        for e in errors or ["la richiesta non contiene comandi"]:
            print("ERRORE " + e, flush=True)
        print("Richiesta NON eseguita: va corretta. Il file è rimasto dov'era.", flush=True)
        return ERROR

    described = [describe(a) for a in commands]
    print(f"Richiesta: {title or '(senza titolo)'}", flush=True)
    for i, (writes, text) in enumerate(described, start=1):
        print(f"  {i}. [{'INVIA O MODIFICA' if writes else 'sola lettura'}] {text}", flush=True)
    if any(w for w, _ in described):
        answer = ask("\nQuesta richiesta invia mail o modifica il funnel. Scrivi SI e premi Invio per procedere: ")
        if (answer or "").strip().lower() not in ("si", "sì", "s"):
            print("Annullata: niente eseguito. La richiesta è rimasta in locale/richieste/.", flush=True)
            return NEEDS_CONFIRM

    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M")
    name = f"{stamp}_{slug(title)}.txt"
    results_dir.mkdir(parents=True, exist_ok=True)
    result_path = _unique(results_dir / name)
    codes = []
    with result_path.open("w", encoding="utf-8") as log:
        real = sys.stdout
        sys.stdout = _Tee(real, log)
        try:
            print(f"Richiesta: {title or '(senza titolo)'} · eseguita il {(now or datetime.now()):%d/%m/%Y %H:%M}")
            for i, ((_, text), argv) in enumerate(zip(described, commands), start=1):
                print(f"\n===== [{i}/{len(commands)}] {text} =====", flush=True)
                codes.append(runner(argv))
            print(f"\nCodici di uscita: {codes} (0 = fatto, 1 = errore, 2 = anteprima o conferma mancante)", flush=True)
        finally:
            sys.stdout = real
    done_dir = path.parent / "eseguite"
    done_dir.mkdir(parents=True, exist_ok=True)
    path.replace(_unique(done_dir / name))
    print(f"Esito salvato in locale/esiti/{result_path.name}", flush=True)
    return OK if all(c in (OK, NEEDS_CONFIRM) for c in codes) else ERROR
