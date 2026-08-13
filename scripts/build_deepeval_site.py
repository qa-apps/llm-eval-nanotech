#!/usr/bin/env python3
"""Build a GitHub Pages dashboard for DeepEval results."""

from __future__ import annotations

import html
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.cwd()
DEEPEVAL_DIR = ROOT / ".deepeval"
OUT = ROOT / "gh-pages-site"
EXISTING = ROOT / "gh-pages-existing"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest_run_file() -> Path | None:
    candidates = [DEEPEVAL_DIR / ".latest_run_full.json"]
    candidates.extend(sorted(DEEPEVAL_DIR.glob("test_run_*.json"), reverse=True))
    for path in candidates:
        if path.exists():
            return path
    return None


def _summary(data: dict[str, Any]) -> dict[str, Any]:
    cases = data.get("testCases") or []
    total = len(cases)
    passed = sum(1 for case in cases if case.get("success"))
    failed = total - passed
    metrics = []
    for case in cases:
        for metric in case.get("metricsData") or []:
            metrics.append(metric)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "metric_total": len(metrics),
        "metric_passed": sum(1 for metric in metrics if metric.get("success")),
        "metric_failed": sum(1 for metric in metrics if not metric.get("success")),
        "run_duration": data.get("runDuration"),
    }


def _metric_card(metric: dict[str, Any]) -> str:
    ok = bool(metric.get("success"))
    cls = "pass" if ok else "fail"
    score = metric.get("score")
    threshold = metric.get("threshold")
    reason = html.escape(str(metric.get("reason") or ""))
    name = html.escape(str(metric.get("name") or "Metric"))
    model = html.escape(str(metric.get("evaluationModel") or ""))
    return (
        f'<div class="metric {cls}">'
        f'<div class="metric-head"><strong>{name}</strong><span>{score} / {threshold}</span></div>'
        f'<div class="metric-model">{model}</div>'
        f'<p>{reason}</p>'
        "</div>"
    )


def _case_row(case: dict[str, Any]) -> str:
    ok = bool(case.get("success"))
    cls = "pass" if ok else "fail"
    status = "PASS" if ok else "FAIL"
    name = html.escape(str(case.get("name") or "DeepEval test case"))
    prompt = html.escape(str(case.get("input") or ""))
    output = html.escape(str(case.get("actualOutput") or ""))
    metrics = "".join(_metric_card(m) for m in (case.get("metricsData") or []))
    return (
        f'<article class="case {cls}">'
        f'<div class="case-status">{status}</div>'
        f'<div class="case-body"><h3>{name}</h3>'
        f'<div class="io"><span>Input</span><p>{prompt}</p></div>'
        f'<div class="io"><span>Output</span><p>{output}</p></div>'
        f'<div class="metrics">{metrics}</div></div>'
        "</article>"
    )


