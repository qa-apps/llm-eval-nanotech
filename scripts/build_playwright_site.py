#!/usr/bin/env python3
"""Build a static GitHub Pages UI for NanoTech pytest/Playwright results."""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path.cwd()
OUT = ROOT / "gh-pages-site"
EXISTING = ROOT / "gh-pages-existing"
RUN_NUMBER = os.environ.get("RUN_NUMBER", "local")
RUN_URL = os.environ.get("RUN_URL", "")
TIMESTAMP = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def carry_forward() -> list[dict]:
    if EXISTING.exists():
        shutil.copytree(EXISTING, OUT, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    OUT.mkdir(parents=True, exist_ok=True)
    hist = OUT / "playwright" / "history.json"
    if hist.exists():
        try:
            return json.loads(hist.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def collect_cases() -> list[dict]:
    path = ROOT / "test-results" / "junit.xml"
    if not path.exists():
        return []
    root = ET.parse(path).getroot()
    cases = []
    for case in root.iter("testcase"):
        failure = case.find("failure")
        if failure is None:
            failure = case.find("error")
        skipped = case.find("skipped")
        status = "skipped" if skipped is not None else ("failed" if failure is not None else "passed")
        cases.append({
            "name": f"{case.attrib.get('classname', '')}.{case.attrib.get('name', '')}".strip("."),
            "time": case.attrib.get("time", ""),
            "status": status,
            "message": "" if failure is None else (failure.attrib.get("message") or failure.text or ""),
        })
    return cases


def case_rows(cases: list[dict], statuses: set[str]) -> str:
    rows = []
    for case in cases:
        if case["status"] not in statuses:
            continue
        cls = "pass" if case["status"] == "passed" else "fail"
        details = (
            f"<details><summary>failure</summary><pre>{html.escape(case['message'][:5000])}</pre></details>"
            if case.get("message")
            else ""
        )
        rows.append(
            f"<tr><td class='{cls}'>{html.escape(case['status'])}</td>"
            f"<td>{html.escape(case['name'])}{details}</td>"
            f"<td>{html.escape(str(case.get('time', '')))}s</td></tr>"
        )
    return "".join(rows)


def render(run_dir: Path, cases: list[dict]) -> str:
    passed = sum(1 for c in cases if c["status"] == "passed")
    failed = sum(1 for c in cases if c["status"] == "failed")
    skipped = sum(1 for c in cases if c["status"] == "skipped")
    total = len(cases)
    run_link = f'<a href="{html.escape(RUN_URL)}">GitHub Actions run</a>' if RUN_URL else "local run"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>NanoTech Playwright run {html.escape(str(RUN_NUMBER))}</title>
<style>
body{{font:14px/1.45 -apple-system,BlinkMacSystemFont,sans-serif;margin:0 auto;max-width:1180px;padding:24px;color:#1f2328}}
a{{color:#0969da;text-decoration:none}}.meta{{color:#656d76}}.cards{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}}
.card{{border:1px solid #d0d7de;border-radius:6px;padding:12px;background:#f6f8fa}}.value{{font-size:24px;font-weight:700}}
table{{width:100%;border-collapse:collapse;margin-top:16px}}th,td{{padding:8px 10px;border-bottom:1px solid #d8dee4;text-align:left;vertical-align:top}}th{{background:#f6f8fa}}
pre{{white-space:pre-wrap;max-width:860px}}.pass{{color:#1a7f37;font-weight:700}}.fail{{color:#cf222e;font-weight:700}}
</style></head><body>
<p><a href="../../index.html">← all Playwright runs</a></p>
<h1>NanoTech Playwright #{html.escape(str(RUN_NUMBER))}</h1>
<p class="meta">{html.escape(TIMESTAMP)} · {run_link}</p>
<div class="cards"><div class="card"><div>Passed</div><div class="value pass">{passed}</div></div><div class="card"><div>Failed</div><div class="value fail">{failed}</div></div><div class="card"><div>Skipped</div><div class="value">{skipped}</div></div><div class="card"><div>Total</div><div class="value">{total}</div></div></div>
<p class="meta">Failure screenshots, videos, and traces are copied under <code>raw-test-results/</code> when Playwright produces them.</p>
<h2>Failed tests</h2><table><thead><tr><th>Status</th><th>Test</th><th>Time</th></tr></thead><tbody>{case_rows(cases, {'failed'}) or '<tr><td colspan="3">No failed tests.</td></tr>'}</tbody></table>
<h2>Passed tests</h2><table><thead><tr><th>Status</th><th>Test</th><th>Time</th></tr></thead><tbody>{case_rows(cases, {'passed'}) or '<tr><td colspan="3">No passed tests listed.</td></tr>'}</tbody></table>
</body></html>"""


def index(history: list[dict]) -> str:
    rows = []
    for item in sorted(history, key=lambda r: int(r.get("run_number", 0)) if str(r.get("run_number", "")).isdigit() else 0, reverse=True)[:50]:
        rows.append(
            f"<tr><td><a href='runs/{html.escape(str(item.get('run_number')))}/index.html'>#{html.escape(str(item.get('run_number')))}</a></td>"
            f"<td>{html.escape(str(item.get('timestamp', ''))[:19].replace('T', ' '))}</td>"
            f"<td>{item.get('passed', 0)}/{item.get('total', 0)}</td><td>{item.get('failed', 0)}</td></tr>"
        )
    return f"<!doctype html><title>NanoTech Playwright</title><body><h1>NanoTech Playwright</h1><table><thead><tr><th>Run</th><th>Timestamp UTC</th><th>Passed</th><th>Failed</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan=4>No runs yet.</td></tr>'}</tbody></table></body>"


def main() -> int:
    history = carry_forward()
    cases = collect_cases()
    root = OUT / "playwright"
    run_dir = root / "runs" / str(RUN_NUMBER)
    run_dir.mkdir(parents=True, exist_ok=True)
    if Path("test-results").exists():
        shutil.copytree("test-results", run_dir / "raw-test-results", dirs_exist_ok=True)
    (run_dir / "index.html").write_text(render(run_dir, cases), encoding="utf-8")
    record = {
        "run_number": RUN_NUMBER,
        "timestamp": TIMESTAMP,
        "passed": sum(1 for c in cases if c["status"] == "passed"),
        "failed": sum(1 for c in cases if c["status"] == "failed"),
        "total": len(cases),
    }
    history = [h for h in history if str(h.get("run_number")) != str(RUN_NUMBER)]
    history.append(record)
    root.mkdir(parents=True, exist_ok=True)
    (root / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    (root / "index.html").write_text(index(history), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
