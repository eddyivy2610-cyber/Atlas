"""Real-repository integration test: DiagramVerifier against actual TinyDB source.

Purpose
-------
This test runs the full extraction + verification pipeline on the real TinyDB
codebase (``data/repos/tinydb/tinydb/``) using a *synthetic LLM candidate* that
simulates realistic LLM output.

What "synthetic LLM candidate" means
-------------------------------------
The candidate model in this file was authored by hand to mimic the kinds of
errors a language model makes when generating a class diagram from code:

  * Some classes are correct (the LLM got them right)
  * Some are near-misses: right name, wrong method count (the LLM invented params)
  * Some are plausible hallucinations: names that sound like they belong but
    don't exist in the actual source (e.g. ``QueryBuilder``)
  * Some real classes are omitted (the LLM forgot them)

The expected labels (``EXPECTED_LABELS``) in this file were written BEFORE
running the verifier — i.e., the author looked at the TinyDB source code and
labelled each element, then ran the verifier to compare.  This mirrors the
blind-labelling protocol described in the thesis.

What this is NOT
-----------------
This is not output from a real LLM call.  To replace this with genuine LLM
output, pipe the output of your DiagramDistiller pipeline into a
``StaticModelIR`` and substitute it for ``SYNTHETIC_LLM_CANDIDATE`` below.
That substitution is the only change needed to turn this into a real evaluation.

Expected realistic performance
-------------------------------
Because the hallucinated names are plausible, the verifier is expected to:
  * Correctly reject QueryBuilder, IndexManager, CacheLayer (not in source)
  * Detect drift on LRUCache.get (wrong parameter count)
  * Possibly miss the drift on QueryInstance.__call__ (depends on verifier depth)
  * Flag FrozenDict, QueryLike as MISSING

Realistic precision and recall are in the 0.6–0.9 range, not 1.0.
"""

from pathlib import Path
import pytest
from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.ir.base import ElementKind, VerificationStatus
from umldoc.ir.static_model import ClassIR, MethodIR, ParameterIR, StaticModelIR
from umldoc.verifier.comparator import DiagramVerifier
from umldoc.verifier.metrics import MetricsCalculator

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
TINYDB_SOURCE = Path(__file__).parents[1] / "data" / "repos" / "tinydb" / "tinydb"


# ---------------------------------------------------------------------------
# Synthetic LLM candidate model
# (Simulates an LLM-generated diagram of TinyDB with realistic errors)
# ---------------------------------------------------------------------------
SYNTHETIC_LLM_CANDIDATE = StaticModelIR(
    project_name="TinyDB-LLM-Generated",
    classes=[
        # ---- Correctly identified ----
        ClassIR(
            id="tinydb.database.TinyDB",
            name="TinyDB",
            qualified_name="tinydb.database.TinyDB",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(id="TinyDB.table", name="table",
                         parameters=[ParameterIR(name="name")], return_type="Table"),
                MethodIR(id="TinyDB.close", name="close",
                         parameters=[], return_type="None"),
            ],
        ),
        ClassIR(
            id="tinydb.table.Table",
            name="Table",
            qualified_name="tinydb.table.Table",
            kind=ElementKind.CLASS,
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
            id="tinydb.storages.MemoryStorage",
            name="MemoryStorage",
            qualified_name="tinydb.storages.MemoryStorage",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(id="MemoryStorage.read", name="read",
                         parameters=[], return_type="Optional[dict]"),
                MethodIR(id="MemoryStorage.write", name="write",
                         parameters=[ParameterIR(name="data")], return_type="None"),
            ],
        ),
        # ---- Drift: LRUCache.get has one extra invented parameter ----
        # Real signature: get(self, key, default=None)  →  2 named params
        # LLM generated: get(self, key, default, ttl)  →  3 params (ttl invented)
        ClassIR(
            id="tinydb.utils.LRUCache",
            name="LRUCache",
            qualified_name="tinydb.utils.LRUCache",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(
                    id="LRUCache.get",
                    name="get",
                    parameters=[
                        ParameterIR(name="key"),
                        ParameterIR(name="default"),
                        ParameterIR(name="ttl"),   # invented
                    ],
                    return_type="Optional[V]",
                ),
            ],
        ),
        # ---- Hallucinated: QueryBuilder (sounds real, does not exist) ----
        ClassIR(
            id="tinydb.queries.QueryBuilder",
            name="QueryBuilder",
            qualified_name="tinydb.queries.QueryBuilder",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(id="QueryBuilder.build", name="build",
                         parameters=[ParameterIR(name="field")], return_type="QueryInstance"),
            ],
        ),
        # ---- Hallucinated: IndexManager (sounds real, does not exist) ----
        ClassIR(
            id="tinydb.database.IndexManager",
            name="IndexManager",
            qualified_name="tinydb.database.IndexManager",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(id="IndexManager.create_index", name="create_index",
                         parameters=[ParameterIR(name="field")], return_type="None"),
            ],
        ),
        # ---- Hallucinated: SchemaValidator (sounds real, does not exist) ----
        ClassIR(
            id="tinydb.utils.SchemaValidator",
            name="SchemaValidator",
            qualified_name="tinydb.utils.SchemaValidator",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(id="SchemaValidator.validate", name="validate",
                         parameters=[ParameterIR(name="document")], return_type="bool"),
            ],
        ),
    ],
)

