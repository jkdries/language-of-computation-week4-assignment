#!/usr/bin/env python3
"""Load books CSV files into books.db, following rules.md.

Usage:
    python3 ingest.py [--db PATH] [--log PATH] FILE.csv [FILE.csv ...]

Without --db and --log, the catalog is books.db and the log is
ingestion-log.json, both beside this script. The files are processed in the
order given, as one run: if any file cannot be read completely, nothing from
any file in the run is kept. Every run adds one entry to the log.

It uses only Python's standard library, without AI or internet, so the same
files and the same starting database always give the same result.
"""

import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))

# rules.md, "Files and the report": all 23 headers of the supplied books.csv.
COLUMNS = [
    "book_id", "goodreads_book_id", "best_book_id", "work_id", "books_count",
    "isbn", "isbn13", "authors", "original_publication_year", "original_title",
    "title", "language_code", "average_rating", "ratings_count",
    "work_ratings_count", "work_text_reviews_count", "ratings_1", "ratings_2",
    "ratings_3", "ratings_4", "ratings_5", "image_url", "small_image_url",
]
ORDINARY = [name for name in COLUMNS if name not in ("isbn", "isbn13", "title", "authors")]

# rules.md: the action sentences, word for word.
ACTION_ISBN = "Find the correct ISBN, correct the row, and load the file again."
ACTION_CONFLICT = "Check which value or book is correct."
ACTION_IDENTITY = "Supply an identifying title and author, then load the file again."
ACTION_FILE = "Correct the file error and rerun the files."

# Kinds of problem, each with its action sentence.
ISBN_ERROR, CONFLICT, MISSING_IDENTITY = "isbn", "conflict", "identity"
ACTIONS = {ISBN_ERROR: ACTION_ISBN, CONFLICT: ACTION_CONFLICT, MISSING_IDENTITY: ACTION_IDENTITY}

# Repair types (rules.md, "Checking ISBNs").
FORMATTING = "formatting"
PADDING = "leading-zero padding"
MISSING = "missing equivalent calculated"
MOVE = "ISBN-13 moved from isbn to isbn13"
SCIENTIFIC = "scientific notation confirmed"

PLACEHOLDERS = {"unknown", "untitled", "untitled manuscript"}

SCIENTIFIC_RE = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)[eE][+-]?\d+")
DECIMAL_RE = re.compile(r"[+-]?(\d+\.\d*|\.\d+)")

OVERLAP_NOTE = (
    "Warning and repair counts overlap the outcomes: a row loaded, updated or "
    "skipped can also have warnings and repairs. Only loaded, updated, skipped "
    "and rejected add up to rows read."
)


class FileError(Exception):
    """A file that cannot be read completely. The whole run fails."""

    def __init__(self, message, record=None):
        super().__init__(message)
        self.record = record


# ---------------------------------------------------------------------------
# ISBN checks and conversions
# ---------------------------------------------------------------------------

def isbn10_ok(value):
    if not re.fullmatch(r"\d{9}[\dX]", value):
        return False
    total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(value))
    return total % 11 == 0


def check13(first12):
    total = sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(first12))
    return str((10 - total % 10) % 10)


def isbn13_ok(value):
    return bool(re.fullmatch(r"97[89]\d{10}", value)) and check13(value[:12]) == value[12]


def to13(isbn10):
    first12 = "978" + isbn10[:9]
    return first12 + check13(first12)


def to10(isbn13):
    """The ISBN-10 for a 978 ISBN-13; None for 979, which has no ISBN-10."""
    if not isbn13.startswith("978"):
        return None
    first9 = isbn13[3:12]
    check = (11 - sum((10 - i) * int(c) for i, c in enumerate(first9)) % 11) % 11
    return first9 + ("X" if check == 10 else str(check))


def round12(isbn13):
    """The ISBN-13 rounded to 12 significant digits, exactly, ties to even."""
    number = Decimal(isbn13)
    return number.quantize(Decimal(1).scaleb(number.adjusted() - 11), rounding=ROUND_HALF_EVEN)


