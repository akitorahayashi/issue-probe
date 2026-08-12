# Contributing

This repository is a Claude Code plugin whose skills are backed by Python
scripts. User-facing documentation is in [README.md](README.md); the source map
and invariants are in [AGENTS.md](AGENTS.md). This guide covers the development
workflow.

## Runtime constraint

The shared CLIs run on the plugin user's own `python3`. Dependencies are the
standard library only. No third-party import enters `plugin/scripts/`. The
dependencies declared in `pyproject.toml` are development tools and never ship
as a runtime requirement.

The supported runtime floor is Python 3.10 (`requires-python`), and ruff and
mypy target `py310`.

Beyond python3, the workflow expects `gh` authenticated with the `repo` scope,
`git`, and `ripgrep`. A skill that needs one of these declares it in its
`compatibility` frontmatter so the requirement is visible before the skill runs.

## Environment

Development uses [uv](https://docs.astral.sh/uv/). `.python-version` pins the
development interpreter to 3.12, which affects only the uv-managed `.venv`, not
the runtime of an installed plugin. `uv run` syncs the `dev` dependency group
from `uv.lock` automatically, so no separate install step is needed.

## Tasks

The `Makefile` collects the common commands.

- `make test` runs the test suite with pytest.
- `make fix` applies ruff formatting and autofixes.
- `make lint` runs ruff format in check mode, ruff check, and mypy.

`make fix` is the pass to run before committing; `make lint` is the verification
pass. Run `make fix` before `make lint`.

## Code style

Formatting and linting are handled by ruff. Type checking is handled by mypy over
`plugin/scripts` and `tests`. Scripts are fully type-annotated, and mypy is
expected to report no problems.

Avoid silent fallbacks. Configuration and runtime problems surface as explicit
errors carrying a user-actionable `action`, not a degraded result.

CLIs own the side effects — `gh`, `git`, `ripgrep`, and every filesystem write.
Libraries stay pure: they parse, validate, and render, and they raise instead of
exiting. A library module carries no shebang and is not executable.

## Tests

Tests live outside the plugin, at the repository root under `tests/`, as pytest
functions split by CLI into directories. They assert each CLI's process boundary
(exit code, the stdout and stderr JSON, any written files), not internal
functions.

`tests/conftest.py` provides subprocess runners that invoke a CLI with the given
arguments, plus fixtures that build a workspace under `tmp_path`. Expected values
come from hand-written fixtures, never from the code under test.

Enumerate matrix cases with `@pytest.mark.parametrize`, and keep any temporary
state in `tmp_path`.

The highest-value tests are the ones that stop a transfer accident: a cell
carrying a tab or a newline, a row with the wrong column count, a header that
drifted from `schema.json`, or a duplicated item ID. Each of those must fail the
check before anyone pastes into the shared sheet.

## CLI contract

Each CLI prints one JSON document on stdout and uses meaningful exit codes.

| Exit | Meaning |
|---|---|
| 0 | Success |
| 1 | A valid request whose result is negative — the check did not hold, or nothing matched |
| 2 | Input error. stderr carries JSON with an `error` and an actionable `action` |
| 4 | An external command (`gh`, `git`, `ripgrep`) failed. stderr relays its message |

Exit 3 is deliberately unused so the families stay distinct: 1 is about content,
2 is about how the CLI was called, 4 is about the outside world.

Checks do not fail fast. One run reports every problem it found, so the caller
can fix them in a single pass.

There is no `--json` flag; stdout is always JSON, always with
`ensure_ascii=False` so Japanese content stays readable. Subcommands are not
used: each CLI takes positional arguments plus, at most, a small boolean flag,
and `main(argv) -> int` dispatches inside.

## Distribution boundary

The repository root is the marketplace root for Claude Code. The marketplace
manifest at `.claude-plugin/marketplace.json` points to `./plugin`.

The `plugin/` directory is the plugin root. Component directories such as
`skills/`, `agents/`, and `scripts/` live beside the plugin manifest at
`.claude-plugin/plugin.json`; Claude Code does not load components nested inside
the manifest directory. Development assets at the repository root do not enter
the installable plugin.
