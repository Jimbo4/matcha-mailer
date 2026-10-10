"""Matcha Mailer window: list of venues with checkboxes, editable preview, send with confirmation."""

from __future__ import annotations

import imaplib
import logging
import queue
import smtplib
import sys
import threading
import traceback
import tkinter as tk
import webbrowser
from datetime import date
from tkinter import messagebox, simpledialog, ttk

from matcha_mailer import config as config_mod
from matcha_mailer import engine, planner
from matcha_mailer.mailbox import Mailbox

ACCENT = "#38A096"
GREY = "#8A9A9A"
KEYRING_SERVICE = "matcha-mailer"
CHECK_ON, CHECK_OFF = "☑", "☐"

config_mod.DATA_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=config_mod.DATA_DIR / "mailer.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("matcha_mailer")


def _fix_surrogates(s: str) -> str:
    """Tk may hand back emoji as surrogate pairs: join them into real characters."""
    try:
        return s.encode("utf-16", "surrogatepass").decode("utf-16")
    except UnicodeError:
        return s


# ------------------------------------------------------------------ password


def _keyring():
    try:
        import keyring

        return keyring
    except Exception:
        return None


def get_password(root, email: str, force_ask: bool = False) -> str | None:
    kr = _keyring()
    if kr and not force_ask:
        try:
            pw = kr.get_password(KEYRING_SERVICE, email)
            if pw:
                return pw
        except Exception:
            pass
    pw = simpledialog.askstring(
        "Password Aruba",
        f"Password della casella {email}\n(la salvo nel portachiavi di Windows, non in un file)",
        show="•",
        parent=root,
    )
    if pw and kr:
        try:
            kr.set_password(KEYRING_SERVICE, email, pw)
        except Exception:
            pass
    return pw


def forget_password(email: str) -> None:
    kr = _keyring()
    if kr:
        try:
            kr.delete_password(KEYRING_SERVICE, email)
        except Exception:
            pass


