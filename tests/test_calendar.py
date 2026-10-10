from datetime import date

from matcha_mailer import calendar_it as c


def test_tomorrow_label():
    assert c.tomorrow_label(date(2026, 10, 15)) == "domani"  # Thursday
    assert c.tomorrow_label(date(2026, 10, 16)) == "lunedì"  # Friday
    assert c.tomorrow_label(date(2026, 12, 4)) == "mercoledì"  # 7 and 8 December are holidays in Milan


def test_easter_monday_and_working_days():
    assert not c.is_working_day(date(2027, 3, 29))  # Easter Monday 2027
    assert c.add_working_days(date(2026, 10, 30), 1) == date(2026, 11, 2)
    assert c.add_working_days(date(2026, 12, 23), 2) == date(2026, 12, 28)


def test_parse():
    assert c.parse("28/09/2026") == date(2026, 9, 28)
    assert c.parse("1/10/26") == date(2026, 10, 1)
    assert c.parse("") is None and c.parse("ieri") is None
