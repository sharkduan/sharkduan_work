from __future__ import annotations

from dataclasses import dataclass

from covalent_design.contracts.types import CONTRACT_VERSION


@dataclass(frozen=True)
class ModelConfig:
    contract_version: str = CONTRACT_VERSION
    rule_table_hash: str = ""
    fake_backbone: bool = True
    hidden_dim: int = 256
    ligand_feature_dim: int = 128
    protein_feature_dim: int = 128
    ligand_pair_feature_dim: int = 0
    protein_ligand_pair_feature_dim: int = 0
    seed: int = 42
    candidate_radius_angstrom: float = 4.0

    def __post_init__(self) -> None:
        if self.ligand_feature_dim <= 0:
            raise ValueError(
                f"ligand_feature_dim must be positive, got {self.ligand_feature_dim}"
            )
        if self.protein_feature_dim <= 0:
            raise ValueError(
                f"protein_feature_dim must be positive, got {self.protein_feature_dim}"
            )
        if self.hidden_dim <= 0:
            raise ValueError(
                f"hidden_dim must be positive, got {self.hidden_dim}"
            )
        if self.candidate_radius_angstrom <= 0:
            raise ValueError(
                f"candidate_radius_angstrom must be positive, "
                f"got {self.candidate_radius_angstrom}"
            )
        if self.ligand_pair_feature_dim < 0:
            raise ValueError(
                f"ligand_pair_feature_dim must be non-negative, "
                f"got {self.ligand_pair_feature_dim}"
            )
        if self.protein_ligand_pair_feature_dim < 0:
            raise ValueError(
                f"protein_ligand_pair_feature_dim must be non-negative, "
                f"got {self.protein_ligand_pair_feature_dim}"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "rule_table_hash": self.rule_table_hash,
            "fake_backbone": self.fake_backbone,
            "hidden_dim": self.hidden_dim,
            "ligand_feature_dim": self.ligand_feature_dim,
            "protein_feature_dim": self.protein_feature_dim,
            "ligand_pair_feature_dim": self.ligand_pair_feature_dim,
            "protein_ligand_pair_feature_dim": self.protein_ligand_pair_feature_dim,
            "seed": self.seed,
            "candidate_radius_angstrom": self.candidate_radius_angstrom,
        }
