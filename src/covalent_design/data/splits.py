"""Task 14: leakage-aware covalent splits.

Produces split_index.json, leakage_report.json, scaffold_keys.jsonl,
fallback_accounting.json, and manual_review_index.json under ``--out-root``.
"""

from __future__ import annotations

import json
import random
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from covalent_design.contracts import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ContractEnvelope,
    ContractErrorInfo,
    ValidationReceipt,
)

# ---------------------------------------------------------------------------
# SplitPolicy
# ---------------------------------------------------------------------------

DEFAULT_ALGORITHM = "leakage_aware_covalent_splits"
DEFAULT_ALGORITHM_VERSION = "1.0.0"
DEFAULT_RANDOM_SEED = 42
DEFAULT_SPLIT_RATIOS = {"train": 0.8, "val": 0.1, "test": 0.1}

REQUIRED_CORE_LABELS_KEYS = frozenset({
    "bond_type",
    "warhead_type",
    "residue_reaction_family",
    "pdb_id",
})

VALID_SPLITS = frozenset({"train", "val", "test", "excluded"})
CORE_SPLITS = frozenset({"train", "val", "test"})

VALID_FALLBACK_REASONS = frozenset({
    "warhead_unmatched",
    "missing_scaffold_input",
    "missing_protein_cluster_input",
    "manual_review_override",
})

VALID_REVIEW_STATUSES = frozenset({"pending", "approved", "rejected"})


