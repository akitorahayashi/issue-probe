# skills-plugin-py

## Project Overview

A template for a multi-client Agent Skills plugin whose skills are backed by
Python scripts. One repository is one plugin, installable on Claude Code, Codex
CLI, and Antigravity CLI from a shared `skills/` directory. Each skill drives a
standalone stdlib-only Python CLI that prints one JSON document. `example-skill`
is a placeholder, meant to be renamed and replaced.

## Directory Structure

```
plugin/
  example-plugin/                    Distributed plugin — the marketplace `source` target
    .claude-plugin/plugin.json       Claude Code manifest
    .codex-plugin/plugin.json        Codex manifest
    plugin.json                      Antigravity CLI manifest
    skills/
      example-skill/
        SKILL.md                     Drives summarize.py
        scripts/summarize.py         Example CLI — count/sum/min/max/mean
.claude-plugin/marketplace.json      Distribution catalog; git-subdir → plugin/example-plugin
tests/                               pytest process-boundary tests; excluded from the plugin
  conftest.py                        Subprocess CLI runner
  example_skill/                     summarize.py tests, split by concern
pyproject.toml                       Dev-tool configuration only (pytest, ruff, mypy)
Makefile                             make test / fix / lint
```

Only the `plugin/example-plugin/` subtree ships, selected by the `git-subdir`
source in `.claude-plugin/marketplace.json`. Development assets stay at the
repository root and are excluded from the installed plugin. Component
directories (`skills/`, and later `hooks/`, `agents/`, `commands/`, `.mcp.json`)
live at the subtree root, not inside its `.claude-plugin/`. CONTRIBUTING.md
covers the per-client details.

## Testing

Tests live under `tests/`, outside the distributed subtree, one directory per
skill. They assert the CLI process boundary — exit code, stdout/stderr JSON,
written files — not internal composition. `tests/conftest.py` holds the
subprocess runner.

Run `make fix` first, then `make lint` and `make test`.

## Core Concepts

### Stdlib-Only Runtime

Standard library only, Python 3.10+. No third-party import enters
`plugin/**/skills/**/scripts/`, so a skill runs on the user's own `python3` as
installed. The `pyproject.toml` dependencies are dev tools that never ship.

### CLI Contract

One JSON document on stdout. Exit 0 for an affirmative result, 1 for a valid
request with a negative or empty result, 2 for a config or runtime error. Exit 2
prints JSON to stderr carrying an actionable `action`. Failures surface
explicitly, never as a silently degraded result.

## Documentation Responsibilities

- AGENTS.md — source map and invariants. The orientation layer.
- README.md — structure, manifests, install, and customization. The front door.
- CONTRIBUTING.md — development workflow and the distribution boundary in full.
- `skills/<name>/SKILL.md` — agent-facing behavior of that skill.
