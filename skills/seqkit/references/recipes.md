# seqkit recipes

Compositions where the composition is the insight. A single command, or an
obvious pipe between two, is not here — the routing table in `SKILL.md` already
covers those.

Verified against seqkit v2.13.0.

## When no subcommand does it, round-trip through TSV

This is the escape hatch, and it is almost always better than writing a parser.
`fx2tab` flattens fastx to one record per line; `tab2fx` converts back. Anything
in between is line-oriented text processing.

```bash
seqkit fx2tab --name --length --gc input.fa \
  | awk -F'\t' '$3 > 1000 && $4 > 40' \
  | cut -f1 \
  | seqkit grep --pattern-file - input.fa
```

Reach for this before writing Biopython. Note `fx2tab` always emits three
columns for FASTA (ID, sequence, empty quality) — see `traps.md`.

For anything beyond a simple filter, hand the TSV to `csvtk` rather than
escalating the awk.

## Remove sequences nested inside other sequences

`rmdup --by-seq` removes *identical* sequences. It will not remove a contig that
is wholly contained within a longer one. The trick is to use `locate` as a
self-join: search the file for its own sequences as patterns.

```bash
# 1. remove exact duplicates first
seqkit rmdup --by-seq --ignore-case contigs.fa > uniq.fa

# 2. search the file against itself; every sequence matches itself,
#    so any row where the hit is in a *different* record is a nesting
seqkit locate --hide-matched --pattern-file uniq.fa uniq.fa \
  | awk 'NR > 1 && $1 != $2 { print $2 }' \
  | sort -u > nested.txt

# 3. drop them
seqkit grep --invert-match --pattern-file nested.txt uniq.fa > final.fa
```

Column 1 is the record searched, column 2 is the pattern found in it. A row
where they differ means the column-2 sequence is contained in the column-1
sequence, so column 2 is the one to drop.

## Pull records out of a huge file using a small one

`common` is the obvious command and the wrong one for two files — seqkit's own
help says so. Feed one file's IDs into `grep` instead:

```bash
seqkit grep --pattern-file <(seqkit seq --name --only-id small.fq.gz) big.fq.gz
```

The insight is the process substitution: `seq --name --only-id` turns a fastx
file into the plain ID list that `grep --pattern-file` wants, with no temp file.

Matching by *sequence* rather than ID works but is dramatically slower:
`seqkit grep --by-seq --pattern-file <(seqkit seq --seq small.fq.gz) big.fq.gz`.

## Take a fixed number of reads from a large FASTQ without loading it

`sample --number` reads everything into memory. Sample generously by proportion,
then truncate:

```bash
seqkit sample --proportion 0.1 reads.fq.gz | seqkit head --number 10000
```

The proportion must be large enough that the stream yields at least N records —
this trades exactness for bounded memory. On seqkit 2.13+, prefer
`seqkit sample2 --number 10000 --two-pass reads.fq.gz`, which is exact; the
recipe above is the fallback for older installs and for streaming input that
cannot be read twice.

## Find records containing ambiguous or unexpected bases

`--alphabet` reports the distinct characters each record actually uses, which
turns "does this file contain non-ACGT bases" into a text match:

```bash
seqkit fx2tab --name --only-id --alphabet input.fa \
  | awk -F'\t' '$2 !~ /^ACGT?$/ { print $1 }'
```

The alphabet string is sorted, so `ACGNRTY` sorts predictably and a regex over
it is stable. Useful as a pre-flight before tools that reject ambiguity codes.
