"""Diagram verifier comparing candidate diagram elements against AST ground truth."""

from typing import Dict, List, Optional
from umldoc.ir.base import ElementKind, VerificationStatus
from umldoc.ir.static_model import ClassIR, MethodIR, StaticModelIR
from umldoc.ir.verification import ElementVerificationIR, VerificationSummaryIR


class DiagramVerifier:
    """Verifies proposed or extracted diagram elements against codebase AST ground truth."""

    def __init__(self, ground_truth: StaticModelIR):
        self.ground_truth = ground_truth
        self._class_map: Dict[str, ClassIR] = {cls.name: cls for cls in ground_truth.classes}
        self._qual_class_map: Dict[str, ClassIR] = {cls.id: cls for cls in ground_truth.classes}

    def verify_candidate_model(self, candidate: StaticModelIR) -> VerificationSummaryIR:
        """Verify an entire candidate StaticModelIR against ground truth."""
        records: List[ElementVerificationIR] = []
        verified_count = 0
        hallucinated_count = 0
        drifted_count = 0

        # Check candidate classes
        candidate_class_names = set()
        for cand_cls in candidate.classes:
            candidate_class_names.add(cand_cls.name)
            gt_cls = self._class_map.get(cand_cls.name) or self._qual_class_map.get(cand_cls.id)

            if gt_cls is None:
                hallucinated_count += 1
                records.append(
                    ElementVerificationIR(
                        element_id=cand_cls.id,
                        element_name=cand_cls.name,
                        element_kind=ElementKind.CLASS,
                        status=VerificationStatus.HALLUCINATED,
                        confidence_score=0.0,
                        evidence=f"Class '{cand_cls.name}' was not found in codebase AST.",
                        issues=[f"No class '{cand_cls.name}' declared in ground truth modules."],
                    )
                )
            else:
                # Class exists, now verify methods & attributes
                cls_issues = []
                method_score = self._verify_methods(cand_cls, gt_cls, cls_issues)

                if cls_issues:
                    drifted_count += 1
                    status = VerificationStatus.DRIFTED
                    conf = max(0.2, method_score)
                else:
                    verified_count += 1
                    status = VerificationStatus.MATCH
                    conf = 1.0

                gt_loc = f"{gt_cls.source_location.file_path}:{gt_cls.source_location.start_line}" if gt_cls.source_location else None
                records.append(
                    ElementVerificationIR(
                        element_id=cand_cls.id,
                        element_name=cand_cls.name,
                        element_kind=ElementKind.CLASS,
                        status=status,
                        confidence_score=conf,
                        ground_truth_ref=gt_loc,
                        evidence=f"Matched AST definition at {gt_loc}" if gt_loc else "Matched AST class.",
                        issues=cls_issues,
                    )
                )

        # Check missing classes (in ground truth but absent in candidate)
        missing_count = 0
        for gt_cls in self.ground_truth.classes:
            if gt_cls.name not in candidate_class_names:
                missing_count += 1
                gt_loc = f"{gt_cls.source_location.file_path}:{gt_cls.source_location.start_line}" if gt_cls.source_location else None
                records.append(
                    ElementVerificationIR(
                        element_id=gt_cls.id,
                        element_name=gt_cls.name,
                        element_kind=ElementKind.CLASS,
                        status=VerificationStatus.MISSING,
                        confidence_score=0.0,
                        ground_truth_ref=gt_loc,
                        evidence="Ground truth class omitted from diagram.",
                        issues=["Element is present in source code but omitted from candidate model."],
                    )
                )

        total = len(records)
        overall_conf = (
            sum(r.confidence_score for r in records) / total if total > 0 else 1.0
        )

        return VerificationSummaryIR(
            total_elements=total,
            verified_count=verified_count,
            hallucinated_count=hallucinated_count,
            missing_count=missing_count,
            drifted_count=drifted_count,
            overall_confidence=round(overall_conf, 3),
            verifications=records,
        )

    def _verify_methods(self, cand_cls: ClassIR, gt_cls: ClassIR, issues: List[str]) -> float:
        """Verify methods on a class, appending discrepancies to issues."""
        gt_method_map: Dict[str, MethodIR] = {m.name: m for m in gt_cls.methods}
        matched = 0

        for cand_m in cand_cls.methods:
            gt_m = gt_method_map.get(cand_m.name)
            if gt_m is None:
                issues.append(f"Method '{cand_m.name}' on '{cand_cls.name}' does not exist in AST.")
            else:
                # Check parameter count
                if len(cand_m.parameters) != len(gt_m.parameters):
                    issues.append(
                        f"Method '{cand_m.name}' parameter mismatch: candidate has {len(cand_m.parameters)}, AST has {len(gt_m.parameters)}."
                    )
                else:
                    matched += 1

        total_methods = len(cand_cls.methods)
        return (matched / total_methods) if total_methods > 0 else 1.0