@dataclass
class SplitPolicy:
    algorithm: str = DEFAULT_ALGORITHM
    algorithm_version: str = DEFAULT_ALGORITHM_VERSION
    random_seed: int = DEFAULT_RANDOM_SEED
    split_ratios: dict = field(default_factory=lambda: dict(DEFAULT_SPLIT_RATIOS))

    def to_dict(self) -> dict:
        return {
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
            "random_seed": self.random_seed,
            "split_ratios": dict(self.split_ratios),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SplitPolicy":
        return cls(
            algorithm=d.get("algorithm", DEFAULT_ALGORITHM),
            algorithm_version=d.get("algorithm_version", DEFAULT_ALGORITHM_VERSION),
            random_seed=d.get("random_seed", DEFAULT_RANDOM_SEED),
            split_ratios=d.get("split_ratios", dict(DEFAULT_SPLIT_RATIOS)),
        )

    @classmethod
    def from_json_path(cls, path: Path) -> "SplitPolicy":
        return cls.from_dict(json.loads(path.read_text("utf-8")))


# ---------------------------------------------------------------------------
# records I/O
# ---------------------------------------------------------------------------

def _load_records(records_path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in records_path.read_text("utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# core_labels validation
# ---------------------------------------------------------------------------

def _validate_core_labels(records: list[dict]) -> list[ContractErrorInfo]:
    errors: list[ContractErrorInfo] = []
    for record in records:
        rid = record.get("record_id", "<unknown>")
        cl = record.get("core_labels")
        if cl is None:
            errors.append(ContractErrorInfo(
                code="MISSING_CORE_LABELS",
                owner="data",
                message=f"Record {rid} has no core_labels",
                location=rid,
            ))
            continue
        missing = REQUIRED_CORE_LABELS_KEYS - set(cl)
        if missing:
            errors.append(ContractErrorInfo(
                code="MISSING_CORE_LABEL_FIELDS",
                owner="data",
                message=f"Record {rid} missing core_labels fields: {sorted(missing)}",
                location=rid,
                details={"missing_fields": sorted(missing)},
            ))
    return errors


# ---------------------------------------------------------------------------
# scaffold key derivation (no RDKit - minimal metadata-based)
# ---------------------------------------------------------------------------

SCAFFOLD_KEY_ALGORITHM = "fixture_key"
SCAFFOLD_KEY_ALGORITHM_VERSION = "1.0.0"

# Fields that form the structural identity, excluding PDB-specific fields.
_SCAFFOLD_IDENTITY_FIELDS = (
    "warhead_type",
    "residue_reaction_family",
    "bond_type",
    "ligand_atom_element",
    "ligand_atom_index",
    "ligand_atom_name",
    "target_atom_index",
    "target_atom_name",
)


def _is_warhead_empty(record: dict) -> bool:
    cl = record.get("core_labels", {})
    wt = cl.get("warhead_type")
    return not wt or not str(wt).strip()


def _has_scaffold_input(record: dict) -> bool:
    """Check that the record has the minimum fields for scaffold key derivation."""
    cl = record.get("core_labels", {})
    ligand_atom_element = cl.get("ligand_atom_element")
    ligand_atom_index = cl.get("ligand_atom_index")
    ligand_atom_name = cl.get("ligand_atom_name")
    if ligand_atom_element is None or ligand_atom_index is None or ligand_atom_name is None:
        return False
    target_atom_index = cl.get("target_atom_index")
    target_atom_name = cl.get("target_atom_name")
    if target_atom_index is None or target_atom_name is None:
        return False
    return True


def _has_scaffold_artifacts(record: dict) -> bool:
    """Check that required molecular artifacts for scaffold computation exist."""
    artifacts = record.get("artifacts") or []
    artifact_roles = {a.get("role") for a in artifacts}
    required_roles = {"ligand_atom_table", "ligand_bond_table"}
    return required_roles.issubset(artifact_roles)


def _derive_scaffold_key(record: dict) -> tuple[str | None, str | None]:
    """Return (scaffold_key, fallback_reason)."""
    metadata_scaffold_key = (record.get("metadata") or {}).get("scaffold_key")
    if metadata_scaffold_key:
        return (str(metadata_scaffold_key), None)
    if _is_warhead_empty(record):
        return (None, "warhead_unmatched")
    if not _has_scaffold_input(record):
        return (None, "missing_scaffold_input")

    cl = record.get("core_labels", {})
    identity_parts = []
    for field in _SCAFFOLD_IDENTITY_FIELDS:
        identity_parts.append(str(cl.get(field, "")))
    identity_str = "|".join(identity_parts)
    # Use a short hex digest for compact but unique keys.
    key = hashlib.sha256(identity_str.encode()).hexdigest()[:12]
    return (key, None)


def _derive_scaffold_key_artifact(record: dict) -> dict:
    """Produce a scaffold_key artifact dict per the schema."""
    cl = record.get("core_labels", {})
    scaffold_key, fallback_reason = _derive_scaffold_key(record)

    if _is_warhead_empty(record):
        warhead_match = {
            "matched": False,
            "warhead_type": None,
            "warhead_smarts": None,
            "removed_atom_indices": [],
        }
    elif fallback_reason is not None:
        warhead_match = {
            "matched": True,
            "warhead_type": cl.get("warhead_type"),
            "warhead_smarts": None,
            "removed_atom_indices": [],
        }
    else:
        warhead_match = {
            "matched": True,
            "warhead_type": cl.get("warhead_type"),
            "warhead_smarts": None,
            "removed_atom_indices": [],
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "record_id": record["record_id"],
        "role": "scaffold_key",
        "algorithm": SCAFFOLD_KEY_ALGORITHM,
        "algorithm_version": SCAFFOLD_KEY_ALGORITHM_VERSION,
        "warhead_match": warhead_match,
        "scaffold_key": scaffold_key,
        "fallback_reason": fallback_reason,
    }


# ---------------------------------------------------------------------------
# protein cluster helpers
# ---------------------------------------------------------------------------

def _get_protein_cluster_id(record: dict) -> str | None:
    """Extract protein_cluster_id from metadata.

    Returns None when the key is absent; returns the raw string value otherwise
    (including empty strings, which signal missing input).
    """
    meta = record.get("metadata") or {}
    if "protein_cluster_id" not in meta:
        return None
    return meta["protein_cluster_id"]


def _protein_cluster_is_valid(pc_value) -> bool:
    """A valid protein cluster is a non-empty string."""
    return isinstance(pc_value, str) and bool(pc_value.strip())


def _get_manual_review_status(record: dict) -> str | None:
    """Read manual_review_status from metadata if present."""
    return (record.get("metadata") or {}).get("manual_review_status")


# ---------------------------------------------------------------------------
# split assignment
# ---------------------------------------------------------------------------

def _build_assignments(
    records: list[dict],
    policy: SplitPolicy,
    out_root: Path,
) -> tuple[list[dict], list[dict], list[dict], list[dict], int, int]:
    """Build the full assignment table.

    Returns:
      (assignments, scaffold_key_artifacts, scaffold_overlaps,
       protein_cluster_overlaps, fallback_count, manual_review_count)
    """
    rng = random.Random(policy.random_seed)

    # Get manual review statuses and protein cluster info upfront.
    manual_review: dict[str, str | None] = {}
    protein_cluster: dict[str, str | None] = {}
    for rec in records:
        rid = rec["record_id"]
        manual_review[rid] = _get_manual_review_status(rec)
        protein_cluster[rid] = _get_protein_cluster_id(rec)

    # --- fallback reason priority chain ---
    # 1. protein_cluster missing/invalid -> missing_protein_cluster_input
    # 2. scaffold artifacts missing -> missing_scaffold_input
    # 3. warhead empty -> warhead_unmatched
    # 4. manual_review_status present w/o other fallback -> manual_review_override
    fallback_reasons: dict[str, str | None] = {}
    for rec in records:
        rid = rec["record_id"]
        explicit_fallback = (rec.get("metadata") or {}).get("fallback_reason")

        if not _protein_cluster_is_valid(protein_cluster.get(rid)):
            fallback_reasons[rid] = "missing_protein_cluster_input"
        elif not _has_scaffold_artifacts(rec):
            fallback_reasons[rid] = "missing_scaffold_input"
        elif _is_warhead_empty(rec):
            fallback_reasons[rid] = "warhead_unmatched"
        elif explicit_fallback == "manual_review_override":
            fallback_reasons[rid] = "manual_review_override"

    # --- derive scaffold keys ---
    scaffold_keys: dict[str, str | None] = {}
    scaffold_key_artifacts: list[dict] = []
    for rec in records:
        rid = rec["record_id"]
        fr = fallback_reasons.get(rid)
        # Scaffold key is null for: warhead_unmatched, missing_scaffold_input.
        # For missing_protein_cluster_input, scaffold key is derived if possible.
        if fr == "warhead_unmatched" and manual_review.get(rid) == "approved":
            scaffold_keys[rid] = _derive_scaffold_key(rec)[0]
        elif fr in ("warhead_unmatched", "missing_scaffold_input"):
            scaffold_keys[rid] = None
        elif fr == "missing_protein_cluster_input":
            # Derive scaffold key from core_labels if possible.
            if _is_warhead_empty(rec) or not _has_scaffold_input(rec):
                scaffold_keys[rid] = None
            else:
                scaffold_keys[rid] = _derive_scaffold_key(rec)[0]
        else:
            scaffold_keys[rid] = _derive_scaffold_key(rec)[0]

        sk_artifact = _derive_scaffold_key_artifact(rec)
        # Override artifact with resolved scaffold_key.
        sk_artifact["scaffold_key"] = scaffold_keys[rid]
        sk_artifact["fallback_reason"] = fr
        scaffold_key_artifacts.append(sk_artifact)

    # Determine which records are excluded by fallback reasons.
    excluded_record_ids: set[str] = set()
    for rec in records:
        rid = rec["record_id"]
        fr = fallback_reasons.get(rid)
        mr = manual_review.get(rid)
        if fr == "warhead_unmatched":
            if mr != "approved":
                excluded_record_ids.add(rid)
        elif fr == "missing_scaffold_input":
            excluded_record_ids.add(rid)
        elif fr == "missing_protein_cluster_input":
            excluded_record_ids.add(rid)
        elif fr == "manual_review_override":
            if mr != "approved":
                excluded_record_ids.add(rid)

    # Build scaffold groups from non-excluded records.
    scaffold_groups: dict[str, list[str]] = {}  # scaffold_key -> [record_ids]
    null_scaffold_group: list[str] = []
    for rid in {r["record_id"] for r in records} - excluded_record_ids:
        sk = scaffold_keys.get(rid)
        if sk is None:
            null_scaffold_group.append(rid)
        else:
            scaffold_groups.setdefault(sk, []).append(rid)

    # Assign scaffold groups to splits.
    split_names = ["train", "val", "test"]
    ratios = policy.split_ratios
    total = sum(len(v) for v in scaffold_groups.values()) + len(null_scaffold_group)
    if total == 0:
        # Everything is excluded.
        pass

    # Collect scaffold group keys and shuffle.
    group_keys = list(scaffold_groups.keys())
    rng.shuffle(group_keys)

    # Greedy assignment of scaffold groups to splits.
    split_assignments: dict[str, str] = {}  # record_id -> split
    split_counts: dict[str, int] = {s: 0 for s in split_names}

    for sk in group_keys:
        group_records = scaffold_groups[sk]
        group_size = len(group_records)
        # Pick the split that's most under-represented relative to target.
        best_split = min(
            split_names,
            key=lambda s: split_counts[s] / max(total, 1) - ratios.get(s, 0.0),
        )
        for rid in group_records:
            split_assignments[rid] = best_split
        split_counts[best_split] += group_size

    # Handle null-scaffold records (approved warhead_unmatched, etc.).
    if null_scaffold_group:
        for rid in null_scaffold_group:
            best_split = min(
                split_names,
                key=lambda s: split_counts[s] / max(total, 1) - ratios.get(s, 0.0),
            )
            split_assignments[rid] = best_split
            split_counts[best_split] += 1

    # --- protein cluster integrity correction ---
    # Build protein cluster -> records mapping (only for non-excluded).
    pc_to_records: dict[str, list[str]] = {}
    for rid, split_name in split_assignments.items():
        pc = protein_cluster.get(rid)
        if pc:
            pc_to_records.setdefault(pc, []).append(rid)

    # Detect violations.
    scaffold_to_split: dict[str, str] = {}
    for sk, rids in scaffold_groups.items():
        if rids:
            scaffold_to_split[sk] = split_assignments.get(rids[0], "excluded")

    pc_violations: list[tuple[str, list[str], set[str]]] = []
    for pc, rids in pc_to_records.items():
        splits_set = {split_assignments.get(rid, "excluded") for rid in rids}
        if len(splits_set) > 1:
            pc_violations.append((pc, rids, splits_set))

    # Correct protein cluster violations.
    for pc, rids, splits_set in pc_violations:
        # Choose the split with the most records in this cluster.
        split_votes: dict[str, int] = {}
        for rid in rids:
            s = split_assignments.get(rid, "excluded")
            split_votes[s] = split_votes.get(s, 0) + 1
        majority_split = max(split_votes, key=split_votes.get)

        # Check if moving all to majority_split would cause scaffold leakage.
        would_cause_leakage = False
        affected_scaffolds: dict[str, set[str]] = {}
        for rid in rids:
            sk = scaffold_keys.get(rid)
            if sk is None:
                continue
            affected_scaffolds.setdefault(sk, set()).add(rid)
        for sk, sk_rids in affected_scaffolds.items():
            # Check if any of these scaffold-group records are already in a different split.
            for check_rid in (scaffold_groups.get(sk) or []):
                if check_rid not in rids:
                    existing_split = split_assignments.get(check_rid)
                    if existing_split is not None and existing_split != majority_split:
                        would_cause_leakage = True
                        break
            if would_cause_leakage:
                break

        if would_cause_leakage:
            # Move all records in this cluster to excluded.
            for rid in rids:
                old_split = split_assignments.pop(rid, None)
                if old_split:
                    split_counts[old_split] -= 1
                excluded_record_ids.add(rid)
        else:
            for rid in rids:
                old_split = split_assignments.get(rid)
                if old_split != majority_split:
                    if old_split:
                        split_counts[old_split] -= 1
                    split_assignments[rid] = majority_split
                    split_counts[majority_split] += 1

    # --- detect scaffold leakage in final assignments ---
    scaffold_overlaps: list[dict] = []
    scaffold_split_map: dict[str, set[str]] = {}
    for rid, s in split_assignments.items():
        sk = scaffold_keys.get(rid)
        if sk is None:
            continue
        scaffold_split_map.setdefault(sk, set()).add(s)

    for sk, splits_set in scaffold_split_map.items():
        if len(splits_set) > 1:
            scaffold_overlaps.append({
                "scaffold_key": sk,
                "overlapping_splits": sorted(splits_set),
                "record_ids": sorted(
                    rid for rid in split_assignments
                    if scaffold_keys.get(rid) == sk
                ),
            })

    # --- detect protein cluster leakage ---
    protein_cluster_overlaps: list[dict] = []
    final_pc_map: dict[str, set[str]] = {}
    for rid, s in split_assignments.items():
        pc = protein_cluster.get(rid)
        if not pc:
            continue
        final_pc_map.setdefault(pc, set()).add(s)

    for pc, splits_set in final_pc_map.items():
        if len(splits_set) > 1:
            protein_cluster_overlaps.append({
                "protein_cluster_id": pc,
                "overlapping_splits": sorted(splits_set),
                "record_ids": sorted(
                    rid for rid in split_assignments
                    if protein_cluster.get(rid) == pc
                ),
            })

    # --- build final assignments ---
    assignments: list[dict] = []
    for rec in records:
        rid = rec["record_id"]
        if rid in excluded_record_ids:
            s = "excluded"
        else:
            s = split_assignments.get(rid, "excluded")

        sk = scaffold_keys.get(rid)
        # For excluded with missing scaffold, scaffold_key stays None.
        # For excluded warhead_unmatched, also None.

        fr = fallback_reasons.get(rid)
        mr = manual_review.get(rid)

        # Verify that unapproved warhead_unmatched is excluded.
        if fr == "warhead_unmatched" and mr != "approved" and s != "excluded":
            s = "excluded"

        assignments.append({
            "record_id": rid,
            "split": s,
            "scaffold_key": sk,
            "protein_cluster_id": protein_cluster.get(rid),
            "residue_reaction_family": (rec.get("core_labels") or {}).get(
                "residue_reaction_family", ""
            ),
            "fallback_reason": fr,
            "manual_review_status": mr,
        })

    # Count fallbacks.
    fallback_count = sum(1 for a in assignments if a["fallback_reason"] is not None)
    manual_review_count = sum(
        1 for a in assignments if a["manual_review_status"] is not None
    )

    return (
        assignments,
        scaffold_key_artifacts,
        scaffold_overlaps,
        protein_cluster_overlaps,
        fallback_count,
        manual_review_count,
    )


# ---------------------------------------------------------------------------
# output writers
# ---------------------------------------------------------------------------

def _write_split_index(
    out_root: Path,
    assignments: list[dict],
    policy: SplitPolicy,
) -> None:
    index = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "split_index",
        "split_policy": policy.to_dict(),
        "assignment_count": len(assignments),
        "assignments": assignments,
    }
    (out_root / "split_index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), "utf-8"
    )


def _write_leakage_report(
    out_root: Path,
    assignments: list[dict],
    scaffold_overlaps: list[dict],
    protein_cluster_overlaps: list[dict],
    fallback_count: int,
    manual_review_count: int,
) -> None:
    counts = {"train": 0, "val": 0, "test": 0, "excluded": 0}
    fallback_by_reason: dict[str, int] = {}
    for a in assignments:
        counts[a["split"]] += 1
        fr = a.get("fallback_reason")
        if fr:
            fallback_by_reason[fr] = fallback_by_reason.get(fr, 0) + 1

    report = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "leakage_report",
        "record_count": len(assignments),
        "train_count": counts["train"],
        "val_count": counts["val"],
        "test_count": counts["test"],
        "excluded_count": counts["excluded"],
        "fallback_count": fallback_count,
        "fallback_by_reason": fallback_by_reason,
        "manual_review_count": manual_review_count,
        "scaffold_overlaps": scaffold_overlaps,
        "protein_cluster_overlaps": protein_cluster_overlaps,
        "zero_overlap": {
            "scaffold": len(scaffold_overlaps) == 0,
            "protein_cluster": len(protein_cluster_overlaps) == 0,
        },
    }
    (out_root / "leakage_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), "utf-8"
    )


def _write_scaffold_keys_jsonl(
    out_root: Path,
    scaffold_key_artifacts: list[dict],
) -> None:
    lines = "\n".join(
        json.dumps(a, ensure_ascii=False) for a in scaffold_key_artifacts
    ) + "\n"
    (out_root / "scaffold_keys.jsonl").write_text(lines, "utf-8")


def _write_fallback_accounting(
    out_root: Path,
    assignments: list[dict],
) -> None:
    """Write fallback_accounting.json with per-reason breakdown."""
    fallback_by_reason: dict[str, list[str]] = {}
    for a in assignments:
        fr = a.get("fallback_reason")
        if fr:
            fallback_by_reason.setdefault(fr, []).append(a["record_id"])

    accounting = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "fallback_accounting",
        "fallback_count": sum(len(v) for v in fallback_by_reason.values()),
        "fallback_by_reason": {
            reason: {"count": len(record_ids), "record_ids": sorted(record_ids)}
            for reason, record_ids in fallback_by_reason.items()
        },
    }
    (out_root / "fallback_accounting.json").write_text(
        json.dumps(accounting, indent=2, ensure_ascii=False), "utf-8"
    )


