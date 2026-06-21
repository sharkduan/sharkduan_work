"""Chemistry adapters for optional heavy-profile dependencies."""

from covalent_design.chem.rdkit_descriptors import (
    DescriptorResult,
    compute_descriptors,
    descriptor_result_to_dict,
)

from covalent_design.chem.rdkit_normalize import (
    MoleculeNormalizationResult,
    normalize_molecule,
    result_to_dict,
)

from covalent_design.chem.scaffolds import (
    ScaffoldResult,
    derive_scaffold,
    scaffold_result_to_dict,
)

__all__ = [
    "DescriptorResult",
    "MoleculeNormalizationResult",
    "ScaffoldResult",
    "compute_descriptors",
    "derive_scaffold",
    "descriptor_result_to_dict",
    "normalize_molecule",
    "result_to_dict",
    "scaffold_result_to_dict",
]
