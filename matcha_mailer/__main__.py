import sys
import traceback


def _fatal(text: str) -> None:
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "data" / "errore_avvio.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0, f"Il Matcha Mailer non si è avviato. Dettagli in {path}", "Matcha Mailer", 0x10
        )


try:
    from matcha_mailer.app import main
except Exception:  # noqa: BLE001
    _fatal(traceback.format_exc())
    raise SystemExit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        _fatal(traceback.format_exc())
        raise SystemExit(1)
