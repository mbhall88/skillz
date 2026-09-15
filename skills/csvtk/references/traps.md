# csvtk traps

Behaviours that produce plausible but **wrong** output, or exhaust memory or
time. Anything that fails loudly is deliberately excluded — the error message is
enough. (Mixing field numbers and names in one `-f`, for instance, errors
clearly and so is not listed here.)

Every trap below was reproduced against csvtk v0.36.0.

## Cross-cutting

### The input format is assumed, not detected

This is the trap. csvtk assumes **CSV with a header row** and does not sniff the
file. Getting it wrong never errors:

```bash
printf 'a\tb\n1\t2\n' > t.tsv
csvtk ncol t.tsv        # 1   — the whole line parsed as one column
csvtk ncol -t t.tsv     # 2   — correct

printf '1,2\n3,4\n' > noheader.csv
csvtk nrow noheader.csv       # 1  — the first data row was eaten as the header
csvtk nrow -H noheader.csv    # 2  — correct
```

Set `-t/--tabs` for TSV and `-H/--no-header-row` for headerless input, every
time. `CSVTK_T` and `CSVTK_H` set them globally for a shell if that is safer for
a given pipeline.

### Lines starting with `#` are silently dropped

```bash
printf 'a,b\n#note,x\n1,2\n' | csvtk nrow          # 1  — the #note row is gone
printf 'a,b\n#note,x\n1,2\n' | csvtk nrow -C '$'   # 2  — comment char reassigned
```

If the **header** itself starts with `#` (common in bioinformatics TSVs), you
must reassign the comment character with `-C` or the header disappears.

### Short flags mean different things in different subcommands

Write long flags. This table exists for *reading* commands you didn't write.

| Flag | Meaning | In |
|---|---|---|
| `-f` | `--fields` | `cut`, `grep`, `freq`, `join`, `summary`, `uniq`, `replace`, `mutate`, `sep`, and ~12 more |
| `-f` | `--filter` (the **expression**) | `filter`, `filter2` |
| `-f` | — (not accepted) | `sort`, which uses `-k/--key` |
| `-n` | `--line-number` | `head`, `pretty`, and others |
| `-n` | `--number`, `--rows`, `--names`, `--name`, `--file-name`, `--buf-rows`, `--start-num`, `--decimal-width`, `--ignore-null`, `--keep-n`, `--no-files`, `--parse-num`, `--sort-by-freq` | scattered across the toolkit — eleven distinct meanings in all |
| `-k` | `--key` | `sort` |
| `-k` | `--keep-unmatched` / `--kv-file` / `--keys` / `--keep-unparsed` / `--sort-by-key` | `join`, `replace`, and others |
| `-s` | `--separater` *(sic)* | `fold`, `unfold`, and others |
| `-s` | `--rand-seed` | `sample`, `shuf` |
| `-s` | `--numeric-as-string`, `--sort`, `--suffix`, `--prefix-as-subdir` | scattered |
| `-r` | `--use-regexp` | `grep`, `uniq` |
| `-r` | `--replacement` | `replace`, `mutate` |
| `-r` | `--reverse` / `--align-right` | `sort`, `pretty` |
| `-p` | `--pattern` | `grep`, `replace`, and others |
| `-p` | `--proportion` / `--out-prefix` / `--prefix-filename` | `sample`, `split` |

The worst pair: `-f` selects **columns** almost everywhere, but in `filter` and
`filter2` it is the filter **expression**. `csvtk filter -f name` does not
select a column.

### Field selection syntax

`-f` accepts numbers (`1,3`), names (`id,name`), ranges (`3-5`, `5-` to the
end), and negatives to exclude (`-1,-2` drops the first two; `-1--3` drops one
through three). Wildcards require `-F/--fuzzy-fields`: `-F -f "*_name"`.

Numbers and names cannot be mixed in one `-f` — that errors clearly.

---

## concat

**Columns not present in every file are silently dropped, and missing values
silently blanked.** Verified:

```bash
printf 'a,b\n1,2\n' > c1.csv
printf 'a,c\n5,6\n' > c3.csv
csvtk concat c1.csv c3.csv
# a,b
# 1,2
# 5,          <- column c discarded, column b empty, no warning
```

Files whose columns match but are in a *different order* are realigned
correctly. Check headers agree before concatenating.

## csv2json

