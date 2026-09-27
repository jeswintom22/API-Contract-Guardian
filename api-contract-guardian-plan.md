# API Contract Guardian — Implementation Plan

## Top-Level Overview

A skeleton of the project already exists. The structure is correct and the core
abstractions are sound. The work is to close the gaps so the end-to-end demo
actually runs:

1. **`sample-repo` has no git history** — `setup_demo.sh` must be run to create
   the `main` and `breaking-change` branches that the demo compares.

2. **`guardian/main.py` has import-path bugs** — it is meant to be run as
   `uvicorn main:app` from inside `guardian/`, but imports reference
   `analyzer` and `git_diff` without any path adjustment, and
   `Jinja2Templates(directory="guardian/templates")` uses a path that only
   works if the process CWD is the repo root, not `guardian/`. Both must be
   fixed for `uvicorn main:app` from `guardian/` to work.

3. **No real LLM backend** — the two existing backends are either a manual
   copy-paste stub (`ManualBobBackend`) or a CLI stub with a `None` command
   (`BobCLIBackend`). Neither runs end-to-end automatically. A new
   `DirectLLMBackend` using the `openai` SDK (or the local `bob` API if
   available) must be added so the three parallel subagent tasks actually
   execute and return JSON.

4. **`run_analysis` is sequential** — the task description says the three
   subagent scans must run as visibly parallel concurrent tasks. The
   orchestration loop in `analyzer.py` must switch from a `for` loop to
   `concurrent.futures.ThreadPoolExecutor` (or `asyncio.gather`).

5. **The report is functional but bare** — minor improvements to clearly
   distinguish the three categories and show a "plain diff only showed 1 file
   changed" callout to make the demo point obvious.

6. **No `__init__.py` or `pyproject.toml`** needed — running `uvicorn main:app`
   from inside `guardian/` means relative imports are fine as-is; the path
   fix in sub-task 2 is the only structural change needed.

---

## Sub-Tasks

---

### Sub-Task 1 — Initialize the `sample-repo` git history

**Intent**
The `sample-repo/` directory exists but has no `.git` folder and no branches.
`get_repo_snapshot()` calls `git.Repo(repo_path)` which will raise
`InvalidGitRepositoryError` at runtime without this. `setup_demo.sh` creates
`main` (original `total_amount`) and `breaking-change` (renamed to `total`).

**Expected Outcomes**
- `sample-repo/.git/` exists.
- `git -C sample-repo branch` lists both `main` and `breaking-change`.
- `git -C sample-repo diff main breaking-change` shows only `app/main.py`
  changed.

**Todo List**
1. Run `bash setup_demo.sh` from inside `sample-repo/`. On Windows use
   Git Bash or WSL — the script uses `sed -i` and `git init`.
2. Verify with `git -C sample-repo log --oneline --all` that two commits
   exist on two branches.

**Relevant Context**
- Script: `sample-repo/setup_demo.sh`
- Target files touched by the script: `sample-repo/app/main.py`

**Status**: `[ ] pending`

---

### Sub-Task 2 — Fix `guardian/` import paths and CWD assumptions

**Intent**
`guardian/main.py` must run cleanly with `uvicorn main:app --port 8001` from
inside `guardian/`. Two bugs block this:

- `Jinja2Templates(directory="guardian/templates")` — this path only resolves
  if CWD is the project root. When run from `guardian/`, it should be
  `"templates"`.
- Both `from analyzer import ...` and `from git_diff import ...` work fine
  once CWD is `guardian/` (Python adds CWD to `sys.path` for scripts), but
  the `ManualBobBackend.prompts_dir` default of `"guardian/manual_runs"`
  will create the directory in the wrong place. Change it to `"manual_runs"`.

**Expected Outcomes**
- `cd guardian && uvicorn main:app --port 8001` starts without `ImportError`
  or `TemplateNotFound`.
- Navigating to `http://localhost:8001/` serves the index form.

**Todo List**
1. In `guardian/main.py` change `directory="guardian/templates"` to
   `directory="templates"`.
2. In `guardian/analyzer.py` change the `ManualBobBackend` default
   `prompts_dir="guardian/manual_runs"` to `prompts_dir="manual_runs"`.

**Relevant Context**
- `guardian/main.py` line 9: `Jinja2Templates(directory="guardian/templates")`
- `guardian/analyzer.py` line 118: `prompts_dir: str = "guardian/manual_runs"`

**Status**: `[ ] pending`

---

### Sub-Task 3 — Add `DirectLLMBackend` and wire it as the default

**Intent**
Replace the non-functional stubs with a backend that actually calls an LLM.
The simplest approach that avoids heavy dependencies: use the `openai` Python
SDK pointed at either OpenAI's API or a local compatible endpoint. The backend
builds a single chat completion request from the task's `prompt`, `diff`, and
`files` dict, then parses the JSON response.

The prompt must tell the model to return ONLY the JSON object described in
`SYSTEM_PROMPT` — no markdown fences, no preamble.

**Expected Outcomes**
- `DirectLLMBackend().run(task)` returns a `dict` with a `"findings"` key.
- The default `BACKEND` in `guardian/main.py` is `DirectLLMBackend()`.
- Credentials come from an `OPENAI_API_KEY` environment variable; the app
  prints a clear startup error if it is missing, rather than crashing on the
  first request.