def strip_spaces(value):
    return "".join(c for c in value if not c.isspace())


def clean(value):
    """Permitted cleanup: remove spaces and ordinary hyphens, lowercase x to X."""
    return strip_spaces(value).replace("-", "").replace("x", "X")


def is_blank(value):
    return value is None or value.strip() == ""


# ---------------------------------------------------------------------------
# Reading one row's two ISBN fields
# ---------------------------------------------------------------------------

class Field:
    """What one ISBN field turned out to be."""

    def __init__(self, kind, value=None, repairs=(), problem=None):
        self.kind = kind          # blank, isbn10, isbn13, scientific, other, bad
        self.value = value        # cleaned value, when there is one
        self.repairs = list(repairs)
        self.problem = problem    # reason text when kind is bad


def read_isbn(raw):
    """The isbn column."""
    if is_blank(raw):
        return Field("blank")
    compact = strip_spaces(raw)
    # Scientific and decimal notation are recognised first, before hyphens
    # (which might be exponent signs) are removed. They are not repairs here.
    if SCIENTIFIC_RE.fullmatch(compact) or DECIMAL_RE.fullmatch(compact):
        return Field("bad", problem="isbn is in scientific or decimal notation, which is invalid isbn formatting")
    if compact[0] in "+-":
        return Field("bad", problem="isbn has an illegal leading plus or minus sign")
    value = clean(raw)
    repairs = [FORMATTING] if value != raw else []
    if value == "" or not re.fullmatch(r"\d*X?", value):
        return Field("bad", problem="isbn has an illegal character")
    if 2 <= len(value) <= 9:
        value = value.zfill(10)
        repairs.append(PADDING)
    if len(value) == 10:
        if isbn10_ok(value):
            return Field("isbn10", value, repairs)
        return Field("bad", problem="isbn has a bad ISBN-10 checksum")
    if len(value) == 13 and value.isdigit() and value[:3] in ("978", "979"):
        if isbn13_ok(value):
            return Field("isbn13", value, repairs)
        return Field("bad", problem="isbn has a bad ISBN-13 checksum")
    if len(value) < 2:
        return Field("bad", problem="isbn is too short")
    return Field("bad", problem="isbn is overlong and not a valid ISBN-13")


def read_isbn13(raw):
    """The isbn13 column."""
    if is_blank(raw):
        return Field("blank")
    compact = strip_spaces(raw)
    if SCIENTIFIC_RE.fullmatch(compact):
        if compact[0] in "+-":
            return Field("bad", problem="isbn13 has an illegal leading plus or minus sign")
        return Field("scientific", compact)
    if DECIMAL_RE.fullmatch(compact):
        if compact[0] in "+-":
            return Field("bad", problem="isbn13 has an illegal leading plus or minus sign")
        return Field("other", compact)  # a decimal-looking value is another kind of code
    if compact[0] in "+-":
        return Field("bad", problem="isbn13 has an illegal leading plus or minus sign")
    value = clean(raw)
    repairs = [FORMATTING] if value != raw else []
    if value == "" or not value.isdigit():
        return Field("bad", problem="isbn13 has an illegal character")
    if len(value) == 13 and value[:3] in ("978", "979"):
        if isbn13_ok(value):
            return Field("isbn13", value, repairs)
        return Field("bad", problem="isbn13 has a bad ISBN-13 checksum")
    return Field("other", value)  # numeric, but the wrong length or prefix


class Outcome:
    """The ISBN decision for one row."""

    def __init__(self):
        self.isbn = None
        self.isbn13 = None
        self.repairs = []
        self.warnings = []
        self.problems = []        # (kind, reason)
        self.no_isbn = False      # use the title/author identity rule


