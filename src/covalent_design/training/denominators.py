"""Task 23: Edge denominator projection, timestep bucketing, and strata aggregation."""

from __future__ import annotations

from dataclasses import dataclass, fields as dc_fields
from itertools import groupby
import math
from typing import Iterable

from covalent_design.contracts.types import (
    DenominatorsStratum,
    EdgeDenominators,
    MaskAudit,
)

_BUCKET_ORDER = ("early", "mid", "late")


@dataclass(frozen=True)
class DenominatorStratumEntry:
    residue_reaction_family: str
    timestep_value: float
    mask_audit: MaskAudit


def build_edge_denominators(mask_audit: MaskAudit) -> EdgeDenominators:
    denoms = EdgeDenominators(
        candidate_count=mask_audit.candidate_count,
        natural_candidate_count=mask_audit.natural_positive_count
        + mask_audit.natural_negative_count,
        forced_positive_count=mask_audit.forced_positive_count,
        eligible_edge_count=mask_audit.edge_loss_eligible_count,
        masked_candidate_count=mask_audit.candidate_count
        - mask_audit.edge_loss_eligible_count,
        edge_loss_denominator=mask_audit.edge_loss_eligible_count,
        bond_type_loss_denominator=mask_audit.bond_type_loss_eligible_count,
        geometry_loss_denominator=mask_audit.geometry_loss_eligible_count,
        message_passing_candidate_count=mask_audit.message_passing_candidate_count,
        gate_evaluated_count=mask_audit.gate_evaluated_count,
    )
    denoms.validate()
    return denoms


def classify_timestep_bucket(timestep_value: float) -> str:
    if not math.isfinite(timestep_value) or timestep_value < 0.0 or timestep_value > 1.0:
        raise ValueError(
            f"timestep_value {timestep_value!r} is outside [0.0, 1.0]"
        )
    if timestep_value >= 0.8:
        return "early"
    if timestep_value >= 0.3:
        return "mid"
    return "late"


def aggregate_denominator_strata(
    entries: Iterable[DenominatorStratumEntry],
) -> tuple[DenominatorsStratum, ...]:

    def _sort_key(entry: DenominatorStratumEntry) -> tuple[str, str]:
        return (entry.residue_reaction_family, classify_timestep_bucket(entry.timestep_value))

    sorted_entries = sorted(entries, key=_sort_key)

    _MASK_AUDIT_FIELDS = [f.name for f in dc_fields(MaskAudit)]

    strata: list[DenominatorsStratum] = []
    for (family, bucket), group in groupby(sorted_entries, key=_sort_key):
        group_list = list(group)

        aggregated_fields: dict[str, int] = {}
        for field_name in _MASK_AUDIT_FIELDS:
            aggregated_fields[field_name] = sum(
                getattr(e.mask_audit, field_name) for e in group_list
            )

        aggregated_audit = MaskAudit(**aggregated_fields)
        denoms = build_edge_denominators(aggregated_audit)

        strata.append(
            DenominatorsStratum(
                residue_reaction_family=family,
                timestep_bucket=bucket,
                denominators=denoms,
                mask_audit=aggregated_audit,
            )
        )

    strata.sort(key=lambda s: (s.residue_reaction_family, _BUCKET_ORDER.index(s.timestep_bucket)))
    return tuple(strata)
