# API Contract Guardian

Catches breaking API changes across a whole repository — not just the diff
— by reading the full repo tree and finding every real consumer of the
changed API contract: frontend calls, tests, docs, other services.

## How it works

1. You give it two git refs (e.g. `main` and `breaking-change`).
2. It extracts the diff **and** the full file tree of the repo.
3. It fans out three parallel LLM tasks — one for frontend code, one for
   tests, one for docs — each receiving the diff plus only their slice of
   the tree.
4. Each task classifies every consumer as **BROKEN**, **RISKY**, or **SAFE**
   with a plain-English reason and a suggested fix.
5. Results are collected and rendered as a single report page.

## Structure

```
sample-repo/     the demo target — a tiny FastAPI app with 3 consumers
                 (frontend JS call, pytest test, README curl example)
guardian/        the orchestrator — diffs two refs, runs 3 parallel LLM
                 subagent tasks, renders a report page
```

## Quick start

### 1 — Initialize the demo repo (one-time)

```bash
cd sample-repo
bash setup_demo.sh   # creates main + breaking-change branches
```

### 2 — Install dependencies

```bash
cd guardian
pip install -r requirements.txt
```

### 3 — Set your OpenAI API key

```bash
export OPENAI_API_KEY=sk-...        # Linux / macOS / Git Bash
# or on Windows PowerShell:
$env:OPENAI_API_KEY = "sk-..."
```

### 4 — Start the guardian server

```bash
# from inside guardian/
python -m uvicorn main:app --reload
```

Open http://localhost:8000, leave the defaults (`repo_path=../sample-repo`,
`base_ref=main`, `head_ref=breaking-change`), hit **Run analysis**.

The report will show:

| File | Status | Why |
|---|---|---|
| `consumers/frontend_checkout.js` | **BROKEN** | reads `data.total_amount` which no longer exists |
| `tests/test_checkout.py` | **BROKEN** | asserts `"total_amount" in body` |
| `README.md` | **BROKEN** | curl example documents `total_amount` in response |

A plain `git diff` would show **1 changed file**. Guardian finds **3 broken consumers**.

## Backends

`guardian/analyzer.py` ships three backends:

| Backend | When to use |
|---|---|
| `DirectLLMBackend` (default) | Fully automated — needs `OPENAI_API_KEY` |
| `BobCLIBackend` | If you have a Bob headless CLI available |
| `ManualBobBackend` | Copy-paste fallback — writes prompt files to `guardian/manual_runs/` |

To switch backends, change the `BACKEND` line in `guardian/main.py`.
