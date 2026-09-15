# skillz

A collection of agent skills. This glossary pins the terms that recur across
skills in this repo, and the domain terms of the data those skills touch.

## Language

### Skill content

**Trap**:
A documented behaviour that produces a plausible but incorrect result, or
exhausts memory or time, without the operator noticing. Behaviours that fail
loudly are not traps — the error message is sufficient.
_Avoid_: Gotcha, pitfall, footgun

**Recipe**:
A composition of two or more commands where the composition itself is the
insight. A single command, or an obvious pipe between two, is not a recipe.
_Avoid_: Example, snippet, how-to

**Boundary**:
A job a tool does not do, paired with the tool that does. A boundary names the
alternative; it does not teach it.
_Avoid_: Limitation, caveat, out of scope

### Sequence data

**fastx**:
FASTA or FASTQ. seqkit's own word for the pair, and the only formats it
operates on natively.
_Avoid_: Sequence file, bioinformatic file, genome file
