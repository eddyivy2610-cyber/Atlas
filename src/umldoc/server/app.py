"""Lightweight, zero-external-dependency local HTTP presentation server for UMLdoc.

Provides:
1. Browse mode for pre-generated TinyDB and Click dossiers.
2. Live-run mode for the validated extraction, verification, drift, and bundling pipeline.
3. In-memory session run history.
4. Static hosting for generated bundles and the presentation UI.
"""

import http.server
import json
import mimetypes
import os
import socketserver
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.ir.schema import DocumentIR
from umldoc.packaging.bundler import BundlePackager
from umldoc.parser.puml_parser import PlantUMLParser
from umldoc.verifier.comparator import DiagramVerifier
from umldoc.verifier.drift import DriftAnalyzer

REPO_ROOT = Path(__file__).parents[3]
BUNDLES_DIR = REPO_ROOT / "output" / "bundles"
OUTPUT_DIR = REPO_ROOT / "output"
STATIC_DIR = Path(__file__).with_name("static")
RUN_HISTORY: List[Dict[str, Any]] = []

REPOS = {
    "tinydb": REPO_ROOT / "data" / "repos" / "tinydb" / "tinydb",
    "click": REPO_ROOT / ".venv" / "Lib" / "site-packages" / "click",
}


def execute_pipeline(project_name: str) -> Dict[str, Any]:
    """Execute the full UMLdoc pipeline server-side and return an execution summary."""
    start_time = time.time()
    repo_path = REPOS.get(project_name)
    if not repo_path or not repo_path.exists():
        raise ValueError(f"Unknown or missing repository path for: {project_name}")

    extractor = ASTStaticExtractor(project_name=project_name, root_path=str(repo_path))
    static_model = extractor.extract_directory(target_dir=str(repo_path))

    verif_summary = None
    metrics_data = None
    raw_puml = OUTPUT_DIR / f"{project_name}_llm_raw.puml"
    metrics_file = OUTPUT_DIR / f"{project_name}_llm_eval_metrics.json"
    if raw_puml.exists():
        candidate_model = PlantUMLParser.parse_class_diagram(
            raw_puml.read_text(encoding="utf-8"),
            project_name=f"{project_name}-LLM",
        )
        verif_summary = DiagramVerifier(ground_truth=static_model).verify_candidate_model(candidate_model)
    if metrics_file.exists():
        try:
            metrics_data = json.loads(metrics_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            metrics_data = None

    drift_report = None
    if project_name == "tinydb":
        v3_path = REPO_ROOT / "data" / "repos" / "tinydb_v3"
        v4_path = REPO_ROOT / "data" / "repos" / "tinydb_v4"
        if v3_path.exists() and v4_path.exists():
            model_v3 = ASTStaticExtractor(project_name="TinyDB", root_path=str(v3_path)).extract_directory(str(v3_path))
            model_v4 = ASTStaticExtractor(project_name="TinyDB", root_path=str(v4_path)).extract_directory(str(v4_path))
            drift_report = DriftAnalyzer.analyze_evolution(
                model_v3, model_v4, base_commit="v3.15.2", target_commit="v4.0.0"
            )

    doc_ir = DocumentIR(
        project_name=project_name,
        static_model=static_model,
        verification=verif_summary,
        drift_report=drift_report,
    )
    bundle_dir = BUNDLES_DIR / project_name
    BundlePackager.package_document(
        document_ir=doc_ir,
        output_dir=bundle_dir,
        include_zip=True,
        extra_metrics=metrics_data,
    )

    duration_ms = (time.time() - start_time) * 1000
    run_entry = {
        "id": len(RUN_HISTORY) + 1,
        "project": project_name,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "classes_extracted": len(static_model.classes),
        "relations_extracted": len(static_model.relations),
        "verified_count": verif_summary.verified_count if verif_summary else 0,
        "drift_count": len(drift_report.drifted_elements) if drift_report else 0,
        "duration_ms": round(duration_ms, 1),
        "bundle_url": f"/bundles/{project_name}/index.html",
        "status": "SUCCESS",
    }
    RUN_HISTORY.insert(0, run_entry)
    return run_entry


def render_landing_page() -> str:
    """Read the static Orbit Glass presentation shell."""
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


def _safe_static_file(relative_path: str) -> Optional[Path]:
    """Resolve a static asset while preventing path traversal."""
    static_root = STATIC_DIR.resolve()
    candidate = (static_root / relative_path).resolve()
    try:
        candidate.relative_to(static_root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


class UMLdocHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler for UMLdoc's presentation layer."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def _send_file(self, file_path: Path, content_type: Optional[str] = None) -> None:
        file_bytes = file_path.read_bytes()
        resolved_type = content_type or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", resolved_type)
        self.send_header("Content-Length", str(len(file_bytes)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(file_bytes)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            encoded = render_landing_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(encoded)
            return

        if path.startswith("/static/"):
            relative_path = path[len("/static/"):]
            static_file = _safe_static_file(relative_path)
            if not static_file:
                self.send_error(404, "Static asset not found")
                return
            content_type = mimetypes.guess_type(static_file.name)[0]
            if static_file.suffix == ".js":
                content_type = "text/javascript; charset=utf-8"
            elif static_file.suffix == ".css":
                content_type = "text/css; charset=utf-8"
            self._send_file(static_file, content_type)
            return

        if path == "/api/history":
            data = json.dumps(RUN_HISTORY, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path.startswith("/bundles/"):
            rel_bundle_path = path[len("/bundles/"):]
            target_file = (BUNDLES_DIR / rel_bundle_path).resolve()
            try:
                target_file.relative_to(BUNDLES_DIR.resolve())
            except ValueError:
                target_file = Path()
            if target_file.is_file():
                content_type = mimetypes.guess_type(target_file.name)[0] or "application/octet-stream"
                if target_file.suffix in (".puml", ".mmd"):
                    content_type = "text/plain; charset=utf-8"
                self._send_file(target_file, content_type)
                return

        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self.send_error(404, "Endpoint not found")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            payload = json.loads(body)
            project = str(payload.get("project", "tinydb")).lower()
            result = execute_pipeline(project)
            response = json.dumps(result).encode("utf-8")
            self.send_response(200)
        except (ValueError, OSError, json.JSONDecodeError) as error:
            response = json.dumps({"status": "ERROR", "error": str(error)}).encode("utf-8")
            self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


class UMLdocServer:
    """Thread-safe, self-contained presentation server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host = host
        self.port = port
        self.httpd: Optional[socketserver.TCPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, blocking: bool = False) -> None:
        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = socketserver.TCPServer((self.host, self.port), UMLdocHTTPHandler)
        print("\n========================================================")
        print("  [server] UMLdoc Live Presentation Server Running")
        print(f"  Local URL: http://{self.host}:{self.port}/")
        print("========================================================\n")
        if blocking:
            try:
                self.httpd.serve_forever()
            except KeyboardInterrupt:
                self.stop()
        else:
            self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            print("[server] UMLdoc server stopped.")


def run_server(host: str = "127.0.0.1", port: int = 8000, blocking: bool = True) -> None:
    server = UMLdocServer(host=host, port=port)
    server.start(blocking=blocking)


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port=port_arg, blocking=True)
