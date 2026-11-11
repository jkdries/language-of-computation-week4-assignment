# Comparison of my books.db with Micaiah's

Mine: `books.db`. Micaiah's: `partner-2/books.db`.

**The two databases hold the same data.**

| | Mine | Micaiah's |
|---|---|---|
| Books | 9404 | 9404 |
| Books only in this database | 0 | 0 |
| Books in both with a different value | 0 | 0 |
| Differing values (book and column) | 0 | 0 |

## How the comparison was made

- **Same book**, as `rules.md` defines it: the same ISBN-13, converting an ISBN-10 to its ISBN-13 when a book has no ISBN-13. A book stored without any ISBN is matched by title and authors together, ignoring capitalization and extra spaces.
- **Columns compared:** `isbn` and `isbn13`, matched to the columns with the same names. Both databases have the same columns in their `books` table.
- **Left out:** the internal `id` row number, the other 21 source columns (this assignment is about the ISBNs), and the tables that hold copies of log entries with run times (`runs`, `run_history`). Title and authors are used only to match books without an ISBN.
- An empty ISBN is shown as null or as empty text, exactly as stored.

## Books only in mine (0)

None.

## Books only in Micaiah's (0)

None.

## Books in both with a different value (0)

None.

## Why our data differs
The comparison showed that there was no difference between my database and Micaiah's database.  In both of our cases, Claude Code chose the same treatment of the three rows with the scientific notation which were noted as a difference when compared to Ricky's database.

