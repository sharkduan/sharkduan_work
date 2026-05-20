# Covalent Generation IO Contract

This document defines the reviewable contract for generation requests, per-sample results, and evaluation summaries. It is intentionally separate from ETL plans, rule schemas, and model design.

## Scope

Covered:

- `ReactiveSiteGenerationRequest`
- `CovalentGenerationResult`
- request validation errors
- result validity semantics
- covalent docking evaluation semantics
- scaffold split terminology used in evaluation review

Not covered:

- ETL implementation order
- reaction family rule-table schema
- PMDM model architecture
- training loss implementation

## Terminology Decisions

### ADR 0021-0029 status

ADR 0021 through ADR 0029 are formal project context. They are not informal notes. They govern dataset source priority, field priority, normalized record boundaries, storage, smoke tests, staging, monodentate first-core scope, quality filters, and ETL quality reporting.

### Reaction Family vs Residue-Reaction Family

`residue_reaction_family` is the canonical primary key for requests, rule lookup, result reporting, and family-stratified evaluation.

`reaction_family` is a chemistry class derived from or associated with `residue_reaction_family`. It may be reported for readability, but it must not replace `residue_reaction_family` when residue identity affects validity.

Example:

- `residue_reaction_family`: `CYS_MICHAEL_ADDITION`
- `reaction_family`: `MICHAEL_ADDITION`

### Warhead Type Evidence

`matched_warhead_type` means a post-generation structural rule or SMARTS match found a warhead compatible with the generated ligand.

`predicted_warhead_type` means the model emitted a warhead label as auxiliary output.

Validity decisions must use residue-reaction-family rules and structural matching. A predicted warhead type is diagnostic evidence only and cannot make an otherwise invalid structure valid.

## ReactiveSiteGenerationRequest

### Required Fields

| Field | Meaning | Review requirement |
| --- | --- | --- |
| `request_id` | Stable request identifier | Unique within a run |
| `protein_structure_uri` | Input protein structure path or URI | Resolvable by the runner |
| `protein_structure_format` | `mmcif` or `pdb` | Prefer `mmcif`; PDB allowed for compatibility |
| `target_model_id` | Structure model identifier when present | Required for multi-model structures |
| `target_chain_id` | Author or label chain/asym identifier | Must state identifier namespace |
| `target_residue_id` | Residue sequence identity, including insertion code when present | Must locate exactly one residue |
| `target_residue_name` | Three-letter residue name | Must match located residue |
| `target_atom_name` | Protein reactive atom name | Must exist on the located residue |
| `residue_reaction_family` | Canonical residue-reaction family key | Must be supported by the rule table |
| `sample_count` | Number of requested samples | Positive integer |

### Optional Fields

| Field | Meaning |
| --- | --- |
| `pocket_radius_angstrom` | Pocket construction radius |
| `num_ligand_heavy_atoms` | Fixed generated ligand heavy-atom count; maps to PMDM-style `num_atom` |
| `min_ligand_heavy_atoms` | Inclusive lower generated ligand heavy-atom bound |
| `max_ligand_heavy_atoms` | Inclusive upper generated ligand heavy-atom bound |
| `guidance_strength` | Sampling guidance control |
| `sampling_steps` | Number of denoising steps |
| `random_seed` | Reproducibility seed |
| `output_complex_format` | Requested complex export format; `mmcif` remains authoritative |
| `protein_preparation_policy` | Declared protein preparation or protonation policy used before generation |
| `target_atom_formal_charge` | Explicit target atom formal charge when known or required by the rule table |
| `target_atom_protonation_state` | Explicit target atom protonation state when known or required by the rule table |
| `target_atom_hydrogen_state` | `explicit`, `inferred`, `absent`, or `not_applicable` |

Reference ligands, user-specified scaffolds, user-specified warhead motifs, and ligand attachment atoms are not required request fields.

