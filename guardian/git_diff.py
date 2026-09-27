"""
Extracts a diff between two refs of a target repo, plus the full
repo file tree at the target ref. This is what feeds Bob's
document-understanding step: not just the diff, but everything
around it, so it can trace real consumers of the changed contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from git import Repo


@dataclass
class RepoSnapshot:
    diff_text: str
    changed_files: list[str]
    full_tree: dict[str, str] = field(default_factory=dict)  # path -> file content


# Skip binary/noise files when building the full-tree context sent to Bob.
SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".lock", ".pyc"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}


def get_repo_snapshot(repo_path: str, base_ref: str, head_ref: str) -> RepoSnapshot:
    repo = Repo(repo_path)

    diff_text = repo.git.diff(base_ref, head_ref)
    changed_files = repo.git.diff(base_ref, head_ref, name_only=True).splitlines()

    # Full tree at head_ref — this is the extra context a plain `git diff`
    # never gives you, and it's what lets the analysis catch consumers
    # far away from the changed lines (docs, tests, frontend calls).
    full_tree: dict[str, str] = {}
    root = Path(repo_path)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in SKIP_EXTENSIONS:
            continue
        try:
            full_tree[str(path.relative_to(root))] = path.read_text(errors="ignore")
        except (UnicodeDecodeError, OSError):
            continue

    return RepoSnapshot(diff_text=diff_text, changed_files=changed_files, full_tree=full_tree)
