# csvtk recipes

Compositions where the composition is the insight. A single command, or an
obvious pipe between two, is not here — the routing table in `SKILL.md` already
covers those.

Verified against csvtk v0.36.0.

## Tabulate sequences, then wrangle them

`seqkit fx2tab` deliberately stops where csvtk starts. This is the seam both
tools were built around, and it replaces most one-off Biopython scripts:

```bash
seqkit fx2tab --name --only-id --length --gc contigs.fa \
  | csvtk add-header -t -n id,length,gc \
  | csvtk filter2 -t -f '$length > 1000 && $gc > 40' \
  | csvtk sort -t -k 'length:nr' \
  | csvtk pretty -t
```

Two things make this work and are easy to get wrong:

- `fx2tab` emits **headerless TSV**, so every csvtk stage needs `-t`, and the
  first needs `add-header` (or `-H` throughout, referring to columns by number).
- `fx2tab --gc` and `seqkit stats` compute GC differently — see the seqkit
  skill's traps file before mixing them.

To go back to sequences, select the IDs and feed them to `seqkit grep`:

```bash
csvtk cut -t -f id filtered.tsv | tail -n +2 | seqkit grep --pattern-file - contigs.fa
```

## Anti-join: rows in A with no match in B

csvtk has no anti-join subcommand. Compose one from a left join and a test for
the unfilled column:

```bash
csvtk join -f id --left-join left.csv right.csv \
  | csvtk filter2 -f '$tag == ""'
```

`tag` is any column that comes only from the right-hand file; a left join leaves
it empty exactly on the non-matching rows. Verified: with ids 1,2,3 on the left
and 1,3 on the right, this returns id 2 alone.

## Prove a join didn't silently lose rows

`join` is an inner join by default, so unmatched rows vanish without a word.
Make the check explicit rather than trusting the output to look right:

```bash
before=$(csvtk nrow left.csv)
csvtk join -f id left.csv right.csv > joined.csv
after=$(csvtk nrow joined.csv)
echo "$before -> $after"
```

A drop means either genuine non-matches or a key mismatch — whitespace, case, or
a type difference such as `01` versus `1`. `csvtk join` matches on exact string
equality.

## Rank groups by an aggregate

`summary` names its output column `<field>:<stat>`, and that whole string is the
column name — so the sort key carries two colons, one from the name and one from
the sort type:

```bash
csvtk summary --groups g --fields v:sum data.csv \
  | csvtk sort -k 'v:sum:nr' \
  | csvtk head -n 10
```

`v:sum:nr` reads as column `v:sum`, sorted numerically (`n`), reversed (`r`).
Without the `n` the aggregate sorts as text and the ranking is wrong.

## Make a headerless or oddly-commented file workable

Two csvtk defaults bite bioinformatics TSVs in particular: no header, and a
header line that begins with `#`. Normalise once at the front of the pipeline
rather than passing flags to every stage:

```bash
# headerless TSV -> named columns
csvtk add-header -t -H -n chrom,start,end,name < regions.bed > regions.tsv

# header line starts with '#': reassign the comment character
csvtk headers -t -C '$' annotations.tsv
```

Once a file has a real header, the rest of the pipeline only needs `-t`.