def decide_isbns(raw_isbn, raw_isbn13):
    out = Outcome()
    a, b = read_isbn(raw_isbn), read_isbn13(raw_isbn13)

    if a.kind == "blank" and b.kind == "blank":
        out.problems.append((ISBN_ERROR, "isbn and isbn13 are both blank"))
        return out
    for field in (a, b):
        if field.kind == "bad":
            out.problems.append((ISBN_ERROR, field.problem))

    # A valid ISBN-13 in isbn moves to isbn13. This check comes before the
    # scientific-notation rule, and any different nonblank destination is a conflict.
    if a.kind == "isbn13":
        if b.kind != "blank" and clean(raw_isbn13) != a.value:
            out.problems.append((CONFLICT, "isbn holds ISBN-13 %s but isbn13 already holds a different value %r"
                                 % (a.value, raw_isbn13)))
        if out.problems:
            return out
        out.isbn13 = a.value
        out.repairs = a.repairs + [MOVE] + (b.repairs if b.kind == "isbn13" else [])
        out.isbn = to10(a.value)
        if out.isbn:
            out.repairs.append(MISSING)
        return out

    if out.problems:
        return out

    if a.kind == "isbn10":
        out.isbn = a.value
        out.repairs = list(a.repairs)
        derived = to13(a.value)
        if b.kind == "blank":
            out.isbn13 = derived
            out.repairs.append(MISSING)
        elif b.kind == "isbn13":
            if b.value != derived:
                out.problems.append((CONFLICT, "isbn %s and isbn13 %s identify different books" % (a.value, b.value)))
                return out
            out.isbn13 = b.value
            out.repairs += b.repairs
        elif b.kind == "scientific":
            if round12(derived) != Decimal(b.value):
                out.problems.append((CONFLICT, "isbn13 %s does not agree with %s, the ISBN-13 of isbn %s"
                                     % (b.value, derived, a.value)))
                return out
            out.isbn13 = derived
            out.repairs.append(SCIENTIFIC)
        else:  # another kind of code: discard it, and do not fill it again
            out.warnings.append("isbn13 %r is another kind of code, not an ISBN-13, so isbn13 was left blank"
                                % raw_isbn13)
        return out

    # isbn is blank from here on.
    if b.kind == "isbn13":
        out.isbn13 = b.value
        out.repairs = list(b.repairs)
        out.isbn = to10(b.value)
        if out.isbn:
            out.repairs.append(MISSING)
        return out
    out.no_isbn = True
    if b.kind == "scientific":
        out.warnings.append("isbn is blank and isbn13 %r is a rounded number, so it was not repaired; "
                            "loaded without ISBNs, identified by title and author" % raw_isbn13)
    else:
        out.warnings.append("isbn is blank and isbn13 %r is another kind of code; "
                            "loaded without ISBNs, identified by title and author" % raw_isbn13)
    return out


# ---------------------------------------------------------------------------
# Reading files
# ---------------------------------------------------------------------------

def read_file(path):
    """Return (sha256, [(record number, row dict)]). Raise FileError if it can't be read completely."""
    records = []
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as error:
        raise FileError("the file could not be opened: %s" % error.strerror, record=None)
    digest = hashlib.sha256(data).hexdigest()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise FileError("the file is not readable UTF-8 (byte %d)" % error.start, record=None)

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    number = 0
    header = None
    try:
        for fields in reader:
            if not fields:
                continue  # a completely empty line
            number += 1
            if header is None:
                header = fields
                check_header(header)
                continue
            if len(fields) != len(header):
                raise FileError("record %d has %d fields, expected %d" % (number, len(fields), len(header)),
                                record=number)
            records.append((number, dict(zip(header, fields))))
    except csv.Error as error:
        failure = FileError("broken CSV after record %d: %s" % (number, error), record=number + 1)
        failure.records = records
        raise failure
    except FileError as error:
        error.records = records
        raise
    if header is None:
        raise FileError("the file has no header", record=None)
    return digest, records


