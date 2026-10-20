"""Command line for the mailer, so that Claude (or a terminal) can use it without the window.

    python -m matcha_mailer verifica
    python -m matcha_mailer stato [--json]
    python -m matcha_mailer anteprima "N'Ombra de Vin"
    python -m matcha_mailer prova "N'Ombra de Vin"
    python -m matcha_mailer invia "N'Ombra de Vin" [--conferma]
    python -m matcha_mailer invia "Locale perso" --riattiva [--conferma]   (solo su richiesta di Jacopo)
    python -m matcha_mailer whatsapp "Nuova Posteria Milanese" [--inviato]
    python -m matcha_mailer segna "N'Ombra de Vin" risposta|stop [--conferma]
    python -m matcha_mailer password

Nothing is ever sent or written without --conferma (or --inviato for WhatsApp).
Exit codes: 0 done, 1 error, 2 nothing done because --conferma is missing.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
import webbrowser
from datetime import date

from matcha_mailer import config as config_mod
from matcha_mailer import engine, keychain, planner, texts
from matcha_mailer.funnel import norm

OK, ERROR, NEEDS_CONFIRM = 0, 1, 2


class CliError(Exception):
    pass


# ------------------------------------------------------------------ helpers


def _out(text: str = "") -> None:
    print(text, flush=True)


def _connect(cfg, need_mailbox: bool):
    """Google + Aruba. The Aruba password is read from the Windows credential store only."""
    from matcha_mailer.mailbox import Mailbox

    session = engine.Session.connect(cfg)
    pw = keychain.get_password(cfg.sender_email)
    if pw:
        session.mailbox = Mailbox(cfg, pw)
    elif need_mailbox:
        raise CliError(
            "Password Aruba non salvata. Jacopo deve eseguire lui, in un suo terminale, "
            "'.venv\\Scripts\\python -m matcha_mailer password' oppure aprire una volta Matcha Mailer.bat."
        )
    return session


def _find(actions, name: str, selectable_only: bool = True, venues=None, revived: bool = False):
    """Finds the action for a venue. When there is none, explains why and what to do (venues = funnel rows)."""
    target = norm(name)
    pool = [a for a in actions if a.selectable] if selectable_only else actions
    exact = [a for a in pool if norm(a.venue.name) == target]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise CliError(f"'{name}': più righe con lo stesso nome nel funnel, non procedo. "
                       "Rinomina o elimina una delle due righe nel funnel, poi rilancia.")
    waiting = [a for a in actions if not a.selectable and norm(a.venue.name) == target]
    if waiting:
        raise CliError(f"'{waiting[0].venue.name}': nessuna azione da fare oggi ({waiting[0].status})")
    rows = [v for v in (venues or []) if norm(v.name) == target]
    if len(rows) > 1:
        raise CliError(f"'{name}': più righe con lo stesso nome nel funnel, non procedo. "
                       "Rinomina o elimina una delle due righe nel funnel, poi rilancia.")
    if rows:
        raise CliError(f"'{rows[0].name}': nessuna azione da fare oggi: {planner.explain(rows[0], revived)}")
    names = {v.name for v in venues} if venues else {a.venue.name for a in actions}
    similar = sorted(n for n in names if target and target in norm(n))
    hint = f" Forse intendevi: {', '.join(similar)}." if similar else ""
    if venues:
        raise CliError(
            f"'{name}' non è nel funnel.{hint} Se è un locale nuovo, aggiungi una riga nel funnel con "
            "Nome attività, Zona, Mail e Probabilità \"10 - nuovo\", poi rilancia."
        )
    raise CliError(
        f"'{name}' non ha azioni da fare oggi.{hint} Usa 'stato' per l'elenco. "
        "Se il locale è nel funnel ma non compare, controlla Probabilità (10 o 50), Mail e Ultima azione."
    )


def _plan(session, ctx, names=(), riattiva: bool = False):
    revive = set(names) if riattiva else None
    return session.build_plan(ctx["today"], revive=revive)


def _locate(session, actions, name: str, riattiva: bool = False):
    return _find(actions, name, venues=getattr(session, "venues", None), revived=riattiva)


def _apply_overrides(action, values: list[str], subject: str | None, body_file: str | None) -> None:
    for item in values or []:
        if "=" not in item:
            raise CliError(f"--valore '{item}': usa il formato nome=valore, es. numero_coppie=12")
        key, val = item.split("=", 1)
        key = key.strip().strip("{}")
        action.subject = action.subject.replace("{" + key + "}", val)
        action.body = action.body.replace("{" + key + "}", val)
        action.edited = True
    if subject:
        action.subject, action.edited = subject, True
    if body_file:
        with open(body_file, encoding="utf-8") as f:
            action.body, action.edited = f.read().strip("\n"), True


def _recipients(cfg, a) -> str:
    if a.kind == "whatsapp":
        return f"WhatsApp +{planner.mobile_number(a.venue.phone)}"
    cc = f"  ·  Cc: {', '.join(cfg.cc)}" if cfg.cc else ""
    return f"Da: {cfg.sender_name} <{cfg.sender_email}>  ·  A: {a.venue.email}{cc}"


def _print_preview(session, a) -> None:
    cfg = session.cfg
    _out(f"=== {a.venue.name} · {a.label} ===")
    _out(_recipients(cfg, a))
    if a.is_mail:
        _out(f"Oggetto: {a.subject}")
        if a.kind == "mail4":
            _out(f"Allegato: {cfg.letter_filename} (esportato da lettera_intenti_v2)")
        if a.kind in ("mail2", "mail3"):
            _out("Thread: in risposta alla mail 1")
        _out("-" * 60)
        _out(texts.to_text(a.body, session.texts.signature_text).rstrip())
    else:
        _out("-" * 60)
        _out(a.body)
    _out("-" * 60)
    if a.lost:
        _out("Nota: nel funnel il locale è \"00 - perso\", riattivato su richiesta di Jacopo. Probabilità resta 00.")
    missing = engine.problems(a)
    if missing:
        _out("DA COMPLETARE prima dell'invio: " + ", ".join("{" + m + "}" for m in missing)
             + "  (usa --valore nome=valore)")


# ------------------------------------------------------------------ commands


def cmd_verifica(args, ctx) -> int:
    cfg = ctx["cfg"]
    rows = []
    rows.append(("config.ini", True, "letto"))
    secret = cfg.client_secret.exists()
    rows.append(("secrets/credentials.json", secret, "presente" if secret else "manca: vedi README, Accesso a Google"))
    rows.append(("token Google", cfg.token_path.exists(), "presente" if cfg.token_path.exists() else "al primo uso si apre il browser"))
    pw = keychain.get_password(cfg.sender_email)
    rows.append(("password Aruba", bool(pw), "salvata" if pw else "manca: Jacopo esegue 'python -m matcha_mailer password'"))
    t = texts.load_texts(config_mod.TEXTS_PATH)
    missing_tpl = [k for k in ("mail1", "mail2", "mail3", "mail4", "whatsapp") if k not in t.templates]
    rows.append(("testi_email.md", not missing_tpl, "ok" if not missing_tpl else "mancano: " + ", ".join(missing_tpl)))
    ok_all = all(r[1] for r in rows[:2]) and not missing_tpl
    if secret and not args.offline:
        try:
            session = ctx["connect"](cfg, need_mailbox=False)
            n = len(session.funnel.load())
            cols = session.funnel.missing_mailer_columns()
            rows.append(("funnel Google", not cols, f"{n} locali letti" + (f", mancano colonne {cols}" if cols else "")))
            ok_all &= not cols
            if session.mailbox:
                session.mailbox.check_login()
                rows.append(("accesso Aruba", True, "login riuscito"))
        except Exception as exc:  # noqa: BLE001
            rows.append(("connessione", False, str(exc)))
            ok_all = False
    for name, good, note in rows:
        _out(f"{'OK ' if good else 'NO '} {name}: {note}")
    return OK if ok_all and pw else ERROR


def cmd_stato(args, ctx) -> int:
    session = ctx["connect"](ctx["cfg"], need_mailbox=False)
    actions, warnings = session.build_plan(ctx["today"])
    week = engine.sent_this_week(ctx["today"])
    if args.json:
        _out(json.dumps({
            "mail_inviate_settimana": week,
            "soglia": ctx["cfg"].weekly_limit,
            "avvisi": warnings + ([] if session.mailbox else ["password Aruba non salvata: risposte non controllate"]),
            "azioni": [
                {"locale": a.venue.name, "zona": a.venue.zone, "azione": a.kind, "descrizione": a.label or a.status,
                 "destinatario": a.venue.email if a.is_mail else a.venue.phone, "da_fare_oggi": a.selectable,
                 "oggetto": a.subject, "da_completare": engine.problems(a) if a.selectable else []}
                for a in actions
            ],
        }, ensure_ascii=False, indent=2))
        return OK
    _out(f"Mail inviate questa settimana: {week} (soglia {ctx['cfg'].weekly_limit})")
    if not session.mailbox:
        _out("Attenzione: password Aruba non salvata, risposte non controllate")
    for w in warnings:
        _out("Attenzione: " + w)
    due = [a for a in actions if a.selectable]
    rest = [a for a in actions if not a.selectable]
    _out(f"\nDA FARE OGGI ({len(due)})")
    for a in due:
        dest = a.venue.email if a.is_mail else a.venue.phone
        flag = "  [da completare: " + ", ".join(engine.problems(a)) + "]" if engine.problems(a) else ""
        _out(f"  - {a.venue.name} | {a.venue.zone or '-'} | {a.label} | {dest}{flag}")
    _out(f"\nIN ATTESA O DA GESTIRE A MANO ({len(rest)})")
    for a in rest:
        _out(f"  - {a.venue.name} | {a.status}")
    return OK


def cmd_anteprima(args, ctx) -> int:
    session = ctx["connect"](ctx["cfg"], need_mailbox=False)
    actions, _ = _plan(session, ctx, [args.locale], args.riattiva)
    a = _locate(session, actions, args.locale, args.riattiva)
    _apply_overrides(a, args.valore, args.oggetto, args.testo_file)
    _print_preview(session, a)
    return OK


def cmd_prova(args, ctx) -> int:
    session = ctx["connect"](ctx["cfg"], need_mailbox=True)
    actions, _ = _plan(session, ctx, [args.locale], args.riattiva)
    a = _locate(session, actions, args.locale, args.riattiva)
    if not a.is_mail:
        raise CliError("La prova vale solo per le mail")
    _apply_overrides(a, args.valore, args.oggetto, args.testo_file)
    if engine.problems(a):
        raise CliError("Completa prima: " + ", ".join(engine.problems(a)))
    session.send_test(a)
    _out(f"Prova inviata a {ctx['cfg'].sender_email}: {a.venue.name}, {a.label}. Funnel non modificato.")
    return OK


def cmd_invia(args, ctx) -> int:
    cfg = ctx["cfg"]
    if (args.oggetto or args.testo_file) and len(args.locali) != 1:
        raise CliError("--oggetto e --testo-file si usano con un solo locale alla volta")
    session = ctx["connect"](cfg, need_mailbox=bool(args.conferma))
    actions, warnings = _plan(session, ctx, args.locali, args.riattiva)
    chosen = []
    for name in args.locali:
        a = _locate(session, actions, name, args.riattiva)
        if not a.is_mail:
            raise CliError(f"'{a.venue.name}': l'azione è WhatsApp, usa il comando whatsapp")
        if a in chosen:
            continue
        chosen.append(a)
    for a in chosen:
        _apply_overrides(a, args.valore, args.oggetto, args.testo_file)
    for w in warnings:
        _out("Attenzione: " + w)
    for a in chosen:
        _print_preview(session, a)
        _out()
    bad = [f"{a.venue.name}: " + ", ".join(engine.problems(a)) for a in chosen if engine.problems(a)]
    if bad:
        raise CliError("Parti da completare: " + "; ".join(bad))
    week = engine.sent_this_week(ctx["today"])
    total = week + len(chosen)
    over = total > cfg.weekly_limit
    if not args.conferma:
        _out(f"NESSUNA MAIL INVIATA. Riepilogo: {len(chosen)} mail, settimana {week} → {total} (soglia {cfg.weekly_limit}).")
        if over:
            _out("Sopra la soglia settimanale: serviranno anche --oltre-soglia e l'ok esplicito di Jacopo.")
        _out("Per inviare davvero, dopo l'ok di Jacopo, rilancia lo stesso comando con --conferma.")
        return NEEDS_CONFIRM
    if over and not args.oltre_soglia:
        _out(f"NESSUNA MAIL INVIATA: arriveresti a {total} mail questa settimana (soglia {cfg.weekly_limit}). "
             "Chiedi a Jacopo e, se è d'accordo, aggiungi --oltre-soglia.")
        return NEEDS_CONFIRM
    if len(chosen) > 1:
        _out(f"Invio {len(chosen)} mail con pausa casuale di {cfg.pause_min:g}-{cfg.pause_max:g} s "
             f"(circa {engine.estimated_minutes(cfg, len(chosen))} min).")
    ok, failed = engine.send_batch(session, chosen, ctx["today"], log=_out, sleep=ctx["sleep"])
    _out(f"Fatto: {ok} inviate, {len(failed)} non inviate.")
    return OK if not failed else ERROR


def cmd_whatsapp(args, ctx) -> int:
    session = ctx["connect"](ctx["cfg"], need_mailbox=False)
    actions, _ = session.build_plan(ctx["today"])
    a = _locate(session, actions, args.locale)
    if a.kind != "whatsapp":
        raise CliError(f"'{a.venue.name}': l'azione di oggi è {a.label}, non WhatsApp")
    _apply_overrides(a, args.valore, None, args.testo_file)
    if engine.problems(a):
        raise CliError("Completa prima: " + ", ".join(engine.problems(a)))
    link = planner.whatsapp_link(planner.mobile_number(a.venue.phone), a.body)
    if not args.inviato:
        _print_preview(session, a)
        _out("Link da aprire (WhatsApp con il testo pronto): " + link)
        if args.apri:
            webbrowser.open(link)
        _out("Quando Jacopo conferma di averlo inviato, rilancia con --inviato per aggiornare funnel e cronologia.")
        return NEEDS_CONFIRM
    engine.register_whatsapp(session, a, ctx["today"])
    _out(f"✓ {a.venue.name}: WhatsApp registrato nel funnel e nella cronologia")
    return OK


def cmd_segna(args, ctx) -> int:
    if not args.conferma:
        _out(f"NIENTE MODIFICATO. Imposterei 'Mail step' = {args.valore} per '{args.locale}' "
             "(riga cercata per nome) e lo scriverei in cronologia. Rilancia con --conferma dopo l'ok di Jacopo.")
        return NEEDS_CONFIRM
    session = ctx["connect"](ctx["cfg"], need_mailbox=False)
    changes = engine.close_sequence(session, args.locale, args.valore, ctx["today"])
    _out(f"✓ {args.locale}: Mail step = {args.valore}" + ("" if changes else " (era già così)"))
    return OK


def cmd_password(args, ctx) -> int:
    email = ctx["cfg"].sender_email
    if not sys.stdin.isatty():
        raise CliError("Questo comando va eseguito da Jacopo in un suo terminale, non da Claude.")
    pw = getpass.getpass(f"Password di {email} (non viene mostrata): ")
    if not pw:
        raise CliError("Password vuota, niente salvato")
    from matcha_mailer.mailbox import Mailbox

    Mailbox(ctx["cfg"], pw).check_login()
    if not keychain.set_password(email, pw):
        raise CliError("Login riuscito ma non riesco a salvarla nel portachiavi di Windows")
    _out("Password verificata con Aruba e salvata nel portachiavi di Windows.")
    return OK


# ------------------------------------------------------------------ entry point


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m matcha_mailer", description="Matcha Mailer da riga di comando")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("verifica", help="controlla configurazione, credenziali e accessi")
    s.add_argument("--offline", action="store_true", help="non si collega a Google e Aruba")
    s.set_defaults(fn=cmd_verifica)

    s = sub.add_parser("stato", help="azioni da fare oggi e locali in attesa")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_stato)

    def overrides(sp, subject=True):
        sp.add_argument("--valore", action="append", default=[], metavar="NOME=VALORE",
                        help="completa una parte tra graffe, es. numero_coppie=12")
        if subject:
            sp.add_argument("--oggetto", help="oggetto modificato (un solo locale)")
        sp.add_argument("--testo-file", help="file UTF-8 con il testo modificato (un solo locale)")

    def riattiva(sp):
        sp.add_argument("--riattiva", action="store_true",
                        help="tratta i locali \"00 - perso\" indicati come \"10 - nuovo\" (solo su richiesta di Jacopo)")

    s = sub.add_parser("anteprima", help="mostra la mail o il WhatsApp di un locale")
    s.add_argument("locale")
    overrides(s)
    riattiva(s)
    s.set_defaults(fn=cmd_anteprima)

    s = sub.add_parser("prova", help="invia la mail di un locale solo a te stesso")
    s.add_argument("locale")
    overrides(s)
    riattiva(s)
    s.set_defaults(fn=cmd_prova)

    s = sub.add_parser("invia", help="invia le mail ai locali indicati (serve --conferma)")
    s.add_argument("locali", nargs="+")
    overrides(s)
    s.add_argument("--conferma", action="store_true", help="invia davvero")
    s.add_argument("--oltre-soglia", action="store_true", help="consente di superare la soglia settimanale")
    riattiva(s)
    s.set_defaults(fn=cmd_invia)

    s = sub.add_parser("whatsapp", help="link WhatsApp con testo pronto; --inviato per registrarlo")
    s.add_argument("locale")
    overrides(s, subject=False)
    s.add_argument("--apri", action="store_true", help="apre il link nel browser")
    s.add_argument("--inviato", action="store_true", help="registra l'invio nel funnel e in cronologia")
    s.set_defaults(fn=cmd_whatsapp)

    s = sub.add_parser("segna", help="chiude la sequenza di un locale: risposta o stop")
    s.add_argument("locale")
    s.add_argument("valore", choices=["risposta", "stop"])
    s.add_argument("--conferma", action="store_true")
    s.set_defaults(fn=cmd_segna)

    s = sub.add_parser("password", help="salva la password Aruba (solo Jacopo, in un suo terminale)")
    s.set_defaults(fn=cmd_password)
    return p


def run(argv: list[str], connect=None, today: date | None = None, cfg=None, sleep=None) -> int:
    import time

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    try:
        ctx = {
            "cfg": cfg or config_mod.load_config(),
            "connect": connect or _connect,
            "today": today or date.today(),
            "sleep": sleep or time.sleep,
        }
        return args.fn(args, ctx)
    except (CliError, config_mod.ConfigMissing, ValueError) as exc:
        _out(f"ERRORE: {exc}")
        return ERROR
    except Exception as exc:  # noqa: BLE001
        _out(f"ERRORE: {type(exc).__name__}: {exc}")
        return ERROR


def main() -> None:
    raise SystemExit(run(sys.argv[1:]))
