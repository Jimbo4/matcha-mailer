"""Aruba password in the Windows credential store (never in a file, never printed)."""

from __future__ import annotations

SERVICE = "matcha-mailer"


def _kr():
    try:
        import keyring

        return keyring
    except Exception:
        return None


def get_password(email: str) -> str | None:
    kr = _kr()
    if not kr:
        return None
    try:
        return kr.get_password(SERVICE, email)
    except Exception:
        return None


def set_password(email: str, password: str) -> bool:
    kr = _kr()
    if not kr:
        return False
    try:
        kr.set_password(SERVICE, email, password)
        return True
    except Exception:
        return False


def delete_password(email: str) -> None:
    kr = _kr()
    if kr:
        try:
            kr.delete_password(SERVICE, email)
        except Exception:
            pass
