# Reaction Family Rule Table Schema

The reaction family rule table is the shared rule source for training consistency, hard covalent edge decoding, and covalent evaluation.

Rules are data-derived and manually curated. They must not live only in code comments or unstructured prose.

## Storage

Initial file:

```text
data/rules/reaction_family_rule_table.yml
```

## Top-Level Shape

```yaml
version: 1
families:
  - family_id: CYS_MICHAEL_ADDITION
    target_residue_name: CYS
    target_atom_name: SG
    residue_reaction_class: MICHAEL_ADDITION
    allowed_ligand_attachment_elements: [C]
    allowed_covalent_bond_types: [single]
    allowed_warhead_smarts: []
    warhead_rule_status: pending
    forbidden_warhead_smarts: []
    bond_length_range: {min: null, max: null, unit: angstrom}
    protein_side_angle_range: {min: null, max: null, unit: degree}
    ligand_side_angle_range: {min: null, max: null, unit: degree}
    geometry_status:
      bond_length: pending
      protein_side_angle: pending
      ligand_side_angle: pending
    anchor_atom_name: CB
    ligand_neighbor_policy: first_heavy_atom_excluding_target
    protein_state_requirements:
      target_atom_formal_charge: required
      target_atom_protonation_state: required
      explicit_hydrogen_state: required_or_inferred
    valence_delta:
      target_atom: 1
      ligand_attachment_atom: 1
    notes: "Geometry ranges and allowed SMARTS are pending calibration."
```

## Fields

### `family_id`

Unique internal identifier for the residue-reaction family.

Examples:

- `CYS_MICHAEL_ADDITION`
- `CYS_NUCLEOPHILIC_SUBSTITUTION`
- `CYS_DISULFIDE_EXCHANGE`
- `SER_ACYLATION`
- `SER_PHOSPHONYLATION`
- `LYS_SCHIFF_BASE`

`family_id` must be consistent with `target_residue_name`, `target_atom_name`, and `residue_reaction_class`. The first token must match the residue name, and the suffix must match the reaction class.

Examples:

```text
CYS_MICHAEL_ADDITION:
  target_residue_name: CYS
  target_atom_name: SG
  residue_reaction_class: MICHAEL_ADDITION

SER_ACYLATION:
  target_residue_name: SER
  target_atom_name: OG
  residue_reaction_class: ACYLATION

LYS_SCHIFF_BASE:
  target_residue_name: LYS
  target_atom_name: NZ
  residue_reaction_class: SCHIFF_BASE
```

### `target_residue_name`

Protein residue class allowed by the family.

Examples:

- `CYS`
- `SER`
- `LYS`

### `target_atom_name`

Protein-side atom that forms the covalent cross edge.

Examples:

- `SG` for cysteine
- `OG` for serine
- `NZ` for lysine

First-pass residue atom contract:

```text
CYS -> SG
SER -> OG
LYS -> NZ
```

Any family whose `family_id` residue token, `target_residue_name`, and `target_atom_name` do not match this contract is invalid for v1 unless a later ADR extends the residue vocabulary.

### `residue_reaction_class`

Reaction class suffix used to validate `family_id` and to group families in reports.

First-pass values:

```text
MICHAEL_ADDITION
NUCLEOPHILIC_SUBSTITUTION
DISULFIDE_EXCHANGE
ACYLATION
PHOSPHONYLATION
SCHIFF_BASE
```

### `allowed_ligand_attachment_elements`

Allowed element types for the ligand-side attachment atom.

This is used by:

- reaction-family consistency loss
- final hard covalent edge decoding
- validity reporting

### `allowed_covalent_bond_types`

Allowed bond types for the protein-ligand covalent cross edge.

The first version should keep this conservative. Most supported reaction families are expected to decode a single covalent bond.

### `allowed_warhead_smarts`

SMARTS patterns for ligand local environments that are accepted as compatible warheads for this family.

These rules are manually curated and checked against corpus coverage.

An empty list has strict semantics:

```text
allowed_warhead_smarts: []
```

