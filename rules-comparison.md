# Revised rules comparison and sanity check

This compares the new decisions with M (my saved rules), A (the first student's paste), and B (the second student's paste). A's later clarifications take priority over its earlier tables. The new decisions take priority over all three. For other decisions, use agreement between two sets, then the most specific answer. Silence is not a vote.

This is a review of the proposed rules. The saved rules.md and ingest.py still describe the earlier behavior. Neither the database nor the source CSVs has been changed for this review.

## Decisions already settled

| Decision | Revised decision | Compared with the originals |
|---|---|---|
| 9790 exception | Remove the special exclusion. Check the stated 978/979 prefix rule without that extra exception. | Removes M's extra check; A and B do not specify the exception. This broadens what the program accepts; it is a project rule, not proof of ISBN allocation. |
| Already valid | Load and calculate a missing equivalent when possible. | A and B. |
| Spaces, hyphens, lowercase x | Clean, validate, count repairs. Reject if validation still fails after applicable permitted repairs. | A and B; stricter than M. |
| Wrong checksum at correct length | Reject the whole row, in either column. Do not change its check digit. | A and B. |
| Illegal characters after cleanup | Reject the whole row. | A and B. |
| Overlong isbn, not valid ISBN-13 | Reject. Do not remove digits. | A and B. |
| Wrong-length numeric isbn13 or other product code | With good isbn, leave isbn13 blank and warn. With blank isbn, allow empty ISBNs only when title/author identify the book. | B; M uses supplier ID, A rejects the no-ISBN case. |
| Scientific notation with valid isbn | Derive ISBN-13 from isbn and require agreement with the supplied number when the derived ISBN-13 is rounded to 12 significant digits. Store the complete derived identifier, never the rounded value. Reject disagreement. | B's more specific version of A's rule. |
| Decimal-looking value | No .0 cleanup is authorized. In isbn13 it follows the other-code fallback. | Replaces M's decimal repair; follows B's lack of a decimal-repair rule. This does not grant permission to strip decimal digits in isbn. |
| One blank, other valid | Calculate the missing equivalent. | A and B. |
| Valid 979 ISBN-13 | Leave isbn blank; there is no ISBN-10 equivalent. | All three agree. The blank here is not a failed repair. |
| Valid ISBN-13 in isbn | Move to isbn13 and calculate ISBN-10 when possible. Reject a conflicting existing isbn13 value. | A and B, with B's explicit conflict rule. Confirmed in the follow-up clarification. |
| Both original ISBN fields blank | Reject, including a known book. | A; explicitly overrides M and B. |
| Two usable ISBNs disagree | Reject. | All three agree. |
| Repair uncertainty | Checking a candidate is evidence; inventing a digit to make it pass is not independent evidence. Do not perform uncertain repairs outside the listed permissions. | B's distinction, selected explicitly. A passing checksum still does not prove title ownership. |

## Decisions selected by two-out-of-three agreement

These choices apply only where the explicit decisions above do not override them.

| Decision | Result | Basis |
|---|---|---|
| Final X in ISBN-10 | Allow it when the checksum passes. | All three. |
| Leading zeros | Pad a short plain ISBN-10 with zeros and test it; reject if it fails. | All allow padding; A and B reject failure. M's 2–9-character limit is the most specific boundary. |
| Missing equivalent ISBN | Calculate it, except ISBN-10 from 979. | A and B, also explicitly selected. |
| Exact repeat | Skip without creating a second book, including repeats within a file. | All three. |
| Publication year | Treat it as an updatable detail rather than part of identity. | M and B do not include it in identity; A does. |
| Changes to ordinary fields | Update only nonblank new values; a blank does not erase an existing value. | M and B. Validation can still reject the incoming row before this applies. |
| Title/author comparison | Ignore capitalization and extra whitespace. | M and B. |
| Same ISBN, clearly different title and author | Reject, leave existing book unchanged, report the conflict. | All three. |
| File order | Process in supplied order; later accepted records provide newer nonblank details. | M and B are compatible. B explicitly calls latest loaded data the newest. |
| Stored columns | Keep all 23 source columns, with resulting ISBN values. | A and B. |
| Failed file/run | Roll back changes from the whole run and report the failure. | M and B. |
| Damaged CSV row | Too many/few fields makes the file unreadable; report the record and fail the run. | M and B. |
| Outcome totals | Read = inserted + updated + unchanged/skipped + rejected. Repairs and warnings overlap these outcomes. | M and B explicitly require reconciliation; all require outcome counts. |
| Update detail | Report old and new values and source location. | M and B. |
| No network or AI | Run offline without AI. | M and A explicitly say so. |

