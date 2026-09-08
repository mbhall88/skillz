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

- [`meeting-transcribe`](./skills/meeting-transcribe/README.md) — transcribes
  and diarizes local meeting recordings, matches speakers against enrolled
  voiceprints, and interactively resolves anyone it can't confidently match.
  Also files Zoom `.vtt` exports.

## License

MIT — see [LICENSE](./LICENSE).
