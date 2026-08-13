#!/usr/bin/env python3
"""
Measure the searches that back the coverage claims, so nobody counts by hand.

Past investigations wrote counts a person had tallied, and re-verification kept
overturning them: a formatter count of 53 that was 38 once false positives were
removed, a count of 34 that was 26 once deliberate uses were excluded. Those
numbers had already reached an external audience.

So the counts come from here. coverage.json declares each search and the scope it
runs in, this CLI runs them, and the artifacts quote what it recorded. A count
without a scope means nothing, which is why scope is part of the declaration
rather than a footnote.

Re-running reports what moved since the last measurement, so a count that drifted
after a code change is visible instead of quietly stale.

Exit codes:
- 0: every search ran; counts are recorded and the deltas are reported
- 2: coverage.json cannot be read; stderr carries JSON with an "action"
- 4: ripgrep or git failed; stderr relays the message
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CLIError(Exception):
    """An input error carrying an action for the user to fix."""

    def __init__(self, message: str, action: str) -> None:
        super().__init__(message)
        self.message = message
        self.action = action


class ExternalError(Exception):
    """A ripgrep or git invocation that failed, carrying the relayed message."""

    def __init__(self, command: str, message: str) -> None:
        super().__init__(message)
        self.command = command
        self.message = message


def load_coverage(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CLIError(
            f"{path} がありません。",
            "網羅性の検索定義を coverage.json に書いてください。",
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CLIError(f"{path} を JSON として読めません: {error}", "JSON の構文を直してください。") from error
    if not isinstance(document, dict):
        raise CLIError(f"{path} の最上位がオブジェクトではありません。", "オブジェクトに直してください。")

    scope = document.get("scope")
    if not isinstance(scope, list) or not scope or not all(isinstance(entry, str) for entry in scope):
        raise CLIError(
            f"{path} に scope がありません。",
            "検索対象のディレクトリを scope に文字列の配列で並べてください。",
        )
    searches = document.get("searches")
    if not isinstance(searches, list) or not searches:
        raise CLIError(
            f"{path} に searches がありません。",
            "issue に書かれた検索キーワードを searches に並べてください。",
        )
    for index, search in enumerate(searches):
        if not isinstance(search, dict) or not isinstance(search.get("pattern"), str):
            raise CLIError(
                f"{path} の searches[{index}] に pattern がありません。",
                '各検索を {"id": ..., "pattern": ...} の形にしてください。',
            )
        search.setdefault("id", f"S{index + 1}")
    return document


def measure(pattern: str, scope: list[str], globs: list[str], root: Path) -> tuple[int, int]:
    """Count matches and matching files for one search.

    ripgrep exits 1 when nothing matched, which is an answer rather than a failure,
    so only other non-zero codes are relayed as external errors.
    """
    argv = ["rg", "--count-matches", "--no-heading", "--color", "never"]
    for glob in globs:
        argv += ["--glob", glob]
    argv += ["--regexp", pattern, "--", *scope]
    result = subprocess.run(argv, capture_output=True, text=True, cwd=root)
    if result.returncode == 1:
        return 0, 0
    if result.returncode != 0:
        raise ExternalError("rg", result.stderr.strip() or result.stdout.strip())

    matches = 0
    files = 0
    for line in result.stdout.splitlines():
        _, separator, count = line.rpartition(":")
        if not separator or not count.isdigit():
            continue
        matches += int(count)
        files += 1
    return matches, files


def head_sha(root: Path) -> str:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
    if result.returncode != 0:
        raise ExternalError("git", result.stderr.strip())
    return result.stdout.strip()


def run(directory: Path, now: str) -> dict[str, Any]:
    if not directory.is_dir():
        raise CLIError(f"{directory} がありません。", "probe-issue の準備を先に実行してください。")
    path = directory / "coverage.json"
    document = load_coverage(path)

    root = directory.resolve()
    while not (root / ".git").exists() and root != root.parent:
        root = root.parent
    if not (root / ".git").exists():
        raise CLIError(
            f"{directory} を含む git リポジトリが見つかりません。",
            "調査対象リポジトリの中で実行してください。",
        )

    scope: list[str] = document["scope"]
    reported: list[dict[str, Any]] = []
    for search in document["searches"]:
        globs = search.get("globs") or []
        previous = search.get("count")
        matches, files = measure(search["pattern"], scope, globs, root)
        search["count"] = matches
        search["files"] = files
        entry: dict[str, Any] = {
            "id": search["id"],
            "pattern": search["pattern"],
            "count": matches,
            "files": files,
        }
        if isinstance(previous, int) and previous != matches:
            entry["previous"] = previous
            entry["delta"] = matches - previous
        reported.append(entry)

    document["measuredAt"] = now
    document["codeSha"] = head_sha(root)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "measuredAt": document["measuredAt"],
        "codeSha": document["codeSha"],
        "scope": scope,
        "searches": reported,
        "changed": [entry["id"] for entry in reported if "previous" in entry],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the declared searches and record their counts.")
    parser.add_argument("directory", help="Workspace directory, for example .tmp/issue-probes/321")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    try:
        document = run(Path(args.directory), now)
    except CLIError as error:
        json.dump({"error": error.message, "action": error.action}, sys.stderr, ensure_ascii=False, indent=2)
        sys.stderr.write("\n")
        return 2
    except ExternalError as error:
        action = f"{error.command} の失敗を解消してから再実行してください。"
        json.dump({"error": error.message, "action": action}, sys.stderr, ensure_ascii=False, indent=2)
        sys.stderr.write("\n")
        return 4
    json.dump(document, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
