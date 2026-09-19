"""Standalone extraction + verification report for TinyDB.

Usage
-----
    python scripts/extract_tinydb_report.py

Outputs
-------
    output/tinydb_verification_report.html  — full HTML report
    output/tinydb_verification_metrics.json — machine-readable confusion matrix

This script is the artifact you can show an evaluator as concrete evidence of
what the pipeline produces on a real, non-trivial codebase.  The synthetic LLM
candidate used here is the same one used in
``tests/test_tinydb_verifier_integration.py`` — see that file for rationale and
a description of what would need to change to use output from a real LLM call.
"""

import json
import sys
from pathlib import Path

# Make sure we can import from src/ regardless of how the script is invoked
REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.ir.base import ElementKind, VerificationStatus
from umldoc.ir.schema import DocumentIR
from umldoc.ir.static_model import ClassIR, MethodIR, ParameterIR, StaticModelIR
from umldoc.verifier.comparator import DiagramVerifier
from umldoc.verifier.html_report import HTMLReportGenerator
from umldoc.verifier.metrics import MetricsCalculator

# ---------------------------------------------------------------------------
# Synthetic LLM candidate (same as test_tinydb_verifier_integration.py)
# ---------------------------------------------------------------------------
SYNTHETIC_LLM_CANDIDATE = StaticModelIR(
    project_name="TinyDB-LLM-Generated",
    classes=[
        ClassIR(
            id="tinydb.database.TinyDB", name="TinyDB",
            qualified_name="tinydb.database.TinyDB", kind=ElementKind.CLASS,
            methods=[
                MethodIR(id="TinyDB.table", name="table",
                         parameters=[ParameterIR(name="name")], return_type="Table"),
                MethodIR(id="TinyDB.close", name="close",
                         parameters=[], return_type="None"),
            ],
        ),
        ClassIR(
            id="tinydb.table.Table", name="Table",
            qualified_name="tinydb.table.Table", kind=ElementKind.CLASS,
            methods=[
                MethodIR(id="Table.insert", name="insert",
                         parameters=[ParameterIR(name="document")], return_type="int"),
                MethodIR(id="Table.search", name="search",
                         parameters=[ParameterIR(name="cond")], return_type="list"),
                MethodIR(id="Table.all", name="all",
                         parameters=[], return_type="list"),
                MethodIR(id="Table.remove", name="remove",
                         parameters=[ParameterIR(name="cond")], return_type="list"),
            ],
        ),
        ClassIR(
            id="tinydb.storages.MemoryStorage", name="MemoryStorage",
            qualified_name="tinydb.storages.MemoryStorage", kind=ElementKind.CLASS,
            methods=[
                MethodIR(id="MemoryStorage.read", name="read",
                         parameters=[], return_type="Optional[dict]"),
                MethodIR(id="MemoryStorage.write", name="write",
                         parameters=[ParameterIR(name="data")], return_type="None"),
            ],
        ),
        # Drift: LRUCache.get has an extra invented 'ttl' parameter
        ClassIR(
            id="tinydb.utils.LRUCache", name="LRUCache",
            qualified_name="tinydb.utils.LRUCache", kind=ElementKind.CLASS,
            methods=[
                MethodIR(
                    id="LRUCache.get", name="get",
                    parameters=[
                        ParameterIR(name="key"),
                        ParameterIR(name="default"),
                        ParameterIR(name="ttl"),   # invented
                    ],
                    return_type="Optional[V]",
                ),
            ],
        ),
        # Hallucinations
        ClassIR(
            id="tinydb.queries.QueryBuilder", name="QueryBuilder",
            qualified_name="tinydb.queries.QueryBuilder", kind=ElementKind.CLASS,
            methods=[
                MethodIR(id="QueryBuilder.build", name="build",
                         parameters=[ParameterIR(name="field")], return_type="QueryInstance"),
            ],
        ),
        ClassIR(
            id="tinydb.database.IndexManager", name="IndexManager",
            qualified_name="tinydb.database.IndexManager", kind=ElementKind.CLASS,
            methods=[
                MethodIR(id="IndexManager.create_index", name="create_index",
                         parameters=[ParameterIR(name="field")], return_type="None"),
            ],
        ),
        ClassIR(
            id="tinydb.utils.SchemaValidator", name="SchemaValidator",
            qualified_name="tinydb.utils.SchemaValidator", kind=ElementKind.CLASS,
            methods=[
                MethodIR(id="SchemaValidator.validate", name="validate",
                         parameters=[ParameterIR(name="document")], return_type="bool"),
            ],
        ),
    ],
)

