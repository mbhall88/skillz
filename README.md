# skillz

My agent skills, for Claude Code, Codex, and anything else that speaks the
[`SKILL.md` convention](https://skills.sh).

## Installation

```bash
npx skills@latest add mbhall88/skillz
```

Pick which skills you want and which agents to install them to. Or symlink
one manually into an agent's skills directory, e.g. for Claude Code:

```bash
ln -s /path/to/skillz/skills/<name> ~/.claude/skills/<name>
```

## Skills

- [`seqkit`](./skills/seqkit/README.md) — teaches an agent to reach for
  [seqkit](https://github.com/shenwei356/seqkit) instead of writing a throwaway
  script every time a task touches a FASTA or FASTQ file. Intent-phrased routing
  across all 39 subcommands, plus the traps that silently produce wrong output.
- [`meeting-transcribe`](./skills/meeting-transcribe/README.md) — transcribes
  and diarizes local meeting recordings, matches speakers against enrolled
  voiceprints, and interactively resolves anyone it can't confidently match.
  Also files Zoom `.vtt` exports.

## Changelog

See [CHANGELOG.md](./CHANGELOG.md).

## License

MIT — see [LICENSE](./LICENSE).