# ------------------------------------------------------------------ app


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.cfg: config_mod.Config | None = None
        self.session: engine.Session | None = None
        self.actions: list[planner.Action] = []
        self.by_iid: dict[str, planner.Action] = {}
        self.current: planner.Action | None = None
        self._loaded = ("", "")
        self.busy = False
        self.today = date.today()

        root.title("Matcha Mailer")
        root.geometry("1280x800")
        root.minsize(1100, 660)
        root.report_callback_exception = self._tk_error
        self._style()
        self._build()
        root.after(100, self._poll)
        root.after(200, self.start)

    # ------------------------------------------------------------ layout
    def _style(self):
        st = ttk.Style(self.root)
        if sys.platform == "win32":
            import tkinter.font as tkfont

            for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont"):
                tkfont.nametofont(name).configure(family="Segoe UI", size=10)
        st.configure("Treeview", rowheight=26)
        st.configure("Title.TLabel", font=("Georgia", 18, "bold"), foreground=ACCENT)
        st.configure("Muted.TLabel", foreground=GREY)
        st.configure("Warn.TLabel", foreground="#B3261E")
        st.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), foreground=ACCENT)

    def _build(self):
        top = ttk.Frame(self.root, padding=(14, 10, 14, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Matcha", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="  mailer locali", style="Muted.TLabel").pack(side="left", pady=(6, 0))
        self.btn_reload = ttk.Button(top, text="Aggiorna", command=self.reload)
        self.btn_reload.pack(side="right")
        self.week_lbl = ttk.Label(top, text="", style="Muted.TLabel")
        self.week_lbl.pack(side="right", padx=12)
        self.status = ttk.Label(self.root, text="", padding=(14, 0), style="Muted.TLabel")
        self.status.pack(fill="x")

        self.logbox = tk.Text(self.root, height=6, wrap="word", state="disabled", relief="flat",
                              background="#F4F7F7", padx=10, pady=6, font="TkTextFont")
        self.logbox.pack(side="bottom", fill="x", padx=14, pady=(0, 12))
        bottom = ttk.Frame(self.root, padding=(14, 0, 14, 6))
        bottom.pack(side="bottom", fill="x")
        ttk.Button(bottom, text="Seleziona tutte", command=lambda: self._select_all(True)).pack(side="left")
        ttk.Button(bottom, text="Deseleziona tutte", command=lambda: self._select_all(False)).pack(side="left", padx=6)
        ttk.Label(bottom, text="Clic sulla casella per includere o escludere un locale", style="Muted.TLabel").pack(side="left", padx=10)
        self.btn_send = ttk.Button(bottom, text="Invia selezionate", style="Accent.TButton", command=self.send_selected)
        self.btn_send.pack(side="right")

        pane = ttk.PanedWindow(self.root, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=14, pady=8)

        left = ttk.Frame(pane)
        cols = ("sel", "locale", "zona", "azione", "dest")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        for c, title, w, anchor in [
            ("sel", "", 30, "center"), ("locale", "Locale", 170, "w"), ("zona", "Zona", 100, "w"),
            ("azione", "Azione", 230, "w"), ("dest", "Destinatario", 180, "w"),
        ]:
            self.tree.heading(c, text=title)
            self.tree.column(c, width=w, minwidth=30, anchor=anchor, stretch=c in ("azione", "dest"))
        self.tree.tag_configure("info", foreground=GREY)
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<space>", lambda e: self._toggle(self.tree.focus()))
        pane.add(left, weight=5)

        right = ttk.Frame(pane, padding=(12, 0, 0, 0))
        self.prev_title = ttk.Label(right, text="Seleziona un locale per vedere l'anteprima", style="Muted.TLabel")
        self.prev_title.pack(anchor="w")
        ttk.Label(right, text="Oggetto").pack(anchor="w", pady=(8, 2))
        self.subject = ttk.Entry(right)
        self.subject.pack(fill="x")
        ttk.Label(right, text="Testo (la firma si aggiunge da sola)").pack(anchor="w", pady=(8, 2))
        body_frame = ttk.Frame(right)
        body_frame.pack(fill="both", expand=True)
        self.body = tk.Text(body_frame, wrap="word", undo=True, padx=8, pady=8, relief="solid", borderwidth=1,
                            font="TkTextFont")
        bsb = ttk.Scrollbar(body_frame, orient="vertical", command=self.body.yview)
        self.body.configure(yscrollcommand=bsb.set)
        self.body.pack(side="left", fill="both", expand=True)
        bsb.pack(side="left", fill="y")
        self.missing_lbl = ttk.Label(right, text="", style="Warn.TLabel")
        self.missing_lbl.pack(anchor="w", pady=(4, 0))
        row = ttk.Frame(right)
        row.pack(fill="x", pady=(6, 0))
        self.btn_reset = ttk.Button(row, text="Ripristina dal modello", command=self.reset_text)
        self.btn_reset.pack(side="left")
        self.btn_test = ttk.Button(row, text="Invia prova a me", command=self.send_test)
        self.btn_test.pack(side="left", padx=6)
        self.btn_wa = ttk.Button(row, text="Apri WhatsApp", command=self.open_whatsapp)
        self.btn_wa.pack(side="left")
        pane.add(right, weight=4)
        self.root.after(80, lambda: pane.sashpos(0, int(self.root.winfo_width() * 0.57)))
        for w in (self.subject, self.body):
            w.bind("<KeyRelease>", lambda e: self._update_missing())

        self._set_preview_enabled(False)

    # ------------------------------------------------------------ helpers
    def say(self, text: str):
        log.info(text)
        self.logbox.configure(state="normal")
        self.logbox.insert("end", text + "\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def _tk_error(self, exc, val, tb):
        log.error("".join(traceback.format_exception(exc, val, tb)))
        messagebox.showerror("Errore", str(val), parent=self.root)

    def _set_busy(self, busy: bool, text: str = ""):
        self.busy = busy
        self.status.configure(text=text)
        state = "disabled" if busy else "normal"
        for b in (self.btn_send, self.btn_reload, self.btn_test, self.btn_wa, self.btn_reset):
            b.configure(state=state)
        self.root.configure(cursor="watch" if busy else "")
        if not busy:
            self._refresh_buttons()

    def run_bg(self, fn, status: str, done=None):
        self._set_busy(True, status)

        def worker():
            try:
                res = fn()
                self.q.put(("done", done, res))
            except Exception as exc:  # noqa: BLE001
                self.q.put(("error", exc, traceback.format_exc()))

        threading.Thread(target=worker, daemon=True).start()

    def bg_say(self, text: str):
        self.q.put(("log", text, None))

    def _poll(self):
        try:
            while True:
                kind, a, b = self.q.get_nowait()
                if kind == "log":
                    self.say(a)
                elif kind == "done":
                    self._set_busy(False)
                    if a:
                        a(b)
                elif kind == "error":
                    self._set_busy(False)
                    log.error(b)
                    self._handle_error(a)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _handle_error(self, exc: Exception):
        imap_auth = isinstance(exc, imaplib.IMAP4.error) and "auth" in str(exc).lower()
        if isinstance(exc, smtplib.SMTPAuthenticationError) or imap_auth:
            forget_password(self.cfg.sender_email if self.cfg else "")
            messagebox.showerror("Password Aruba", "Aruba non ha accettato la password. Riprova.", parent=self.root)
            self.start(force_password=True)
            return
        self.say(f"Errore: {exc}")
        messagebox.showerror("Errore", str(exc), parent=self.root)

    # ------------------------------------------------------------ startup
    def start(self, force_password: bool = False):
        try:
            self.cfg = config_mod.load_config()
        except config_mod.ConfigMissing as exc:
            messagebox.showwarning("Configurazione", str(exc), parent=self.root)
            self.status.configure(text=str(exc))
            return
        pw = get_password(self.root, self.cfg.sender_email, force_ask=force_password)
        if not pw:
            self.status.configure(text="Serve la password della casella per continuare. Premi Aggiorna.")
            return
        cfg = self.cfg

        def job():
            self.bg_say("Accesso a Google (la prima volta si apre il browser)…")
            session = self.session or engine.Session.connect(cfg)
            self.bg_say("Accesso alla casella Aruba…")
            mb = Mailbox(cfg, pw)
            mb.check_login()
            session.mailbox = mb
            session.reload_texts()
            self.bg_say("Leggo il funnel e controllo chi ha risposto…")
            return session, *session.build_plan(self.today)

        self.run_bg(job, "Mi collego…", done=self._loaded_plan)

    def reload(self):
        if any(a.edited for a in self.actions):
            if not messagebox.askyesno("Aggiorna", "Hai modificato dei testi in anteprima: aggiornando li perdi. Continuo?", parent=self.root):
                return
        if not self.session:
            self.start()
            return
        session = self.session

        def job():
            session.reload_texts()
            return session, *session.build_plan(self.today)

        self.run_bg(job, "Aggiorno…", done=self._loaded_plan)

    def _loaded_plan(self, res):
        self.session, self.actions, warnings = res
        for w in warnings:
            self.say("Attenzione: " + w)
        self._fill_tree()
        due = sum(1 for a in self.actions if a.selectable)
        self.status.configure(text=f"{due} azioni da fare oggi, {len(self.actions) - due} in attesa o da gestire a mano (in grigio)")
        self.say("Pronto.")

    # ------------------------------------------------------------ table
    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.by_iid.clear()
        for i, a in enumerate(self.actions):
            iid = str(i)
            self.by_iid[iid] = a
            self.tree.insert("", "end", iid=iid, values=self._row(a), tags=() if a.selectable else ("info",))
        self.current = None
        self._show(None)
        self._refresh_buttons()

    def _row(self, a: planner.Action):
        check = (CHECK_ON if a.selected else CHECK_OFF) if a.selectable else ""
        dest = a.venue.email if a.is_mail else (a.venue.phone if a.kind == "whatsapp" else "")
        label = a.label if a.selectable else a.status
        return (check, a.venue.name, a.venue.zone, label, dest)

    def _on_click(self, event):
        if self.tree.identify_region(event.x, event.y) == "cell" and self.tree.identify_column(event.x) == "#1":
            self._toggle(self.tree.identify_row(event.y))

    def _toggle(self, iid: str):
        a = self.by_iid.get(iid)
        if not a or not a.selectable or self.busy:
            return
        a.selected = not a.selected
        self.tree.item(iid, values=self._row(a))
        self._refresh_buttons()

    def _select_all(self, value: bool):
        for iid, a in self.by_iid.items():
            if a.selectable and a.kind != "whatsapp":
                a.selected = value
                self.tree.item(iid, values=self._row(a))
        self._refresh_buttons()

    def _refresh_buttons(self):
        n = sum(1 for a in self.actions if a.selected and a.selectable and a.is_mail)
        self.btn_send.configure(text=f"Invia selezionate ({n})", state="normal" if n and not self.busy else "disabled")
        if self.cfg:
            sent = engine.sent_this_week(self.today)
            self.week_lbl.configure(text=f"Mail inviate questa settimana: {sent} (soglia {self.cfg.weekly_limit})")
        cur = self.current
        self.btn_wa.configure(state="normal" if cur and cur.kind == "whatsapp" and not self.busy else "disabled")
        self.btn_test.configure(state="normal" if cur and cur.is_mail and not self.busy else "disabled")
        self.btn_reset.configure(state="normal" if cur and cur.selectable and not self.busy else "disabled")

    # ------------------------------------------------------------ preview
    def _set_preview_enabled(self, on: bool):
        self.subject.configure(state="normal" if on else "disabled")
        self.body.configure(state="normal" if on else "disabled")

    def _save_editor(self):
        a = self.current
        if not a or not a.selectable:
            return
        subj = _fix_surrogates(self.subject.get())
        body = _fix_surrogates(self.body.get("1.0", "end-1c"))
        if (subj, body) != self._loaded:
            a.subject, a.body, a.edited = subj, body, True
            self._loaded = (subj, body)

    def _on_select(self, _event=None):
        self._save_editor()
        sel = self.tree.selection()
        self.current = self.by_iid.get(sel[0]) if sel else None
        self._show(self.current)
        self._refresh_buttons()

    def _show(self, a: planner.Action | None):
        self._set_preview_enabled(True)
        self.subject.delete(0, "end")
        self.body.delete("1.0", "end")
        if not a:
            self.prev_title.configure(text="Seleziona un locale per vedere l'anteprima")
            self._set_preview_enabled(False)
            self.missing_lbl.configure(text="")
            return
        if not a.selectable:
            self.prev_title.configure(text=f"{a.venue.name}: {a.status}")
            note = a.venue.notes or ""
            self.body.insert("1.0", f"Note dal funnel:\n{note}")
            self._set_preview_enabled(False)
            self.missing_lbl.configure(text="")
            return
        to = a.venue.email if a.is_mail else planner.mobile_number(a.venue.phone)
        cc = (", in copia " + ", ".join(self.cfg.cc)) if (a.is_mail and self.cfg.cc) else ""
        self.prev_title.configure(text=f"{a.label}  ·  a {to}{cc}")
        self.subject.insert(0, a.subject)
        self.body.insert("1.0", a.body)
        if a.kind == "whatsapp":
            self.subject.configure(state="disabled")
        self._loaded = (_fix_surrogates(self.subject.get()), _fix_surrogates(self.body.get("1.0", "end-1c")))
        self._update_missing()

    def _update_missing(self):
        a = self.current
        if not a or not a.selectable:
            return
        text = self.subject.get() + "\n" + self.body.get("1.0", "end-1c")
        from matcha_mailer.texts import missing_placeholders

        miss = missing_placeholders(text)
        self.missing_lbl.configure(text=("Da completare prima dell'invio: " + ", ".join("{" + m + "}" for m in miss)) if miss else "")

    def reset_text(self):
        a = self.current
        if not a or not self.session:
            return
        self.session.reload_texts()
        a.edited = False
        engine.render(a, self.session.texts)
        self._show(a)

    # ------------------------------------------------------------ actions
    def send_test(self):
        self._save_editor()
        a = self.current
        if not a or not a.is_mail:
            return
        if engine.problems(a):
            messagebox.showwarning("Prova", "Completa prima: " + ", ".join(engine.problems(a)), parent=self.root)
            return
        self.run_bg(lambda: self.session.send_test(a), "Invio la prova…",
                    done=lambda _: self.say(f"Prova inviata a {self.cfg.sender_email}: {a.venue.name}, {a.label}"))

    def send_selected(self):
        self._save_editor()
        sel = [a for a in self.actions if a.selectable and a.selected and a.is_mail]
        if not sel:
            return
        bad = [f"• {a.venue.name}: " + ", ".join("{" + p + "}" for p in engine.problems(a)) for a in sel if engine.problems(a)]
        if bad:
            messagebox.showwarning(
                "Testi da completare",
                "Queste mail hanno ancora parti da completare nell'anteprima:\n\n" + "\n".join(bad)
                + "\n\nCompletale oppure togli la spunta.",
                parent=self.root,
            )
            return
        week = engine.sent_this_week(self.today)
        total = week + len(sel)
        limit = self.cfg.weekly_limit
        if total > limit and not messagebox.askyesno(
            "Soglia settimanale",
            f"Questa settimana hai già inviato {week} mail. Con queste {len(sel)} arrivi a {total}, "
            f"sopra la soglia di {limit}.\n\nVuoi procedere comunque?",
            icon="warning", parent=self.root,
        ):
            return
        lines = "\n".join(f"• {a.venue.name}: {a.label} → {a.venue.email}" for a in sel)
        cc = f" (in copia {', '.join(self.cfg.cc)})" if self.cfg.cc else ""
        if not messagebox.askyesno(
            "Conferma invio",
            f"Invio {len(sel)} mail da {self.cfg.sender_email}{cc}:\n\n{lines}\n\n"
            "Dopo l'invio aggiorno il funnel (righe cercate per nome) e la cronologia. Procedo?",
            parent=self.root,
        ):
            return
        self.run_bg(lambda: self._send_batch(sel), f"Invio {len(sel)} mail…", done=self._after_send)

    def _send_batch(self, sel):
        today = self.today
        bullets, ok, failed = [], 0, []
        for a in sel:
            try:
                changes, warn = self.session.send(a, today)
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{a.venue.name}: {exc}")
                self.bg_say(f"✗ {a.venue.name}: non inviata ({exc})")
                continue
            ok += 1
            self.bg_say(f"✓ {a.venue.name}: {a.label} inviata a {a.venue.email}" + (f" ({warn})" if warn else ""))
            extra = f"{a.label} inviata a {a.venue.email}" + (f"; {warn}" if warn else "")
            bullets.append(engine.describe(changes, extra) or f"{a.venue.name}: {extra}")
        try:
            self.session.write_history(today, f"Mailer: {ok} mail inviate", bullets)
            self.bg_say("Cronologia aggiornata.")
        except Exception as exc:  # noqa: BLE001
            self.bg_say(f"Attenzione: cronologia non aggiornata ({exc}). Dettagli in data/invii.csv")
        return ok, failed

    def _after_send(self, res):
        ok, failed = res
        msg = f"Inviate {ok} mail."
        if failed:
            msg += "\n\nNon inviate:\n" + "\n".join(failed)
        messagebox.showinfo("Invio completato", msg, parent=self.root)
        self.reload()

    def open_whatsapp(self):
        self._save_editor()
        a = self.current
        if not a or a.kind != "whatsapp":
            return
        if engine.problems(a):
            messagebox.showwarning("WhatsApp", "Completa prima: " + ", ".join(engine.problems(a)), parent=self.root)
            return
        number = planner.mobile_number(a.venue.phone)
        webbrowser.open(planner.whatsapp_link(number, a.body))
        if messagebox.askyesno("WhatsApp", f"Hai inviato il messaggio a {a.venue.name}?\nSe sì, aggiorno funnel e cronologia.", parent=self.root):
            def job():
                changes = self.session.mark_whatsapp_sent(a, self.today)
                bullet = engine.describe(changes, "WhatsApp con lettera d'intenti inviato") or f"{a.venue.name}: WhatsApp inviato"
                self.session.write_history(self.today, "Mailer: WhatsApp inviato", [bullet])
                return a.venue.name

            self.run_bg(job, "Aggiorno il funnel…", done=lambda name: (self.say(f"✓ {name}: WhatsApp registrato"), self.reload()))


def main():
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