def check_header(header):
    duplicates = sorted({name for name in header if header.count(name) > 1})
    missing = [name for name in COLUMNS if name not in header]
    unexpected = [name for name in header if name not in COLUMNS]
    problems = []
    if missing:
        problems.append("missing headers: " + ", ".join(missing))
    if unexpected:
        problems.append("unexpected headers: " + ", ".join(unexpected))
    if duplicates:
        problems.append("duplicate headers: " + ", ".join(duplicates))
    if problems:
        raise FileError("; ".join(problems), record=1)


# ---------------------------------------------------------------------------
# The catalog
# ---------------------------------------------------------------------------

def norm(text):
    """Comparison form: ignore capitalization, trim the ends, collapse whitespace."""
    return " ".join((text or "").split()).casefold()


def isbn_key(isbn, isbn13):
    """One key per edition, converting ISBN-10 to ISBN-13 so equivalent forms match."""
    if isbn13:
        return isbn13
    if isbn:
        return to13(isbn)
    return None


class Catalog:
    def __init__(self, connection):
        self.db = connection
        self.books = {}
        self.by_key, self.by_name, self.by_supplier = {}, {}, {}
        names = ", ".join('"%s"' % c for c in COLUMNS)
        for row in connection.execute("SELECT id, %s FROM books ORDER BY id" % names):
            self._index(row[0], dict(zip(COLUMNS, row[1:])))

    def _index(self, book_id, book):
        self.books[book_id] = book
        key = isbn_key(book["isbn"], book["isbn13"])
        if key:
            self.by_key[key] = book_id
        self.by_name.setdefault((norm(book["title"]), norm(book["authors"])), set()).add(book_id)
        self.by_supplier.setdefault(book["book_id"], set()).add(book_id)

    def _unindex(self, book_id):
        book = self.books.pop(book_id)
        key = isbn_key(book["isbn"], book["isbn13"])
        if key and self.by_key.get(key) == book_id:
            del self.by_key[key]
        self.by_name[(norm(book["title"]), norm(book["authors"]))].discard(book_id)
        self.by_supplier[book["book_id"]].discard(book_id)

    def count(self):
        return len(self.books)

    def insert(self, book):
        names = ", ".join('"%s"' % c for c in COLUMNS)
        marks = ", ".join("?" for _ in COLUMNS)
        cursor = self.db.execute("INSERT INTO books (%s) VALUES (%s)" % (names, marks),
                                 [book[c] for c in COLUMNS])
        self._index(cursor.lastrowid, dict(book))
        return cursor.lastrowid

    def update(self, book_id, changes):
        book = dict(self.books[book_id])
        book.update(changes)
        sets = ", ".join('"%s" = ?' % c for c in changes)
        self.db.execute("UPDATE books SET %s WHERE id = ?" % sets, list(changes.values()) + [book_id])
        self._unindex(book_id)
        self._index(book_id, book)

    def others_with_supplier_id(self, supplier_id, book_id=None):
        if is_blank(supplier_id):
            return set()
        return self.by_supplier.get(supplier_id, set()) - {book_id}


# ---------------------------------------------------------------------------
# One row
# ---------------------------------------------------------------------------

class Run:
    def __init__(self):
        self.files = []
        self.rejected, self.skipped, self.warnings, self.updates = [], [], [], []
        self.file_errors = []
        self.repairs_by_type = {}
        self.rejection_reasons = {}
        self.rows_repaired = 0


def row_info(name, number, raw, out=None):
    info = {
        "file": name,
        "record": number,
        "title": raw.get("title", ""),
        "book_id": raw.get("book_id", ""),
        "original_isbn": raw.get("isbn", ""),
        "original_isbn13": raw.get("isbn13", ""),
    }
    if out is not None:
        info["interpreted_isbn"] = out.isbn
        info["interpreted_isbn13"] = out.isbn13
    return info


