"""Drift analyzer comparing structural model evolution across Git revisions."""

from typing import Dict, List, Set
from umldoc.ir.base import ElementKind
from umldoc.ir.static_model import ClassIR, MethodIR, StaticModelIR
from umldoc.ir.verification import DriftChangeType, DriftReportIR, ElementDriftIR


class DriftAnalyzer:
    """Detects architectural and API drift between two codebase revisions."""

    @classmethod
    def analyze_drift(
        cls,
        base_model: StaticModelIR,
        target_model: StaticModelIR,
        base_commit: str = "base",
        target_commit: str = "head",
    ) -> DriftReportIR:
        """Compare base_model and target_model to produce a detailed DriftReportIR."""
        base_classes: Dict[str, ClassIR] = {c.name: c for c in base_model.classes}
        target_classes: Dict[str, ClassIR] = {c.name: c for c in target_model.classes}

        drifted_elements: List[ElementDriftIR] = []
        breaking_count = 0

        # 1. Check for removed classes
        for name, base_cls in base_classes.items():
            if name not in target_classes:
                breaking_count += 1
                drifted_elements.append(
                    ElementDriftIR(
                        element_id=base_cls.id,
                        element_name=name,
                        element_kind=ElementKind.CLASS,
                        change_type=DriftChangeType.REMOVED,
                        base_snapshot=f"class {name}({', '.join(base_cls.bases)})",
                        target_snapshot=None,
                        diff_description=f"Class '{name}' was removed in target commit.",
                        is_breaking=True,
                    )
                )

        # 2. Check for added classes
        for name, target_cls in target_classes.items():
            if name not in base_classes:
                drifted_elements.append(
                    ElementDriftIR(
                        element_id=target_cls.id,
                        element_name=name,
                        element_kind=ElementKind.CLASS,
                        change_type=DriftChangeType.ADDED,
                        base_snapshot=None,
                        target_snapshot=f"class {name}({', '.join(target_cls.bases)})",
                        diff_description=f"New class '{name}' added.",
                        is_breaking=False,
                    )
                )

        # 3. Check for modified classes
        for name in base_classes.keys() & target_classes.keys():
            base_cls = base_classes[name]
            target_cls = target_classes[name]

            # Check inheritance changes
            if set(base_cls.bases) != set(target_cls.bases):
                is_breaking = len(base_cls.bases) > len(target_cls.bases)
                if is_breaking:
                    breaking_count += 1
                drifted_elements.append(
                    ElementDriftIR(
                        element_id=target_cls.id,
                        element_name=name,
                        element_kind=ElementKind.CLASS,
                        change_type=DriftChangeType.MODIFIED_RELATION,
                        base_snapshot=f"bases: {base_cls.bases}",
                        target_snapshot=f"bases: {target_cls.bases}",
                        diff_description=f"Inheritance bases changed for '{name}' from {base_cls.bases} to {target_cls.bases}.",
                        is_breaking=is_breaking,
                    )
                )

            # Check method level drift
            cls._check_method_drift(base_cls, target_cls, drifted_elements)

        total_drift = len(drifted_elements)
        summary = (
            f"Analyzed {len(base_classes)} base classes vs {len(target_classes)} target classes. "
            f"Found {total_drift} drifted elements ({breaking_count} breaking)."
        )

        return DriftReportIR(
            project_name=target_model.project_name or base_model.project_name,
            base_commit=base_commit,
            target_commit=target_commit,
            drifted_elements=drifted_elements,
            breaking_changes_count=breaking_count,
            total_drift_count=total_drift,
            summary_notes=summary,
        )

    @classmethod
    def _check_method_drift(
        cls,
        base_cls: ClassIR,
        target_cls: ClassIR,
        drifted: List[ElementDriftIR],
    ) -> None:
        base_methods: Dict[str, MethodIR] = {m.name: m for m in base_cls.methods}
        target_methods: Dict[str, MethodIR] = {m.name: m for m in target_cls.methods}

        # Removed methods
        for m_name, base_m in base_methods.items():
            if m_name not in target_methods:
                is_pub = base_m.name.startswith("_") is False
                drifted.append(
                    ElementDriftIR(
                        element_id=base_m.id,
                        element_name=f"{base_cls.name}.{m_name}",
                        element_kind=ElementKind.METHOD,
                        change_type=DriftChangeType.REMOVED,
                        base_snapshot=f"def {m_name}(...)",
                        target_snapshot=None,
                        diff_description=f"Method '{m_name}' on '{base_cls.name}' was removed.",
                        is_breaking=is_pub,
                    )
                )

        # Added methods
        for m_name, target_m in target_methods.items():
            if m_name not in base_methods:
                drifted.append(
                    ElementDriftIR(
                        element_id=target_m.id,
                        element_name=f"{target_cls.name}.{m_name}",
                        element_kind=ElementKind.METHOD,
                        change_type=DriftChangeType.ADDED,
                        base_snapshot=None,
                        target_snapshot=f"def {m_name}(...)",
                        diff_description=f"New method '{m_name}' added to '{target_cls.name}'.",
                        is_breaking=False,
                    )
                )

        # Modified signatures
        for m_name in base_methods.keys() & target_methods.keys():
            bm = base_methods[m_name]
            tm = target_methods[m_name]

            b_params = [p.name for p in bm.parameters]
            t_params = [p.name for p in tm.parameters]

            if b_params != t_params or bm.return_type != tm.return_type:
                is_breaking = len(t_params) > len(b_params)  # new required param
                drifted.append(
                    ElementDriftIR(
                        element_id=tm.id,
                        element_name=f"{target_cls.name}.{m_name}",
                        element_kind=ElementKind.METHOD,
                        change_type=DriftChangeType.MODIFIED_SIGNATURE,
                        base_snapshot=f"def {m_name}({', '.join(b_params)}) -> {bm.return_type}",
                        target_snapshot=f"def {m_name}({', '.join(t_params)}) -> {tm.return_type}",
                        diff_description=f"Method signature of '{base_cls.name}.{m_name}' modified.",
                        is_breaking=is_breaking,
                    )
                )