## Most-specific choices where there is no majority

These are selected answers, not claims that the other documents agreed. Where two equally explicit rules contradict each other, the unresolved section below takes precedence.

| Decision | Selected answer | Basis |
|---|---|---|
| Main identity | Match ISBN-13 first, then ISBN-10 if ISBN-13 is absent. Compare repaired values. | B specifies matching order; the other sets use different full identities. |
| No-ISBN identity | Use normalized title and authors. Reject multiple matches. A row with an ISBN and a row without one can match by title/author. | B gives explicit matching and ambiguity rules. This applies only to an allowed other-code/rounded fallback, not to originally blank/blank rows. |
| Placeholder identity | For a no-ISBN row, reject blank title/author or whole-field Unknown, Untitled, or Untitled Manuscript, ignoring case. | Only B defines this test. |
| One title/author field differs for the same ISBN | Treat as same book with warning; both differing means reject. | B gives the most detailed split between the two cases. |
| Significant text distinctions | Do not remove punctuation or accents, or reorder authors, for matching. | M explicitly describes those boundaries. |
| Wrong-column ISBN-10 | A numeric ISBN-10 placed in isbn13 is another code, not an automatically rescued ISBN-10. | B explicitly classifies wrong-length numeric isbn13; A is silent. |
| Scientific notation with blank isbn | Do not use the expanded value as a confirmed ISBN. Allow a no-ISBN title/author fallback with warning. | B spells out this fallback and identity requirements. |
| Stored ordinary source values | Preserve non-ISBN source fields as supplied rather than trimming their stored display values. Normalize only for comparisons. | B explicitly says all source columns except ISBN fields stay as supplied. Later updates still obey the nonblank rule. |
| Multiple problems | Record every problem; illegal characters take priority over too-short for the same value. | B explicitly sets this priority. |
| Read encoding and headers | UTF-8 with optional BOM; ignore completely empty lines; duplicate headers and unreadable files fail the run. | M is the only detailed specification. Required-header scope remains open below. |
| Revalidation | Check every row every run, including repeats. | M explicitly requires this. |
| Log preservation | Keep earlier runs; stop on unreadable JSON; retain recovery history in SQLite; do not run simultaneous imports. | M explicitly defines these safeguards. |
| Run metadata | Time, ordered file names, hashes, completion/failure, and book counts before and after. | M is most detailed. |
| Rejection report | Include location, identity, raw/interpreted values, reason, action and next step. Also count rejections by reason. | M supplies field detail; A explicitly adds reason totals. |
| Skipped rows | List them separately from rejected rows. | B explicitly requires separate headings. |
| Repair reporting | Count repairs by type; show warnings and updates in both JSON and HTML. | B specifies repair categories and report parity. Individual repair-history retention remains open below. |
| Verdict | Completed, some rows need attention, or failed. Only rejected rows trigger attention; warnings remain visible without changing that verdict. | B defines the exact distinction. |
| Next action text | Fixed sentence per reason; conflicts tell the reader to check which value/book is correct. | B is most specific. |
| Report interface | Self-contained HTML with JSON file-open button and expandable details. Keep database/log beside the script. | M explicitly defines local operation. |

## Sanity check: precedence that must be clear