def process_row(catalog, run, counts, name, number, raw):
    """Decide one row. Return loaded, updated, skipped or rejected."""
    out = decide_isbns(raw.get("isbn", ""), raw.get("isbn13", ""))
    problems = list(out.problems)
    warnings = list(out.warnings)
    match, changes = None, {}

    if not problems and out.no_isbn:
        title, authors = norm(raw.get("title")), norm(raw.get("authors"))
        if not title or not authors or title in PLACEHOLDERS or authors in PLACEHOLDERS:
            problems.append((MISSING_IDENTITY, "a row without ISBNs needs a real title and author"))
        else:
            matches = catalog.by_name.get((title, authors), set())
            if len(matches) > 1:
                problems.append((CONFLICT, "title and author match %d catalog entries, so the book is ambiguous"
                                 % len(matches)))
            elif matches:
                match = next(iter(matches))

    if not problems and not out.no_isbn:
        key = isbn_key(out.isbn, out.isbn13)
        match = catalog.by_key.get(key)
        if match is None:
            # A row with an ISBN can match an entry without one by title and author.
            names = catalog.by_name.get((norm(raw.get("title")), norm(raw.get("authors"))), set())
            without = [i for i in names if isbn_key(catalog.books[i]["isbn"], catalog.books[i]["isbn13"]) is None]
            if len(without) > 1:
                problems.append((CONFLICT, "title and author match %d catalog entries without ISBNs, "
                                 "so the book is ambiguous" % len(without)))
            elif without:
                match = without[0]

    if not problems and match is not None:
        stored = catalog.books[match]
        if not out.no_isbn:
            title_differs = not is_blank(raw.get("title")) and norm(raw.get("title")) != norm(stored["title"])
            author_differs = not is_blank(raw.get("authors")) and norm(raw.get("authors")) != norm(stored["authors"])
            if title_differs and author_differs:
                problems.append((CONFLICT, "the ISBN belongs to catalog entry %d, %r by %r, but both title "
                                 "and author differ" % (match, stored["title"], stored["authors"])))
            elif title_differs or author_differs:
                field = "title" if title_differs else "authors"
                warnings.append("%s differs from catalog entry %d (%r); updated to the incoming value"
                                % (field, match, stored[field]))
                changes[field] = raw[field]
        if not problems:
            for field in ORDINARY:
                incoming = raw.get(field, "")
                if not is_blank(incoming) and incoming != stored[field]:
                    changes[field] = incoming
            for field in ("isbn", "isbn13"):
                incoming = getattr(out, field)
                if incoming and not stored[field]:
                    changes[field] = incoming

    if problems:
        info = row_info(name, number, raw, out)
        info["reasons"] = [reason for _, reason in problems]
        info["actions"] = sorted({ACTIONS[kind] for kind, _ in problems})
        run.rejected.append(info)
        for _, reason in problems:
            run.rejection_reasons[reason] = run.rejection_reasons.get(reason, 0) + 1
        counts["rejected"] += 1
        return

    if match is None:
        book = {c: raw.get(c, "") for c in COLUMNS}
        book["isbn"], book["isbn13"] = out.isbn, out.isbn13
        if catalog.others_with_supplier_id(book["book_id"]):
            warnings.append("book_id %s already appears on a different catalog entry" % book["book_id"])
        catalog.insert(book)
        counts["loaded"] += 1
    elif changes:
        stored = catalog.books[match]
        if "book_id" in changes and catalog.others_with_supplier_id(changes["book_id"], match):
            warnings.append("book_id %s already appears on a different catalog entry" % changes["book_id"])
        update = row_info(name, number, raw, out)
        update["catalog_entry"] = match
        update["changes"] = [{"field": f, "old": stored[f], "new": v} for f, v in changes.items()]
        run.updates.append(update)
        catalog.update(match, changes)
        counts["updated"] += 1
    else:
        info = row_info(name, number, raw, out)
        info["reason"] = "identical to catalog entry %d, nothing changed" % match
        run.skipped.append(info)
        counts["skipped"] += 1

    for message in warnings:
        warning = row_info(name, number, raw, out)
        warning["warning"] = message
        run.warnings.append(warning)
    counts["warnings"] += len(warnings)
    for repair in out.repairs:
        run.repairs_by_type[repair] = run.repairs_by_type.get(repair, 0) + 1
    counts["repairs"] += len(out.repairs)
    if out.repairs:
        run.rows_repaired += 1


