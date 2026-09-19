"""Curated benchmark dataset with known verification ground truth.

Design notes
------------
This dataset is built around the **real** TinyDB codebase
(``data/repos/tinydb/tinydb/``) which the ASTStaticExtractor can parse as a
ground-truth oracle.

Element inventory (13 labelled elements — honest count):
  MATCH       : TinyDB, Table, Storage, MemoryStorage, JSONStorage, Document  (6)
  HALLUCINATED: QueryBuilder, IndexManager, CacheLayer                        (3)
  DRIFTED     : LRUCache (wrong method count on 'get'), QueryInstance (wrong  (2)
                signature on '__call__')
  MISSING     : FrozenDict, QueryLike                                         (2)
                                                                        Total: 13

Hallucination realism
---------------------
All three hallucinated classes use *plausible* TinyDB-adjacent names that a
language model could plausibly generate.  They are NOT in the ``fake.*``
namespace — they look like real TinyDB classes.

Limitations (documented for thesis)
------------------------------------
* This is a hand-authored benchmark, not output from a real LLM call.
* The hallucinations were designed by the same author as the verifier, which
  introduces potential leakage bias.  See ``tests/test_tinydb_verifier_integration.py``
  for a more realistic evaluation.
* Perfect verifier scores on this fixture are NOT expected or asserted; see
  ``tests/test_verifier_metrics.py`` for what is actually checked.
"""

from typing import Dict
from umldoc.ir.base import ElementKind, VerificationStatus
from umldoc.ir.static_model import (
    AttributeIR,
    ClassIR,
    MethodIR,
    ParameterIR,
    StaticModelIR,
)

