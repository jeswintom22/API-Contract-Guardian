"""
Quick smoke test for the full pipeline using a mock LLM backend.
Run from inside guardian/: python test_pipeline.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from git_diff import get_repo_snapshot
from analyzer import build_subagent_tasks, run_analysis


class MockLLM:
    RESPONSES = {
        "frontend_consumers": {
            "findings": [{
                "file": "consumers/frontend_checkout.js",
                "status": "BROKEN",
                "reason": "Reads data.total_amount which was renamed to data.total in the API response.",
                "suggested_fix": "Change data.total_amount to data.total on line 10.",
                "line_reference": "amount: data.total_amount,",
            }]
        },
        "tests": {
            "findings": [{
                "file": "tests/test_checkout.py",
                "status": "BROKEN",
                "reason": 'Asserts "total_amount" in body but the field was renamed to "total".',
                "suggested_fix": 'Change assert "total_amount" in body to assert "total" in body.',
                "line_reference": 'assert "total_amount" in body',
            }]
        },
        "docs": {
            "findings": [{
                "file": "README.md",
                "status": "BROKEN",
                "reason": "Curl example documents total_amount in the expected response, which no longer exists.",
                "suggested_fix": "Update the curl example comment to show total instead of total_amount.",
                "line_reference": '#   "total_amount": 42.50,',
            }]
        },
    }

    def run(self, task: dict) -> dict:
        return self.RESPONSES[task["subagent"]]


if __name__ == "__main__":
    snap = get_repo_snapshot("../sample-repo", "main", "breaking-change")
    print("Changed files :", snap.changed_files)
    print("Full tree     :", list(snap.full_tree.keys()))

    tasks = build_subagent_tasks(snap)
    print("Subagent tasks:", [t["subagent"] for t in tasks])
    print()

    report = run_analysis(snap, MockLLM())
    print(f"Total findings : {report['total_findings']}")
    print(f"BROKEN : {len(report['broken'])}  RISKY : {len(report['risky'])}  SAFE : {len(report['safe'])}")
    print()

    for f in report["broken"]:
        print(f"  BROKEN  {f['file']}")
        print(f"    Reason : {f['reason']}")
        print(f"    Fix    : {f['suggested_fix']}")
        print(f"    Line   : {f.get('line_reference', '')}")
        print()

    assert len(report["broken"]) == 3, f"Expected 3 BROKEN, got {len(report['broken'])}"
    files = {f["file"] for f in report["broken"]}
    assert "consumers/frontend_checkout.js" in files
    assert "tests/test_checkout.py" in files
    assert "README.md" in files
    print("All assertions passed.")
