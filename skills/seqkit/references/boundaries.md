# What seqkit does not do

seqkit operates on **fastx** files — FASTA and FASTQ. When the job is something
else, reach for the tool named here rather than forcing seqkit or writing a
script. This file names the alternative; it does not teach it.

| Job | Tool |
|---|---|
| Interval arithmetic on BED/GFF — intersect, merge, subtract, closest | `bedtools` |
| BAM/SAM manipulation — view, sort, index, pileup, filter | `samtools` |
| Read alignment and mapping | `minimap2`, `bwa`, `bowtie2` |
| Sequence similarity search at scale | `blast`, `diamond`, `minimap2` |
| Multiple sequence alignment | `mafft`, `muscle`, `clustalo` |
| Quality trimming and adapter removal | `fastp`, `cutadapt`, `trim_galore` |
| Assembly evaluation beyond N50/L50/Nx | `quast` |
| Variant calling and VCF manipulation | `bcftools` |
| GFF3 handling — `subseq --gtf` accepts GTF 2.2 only | `gffread` to convert first |
| k-mer counting and sketching | `jellyfish`, `sourmash`, `unikmer` |
| Wrangling the TSV that `fx2tab` produces | `csvtk` — see the [csvtk skill](../../csvtk/SKILL.md) |
| Splitting a sequence into N equal chunks | `kmcp utils split-genomes` |

## Notes on the near misses

**`seqkit bam`** reports statistics and histograms of BAM records. It does not
manipulate BAM files. Anything beyond inspection is a `samtools` job.

**`seqkit fish`** and **`grep --by-seq --max-mismatch`** do sequence search, but
seqkit's own documentation says to use a mapping or alignment tool for
genome-scale work. They are for short queries in modest targets.

**`seqkit locate --bed`** emits intervals but performs no interval arithmetic.
Once you have the BED, the next step is `bedtools`.

**`seqkit subseq --bed`** reads a BED to cut sequence out of a FASTA. That is the
only direction it goes.

**`csvtk`** is the designated downstream partner — `fx2tab` deliberately stops
where csvtk starts, and `seqkit stats --help` and `replace --help` both name it.
See the [csvtk skill](../../csvtk/SKILL.md), which covers that handoff and the
`fx2tab | csvtk` pipe.
