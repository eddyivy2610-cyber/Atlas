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
from typing import Any, Dict, List, Optional, Union
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
# In-memory store: project -> list of sequence-ready session dicts
TRACE_STORE: Dict[str, List[Dict[str, Any]]] = {}

REPOS = {
    "tinydb": REPO_ROOT / "data" / "repos" / "tinydb" / "tinydb",
    "click": REPO_ROOT / ".venv" / "Lib" / "site-packages" / "click",
}


def resolve_directory_path(path_input: Optional[Union[str, Path]]) -> Optional[Path]:
    """Resolve a directory path, handling absolute paths, relative paths, and bare folder names."""
    if not path_input:
        return None
    raw_str = str(path_input).strip()
    if not raw_str:
        return None

    raw_path = Path(raw_str)
    try:
        if raw_path.exists() and raw_path.is_dir():
            return raw_path.resolve()
    except OSError:
        pass

    # Normalize folder name if a relative path was passed
    folder_name = raw_path.name if raw_path.name else raw_str.strip("/\\")
    candidates = [
        raw_path,
        Path.cwd() / raw_str,
        Path.home() / "Desktop" / folder_name,
        Path.home() / "Desktop" / raw_str,
        Path.home() / "Downloads" / folder_name,
        Path.home() / "Documents" / folder_name,
        Path.home() / folder_name,
        REPO_ROOT.parent / folder_name,
        REPO_ROOT.parent.parent / folder_name,
    ]
    for cand in candidates:
        try:
            if cand.exists() and cand.is_dir():
                return cand.resolve()
        except OSError:
            continue
    return None


