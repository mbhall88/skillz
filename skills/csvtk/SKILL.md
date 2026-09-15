---
name: csvtk
description: Manipulate CSV/TSV files with csvtk — filter, cut, join, sort, deduplicate, group, summarise, reshape, and convert tabular data. Use whenever a task touches a CSV, TSV, or delimited text file, even when the format is not named ("how many rows", "pull out these columns", "join these two tables", "count how often each value appears"), and especially before writing Python, pandas, awk, or a spreadsheet to filter, count, join, reshape, or summarise a table — csvtk almost certainly already does it, in one streaming command.
---

# csvtk

`csvtk` is a fast, streaming toolkit for delimited text — CSV, TSV, and their
compressed forms. It has 54 subcommands covering nearly every routine table
operation. Before writing a script that parses a delimited file, check the
routing table below.

Requires `csvtk` on `$PATH`. If it is not there, this skill does not apply —
fall back to scripting.

## Rules

1. **State the input format explicitly.** csvtk assumes **CSV with a header
   row**. A TSV read without `-t` parses as a single column; a headerless file
   read without `-H` silently loses its first data row to the header. Neither
   errors. This is the single most common way to get confident garbage out of
   csvtk — see [references/traps.md](references/traps.md).
2. **Write long flags.** `-f` is `--fields` in twenty subcommands but
   `--filter` — the *expression* — in `filter` and `filter2`. `-n` has eleven
   different meanings. `sort` does not take `-f` at all; it uses `-k/--key`.
   See the collision table in [references/traps.md](references/traps.md).
3. **`csvtk <cmd> --help` is the authority on whether a flag exists.** Never
   assume a flag transfers between subcommands. This document lists no flags on
   purpose — `--help` cannot go stale.

If the job needs real statistics, joins over millions of rows, or anything
beyond row-and-column manipulation, see
[references/boundaries.md](references/boundaries.md).

## Routing table

⚠ marks a subcommand with a documented trap — read its entry in
[references/traps.md](references/traps.md) before using it.

### Inspect and summarise

| Want to... | Command |
|---|---|
| Count rows | `csvtk nrow` |
| Count columns | `csvtk ncol` |
| Get both, plus file size | `csvtk dim` |
| See the column names | `csvtk headers` |
| Get min/max/sum/mean/median/stdev per column | `csvtk summary` ⚠ |
| Get those statistics per group | `csvtk summary --groups` ⚠ |
| Count how often each value appears | `csvtk freq` |
| Get the distinct values of a column | `csvtk uniq` |
| Correlate two numeric columns | `csvtk corr` |
| Print a readable aligned table | `csvtk pretty` |
| Watch a column's distribution as data streams | `csvtk watch` |
| Show progress while streaming a big file | `csvtk cat` |

### Select rows and columns

| Want to... | Command |
|---|---|
| Keep or reorder columns | `csvtk cut --fields` ⚠ |
| Drop columns | `csvtk cut --fields -1,-2` ⚠ |
| Select columns by wildcard | `csvtk cut --fuzzy-fields --fields "*_id"` ⚠ |
| Keep rows where a column matches a value | `csvtk grep` ⚠ (**exact** match; add `--use-regexp` for partial) |
| Keep rows matching a regex | `csvtk grep --use-regexp` ⚠ |
| Keep rows matching any of many values | `csvtk grep --pattern-file` ⚠ |
| Filter rows by a numeric comparison | `csvtk filter` ⚠ (**silently drops** non-numeric rows) |
| Filter rows by an expression over several columns, or on strings | `csvtk filter2` ⚠ |
| Take the first N rows | `csvtk head` |
| Take a random sample | `csvtk sample` |
| Shuffle rows | `csvtk shuf` |

### Combine tables

| Want to... | Command |
|---|---|
| Join two tables on a key | `csvtk join` ⚠ (**inner** join by default — unmatched rows vanish) |
| Keep every row from the first table | `csvtk join --left-join` ⚠ |
| Keep every row from both | `csvtk join --outer-join` ⚠ |
| Stack files with the same columns | `csvtk concat` ⚠ |
| Find rows common to several files | `csvtk inter` |
| Split one file into many by a column's value | `csvtk split` ⚠ |
| Compute combinations of items in a row | `csvtk comb` |

### Edit values and headers

| Want to... | Command |
|---|---|
| Add a column from a regex over existing ones | `csvtk mutate` ⚠ |
| Add a column from an arithmetic or string expression | `csvtk mutate2` ⚠ |
| Add a column using Go-like expressions | `csvtk mutate3` ⚠ |
| Rewrite values in place with a regex | `csvtk replace` ⚠ |
| Rename columns by giving new names | `csvtk rename` |
| Rename columns with a regex | `csvtk rename2` ⚠ |
| Round floats to N decimal places | `csvtk round` |
| Add thousands separators to numbers | `csvtk comma` |
| Reformat dates | `csvtk fmtdate` |
| Add a header row to a headerless file | `csvtk add-header` |
| Strip the header row | `csvtk del-header` |

### Reshape

| Want to... | Command |
|---|---|
| Wide to long (like `tidyr::pivot_longer`) | `csvtk gather` ⚠ |
| Long to wide (like `tidyr::pivot_wider`) | `csvtk spread` ⚠ |
| Split one column into several | `csvtk sep` ⚠ |
| Collapse a group's values into one cell | `csvtk fold` |
| Expand a multi-value cell into rows | `csvtk unfold` |
| Swap rows and columns | `csvtk transpose` |

### Order

| Want to... | Command |
|---|---|
| Sort alphabetically | `csvtk sort --key name` ⚠ (uses `-k`, not `-f`) |
| Sort numerically | `csvtk sort --key "n:n"` ⚠ (plain sort is **lexicographic**: 10 < 9) |
| Sort naturally (a9 before a10) | `csvtk sort --key "n:N"` ⚠ |
| Sort by date | `csvtk sort --key "d:d"` ⚠ |
| Sort by a custom level order | `csvtk sort --key "x:u" --levels "x:levels.txt"` ⚠ |

### Convert

| Want to... | Command |
|---|---|
| CSV to TSV, or TSV to CSV | `csvtk csv2tab` / `csvtk tab2csv` |
| To JSON | `csvtk csv2json` ⚠ |
| To Markdown table | `csvtk csv2md` |
| To reStructuredText | `csvtk csv2rst` |
| To or from Excel | `csvtk csv2xlsx` / `csvtk xlsx2csv` |
| Split an Excel sheet by column value | `csvtk splitxlsx` |
| Space-aligned text to TSV | `csvtk space2tab` |

### Repair

| Want to... | Command |
|---|---|
| Fix rows with inconsistent column counts | `csvtk fix` |
| Fix malformed double quotes | `csvtk fix-quotes` ⚠ |
| Undo `fix-quotes` | `csvtk del-quotes` |

### Plot

| Want to... | Command |
|---|---|
| Histogram, box plot, or line/scatter plot to PNG/PDF | `csvtk plot hist` / `plot box` / `plot line` |

## References

- [references/traps.md](references/traps.md) — behaviours that produce plausible
  but wrong output, indexed by subcommand, plus the short-flag collision table.
- [references/recipes.md](references/recipes.md) — multi-command compositions
  where the composition is the insight.
- [references/boundaries.md](references/boundaries.md) — what csvtk does not do,
  and what does it instead.

---

Verified against **csvtk v0.36.0**. If a command here is unknown to your
`csvtk`, it is older — check `csvtk version`.
