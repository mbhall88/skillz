# seqkit traps

Behaviours that produce plausible but **wrong** output, or that exhaust memory
or time. Anything that fails loudly is deliberately excluded — the error message
is enough.

Every trap below was reproduced against seqkit v2.13.0.

## Cross-cutting

### Short flags mean different things in different subcommands

Write long flags. This table exists for *reading* commands you didn't write.

| Flag | Meaning | In |
|---|---|---|
| `-s` | `--by-seq` | `common`, `grep`, `replace`, `rmdup`, `sort` |
| `-s` | `--rand-seed` | `sample`, `sample2`, `shuffle` |
| `-s` | `--by-size` | `split`, `split2` |
| `-s` | `--step` | `sliding` |
| `-s` | `--pattern` | `mutate` |
| `-s` | `--separator` | `concat`, `rename` |
| `-s` | `--seq` | `seq` |
| `-p` | `--pattern` | `grep`, `locate`, `replace` |
| `-p` | `--point` | `mutate` |
| `-p` | `--proportion` | `sample`, `sample2` |
| `-p` | `--by-part` | `split`, `split2` |
| `-p` | `--complement` | `seq` |
| `-r` | `--use-regexp` | `grep`, `locate`, `mutate`, `faidx` |
| `-r` | `--reverse` | `seq`, `sort` |
| `-r` | `--region` | `subseq`, `amplicon` |
| `-r` | `--replacement` | `replace` |
| `-r` | `--non-deterministic` | `sample`, `sample2`, `shuffle` |
| `-2` | `--two-pass` | `sort`, `shuffle`, `sample`, `sample2`, `split` |
| `-2` | `--read2` | `split2`, `pair` |

The worst pair: `grep -p PATTERN` and `mutate -p` are unrelated — in `mutate`,
`-p` is `--point` and the pattern flag is `-s`. A command transferred between
them is valid and wrong.

`grep` uses `-r` for regexp and `-R` for region; `subseq` uses `-r` for region.
Exactly inverted.

### Threads

`-j/--threads` defaults to 4. Raising it only affects `stats`, `scat`, and
`--by-seq --max-mismatch` searches in `grep`, `locate`, and `amplicon`.
Everywhere else it does nothing.

### `-t/--seq-type` is global but mostly inert

It appears in every subcommand's help. It only takes effect in `seq` and
`locate`. Setting it also silently switches on `-v/--validate-seq`.

---

## amplicon

Only the **single longest match** per primer pair is returned, and you cannot
control whether a mismatch falls at the 5' or 3' end. A primer pair that matches
several times in a sequence yields one amplicon, not all of them.

`--max-mismatch` cannot be combined with degenerate bases in the primer.

## common

**Comparing by sequence compares both strands.** `--by-seq` treats a sequence and
its reverse complement as shared. Use `--only-positive-strand` for strand-aware
comparison.

**For exactly two files, don't use it.** seqkit's own help says `grep` is much
faster and uses far less memory:

```bash
seqkit grep --pattern-file <(seqkit seq --name --only-id small.fq.gz) big.fq.gz
```

The `--by-seq` equivalent is described in the help as "much slower!!!!".

**Record count can exceed the smallest file.** If several records in one file
share a sequence or ID, all of them are retrieved.

## concat

**Sequences with different IDs come out in random order.** If order matters,
sort afterwards.

By default only IDs present in *every* input file are output. Records sharing an
ID produce the Cartesian product of those sequences, not a single pairing.

## faidx

**`.seqkit.fai` is not a samtools `.fai`.** seqkit keys the index on the full
sequence header, samtools on the ID alone. The two are not interchangeable
despite the similar name.

**A stale index silently returns wrong sequence.** If the FASTA changed after the
index was built, extraction succeeds and returns the wrong bases. Pass
`-U/--update-faidx` whenever you are not certain the index is current. The same
applies to `--two-pass` in `sort`, `shuffle`, `split`, and `subseq`.

## fish

Output coordinates are **BED-like: 0-based, half-open** — unlike `subseq`,
`faidx`, and `locate`'s default output, which are 1-based inclusive.

## fx2tab

**GC% disagrees with `seqkit stats`.** `fx2tab --gc` uses `(G+C)/(G+C+A+T)`;
`stats` divides by the full sequence length including gaps. On `ACGT--ACGT`:
`fx2tab` reports 50.00, `stats` reports 40.00. Neither is wrong; they answer
different questions. Do not mix them in one analysis.

(The `fx2tab` denominator changed in v2.10.1. Numbers from older seqkit differ.)

**Output always has three columns, even for FASTA** — ID, sequence, quality —
with the quality column empty. Code that assumes two columns for FASTA and three
for FASTQ will misparse.

## grep

**It is not POSIX grep.** By default the pattern is compared against the
**whole ID**, not searched within it:

```bash
seqkit grep --pattern s1   # matches the record with ID exactly "s1"
seqkit grep --pattern s    # matches nothing
seqkit grep --use-regexp --pattern s   # matches every ID containing "s"
```

