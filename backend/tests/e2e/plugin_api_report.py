"""Pytest plugin that captures API request/response details and generates an HTML report.

Usage: automatically loaded via conftest.py.
Output: e2e-api-report.html in the backend directory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any

import pytest


@dataclass
class ApiCall:
    """Single API request/response pair."""

    method: str = ""
    path: str = ""
    query_params: dict[str, Any] = field(default_factory=dict)
    request_headers: dict[str, str] = field(default_factory=dict)
    request_body: Any = None
    status_code: int = 0
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: Any = None


@dataclass
class TestRecord:
    """All API calls made during a single test."""

    module: str = ""
    class_name: str = ""
    test_name: str = ""
    outcome: str = ""  # passed / failed / skipped / error
    duration: float = 0.0
    calls: list[ApiCall] = field(default_factory=list)


# ── Session-level storage ────────────────────────────────────────────────────

_records: list[TestRecord] = []
_current: TestRecord | None = None


# ── Monkey-patched APIClient ─────────────────────────────────────────────────


def _wrap_client_method(original, method_name: str):
    """Wrap an APIClient HTTP method to capture request/response."""

    def wrapper(self, path, data=None, format=None, content_type=None, **extra):
        resp = original(self, path, data=data, format=format, content_type=content_type, **extra)

        if _current is not None:
            call = ApiCall(
                method=method_name.upper(),
                path=str(path),
            )

            # Query params (from GET params embedded in path or passed as data for GET)
            if method_name == "get" and isinstance(data, dict):
                call.query_params = {k: str(v) for k, v in data.items()}
            elif "?" in str(path):
                call.query_params = {"_raw": str(path).split("?", 1)[1]}

            # Request headers
            req_headers: dict[str, str] = {}
            if hasattr(self, "_credentials"):
                req_headers.update(self._credentials)
            if content_type:
                req_headers["Content-Type"] = content_type
            elif format == "json":
                req_headers["Content-Type"] = "application/json"
            call.request_headers = req_headers

            # Request body
            if data is not None and method_name != "get":
                call.request_body = data

            # Response
            call.status_code = resp.status_code
            resp_headers: dict[str, str] = {}
            if hasattr(resp, "headers"):
                resp_headers = {k: v for k, v in resp.headers.items()}
            elif hasattr(resp, "_headers"):
                resp_headers = {k: v[-1] for k, v in resp._headers.items()}
            call.response_headers = resp_headers

            try:
                call.response_body = resp.json()
            except Exception:
                call.response_body = getattr(resp, "data", None)

            _current.calls.append(call)

        return resp

    return wrapper


# ── Pytest hooks ─────────────────────────────────────────────────────────────


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Start tracking a new test."""
    global _current
    node = (
        item.nodeid
    )  # e.g. tests/e2e/accounts/test_auth_login.py::TestAuthLogin::test_login_success
    parts = node.split("::")
    module = parts[0] if parts else ""
    class_name = parts[1] if len(parts) > 2 else ""
    test_name = parts[-1] if parts else ""

    _current = TestRecord(
        module=module,
        class_name=class_name,
        test_name=test_name,
    )


def pytest_runtest_makereport(item: pytest.Item, call):
    """Capture test outcome."""
    if call.when == "call" and _current is not None:
        _current.duration = call.duration


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    yield


def pytest_runtest_teardown(item: pytest.Item, nextitem) -> None:
    """Finalize the current test record."""
    global _current
    if _current is not None:
        _records.append(_current)
        _current = None


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report) -> None:
    """Set outcome on the most recent record."""
    if report.when == "call" and _records:
        rec = _records[-1]
        if not rec.outcome:
            rec.outcome = report.outcome
    elif report.when == "setup" and report.skipped and _records:
        rec = _records[-1]
        rec.outcome = "skipped"


