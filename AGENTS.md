# issue-probe

## Purpose

Turn an investigation request written in a GitHub issue into two hand-off
artifacts: a paste-ready list for the shared spreadsheet that tracks the same
investigation across platforms, and a comment draft that reports the result back
on the issue. The plugin never writes outward; a person pastes and posts.

```text
probe-issue ──→ findings/ + report.tsv + issue-comment.md ──→ human pastes and posts
                    │
                    ├── verify-items (optional) ──→ artifacts updated + verdicts.md
                    └── withdraw-items ───────────→ named items retired
```

## Architecture

The repository root is the marketplace root; `plugin/` is the plugin root. This
is a Claude Code plugin only; no Codex or Antigravity manifests exist.

| Component | Name | Responsibility |
|---|---|---|
| Entry skill | probe-issue | Read the issue, fix the contracts, fan out investigators, assemble report.tsv, draft the issue comment |
| Entry skill | verify-items | Re-verify existing items by refutation and record verdicts |
| Entry skill | withdraw-items | Retire named items without renumbering |
| Judgment skill | probe-workspace | Structure, canonical files, editing responsibility, IDs, freshness |
| Judgment skill | row-style | How a spreadsheet cell is written for a mixed engineering and business audience |
| Agent | issue-investigator | Investigate one axis and write its evidence file |
| Agent | item-verifier | Refute assigned items and write its verdict file |

Shared runtime scripts live under `plugin/scripts/`. CLIs own every side effect
(gh, git, ripgrep, filesystem); libraries stay pure.

## Artifacts

Every runtime artifact lives under `.tmp/issue-probes/<issue>/` in the
repository whose code is being investigated. The issue itself may live in a
different repository; the workspace still follows the code.

- `report.tsv` is the canonical list. Its first column is the immutable item ID
- `findings.md` plus `findings/<axis>.md` carry the evidence. One writer per file
- `schema.json` is the spreadsheet column contract that `check_rows.py` enforces
- `coverage.json` records the search definitions and the counts `count_hits.py` measured
- `verdicts.md` is the append-only record of re-verification rounds
- `issue-comment.md` is the outbound report draft

Item numbers are never renumbered and never reused. A pasted spreadsheet row
keeps its position, so compacting numbers would desynchronize the transcript.

## Repository Conventions

Skill documents, agent definitions, templates, and investigation artifacts are
Japanese. Repository engineering documentation, script docstrings, and test
names are English.

The plugin version lives in `plugin/.claude-plugin/plugin.json`. Runtime code
uses only the Python standard library; development dependencies live in
pyproject.toml.

Run `make fix` before `make lint`. Validate both the marketplace root and the
plugin root after component changes.

## Documentation Responsibilities

- AGENTS.md — source map and invariants; the orientation layer
- README.md — what the plugin does, its components, and how to install it
- CONTRIBUTING.md — development workflow, CLI contract, distribution boundary
- `plugin/skills/<name>/SKILL.md` — that skill's behavior for the agent
