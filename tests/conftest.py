import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from matcha_mailer.config import Config  # noqa: E402

HEADER = ["Nome attività", "Luogo attività o sede", "Zona", "Referente", "Cellulare", "Mail",
          "Probabilitá", "Ultima azione fatta", "Last contacted", "Note"]


class FakeWorksheet:
    def __init__(self, rows):
        self.values = [list(r) for r in rows]
        self.col_count = 26
        self.writes = []

    def get_all_values(self):
        return [list(r) for r in self.values]

    def row_values(self, n):
        return list(self.values[n - 1])

    def add_cols(self, n):
        self.col_count += n

    def batch_update(self, data, value_input_option="RAW"):
        from gspread.utils import a1_to_rowcol

        for item in data:
            r, c = a1_to_rowcol(item["range"])
            while len(self.values) < r:
                self.values.append([])
            row = self.values[r - 1]
            while len(row) < c:
                row.append("")
            row[c - 1] = item["values"][0][0]
            self.writes.append((item["range"], item["values"][0][0]))


@pytest.fixture
def sheet():
    return FakeWorksheet([
        HEADER + ["Mail step", "Mail ultimo invio", "Mail prossimo invio", "Mail thread"],
        ["Bar Uno", "Via A 1", "Isola", "Mario (titolare)", "02 1234 5678", "info@baruno.it",
         "10 - nuovo", "Chiamata", "", "Lasciato nostro numero, in attesa"],
        ["Pub Due", "Via B 2", "Navigli", "", "", "pubdue@gmail.com", "10 - nuovo", "Email", "", ""],
        ["Bar Tre", "Via C 3", "Dergano", "Anna", "345 111 2233", "", "50 - curioso", "Di persona",
         "28/09/2026", "Interessati"],
    ])


@pytest.fixture
def cfg(tmp_path):
    return Config(
        sender_email="jacopo@matchadating.it", sender_name="Jacopo Marcolini", cc=["info@matchadating.it"],
        smtp_host="smtp", smtp_port=465, imap_host="imap", imap_port=993, sent_folder="",
        funnel_id="F", funnel_sheet="Sheet1", history_doc_id="H", letter_doc_id="L",
        letter_filename="Lettera.pdf", client_secret=tmp_path / "c.json", token_path=tmp_path / "t.json",
        days_mail_2=4, days_mail_3=6, weekly_limit=20, reply_lookback_days=60,
    )