means "no allowed SMARTS have been approved for this family yet". It does not mean "all warheads are allowed". A family with an empty `allowed_warhead_smarts` list may appear in calibration reports, but it must not pass the rule-table release gate unless `notes` explains the temporary override and the consumer treats the family as `warhead_rule_status: pending`.

When a family is intentionally allowed without SMARTS gating, use:

```yaml
allowed_warhead_smarts: []
warhead_rule_status: not_applicable
notes: "SMARTS gate intentionally disabled because ..."
```

This exception is not allowed by default for first-pass training.

### `warhead_rule_status`

Review status for `allowed_warhead_smarts`.

Allowed values:

```text
calibrated
pending
not_applicable
```

Rules:

- `calibrated` requires at least one allowed SMARTS pattern.
- `pending` allows `allowed_warhead_smarts: []`, but the family must not pass the first-pass training release gate.
- `not_applicable` requires a note explaining why SMARTS gating is intentionally disabled and is not allowed by default for first-pass training.

### `forbidden_warhead_smarts`

SMARTS patterns for explicitly rejected local structures.

Use this field for:

- incorrect warhead matches
- over-reactive or undesirable motifs
- known false positives from automatic SMARTS matching

### `bond_length_range`

Allowed distance range for:

```text
target_atom -> ligand_attachment_atom
```

This range is used in:

- local covalent geometry supervision
- hard decoding validity gate
- evaluation metrics

`min: null` or `max: null` is valid only when the corresponding `geometry_status.bond_length` is `pending`. Null geometry limits mean "not calibrated yet" and must not be interpreted as an unbounded pass range.

### `protein_side_angle_range`

Allowed angle range for:

```text
residue_anchor_atom -> target_atom -> ligand_attachment_atom
```

The residue anchor atom should be defined by the implementation for each target residue.

For v1, the anchor atom is not implementation-defined; it must be specified as `anchor_atom_name` in the rule table.

Default first-pass anchors:

```text
CYS SG anchor: CB
SER OG anchor: CB
LYS NZ anchor: CE
```

The measured angle is:

```text
anchor_atom_name -> target_atom_name -> ligand_attachment_atom
```

If the anchor atom is missing in the structure, the record receives a geometry quality flag and is excluded from geometry-gated evaluation.

### `ligand_side_angle_range`

Allowed angle range for:

```text
target_atom -> ligand_attachment_atom -> ligand_neighbor_atom
```

When the ligand attachment atom has multiple neighbors, the implementation must define which neighbor or local aggregate is used.

For v1, the ligand neighbor must be defined deterministically by `ligand_neighbor_policy`:

```text
first_heavy_atom_excluding_target
warhead_reaction_center_neighbor
manual_atom_map_neighbor
not_applicable
```

`first_heavy_atom_excluding_target` selects the bonded heavy atom neighbor of the ligand attachment atom with the lowest normalized ligand atom index after excluding the protein target atom. If no such atom exists, ligand-side angle status is `pending` for that record.

`warhead_reaction_center_neighbor` requires a SMARTS match that names the ligand neighbor atom. `manual_atom_map_neighbor` requires source-provided or curated atom mapping. `not_applicable` is allowed only when `geometry_status.ligand_side_angle` is `pending` or disabled by a later ADR.

`min: null` or `max: null` is valid only when the corresponding angle status is `pending`. Null angles are not valid decoding ranges.

### `geometry_status`

Review status for each geometry constraint.

Allowed values:

```text
calibrated
pending
disabled
```

Rules:

- `calibrated` requires numeric `min` and `max`.
- `pending` requires `min: null` and `max: null`, and an explanation in `notes`.
- `disabled` requires `min: null` and `max: null`, an ADR reference in `notes`, and must not be used for hard decoding.

First-pass release may include `pending` geometry only if the family is excluded from geometry-gated evaluation and listed in the quality report.

### `anchor_atom_name`

Protein atom used to define the protein-side angle.

Allowed v1 values:

```text
CYS: CB
SER: CB
LYS: CE
```