This fails silently — an empty result looks like "no hits" rather than "wrong
flag".

**It matches the ID, not the full header.** Use `--by-name` to match the whole
description line.

**`--by-seq` searches both strands.** A record matches if the pattern occurs on
either strand. `--only-positive-strand` disables this.

**Output order follows the input file, not the pattern list.** To get results in
the order of your ID list, use `seqkit faidx --region-file ids.txt` instead
(FASTA only).

**`--pattern` parses commas as separators.** A regex containing a literal comma
must be double-quoted inside the shell quotes: `--pattern '"A{2,}"'`. Patterns
supplied via `--pattern-file` are exempt.

**Not for genome-scale search.** seqkit's help says to use a mapping or alignment
tool for large genomes.

## locate

**Default output is 1-based inclusive; `--bed` output is 0-based half-open.** The
same match is reported as `3..8` by default and `2..8` with `--bed`. Mixing the
two silently shifts every coordinate by one.

**Palindromic motifs are reported twice** — once per strand, with identical
coordinates. `GAATTC` in one sequence yields two rows.

## mutate

`-p` is `--point`, **not** `--pattern`. The record-selection flag is
`-s/--pattern`. See the collision table above.

## pair

**If the two files are not in the same order, memory use explodes.** seqkit
buffers reads while waiting for their mates. It does not warn; it just grows.
Confirm both files are in matching order first.

Output gzip files may be slightly larger than the originals — seqkit's gzip
writer is not GNU gzip. Nothing is wrong with the data.

## rename

**It is not a general renamer.** It only appends `_2`, `_3` … to *duplicate* IDs,
leaving the first occurrence untouched. For actual renaming use `replace`.

## replace

**Use single quotes, not double quotes.** `$` in a replacement must be written
`$$`, and `$$$$` inside a key-value file.

**With `--kv-file`, write `${1}` not `$1`.** The braced form is required for the
capture group to be delimited correctly when followed by other characters.

`--key-capt-idx` selects *which* capture group is the lookup key, and defaults
to 1. With a multi-group pattern, the default is often the wrong group and the
lookup silently misses.

## rmdup

**`--by-seq` treats reverse complements as duplicates.** Verified:

```bash
printf '>a\nAAAA\n>b\nTTTT\n' | seqkit rmdup --by-seq   # only >a survives
```

`b` is not a literal duplicate — it is the reverse complement of `a`. Use
`--only-positive-strand` for literal deduplication. The same applies to
`common --by-seq` and `grep --by-seq`.

## sample / sample2

**`sample --number` loads every record into memory.** On a large FASTQ this is
fatal. seqkit's help recommends
`seqkit sample --proportion 0.1 seqs.fq.gz | seqkit head --number N`.

**`sample2` is the better tool (2.13+)** but is not unconditional: its own help
says `--number` "SHOULD BE coupled with 2-pass mode (`-2`) when large FASTQ
files, otherwise it loads ALL seqs into memory". The bounded-memory claim
applies to two-pass mode.

Output is **deterministic** by default given the same input and seed. For true
randomness pass `--non-deterministic`.

## seq

`--min-len`/`--max-len` measure the sequence **as stored**, gaps included. Strip
gaps first with `--remove-gaps` if you mean ungapped length.

`--line-width` applies to FASTA only; FASTQ output is always four lines.

## shuffle / sort

**Everything is read into memory by default.** `--two-pass` reduces this but is
**FASTA only** — seqkit's help states plainly that FASTQ is not supported. There
is no low-memory path for sorting or shuffling a large FASTQ.

When using `--two-pass`, pass `-U/--update-faidx` unless you are certain the
index is current. See `faidx` above.

## split

**On macOS and Windows, `--by-id` can silently overwrite output.** Case-
insensitive filesystems collapse IDs differing only in case (`Abc` and `ABC`)
into one file. Pass `-I/--ignore-case` to avoid it.

**`split2` is faster and uses less memory.** seqkit's own help says
`seqkit split2 --by-size 1 --seqid-as-filename` is equivalent to
`seqkit split --by-id` but "much faster and uses less memory".

## split2

`-2` here is `--read2`, not `--two-pass`. See the collision table.

## stats

**All length metrics include gaps and spaces** — `sum_len`, `min_len`, `avg_len`,
`max_len`, and the quartiles. For ungapped statistics, strip first:

```bash
seqkit seq --remove-gaps input.fa | seqkit stats --all
```

**GC% is computed differently from `fx2tab --gc`.** See `fx2tab` above.

## subseq

**Extracting with `--bed` or `--gtf` from a plain-text FASTA produces randomly
ordered output.** seqkit's documented fix is counter-intuitive: compress the
input and use `input.fasta.gz` instead.

**Memory scales with the annotation file**, not the FASTA. Narrow it with
`--chr` and `--feature` on large GTFs.

Coordinates are **1-based inclusive**, and negative indices count from the end
(`-12:-1` is the last twelve bases). This differs from `locate --bed` and `fish`.