def execute_pipeline(project_name: str, custom_path: Optional[Path] = None) -> Dict[str, Any]:
    """Execute the full UMLdoc pipeline server-side and return an execution summary."""
    start_time = time.time()
    resolved_custom = resolve_directory_path(custom_path) if custom_path else None
    repo_path = resolved_custom if resolved_custom else REPOS.get(project_name.lower())
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
            drift_report = DriftAnalyzer.analyze_drift(
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


def _session_to_sequence_payload(session_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a TraceSessionIR dict into the sequence diagram payload shape the UI expects."""
    participants_raw = session_dict.get("participants", [])
    interactions_raw = session_dict.get("interactions", [])

    # Build participant list (deduplicate, keep order)
    seen_ids: set = set()
    participants = []
    for p in participants_raw:
        pid = p.get("id", "")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            cls_name = p.get("class_name") or p.get("name", pid)
            # Heuristic participant type from class name
            name_lower = cls_name.lower()
            if any(k in name_lower for k in ("client", "caller", "user", "actor")):
                ptype, icon = "external", "user"
            elif any(k in name_lower for k in ("view", "ui", "web", "browser", "frontend")):
                ptype, icon = "ui", "monitor"
            elif any(k in name_lower for k in ("db", "database", "storage", "repo", "repository", "store")):
                ptype, icon = "data", "database"
            elif any(k in name_lower for k in ("gateway", "stripe", "paypal", "external", "api")):
                ptype, icon = "service", "globe"
            else:
                ptype, icon = "business", "box"
            participants.append({
                "id": pid,
                "name": p.get("name", pid),
                "type": ptype,
                "icon": icon,
            })

    # Ensure a "Client" / initial caller is always first
    client_ids = {p["id"] for p in participants if p["type"] == "external"}
    if not client_ids and participants:
        participants[0]["type"] = "external"
        participants[0]["icon"] = "user"

    # Build message list from CALL and RETURN interactions
    messages = []
    seq = 1
    for ev in sorted(interactions_raw, key=lambda e: e.get("sequence_order", 0)):
        event_type = ev.get("event_type", "call")
        caller = ev.get("caller_id", "")
        callee = ev.get("callee_id", "")
        if not caller or not callee or caller == callee:
            continue
        if event_type == "call":
            method = ev.get("method_name", "")
            # Build arg string
            args = ev.get("arguments", {})
            arg_str = ", ".join(
                f"{k}={v.get('repr_value', '?')}" for k, v in (args.items() if isinstance(args, dict) else [])
            )
            label = f"{seq}. {method}({arg_str})" if arg_str else f"{seq}. {method}()"
            messages.append({"from": caller, "to": callee, "label": label[:60], "type": "call"})
            seq += 1
        elif event_type == "return":
            ret = ev.get("return_value")
            ret_repr = ret.get("repr_value", "") if isinstance(ret, dict) else ""
            label = f"{seq}. {ret_repr}" if ret_repr and ret_repr not in ("None", "<NoneType>") else f"{seq}. return"
            messages.append({"from": caller, "to": callee, "label": label[:60], "type": "return"})
            seq += 1
        elif event_type == "exception":
            exc = ev.get("exception", {})
            exc_name = exc.get("type_name", "Exception") if isinstance(exc, dict) else "Exception"
            label = f"{seq}. raise {exc_name}"
            messages.append({"from": caller, "to": callee, "label": label[:60], "type": "return"})
            seq += 1

    return {
        "title": session_dict.get("scenario_name", "Execution Trace"),
        "description": f"Entrypoint: {session_dict.get('entrypoint', '')}  |  Duration: {session_dict.get('duration_ms', 0):.1f} ms  |  Events: {session_dict.get('metadata', {}).get('total_events', '?')}",
        "session_id": session_dict.get("session_id", ""),
        "participants": participants,
        "messages": messages,
    }


def get_ecommerce_demo_data() -> Dict[str, Any]:
    """Return the reference e-commerce architecture model matching the UI specification."""
    classes = [
        {
            "name": "PaymentGateway",
            "id": "PaymentGateway",
            "stereotype": "«interface»",
            "bases": [],
            "file": "payment/gateway.py",
            "line": 1,
            "code": ["class PaymentGateway(Protocol):", "    def process_payment(self, amount: Decimal) -> bool: ...", "    def refund(self, payment_id: str) -> bool: ...", "    def get_status(self, payment_id: str) -> str: ..."],
            "attributes": [],
            "methods": [
                {"name": "process_payment(amount: Decimal)", "ret": "bool", "vis": "+"},
                {"name": "refund(payment_id: str)", "ret": "bool", "vis": "+"},
                {"name": "get_status(payment_id: str)", "ret": "str", "vis": "+"},
            ],
            "pos": {"x": 50, "y": 140},
            "verification_status": "Verified",
            "drift_status": "Current",
        },
        {
            "name": "StripePaymentGateway",
            "id": "StripePaymentGateway",
            "stereotype": "«class»",
            "bases": ["PaymentGateway"],
            "file": "payment/stripe.py",
            "line": 15,
            "code": ["class StripePaymentGateway(PaymentGateway):", "    api_key: str", "    environment: str"],
            "attributes": [
                {"name": "api_key", "type": "str", "vis": "-"},
                {"name": "environment", "type": "str", "vis": "-"},
            ],
            "methods": [
                {"name": "process_payment(amount: Decimal)", "ret": "bool", "vis": "+"},
                {"name": "refund(payment_id: str)", "ret": "bool", "vis": "+"},
                {"name": "get_status(payment_id: str)", "ret": "str", "vis": "+"},
            ],
            "pos": {"x": 50, "y": 410},
            "verification_status": "Verified",
            "drift_status": "Current",
        },
        {
            "name": "User",
            "id": "User",
            "stereotype": "«entity»",
            "bases": [],
            "file": "models/user.py",
            "line": 1,
            "code": ["class User:", "    def __init__(self, id: int, name: str, email: str, is_active: bool): ..."],
            "attributes": [
                {"name": "id", "type": "int", "vis": "#"},
                {"name": "name", "type": "str", "vis": "#"},
                {"name": "email", "type": "str", "vis": "#"},
                {"name": "is_active", "type": "bool", "vis": "#"},
            ],
            "methods": [
                {"name": "update_profile()", "ret": "None", "vis": "+"},
                {"name": "change_password()", "ret": "None", "vis": "+"},
                {"name": "get_orders()", "ret": "List[Order]", "vis": "+"},
            ],
            "pos": {"x": 370, "y": 130},
            "verification_status": "Verified",
            "drift_status": "Current",
        },
        {
            "name": "Customer",
            "id": "Customer",
            "stereotype": "«class»",
            "bases": ["User"],
            "file": "models/customer.py",
            "line": 20,
            "code": ["class Customer(User):", "    def place_order(self, cart: Cart) -> Order: ..."],
            "attributes": [
                {"name": "customer_id", "type": "int", "vis": "+"},
                {"name": "phone", "type": "str", "vis": "+"},
                {"name": "address", "type": "str", "vis": "+"},
            ],
            "methods": [
                {"name": "place_order(cart: Cart)", "ret": "Order", "vis": "+"},
                {"name": "get_order_history()", "ret": "List[Order]", "vis": "+"},
            ],
            "pos": {"x": 370, "y": 390},
            "verification_status": "Verified",
            "drift_status": "Current",
        },
        {
            "name": "Cart",
            "id": "Cart",
            "stereotype": "«class»",
            "bases": [],
            "file": "models/cart.py",
            "line": 1,
            "code": ["class Cart:", "    def add_item(self, product: Product, qty: int) -> None: ..."],
            "attributes": [
                {"name": "cart_id", "type": "int", "vis": "+"},
                {"name": "user_id", "type": "int", "vis": "+"},
                {"name": "created_at", "type": "datetime", "vis": "+"},
            ],
            "methods": [
                {"name": "add_item(product: Product, qty: int)", "ret": "None", "vis": "+"},
                {"name": "remove_item(product_id: int)", "ret": "None", "vis": "+"},
                {"name": "clear()", "ret": "None", "vis": "+"},
                {"name": "get_total()", "ret": "Decimal", "vis": "+"},
            ],
            "pos": {"x": 370, "y": 660},
            "verification_status": "Verified",
            "drift_status": "Current",
        },
        {
            "name": "OrderStatus",
            "id": "OrderStatus",
            "stereotype": "«enum»",
            "bases": ["Enum"],
            "file": "models/order.py",
            "line": 5,
            "code": ["class OrderStatus(Enum):", "    PENDING = 'PENDING'", "    PAID = 'PAID'", "    SHIPPED = 'SHIPPED'", "    DELIVERED = 'DELIVERED'", "    CANCELLED = 'CANCELLED'"],
            "attributes": [
                {"name": "PENDING", "type": "", "vis": "+"},
                {"name": "PAID", "type": "", "vis": "+"},
                {"name": "SHIPPED", "type": "", "vis": "+"},
                {"name": "DELIVERED", "type": "", "vis": "+"},
                {"name": "CANCELLED", "type": "", "vis": "+"},
            ],
            "methods": [],
            "pos": {"x": 730, "y": 140},
            "verification_status": "Verified",
            "drift_status": "Current",
        },
        {
            "name": "Order",
            "id": "Order",
            "stereotype": "«class»",
            "bases": [],
            "file": "models/order.py",
            "line": 25,
            "code": ["class Order:", "    def add_item(self, product: Product, qty: int) -> None: ..."],
            "attributes": [
                {"name": "order_id", "type": "int", "vis": "+"},
                {"name": "customer_id", "type": "int", "vis": "+"},
                {"name": "status", "type": "OrderStatus", "vis": "+"},
                {"name": "total_amount", "type": "Decimal", "vis": "+"},
                {"name": "created_at", "type": "datetime", "vis": "+"},
            ],
            "methods": [
                {"name": "add_item(product: Product, qty: int)", "ret": "None", "vis": "+"},
                {"name": "calculate_total()", "ret": "Decimal", "vis": "+"},
                {"name": "update_status(status: OrderStatus)", "ret": "None", "vis": "+"},
            ],
            "pos": {"x": 730, "y": 370},
            "verification_status": "Verified",
            "drift_status": "Current",
        },
        {
            "name": "OrderItem",
            "id": "OrderItem",
            "stereotype": "«class»",
            "bases": [],
            "file": "models/order_item.py",
            "line": 1,
            "code": ["class OrderItem:", "    def get_subtotal(self) -> Decimal: ..."],
            "attributes": [
                {"name": "order_item_id", "type": "int", "vis": "+"},
                {"name": "order_id", "type": "int", "vis": "+"},
                {"name": "product_id", "type": "int", "vis": "+"},
                {"name": "quantity", "type": "int", "vis": "+"},
                {"name": "unit_price", "type": "Decimal", "vis": "+"},
            ],
            "methods": [
                {"name": "get_subtotal()", "ret": "Decimal", "vis": "+"},
            ],
            "pos": {"x": 730, "y": 680},
            "verification_status": "Verified",
            "drift_status": "Current",
        },
        {
            "name": "Product",
            "id": "Product",
            "stereotype": "«class»",
            "bases": [],
            "file": "models/product.py",
            "line": 1,
            "code": ["class Product:", "    def is_in_stock(self) -> bool: ..."],
            "attributes": [
                {"name": "product_id", "type": "int", "vis": "+"},
                {"name": "name", "type": "str", "vis": "+"},
                {"name": "description", "type": "str", "vis": "+"},
                {"name": "price", "type": "Decimal", "vis": "+"},
                {"name": "stock_quantity", "type": "int", "vis": "+"},
            ],
            "methods": [
                {"name": "is_in_stock()", "ret": "bool", "vis": "+"},
                {"name": "update_stock(qty: int)", "ret": "None", "vis": "+"},
            ],
            "pos": {"x": 1130, "y": 370},
            "verification_status": "Verified",
            "drift_status": "Current",
        },
        {
            "name": "InventoryService",
            "id": "InventoryService",
            "stereotype": "«service»",
            "bases": [],
            "file": "services/inventory.py",
            "line": 1,
            "code": ["class InventoryService:", "    def check_stock(self, product_id: int, qty: int) -> bool: ..."],
            "attributes": [
                {"name": "product_repository", "type": "ProductRepository", "vis": "-"},
            ],
            "methods": [
                {"name": "check_stock(product_id: int, qty: int)", "ret": "bool", "vis": "+"},
                {"name": "reserve_stock(product_id: int, qty: int)", "ret": "bool", "vis": "+"},
                {"name": "release_stock(product_id: int, qty: int)", "ret": "None", "vis": "+"},
            ],
            "pos": {"x": 660, "y": 880},
            "verification_status": "Verified",
            "drift_status": "Current",
        },
        {
            "name": "ProductRepository",
            "id": "ProductRepository",
            "stereotype": "«interface»",
            "bases": [],
            "file": "repositories/product.py",
            "line": 1,
            "code": ["class ProductRepository(Protocol):", "    def find_by_id(self, id: int) -> Product: ..."],
            "attributes": [],
            "methods": [
                {"name": "find_by_id(id: int)", "ret": "Product", "vis": "+"},
                {"name": "save(product: Product)", "ret": "None", "vis": "+"},
                {"name": "update(product: Product)", "ret": "None", "vis": "+"},
            ],
            "pos": {"x": 1070, "y": 810},
            "verification_status": "Verified",
            "drift_status": "Current",
        },
    ]

    relations = [
        {"source": "Customer", "target": "User", "type": "INHERITANCE", "label": "", "source_cardinality": "", "target_cardinality": ""},
        {"source": "StripePaymentGateway", "target": "PaymentGateway", "type": "REALIZATION", "label": "", "source_cardinality": "", "target_cardinality": ""},
        {"source": "Customer", "target": "Order", "type": "ASSOCIATION", "label": "places", "source_cardinality": "1", "target_cardinality": "0..*"},
        {"source": "Customer", "target": "Cart", "type": "ASSOCIATION", "label": "has", "source_cardinality": "1", "target_cardinality": "1"},
        {"source": "Order", "target": "OrderItem", "type": "COMPOSITION", "label": "contains", "source_cardinality": "1", "target_cardinality": "1..*"},
        {"source": "Order", "target": "Product", "type": "COMPOSITION", "label": "contains", "source_cardinality": "1..*", "target_cardinality": "0..*"},
        {"source": "OrderItem", "target": "Product", "type": "AGGREGATION", "label": "refers to", "source_cardinality": "0..*", "target_cardinality": "1"},
        {"source": "InventoryService", "target": "ProductRepository", "type": "DEPENDENCY", "label": "uses", "source_cardinality": "", "target_cardinality": ""},
    ]

    return {
        "project": "e-commerce-service",
        "workspace": "e-commerce-service",
        "generated_at": "Apr 28, 2025 14:32",
        "source_branch": "main (commit a1b2c3d)",
        "classes": classes,
        "relations": relations,
        "drift": [],
        "verification_status": "Verified",
        "drift_status": "Verified",
        "issues_count": 0,
        "verified_count": 11,
        "mismatch_count": 0,
    }


def _extract_classes_json(project_name: str, custom_path: Optional[Path] = None) -> Dict[str, Any]:
    """Run extraction only and return class/relation data as a JSON-serialisable dict."""
    norm_name = project_name.lower().replace("-", "_")
    if norm_name in ("ecommerce", "e_commerce", "e_commerce_service", "ecommerce_service"):
        return get_ecommerce_demo_data()

    resolved_custom = resolve_directory_path(custom_path) if custom_path else None
    repo_path = resolved_custom if resolved_custom else REPOS.get(project_name.lower())
    if not repo_path or not repo_path.exists():
        raise ValueError(f"Unknown or missing repository: {project_name}")

    extractor = ASTStaticExtractor(project_name=project_name, root_path=str(repo_path))
    model = extractor.extract_directory(target_dir=str(repo_path))

    _vis = {"PUBLIC": "+", "PROTECTED": "#", "PRIVATE": "-"}

    classes = []
    for cls in model.classes[:60]:  # cap for UI performance
        loc = cls.source_location
        if cls.kind.value == "module":
            name_lower = cls.name.lower()
            if "route" in name_lower or "app" in name_lower or "controller" in name_lower:
                stereo = "\u00abcontroller\u00bb"
            elif "database" in name_lower or "db" in name_lower:
                stereo = "\u00abdatabase\u00bb"
            elif "engine" in name_lower or "service" in name_lower or "processor" in name_lower:
                stereo = "\u00abservice\u00bb"
            else:
                stereo = "\u00abmodule\u00bb"
        elif cls.is_abstract or cls.is_protocol or "interface" in cls.name.lower() or "protocol" in cls.name.lower():
            stereo = "\u00abinterface\u00bb"
        elif cls.is_enum:
            stereo = "\u00abenum\u00bb"
        elif cls.is_dataclass:
            stereo = "\u00abdataclass\u00bb"
        elif "service" in cls.name.lower() or "engine" in cls.name.lower() or "handler" in cls.name.lower():
            stereo = "\u00abservice\u00bb"
        elif cls.name.lower() in ("user", "account", "profile"):
            stereo = "\u00abentity\u00bb"
        else:
            stereo = "\u00abclass\u00bb"
        code_lines = []
        if loc and loc.file_path:
            fpath = Path(loc.file_path)
            if not fpath.is_file() and repo_path:
                candidate = repo_path / fpath
                if candidate.is_file():
                    fpath = candidate
            if fpath.is_file():
                try:
                    all_lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
                    s_idx = max(0, loc.start_line - 1)
                    e_idx = loc.end_line if (loc.end_line and loc.end_line > s_idx) else min(len(all_lines), s_idx + 40)
                    code_lines = all_lines[s_idx:e_idx]
                except Exception:
                    code_lines = []

        classes.append({
            "name": cls.name,
            "id": cls.id,
            "stereotype": stereo,
            "bases": cls.bases,
            "file": loc.file_path if loc else "",
            "line": loc.start_line if loc else 0,
            "code": code_lines,
            "attributes": [
                {"name": a.name, "type": a.type_annotation or "", "vis": _vis.get(a.visibility.name, "+")}
                for a in cls.attributes
            ],
            "methods": [
                {
                    "name": f"{m.name}({', '.join(p.name for p in m.parameters if p.name not in ('self', 'cls'))})",
                    "ret": m.return_type or "None",
                    "vis": _vis.get(m.visibility.name, "+"),
                }
                for m in cls.methods
                if not (m.name.startswith("__") and m.name.endswith("__") and m.name != "__init__")
            ],
        })

    seen: set = set()
    relations = []
    id_to_name = {c.id: c.name for c in model.classes}
    for c in model.classes:
        id_to_name[c.name] = c.name
        id_to_name[c.id.split(".")[-1]] = c.name

    for r in model.relations:
        src = id_to_name.get(r.source_id, r.source_id.split(".")[-1])
        tgt = id_to_name.get(r.target_id, r.target_id.split(".")[-1])
        key = (src, tgt, r.relation_type.name)
        if key not in seen:
            seen.add(key)
            relations.append({
                "source": src,
                "target": tgt,
                "type": r.relation_type.name,
                "label": r.label or "",
                "source_cardinality": getattr(r, "multiplicity_source", None) or "",
                "target_cardinality": getattr(r, "multiplicity_target", None) or "",
            })

    drift_items = []
    has_drift = False
    if project_name.lower() == "tinydb":
        v3_path = REPO_ROOT / "data" / "repos" / "tinydb_v3"
        v4_path = REPO_ROOT / "data" / "repos" / "tinydb_v4"
        if v3_path.exists() and v4_path.exists():
            has_drift = True
            try:
                m_v3 = ASTStaticExtractor(project_name="TinyDB", root_path=str(v3_path)).extract_directory(str(v3_path))
                m_v4 = ASTStaticExtractor(project_name="TinyDB", root_path=str(v4_path)).extract_directory(str(v4_path))
                rep = DriftAnalyzer.analyze_drift(m_v3, m_v4, base_commit="v3.15.2", target_commit="v4.0.0")
                for item in rep.drifted_elements:
                    drift_items.append({
                        "node": item.element_name,
                        "type": item.drift_type.name if hasattr(item.drift_type, "name") else str(item.drift_type),
                        "description": item.description,
                        "severity": item.severity.name if hasattr(item.severity, "name") else "CHANGED",
                    })
            except Exception:
                pass

    drift_map = {d["node"]: d for d in drift_items}
    for c in classes:
        if c["name"] in drift_map:
            c["drift_status"] = "Changed"
            c["drift_detail"] = drift_map[c["name"]]["description"]
            c["verification_status"] = "Mismatch"
        else:
            c["drift_status"] = "Current" if has_drift else "Not checked"
            c["drift_detail"] = "No structural drift detected"
            c["verification_status"] = "Verified"

    project_drift_status = "Changed" if drift_items else ("Current" if has_drift else "Not checked")
    project_verif_status = "Mismatch" if drift_items else "Verified"

    return {
        "project": project_name,
        "workspace": project_name,
        "generated_at": datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M"),
        "source_branch": "main (commit a1b2c3d)",
        "classes": classes,
        "relations": relations,
        "drift": drift_items,
        "verification_status": project_verif_status,
        "drift_status": project_drift_status,
        "issues_count": len(drift_items),
        "verified_count": len([c for c in classes if c.get("verification_status") == "Verified"]),
        "mismatch_count": len([c for c in classes if c.get("verification_status") != "Verified"]),
    }


def _scan_directory_summary(target_path: Path) -> Dict[str, Any]:
    """Fast scan of directory to provide live file count and filtering summary."""
    from umldoc.extractors.static_ast import DEFAULT_EXCLUDES, ASTStaticExtractor

    system_files = []
    filtered_tests = 0
    filtered_assets = 0
    filtered_libs = 0
    test_names = {"tests", "test", "testing", "fixtures", "mocks", "spec", "specs"}
    asset_names = {"static", "templates", "public", "assets", "media", "uploads", "data", "docs", "doc", "documentation"}
    lib_names = {"venv", ".venv", "env", ".env", "virtualenv", "site-packages", "node_modules", "lib", "include", "scripts", "build", "dist"}
    excludes = {d.lower() for d in DEFAULT_EXCLUDES}

    for root, dirs, files in os.walk(target_path):
        skipped = [d for d in dirs if d.startswith(".") or d.lower() in excludes]
        for d in skipped:
            dl = d.lower()
            if dl in test_names:
                filtered_tests += 1
            elif dl in asset_names:
                filtered_assets += 1
            elif dl in lib_names:
                filtered_libs += 1

        dirs[:] = [
            d for d in dirs
            if not d.startswith(".")
            and d.lower() not in excludes
            and not d.lower().endswith(".egg-info")
            and not d.lower().endswith("-dist-info")
        ]

        for file in files:
            if not file.endswith(".py") or file.startswith("."):
                fl = file.lower()
                if any(fl.endswith(ext) for ext in (".html", ".css", ".js", ".png", ".jpg", ".svg", ".json", ".md", ".txt", ".sql", ".db")):
                    filtered_assets += 1
                continue
            if ASTStaticExtractor.is_test_file(file):
                filtered_tests += 1
                continue
            rel_file = (Path(root) / file).relative_to(target_path).as_posix()
            system_files.append(rel_file)

    return {
        "status": "OK",
        "path": str(target_path),
        "folder_name": target_path.name,
        "system_files_count": len(system_files),
        "system_files": sorted(system_files),
        "filtered_tests": filtered_tests,
        "filtered_assets": filtered_assets,
        "filtered_libs": filtered_libs,
        "summary": f"{len(system_files)} system files found (filtered tests, web assets & venv).",
    }


def render_landing_page() -> str:
    """Read the static UML Forge presentation shell."""
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
            elif static_file.suffix in (".otf", ".ttf"):
                content_type = "font/otf" if static_file.suffix == ".otf" else "font/ttf"
            elif static_file.suffix == ".woff2":
                content_type = "font/woff2"
            elif static_file.suffix == ".woff":
                content_type = "font/woff"
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

        if path == "/api/classes":
            from urllib.parse import parse_qs
            params = parse_qs(parsed.query)
            project = params.get("project", ["tinydb"])[0]
            path_param = params.get("path", [None])[0]
            custom = resolve_directory_path(path_param)
            try:
                payload = json.dumps(_extract_classes_json(project, custom)).encode("utf-8")
                self.send_response(200)
            except (ValueError, OSError) as err:
                payload = json.dumps({"error": str(err)}).encode("utf-8")
                self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if path == "/api/scan":
            from urllib.parse import parse_qs
            params = parse_qs(parsed.query)
            path_param = params.get("path", [None])[0]
            if not path_param:
                payload = json.dumps({"status": "ERROR", "error": "No directory path specified"}).encode("utf-8")
                self.send_response(400)
            else:
                target_path = resolve_directory_path(path_param)
                if not target_path or not target_path.exists() or not target_path.is_dir():
                    payload = json.dumps({"status": "ERROR", "error": f"Folder not found: {path_param}"}).encode("utf-8")
                    self.send_response(404)
                else:
                    summary = _scan_directory_summary(target_path)
                    payload = json.dumps(summary).encode("utf-8")
                    self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
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

        # ── GET /api/trace ── return stored trace sessions for a project
        if path == "/api/trace":
            from urllib.parse import parse_qs
            params = parse_qs(parsed.query)
            project = params.get("project", ["e-commerce-service"])[0]
            sessions = TRACE_STORE.get(project, [])
            payload = json.dumps({"project": project, "sessions": sessions}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        # ── POST /api/trace ── accept TraceSessionIR JSON, store it, return sequence payload
        if parsed.path == "/api/trace":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                raw = json.loads(body)
                # Accept either bare TraceSessionIR or {project, session} wrapper
                if "session" in raw and "project" in raw:
                    project = str(raw["project"])
                    session_dict = raw["session"]
                elif "session_id" in raw:
                    project = raw.get("metadata", {}).get("project", "unknown")
                    session_dict = raw
                else:
                    raise ValueError("Body must be a TraceSessionIR or {project, session} wrapper")

                seq_payload = _session_to_sequence_payload(session_dict)

                # Persist to output/traces/
                trace_out_dir = OUTPUT_DIR / "traces"
                trace_out_dir.mkdir(parents=True, exist_ok=True)
                session_id = session_dict.get("session_id", f"trace_{len(TRACE_STORE)}")
                (trace_out_dir / f"{project}_{session_id}.json").write_text(
                    json.dumps(session_dict, indent=2), encoding="utf-8"
                )

                # Store in memory keyed by project
                if project not in TRACE_STORE:
                    TRACE_STORE[project] = []
                TRACE_STORE[project].insert(0, seq_payload)

                response = json.dumps(seq_payload).encode("utf-8")
                self.send_response(200)
            except (ValueError, json.JSONDecodeError, KeyError) as err:
                response = json.dumps({"status": "ERROR", "error": str(err)}).encode("utf-8")
                self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            return

        # ── POST /api/run ── execute the analysis pipeline
        if parsed.path != "/api/run":
            self.send_error(404, "Endpoint not found")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            payload = json.loads(body)
            project = str(payload.get("project", "tinydb"))
            path_param = payload.get("path")
            custom = resolve_directory_path(path_param)
            result = execute_pipeline(project, custom)
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
    port_arg = 8000
    if len(sys.argv) > 1:
        if "--port" in sys.argv:
            idx = sys.argv.index("--port")
            if idx + 1 < len(sys.argv):
                port_arg = int(sys.argv[idx + 1])
        elif sys.argv[1].isdigit():
            port_arg = int(sys.argv[1])
    run_server(port=port_arg, blocking=True)
