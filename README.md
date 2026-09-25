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

## Uninstalling

Remove skills with `npx skills remove`, not `rm -rf`. The CLI records every
install in `~/.agents/.skill-lock.json`, and `npx skills update` reinstalls
anything still listed there, including skills whose folders you deleted by hand.

[`scripts/skills-prune`](./scripts/skills-prune) lists every globally installed
skill, marks the ones whose folders are gone as `missing`, and lets you pick
which to remove. It needs `bash` and `python3`, and uses `fzf` if it's installed.

```bash
curl -fsSL https://raw.githubusercontent.com/mbhall88/skillz/main/scripts/skills-prune \
  -o ~/bin/skills-prune && chmod +x ~/bin/skills-prune

skills-prune --list      # show the table and exit
skills-prune --dry-run   # pick, then print the remove command without running it
skills-prune             # pick, confirm, remove
```

## Skills

- [`seqkit`](./skills/seqkit/README.md) — teaches an agent to reach for
  [seqkit](https://github.com/shenwei356/seqkit) instead of writing a throwaway
  script every time a task touches a FASTA or FASTQ file. Intent-phrased routing
  across all 39 subcommands, plus the traps that silently produce wrong output.
- [`csvtk`](./skills/csvtk/README.md) — the same idea for
  [csvtk](https://github.com/shenwei356/csvtk) and CSV/TSV files: routing across
  all 54 subcommands, plus the silent traps (a TSV read without `-t` reports one
  column). Companion to `seqkit` — `fx2tab` stops where csvtk starts.
- [`meeting-transcribe`](./skills/meeting-transcribe/README.md) — transcribes
  and diarizes local meeting recordings, matches speakers against enrolled
  voiceprints, and interactively resolves anyone it can't confidently match.
  Also files Zoom `.vtt` exports.

## Changelog

See [CHANGELOG.md](./CHANGELOG.md).

## License

MIT — see [LICENSE](./LICENSE).