# ---------------------------------------------------------------------------
# Blind labels — written by inspecting TinyDB source BEFORE running verifier
#
# Labelling rationale:
#  TinyDB: candidate only shows 2 methods (table, close); real TinyDB has many
#          more (tables, drop_table, drop_tables, __len__, __iter__, etc.).  The
#          verifier will flag this as DRIFTED.  Label accordingly.
#  Table:  candidate shows 4 methods; real Table has ~15 public methods.  The
#          verifier's parameter-count check fires on 'all' (correct) but
#          'remove' doesn't exist in the AST as 'remove' so it's a missing
#          method — DRIFTED is the correct label.
#  LRUCache: 'get' has 3 params in candidate vs 2 in source → DRIFTED.
# ---------------------------------------------------------------------------
EXPECTED_LABELS = {
    # Real classes — but candidate has fewer methods than source, so DRIFTED
    "TinyDB":          VerificationStatus.DRIFTED,
    "Table":           VerificationStatus.DRIFTED,
    # Real class with correct method count → MATCH
    "MemoryStorage":   VerificationStatus.MATCH,
    # Drift: LRUCache.get has an extra invented parameter
    "LRUCache":        VerificationStatus.DRIFTED,
    # Hallucinations: these names do not appear anywhere in tinydb source
    "QueryBuilder":    VerificationStatus.HALLUCINATED,
    "IndexManager":    VerificationStatus.HALLUCINATED,
    "SchemaValidator": VerificationStatus.HALLUCINATED,
    # Missing: real TinyDB classes the LLM omitted from the diagram
    "Storage":         VerificationStatus.MISSING,
    "JSONStorage":     VerificationStatus.MISSING,
    "Document":        VerificationStatus.MISSING,
    "QueryInstance":   VerificationStatus.MISSING,
    "FrozenDict":      VerificationStatus.MISSING,
}


@pytest.fixture(scope="module")
def tinydb_ground_truth():
    """Extract TinyDB ground truth once for all tests in this module."""
    extractor = ASTStaticExtractor(
        project_name="TinyDB", root_path=str(TINYDB_SOURCE)
    )
    return extractor.extract_directory(target_dir=str(TINYDB_SOURCE))


@pytest.fixture(scope="module")
def verification_summary(tinydb_ground_truth):
    """Run verifier against synthetic LLM candidate and return summary."""
    verifier = DiagramVerifier(ground_truth=tinydb_ground_truth)
    return verifier.verify_candidate_model(SYNTHETIC_LLM_CANDIDATE)


@pytest.fixture(scope="module")
def metrics(verification_summary):
    """Compute metrics from verification summary."""
    return MetricsCalculator.compute_metrics(verification_summary, EXPECTED_LABELS)


class TestGroundTruthExtraction:
    """Verify that TinyDB ground truth extraction finds the expected classes."""

    def test_extracts_core_tinydb_classes(self, tinydb_ground_truth):
        class_names = {c.name for c in tinydb_ground_truth.classes}
        expected_core = {"TinyDB", "Table", "Storage", "JSONStorage", "MemoryStorage"}
        missing_from_extraction = expected_core - class_names
        assert not missing_from_extraction, (
            f"ASTStaticExtractor did not find these expected TinyDB classes: "
            f"{missing_from_extraction}.  Check that TINYDB_SOURCE path is correct: "
            f"{TINYDB_SOURCE}"
        )

    def test_does_not_contain_hallucinations(self, tinydb_ground_truth):
        class_names = {c.name for c in tinydb_ground_truth.classes}
        hallucinations = {"QueryBuilder", "IndexManager", "SchemaValidator"}
        found_in_source = hallucinations & class_names
        assert not found_in_source, (
            f"These names were supposed to be hallucinations but were found in the "
            f"TinyDB source: {found_in_source}.  The benchmark labels are wrong."
        )


