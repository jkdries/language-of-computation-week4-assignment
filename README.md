# Module 4 Assignment – MSAI-5523

This is my Module 4 assignment for MSAI-5523.

Partners: Ricky Wooten and Micaiah Mackenzie

## Running the tests and the ingestion

Run every command below in Terminal on a Mac, from this folder. Start by going there:

```bash
cd ~/workspace/language-of-computation/week4-assignment
```

### 1. Install what the tests need (once)

The tests use Python 3 and pytest 8.4.2. This creates a private Python environment in a folder named `.venv` and installs pytest into it, without changing the rest of the computer:

```bash
python3 -m venv .venv
```

```bash
.venv/bin/python -m pip install --timeout 300 --retries 10 pytest==8.4.2
```

Check that it worked. This should print `pytest 8.4.2`:

```bash
.venv/bin/python -m pytest --version
```

### 2. Run the tests

This runs every test in `test_ingest.py`, prints one line per test, and saves a copy of the output. Use `test-results-before.txt` for the first run, before `ingest.py` is changed:

```bash
.venv/bin/python -m pytest -v 2>&1 | tee test-results-before.txt
```

and `test-results.txt` for the final run, after it is changed:

```bash
.venv/bin/python -m pytest -v 2>&1 | tee test-results.txt
```

The tests never touch `books.db` or `ingestion-log.json` in this folder. Each test works in its own temporary folder with its own `test.db` and temporary log, and deletes that folder when it finishes, whether it passed or failed.

### 3. Run the ingestion

`ingest.py` needs only Python 3, not pytest. Start from an empty database and log by deleting the old ones if they exist (this does nothing if they don't):

```bash
rm -f books.db ingestion-log.json
```

Then run these three commands one at a time, in this order:

```bash
python3 ingest.py books.csv
```

```bash
python3 ingest.py books.csv
```

```bash
python3 ingest.py books-batch2.csv
```

Each run updates `books.db` and adds one entry to `ingestion-log.json`, both in this folder. To read the log, open `report.html` in a browser and select `ingestion-log.json`.

## How the tests run ingest.py

`rules.md` does not say how a test tells `ingest.py` to use `test.db` and a temporary log, or which names to read the results from. None of these choices changes how any book is handled. They are only how the tests connect to `ingest.py`:

- The tests run `python ingest.py --db <temp>/test.db --log <temp>/ingestion-log.json FILE.csv ...`. Without `--db` and `--log`, `ingest.py` uses `books.db` and `ingestion-log.json` beside itself, as `rules.md` says.
- The catalog is the table named `books`, with one column per source header, named exactly as in the header.
- `ingestion-log.json` is a JSON list with one entry per run, oldest first. Each entry has a `totals` object with these whole numbers for the whole run: `rows_read`, `loaded`, `updated`, `skipped`, `rejected`, `warnings` (number of warnings) and `repairs` (number of repairs of all types).
- The action sentence for each rejected row appears in that run's entry.
- "The same database" means the same rows in the `books` table. The run records `ingest.py` keeps in SQLite contain times, so they are not compared.