- `guardian/requirements.txt` gains `openai`.

**Todo List**
1. Add `openai` to `guardian/requirements.txt`.
2. In `guardian/analyzer.py`, add `DirectLLMBackend` dataclass:
   - Reads `OPENAI_API_KEY` from env at construction time.
   - `run(task)` assembles a user message: the diff, then each file path +
     content from `task["files"]`, then asks for the JSON report.
   - Calls `openai.chat.completions.create` with `model="gpt-4o-mini"` (cheap,
     fast, sufficient for this task).
   - Strips any markdown fences from the response before `json.loads`.
   - Returns the parsed dict.
3. In `guardian/main.py`, change `BACKEND = ManualBobBackend()` to
   `BACKEND = DirectLLMBackend()`.
4. Add a startup guard: if `OPENAI_API_KEY` is not set, log a warning but
   do not crash — let the user see the error when they hit `/analyze`.

**Relevant Context**
- `guardian/analyzer.py` — `SYSTEM_PROMPT`, `AnalysisBackend` Protocol,
  existing `BobCLIBackend` and `ManualBobBackend` for reference
- `guardian/main.py` line 12: `BACKEND = ManualBobBackend()`

**Status**: `[ ] pending`

---

### Sub-Task 4 — Make the three subagent tasks run in parallel

**Intent**
`run_analysis` currently iterates tasks with a `for` loop — sequential. The
requirement is that the three category scans (frontend, tests, docs) run as
visibly concurrent tasks. Use `concurrent.futures.ThreadPoolExecutor` with
`max_workers=3` to fan out the calls and collect results. Each future maps back
to its task name so errors surface with context.

**Expected Outcomes**
- Log output (or response timing) shows all three LLM calls in flight at the
  same time.
- Any exception in one worker is caught, logged, and the worker returns an
  empty findings list so the other results are not lost.
- The aggregated `findings` list is unchanged from the caller's perspective.

**Todo List**
1. In `guardian/analyzer.py`, import `concurrent.futures`.
2. Replace the `for task in tasks` loop in `run_analysis` with a
   `ThreadPoolExecutor` submit/as_completed pattern.
3. Wrap each worker call in try/except; on failure log the subagent name and
   error, yield `[]` findings for that worker.
4. Preserve the existing `broken / risky / safe` bucketing after collection.

**Relevant Context**
- `guardian/analyzer.py` lines 135–151: `run_analysis` function

**Status**: `[ ] pending`

---

### Sub-Task 5 — Polish the report page for the demo

**Intent**
The report already has the right structure. Two small additions make the demo
point obvious at a glance:

1. A "plain diff callout" — a highlighted box showing "plain `git diff` showed
   1 changed file; Guardian found N impacted consumers" to make the value
   proposition visible without explanation.
2. Each finding card shows the line/snippet that references the broken field,
   not just the file name, so the viewer can see exactly what broke. This
   requires the LLM prompt to include a `line_reference` field in each
   finding, and the report template to render it.

**Expected Outcomes**
- The report page shows the diff-vs-Guardian callout at the top.
- Each BROKEN finding card shows a `line_reference` snippet (e.g.
  `amount: data.total_amount`).
- The page still renders correctly if `line_reference` is absent (optional
  field).

**Todo List**
1. Update `SYSTEM_PROMPT` in `guardian/analyzer.py` to add an optional
   `"line_reference"` field to each finding object in the JSON schema.
2. In `guardian/templates/report.html`, add a callout div at the top of the
   report that shows changed files count vs total findings count.
3. In each finding card, add a `<code>` block that renders
   `f.line_reference` if present.

**Relevant Context**
- `guardian/analyzer.py` lines 37–56: `SYSTEM_PROMPT`
- `guardian/templates/report.html` lines 20–35: finding card markup

**Status**: `[ ] pending`

---

### Sub-Task 6 — End-to-end smoke test and README update

**Intent**
Verify the full flow works: start guardian, submit the form, get back a report
that flags `consumers/frontend_checkout.js`, `tests/test_checkout.py`, and
`sample-repo/README.md` all as BROKEN with a plain-English reason and fix.
Update the root README with the exact commands needed to run the demo.

**Expected Outcomes**
- Running `cd guardian && uvicorn main:app --port 8001` starts cleanly.
- Submitting the form with `repo_path=../sample-repo`, `base_ref=main`,
  `head_ref=breaking-change` returns a report with exactly 3 BROKEN findings.
- Each BROKEN finding names the `total_amount` → `total` rename as the reason.
- Root `README.md` reflects the real one-command setup (including the
  `OPENAI_API_KEY` env var step).

**Todo List**
1. Start the guardian server and hit `/analyze` with the demo parameters.
2. Confirm all three consumers appear as BROKEN in the rendered report.
3. If any consumer is missed or misclassified, tune `SYSTEM_PROMPT` and
   re-run (one category at a time to save coins).
4. Update root `README.md`: add `export OPENAI_API_KEY=...` step and confirm
   the uvicorn command matches `cd guardian && uvicorn main:app --port 8001`.

**Relevant Context**
- `README.md` — current setup instructions
- `guardian/analyzer.py` — `SYSTEM_PROMPT` (tune here if needed)

**Status**: `[ ] pending`
