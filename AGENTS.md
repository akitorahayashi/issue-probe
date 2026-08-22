# issue-probe

## Purpose

Turn an investigation request written in a GitHub issue into hand-off artifacts:
one canonical findings.md that carries both the list and its evidence, the
paste-ready TSV derived from it for the shared spreadsheet that tracks the same
investigation across platforms, and a comment draft that reports the result back
on the issue. The plugin never writes outward; a person pastes and posts.

```text
probe-issue ──→ findings.md + issue-comment.md ──→ export-items ──→ paste.tsv ──→ human pastes
                    │
                    ├── verify-items (optional) ──→ findings.md updated + verdicts.md
                    └── withdraw-items ───────────→ named items retired
```

## Architecture

The repository root is the marketplace root; `plugin/` is the plugin root. This
is a Claude Code and Codex plugin. Claude Code can use the bundled agents; Codex
uses available built-in or configured subagents. When delegation is unavailable,
the entry skill performs the same role sequentially in its main session.

| Component | Name | Responsibility |
|---|---|---|
| Entry skill | probe-issue | Read the issue, fix the coverage contract, fan out investigators, assemble findings.md, draft the issue comment |
| Entry skill | verify-items | Re-verify existing items by refutation and record verdicts |
| Entry skill | withdraw-items | Retire named items without renumbering |
| Entry skill | export-items | Derive the sheet paste from findings.md |
| Judgment skill | probe-workspace | Structure, canonical files, the findings.md heading contract, IDs, freshness |
| Judgment skill | row-style | How a spreadsheet cell is written for a mixed engineering and business audience |
| Agent | issue-investigator | Investigate one axis and report its item sections |
| Agent | item-verifier | Refute assigned items and report its verdicts |

Delegated investigators and verifiers write no files. The entry skill's main
writes every artifact, which is how one-writer-per-file is kept: the unit of
parallelism is the investigation axis, so main is the only writer that can be
single.

Shared runtime scripts live under `plugin/scripts/`. CLIs own every side effect
(gh, git, ripgrep, filesystem); libraries stay pure.

## Artifacts

Every runtime artifact lives under `.tmp/issue-probes/<issue>/` in the
repository whose code is being investigated. The issue itself may live in a
different repository; the workspace still follows the code.

- `findings.md` is the only canonical file. One item is one
  `### <番号> [<リスク度>] <項目名>` section whose labelled fields are the sheet row
  and whose `#### 根拠` subsection is the evidence
- `paste.tsv` is derived by `export_items.py` and rewritten on every run
- `coverage.json` records the search definitions and the counts `count_hits.py` measured
- `verdicts.md` is the append-only record of re-verification and withdrawal rounds
- `issue-comment.md` is the outbound report draft

`plugin/scripts/columns.py` holds the sheet's column layout for every
investigation. A workspace declares no layout of its own.

Item numbers are never renumbered and never reused. A pasted spreadsheet row
keeps its position, so compacting numbers would desynchronize the transcript. A
gap below `nextItem` must carry a `delete` verdict, because the section that
stated the claim is gone and the verdict is the only remaining record of it.

## Repository Conventions

Skill documents, agent definitions, templates, and investigation artifacts are
Japanese. Repository engineering documentation, script docstrings, and test
names are English.

The plugin identity lives in `plugin/.claude-plugin/plugin.json` and
`plugin/.codex-plugin/plugin.json`. Runtime code
uses only the Python standard library; development dependencies live in
pyproject.toml.

Run `make fix` before `make lint`. Validate both the marketplace root and the
plugin root after component changes.

## Documentation Responsibilities

- AGENTS.md — source map and invariants; the orientation layer
- README.md — what the plugin does, its components, and how to install it
- CONTRIBUTING.md — development workflow, CLI contract, distribution boundary
- `plugin/skills/<name>/SKILL.md` — that skill's behavior for the agent