def _render(data: dict[str, Any], source: str, run_number: str, run_url: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary = _summary(data)
    cases = data.get("testCases") or []
    status = "FAILED" if summary["failed"] else ("PASSED" if summary["total"] else "NO RESULTS")
    rows = "".join(_case_row(case) for case in cases)
    if not rows:
        rows = '<div class="empty">No DeepEval test cases were found in this run.</div>'
    failed_cls = "bad" if summary["failed"] else "good"
    run_link = f'<a href="{html.escape(run_url)}">GitHub Actions run</a>' if run_url else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DeepEval UI - run {html.escape(run_number)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg:#f7f8fb; --panel:#ffffff; --text:#18202f; --muted:#657084;
      --border:#d7dce5; --good:#0f7b3a; --bad:#b42318; --accent:#2457d6;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Arial, sans-serif; background:var(--bg); color:var(--text); }}
    header {{ padding:28px clamp(16px, 4vw, 48px) 18px; border-bottom:1px solid var(--border); background:#fff; }}
    .kicker {{ font-size:12px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); font-weight:700; }}
    h1 {{ margin:6px 0 8px; font-size:clamp(26px, 4vw, 42px); letter-spacing:0; }}
    .meta {{ color:var(--muted); display:flex; gap:14px; flex-wrap:wrap; font-size:14px; }}
    .meta a {{ color:var(--accent); text-decoration:none; font-weight:700; }}
    main {{ width:min(1180px, calc(100vw - 28px)); margin:22px auto 48px; }}
    .summary {{ display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:10px; margin-bottom:18px; }}
    .tile {{ background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:14px; min-height:84px; }}
    .tile span {{ display:block; color:var(--muted); font-size:12px; text-transform:uppercase; font-weight:700; }}
    .tile strong {{ display:block; margin-top:7px; font-size:28px; }}
    .tile .good {{ color:var(--good); }}
    .tile .bad {{ color:var(--bad); }}
    .case {{ display:grid; grid-template-columns:84px minmax(0,1fr); gap:14px; background:#fff; border:1px solid var(--border); border-radius:8px; padding:14px; margin-bottom:12px; }}
    .case-status {{ font-weight:800; color:#fff; border-radius:6px; display:flex; align-items:center; justify-content:center; min-height:64px; }}
    .case.pass .case-status {{ background:var(--good); }}
    .case.fail .case-status {{ background:var(--bad); }}
    h3 {{ margin:0 0 10px; font-size:17px; }}
    .io {{ border:1px solid var(--border); border-radius:6px; padding:10px; margin:8px 0; background:#fbfcfe; }}
    .io span, .metric-model {{ display:block; color:var(--muted); font-size:12px; font-weight:700; text-transform:uppercase; }}
    .io p, .metric p {{ margin:5px 0 0; white-space:pre-wrap; line-height:1.45; }}
    .metrics {{ display:grid; gap:8px; margin-top:10px; }}
    .metric {{ border-left:4px solid var(--border); background:#fbfcfe; border-radius:6px; padding:10px 12px; }}
    .metric.pass {{ border-left-color:var(--good); }}
    .metric.fail {{ border-left-color:var(--bad); }}
    .metric-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
    .metric-head span {{ font-family:ui-monospace, SFMono-Regular, Menlo, monospace; color:var(--muted); }}
    .empty {{ background:#fff; border:1px solid var(--border); border-radius:8px; padding:18px; color:var(--muted); }}
    @media (max-width:760px) {{
      .summary {{ grid-template-columns:repeat(2, minmax(0, 1fr)); }}
      .case {{ grid-template-columns:1fr; }}
      .case-status {{ min-height:38px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="kicker">NanoTech Hub LLM Evaluation</div>
    <h1>DeepEval Run {html.escape(run_number)} - <span class="{failed_cls}">{status}</span></h1>
    <div class="meta"><span>Built {now}</span><span>Source: {html.escape(source)}</span>{run_link}</div>
  </header>
  <main>
    <section class="summary">
      <div class="tile"><span>Tests</span><strong>{summary["total"]}</strong></div>
      <div class="tile"><span>Passed</span><strong class="good">{summary["passed"]}</strong></div>
      <div class="tile"><span>Failed</span><strong class="bad">{summary["failed"]}</strong></div>
      <div class="tile"><span>Metrics</span><strong>{summary["metric_total"]}</strong></div>
      <div class="tile"><span>Duration</span><strong>{summary["run_duration"] or "n/a"}</strong></div>
    </section>
    {rows}
  </main>
</body>
</html>
"""


def main() -> int:
    if EXISTING.exists():
        shutil.copytree(EXISTING, OUT, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    OUT.mkdir(parents=True, exist_ok=True)
    run_number = os.environ.get("RUN_NUMBER", "local")
    run_url = os.environ.get("RUN_URL", "")
    run_file = _latest_run_file()
    data = _load_json(run_file) if run_file else {}
    source = str(run_file) if run_file else "missing .deepeval result"
    run_dir = OUT / "deepeval" / "runs" / str(run_number)
    run_dir.mkdir(parents=True, exist_ok=True)
    html_text = _render(data, source, str(run_number), run_url)
    (run_dir / "index.html").write_text(html_text, encoding="utf-8")
    (OUT / "deepeval").mkdir(parents=True, exist_ok=True)
    (OUT / "deepeval" / "index.html").write_text(
        '<!doctype html><meta http-equiv="refresh" content="0; url=runs/{0}/">'.format(html.escape(str(run_number))),
        encoding="utf-8",
    )
    summary = {"run_number": run_number, "source": source, **_summary(data)}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Built DeepEval UI at {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
