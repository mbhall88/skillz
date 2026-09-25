# Changelog

All notable changes to this repository are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.3.1] - 2026-09-25

### Changed

- `seqkit` skill: updated for seqkit v2.14.0. New routing entries for
  `sum --include-id`, `fx2tab --file-name`, and `replace --by-seq` on FASTQ.
  New traps: an explicit `--line-width` now wraps FASTQ, `fx2tab --header-line`
  has no column for `--file-name`, and FASTQ `replace --by-seq` keeps the old
  qualities on masked bases. Older releases also get traps for a wrong L50 on
  tied contig lengths and an ignored `sum --rna2dna`. The `-f` and `-i` rows are
  added to the short-flag collision table.

### Fixed

- `seqkit` skill: `sample --number` is non-uniform, and so is the
  `sample --proportion | head` fallback recipe, which was biased toward the
  start of the file. Both are now documented as such, and the recipe points to
  `sample2 --number --two-pass`. Removed the claim that FASTQ output ignores
  `--line-width`.

## [0.3.0] - 2026-09-15

### Added

- `csvtk` skill: routes tabular-data tasks to the right csvtk subcommand instead
  of pandas or awk. Intent-phrased routing table across all 54 subcommands, plus
  reference files for traps, recipes, and boundaries. Verified against csvtk
  v0.36.0.

### Changed

- `seqkit` skill: `boundaries.md` now points at the csvtk skill for the
  `fx2tab | csvtk` handoff, rather than noting it as planned.

## [0.2.0] - 2026-09-15

### Added

- `seqkit` skill: routes sequence-file tasks to the right seqkit subcommand
  instead of a throwaway script. Intent-phrased routing table across all 39
  subcommands, plus reference files for traps, recipes, and boundaries.
  Verified against seqkit v2.13.0.
- `CONTEXT.md` glossary and `docs/adr/` for architecture decision records.

## [0.1.0] - 2026-09-08

### Added

- `meeting-transcribe` skill: transcribes and diarizes local `.m4a` meeting
  recordings with WhisperX and pyannote.audio, matches speakers against
  enrolled voiceprints, and interactively resolves anyone it can't
  confidently identify. Also files Zoom `.vtt` exports without re-running
  the ML pipeline.

[Unreleased]: https://github.com/mbhall88/skillz/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/mbhall88/skillz/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/mbhall88/skillz/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mbhall88/skillz/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mbhall88/skillz/releases/tag/v0.1.0
