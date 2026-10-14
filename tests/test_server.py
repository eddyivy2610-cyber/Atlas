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


def test_api_classes_static_diagrams_payload(live_server: str):
    """Verify /api/classes supplies models for Package and Architecture static diagrams."""
    url = f"{live_server}/api/classes?project=umldoc"
    with urllib.request.urlopen(url, timeout=10) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "classes" in data and len(data["classes"]) > 0
        assert "packages" in data and len(data["packages"]) > 0
        assert "package_relations" in data
        assert "components" in data and len(data["components"]) > 0
        assert "component_relations" in data
        assert data["packages"][0]["stereotype"] == "«package»"
        assert "tier" in [a["name"] for a in data["components"][0]["attributes"]]


def test_api_workspaces_crud(live_server: str):
    """Verify /api/workspaces saves, retrieves, and maintains workspace history."""
    # 1. GET initial workspaces
    get_url = f"{live_server}/api/workspaces"
    with urllib.request.urlopen(get_url, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "workspaces" in data
        assert len(data["workspaces"]) >= 1

    # 2. POST a new workspace
    new_ws = {
        "id": "pytest-workspace",
        "name": "Pytest Test Workspace",
        "path": "tests/workspace",
        "icon": "folder",
        "classesCount": 12,
        "verification": "VERIFIED"
    }
    post_req = urllib.request.Request(
        get_url,
        data=json.dumps(new_ws).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(post_req, timeout=5) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res["status"] == "OK"
        # The new workspace should be prepended
        assert res["workspaces"][0]["id"] == "pytest-workspace"
        assert res["workspaces"][0]["classesCount"] == 12

    # 3. DELETE the workspace
    del_req = urllib.request.Request(
        f"{live_server}/api/workspaces?id=pytest-workspace",
        method="DELETE"
    )
    with urllib.request.urlopen(del_req, timeout=5) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res["status"] == "OK"
        ids = [w["id"] for w in res["workspaces"]]
        assert "pytest-workspace" not in ids


def test_api_report_endpoint(live_server: str):
    """Verify /api/report supplies all 5 MVP dossier sections with real grounded metrics."""
    url = f"{live_server}/api/report?project=tinydb"
    with urllib.request.urlopen(url, timeout=10) as resp:
        assert resp.status == 200
        assert "application/json" in resp.headers.get("Content-Type", "")
        data = json.loads(resp.read().decode("utf-8"))
        
        # Verify 5 mandatory sections
        assert "run_summary" in data
        assert "verification_report" in data
        assert "drift_report" in data
        assert "performance_report" in data
        assert "export_bundle" in data
        
        # Check Section 1: Run Summary
        rs = data["run_summary"]
        assert rs["project"] == "tinydb"
        assert rs["classes_count"] >= 14
        assert "diagram_counts" in rs
        assert rs["diagram_counts"]["class"] >= 1
        assert rs["verification_status"].upper() in ("VERIFIED", "DRIFT DETECTED", "MISMATCH")
        
        # Check Section 2: Verification Report
        vr = data["verification_report"]
        assert "precision" in vr and 0.0 <= vr["precision"] <= 1.0
        assert "recall" in vr and 0.0 <= vr["recall"] <= 1.0
        assert "f1_score" in vr and 0.0 <= vr["f1_score"] <= 1.0
        assert "confusion_matrix" in vr
        cm = vr["confusion_matrix"]
        assert all(k in cm for k in ["TP", "FP", "FN", "TN"])
        assert isinstance(vr.get("issues"), list)
        
        # Check Section 3: Drift Report
        dr = data["drift_report"]
        assert "elements" in dr
        assert "summary" in dr
        
        # Check Section 4: Performance Report
        pr = data["performance_report"]
        assert "total_pipeline_ms" in pr
        assert "stages" in pr and len(pr["stages"]) >= 4
        
        # Check Section 5: Export / Evidence Bundle
        eb = data["export_bundle"]
        assert "pdf_url" in eb
        assert "csv_url" in eb
        assert "puml_url" in eb
        assert "mmd_url" in eb


def test_api_export_endpoints(live_server: str):
    """Verify /api/export/csv, /api/export/puml, and /api/export/mmd return valid file payloads."""
    # 1. CSV Summary Export
    csv_url = f"{live_server}/api/export/csv?project=tinydb"
    with urllib.request.urlopen(csv_url, timeout=10) as resp:
        assert resp.status == 200
        assert "text/csv" in resp.headers.get("Content-Type", "")
        csv_text = resp.read().decode("utf-8")
        assert "Entity Name,Stereotype,Attributes Count" in csv_text
        assert "TinyDB" in csv_text

    # 2. PlantUML Export
    puml_url = f"{live_server}/api/export/puml?project=tinydb"
    with urllib.request.urlopen(puml_url, timeout=10) as resp:
        assert resp.status == 200
        assert "text/plain" in resp.headers.get("Content-Type", "")
        puml_text = resp.read().decode("utf-8")
        assert "@startuml" in puml_text
        assert "@enduml" in puml_text
        assert "class TinyDB" in puml_text or "class" in puml_text

    # 3. Mermaid Export
    mmd_url = f"{live_server}/api/export/mmd?project=tinydb"
    with urllib.request.urlopen(mmd_url, timeout=10) as resp:
        assert resp.status == 200
        assert "text/plain" in resp.headers.get("Content-Type", "")
        mmd_text = resp.read().decode("utf-8")
        assert "classDiagram" in mmd_text

    # 4. Diagram Vector SVG Export
    arch_url = f"{live_server}/api/export/diagram?project=tinydb&type=architecture&format=svg"
    with urllib.request.urlopen(arch_url, timeout=10) as resp:
        assert resp.status == 200
        assert "image/svg+xml" in resp.headers.get("Content-Type", "")
        svg_text = resp.read().decode("utf-8")
        assert "<svg" in svg_text
        assert "</svg>" in svg_text
        assert "parsererror" not in svg_text


def test_api_scan_git_repository_cached(live_server: str):
    """Verify /api/scan returns cached clone info when Git URL points to an existing repo."""
    git_url = "https://github.com/msiemens/tinydb.git"
    scan_url = f"{live_server}/api/scan?path={urllib.request.quote(git_url)}"
    with urllib.request.urlopen(scan_url, timeout=10) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "OK"
        assert data["is_git"] is True
        assert data["is_cloned"] is True
        assert data["repo_name"] == "tinydb"
        assert data["system_files_count"] >= 5


def test_api_scan_git_repository_remote_mock(live_server: str, monkeypatch):
    """Verify /api/scan verifies remote Git repositories."""
    from unittest.mock import patch
    with patch("umldoc.server.app.check_remote_git_repo") as mock_check:
        mock_check.return_value = {
            "accessible": True,
            "branches": ["main", "feature"],
            "default_branch": "main",
        }
        git_url = "https://github.com/org/mock-remote-project.git"
        scan_url = f"{live_server}/api/scan?path={urllib.request.quote(git_url)}"
        with urllib.request.urlopen(scan_url, timeout=10) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "OK"
            assert data["is_git"] is True
            assert data["is_cloned"] is False
            assert data["repo_name"] == "mock-remote-project"
            assert "main" in data["branches"]
            assert data["default_branch"] == "main"


def test_api_run_git_clone_pipeline(live_server: str):
    """Verify POST /api/run handles git_url, invokes clone_or_update_repo, and runs the extraction pipeline."""
    from unittest.mock import patch
    from umldoc.server.app import REPO_ROOT

    tinydb_path = REPO_ROOT / "data" / "repos" / "tinydb" / "tinydb"
    with patch("umldoc.server.app.clone_or_update_repo") as mock_clone:
        mock_clone.return_value = tinydb_path

        run_url = f"{live_server}/api/run"
        payload = json.dumps({
            "project": "tinydb-git",
            "git_url": "https://github.com/msiemens/tinydb.git",
            "branch": "master",
            "token": "ghp_mock_token",
        }).encode("utf-8")
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
            assert result["project"] == "tinydb-git"
            assert result["classes_extracted"] >= 14
            assert mock_clone.called
            called_args = mock_clone.call_args[1]
            assert called_args["repo_url"] == "https://github.com/msiemens/tinydb.git"
            assert called_args["branch"] == "master"
            assert called_args["token"] == "ghp_mock_token"



