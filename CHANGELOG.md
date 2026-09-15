# Changelog

All notable changes to this repository are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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

[Unreleased]: https://github.com/mbhall88/skillz/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mbhall88/skillz/releases/tag/v0.1.0
