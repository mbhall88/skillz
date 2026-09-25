# seqkit traps

Behaviours that produce plausible but **wrong** output, or that exhaust memory
or time. Anything that fails loudly is deliberately excluded — the error message
is enough.

Every trap below was reproduced against seqkit v2.14.0. Traps that exist only
in older releases say so, and were reproduced against v2.13.0.

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
| `-f` | `--pattern-file` | `grep`, `locate`, `mutate` |
| `-f` | `--file-name` | `fx2tab` (2.14+) |
| `-f` | `--full-head` | `faidx` |
| `-f` | `--only-flank` | `subseq` |
| `-f` | `--force` | `convert`, `pair`, `rename`, `split`, `split2` |
| `-i` | `--ignore-case` | `common`, `faidx`, `grep`, `locate`, `replace`, `rmdup`, `sort` |
| `-i` | `--only-id` | `fx2tab`, `seq` |
| `-i` | `--by-id` | `split` |
| `-i` | `--include-id` | `sum` (2.14+) |

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

**`--header-line` has no column for `--file-name` (2.14+).** The file name is
appended as the last column of every row, but the header line doesn't name it:

```bash
seqkit fx2tab --name --length --file-name --header-line a.fa
# #name   length        <- 2 columns
# x       4       a.fa  <- 3 columns
```

A header-aware parser either rejects the table or drops the file name. Omit
`--header-line` and supply your own header, or append the missing name:
`sed '1s/$/\tfile/'`.

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

**On FASTQ, `--by-seq` keeps the original qualities for replaced bases (2.14+).**
Masking `GT` to `NN` leaves the Ns with the Q scores of the bases they replaced,
so a masked base can still read as Q40. A shorter replacement takes the
quality of the first base in the match, and deletions drop their qualities.
Replacements that lengthen a read are refused outright. Before 2.14, `--by-seq`
refuses FASTQ entirely.

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

**`sample --number` is neither exact nor uniform.** It can return fewer than N
records, and it favours records near the start of the file. Drawing 100 of
1,000 records, the mean record index came out around 390–450 over several
seeds, against 500 for a uniform draw. The last few hundred records are
under-represented. seqkit's own help (2.14) now says it "is not uniform
fixed-size sampling".

**For an exact, uniform N, use `sample2 --number N` (2.13+).** Without
`--two-pass` it loads every record into memory, which is fatal on a large
FASTQ. With `--two-pass` it stores only N record indices, but it needs a file
and can't read stdin. `sample --number` also loads every record without
`--two-pass`.

**`--proportion` never yields an exact count**, except with
`sample2 --proportion p --two-pass`, which outputs exactly `floor(total * p)`.

Output is **deterministic** by default given the same input and seed. For true
randomness pass `--non-deterministic`.

## seq

`--min-len`/`--max-len` measure the sequence **as stored**, gaps included. Strip
gaps first with `--remove-gaps` if you mean ungapped length.

**Setting `--line-width` explicitly wraps FASTQ too (2.14+).** `--line-width 60`
turns each FASTQ record into a multi-line record, wrapping sequence and quality
alike. Many downstream tools expect four-line FASTQ; `seqkit sana` given wrapped
FASTQ discards every record and still exits 0.
The default (not passing the flag) and `--line-width 0` leave FASTQ unwrapped.
`--help` still says the flag is for FASTA only; it is wrong. The flag is
global, so this applies to every subcommand that writes fastx, not just `seq`.
Before 2.14, FASTQ was never wrapped.

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

**Before 2.14, L50 (`N50_num`) is wrong when contig lengths tie.** For contigs of
10, 10, 10, and 2 bp, 2.13 reports L50 = 1; the correct value is 2. N50 itself
is unaffected. On older installs, don't trust L50 from assemblies with many
equal-length contigs.

## sum

**Before 2.14, `--rna2dna` is silently ignored.** An RNA file and its DNA
equivalent get different digests, so the "are these the same?" check reports
a false difference. On older installs, convert first:
`seqkit seq --rna2dna in.fa | seqkit sum`.

**IDs are ignored by default.** Two files with identical sequences under
different IDs get the same digest. Pass `--include-id` (2.14+) if the IDs
matter.

## subseq

**Extracting with `--bed` or `--gtf` from a plain-text FASTA produces randomly
ordered output.** seqkit's documented fix is counter-intuitive: compress the
input and use `input.fasta.gz` instead.

**Memory scales with the annotation file**, not the FASTA. Narrow it with
`--chr` and `--feature` on large GTFs.

Coordinates are **1-based inclusive**, and negative indices count from the end
(`-12:-1` is the last twelve bases). This differs from `locate --bed` and `fish`.
