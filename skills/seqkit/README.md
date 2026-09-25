# seqkit

Teaches an agent to reach for [seqkit](https://github.com/shenwei356/seqkit)
instead of writing a throwaway script every time a task touches a FASTA or
FASTQ file.

The problem this solves is not that agents can't use seqkit — it's that they
don't think of it. Asked to filter contigs by length, an agent will happily
write forty lines of Biopython for something `seqkit seq --min-len 1000` does
in one streaming pass. And when it *does* reach for seqkit, the flag surface is
full of traps that produce plausible, wrong output.

## Setup

None. Requires `seqkit` on `$PATH`; if it isn't there, the skill doesn't apply
and the agent falls back to scripting.

## What's in it

`SKILL.md` carries the part that must always be loaded:

- A routing table covering **all 39 subcommands**, phrased by intent ("want to
  deduplicate" → `seqkit rmdup`) rather than by seqkit's own summaries, so it
  matches how a request actually arrives. Nothing is curated out — the long
  tail is where the surprises live, and nobody guesses that `seqkit sum` gives
  a rotation- and strand-invariant digest of a genome, or that `sana` repairs
  truncated FASTQ.
- Three standing rules: write long flags, treat `--help` as the authority on
  whether a flag exists, and don't force seqkit onto non-fastx jobs.

Three reference files are read only when needed:

- **`references/traps.md`** — behaviours that produce plausible but wrong
  output, or exhaust memory, indexed by subcommand. Anything that fails loudly
  is excluded: the error message is enough. Includes the short-flag collision
  table, needed for *reading* commands rather than writing them.
- **`references/recipes.md`** — multi-command compositions where the
  composition is the insight, such as using `locate` as a self-join to find
  nested contigs.
- **`references/boundaries.md`** — what seqkit doesn't do and what does it
  instead. Signposts only.

## What it deliberately omits

There is no flag reference. `seqkit <cmd> --help` is available at runtime, is
authoritative, and cannot go stale — whereas published seqkit documentation
demonstrably can: the official FAQ still tells users to run `rmdup --md5`, a
flag that doesn't exist in any 2.x release. The skill carries only what
`--help` omits. See
[ADR-0001](../../docs/adr/0001-no-flag-reference-in-tool-skills.md).

## Verification

Every trap and recipe was reproduced against **seqkit v2.14.0** before being
written down, including the full short-flag collision map. Traps that apply
only to older releases were reproduced against v2.13.0. The version is pinned
at the bottom of `SKILL.md`. Recent additions carry a version marker, because
HPC module files often run years behind: `(2.13+)` for `sample2` and the
`seq --f-*` filters, `(2.14+)` for `sum --include-id`, `fx2tab --file-name`,
and `replace --by-seq` on FASTQ.
