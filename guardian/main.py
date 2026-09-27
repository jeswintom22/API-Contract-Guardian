import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from analyzer import DirectLLMBackend, run_analysis
from git_diff import get_repo_snapshot

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

app = FastAPI(title="API Contract Guardian")
templates = Jinja2Templates(directory="templates")

BACKEND = DirectLLMBackend()


@app.get("/analyze", response_class=HTMLResponse)
def analyze(request: Request, repo_path: str, base_ref: str = "main", head_ref: str = "HEAD"):
    snapshot = get_repo_snapshot(repo_path, base_ref, head_ref)
    report = run_analysis(snapshot, BACKEND)
    return templates.TemplateResponse(
        request,
        "report.html",
        {"report": report, "base_ref": base_ref, "head_ref": head_ref},
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {})
