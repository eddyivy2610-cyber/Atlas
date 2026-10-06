"""Acceptance and integration tests for the live presentation server and interaction layer.

Tests:
1. Server starts and stops cleanly on localhost.
2. Landing page (Browse Mode) serves complete dashboard.
3. Static bundle serving serves index.html, SVG, and JSON.
4. Live-run endpoint (/api/run) executes pipeline end-to-end and returns 200 JSON.
5. History API (/api/history) maintains in-memory session records.
"""

import json
import time
import urllib.error
import urllib.request
import pytest

from umldoc.server.app import UMLdocServer, RUN_HISTORY


@pytest.fixture(scope="module")
def live_server():
    """Start an ephemeral UMLdoc presentation server in a background thread."""
    port = 8991
    server = UMLdocServer(host="127.0.0.1", port=port)
    server.start(blocking=False)
    time.sleep(0.3)  # Allow socket to bind
    yield f"http://127.0.0.1:{port}"
    server.stop()


def test_landing_page_browse_mode(live_server: str):
    """Verify landing page renders with Browse Mode and Live-Run controls."""
    url = f"{live_server}/"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        assert "text/html" in resp.headers.get("Content-Type", "")
        content = resp.read().decode("utf-8")
        assert "ATLAS" in content or "UMLdoc" in content
        assert "topbar" in content
        assert "diagHeaderMainTitle" in content


def test_static_bundle_serving(live_server: str):
    """Verify static bundles are served with correct MIME types."""
    # 1. HTML dossier
    html_url = f"{live_server}/bundles/tinydb/index.html"
    with urllib.request.urlopen(html_url, timeout=5) as resp:
        assert resp.status == 200
        assert "text/html" in resp.headers.get("Content-Type", "")
        assert len(resp.read()) > 500

    # 2. Native SVG diagram
    svg_url = f"{live_server}/bundles/tinydb/architecture.svg"
    with urllib.request.urlopen(svg_url, timeout=5) as resp:
        assert resp.status == 200
        assert "image/svg+xml" in resp.headers.get("Content-Type", "")
        svg_data = resp.read().decode("utf-8")
        assert "<svg" in svg_data

    # 3. Canonical JSON IR
    json_url = f"{live_server}/bundles/tinydb/document_ir.json"
    with urllib.request.urlopen(json_url, timeout=5) as resp:
        assert resp.status == 200
        assert "application/json" in resp.headers.get("Content-Type", "")
        data = json.loads(resp.read().decode("utf-8"))
        assert data["project_name"] == "tinydb"


def test_live_run_pipeline_execution(live_server: str):
    """Verify triggering live execution via POST /api/run."""
    run_url = f"{live_server}/api/run"
    payload = json.dumps({"project": "tinydb"}).encode("utf-8")
    req = urllib.request.Request(
        run_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        assert resp.status == 200
        result = json.loads(resp.read().decode("utf-8"))
        assert result["status"] == "SUCCESS"
        assert result["project"] == "tinydb"
        assert result["classes_extracted"] >= 14
        assert result["duration_ms"] > 0
        assert result["bundle_url"] == "/bundles/tinydb/index.html"


def test_session_run_history_api(live_server: str):
    """Verify in-memory session history API records past runs."""
    hist_url = f"{live_server}/api/history"
    with urllib.request.urlopen(hist_url, timeout=5) as resp:
        assert resp.status == 200
        history = json.loads(resp.read().decode("utf-8"))
        assert isinstance(history, list)
        assert len(history) >= 1
        assert history[0]["project"] == "tinydb"
        assert history[0]["status"] == "SUCCESS"
