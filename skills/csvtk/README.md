# csvtk

Teaches an agent to reach for [csvtk](https://github.com/shenwei356/csvtk)
instead of writing pandas or awk every time a task touches a CSV or TSV.

Companion to the [`seqkit`](../seqkit/README.md) skill, and built to the same
shape. `seqkit fx2tab` deliberately stops where csvtk starts, so the two
together cover the whole path from sequences to a summarised table.

## Setup

None. Requires `csvtk` on `$PATH`; if it isn't there, the skill doesn't apply
and the agent falls back to scripting.

## What's in it

`SKILL.md` carries the part that must always be loaded:

- A routing table covering **all 54 subcommands**, phrased by intent ("want to
  join two tables" → `csvtk join`) rather than by csvtk's own summaries.
- Three standing rules. The first is specific to csvtk and earns its place:
  **state the input format explicitly**. csvtk assumes CSV-with-header and does
  not sniff the file, so a TSV read without `-t` parses as a single column and a
  headerless file quietly loses its first row. Neither errors.

Three reference files are read only when needed:

- **`references/traps.md`** — behaviours that produce plausible but wrong
  output, indexed by subcommand. Anything that fails loudly is excluded.
  Includes the short-flag collision table.
- **`references/recipes.md`** — compositions where the composition is the
  insight, including the `seqkit fx2tab | csvtk` pipe and an anti-join built
  from a left join (csvtk has no anti-join subcommand).
- **`references/boundaries.md`** — what csvtk doesn't do and what does it
  instead. Signposts only.

## The traps that motivated it

All verified against csvtk v0.36.0, all silent:

- A TSV read without `-t` reports **one** column.
- A headerless file read without `-H` loses its first data row to the header.
- Rows beginning with `#` are dropped — including the header, if it starts
  with `#`, as many bioinformatics TSVs do.
- `csvtk sort -k n` sorts **lexicographically**: 10 before 9.
- `csvtk join` is an **inner** join by default; unmatched rows vanish.
- `csvtk filter` **silently discards** rows whose value isn't numeric.
- `csvtk concat` **drops columns** not present in every file and blanks the rest.
- `csvtk summary -f v` with no statistic defaults to **count**, not sum.
- `-f` is `--fields` in twenty subcommands but `--filter` in `filter`/`filter2`.

## What it deliberately omits

There is no flag reference — `csvtk <cmd> --help` is authoritative and cannot go
stale. See
[ADR-0001](../../docs/adr/0001-no-flag-reference-in-tool-skills.md).
