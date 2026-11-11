# Comparison of my books.db with Ricky's

Mine: `books.db`. Ricky's: `partner-1/books.db`.

**The two databases do not hold the same data.**

| | Mine | Ricky's |
|---|---|---|
| Books | 9404 | 9407 |
| Books only in this database | 0 | 3 |
| Books in both with a different value | 0 | 0 |
| Differing values (book and column) | 0 | 0 |

## How the comparison was made

- **Same book**, as `rules.md` defines it: the same ISBN-13, converting an ISBN-10 to its ISBN-13 when a book has no ISBN-13. A book stored without any ISBN is matched by title and authors together, ignoring capitalization and extra spaces.
- **Columns compared:** `isbn` and `isbn13`, matched to the columns with the same names. Both databases have the same columns in their `books` table.
- **Left out:** the internal `id` row number, the other 21 source columns (this assignment is about the ISBNs), and the tables that hold copies of log entries with run times (`runs`, `run_history`). Title and authors are used only to match books without an ISBN.
- An empty ISBN is shown as null or as empty text, exactly as stored.

## Books only in mine (0)

None.

## Books only in Ricky's (3)

| Book | Matched by | Supplier ID | isbn | isbn13 |
|---|---|---|---|---|
| Anatomy for the Artist by Sarah Simblet | ISBN-13 9780789480453 | 5268 | `078948045X` | null |
| Sailor Moon, #1 (Sailor Moon, #1) by Naoko Takeuchi | ISBN-13 9781892213013 | 2894 | `189221301X` | null |
| The Practice of the Presence of God by Brother Lawrence | ISBN-13 9780883681053 | 3689 | `0883681056` | null |

## Books in both with a different value (0)
None.

## Why our data differs
The three rows which differed in this comparison were all impacted due to their scientific notation formatting.  Claude indicates that there was some ambiguity in the rules that we agreed upon on the treatment of ISBN numbers formatted as scientific notation.  The two rules at conflict here are the scientific notation rule and the another kind of code rule.  Ricky's Claude session chose one treatment option (loading the rows with a warning) while Micaiah's and my Claude session chose the other treatment (reject the rows). Our examples table in the rules.md also did not have something which matched this situation.

After learning of the difference between the approaches followed by Claude, Ricky chose to update his approach for these scientific notation rows to match the process that Micaiah and I followed.  I have kept Ricky's original books.db file so as to show the differences which occur during the comparison. 