1. Blank/blank rejection refers to the incoming fields. A nonblank other code can be discarded and leave two empty stored ISBN fields while the row loads with a warning. That is different from accepting an originally blank/blank row.
2. Scientific notation must take its special confirmation path before a checksum is applied to an expanded number. Otherwise a rounded number would be rejected before the authorized confirmation repair could occur.
3. A numeric wrong-length isbn13 uses the other-code rule, not the overlong-isbn rule. The latter applies to the isbn column.
4. Decimal notation in isbn13 follows the explicitly selected other-code rule. That special classification must happen before a generic illegal-character test for the decimal point. It does not authorize decimal cleanup.
5. A correct-length, book-prefix ISBN with a bad checksum is a rejection, not a harmless other product code. A good partner field does not rescue it.
6. Cleanup can be followed by the permitted leading-zero repair before declaring failure. Otherwise a spaced short ISBN would be rejected even though both individual repairs were allowed.
7. A moved valid ISBN-13 must be checked against a nonblank destination before overwriting it. A literal difference from the cleaned destination triggers the selected move-conflict rule. Rounded destination values need the clarification below.
8. Checksum success does not establish that a number is assigned or belongs to the listed title. Removing the 9790 exception changes the project's validation policy, not that limitation.
9. Validation happens before repeat handling. A known book arriving with both fields blank is rejected under the new rule, not silently skipped using its old ISBN.
10. The existing script does not yet implement these decisions. In particular it still loads several invalid-ISBN rows through supplier IDs, repairs .0 values, and treats scientific notation differently. Existing run results should not be described as tests of the revised rules.

## Decisions the selection method does not fully settle

These are not a judgement of the rules. They are places where equally explicit choices conflict, or the supplied documents omit a detail. They should be answered before implementation rather than silently invented.

| Open decision | Why it is still open |
|---|---|
| Same supplier ID but a different book | M explicitly rejects a changed ISBN or conflicting identity. A explicitly allows a separate book sharing that ID. B does not make supplier ID an identity key. There is no two-vote result, and both opposing answers are specific. |
| Supplier ID required on every row | M explicitly requires a positive digits-only ID. A explicitly allows shared IDs but does not define missing/invalid IDs; B identifies no-ISBN books by title/author. Retaining M's requirement would add a rejection to B's fallback. Decide whether to keep the requirement. |
| Header requirements | M requires only five named headers and allows extras. A/B require storing all 23 columns, but do not explicitly say whether a missing non-ISBN column fails the file. Storing 23 fields does not by itself define missing-header policy. |
| Original values and individual repair history | M explicitly retains full originals and individual repairs. A explicitly excludes original ISBNs from the database and says not to list each repair. B requires repair totals but does not settle raw-history retention. Decide whether detailed history stays, separate from summarized report counts. |
| 12-significant-digit ties | B specifies precision but not the rounding method when the next digit is exactly 5. Define ties-to-even or another method before code is written. Also define whether a supplied notation with a different precision is compared numerically to the 12-digit rounded result or at its own written precision. |
| Moving ISBN-13 against a rounded destination | B explicitly says different destination values cause rejection, while its scientific-notation rule can confirm a rounded equivalent. Decide whether confirmation can establish agreement for this move case, or the literal destination-difference rule always wins. |
| Scientific notation or decimals in isbn | The special rounded-data discussion primarily concerns isbn13. Your decimal change specifically chooses that column's other-code fallback. No equally precise path is given for numeric notation in isbn. Do not assume it receives the same fallback. |
| Updating only one changed title/author | B says same book with warning, and its update rule suggests replacing that nonblank field. Explicitly retaining versus replacing the stored display value should be confirmed if that warning was meant for review rather than automatic correction. |

## Revised example outcomes

These cases assume new rows with a nonblank real title and author and a valid supplier ID, no existing match, and no placeholder fields. A/B refer to the two original students; M is the old saved rules. “Load” still involves any required repair/warning counts. These are tests of the proposed decisions, not results from running the old script.