def pytest_configure(config: pytest.Config) -> None:
    """Patch APIClient at import time."""
    from rest_framework.test import APIClient

    for method in ("get", "post", "put", "patch", "delete", "head", "options"):
        original = getattr(APIClient, method)
        setattr(APIClient, method, _wrap_client_method(original, method))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Generate HTML report at end of session."""
    if not _records:
        return

    import os

    server = os.getenv("GITHUB_SERVER_URL", "")
    repo = os.getenv("GITHUB_REPOSITORY", "")
    sha = os.getenv("GITHUB_SHA", "main")
    # e.g. https://github.com/user/repo/blob/abc123/backend/
    blob_base = f"{server}/{repo}/blob/{sha}/backend/" if server and repo else ""

    out_path = Path(session.config.rootpath) / "e2e-api-test-results.html"
    html = _generate_html(_records, blob_base=blob_base)
    out_path.write_text(html, encoding="utf-8")


# ── HTML report generation ───────────────────────────────────────────────────


def _json_pretty(obj: Any) -> str:
    """Pretty-print JSON, truncating large payloads."""
    if obj is None:
        return ""
    try:
        text = json.dumps(obj, indent=2, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(obj)
    if len(text) > 5000:
        text = text[:5000] + "\n... (truncated)"
    return escape(text)


def _badge(outcome: str) -> str:
    colors = {
        "passed": "#22c55e",
        "failed": "#ef4444",
        "skipped": "#f59e0b",
        "error": "#ef4444",
    }
    color = colors.get(outcome, "#6b7280")
    return f'<span class="badge" style="background:{color}">{escape(outcome)}</span>'


def _status_color(code: int) -> str:
    if 200 <= code < 300:
        return "#22c55e"
    if 300 <= code < 400:
        return "#3b82f6"
    if 400 <= code < 500:
        return "#f59e0b"
    return "#ef4444"


def _generate_html(records: list[TestRecord], blob_base: str = "") -> str:
    total = len(records)
    passed = sum(1 for r in records if r.outcome == "passed")
    failed = sum(1 for r in records if r.outcome == "failed")
    skipped = sum(1 for r in records if r.outcome == "skipped")
    total_calls = sum(len(r.calls) for r in records)

    def _module_cell(module: str) -> str:
        name = escape(module)
        if blob_base and module:
            url = blob_base + module
            return f'<a href="{url}" target="_blank">{name}</a>'
        return name

    rows: list[str] = []
    for idx, rec in enumerate(records):
        if not rec.calls:
            rows.append(f"""
            <tr class="test-row {rec.outcome}">
              <td>{_module_cell(rec.module)}</td>
              <td>{escape(rec.class_name)}</td>
              <td>{escape(rec.test_name)}</td>
              <td>{_badge(rec.outcome)}</td>
              <td>—</td>
              <td>—</td>
              <td>—</td>
              <td>{rec.duration:.3f}s</td>
              <td></td>
            </tr>""")
            continue

        for ci, call in enumerate(rec.calls):
            rows.append(f"""
            <tr class="test-row {rec.outcome}">
              <td>{_module_cell(rec.module) if ci == 0 else ""}</td>
              <td>{escape(rec.class_name) if ci == 0 else ""}</td>
              <td>{escape(rec.test_name) if ci == 0 else ""}</td>
              <td>{_badge(rec.outcome) if ci == 0 else ""}</td>
              <td><code>{escape(call.method)}</code></td>
              <td><code>{escape(call.path)}</code></td>
              <td><span style="color:{_status_color(call.status_code)};font-weight:700">{call.status_code}</span></td>
              <td>{f"{rec.duration:.3f}s" if ci == 0 else ""}</td>
              <td>
                <button class="toggle-btn" onclick="toggleDetail('detail-{idx}-{ci}')">Details</button>
                <div id="detail-{idx}-{ci}" class="detail-panel" style="display:none">
                  <h4>Request Headers</h4>
                  <pre>{_json_pretty(call.request_headers)}</pre>
                  <h4>Query Params</h4>
                  <pre>{_json_pretty(call.query_params) if call.query_params else "—"}</pre>
                  <h4>Request Body</h4>
                  <pre>{_json_pretty(call.request_body) if call.request_body else "—"}</pre>
                  <h4>Response Headers</h4>
                  <pre>{_json_pretty(call.response_headers)}</pre>
                  <h4>Response Body</h4>
                  <pre>{_json_pretty(call.response_body)}</pre>
                </div>
              </td>
            </tr>""")

    table_rows = "\n".join(rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>E2E API Test Report</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#f8fafc; color:#1e293b; padding:24px; }}
  h1 {{ font-size:1.5rem; margin-bottom:8px; }}
  .summary {{ display:flex; gap:16px; margin-bottom:20px; flex-wrap:wrap; }}
  .summary .card {{ background:#fff; border:1px solid #e2e8f0; border-radius:8px; padding:12px 20px; min-width:120px; }}
  .summary .card .num {{ font-size:1.5rem; font-weight:700; }}
  .summary .card .label {{ font-size:0.8rem; color:#64748b; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid #e2e8f0; border-radius:8px; overflow:hidden; font-size:0.85rem; }}
  th {{ background:#f1f5f9; text-align:left; padding:10px 12px; font-weight:600; position:sticky; top:0; }}
  td {{ padding:8px 12px; border-top:1px solid #f1f5f9; vertical-align:top; }}
  tr.failed {{ background:#fef2f2; }}
  tr.skipped {{ background:#fffbeb; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:4px; color:#fff; font-size:0.75rem; font-weight:600; }}
  code {{ background:#f1f5f9; padding:1px 4px; border-radius:3px; font-size:0.8rem; }}
  .toggle-btn {{ background:#3b82f6; color:#fff; border:none; padding:4px 10px; border-radius:4px; cursor:pointer; font-size:0.75rem; }}
  .toggle-btn:hover {{ background:#2563eb; }}
  .detail-panel {{ margin-top:8px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:12px; max-width:700px; }}
  .detail-panel h4 {{ font-size:0.8rem; color:#64748b; margin:8px 0 4px; }}
  .detail-panel h4:first-child {{ margin-top:0; }}
  .detail-panel pre {{ background:#1e293b; color:#e2e8f0; padding:8px; border-radius:4px; overflow-x:auto; font-size:0.75rem; white-space:pre-wrap; word-break:break-all; max-height:300px; }}
  .filter-bar {{ margin-bottom:12px; display:flex; gap:8px; align-items:center; }}
  .filter-bar input {{ padding:6px 10px; border:1px solid #e2e8f0; border-radius:4px; font-size:0.85rem; width:300px; }}
  .filter-bar select {{ padding:6px 10px; border:1px solid #e2e8f0; border-radius:4px; font-size:0.85rem; }}
</style>
</head>
<body>
<h1>E2E API Test Report</h1>
<div class="summary">
  <div class="card"><div class="num">{total}</div><div class="label">Total Tests</div></div>
  <div class="card"><div class="num" style="color:#22c55e">{passed}</div><div class="label">Passed</div></div>
  <div class="card"><div class="num" style="color:#ef4444">{failed}</div><div class="label">Failed</div></div>
  <div class="card"><div class="num" style="color:#f59e0b">{skipped}</div><div class="label">Skipped</div></div>
  <div class="card"><div class="num">{total_calls}</div><div class="label">API Calls</div></div>
</div>
<div class="filter-bar">
  <input type="text" id="search" placeholder="Filter by module, test, or endpoint..." oninput="filterTable()">
  <select id="outcomeFilter" onchange="filterTable()">
    <option value="">All outcomes</option>
    <option value="passed">Passed</option>
    <option value="failed">Failed</option>
    <option value="skipped">Skipped</option>
  </select>
</div>
<table id="reportTable">
<thead>
<tr>
  <th>Module</th>
  <th>Class</th>
  <th>Test</th>
  <th>Result</th>
  <th>Method</th>
  <th>Endpoint</th>
  <th>Status</th>
  <th>Duration</th>
  <th>Details</th>
</tr>
</thead>
<tbody>
{table_rows}
</tbody>
</table>
<script>
function toggleDetail(id) {{
  var el = document.getElementById(id);
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}}
function filterTable() {{
  var search = document.getElementById('search').value.toLowerCase();
  var outcome = document.getElementById('outcomeFilter').value;
  var rows = document.querySelectorAll('#reportTable tbody tr');
  rows.forEach(function(row) {{
    var text = row.textContent.toLowerCase();
    var matchSearch = !search || text.indexOf(search) !== -1;
    var matchOutcome = !outcome || row.classList.contains(outcome);
    row.style.display = (matchSearch && matchOutcome) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""