def _write_manual_review_index(
    out_root: Path,
    assignments: list[dict],
) -> None:
    """Write manual_review_index.json."""
    reviewed: list[dict] = []
    for a in assignments:
        if a.get("manual_review_status") is not None and a.get("fallback_reason") is not None:
            reviewed.append({
                "record_id": a["record_id"],
                "split": a["split"],
                "fallback_reason": a.get("fallback_reason"),
                "manual_review_status": a["manual_review_status"],
            })

    index = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "manual_review_index",
        "review_count": len(reviewed),
        "reviewed_records": reviewed,
    }
    (out_root / "manual_review_index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), "utf-8"
    )


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def build_splits(
    records_path: str | Path,
    out_root: str | Path,
    policy: SplitPolicy | None = None,
) -> ContractEnvelope:
    """Build leakage-aware train/val/test splits.

    Args:
        records_path: Path to accepted records JSONL.
        out_root: Directory to write split artifacts.
        policy: Optional SplitPolicy; defaults to 80/10/10, seed 42.

    Returns:
        ContractEnvelope with a list[dict] payload (the assignments) and a
        ValidationReceipt.
    """
    records_path = Path(records_path)
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    if policy is None:
        policy = SplitPolicy()

    # 1. Load records.
    records = _load_records(records_path)
    input_sha256 = _sha256_file(records_path)

    # 2. Validate core_labels.
    validation_errors = _validate_core_labels(records)
    if validation_errors:
        return ContractEnvelope(
            payload=[],
            artifacts=(),
            receipt=ValidationReceipt(
                validator="build_splits",
                contract_version=CONTRACT_VERSION,
                input_sha256=input_sha256,
                ok=False,
                errors=tuple(validation_errors),
            ),
        )

    # 3. Build assignments.
    (
        assignments,
        scaffold_key_artifacts,
        scaffold_overlaps,
        protein_cluster_overlaps,
        fallback_count,
        manual_review_count,
    ) = _build_assignments(records, policy, out_root)

    # 4. Write output artifacts.
    _write_split_index(out_root, assignments, policy)
    _write_leakage_report(
        out_root,
        assignments,
        scaffold_overlaps,
        protein_cluster_overlaps,
        fallback_count,
        manual_review_count,
    )
    _write_scaffold_keys_jsonl(out_root, scaffold_key_artifacts)
    _write_fallback_accounting(out_root, assignments)
    _write_manual_review_index(out_root, assignments)

    return ContractEnvelope(
        payload=assignments,
        artifacts=(),
        receipt=ValidationReceipt(
            validator="build_splits",
            contract_version=CONTRACT_VERSION,
            input_sha256=input_sha256,
            ok=True,
        ),
    )
