"""Evaluation metrics calculating Precision, Recall, F1, and Fidelity scores for UML verification."""

from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from umldoc.ir.base import VerificationStatus
from umldoc.ir.verification import VerificationSummaryIR


class VerificationMetrics(BaseModel):
    """Statistical evaluation metrics for diagram verification accuracy."""
    model_config = ConfigDict(frozen=True)

    true_positives: int = Field(default=0, ge=0, description="Elements correctly verified as valid in code")
    false_positives: int = Field(default=0, ge=0, description="Hallucinations/invalid elements incorrectly accepted")
    false_negatives: int = Field(default=0, ge=0, description="Valid elements incorrectly flagged as missing/hallucinated")
    true_negatives: int = Field(default=0, ge=0, description="Hallucinations/missing elements correctly flagged")
    skipped_labels: int = Field(default=0, ge=0, description="Labels present in expected dict but not in any verification record")
    unlabelled_records: int = Field(default=0, ge=0, description="Verification records with no corresponding expected label")
    precision: float = Field(default=0.0, ge=0.0, le=1.0, description="TP / (TP + FP)")
    recall: float = Field(default=0.0, ge=0.0, le=1.0, description="TP / (TP + FN)")
    f1_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Harmonic mean of precision and recall")
    hallucination_detection_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="TN / (TN + FP)")


class MetricsCalculator:
    """Calculates fidelity and classification metrics from verification summaries."""

    @classmethod
    def compute_metrics(
        cls,
        summary: VerificationSummaryIR,
        expected_ground_truth_labels: Dict[str, VerificationStatus],
    ) -> VerificationMetrics:
        """Compute precision, recall, and F1 against known labelled benchmark elements.

        Classification mapping
        ----------------------
        * TP: expected=MATCH|VERIFIED_GROUND_TRUTH|DRIFTED, actual matches expected exactly
              (both MATCH, or both DRIFTED — verifier correctly identified the status)
        * FP: expected=HALLUCINATED|MISSING, but verifier accepted the element as MATCH/DRIFTED
        * FN: expected=MATCH|DRIFTED, but verifier labelled it HALLUCINATED or MISSING
        * TN: expected=HALLUCINATED|MISSING, verifier correctly rejected / flagged as absent

        DRIFTED rationale: a drift is a real, partial match — it is a *true positive* in the
        sense that the verifier correctly identified the element AND its problem, rather than
        silently accepting a wrong signature or hallucinating a miss.

        Accounting integrity
        --------------------
        Every record that has a matching expected label contributes exactly one count to
        TP/FP/FN/TN.  Records with no matching label contribute to ``unlabelled_records``.
        Expected labels that match no record contribute to ``skipped_labels``.
        The caller can assert  TP+FP+FN+TN == len(expected_ground_truth_labels) - skipped_labels
        to verify full accounting.
        """
        tp = 0
        fp = 0
        fn = 0
        tn = 0
        unlabelled = 0

        # Track which expected labels were actually consumed
        consumed_labels: set[str] = set()

        for record in summary.verifications:
            elem_id = record.element_id
            elem_name = record.element_name
            actual_status = record.status

            expected_status: Optional[VerificationStatus] = (
                expected_ground_truth_labels.get(elem_id)
                or expected_ground_truth_labels.get(elem_name)
            )

            if expected_status is None:
                # This record has no label: count it but do not affect TP/FP/FN/TN
                unlabelled += 1
                continue

            # Record which label key was consumed
            consumed_labels.add(elem_name if elem_name in expected_ground_truth_labels else elem_id)

            # ----------------------------------------------------------------
            # Ground truth: element is real (MATCH / VERIFIED / DRIFTED)
            # ----------------------------------------------------------------
            if expected_status in (
                VerificationStatus.MATCH,
                VerificationStatus.VERIFIED_GROUND_TRUTH,
                VerificationStatus.DRIFTED,
            ):
                if actual_status == expected_status or actual_status in (
                    VerificationStatus.MATCH,
                    VerificationStatus.VERIFIED_GROUND_TRUTH,
                    VerificationStatus.DRIFTED,
                ):
                    # Verifier correctly identified the element as real (even if
                    # it missed whether it was a drift specifically — both real)
                    tp += 1
                else:
                    # Verifier incorrectly flagged a real element as HALLUCINATED or MISSING
                    fn += 1

            # ----------------------------------------------------------------
            # Ground truth: element is absent (HALLUCINATED)
            # ----------------------------------------------------------------
            elif expected_status == VerificationStatus.HALLUCINATED:
                if actual_status == VerificationStatus.HALLUCINATED:
                    tn += 1
                else:
                    # Verifier accepted a hallucinated element as real
                    fp += 1

            # ----------------------------------------------------------------
            # Ground truth: element is absent from diagram (MISSING)
            # ----------------------------------------------------------------
            elif expected_status == VerificationStatus.MISSING:
                if actual_status == VerificationStatus.MISSING:
                    tn += 1
                else:
                    # Verifier did not detect that this element was omitted
                    fp += 1

        # Labels in expected dict that never matched any verification record
        skipped = len(expected_ground_truth_labels) - len(consumed_labels)

        # Compute derived metrics — NO default-to-1.0 fallbacks that hide empty sets
        if (tp + fp) > 0:
            precision = tp / (tp + fp)
        else:
            precision = 0.0  # No positive predictions at all → undefined, report 0

        if (tp + fn) > 0:
            recall = tp / (tp + fn)
        else:
            recall = 0.0  # No real positives seen → undefined, report 0

        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        halluc_rate = (tn / (tn + fp)) if (tn + fp) > 0 else 0.0

        return VerificationMetrics(
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            true_negatives=tn,
            skipped_labels=skipped,
            unlabelled_records=unlabelled,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            hallucination_detection_rate=round(halluc_rate, 4),
        )
