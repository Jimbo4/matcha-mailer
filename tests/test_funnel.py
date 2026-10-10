import pytest

from conftest import HEADER, FakeWorksheet
from matcha_mailer.funnel import Funnel, FunnelError


def test_load_maps_columns_by_name(sheet):
    vs = Funnel(sheet).load()
    assert [v.name for v in vs] == ["Bar Uno", "Pub Due", "Bar Tre"]
    assert vs[0].probability == "10 - nuovo" and vs[0].email == "info@baruno.it"


def test_update_finds_row_by_name_after_resort(sheet):
    f = Funnel(sheet)
    # someone re-sorts the sheet between reading and writing
    sheet.values[1], sheet.values[3] = sheet.values[3], sheet.values[1]
    changes = f.update_by_name("bar uno", {"last_action": "Email 1", "mail_step": "1", "zone": "Isola"})
    row = next(r for r in sheet.values if r[0] == "Bar Uno")
    assert row[7] == "Email 1" and row[10] == "1"
    assert {c.column for c in changes} == {"Ultima azione fatta", "Mail step"}  # zone unchanged: not written
    assert all(rng.endswith("4") for rng, _ in sheet.writes)  # Bar Uno is now on row 4
    other = next(r for r in sheet.values if r[0] == "Bar Tre")
    assert other[7] == "Di persona"


def test_duplicate_or_missing_name_is_not_written(sheet):
    sheet.values.append(["Bar Uno", "", "", "", "", "", "10 - nuovo", "", "", ""])
    with pytest.raises(FunnelError):
        Funnel(sheet).update_by_name("Bar Uno", {"mail_step": "1"})
    with pytest.raises(FunnelError):
        Funnel(sheet).update_by_name("Inesistente", {"mail_step": "1"})
    assert sheet.writes == []


def test_add_mailer_columns_after_last_header():
    ws = FakeWorksheet([HEADER, ["Bar", "", "", "", "", "", "10 - nuovo", "", "", "Nota"]])
    f = Funnel(ws)
    assert f.add_mailer_columns() == ["Mail step", "Mail ultimo invio", "Mail prossimo invio", "Mail thread"]
    assert ws.values[0][10:14] == ["Mail step", "Mail ultimo invio", "Mail prossimo invio", "Mail thread"]
    assert ws.values[1][9] == "Nota"
    assert f.add_mailer_columns() == []
