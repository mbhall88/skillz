---
name: seqkit
description: Manipulate FASTA/FASTQ files with seqkit — filter, subset, convert, search, deduplicate, split, sample, translate, rename, and summarise sequence data. Use whenever a task touches a FASTA or FASTQ file, even when the format is not named ("how many reads", "pull out these contigs", "what is the N50", "find this motif"), and especially before writing Python, Biopython, awk, or bash to parse, filter, count, convert, or summarise sequence files — seqkit almost certainly already does it, in one streaming command.
---

# seqkit

`seqkit` is a fast, streaming toolkit for **fastx** files (FASTA or FASTQ). It has
39 subcommands covering nearly every routine sequence-file operation. Before
writing a script that reads a fastx file, check the routing table below.

Requires `seqkit` on `$PATH`. If it is not there, this skill does not apply —
fall back to scripting.

## Rules

1. **Write long flags.** Short flags mean different things in different
   subcommands: `-s` is `--by-seq` in `rmdup` but `--rand-seed` in `sample`,
   `--step` in `sliding`, and `--pattern` in `mutate`. `-p` is `--pattern` in
   `grep` but `--point` in `mutate`. Long flags are unambiguous and
   self-documenting. See [references/traps.md](references/traps.md) for the
   collision table, needed when *reading* someone else's command.
2. **`seqkit <cmd> --help` is the authority on whether a flag exists.** Never
   assume a flag from another subcommand transfers. This document does not list
   flags on purpose — `--help` cannot go stale, and published seqkit docs
   demonstrably do.
3. **If it isn't fastx, it isn't seqkit.** Interval arithmetic, BAM
   manipulation, alignment, and tabular wrangling are other tools' jobs. See
   [references/boundaries.md](references/boundaries.md).

Leave global flags (`-j/--threads`, `-w/--line-width`, `--id-regexp`) at their
defaults unless the user asks.

## Routing table

⚠ marks a subcommand with a documented trap — read its entry in
[references/traps.md](references/traps.md) before using it.

### Inspect and summarise

| Want to... | Command |
|---|---|
| Count records, total bases, min/max/mean length, GC%, Q20/Q30 | `seqkit stats` ⚠ (lengths and GC **include gaps**) |
| Get N50, L50, or any Nx | `seqkit stats --all --tabular -N 50,90` ⚠ |
| Get machine-readable stats for downstream processing | `seqkit stats --tabular` ⚠ |
| Get per-record length, GC, name, or average quality as a table | `seqkit fx2tab` ⚠ |
| Find records containing ambiguous or unexpected bases | `seqkit fx2tab --alphabet` ⚠ |
| Get a per-sequence MD5 hash | `seqkit fx2tab --seq-hash` ⚠ |
| Tabulate several files at once, tagging each row with its source file (2.14+) | `seqkit fx2tab --file-name` ⚠ |
| Prove two files contain the same sequences, any order or strand | `seqkit sum` ⚠ |
| Prove two files contain the same records, IDs included (2.14+) | `seqkit sum --include-id` ⚠ |
| Watch length/quality/GC distributions while a pipeline runs | `seqkit watch` |
| Get BAM record statistics or histograms | `seqkit bam` |

### Filter and subset

| Want to... | Command |
|---|---|
| Keep sequences above/below a length | `seqkit seq --min-len` / `--max-len` ⚠ |
| Keep reads above an average quality | `seqkit seq --min-qual` ⚠ |
| Filter and transform in one pass (2.13+) | `seqkit seq --f-pattern` ⚠ |
| Pull out records by ID, from a list | `seqkit grep --pattern-file` ⚠ (matches the **whole ID**; use `--use-regexp` for partial) |
| Pull out records by ID, preserving the *list's* order | `seqkit faidx --region-file` ⚠ |
| Take the first N records | `seqkit head` |
| Take the first N bases' worth of records | `seqkit head --length 2G` |
| Take records 101-200, or the last 100 | `seqkit range --range` |
| Take a random subset | `seqkit sample2` (2.13+) ⚠ |
| Extract a region by coordinates | `seqkit subseq --region` ⚠ |
| Extract regions listed in a BED or GTF file | `seqkit subseq --bed` / `--gtf` ⚠ |
| Extract features plus flanking sequence | `seqkit subseq --gtf --up-stream` ⚠ |
| Extract a named region from an indexed FASTA | `seqkit faidx` ⚠ |
| Pull out the first genome from a multi-strain file by name prefix | `seqkit head-genome` |

### Search

