"""Tests for ingest.py, built only from rules.md.

Every test runs ingest.py in a new temporary folder with its own test.db and
its own temporary log. The folder is deleted when the test ends, whether the
test passed or failed. The books.db and ingestion-log.json in this folder are
never used; a check after every test confirms they were not created, changed
or deleted.

How the tests run ingest.py (a test setup choice, not a rule about the data;
see README.md):

    python ingest.py --db <temp>/test.db --log <temp>/ingestion-log.json FILE.csv ...

- The catalog is the table named `books`, with one column per source header.
- ingestion-log.json is a JSON list with one entry per run, oldest first.
- Each entry has a `totals` object with the whole-number counts rows_read,
  loaded, updated, skipped, rejected, warnings and repairs.
- The action sentence for a rejected row appears somewhere in that run's entry.
"""

import csv
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
INGEST = os.path.join(HERE, "ingest.py")
BOOKS_CSV = os.path.join(HERE, "books.csv")
BATCH2_CSV = os.path.join(HERE, "books-batch2.csv")
REAL_FILES = [os.path.join(HERE, "books.db"), os.path.join(HERE, "ingestion-log.json")]

# rules.md, "Files and the report": the action sentences, word for word.
ISBN_ERROR = "Find the correct ISBN, correct the row, and load the file again."
CONFLICT = "Check which value or book is correct."

COUNTS = ["rows_read", "loaded", "updated", "skipped", "rejected", "warnings", "repairs"]


# ---------------------------------------------------------------------------
# Setup and teardown
# ---------------------------------------------------------------------------

def _fingerprint(path):
    """What a real file looks like now: missing, or its SHA-256."""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture(autouse=True)
def real_files_untouched():
    """rules.md: tests never use the real books.db or ingestion-log.json."""
    before = {path: _fingerprint(path) for path in REAL_FILES}
    yield
    after = {path: _fingerprint(path) for path in REAL_FILES}
    assert after == before, "a test created, changed or deleted the real books.db or ingestion-log.json"


class Workspace:
    """A temporary folder holding test.db, a temporary log and test CSV files."""

    def __init__(self, folder):
        self.folder = folder
        self.db = os.path.join(folder, "test.db")
        self.log = os.path.join(folder, "ingestion-log.json")
        # ingest.py is copied in, so even a run that ignored --db or --log
        # could only write inside this temporary folder.
        self.ingest = os.path.join(folder, "ingest.py")
        shutil.copyfile(INGEST, self.ingest)
        self.output = ""

    def run(self, *csv_paths):
        """Run ingest.py once on the given files, in order. Return that run's log entry."""
        result = subprocess.run(
            [sys.executable, self.ingest, "--db", self.db, "--log", self.log, *csv_paths],
            cwd=self.folder, capture_output=True, text=True, timeout=600,
        )
        self.output = "exit code %d\nstdout:\n%s\nstderr:\n%s" % (
            result.returncode, result.stdout, result.stderr)
        return self.entries()[-1]

    def entries(self):
        assert os.path.exists(self.log), "ingest.py wrote no log.\n" + self.output
        with open(self.log, encoding="utf-8") as f:
            entries = json.load(f)
        assert isinstance(entries, list) and entries, "the log is not a list of runs.\n" + self.output
        return entries

    def books(self):
        """Every row of the books table, as dicts, in a stable order."""
        assert os.path.exists(self.db), "ingest.py created no test.db.\n" + self.output
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            rows = [dict(row) for row in connection.execute("SELECT * FROM books")]
        finally:
            connection.close()
        return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, default=str))

    def write_csv(self, name, rows):
        """Write a CSV with the 23 headers of the supplied books.csv."""
        path = os.path.join(self.folder, name)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return path