| isbn | isbn13 | Old M | Original A | Original B | Revised outcome |
|---|---|---|---|---|---|
| 0439139600 | 9780439139601 | Load. | Load. | Load. | Load, no repair. |
| 043965548X | blank | Load, warn. | Fill equivalent, load. | Fill equivalent, load. | Calculate ISBN-13 and load. |
| 031200009x | 9780312000097 | Clean and warn. | Clean and load. | Clean and load. | Uppercase X, load, count repair. |
| 0-450-19827-8 | 9780450198274 | Clean and warn. | Clean and load. | Clean and load. | Remove hyphens, load, count repair. |
| ` 162 001 4750 ` | 9781620014752 | Clean and warn. | Clean and load. | Clean and load. | Remove spaces, load, count repair. |
| 439023483 | blank | Pad and warn. | Pad, fill equivalent. | Pad, fill equivalent. | Pad to 0439023483, calculate ISBN-13, load. |
| 439554934 | 9.78043955493e+12 | Expand independently. | Confirm from ISBN-10. | Confirm at 12 digits. | Pad, derive 9780439554930, confirm rounded agreement, load. |
| 439023483 | 9.78043902348e+12 | Ignore failed expansion; use padded ISBN-10. | Derive full ISBN-13. | Derive full ISBN-13. | Derive 9780439023481 and confirm rounded agreement; load full value. |
| blank | 9.78043902348e+12 | Load without ISBN via supplier ID. | Reject. | Load without ISBN via title/author. | Load without ISBN and warn, using title/author. |
| blank | 76783609419.0 | Strip .0, then discard invalid value. | Reject. | Other-code fallback. | No decimal cleanup; load without ISBN and warn. |
| blank | 9780439139601.0 | Strip .0, use ISBN. | Decimal wording not fully consistent. | No explicit decimal cleanup. | Other-code fallback: load without ISBN and warn. |
| 04390A3483 | blank | Load without ISBN. | Reject. | Reject. | Reject illegal characters. |
| 15287463097 | blank | Load without ISBN. | Reject. | Reject. | Reject overlong isbn. |
| 1854433017 | blank | Load without ISBN. | Reject. | Reject. | Reject checksum failure. |
| blank | blank | Load without ISBN. | Reject. | Load if identifiable. | Reject, even for a known book. |
| 1555550126 | 9781555550134 | Reject. | Reject. | Reject. | Reject conflicting ISBNs. |
| 9781982147600 | blank | Load with column warning. | Move and calculate equivalent. | Move and calculate equivalent. | Move to isbn13, calculate ISBN-10, load and count repair. |
| blank | 9798351220413 | Load, blank warning. | Load without ISBN-10. | Load without ISBN-10. | Load; leave isbn blank because there is no equivalent. |
| 0439139600 | 9780061120085 | Use good field, warn about bad one. | Reject. | Reject. | Reject bad checksum in isbn13. |
| 0439139600 | 12345 | Use good field, warn. | Warn, leave isbn13 blank. | Warn, leave isbn13 blank. | Load with warning, leave isbn13 blank. Do not treat the discarded code as an originally blank field and fill it afterward. |

The old comparison also covered A's 12 standalone examples. Their revised outcomes are summarized here using the same stated scenario: value in isbn, other field blank, required identity present, and example 12 repeats example 11 unchanged. Without specifying the column, invalid-prefix outcomes can differ.

| A example | Value | Revised outcome |
|---:|---|---|
| 1 | 9770684830421 | Reject: not a valid ISBN-13 in isbn. |
| 2 | 9780747532699 | Move, calculate ISBN-10, load. |
| 3 | 978-04-51-52493-5 | Clean, move, calculate ISBN-10, load; count repairs. |
| 4 | 9780061120085 | Reject checksum failure. |
| 5 | 9780141439518 | Move, calculate ISBN-10, load. |
| 6 | 014062022X | Reject checksum failure. |
| 7 | 9781408855652 | Move, calculate ISBN-10, load. |
| 8 | 9780439023481 | Move, calculate ISBN-10, load. |
| 9 | 9783161484100 | Move, calculate ISBN-10, load. |
| 10 | 9780521825146 | Move, calculate ISBN-10, load. |
| 11 | 9780743273565 | Move, calculate ISBN-10, load. |
| 12 | 9780743273565 again | Skip unchanged after validation. |

B supplied no separate examples table. The comparison does not invent one. The prior full comparison remains in Git history; this file is the revised decision review. No repository push or ingestion run was performed for this update.
