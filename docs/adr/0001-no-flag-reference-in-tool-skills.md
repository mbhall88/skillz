# Tool skills ship no flag reference

The `seqkit` skill documents intent-to-subcommand routing, traps, recipes, and
boundaries, but deliberately does not document flags. `seqkit <cmd> --help` is
available at runtime on every machine the skill can run on and cannot go stale,
whereas a written flag reference can: seqkit's own FAQ currently instructs users
to run `rmdup --md5`, a flag that does not exist in any 2.x release. The skill
therefore carries only what `--help` omits — the cost model, the surprising
behaviours, and the multi-command compositions — and treats `--help` as the
authority on whether a flag exists.

## Considered options

**Ship a flag reference.** Rejected. It duplicates a source of truth that is
both authoritative and always present, and it decays silently: the reader has no
way to tell which rows are still true. The failure mode is worse than the gap it
fills.

**Defer everything to `--help`.** Rejected. `--help` documents flag mechanics
well but says nothing about which subcommands stream versus load into RAM, which
benefit from more than four threads, or how commands compose. That material only
exists on the docs site or nowhere.

## Consequences

One exception survives: a minimal table of the short flags that mean different
things in different subcommands (`-s`, `-p`, `-r`, `-2`). The skill's standing
rule is to *write* long flags, which makes the table unnecessary for authoring
commands — but agents also *read* existing pipelines, where short flags are
already present and must be interpreted.

`--help` is authoritative on flag existence, not on prose. `seqkit sample2
--help` refers to a `seqkit shuf` command that does not exist.
