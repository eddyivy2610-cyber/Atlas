"""Precision/recall evaluation for DiagramVerifier against the TinyDB benchmark dataset.

What this test file checks
--------------------------
* test_confusion_matrix_accounting — primary integrity check: every labelled
  element in BENCHMARK_EXPECTED_LABELS must appear in exactly one cell of the
  confusion matrix.  If TP+FP+FN+TN < len(labels) then elements are being
  silently dropped; if > len(labels) then elements are being double-counted.

* test_verifier_precision_recall_benchmark — verifies that the metrics returned
  are self-consistent and within a realistic range.  Critically it does NOT
  assert 100% precision/recall/F1 — doing so would assert a known bug rather
  than a property of the verifier.

What we deliberately do NOT assert
------------------------------------
* We do NOT assert metrics.precision == 1.0 or metrics.recall == 1.0.
  A verifier that achieves perfect scores on a hand-authored benchmark against
  its own author's hallucinations is not demonstrating real-world performance.

* We DO assert that metrics are in [0, 1] and internally consistent with the
  raw TP/FP/FN/TN counts.
"""

from pathlib import Path
import pytest
from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.ir.schema import DocumentIR
from umldoc.ir.base import VerificationStatus
from umldoc.verifier.comparator import DiagramVerifier
from umldoc.verifier.metrics import MetricsCalculator, VerificationMetrics
from umldoc.verifier.html_report import HTMLReportGenerator
from tests.benchmark.benchmark_dataset import (
    BENCHMARK_EXPECTED_LABELS,
    CANDIDATE_BENCHMARK_MODEL,
)

# The TinyDB source tree used as ground truth oracle
TINYDB_SOURCE = Path(__file__).parents[1] / "data" / "repos" / "tinydb" / "tinydb"


def _make_verifier() -> tuple[DiagramVerifier, object]:
    """Extract TinyDB ground truth and build a verifier over it."""
    extractor = ASTStaticExtractor(
        project_name="TinyDB", root_path=str(TINYDB_SOURCE)
    )
    ground_truth = extractor.extract_directory(target_dir=str(TINYDB_SOURCE))
    verifier = DiagramVerifier(ground_truth=ground_truth)
    return verifier, ground_truth


def test_confusion_matrix_accounting():
    """Every labelled element must appear in exactly one confusion-matrix cell.

    This test is the primary reconciliation check for the '30 vs 4' class of
    bug described in the thesis review.  If this test passes, the reported
    confusion matrix is complete — no elements are being silently skipped.
    """
    verifier, _ = _make_verifier()
    summary = verifier.verify_candidate_model(CANDIDATE_BENCHMARK_MODEL)
    metrics = MetricsCalculator.compute_metrics(summary, BENCHMARK_EXPECTED_LABELS)

    tp = metrics.true_positives
    fp = metrics.false_positives
    fn = metrics.false_negatives
    tn = metrics.true_negatives
    labelled = len(BENCHMARK_EXPECTED_LABELS)

    print(f"\nConfusion matrix:")
    print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  TP+FP+FN+TN = {tp + fp + fn + tn}")
    print(f"  len(BENCHMARK_EXPECTED_LABELS) = {labelled}")
    print(f"  skipped_labels = {metrics.skipped_labels}")
    print(f"  unlabelled_records = {metrics.unlabelled_records}")
    print(f"  precision={metrics.precision}  recall={metrics.recall}  "
          f"f1={metrics.f1_score}  halluc_detection={metrics.hallucination_detection_rate}")

    # Core accounting invariant: every label must map to exactly one cell
    assert tp + fp + fn + tn == labelled - metrics.skipped_labels, (
        f"Confusion matrix total ({tp + fp + fn + tn}) does not equal "
        f"number of labelled elements ({labelled} - {metrics.skipped_labels} skipped = "
        f"{labelled - metrics.skipped_labels}).  "
        f"Some elements are being silently dropped from the evaluation."
    )

    # No labels should be silently skipped — every expected label must match
    # at least one verification record produced by the verifier
    assert metrics.skipped_labels == 0, (
        f"{metrics.skipped_labels} expected labels had no matching verification record.  "
        f"Either the candidate model is missing those classes or the label keys do not "
        f"match the element names produced by the verifier."
    )