**Every value is emitted as a string**, including numbers:

```bash
printf 'n,s\n10,abc\n' | csvtk csv2json
# [{"n":"10","s":"abc"}]
```

Consumers that expect numeric JSON types will need a conversion step.

## filter

**Rows whose value is not numeric are silently discarded**, not skipped with a
warning and not treated as false. Verified on `val` = `10`, `NA`, `20`:

```bash
csvtk filter -f 'val>5' m.csv   # returns the 10 and 20 rows; the NA row vanishes
```

The output is a correct-looking table with fewer rows than you expect. If
non-numeric values are meaningful, use `filter2`, which evaluates strings.

**`-f` here is the expression, not the field list.** See the collision table.

## filter2

`-f` is the expression. Column references are `$name` or `${name with spaces}`;
string constants take **single** quotes (`$name == 'beta'`). The expression
engine is govaluate, which is not the same language as `mutate3`'s.

## fix-quotes

Changes the file's quoting, not just its validity. `del-quotes` reverses it. Run
the pair only when a parse actually fails — `-l/--lazy-quotes` handles the
`bare " in non-quoted-field` case without rewriting anything. Note `-l` does
**not** fix `extraneous or missing " in quoted-field`; that one needs
`fix-quotes`.

## gather / spread

`gather` (wide to long) and `spread` (long to wide) are inverses only when the
key-value pair uniquely identifies a row. Duplicate keys within a group make
`spread` ambiguous. Confirm row counts before and after.

## grep

**Matching is exact by default**, against the whole field value:

```bash
csvtk grep -f name -p alpha              # matches "alpha" only
csvtk grep -f name -r -p alpha           # matches "alpha" and "alphabet"
```

Without `--use-regexp`, a partial pattern returns an empty result that reads as
"no matches" rather than "wrong flag".

## join

**Inner join by default** — rows without a match in *both* files disappear
silently:

```bash
csvtk join -f id left.csv right.csv                # inner: unmatched rows gone
csvtk join -f id --left-join left.csv right.csv    # keep all of left
csvtk join -f id --outer-join left.csv right.csv   # keep all of both
```

Compare `csvtk nrow` before and after whenever the row count matters.

## mutate / mutate2 / mutate3

Three different expression languages, not three levels of the same one:

- `mutate` — regular expression capture over one field.
- `mutate2` — arithmetic and string expressions (govaluate). Same language as
  `filter2`. String constants use single quotes.
- `mutate3` — Go-like expressions (expr-lang). Supports `contains`,
  `startsWith`, `matches`, ranges, pipes.

An expression written for one will not generally work in another. Pick by
language, not by version number.

## replace / rename2

`replace` rewrites **values** inside selected fields; `rename2` rewrites
**column names**. Both take a regex and both use `-p/--pattern` with
`-r/--replacement`, so a command aimed at the wrong one is syntactically valid
and quietly edits the wrong thing.

## sep

Splitting a column into N parts when some rows produce fewer parts leaves
trailing columns empty rather than failing. Check for blanks afterwards.

## sort

**Sorting is alphabetical by default**, so numbers order as text:

```bash
csvtk sort -k n      # 10, 2, 9
csvtk sort -k n:n    # 2, 9, 10
```

Append `:n` for numeric, `:N` for natural (`a9` before `a10`), `:d` for dates,
`:u` with `--levels <field>:<file>` for custom level order, and `r` to reverse (`:nr`).

**`sort` takes `-k/--key`, not `-f/--fields`** — the only field-selecting
subcommand that does.

## split

Writes one file per distinct value of the chosen column, into the current
directory by default. A high-cardinality column produces an enormous number of
files with no warning. Check `csvtk freq` on that column first.

## summary

**A field given without a statistic defaults to `count`**, silently:

```bash
csvtk summary -f v      sm.csv    # v:count -> 3
csvtk summary -f v:sum  sm.csv    # v:sum   -> 9.00
```

If you meant a sum and wrote `-f v`, you get a row count that looks like a
plausible answer.

**Output is formatted to two decimal places.** Precision beyond that is lost in
the printed result; adjust with `--decimal-width` if it matters.

Field ranges are supported with the statistic applied across them:
`-f 2-5:sum`.

## uniq

Returns the distinct values of the selected fields, dropping every other column.
For value *counts*, use `freq`; for whole-row deduplication that keeps all
columns, select every field.
