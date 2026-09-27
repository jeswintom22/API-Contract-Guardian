"""
Core analysis logic: turns a RepoSnapshot into a structured breaking-
change report by delegating reasoning to an LLM.

Three backends are available:
  1. DirectLLMBackend (default) — calls the OpenAI API directly using
     the OPENAI_API_KEY environment variable. Runs fully automated.
  2. BobCLIBackend   — shells out to a Bob CLI if available.
  3. ManualBobBackend — writes prompt files for manual copy-paste.
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from git_diff import RepoSnapshot

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are API Contract Guardian, a breaking-change detector.
You are given (1) a diff and (2) the full contents of every other file in
the repository. Do not limit yourself to the diffed lines: search the full
tree for every place that calls, imports, tests, or documents the changed
code, even indirectly (frontend fetch calls, test assertions, README/curl
examples, other services). For each one, classify it as BROKEN, RISKY, or
SAFE, explain why in one sentence, and suggest a concrete fix. Also include
the exact line or snippet from the file that references the changed API
field.

Respond ONLY with valid JSON in this exact shape, no markdown fences, no
extra text before or after:
{
  "summary": "one sentence describing what changed",
  "findings": [
    {
      "file": "path/to/file",
      "status": "BROKEN" | "RISKY" | "SAFE",
      "reason": "one sentence",
      "suggested_fix": "one sentence",
      "line_reference": "the exact line or snippet from the file that references the broken field (optional)"
    }
  ]
}"""


def build_subagent_tasks(snapshot: RepoSnapshot) -> list[dict]:
    """
    Splits the full-tree scan into parallel subagent tasks by consumer
    category, so a larger repo doesn't need one slow sequential pass.
    Each task gets the diff plus only the files in its own category —
    smaller context per call, and the three scans run independently.
    """
    categories = {
        "frontend_consumers": lambda p: p.endswith((".js", ".jsx", ".ts", ".tsx")),
        "tests": lambda p: "test" in p.lower(),
        "docs": lambda p: p.lower().endswith(".md"),
    }

    tasks = []
    for name, matcher in categories.items():
        files = {p: c for p, c in snapshot.full_tree.items() if matcher(p)}
        if not files:
            continue
        tasks.append(
            {
                "subagent": name,
                "prompt": SYSTEM_PROMPT,
                "diff": snapshot.diff_text,
                "files": files,
            }
        )
    return tasks


class AnalysisBackend(Protocol):
    def run(self, task: dict) -> dict: ...


@dataclass
class DirectLLMBackend:
    """Calls the OpenAI API directly. Reads OPENAI_API_KEY from the
    environment. Uses gpt-4o-mini for a good cost/quality balance."""

    model: str = "gpt-4o-mini"
    api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))

    def run(self, task: dict) -> dict:
        import openai  # lazy import so missing dep doesn't break other backends

        if not self.api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. "
                "Export it before starting the server: export OPENAI_API_KEY=sk-..."
            )

        # Build the user message: diff first, then each file's content
        parts = [
            f"## Git diff\n```diff\n{task['diff']}\n```\n",
        ]
        for path, content in task["files"].items():
            parts.append(f"## File: {path}\n```\n{content}\n```\n")
        parts.append(
            "\nAnalyze the files above against the diff and return ONLY the JSON report "
            "described in the system prompt. No markdown fences, no extra text."
        )
        user_message = "\n".join(parts)

        client = openai.OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": task["prompt"]},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if the model wraps its output anyway
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)


@dataclass
class BobCLIBackend:
    """Shells out to Bob's CLI. Adjust `command` once you've confirmed
    the actual invocation your plan supports."""

    working_dir: str
    command: list[str] = None  # e.g. ["bob", "agent", "run", "--stdin-json", "--format", "json"]

    def run(self, task: dict) -> dict:
        result = subprocess.run(
            self.command,
            input=json.dumps(task),
            capture_output=True,
            text=True,
            cwd=self.working_dir,
            timeout=120,
        )
        return json.loads(result.stdout)


@dataclass
class ManualBobBackend:
    """Fallback: writes each subagent task to a prompt file for you to
    paste into the Bob IDE by hand, and reads the reply back from a
    matching response file once you paste Bob's JSON output there."""

    prompts_dir: str = "manual_runs"

    def run(self, task: dict) -> dict:
        Path(self.prompts_dir).mkdir(parents=True, exist_ok=True)
        prompt_path = Path(self.prompts_dir) / f"{task['subagent']}.prompt.json"
        response_path = Path(self.prompts_dir) / f"{task['subagent']}.response.json"

        prompt_path.write_text(json.dumps(task, indent=2))

        if not response_path.exists():
            raise FileNotFoundError(
                f"Paste Bob's reply into {response_path} then re-run. "
                f"Prompt is ready at {prompt_path}."
            )
        return json.loads(response_path.read_text())


def _run_task(backend: AnalysisBackend, task: dict) -> list[dict]:
    """Worker: run one subagent task and return its findings list."""
    try:
        logger.info("Subagent [%s] started", task["subagent"])
        result = backend.run(task)
        findings = result.get("findings", [])
        logger.info("Subagent [%s] finished — %d findings", task["subagent"], len(findings))
        return findings
    except Exception as exc:
        logger.error("Subagent [%s] failed: %s", task["subagent"], exc)
        return []


def run_analysis(snapshot: RepoSnapshot, backend: AnalysisBackend) -> dict:
    tasks = build_subagent_tasks(snapshot)

    # Fan out all category scans in parallel — each runs as an independent worker
    all_findings: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks) or 1) as pool:
        futures = {pool.submit(_run_task, backend, task): task["subagent"] for task in tasks}
        for future in concurrent.futures.as_completed(futures):
            all_findings.extend(future.result())

    broken = [f for f in all_findings if f["status"] == "BROKEN"]
    risky  = [f for f in all_findings if f["status"] == "RISKY"]
    safe   = [f for f in all_findings if f["status"] == "SAFE"]

    return {
        "changed_files": snapshot.changed_files,
        "broken": broken,
        "risky": risky,
        "safe": safe,
        "total_findings": len(all_findings),
    }