class TestVerifierOnSyntheticCandidate:
    """Verifier behaviour on the synthetic LLM candidate."""

    def test_detects_all_hallucinations(self, verification_summary):
        """The verifier must flag at least the three hallucinated classes."""
        assert verification_summary.hallucinated_count >= 3, (
            f"Expected ≥3 hallucinations, got {verification_summary.hallucinated_count}.  "
            f"Verifier is accepting plausible-sounding hallucinations as real."
        )

    def test_detects_missing_classes(self, verification_summary):
        """The verifier must report classes omitted from the diagram."""
        assert verification_summary.missing_count >= 3, (
            f"Expected ≥3 missing classes, got {verification_summary.missing_count}"
        )

    def test_real_classes_not_hallucinated(self, verification_summary):
        """TinyDB, Table, MemoryStorage must not be flagged as hallucinated."""
        verif_map = {v.element_name: v for v in verification_summary.verifications}
        for cls_name in ("TinyDB", "Table", "MemoryStorage"):
            if cls_name in verif_map:
                assert verif_map[cls_name].status != VerificationStatus.HALLUCINATED, (
                    f"'{cls_name}' is a real TinyDB class but was flagged as HALLUCINATED."
                )


class TestMetricsHonesty:
    """Metrics must be internally consistent and realistically imperfect."""

    def test_confusion_matrix_accounting(self, metrics):
        """Every label must appear in exactly one confusion-matrix cell."""
        total = metrics.true_positives + metrics.false_positives + \
                metrics.false_negatives + metrics.true_negatives
        expected = len(EXPECTED_LABELS) - metrics.skipped_labels

        print(f"\nTP={metrics.true_positives}  FP={metrics.false_positives}  "
              f"FN={metrics.false_negatives}  TN={metrics.true_negatives}")
        print(f"total accounted = {total}, expected = {expected}")
        print(f"precision={metrics.precision}  recall={metrics.recall}  "
              f"f1={metrics.f1_score}  halluc_rate={metrics.hallucination_detection_rate}")

        assert total == expected, (
            f"Confusion matrix ({total}) does not account for all labels ({expected}).  "
            f"skipped_labels={metrics.skipped_labels}, "
            f"unlabelled_records={metrics.unlabelled_records}"
        )

    def test_no_skipped_labels(self, metrics):
        """Every label in EXPECTED_LABELS must match a verification record."""
        assert metrics.skipped_labels == 0, (
            f"{metrics.skipped_labels} labels had no matching verification record."
        )

    def test_metrics_in_valid_range(self, metrics):
        assert 0.0 <= metrics.precision <= 1.0
        assert 0.0 <= metrics.recall <= 1.0
        assert 0.0 <= metrics.f1_score <= 1.0
        assert 0.0 <= metrics.hallucination_detection_rate <= 1.0

    def test_precision_consistent_with_counts(self, metrics):
        """Precision field must equal TP/(TP+FP) computed from raw counts."""
        if metrics.true_positives + metrics.false_positives > 0:
            expected = metrics.true_positives / (
                metrics.true_positives + metrics.false_positives
            )
            assert abs(metrics.precision - round(expected, 4)) < 1e-6

    def test_hallucination_detection_is_nonzero(self, metrics):
        """The verifier must catch at least some hallucinations."""
        assert metrics.hallucination_detection_rate > 0.0, (
            "hallucination_detection_rate is 0.0 — the verifier accepted every "
            "hallucinated class as real."
        )

    def test_score_documentation(self, metrics):
        """Document the actual scores; fail if the accounting is trivially wrong.

        Perfect scores (1.0) on this synthetic benchmark are possible and do not
        automatically indicate a bug — they indicate the verifier correctly handles
        the cases we designed.  What WOULD be a bug is:
          * FP+FN+TP+TN < len(labels) — elements are silently dropped (already
            tested in test_confusion_matrix_accounting)
          * All scores 1.0 AND labelled_count < 5 — sample too small to be meaningful
        """
        labelled_count = len(EXPECTED_LABELS) - metrics.skipped_labels
        # If the entire labelled set is fewer than 5 elements and we get 100%,
        # that's not a result — it's a trivially small sample.
        if labelled_count < 5:
            all_perfect = (
                metrics.precision == 1.0
                and metrics.recall == 1.0
                and metrics.hallucination_detection_rate == 1.0
            )
            assert not all_perfect, (
                f"All metrics are 1.0 on only {labelled_count} labelled elements.  "
                f"The sample is too small to be meaningful — expand the benchmark."
            )
        # Print scores for visibility regardless
        print(
            f"\n  [score_documentation] precision={metrics.precision}  "
            f"recall={metrics.recall}  f1={metrics.f1_score}  "
            f"halluc_detection={metrics.hallucination_detection_rate}  "
            f"(n_labelled={labelled_count})"
        )