Size controls use heavy atoms only. Hydrogens, protein atoms, solvent atoms, and the protein-ligand covalent cross edge do not change the ligand heavy-atom count. A request may provide either `num_ligand_heavy_atoms` or the pair `min_ligand_heavy_atoms` / `max_ligand_heavy_atoms`, but not both forms.

### Atom Identity Contract

Protein atom identity must not rely on coordinates or serial numbers alone. The request must resolve the target atom through:

- structure model identifier when applicable
- chain or asym identifier and its namespace
- residue sequence identifier
- insertion code when present
- residue name
- atom name
- alternate-location handling when present

Generated ligand atom identity must be reported through a stable generated-ligand atom index and, when exported, the corresponding mmCIF/PDB atom name.

### Protein Chemical State Contract

If the selected residue-reaction-family rule row requires protein-side chemical state, the request runner must resolve that state before generation or fail request validation. Resolved state must record:

```text
protein_preparation_policy
target_atom_formal_charge
target_atom_protonation_state
target_atom_hydrogen_state
chemical_state_source: explicit_request | structure_file | inferred
chemical_state_tool_name
chemical_state_tool_version
chemical_state_confidence: high | medium | low | unknown
```

An inferred state is allowed only when the tool, version, and confidence are recorded. Missing required chemical state is not a permissive default.

## Request Validation Errors

Request validation happens before sampling. These errors do not produce invalid sample records and do not enter generation denominators.

| Error code | Owner | Meaning |
| --- | --- | --- |
| `REQUEST_STRUCTURE_UNREADABLE` | request | Protein structure cannot be read |
| `REQUEST_TARGET_RESIDUE_NOT_FOUND` | request | Chain/residue locator resolves to no residue |
| `REQUEST_TARGET_RESIDUE_AMBIGUOUS` | request | Chain/residue locator resolves to multiple residues |
| `REQUEST_TARGET_ATOM_NOT_FOUND` | request | Target atom is absent from the resolved residue |
| `REQUEST_RESIDUE_NAME_MISMATCH` | request | Provided residue name does not match the structure |
| `REQUEST_FAMILY_UNSUPPORTED` | request | Residue-reaction family is outside the supported vocabulary |
| `REQUEST_RESIDUE_FAMILY_CONFLICT` | request | Residue identity is incompatible with the residue-reaction family |
| `REQUEST_ATOM_FAMILY_CONFLICT` | request | Target atom is incompatible with the residue-reaction family |
| `REQUEST_SAMPLE_COUNT_INVALID` | request | Sample count is missing, zero, negative, or non-integer |
| `REQUEST_LIGAND_SIZE_INVALID` | request | Fixed ligand heavy-atom count is zero, negative, non-integer, or outside implementation-supported bounds |
| `REQUEST_LIGAND_SIZE_RANGE_INVALID` | request | Ligand heavy-atom range is missing one bound, has min greater than max, or contains invalid values |
| `REQUEST_LIGAND_SIZE_CONFLICT` | request | Fixed ligand heavy-atom count and ligand heavy-atom range are both provided |
| `REQUEST_REQUIRED_CHEMICAL_STATE_UNAVAILABLE` | request | Required protein-side formal charge, protonation, or hydrogen state cannot be resolved before sampling |

Residue, atom, and family conflicts are request errors. They must not be counted as model failures, invalid samples, or docking failures.

## CovalentGenerationResult

One attempted generated sample must produce one result record unless the request failed validation before sampling. Result lifecycle fields are separated so generation validity, complex export, docking eligibility, and docking execution cannot overwrite each other.

### Lifecycle Status Fields

| Field | Allowed values | Meaning |
| --- | --- | --- |
| `generation_validity_status` | `valid`, `invalid` | Whether generation produced a covalently valid internal result after final validity gate |
| `complex_export_status` | `not_applicable`, `exported`, `failed` | Whether an authoritative mmCIF complex was exported for a valid internal result |
| `docking_eligibility_status` | `not_applicable`, `eligible`, `not_evaluable` | Whether an exported valid covalent complex satisfies the selected covalent docking protocol prerequisites |
| `docking_run_status` | `not_applicable`, `not_run`, `succeeded`, `failed` | Whether docking was attempted and completed for a docking-eligible valid sample |
| `primary_failure_reason` | failure code or null | Primary reason for the earliest failing lifecycle stage |
| `secondary_failure_reasons` | list of failure codes | Additional observed failures that did not determine the primary lifecycle state |
| `edge_validity_checks` | list of check records | Per-rule gate observations for scored candidate edges |

