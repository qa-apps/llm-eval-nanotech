#!/usr/bin/env python3
"""
DeepEval local HTML report viewer.

Usage:
    python tests/llmEval/show_report.py

Opens a browser-friendly report at http://localhost:8600
"""

import json
import os
import sys
import webbrowser
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread
from typing import Optional


def _find_run_file() -> Optional[Path]:
    deepeval_dir = Path('.deepeval')
    candidates = [
        deepeval_dir / '.latest_run_full.json',
    ]
    # Also look for dated test_run files in .deepeval/
    candidates.extend(sorted(deepeval_dir.glob('test_run_*.json'), reverse=True))
    # Or in DEEPEVAL_RESULTS_FOLDER if set
    results_folder = os.getenv('DEEPEVAL_RESULTS_FOLDER')
    if results_folder:
        rp = Path(results_folder)
        candidates.append(rp / '.latest_run_full.json')
        candidates.extend(sorted(rp.glob('test_run_*.json'), reverse=True))
    for c in candidates:
        if c.exists():
            return c
    return None


def _load_run_data(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _generate_html(data: dict, source_file: str) -> str:
    test_cases = data.get('testCases', [])
    run_timestamp = data.get('timestamp', datetime.now().isoformat())
    total = len(test_cases)
    passed = sum(1 for tc in test_cases if tc.get('success'))
    failed = total - passed

    rows = []
    for tc in test_cases:
        status = 'PASS' if tc.get('success') else 'FAIL'
        status_class = 'pass' if tc.get('success') else 'fail'
        metrics_html = []
        for md in tc.get('metricsData', []):
            m_status = 'pass' if md.get('success') else 'fail'
            metrics_html.append(
                f'<div class="metric {m_status}">'
                f'<strong>{md.get("name", "?")}</strong> '
                f'— score: <code>{md.get("score")}</code> '
                f'(threshold: {md.get("threshold")})<br>'
                f'<span class="reason">{md.get("reason", "")}</span>'
                f'</div>'
            )

        rows.append(
            f'<tr class="{status_class}">'
            f'<td class="status">{status}</td>'
            f'<td><div class="test-name">{tc.get("name", "—")}</div>'
            f'<div class="prompt"><strong>Input:</strong> {tc.get("input", "—")}</div>'
            f'<div class="reply"><strong>Output:</strong> {tc.get("actualOutput", "—")}</div>'
            f'<div class="metrics">{ "".join(metrics_html) }</div></td>'
            f'</tr>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DeepEval Report — {run_timestamp}</title>
<style>
  :root {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }}
  body {{ margin: 0; padding: 2rem; background: #0f172a; color: #e2e8f0; }}
  h1 {{ margin: 0 0 .5rem; }}
  .subtitle {{ color: #94a3b8; margin-bottom: 1.5rem; }}
  .summary {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; }}
  .badge {{ padding: .5rem .9rem; border-radius: .5rem; font-weight: 600; }}
  .badge.total {{ background: #334155; }}
  .badge.pass {{ background: #14532d; color: #86efac; }}
  .badge.fail {{ background: #450a0a; color: #fca5a5; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: .75rem; border-bottom: 1px solid #334155; vertical-align: top; }}
  th {{ color: #94a3b8; font-weight: 500; }}
  tr.pass .status {{ color: #86efac; }}
  tr.fail .status {{ color: #fca5a5; font-weight: 700; }}
  .test-name {{ font-weight: 700; margin-bottom: .35rem; }}
  .prompt, .reply {{ font-size: .92rem; color: #cbd5e1; margin-bottom: .35rem; }}
  .metrics {{ margin-top: .5rem; }}
  .metric {{ padding: .5rem .6rem; border-radius: .4rem; margin-bottom: .35rem; font-size: .88rem; }}
  .metric.pass {{ background: #14532d22; border-left: 3px solid #22c55e; }}
  .metric.fail {{ background: #450a0a22; border-left: 3px solid #ef4444; }}
  .reason {{ color: #94a3b8; display: block; margin-top: .25rem; }}
  code {{ background: #1e293b; padding: .1rem .35rem; border-radius: .3rem; }}
  .empty {{ color: #94a3b8; }}
</style>
</head>
<body>
<h1>DeepEval Run Report</h1>
<div class="subtitle">Source: {source_file} &middot; {run_timestamp}</div>
<div class="summary">
  <div class="badge total">Total: {total}</div>
  <div class="badge pass">Passed: {passed}</div>
  <div class="badge fail">Failed: {failed}</div>
</div>
<table>
  <thead>
    <tr><th style="width:4rem">Status</th><th>Test case</th></tr>
  </thead>
  <tbody>
    {''.join(rows) if rows else '<tr><td colspan="2" class="empty">No test cases found in this run.</td></tr>'}
  </tbody>
</table>
</body>
</html>"""


def _write_and_serve(html: str, port: int = 8600) -> None:
    out_dir = Path(__file__).parent
    out_path = out_dir / 'report.html'
    out_path.write_text(html, encoding='utf-8')

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(out_dir), **kwargs)
        def log_message(self, format: str, *args) -> None:
            pass

    def serve():
        with HTTPServer(('', port), Handler) as httpd:
            httpd.serve_forever()

    t = Thread(target=serve, daemon=True)
    t.start()
    url = f'http://localhost:{port}/report.html'
    print(f'\n  DeepEval report: {url}')
    print('  Press Ctrl+C to stop\n')
    webbrowser.open(url)
    try:
        while True:
            t.join(timeout=1)
    except KeyboardInterrupt:
        print('\n  Stopped.')
        sys.exit(0)


def main() -> int:
    run_file = _find_run_file()
    if not run_file:
        print('No DeepEval run results found.')
        print('Looked in: .deepeval/.latest_run_full.json and test_run_*.json')
        print('Run tests first with RUN_LLM_EVALS=1')
        return 1
    data = _load_run_data(run_file)
    html = _generate_html(data, str(run_file))
    _write_and_serve(html)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