| Want to... | Command |
|---|---|
| Find records whose ID matches a pattern | `seqkit grep --use-regexp` ⚠ |
| Find records containing a subsequence or motif | `seqkit grep --by-seq` ⚠ |
| Find records containing a motif, allowing mismatches | `seqkit grep --by-seq --max-mismatch` ⚠ |
| Search with IUPAC/degenerate bases | `seqkit grep --by-seq --degenerate` ⚠ |
| Get the *coordinates* of every motif match | `seqkit locate` ⚠ |
| Get motif matches as BED or GTF | `seqkit locate --bed` / `--gtf` ⚠ |
| Scan for restriction sites from a FASTA of motifs | `seqkit locate --degenerate --pattern-file` ⚠ |
| Do in-silico PCR from a primer pair | `seqkit amplicon` ⚠ |
| Locally align short queries into long sequences | `seqkit fish` ⚠ |

### Convert and tabulate

| Want to... | Command |
|---|---|
| Convert FASTQ to FASTA | `seqkit fq2fa` |
| Recover FASTQ (with qualities) for sequences you only have as FASTA | `seqkit fa2fq` |
| Turn fastx into a TSV for downstream tools | `seqkit fx2tab` ⚠ |
| Turn a TSV back into fastx | `seqkit tab2fx` |
| Convert FASTQ quality encoding (Solexa/Illumina/Sanger) | `seqkit convert` |
| Translate DNA/RNA to protein, any genetic code, any frame | `seqkit translate` |
| Reverse complement | `seqkit seq --reverse --complement` ⚠ |
| Strip gaps from an alignment | `seqkit seq --remove-gaps` ⚠ |
| Unwrap FASTA to one line per sequence | `seqkit seq --line-width 0` ⚠ |
| Extract just the IDs or just the sequences | `seqkit seq --name --only-id` / `--seq` ⚠ |

### Set operations and deduplication

| Want to... | Command |
|---|---|
| Remove duplicate records by ID or by sequence | `seqkit rmdup` ⚠ (`--by-seq` also collapses **reverse complements**) |
| Get a report of which records were duplicated | `seqkit rmdup --dup-num-file` ⚠ |
| Find sequences shared across several files | `seqkit common` ⚠ |
| Re-pair paired-end reads, dropping or saving singletons | `seqkit pair` ⚠ |
| Join sequences with the same ID across files | `seqkit concat` ⚠ |
| Repeat each record N times | `seqkit duplicate` |

### Split and sample

| Want to... | Command |
|---|---|
| Split into N files, or files of N records | `seqkit split2 --by-part` / `--by-size` ⚠ |
| Split into one file per record, named by ID | `seqkit split2 --by-size 1 --seqid-as-filename` ⚠ |
| Split by ID, by a regex on the header, or by region | `seqkit split` ⚠ |
| Split paired-end FASTQ, keeping pairs together | `seqkit split2 --read1 --read2` ⚠ |
| Take a random sample of records | `seqkit sample2` (2.13+) ⚠ |
| Chop a sequence into fixed-size windows | `seqkit sliding` |
| Merge sliding windows back into intervals | `seqkit merge-slides` |

### Edit and reorder

| Want to... | Command |
|---|---|
| Rewrite headers with a regex | `seqkit replace` ⚠ |
| Substitute, mask, or delete bases by regex (FASTQ from 2.14+) | `seqkit replace --by-seq` ⚠ |
| Rewrite headers from a TSV lookup table | `seqkit replace --kv-file` ⚠ |
| Number records sequentially, or stamp the filename into the header | `seqkit replace` with `{nr}` / `{fbne}` ⚠ |
| Make duplicate IDs unique | `seqkit rename` ⚠ |
| Introduce point mutations, insertions, or deletions | `seqkit mutate` ⚠ |
| Rotate a circular genome to a new origin | `seqkit restart` |
| Sort by ID, length, or sequence | `seqkit sort` ⚠ |
| Shuffle record order | `seqkit shuffle` ⚠ |

### Streaming and repair

| Want to... | Command |
|---|---|
| Repair a truncated or malformed FASTQ, skipping bad records | `seqkit sana` |
| Stream fastx files as they appear in a directory | `seqkit scat` |
| Feed a long list of input files | any command, with `--infile-list` |

## References

- [references/traps.md](references/traps.md) — behaviours that produce plausible
  but wrong output, or exhaust memory. Indexed by subcommand.
- [references/recipes.md](references/recipes.md) — multi-command compositions
  where the composition is the insight.
- [references/boundaries.md](references/boundaries.md) — what seqkit does not do,
  and what does it instead.

---

Verified against **seqkit v2.14.0**. If a command here is unknown to your
`seqkit`, it is older — check `seqkit version`.