### `ligand_neighbor_policy`

Deterministic policy for selecting the ligand-side neighbor atom used in ligand-side angle measurement.

Allowed v1 values are listed under `ligand_side_angle_range`.

### `protein_state_requirements`

Protein-side chemical state required before valence, protonation, and geometry gates can be evaluated.

Shape:

```yaml
protein_state_requirements:
  target_atom_formal_charge: required | optional | not_applicable
  target_atom_protonation_state: required | optional | not_applicable
  explicit_hydrogen_state: required | required_or_inferred | not_applicable
```

Rules:

- `required` means the value must be present in the normalized record or inference request before the relevant gate can pass.
- `required_or_inferred` means the implementation may infer the value only when it records the inference method, tool version, and confidence flag.
- missing required state must produce `REQUIRED_GATE_STATE_UNAVAILABLE`; it must not be treated as a permissive pass.
- protein chemical state is gate input and conditioning metadata, not a property the first model learns to repair.

### `valence_delta`

Expected valence change after forming the covalent cross edge.

This field is used to reject generated structures whose cross edge would violate target atom or ligand attachment atom valence.

`valence_delta.target_atom` and `valence_delta.ligand_attachment_atom` must be numeric. Null valence deltas are not allowed in v1.

### `notes`

Human-readable notes for rule provenance, exceptions, known limitations, or pending manual review items.

## Manual Curation Priorities

R0 required checks:

- residue-reaction family mapping
- target atom name
- ligand attachment atom mapping
- allowed warhead SMARTS
- valence delta
- family id, residue, target atom, and reaction class consistency
- explicit anchor atom and ligand neighbor policy
- protein-side chemical-state requirements

R1 recommended checks:

- bond length range
- protein-side angle range
- ligand-side angle range
- forbidden warhead SMARTS
- calibrated geometry ranges

R2 later extensions:

- toxicity alert SMARTS
- electrophilicity or reactivity ranking
- kinetic labels such as `kinact/KI`

## Validation Rules

Each family must satisfy:

- `family_id` is unique
- `family_id` residue token matches `target_residue_name`
- `family_id` reaction suffix matches `residue_reaction_class`
- `target_residue_name` is in the supported first-pass vocabulary
- `target_atom_name` matches the residue atom contract
- at least one ligand attachment element is allowed
- at least one covalent bond type is allowed
- `allowed_warhead_smarts: []` is treated as pending, not permissive
- `warhead_rule_status` is present and consistent with `allowed_warhead_smarts`
- geometry ranges are either fully specified with `geometry_status: calibrated` or explicitly marked as pending/disabled
- null geometry bounds are rejected unless the matching geometry status is `pending` or `disabled`
- `anchor_atom_name` is present and valid for the residue
- `ligand_neighbor_policy` is present and deterministic
- `protein_state_requirements` is present and uses only allowed values
- `valence_delta` specifies both protein-side and ligand-side changes
- every pending or manually overridden rule is explained in `notes`

## Acceptance Criteria

The rule table is release-ready when:

- every first-pass family has one row with a unique `family_id`
- `family_id`, `target_residue_name`, `target_atom_name`, and `residue_reaction_class` pass consistency validation
- no first-pass training family has empty `allowed_warhead_smarts` unless it is explicitly blocked as pending
- every geometry null has a matching pending or disabled status and a note
- every calibrated geometry has numeric min and max values
- every family defines `anchor_atom_name` and `ligand_neighbor_policy`
- every family defines `protein_state_requirements`
- validation output lists pending geometry and pending SMARTS separately from hard failures

## First-Pass Families

The first version supports:

```text
CYS_MICHAEL_ADDITION
CYS_NUCLEOPHILIC_SUBSTITUTION
CYS_DISULFIDE_EXCHANGE
SER_ACYLATION
SER_PHOSPHONYLATION
LYS_SCHIFF_BASE
```

Excluded from the first version:

- long-tail residue chemistry
- multi-residue mechanisms
- cofactor covalent modification
- metal coordination
- bidentate or tridentate covalent binders