@pytest.fixture
def ws():
    folder = tempfile.mkdtemp(prefix="ingest-test-")
    try:
        yield Workspace(folder)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _headers():
    with open(BOOKS_CSV, encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


HEADERS = _headers()


def make_row(number, isbn, isbn13, book_id=None):
    """A new row with a real title and author and its own supplier ID (rules.md, Examples)."""
    row = {name: "" for name in HEADERS}
    row.update({
        "book_id": str(book_id if book_id is not None else 900000 + number),
        "goodreads_book_id": str(800000 + number),
        "best_book_id": str(800000 + number),
        "work_id": str(700000 + number),
        "books_count": "1",
        "isbn": isbn,
        "isbn13": isbn13,
        "authors": "Example Author %d" % number,
        "original_publication_year": "2001.0",
        "original_title": "Example Book %d" % number,
        "title": "Example Book %d" % number,
        "language_code": "eng",
        "average_rating": "4.0",
    })
    return row


def totals(entry):
    assert "totals" in entry, "the log entry has no totals: %s" % entry
    return entry["totals"]


def mentions(entry, sentence):
    return sentence in json.dumps(entry, ensure_ascii=False)


def count_records(path):
    """CSV records after the header, ignoring completely empty lines (rules.md)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return sum(1 for record in csv.reader(f) if record) - 1


# ---------------------------------------------------------------------------
# The examples table in rules.md, one test per row
# ---------------------------------------------------------------------------

def load(isbn, isbn13, repairs, warnings):
    return {"outcome": "load", "isbn": isbn, "isbn13": isbn13, "repairs": repairs, "warnings": warnings}


def reject(sentence):
    return {"outcome": "reject", "sentence": sentence}


# (example number, isbn as supplied, isbn13 as supplied, expected result)
# Stored None means null in the database. Repair and warning counts are exact (rules.md, Examples).
EXAMPLES = [
    (1, "0439139600", "9780439139601", load("0439139600", "9780439139601", 0, 0)),
    (2, "043965548X", "", load("043965548X", "9780439655484", 1, 0)),
    (3, "031200009x", "9780312000097", load("031200009X", "9780312000097", 1, 0)),
    (4, "0-450-19827-8", "9780450198274", load("0450198278", "9780450198274", 1, 0)),
    (5, " 162 001 4750 ", "9781620014752", load("1620014750", "9781620014752", 1, 0)),
    (6, "439023483", "", load("0439023483", "9780439023481", 2, 0)),
    (7, "439554934", "9.78043955493e+12", load("0439554934", "9780439554930", 2, 0)),
    (8, "439023483", "9.78043902348e+12", load("0439023483", "9780439023481", 2, 0)),
    (9, "", "9.78043902348e+12", load(None, None, 0, 1)),
    (10, "", "76783609419.0", load(None, None, 0, 1)),
    (11, "", "9780439139601.0", load(None, None, 0, 1)),
    (12, "04390A3483", "", reject(ISBN_ERROR)),
    (13, "15287463097", "", reject(ISBN_ERROR)),
    (14, "1854433017", "", reject(ISBN_ERROR)),
    (15, "", "", reject(ISBN_ERROR)),
    # Two valid ISBNs for different books: a conflict between the two columns.
    (16, "1555550126", "9781555550134", reject(CONFLICT)),
    (17, "9781982147600", "", load("1982147601", "9781982147600", 2, 0)),
    (18, "", "9798351220413", load(None, "9798351220413", 0, 0)),
    (19, "0439139600", "9780061120085", reject(ISBN_ERROR)),
    (20, "0439139600", "12345", load("0439139600", None, 0, 1)),
    # The move would overwrite a different nonblank isbn13: a conflict between the two columns.
    (21, "9780439139601", "9.7804391396e+12", reject(CONFLICT)),
]


@pytest.mark.parametrize(
    "number, isbn, isbn13, expected", EXAMPLES,
    ids=["example_%02d[%s|%s]" % (n, i.strip() or "blank", j or "blank") for n, i, j, _ in EXAMPLES],
)
def test_example(ws, number, isbn, isbn13, expected):
    path = ws.write_csv("example.csv", [make_row(number, isbn, isbn13)])
    entry = ws.run(path)
    counts = totals(entry)
    books = ws.books()

    assert counts["rows_read"] == 1, ws.output

    if expected["outcome"] == "load":
        assert counts["loaded"] == 1, "expected the row to be loaded (inserted).\n" + ws.output
        assert len(books) == 1
        assert books[0]["isbn"] == expected["isbn"], "stored isbn"
        assert books[0]["isbn13"] == expected["isbn13"], "stored isbn13"
        assert counts["repairs"] == expected["repairs"], "number of repairs"
        assert counts["warnings"] == expected["warnings"], "number of warnings"
    else:
        assert counts["rejected"] == 1, "expected the row to be rejected.\n" + ws.output
        assert counts["loaded"] == counts["updated"] == counts["skipped"] == 0
        assert books == [], "a rejected row must store nothing"
        assert mentions(entry, expected["sentence"]), "missing action sentence: " + expected["sentence"]


def test_example_15_blank_and_blank_is_rejected_even_for_a_known_supplier_id(ws):
    known = make_row(15, "0439139600", "9780439139601", book_id=915015)
    first = ws.write_csv("known.csv", [known])
    ws.run(first)
    before = ws.books()
    assert len(before) == 1, ws.output

    blank = make_row(15, "", "", book_id=915015)
    second = ws.write_csv("blank.csv", [blank])
    entry = ws.run(second)

    assert totals(entry)["rejected"] == 1, ws.output
    assert mentions(entry, ISBN_ERROR)
    assert ws.books() == before, "a rejected row must change nothing"


def test_example_22_same_row_again_is_skipped_without_a_duplicate(ws):
    row = make_row(22, "0439139600", "9780439139601")
    path = ws.write_csv("twice.csv", [row, dict(row)])
    counts = totals(ws.run(path))

    assert counts["rows_read"] == 2, ws.output
    assert counts["loaded"] == 1
    assert counts["skipped"] == 1
    assert counts["rejected"] == 0
    assert len(ws.books()) == 1, "the repeated row must not add a book"


# ---------------------------------------------------------------------------
# Running files again, the log, and the counts
# ---------------------------------------------------------------------------

SUPPLIED = [pytest.param(BOOKS_CSV, id="books.csv"), pytest.param(BATCH2_CSV, id="books-batch2.csv")]


@pytest.mark.parametrize("path", SUPPLIED)
def test_running_the_same_file_twice_creates_no_duplicates(ws, path):
    ws.run(path)
    first = ws.books()
    counts = totals(ws.run(path))
    second = ws.books()

    assert counts["loaded"] == 0, "the second run inserted new books"
    assert len(second) == len(first), "the second run changed the number of books"
    for column in ("isbn", "isbn13"):
        values = [book[column] for book in second if book[column] not in (None, "")]
        assert len(values) == len(set(values)), "two books share an %s" % column


def test_every_run_adds_a_log_entry_without_overwriting_earlier_ones(ws):
    earlier = []
    for path in (BATCH2_CSV, BATCH2_CSV, BOOKS_CSV):
        ws.run(path)
        entries = ws.entries()
        assert len(entries) == len(earlier) + 1, "each run must add exactly one entry"
        assert entries[:-1] == earlier, "an earlier entry was lost or changed"
        earlier = entries


@pytest.mark.parametrize("paths", [
    pytest.param([BOOKS_CSV], id="books.csv"),
    pytest.param([BATCH2_CSV], id="books-batch2.csv"),
    pytest.param([BOOKS_CSV, BOOKS_CSV, BATCH2_CSV], id="three-runs-in-order"),
])
def test_loaded_updated_skipped_and_rejected_add_up_to_rows_read(ws, paths):
    for path in paths:
        counts = totals(ws.run(path))
        for name in COUNTS:
            assert isinstance(counts.get(name), int), "totals.%s is missing or not a whole number" % name
        assert counts["rows_read"] == count_records(path), "rows read is not the number of records"
        outcomes = counts["loaded"] + counts["updated"] + counts["skipped"] + counts["rejected"]
        assert outcomes == counts["rows_read"], "outcomes %d != rows read %d for %s" % (
            outcomes, counts["rows_read"], os.path.basename(path))


@pytest.mark.parametrize("path", SUPPLIED)
def test_same_file_on_an_empty_database_twice_gives_the_same_database(path):
    databases = []
    for _ in range(2):
        folder = tempfile.mkdtemp(prefix="ingest-test-")
        try:
            run = Workspace(folder)
            run.run(path)
            databases.append(run.books())
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    assert databases[0], "the first run stored no books"
    assert databases[0] == databases[1], "the two databases differ"
