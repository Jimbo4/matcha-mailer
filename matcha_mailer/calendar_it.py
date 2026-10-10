"""Working days in Milan: weekends, Italian national holidays, Easter Monday, Sant'Ambrogio."""

from __future__ import annotations

from datetime import date, timedelta

WEEKDAYS_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]

_FIXED = {(1, 1), (6, 1), (25, 4), (1, 5), (2, 6), (15, 8), (1, 11), (7, 12), (8, 12), (25, 12), (26, 12)}


def _easter(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def is_working_day(d: date) -> bool:
    if d.weekday() >= 5 or (d.day, d.month) in _FIXED:
        return False
    return d != _easter(d.year) + timedelta(days=1)


def add_working_days(start: date, n: int) -> date:
    d = start
    added = 0
    while added < n:
        d += timedelta(days=1)
        if is_working_day(d):
            added += 1
    return d


def next_working_day(start: date) -> date:
    return add_working_days(start, 1)


def tomorrow_label(today: date) -> str:
    """'domani' if tomorrow is a working day, otherwise the weekday name of the next working day."""
    nxt = next_working_day(today)
    if nxt == today + timedelta(days=1):
        return "domani"
    return WEEKDAYS_IT[nxt.weekday()]


def fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def parse(s: str) -> date | None:
    s = (s or "").strip()
    for sep in ("/", "-", "."):
        parts = s.split(sep)
        if len(parts) == 3:
            try:
                dd, mm, yy = (int(p) for p in parts)
                if yy < 100:
                    yy += 2000
                return date(yy, mm, dd)
            except ValueError:
                return None
    return None
