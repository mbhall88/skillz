# What csvtk does not do

csvtk operates on delimited text — CSV, TSV, and their compressed forms. When
the job is something else, reach for the tool named here rather than forcing
csvtk or writing a script. This file names the alternative; it does not teach it.

| Job | Tool |
|---|---|
| FASTA/FASTQ manipulation | `seqkit` — see the [seqkit skill](../../seqkit/SKILL.md) |
| Statistical modelling, regression, tests beyond Pearson correlation | R, or Python with scipy/statsmodels |
| Joins and aggregations over tens of millions of rows | `duckdb`, SQLite, or Polars |
| Querying tabular data with SQL | `duckdb`, `q`, `textql` |
| Nested or deeply structured JSON | `jq` (csvtk only flattens CSV *into* JSON) |
| Streaming record-oriented transforms across many formats | `miller` (`mlr`) |
| Parquet, Arrow, or other columnar binary formats | `duckdb`, Polars, PyArrow |
| Interval arithmetic on genomic BED/GFF | `bedtools` |
| Publication-quality plots | R/ggplot2, matplotlib — `csvtk plot` is for a quick look |
| Fuzzy or approximate record linkage | a dedicated record-linkage library |

## Notes on the near misses

**`csvtk plot`** draws histograms, box plots, and line/scatter plots to PNG or
PDF. It is for a quick look during exploration, not for figures that will be
published.

**`csvtk summary`** covers the common descriptive statistics — min, max, sum,
mean, median, quartiles, stdev, variance, entropy — grouped or ungrouped. It
does not do inference: no tests, no models, no confidence intervals.

**`csvtk corr`** computes Pearson correlation between two columns. Anything
else — Spearman, partial correlation, a correlation matrix — is R or Python.

**`csvtk csv2json`** flattens a table into an array of flat objects, with every
value a string. It is not a general JSON tool; reading or reshaping nested JSON
is `jq`'s job.

**Row counts.** csvtk streams and is fast well past the point where a spreadsheet
gives up, but it is still a row-at-a-time text tool. Once joins and group-bys
run to tens of millions of rows, an actual query engine will beat it
comfortably.