EXPECTED_LABELS = {
    "TinyDB":          VerificationStatus.MATCH,
    "Table":           VerificationStatus.MATCH,
    "MemoryStorage":   VerificationStatus.MATCH,
    "LRUCache":        VerificationStatus.DRIFTED,
    "QueryBuilder":    VerificationStatus.HALLUCINATED,
    "IndexManager":    VerificationStatus.HALLUCINATED,
    "SchemaValidator": VerificationStatus.HALLUCINATED,
    "Storage":         VerificationStatus.MISSING,
    "JSONStorage":     VerificationStatus.MISSING,
    "Document":        VerificationStatus.MISSING,
    "QueryInstance":   VerificationStatus.MISSING,
    "FrozenDict":      VerificationStatus.MISSING,
}


def main() -> None:
    tinydb_source = REPO_ROOT / "data" / "repos" / "tinydb" / "tinydb"
    output_dir = REPO_ROOT / "output"
    output_dir.mkdir(exist_ok=True)

    print(f"[1/4] Extracting ground truth from {tinydb_source} ...")
    extractor = ASTStaticExtractor(project_name="TinyDB", root_path=str(tinydb_source))
    ground_truth = extractor.extract_directory(target_dir=str(tinydb_source))
    print(f"      Found {len(ground_truth.classes)} classes in ground truth.")

    print("[2/4] Running DiagramVerifier on synthetic LLM candidate ...")
    verifier = DiagramVerifier(ground_truth=ground_truth)
    summary = verifier.verify_candidate_model(SYNTHETIC_LLM_CANDIDATE)
    print(
        f"      total={summary.total_elements}  verified={summary.verified_count}  "
        f"hallucinated={summary.hallucinated_count}  drifted={summary.drifted_count}  "
        f"missing={summary.missing_count}"
    )

    print("[3/4] Computing metrics ...")
    metrics = MetricsCalculator.compute_metrics(summary, EXPECTED_LABELS)

    tp = metrics.true_positives
    fp = metrics.false_positives
    fn = metrics.false_negatives
    tn = metrics.true_negatives

    print()
    print("=" * 52)
    print("  CONFUSION MATRIX")
    print("=" * 52)
    print(f"  True Positives  (TP): {tp:4d}")
    print(f"  False Positives (FP): {fp:4d}")
    print(f"  False Negatives (FN): {fn:4d}")
    print(f"  True Negatives  (TN): {tn:4d}")
    print(f"  -------------------------")
    print(f"  Total accounted:      {tp+fp+fn+tn:4d}  (labels: {len(EXPECTED_LABELS)})")
    print(f"  Skipped labels:       {metrics.skipped_labels:4d}")
    print(f"  Unlabelled records:   {metrics.unlabelled_records:4d}")
    print()
    print(f"  Precision:                  {metrics.precision:.4f}")
    print(f"  Recall:                     {metrics.recall:.4f}")
    print(f"  F1 Score:                   {metrics.f1_score:.4f}")
    print(f"  Hallucination Detection:    {metrics.hallucination_detection_rate:.4f}")
    print("=" * 52)
    print()

    # ---- Write JSON metrics ----
    json_path = output_dir / "tinydb_verification_metrics.json"
    json_path.write_text(
        json.dumps(
            {
                "ground_truth_source": str(tinydb_source),
                "candidate": "synthetic_llm_simulation",
                "confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
                "skipped_labels": metrics.skipped_labels,
                "unlabelled_records": metrics.unlabelled_records,
                "metrics": {
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "f1_score": metrics.f1_score,
                    "hallucination_detection_rate": metrics.hallucination_detection_rate,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[4/4] Wrote metrics to {json_path}")

    # ---- Write HTML report ----
    doc = DocumentIR(
        project_name="TinyDB",
        static_model=ground_truth,
        verification=summary,
    )
    html = HTMLReportGenerator.generate_report(doc, title="TinyDB Verification Report")
    html_path = output_dir / "tinydb_verification_report.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"      Wrote HTML report to {html_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