# ---------------------------------------------------------------------------
# Candidate model: simulates an LLM-generated diagram of TinyDB
# ---------------------------------------------------------------------------
CANDIDATE_BENCHMARK_MODEL = StaticModelIR(
    project_name="TinyDB-BenchmarkEvaluation",
    classes=[
        # ---- MATCH: TinyDB (real class, correct key methods) ----
        ClassIR(
            id="tinydb.database.TinyDB",
            name="TinyDB",
            qualified_name="tinydb.database.TinyDB",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(
                    id="TinyDB.table",
                    name="table",
                    parameters=[ParameterIR(name="name")],
                    return_type="Table",
                ),
                MethodIR(
                    id="TinyDB.tables",
                    name="tables",
                    parameters=[],
                    return_type="set[str]",
                ),
                MethodIR(
                    id="TinyDB.close",
                    name="close",
                    parameters=[],
                    return_type="None",
                ),
            ],
        ),
        # ---- MATCH: Table (real class, correct public interface) ----
        ClassIR(
            id="tinydb.table.Table",
            name="Table",
            qualified_name="tinydb.table.Table",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(
                    id="Table.insert",
                    name="insert",
                    parameters=[ParameterIR(name="document")],
                    return_type="int",
                ),
                MethodIR(
                    id="Table.search",
                    name="search",
                    parameters=[ParameterIR(name="cond")],
                    return_type="list[Document]",
                ),
                MethodIR(
                    id="Table.all",
                    name="all",
                    parameters=[],
                    return_type="list[Document]",
                ),
            ],
        ),
        # ---- MATCH: Storage (real abstract base class) ----
        ClassIR(
            id="tinydb.storages.Storage",
            name="Storage",
            qualified_name="tinydb.storages.Storage",
            kind=ElementKind.INTERFACE,
            is_abstract=True,
            methods=[
                MethodIR(
                    id="Storage.read",
                    name="read",
                    parameters=[],
                    return_type="Optional[dict]",
                ),
                MethodIR(
                    id="Storage.write",
                    name="write",
                    parameters=[ParameterIR(name="data")],
                    return_type="None",
                ),
            ],
        ),
        # ---- MATCH: MemoryStorage (real class, correct interface) ----
        ClassIR(
            id="tinydb.storages.MemoryStorage",
            name="MemoryStorage",
            qualified_name="tinydb.storages.MemoryStorage",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(
                    id="MemoryStorage.read",
                    name="read",
                    parameters=[],
                    return_type="Optional[dict]",
                ),
                MethodIR(
                    id="MemoryStorage.write",
                    name="write",
                    parameters=[ParameterIR(name="data")],
                    return_type="None",
                ),
            ],
        ),
        # ---- MATCH: JSONStorage (real class) ----
        ClassIR(
            id="tinydb.storages.JSONStorage",
            name="JSONStorage",
            qualified_name="tinydb.storages.JSONStorage",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(
                    id="JSONStorage.read",
                    name="read",
                    parameters=[],
                    return_type="Optional[dict]",
                ),
                MethodIR(
                    id="JSONStorage.write",
                    name="write",
                    parameters=[ParameterIR(name="data")],
                    return_type="None",
                ),
                MethodIR(
                    id="JSONStorage.close",
                    name="close",
                    parameters=[],
                    return_type="None",
                ),
            ],
        ),
        # ---- MATCH: Document (real class) ----
        ClassIR(
            id="tinydb.table.Document",
            name="Document",
            qualified_name="tinydb.table.Document",
            kind=ElementKind.CLASS,
            methods=[],
        ),
        # ---- DRIFTED: LRUCache — 'get' signature wrong (extra param invented) ----
        # Real: get(self, key, default=None) → Optional[V|D]   (2 params)
        # Candidate: get(self, key, default, expire_seconds)    (3 params — hallucinated)
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
                        ParameterIR(name="expire_seconds"),  # invented
                    ],
                    return_type="Optional[V]",
                ),
                MethodIR(
                    id="LRUCache.set",
                    name="set",
                    parameters=[ParameterIR(name="key"), ParameterIR(name="value")],
                    return_type="None",
                ),
            ],
        ),
        # ---- DRIFTED: QueryInstance — '__call__' given extra 'strict' param ----
        # Real: __call__(self, value: Mapping) -> bool   (1 param)
        # Candidate: __call__(self, value, strict)       (2 params — invented)
        ClassIR(
            id="tinydb.queries.QueryInstance",
            name="QueryInstance",
            qualified_name="tinydb.queries.QueryInstance",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(
                    id="QueryInstance.__call__",
                    name="__call__",
                    parameters=[
                        ParameterIR(name="value"),
                        ParameterIR(name="strict"),  # invented
                    ],
                    return_type="bool",
                ),
            ],
        ),
        # ---- HALLUCINATED: QueryBuilder — plausible name, does not exist ----
        ClassIR(
            id="tinydb.queries.QueryBuilder",
            name="QueryBuilder",
            qualified_name="tinydb.queries.QueryBuilder",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(
                    id="QueryBuilder.build",
                    name="build",
                    parameters=[ParameterIR(name="field"), ParameterIR(name="op")],
                    return_type="QueryInstance",
                ),
                MethodIR(
                    id="QueryBuilder.reset",
                    name="reset",
                    parameters=[],
                    return_type="None",
                ),
            ],
        ),
        # ---- HALLUCINATED: IndexManager — plausible, does not exist ----
        ClassIR(
            id="tinydb.database.IndexManager",
            name="IndexManager",
            qualified_name="tinydb.database.IndexManager",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(
                    id="IndexManager.create_index",
                    name="create_index",
                    parameters=[ParameterIR(name="field")],
                    return_type="None",
                ),
            ],
        ),
        # ---- HALLUCINATED: CacheLayer — plausible, does not exist ----
        ClassIR(
            id="tinydb.utils.CacheLayer",
            name="CacheLayer",
            qualified_name="tinydb.utils.CacheLayer",
            kind=ElementKind.CLASS,
            methods=[
                MethodIR(
                    id="CacheLayer.invalidate",
                    name="invalidate",
                    parameters=[ParameterIR(name="key")],
                    return_type="None",
                ),
            ],
        ),
    ],
)

# ---------------------------------------------------------------------------
# Ground-truth labels for every element that appears in the candidate model
# MISSING elements are listed here too (they are in source, absent in diagram)
# ---------------------------------------------------------------------------
BENCHMARK_EXPECTED_LABELS: Dict[str, VerificationStatus] = {
    # --- Correctly present ---
    "TinyDB":        VerificationStatus.MATCH,
    "Table":         VerificationStatus.MATCH,
    "Storage":       VerificationStatus.MATCH,
    "MemoryStorage": VerificationStatus.MATCH,
    "JSONStorage":   VerificationStatus.MATCH,
    "Document":      VerificationStatus.MATCH,
    # --- Drifted (present but signature wrong) ---
    "LRUCache":      VerificationStatus.DRIFTED,
    "QueryInstance": VerificationStatus.DRIFTED,
    # --- Hallucinated (not present in source at all) ---
    "QueryBuilder":  VerificationStatus.HALLUCINATED,
    "IndexManager":  VerificationStatus.HALLUCINATED,
    "CacheLayer":    VerificationStatus.HALLUCINATED,
    # --- Missing (in source, omitted from candidate diagram) ---
    "FrozenDict":    VerificationStatus.MISSING,
    "QueryLike":     VerificationStatus.MISSING,
}