# ---------------------------------------------------------------------------
# The log
# ---------------------------------------------------------------------------

def read_log(path):
    """The existing log entries. Stop, changing nothing, if the log can't be read."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            entries = json.load(f)
    except (OSError, ValueError) as error:
        sys.exit("Stopped: %s cannot be read (%s). Nothing was changed." % (path, error))
    if not isinstance(entries, list):
        sys.exit("Stopped: %s is not a list of runs. Nothing was changed." % path)
    return entries


def write_log(path, entries):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


def open_database(path):
    connection = sqlite3.connect(path, isolation_level=None)
    columns = ", ".join('"%s" TEXT' % c for c in COLUMNS)
    connection.execute("CREATE TABLE IF NOT EXISTS books (id INTEGER PRIMARY KEY AUTOINCREMENT, %s)" % columns)
    # The recovery copy of every log entry, in case writing the JSON log is interrupted.
    connection.execute("CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT, entry TEXT NOT NULL)")
    return connection


def recover_log(connection, entries):
    """Add any run kept in SQLite that is missing from the JSON log. Return True if any was added."""
    stored = [json.loads(row[0]) for row in connection.execute("SELECT entry FROM runs ORDER BY id")]
    if len(stored) > len(entries):
        entries.extend(stored[len(entries):])
        return True
    return False


class Lock:
    """Only one import at a time for the same database."""

    def __init__(self, db_path):
        self.path = db_path + ".lock"
        self.handle = None

    def __enter__(self):
        self.handle = open(self.path, "w")
        try:
            import fcntl
            try:
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.handle.close()
                sys.exit("Stopped: another import is running on %s. Nothing was changed." % self.path[:-5])
        except ImportError:
            pass  # no file locking on this system
        return self

    def __exit__(self, *exc):
        self.handle.close()
        try:
            os.remove(self.path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# A run
# ---------------------------------------------------------------------------

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty_counts():
    return {"rows_read": 0, "loaded": 0, "updated": 0, "skipped": 0, "rejected": 0, "warnings": 0, "repairs": 0}


def ingest(paths, db_path, log_path):
    with Lock(db_path):
        entries = read_log(log_path)
        connection = open_database(db_path)
        try:
            if recover_log(connection, entries):
                write_log(log_path, entries)
            entry = run_files(connection, paths)
            connection.execute("INSERT INTO runs (entry) VALUES (?)", [json.dumps(entry, ensure_ascii=False)])
        finally:
            connection.close()
        entries.append(entry)
        write_log(log_path, entries)
    return entry


def run_files(connection, paths):
    started = now()
    run = Run()
    catalog = Catalog(connection)
    before = catalog.count()

    # Read every file completely before changing anything.
    parsed, failure = [], None
    for path in paths:
        name = os.path.basename(path)
        try:
            digest, records = read_file(path)
            parsed.append((path, name, digest, records))
        except FileError as error:
            records = getattr(error, "records", [])
            failure = {"file": name, "path": path, "error": str(error), "records": records,
                       "stopped_at_record": error.record}
            break

    totals = empty_counts()
    if failure is None:
        connection.execute("BEGIN IMMEDIATE")
        try:
            for path, name, digest, records in parsed:
                counts = empty_counts()
                counts["rows_read"] = len(records)
                for number, raw in records:
                    process_row(catalog, run, counts, name, number, raw)
                run.files.append(dict({"file": name, "path": path, "sha256": digest}, **counts))
                for key in totals:
                    totals[key] += counts[key]
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        status = "completed"
        verdict = "Some rows need attention" if totals["rejected"] else "Completed"
        after = catalog.count()
    else:
        # The run failed: nothing is kept. Fully parsed rows count as rejected.
        for path, name, digest, records in parsed:
            counts = empty_counts()
            counts["rows_read"] = counts["rejected"] = len(records)
            run.files.append(dict({"file": name, "path": path, "sha256": digest}, **counts))
        counts = empty_counts()
        counts["rows_read"] = counts["rejected"] = len(failure["records"])
        run.files.append(dict({"file": failure["file"], "path": failure["path"], "sha256": None,
                               "file_error": failure["error"]}, **counts))
        for listed in run.files:
            for key in totals:
                totals[key] += listed[key]
        unread = [os.path.basename(p) for p in paths[len(run.files):]]
        run.file_errors.append({
            "file": failure["file"],
            "error": failure["error"],
            "reading_stopped_at_record": failure["stopped_at_record"],
            "unread_files": unread,
            "note": "Records after this point, and any unread files, were not checked. "
                    "Every change from this run was rolled back.",
            "action": ACTION_FILE,
        })
        status, verdict, after = "failed", "Failed", before

    outcomes = totals["loaded"] + totals["updated"] + totals["skipped"] + totals["rejected"]
    totals["rows_repaired"] = run.rows_repaired
    entry = {
        "started_at": started,
        "finished_at": now(),
        "files": run.files,
        "status": status,
        "verdict": verdict,
        "catalog_before": before,
        "catalog_after": after,
        "totals": totals,
        "totals_match": outcomes == totals["rows_read"],
        "totals_note": ("Loaded, updated, skipped and rejected add up to rows read."
                        if outcomes == totals["rows_read"] else
                        "The totals do not match: loaded, updated, skipped and rejected add up to %d, "
                        "but %d rows were read." % (outcomes, totals["rows_read"])),
        "overlap_note": OVERLAP_NOTE,
        "repairs_by_type": dict(sorted(run.repairs_by_type.items())),
        "rejection_reasons": dict(sorted(run.rejection_reasons.items())),
        "file_errors": run.file_errors,
        "rejected_rows": run.rejected,
        "skipped_rows": run.skipped,
        "warnings": run.warnings,
        "updates": run.updates,
    }
    return entry


def print_summary(entry):
    print("Verdict:  %s" % entry["verdict"])
    for listed in entry["files"]:
        print("File:     %s" % listed["file"])
        if listed.get("file_error"):
            print("  Error:  %s" % listed["file_error"])
        print("  Read %d, loaded %d, updated %d, skipped %d, rejected %d" % (
            listed["rows_read"], listed["loaded"], listed["updated"], listed["skipped"], listed["rejected"]))
    t = entry["totals"]
    print("Overall:  read %d, loaded %d, updated %d, skipped %d, rejected %d" % (
        t["rows_read"], t["loaded"], t["updated"], t["skipped"], t["rejected"]))
    print("          warnings %d, repairs %d (in %d rows)" % (t["warnings"], t["repairs"], t["rows_repaired"]))
    print("Catalog:  %d books before, %d after" % (entry["catalog_before"], entry["catalog_after"]))
    print(entry["totals_note"])
    for error in entry["file_errors"]:
        print("%s: %s" % (error["file"], error["action"]))


def parse_arguments(argv):
    db_path = os.path.join(HERE, "books.db")
    log_path = os.path.join(HERE, "ingestion-log.json")
    paths = []
    i = 0
    while i < len(argv):
        if argv[i] in ("--db", "--log"):
            if i + 1 >= len(argv):
                sys.exit("Usage: python3 ingest.py [--db PATH] [--log PATH] FILE.csv [FILE.csv ...]")
            if argv[i] == "--db":
                db_path = argv[i + 1]
            else:
                log_path = argv[i + 1]
            i += 2
        else:
            paths.append(argv[i])
            i += 1
    if not paths:
        sys.exit("Usage: python3 ingest.py [--db PATH] [--log PATH] FILE.csv [FILE.csv ...]")
    return paths, db_path, log_path


def main(argv):
    paths, db_path, log_path = parse_arguments(argv)
    entry = ingest(paths, db_path, log_path)
    print_summary(entry)
    return 1 if entry["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