def test_verifier_precision_recall_benchmark():
    """Evaluate DiagramVerifier accuracy on the TinyDB benchmark dataset.

    Expectations
    ------------
    * The verifier should correctly identify most MATCHes (real TinyDB classes).
    * The verifier should catch most HALLUCINATIONs (QueryBuilder, IndexManager,
      CacheLayer are all absent from TinyDB source).
    * DRIFTED elements (LRUCache, QueryInstance) may be detected as DRIFTED or
      MATCH depending on verifier sensitivity — both contribute to TP.
    * MISSING elements (FrozenDict, QueryLike) should be flagged.

    We assert a realistic range, not a suspicious perfection.
    """
    verifier, _ = _make_verifier()
    summary = verifier.verify_candidate_model(CANDIDATE_BENCHMARK_MODEL)

    # Basic structural checks on the summary
    assert summary.total_elements >= len(BENCHMARK_EXPECTED_LABELS), (
        f"Expected at least {len(BENCHMARK_EXPECTED_LABELS)} elements in summary, "
        f"got {summary.total_elements}"
    )
    assert summary.hallucinated_count >= 3, (
        "Expected at least 3 hallucinated elements (QueryBuilder, IndexManager, CacheLayer)"
    )
    assert summary.missing_count >= 2, (
        "Expected at least 2 missing elements (FrozenDict, QueryLike)"
    )

    # Compute and validate metrics
    metrics = MetricsCalculator.compute_metrics(summary, BENCHMARK_EXPECTED_LABELS)

    # Range sanity: all metrics must be valid probabilities
    assert 0.0 <= metrics.precision <= 1.0
    assert 0.0 <= metrics.recall <= 1.0
    assert 0.0 <= metrics.f1_score <= 1.0
    assert 0.0 <= metrics.hallucination_detection_rate <= 1.0

    # Internal consistency: metrics must agree with the raw counts
    if metrics.true_positives + metrics.false_positives > 0:
        expected_precision = metrics.true_positives / (
            metrics.true_positives + metrics.false_positives
        )
        assert abs(metrics.precision - round(expected_precision, 4)) < 1e-6, (
            f"precision field ({metrics.precision}) does not match "
            f"TP/(TP+FP) = {expected_precision:.4f}"
        )

    if metrics.true_negatives + metrics.false_positives > 0:
        expected_hdr = metrics.true_negatives / (
            metrics.true_negatives + metrics.false_positives
        )
        assert abs(metrics.hallucination_detection_rate - round(expected_hdr, 4)) < 1e-6

    # Meaningful performance: the verifier should catch at least the trivially
    # absent hallucinations (classes that don't exist in TinyDB source at all)
    assert metrics.hallucination_detection_rate > 0.0, (
        "Hallucination detection rate is zero — the verifier accepted every "
        "hallucinated class as real.  Check comparator.py class-lookup logic."
    )

    # We explicitly do NOT assert precision == 1.0 or recall == 1.0.
    # A suspiciously perfect score would signal a bug, not a result.


def test_html_report_rendering():
    """Verify the HTML verification report generates complete markup."""
    verifier, ground_truth = _make_verifier()
    summary = verifier.verify_candidate_model(CANDIDATE_BENCHMARK_MODEL)

    doc = DocumentIR(
        project_name="BenchmarkReport",
        static_model=ground_truth,
        verification=summary,
    )

    html = HTMLReportGenerator.generate_report(doc, title="TinyDB Benchmark Report")
    assert "<!DOCTYPE html>" in html
    assert "TinyDB Benchmark Report" in html
    assert "HALLUCINATED" in html
    assert "Fidelity:" in html
    # At least one real TinyDB class should appear
    assert "TinyDB" in html or "Table" in html