Lifecycle constraints:

```text
generation_validity_status = invalid:
  complex_export_status = not_applicable
  docking_eligibility_status = not_applicable
  docking_run_status = not_applicable
  primary_failure_reason is required

generation_validity_status = valid and complex_export_status = failed:
  docking_eligibility_status = not_applicable
  docking_run_status = not_applicable
  primary_failure_reason = COMPLEX_EXPORT_FAILED

generation_validity_status = valid and complex_export_status = exported:
  docking_eligibility_status is eligible or not_evaluable

docking_eligibility_status = not_evaluable:
  docking_run_status = not_applicable
  primary_failure_reason may be DOCKING_NOT_EVALUABLE when no earlier failure exists

docking_eligibility_status = eligible:
  docking_run_status is not_run, succeeded, or failed
```

### Required Fields For Every Sample

| Field | Required for every attempted sample | Notes |
| --- | --- | --- |
| `request_id` | Yes | Links result to a validated request |
| `sample_id` | Yes | Stable within the request |
| `residue_reaction_family` | Yes | Canonical family key |
| `target_atom_identity` | Yes | Stable protein-side atom identity |
| `generation_validity_status` | Yes | `valid` or `invalid` |
| `complex_export_status` | Yes | See lifecycle constraints |
| `docking_eligibility_status` | Yes | See lifecycle constraints |
| `docking_run_status` | Yes | See lifecycle constraints |
| `primary_failure_reason` | Yes when any lifecycle stage fails | Null only for fully successful generated/exported/docked samples or valid exported samples with docking intentionally not run |
| `secondary_failure_reasons` | Yes | Empty list when none |
| `generated_ligand_status` | Yes | Indicates whether a parseable ligand exists |
| `molecular_quality_metrics` | When ligand exists | Null only when no parseable ligand exists |
| `covalent_edge_score` | When an edge was scored | Includes failed edge candidates when available |
| `geometry_metrics` | When measurable | Includes failed geometry when available |
| `edge_validity_checks` | Yes when any candidate edge was scored | Empty list only when no edge candidate was scored |
| `covalent_docking_score` | Only when `docking_run_status = succeeded` | Null otherwise |

### Fields Required For Valid Samples

| Field | Meaning |
| --- | --- |
| `ligand_sdf_uri` | Generated ligand file |
| `complex_mmcif_uri` | Authoritative generated covalent complex; required when `complex_export_status = exported` |
| `predicted_ligand_attachment_atom` | Stable generated-ligand atom identity |
| `predicted_covalent_edge` | Protein atom identity plus ligand atom identity |
| `matched_warhead_type` | Structural match used for rule consistency review |
| `edge_validity_checks` | Per-check pass/fail details for family, valence, geometry, and warhead matching |

### Fields Allowed But Not Authoritative

| Field | Rule |
| --- | --- |
| `reaction_family` | Derived readability label; not the primary key |
| `predicted_warhead_type` | Diagnostic model output; cannot override matched warhead checks |
| `complex_pdb_uri` | Compatibility export only; mmCIF remains authoritative |
| `noncovalent_vina_score` | Baseline or compatibility metric; not a covalent docking score |

### Invalid Sample Semantics

An invalid sample is a sampled output that failed generation validity checks. It is not an absent result.

Invalid results must preserve all available diagnostic data:

- generated ligand file if a chemically parseable ligand exists
- candidate or predicted ligand attachment atom if available
- candidate or predicted covalent edge if available
- covalent edge score if computed
- geometry metrics if measurable
- matched and predicted warhead evidence if available
- exact `primary_failure_reason`
- `secondary_failure_reasons` when additional failures are observed
- `edge_validity_checks` for every evaluated gate when available

Invalid results must be included in validity-rate denominators, uniqueness denominators when a ligand exists, and failure-mode summaries. They must be excluded from covalent docking score aggregation unless a future ADR explicitly defines a docking procedure for invalid structures.

## Failure Reason Codes

| Code | Stage | Meaning |
| --- | --- | --- |
| `LIGAND_RECONSTRUCTION_FAILED` | generation | No parseable ligand graph or coordinates could be produced |
| `LIGAND_CHEMISTRY_INVALID` | generation | Generated ligand failed chemistry sanitization |
| `NO_COVALENT_EDGE_PREDICTED` | generation | No ligand atom was selected for the covalent event |
| `COVALENT_EDGE_BELOW_THRESHOLD` | generation | Best edge score did not pass the acceptance threshold |
| `REACTION_FAMILY_RULE_FAIL` | generation gate | Edge or ligand local environment violated residue-reaction-family rules |
| `WARHEAD_MATCH_FAIL` | generation gate | No compatible matched warhead type was found |
| `VALENCE_CHECK_FAIL` | generation gate | Covalent linkage would violate valence constraints |
| `GEOMETRY_CHECK_FAIL` | generation gate | Bond distance or anchor geometry failed family-specific limits |
| `REQUIRED_GATE_STATE_UNAVAILABLE` | generation gate | Required protein or ligand state for a hard gate is unavailable |
| `UNSUPPORTED_GENERATED_CHEMISTRY` | generation gate | Generated chemistry is outside the first-version supported rule vocabulary |
| `COMPLEX_EXPORT_FAILED` | export | Valid internal result could not be exported to mmCIF |
| `DOCKING_NOT_EVALUABLE` | docking eligibility | Valid exported sample could not enter docking due to protocol prerequisites |
| `DOCKING_RUN_FAILED` | docking run | Docking was attempted for an eligible valid sample but did not complete successfully |

### Edge Validity Check Records

Each `edge_validity_checks` entry must contain:

```yaml
check_name: target_atom | ligand_atom_class | bond_type | warhead_smarts | forbidden_smarts | valence | protonation | geometry | single_edge_representability
status: pass | fail | not_applicable | not_evaluable
observed_value: ""
threshold_or_rule: ""
rule_table_version: ""
failure_code: null
```

## mmCIF/PDB Output Contract

The authoritative complex output is mmCIF. It must preserve atom identity for both sides of the covalent edge and a structured linkage record.

PDB export is optional and compatibility-oriented. PDB `LINK` and `CONECT` records may be emitted, but PDB atom serials are not sufficient as durable identity. Reviewers should trace PDB exports back to the mmCIF linkage and result record.

## Evaluation Contract

### Denominators

Evaluation summaries must report:

- requested sample count
- request validation error count
- attempted sample count
- sampling system failure count
- valid generated internal count
- invalid generated sample count
- exported valid complex count
- valid export failure count
- docking-evaluable valid sample count
- valid but not docking-evaluable sample count
- docking not-run valid sample count
- docking failed valid sample count
- successfully docked valid sample count

Required conservation equations:

```text
requested_sample_count =
  request_validation_error_sample_count +
  accepted_request_sample_count

accepted_request_sample_count =
  attempted_sample_count +
  sampling_system_failure_count

attempted_sample_count =
  valid_generated_internal_count +
  invalid_generated_sample_count

valid_generated_internal_count =
  exported_valid_complex_count +
  valid_export_failure_count

exported_valid_complex_count =
  docking_evaluable_valid_sample_count +
  valid_but_not_docking_evaluable_sample_count

docking_evaluable_valid_sample_count =
  successfully_docked_valid_sample_count +
  docking_failed_valid_sample_count +
  docking_not_run_valid_sample_count
```

### Covalent Docking Score

