"""ETL quality report: reconciles sources, records, candidates, splits, and visual checks.

Public API:
    write_quality_report(processed_root, *, ingest_roots=None,
                         splits_root=None, visual_checks_root=None,
                         out_path=None) -> ContractEnvelope[dict]

The report is a JSON envelope with role ``"quality_report"`` that aggregates
ingest coverage, record reconciliation, family/residue/warhead distributions,
linkage/geometry/protein-state quality, candidate statistics, split statistics,
and visual check summaries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from covalent_design.contracts.errors import ContractErrorInfo
from covalent_design.contracts.types import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    ContractEnvelope,
    Provenance,
    ValidationReceipt,
)
from covalent_design.io.jsonl import read_jsonl

_VALIDATOR_NAME = "covalent_design.data.write_quality_report"


def write_quality_report(
    processed_root: Path,
    *,
    ingest_roots: Optional[list[Path]] = None,
    splits_root: Optional[Path] = None,
    visual_checks_root: Optional[Path] = None,
    out_path: Optional[Path] = None,
) -> ContractEnvelope[dict]:
    errors: list[ContractErrorInfo] = []

    if not processed_root.exists():
        errors.append(
            ContractErrorInfo(
                code="PROCESSED_ROOT_NOT_FOUND",
                owner="data",
                message=f"processed_root does not exist: {processed_root}",
                location=str(processed_root),
            )
        )
        return _envelope({}, errors)

    records_path = processed_root / "records.jsonl"
    if not records_path.exists():
        errors.append(
            ContractErrorInfo(
                code="RECORDS_FILE_NOT_FOUND",
                owner="data",
                message=f"records.jsonl not found in processed_root: {records_path}",
                location=str(records_path),
            )
        )
        return _envelope({}, errors)

    try:
        accepted_records = list(read_jsonl(records_path))
    except Exception as exc:
        errors.append(
            ContractErrorInfo(
                code="RECORDS_UNREADABLE",
                owner="data",
                message=f"Failed to read records.jsonl: {exc}",
                location=str(records_path),
            )
        )
        return _envelope({}, errors)

    rejected_path = processed_root / "rejected_index.jsonl"
    rejected_records: list[dict] = []
    if rejected_path.exists():
        try:
            rejected_records = list(read_jsonl(rejected_path))
        except Exception as exc:
            errors.append(
                ContractErrorInfo(
                    code="REJECTED_INDEX_UNREADABLE",
                    owner="data",
                    message=f"Failed to read rejected_index.jsonl: {exc}",
                    location=str(rejected_path),
                )
            )
            rejected_records = []

    conflict_path = processed_root / "conflict_index.jsonl"
    conflict_records: list[dict] = []
    if conflict_path.exists():
        try:
            conflict_records = list(read_jsonl(conflict_path))
        except Exception as exc:
            errors.append(
                ContractErrorInfo(
                    code="CONFLICT_INDEX_UNREADABLE",
                    owner="data",
                    message=f"Failed to read conflict_index.jsonl: {exc}",
                    location=str(conflict_path),
                )
            )
            conflict_records = []

    accepted_count = len(accepted_records)
    rejected_count = len(rejected_records)
    conflict_count = len(conflict_records)
    total_accounted = accepted_count + rejected_count + conflict_count

    # -- source coverage --------------------------------------------------
    source_coverage: dict[str, dict] = {}
    if ingest_roots:
        for root in ingest_roots:
            idx_path = root / "ingest_index.json"
            if not idx_path.exists():
                source_name = root.name
                source_coverage[source_name] = {
                    "complete_for_v1": False,
                    "record_count": 0,
                    "failure_count": 0,
                    "missing_ingest_index": True,
                }
                continue
            try:
                idx = json.loads(idx_path.read_text(encoding="utf-8"))
            except Exception:
                source_name = root.name
                source_coverage[source_name] = {
                    "complete_for_v1": False,
                    "record_count": 0,
                    "failure_count": 0,
                    "unreadable_ingest_index": True,
                }
                continue
            source_name = idx.get("source_database", root.name)
            source_coverage[source_name] = {
                "complete_for_v1": idx.get("complete_for_v1", False),
                "record_count": idx.get("record_count", 0),
                "failure_count": idx.get("failure_count", 0),
            }

    # -- visual check summary --------------------------------------------
    all_complete = all(
        v.get("complete_for_v1", False)
        for v in source_coverage.values()
    )

    visual_blocked_count = 0
    visual_check_summary: dict = {}

    if visual_checks_root is not None:
        vc_index_path = visual_checks_root / "visual_check_index.json"
        if vc_index_path.exists():
            try:
                vc_index = json.loads(vc_index_path.read_text(encoding="utf-8"))
                visual_check_summary = _build_visual_check_summary(vc_index)
                visual_blocked_count = visual_check_summary.get("blocking_counts", {}).get(
                    "blocking_first_core", 0
                )
            except Exception as exc:
                errors.append(
                    ContractErrorInfo(
                        code="VISUAL_CHECK_INDEX_UNREADABLE",
                        owner="data",
                        message=f"Failed to read visual_check_index.json: {exc}",
                        location=str(vc_index_path),
                    )
                )
                visual_check_summary = _empty_visual_summary()
        else:
            visual_check_summary = _empty_visual_summary()
    else:
        visual_check_summary = _empty_visual_summary()

    # -- distributions ----------------------------------------------------
    family_dist: dict[str, int] = {}
    residue_dist: dict[str, int] = {}
    warhead_dist: dict[str, int] = {}
    bond_type_dist: dict[str, int] = {}
    linkage_count_dist: dict[str, int] = {}
    quality_tier_dist: dict[str, int] = {}

    for rec in accepted_records:
        core = rec.get("core_labels", {})
        if isinstance(core, dict):
            fam = core.get("residue_reaction_family")
            if fam:
                family_dist[str(fam)] = family_dist.get(str(fam), 0) + 1
            # Derive residue from family token (for example, CYS_Michael_addition -> CYS).
            if fam and "_" in str(fam):
                residue = str(fam).split("_")[0]
                residue_dist[residue] = residue_dist.get(residue, 0) + 1
            wh = core.get("warhead_type")
            if wh:
                warhead_dist[str(wh)] = warhead_dist.get(str(wh), 0) + 1
            bt = core.get("bond_type")
            if bt:
                bond_type_dist[str(bt)] = bond_type_dist.get(str(bt), 0) + 1

        meta = rec.get("metadata", {})
        if isinstance(meta, dict):
            quality = meta.get("quality", {})
            if isinstance(quality, dict):
                tier = quality.get("quality_tier")
                if tier:
                    quality_tier_dist[str(tier)] = quality_tier_dist.get(str(tier), 0) + 1
        if isinstance(core, dict):
            # Count per-record linkage count (always 1 for monodentate).
            linkage_count_dist["1"] = linkage_count_dist.get("1", 0) + 1

    # -- linkage quality --------------------------------------------------
    linkage_quality = {
        "bond_type_distribution": bond_type_dist,
        "linkage_count_distribution": linkage_count_dist,
    }

    # -- geometry quality -------------------------------------------------
    geo_stats = _build_geometry_quality(accepted_records)

    # -- protein chemical-state quality ------------------------------------
    pcs = _build_protein_chemical_state_quality(accepted_records)

    # -- candidate stats ---------------------------------------------------
    candidate_stats = _build_candidate_stats(processed_root, accepted_records)

    # -- split stats -------------------------------------------------------
    split_stats: dict = {}
    if splits_root is not None:
        split_stats = _build_split_stats(splits_root)

    # -- reconciliation ---------------------------------------------------
    candidate_coverage_ok = candidate_stats.get("record_count", 0) == accepted_count
    split_counts_match = True
    if splits_root is not None:
        split_total = (
            split_stats.get("train_count", 0)
            + split_stats.get("val_count", 0)
            + split_stats.get("test_count", 0)
            + split_stats.get("excluded_count", 0)
        )
        split_counts_match = split_total == accepted_count
    visual_counts_match = True
    if visual_checks_root is not None:
        status_counts = visual_check_summary.get("status_counts", {})
        blocking_counts = visual_check_summary.get("blocking_counts", {})
        sampled_count = visual_check_summary.get("sampled_count", 0)
        visual_counts_match = (
            visual_check_summary.get("total_accepted", accepted_count) == accepted_count
            and sum(status_counts.values()) == sampled_count
            and (
                blocking_counts.get("blocking_first_core", 0)
                + blocking_counts.get("non_blocking", 0)
            )
            == sampled_count
        )
    reconciled = candidate_coverage_ok and split_counts_match and visual_counts_match

    reconciliation = {
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "conflict_count": conflict_count,
        "visual_blocked_count": visual_blocked_count,
        "total_accounted": total_accounted,
        "all_sources_complete_for_v1": all_complete,
        "candidate_coverage_ok": candidate_coverage_ok,
        "split_counts_match": split_counts_match,
        "visual_counts_match": visual_counts_match,
        "reconciled": reconciled,
    }

    # -- quality tier distribution -----------------------------------------
    # (already computed above)

    # -- assemble report ---------------------------------------------------
    report: dict = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "quality_report",
        "source_coverage": source_coverage,
        "reconciliation": reconciliation,
        "family_distribution": family_dist,
        "residue_distribution": residue_dist,
        "warhead_distribution": warhead_dist,
        "linkage_quality": linkage_quality,
        "geometry_quality": geo_stats,
        "protein_chemical_state_quality": pcs,
        "candidate_stats": candidate_stats,
        "quality_tier_distribution": quality_tier_dist,
    }
    if splits_root is not None:
        report["split_stats"] = split_stats
    if visual_checks_root is not None:
        report["visual_check_summary"] = visual_check_summary

    # -- write output ------------------------------------------------------
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        out_path.write_text(payload, encoding="utf-8")

    if not all_complete and len(source_coverage) > 0:
        errors.append(
            ContractErrorInfo(
                code="SOURCE_COVERAGE_INCOMPLETE",
                owner="data",
                message="One or more per-source complete_for_v1 coverage signals are false.",
            )
        )
    if not reconciled:
        errors.append(
            ContractErrorInfo(
                code="COUNT_RECONCILIATION_FAILED",
                owner="data",
                message="One or more count reconciliation equations failed.",
            )
        )

    return _envelope(report, errors)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _envelope(payload: dict, errors: list[ContractErrorInfo]) -> ContractEnvelope[dict]:
    return ContractEnvelope(
        payload=payload,
        artifacts=(),
        receipt=ValidationReceipt(
            validator=_VALIDATOR_NAME,
            contract_version=CONTRACT_VERSION,
            input_sha256="",
            passed=not errors,
            errors=tuple(errors),
        ),
        provenance=Provenance(producer_name="covalent_design"),
    )


def _build_geometry_quality(records: list[dict]) -> dict:
    bond_lengths: list[float] = []
    protein_angles: list[float] = []
    ligand_angles: list[float] = []

    for rec in records:
        meta = rec.get("metadata", {})
        if not isinstance(meta, dict):
            continue
        geo = meta.get("geometry")
        if not isinstance(geo, dict):
            continue

        bl = geo.get("bond_length")
        if isinstance(bl, dict) and bl.get("value") is not None:
            bond_lengths.append(float(bl["value"]))

        pa = geo.get("protein_side_angle")
        if isinstance(pa, dict) and pa.get("value") is not None:
            protein_angles.append(float(pa["value"]))

        la = geo.get("ligand_side_angle")
        if isinstance(la, dict) and la.get("value") is not None:
            ligand_angles.append(float(la["value"]))

    missing = 0
    for rec in records:
        meta = rec.get("metadata", {})
        if not isinstance(meta, dict):
            missing += 1
            continue
        geo = meta.get("geometry")
        if not isinstance(geo, dict):
            missing += 1
            continue
        has_any = False
        for key in ("bond_length", "protein_side_angle", "ligand_side_angle"):
            v = geo.get(key)
            if isinstance(v, dict) and v.get("value") is not None:
                has_any = True
                break
        if not has_any:
            missing += 1

    def _stats(values: list[float]) -> dict:
        if not values:
            return {"min": None, "max": None, "mean": None, "count": 0}
        return {
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "mean": round(sum(values) / len(values), 4),
            "count": len(values),
        }

    return {
        "bond_length": _stats(bond_lengths),
        "protein_side_angle": _stats(protein_angles),
        "ligand_side_angle": _stats(ligand_angles),
        "records_missing_geometry": missing,
    }


def _build_protein_chemical_state_quality(records: list[dict]) -> dict:
    explicit = 0
    inferred = 0
    inferred_ids: list[str] = []

    for rec in records:
        meta = rec.get("metadata", {})
        if isinstance(meta, dict):
            state = meta.get("protein_chemical_state", "")
            if state == "explicit":
                explicit += 1
            elif state == "inferred":
                inferred += 1
                inferred_ids.append(str(rec.get("record_id", "")))

    return {
        "explicit_state_count": explicit,
        "inferred_state_count": inferred,
        "records_with_inferred_state": inferred_ids,
    }


def _build_candidate_stats(processed_root: Path, records: list[dict]) -> dict:
    total_candidates = 0
    total_natural = 0
    total_forced = 0
    empty_window_count = 0
    record_count = 0

    for rec in records:
        rec_id = rec.get("record_id", "")
        ec_path = processed_root / "artifacts" / str(rec_id) / "edge_candidates.json"
        if not ec_path.exists():
            continue
        try:
            ec = json.loads(ec_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        record_count += 1
        denom = ec.get("denominators", {})
        if isinstance(denom, dict):
            total_candidates += denom.get("candidate_count", 0)
            total_natural += denom.get("natural_candidate_count", 0)
            total_forced += denom.get("forced_positive_count", 0)
        if ec.get("empty_radius_window", False):
            empty_window_count += 1

    return {
        "total_candidates": total_candidates,
        "total_natural_candidates": total_natural,
        "total_forced_positives": total_forced,
        "empty_radius_window_count": empty_window_count,
        "record_count": record_count,
    }


def _build_split_stats(splits_root: Path) -> dict:
    idx_path = splits_root / "split_index.json"
    if not idx_path.exists():
        return {
            "train_count": 0,
            "val_count": 0,
            "test_count": 0,
            "excluded_count": 0,
            "fallback_count": 0,
        }
    try:
        si = json.loads(idx_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "train_count": 0,
            "val_count": 0,
            "test_count": 0,
            "excluded_count": 0,
            "fallback_count": 0,
        }

    assignments = si.get("assignments", [])
    counts: dict[str, int] = {"train": 0, "val": 0, "test": 0, "excluded": 0}
    fallback = 0
    for a in assignments:
        split = a.get("split", "excluded")
        counts[split] = counts.get(split, 0) + 1
        if a.get("fallback_reason"):
            fallback += 1

    return {
        "train_count": counts["train"],
        "val_count": counts["val"],
        "test_count": counts["test"],
        "excluded_count": counts["excluded"],
        "fallback_count": fallback,
    }


def _build_visual_check_summary(vc_index: dict) -> dict:
    sample_policy = vc_index.get("sample_policy", {})
    status_counts = vc_index.get("status_counts", {})
    blocking_counts = vc_index.get("blocking_counts", {})
    records = vc_index.get("records", [])

    return {
        "sampled_count": len(records),
        "total_accepted": sample_policy.get("total_accepted", len(records)),
        "status_counts": {
            "pending": status_counts.get("pending", 0),
            "pass": status_counts.get("pass", 0),
            "fail": status_counts.get("fail", 0),
            "needs_rule_review": status_counts.get("needs_rule_review", 0),
        },
        "blocking_counts": {
            "blocking_first_core": blocking_counts.get("blocking_first_core", 0),
            "non_blocking": blocking_counts.get("non_blocking", 0),
        },
    }


def _empty_visual_summary() -> dict:
    return {
        "sampled_count": 0,
        "total_accepted": 0,
        "status_counts": {"pending": 0, "pass": 0, "fail": 0, "needs_rule_review": 0},
        "blocking_counts": {"blocking_first_core": 0, "non_blocking": 0},
    }
