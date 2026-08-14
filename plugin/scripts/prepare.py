#!/usr/bin/env python3
"""
Open a workspace for one investigation and pin down what is being investigated.

The request and the code rarely live together: a ticket filed in a documents
repository asks for an investigation of an application repository. So two
identities are resolved and recorded separately — the issue repository, which
`--repo` names and which defaults to this checkout's origin, and the code
repository, which is always this checkout. The workspace follows the code,
because that is what the evidence points at.

The commit is recorded at the same moment. Every later claim is a claim about
that commit, and the checks compare it against HEAD so a stale list is visible
rather than assumed current.

Exit codes:
- 0: the workspace is ready; the returned fields are what the caller gates on
- 2: input error; stderr carries JSON with an "action"
- 4: gh or git failed; stderr relays the message
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ISSUE_FIELDS = "number,title,body,url,state,labels,author,comments"
REMOTE_PATTERN = re.compile(r"(?:[:/])([^/:]+/[^/]+?)(?:\.git)?$")


class CLIError(Exception):
    """An input error carrying an action for the user to fix."""

    def __init__(self, message: str, action: str) -> None:
        super().__init__(message)
        self.message = message
        self.action = action


class ExternalError(Exception):
    """A gh or git invocation that failed, carrying the relayed message."""

    def __init__(self, command: str, message: str) -> None:
        super().__init__(message)
        self.command = command
        self.message = message


def run_command(argv: list[str]) -> str:
    result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode != 0:
        raise ExternalError(argv[0], result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def normalize_remote(url: str) -> str:
    """Reduce any remote URL form to owner/name.

    ssh, https, and scp-like forms all name the same repository, and the workspace
    records one identity for it.
    """
    match = REMOTE_PATTERN.search(url.strip())
    if match is None:
        raise CLIError(
            f"リモートURLからリポジトリ名を読み取れません: {url}",
            "owner/name の形で --repo を指定してください。",
        )
    return match.group(1)


def code_repository() -> str:
    return normalize_remote(run_command(["git", "remote", "get-url", "origin"]))


def repository_root() -> Path:
    return Path(run_command(["git", "rev-parse", "--show-toplevel"]))


def fetch_issue(issue: int, repo: str) -> dict[str, Any]:
    raw = run_command(["gh", "issue", "view", str(issue), "--repo", repo, "--json", ISSUE_FIELDS])
    document: dict[str, Any] = json.loads(raw)
    document["repo"] = repo
    return document


def write_workspace(root: Path, issue: int, document: dict[str, Any]) -> Path:
    directory = root / ".tmp" / "issue-probes" / str(issue)
    directory.mkdir(parents=True, exist_ok=True)

    gitignore = root / ".tmp" / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")

    payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    (directory / "issue.json").write_text(payload, encoding="utf-8")
    return directory


def run(issue: int, repo: str | None) -> dict[str, Any]:
    if issue < 1:
        raise CLIError(f"issue番号が {issue} です。", "1以上の整数を渡してください。")
    root = repository_root()
    code_repo = code_repository()
    issue_repo = repo or code_repo
    document = fetch_issue(issue, issue_repo)
    directory = write_workspace(root, issue, document)
    code_sha = run_command(["git", "rev-parse", "HEAD"])

    return {
        "dir": str(directory),
        "issue": document.get("number", issue),
        "title": document.get("title", ""),
        "state": document.get("state", ""),
        "issueRepo": issue_repo,
        "codeRepo": code_repo,
        "codeSha": code_sha,
        "labels": [label.get("name", "") for label in document.get("labels", [])],
        "commentCount": len(document.get("comments", [])),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open a workspace for one issue investigation.")
    parser.add_argument("issue", type=int, help="Issue number, for example 321")
    parser.add_argument(
        "--repo",
        help="Repository holding the issue as owner/name. Defaults to this checkout's origin.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        document = run(args.issue, args.repo)
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