`covalent_docking_score` is aggregated only over valid samples with `docking_run_status = succeeded`.

Invalid samples must be reported through validity and failure-mode metrics, not assigned artificial docking scores. Missing docking scores for invalid samples are expected nulls, not missing data.

### Minimum Covalent Docking Protocol Definition

A reported covalent docking score must identify:

- receptor preparation procedure
- ligand preparation procedure
- covalent linkage or constraint representation
- target residue and atom used in docking setup
- scoring engine and version
- search box or local sampling region
- treatment of generated ligand coordinates before docking
- reason a valid sample was not docking-evaluable, when applicable

A docking protocol manifest is required for every run that reports `covalent_docking_score`:

```yaml
docking_protocol_id: ""
engine_name: ""
engine_version: ""
engine_build_hash: ""
full_config_uri: ""
full_config_sha256: ""
random_seed: null
receptor_preparation:
  tool_name: ""
  tool_version: ""
  input_structure_uri: ""
  input_structure_sha256: ""
  output_receptor_uri: ""
  output_receptor_sha256: ""
  pH_or_protonation_policy: ""
  water_policy: keep | remove | selected
  cofactor_policy: keep | remove | selected
  metal_policy: keep | remove | selected
ligand_preparation:
  tool_name: ""
  tool_version: ""
  input_ligand_uri: ""
  input_ligand_sha256: ""
  charge_model: ""
  protonation_policy: ""
covalent_constraint:
  representation: explicit_linkage | distance_constraint | reaction_constraint | other
  target_atom_identity: ""
  ligand_atom_identity: ""
  constraint_parameters: {}
search_region:
  center: [0.0, 0.0, 0.0]
  size: [0.0, 0.0, 0.0]
  unit: angstrom
pose_selection:
  ranking_rule: best_score | first_valid | other
  score_unit: ""
failure_log_uri: ""
failure_log_sha256: ""
```

Per-sample docking results must link to the protocol manifest and preserve docking input and output artifact checksums. A valid sample with missing required manifest fields is `DOCKING_NOT_EVALUABLE`, not a docked sample with missing metadata.

QuickVina2 alone is not a covalent docking protocol because it scores noncovalent receptor-ligand poses unless wrapped in a documented covalent-linkage or constrained protocol. It may be reported as `noncovalent_vina_score` or as a baseline metric.

### Scaffold Split

The primary scaffold split key is the de-warheaded ligand scaffold with residue-reaction-family stratification. This tests whether the model generalizes binding scaffolds rather than merely changing or memorizing warhead groups.

Whole-ligand scaffold summaries may be reported to detect near-duplicate ligands. Warhead-scaffold summaries may be reported to detect warhead memorization. Neither replaces the primary de-warheaded scaffold split key.

## Review Checklist

- ADR 0021-0029 are treated as formal context in prose and review language.
- Requests use `residue_reaction_family` as the canonical primary key.
- `reaction_family` is never the only key where residue identity matters.
- Request residue, atom, and family conflicts are classified as request validation errors.
- Request validation errors are excluded from generation denominators.
- Result lifecycle fields separate generation validity, complex export, docking eligibility, and docking run status.
- Evaluation report counts satisfy the denominator conservation equations.
- Size controls use ligand heavy-atom fields and map unambiguously to PMDM-style `num_atom`.
- Protein atom identity includes chain/asym, residue, insertion or alt-location qualifiers when present, residue name, and atom name.
- Valid generated samples either export an mmCIF complex or record `COMPLEX_EXPORT_FAILED` under `complex_export_status = failed`.
- Invalid results preserve diagnostic fields instead of disappearing.
- `matched_warhead_type` and `predicted_warhead_type` are not conflated.
- Covalent docking scores are null unless `docking_run_status = succeeded`.
- Evaluation reports invalid rates separately from docking scores.
- QuickVina2-only scores are not labeled as covalent docking scores.
- Scaffold split wording states de-warheaded ligand scaffold as the primary split unit.
