"""Hash-lock the blind labels file before running the verifier comparison.

This script computes a SHA-256 hash of the filled-in blind labels file and
writes a .lock file alongside it.  The pytest test reads this lock and verifies
the hash before running the verifier, preventing any (even accidental) label
adjustment after seeing verifier output.

Usage
-----
    # After filling in output/<repo>_llm_blind_labels.json:
    python scripts/lock_labels.py --repo tinydb
    python scripts/lock_labels.py --repo click
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
OUTPUT_DIR = REPO_ROOT / "output"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Hash-lock blind labels file.")
    parser.add_argument("--repo", required=True, help="Repo name (tinydb or click)")
    args = parser.parse_args()

    labels_file = OUTPUT_DIR / f"{args.repo}_llm_blind_labels.json"
    lock_file   = OUTPUT_DIR / f"{args.repo}_llm_blind_labels.lock"

    if not labels_file.exists():
        sys.exit(
            f"[error] Labels file not found: {labels_file}\n"
            f"        Fill in the _TEMPLATE version first, save without _TEMPLATE suffix."
        )

    # Validate the labels file is complete (no __FILL_IN__ remaining)
    content = labels_file.read_text(encoding="utf-8")
    if "__FILL_IN__" in content:
        sys.exit(
            f"[error] Labels file still has '__FILL_IN__' placeholders.\n"
            f"        Complete all verdict fields before locking."
        )

    # Parse and validate verdict values
    data = json.loads(content)
    valid_verdicts = {"MATCH", "HALLUCINATED", "DRIFTED", "OMITTED", "REQUIRED", "INTERNAL_EXCLUDED"}
    bad_entries = []
    for entry in data.get("candidate_classes", []):
        v = entry.get("verdict", "")
        if v not in valid_verdicts:
            bad_entries.append(f"  {entry.get('name', '?')!r}: {v!r}")
    for entry in data.get("omitted_classes", []):
        v = entry.get("verdict", "")
        if v not in valid_verdicts:
            bad_entries.append(f"  {entry.get('name', '?')!r}: {v!r}")
    if bad_entries:
        sys.exit(
            f"[error] Invalid verdict values found:\n" + "\n".join(bad_entries) + "\n"
            f"        Valid values: {sorted(valid_verdicts)}"
        )

    digest = sha256_file(labels_file)
    locked_at = datetime.now(timezone.utc).isoformat()

    lock_data = {
        "repo": args.repo,
        "labels_file": labels_file.name,
        "sha256": digest,
        "locked_at": locked_at,
        "note": (
            "This lock file was written BEFORE any verifier comparison was run. "
            "The SHA-256 hash verifies that the blind labels were not modified "
            "after seeing verifier output."
        ),
    }
    lock_file.write_text(json.dumps(lock_data, indent=2), encoding="utf-8")

    print(f"[lock] {labels_file.name}")
    print(f"  SHA-256: {digest}")
    print(f"  Locked at: {locked_at}")
    print(f"  Lock file: {lock_file}")
    print()
    print("Labels are now locked. Run the evaluation:")
    print(f"  python -m pytest tests/test_llm_real_eval.py -v -s -k {args.repo}")


if __name__ == "__main__":
    main()
