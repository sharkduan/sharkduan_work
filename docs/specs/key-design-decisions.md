# Key Design Decisions

## Purpose

This document is a compact decision index for implementers. It does not replace ADRs or design contracts; it points to the accepted decisions that constrain the final development specs.

## Decisions

| Decision | Final position | Primary authority | Implementation consequence |
| --- | --- | --- | --- |
| Project-owned implementation boundary | New covalent code lives under `src/covalent_design/`; PMDM and PocketFlow remain upstream baselines unless explicitly changed | ADR 0020, ADR 0034, `docs/github-management.md` | Prefer adapters and wrappers over editing baseline code |
| Implementation sequence | ETL-first, model second | ADR 0019, ADR 0030, `docs/covalent_etl_plan.md` | Do not modify PMDM training paths before accepted records, rules, edge candidates, splits, and reports exist |
| Data sources | CovalentInDB 2.0, CovPDB, and CovBinderInPDB are all required for v1 completion | ADR 0021, ADR 0030 | A single-source smoke path is useful, but cannot satisfy v1 release |
| Raw data handling | Raw source files are manually staged and covered by manifests | ADR 0026, ADR 0030 | No automatic downloader in v1; checksum and license/access notes are gates |
| Record identity | `record_id` is deterministic from normalized canonical linkage identity | ADR 0030, `docs/covalent_etl_plan.md` | Source ids are lineage, not canonical ids |
| First training core | Accepted records are monodentate only | ADR 0027, ADR 0030 | Multi-linkage records remain auditable but are excluded from v1 training |
| Quality severity names | ETL quality behavior uses `Q0`, `Q1`, and `Q2` | ADR 0030 | Do not reuse CovalentInDB P0/P1/P2 source-field priority names for quality filters |
| Q2 handling | Q2 records can enter training only through accepted-core gates and must remain stratified | `docs/covalent_etl_plan.md`, `03-training.md` | Training reports need quality-flag stratification and sensitivity paths |
| Primary rule key | `residue_reaction_family` is canonical; rule-table `family_id` must equal it in v1 | `CONTEXT.md`, `docs/reaction_family_rule_table_schema.md`, `00-shared-contracts.md` | Request validation, rule lookup, model conditioning, and reporting use the same key |
| Rule authority | Rule table is authoritative for family, atom, bond, SMARTS, valence, protonation, and geometry gates | ADR 0012, ADR 0030, `docs/reaction_family_rule_table_schema.md` | Empty SMARTS and null geometry are pending states, not permissive wildcards |
| Protein chemical state | Coordinates alone are insufficient; required chemical state must be explicit or inferred with provenance | ADR 0033 | Missing required state fails gates or masks losses; it is not a permissive default |
| Edge candidates | Candidate covalent edges are radius-bounded from the specified target atom to ligand atoms | ADR 0010, ADR 0031 | Do not use all-pairs negatives; encode `empty_radius_window` when no local negatives exist |
| Stepwise candidates | Training and inference candidate sets are based on current noisy or generated ligand coordinates | ADR 0031, `docs/covalent_model_design.md` | No hidden final-structure candidate set during denoising |
| Forced positives | Positive edge is force-included when noise moves it outside radius, with separate counts | ADR 0031 | v1 excludes force-included positives from soft message passing and geometry regression |
| Message passing | Soft edge message passing uses detached predicted probabilities by default | ADR 0031 | Ground-truth edge labels are not training-time message weights |
| Model backbone | PMDM remains the generation backbone; PocketFlow contributes supervision ideas only | ADR 0006, ADR 0008 | Do not replace PMDM with PocketFlow flow likelihood in v1 |
| Loss stack | PMDM losses plus covalent edge, bond type, local geometry, and rule-family consistency masks/gates | ADR 0007, ADR 0031, `docs/covalent_model_design.md` | Optional auxiliary family head is diagnostic, not the source of truth |
| Inference request | User supplies explicit reactive site and residue-reaction family, not a reference ligand | ADR 0016, `docs/covalent_generation_io_contract.md` | Request conflicts fail before sampling and do not enter generation denominators |
| Result lifecycle | Generation validity, complex export, docking eligibility, and docking run are separate statuses | ADR 0032 | Do not collapse result state into one valid/invalid flag |
| Sampling system failures | Accepted request samples that fail before an attempted result are run-level failures | ADR 0032, `00-shared-contracts.md` | Count them in `sampling_system_failure_count`, not invalid generated samples |
| Invalid generated samples | Invalid samples preserve available ligand, edge, geometry, warhead, and failure diagnostics | ADR 0017, ADR 0032 | Do not drop invalid rows from validity or failure-mode denominators |
| Complex output | mmCIF is authoritative; PDB LINK/CONECT is optional compatibility output | ADR 0018, ADR 0032 | Ligand-only SDF is not a complete result |
| Docking scores | Covalent docking score is reported only for valid, exported, eligible, successfully docked samples with a complete protocol manifest | ADR 0032 | QuickVina2-only output is a noncovalent baseline, not a covalent docking score |
| Scaffold split | Primary split key is de-warheaded scaffold (algorithm: `"fixture_key"` — metadata-based hashing of core_labels identity fields: `warhead_type`, `residue_reaction_family`, `bond_type`, `ligand_atom_element`, `ligand_atom_index`, `ligand_atom_name`, `target_atom_index`, `target_atom_name`) with fallback accounting. Default ratios 80/10/10, seed 42. Precomputed `scaffold_key` values from `metadata` bypass derivation. A user-accepted chemistry library is required before production use. | ADR 0015, ADR 0032 | `warhead_unmatched` fallback records are excluded from primary scaffold metrics unless `manual_review_status = "approved"` |
| Split artifact policy | Splits write separate artifacts under a dedicated output root and must not mutate `records.jsonl` or `artifact_manifest.json` | `implementation-plan.md` Task 14, `interface-design.md` | Task 14 input is finalized Task 13 records with `core_labels` and artifact refs |
| Ingest --out | `ingest --out <dir>` writes `source_records.jsonl` and `ingest_index.json` under the output directory | `interface-design.md`, `01-data-processing.md` | The output directory is compatible as `normalize --interim-root` input |
| Fallback reason and manual review | `fallback_reason` enum: `warhead_unmatched`, `missing_scaffold_input`, `missing_protein_cluster_input`, `manual_review_override`. Priority chain: `missing_protein_cluster_input` > `missing_scaffold_input` > `warhead_unmatched` > `manual_review_override`. `manual_review_status`: `pending`/`approved`/`rejected`. `reviewer`, `reviewed_at`, and `notes` fields are deferred until a manual review workflow is established. | `interface-design.md` Split Contracts | Fallback records excluded from primary scaffold metrics unless manually approved |
| Task 14 CLI path | `python -m covalent_design.data.cli.build_splits` | `interface-design.md`, `01-data-processing.md` | Consistent with Task 13 `cli.finalize_record_manifests` pattern |
| Visual checks | Sampled visual inspection artifacts are generated deterministically from accepted records. `pending`, `fail`, and `needs_rule_review` statuses block first-core release for those records until resolved; only `pass` is non-blocking. Missing geometry is `null` (valid output, not a failure). Sampling is by `record_id` sort order with a configurable `--seed` (default 42). `--sample-count` is optional; when omitted all accepted records are sampled. Task 15 reads `metadata.visual_check_status` when present and otherwise initializes sampled records as `pending`; it does not infer reviewer status automatically. Output artifacts: `visual_check_index.json` and per-record `artifacts/<record_id>/visual_check.json`. Task 15 does not generate an ETL quality report — the combined report is Task 16 scope. | `docs/covalent_etl_plan.md`, `interface-design.md` | `pending`, `fail`, and `needs_rule_review` are all gate-blocking states with `blocking_first_core: true`; only `pass` is non-blocking. Visual check artifacts are written under a dedicated output root and do not mutate `records.jsonl` or `artifact_manifest.json`. |
| Task 16 ETL quality report | `python -m covalent_design.data.cli.write_quality_report` produces the Data Release Gate report. `complete_for_v1` remains a per-source coverage signal, while `reconciled` covers candidate coverage, split totals, and visual status/blocking count equations. | `interface-design.md`, `implementation-plan.md`, `verification-matrix.md` | Checkpoint A must inspect both source coverage (`all_sources_complete_for_v1`) and count reconciliation (`reconciled`) before any model/training work starts. |
| CI scope | Default CI is lightweight until stable scientific fixtures and runners exist | ADR 0034 | Compile, docs, ADR numbering, and repo hygiene are default PR checks |

## Decisions Not Yet Final

These need explicit resolution before full v1 release. They do not currently require new ADRs unless the final choice becomes hard to reverse or changes an accepted contract.

- Validation library for cross-module schemas.
- Canonical large artifact formats.
- Protein chemical-state inference tool.
- Protein clustering method and threshold (Task 14 uses `protein_cluster_id` when present; real sequence identity method, threshold, and UniProt mapping authority remain deferred).
- **Manual review workflow** (`reviewer`, `reviewed_at`, and `notes` fields on manual review entries in `manual_review_index.json` are deferred until a manual review workflow is established. The current implementation stores `record_id`, `split`, `fallback_reason`, and `manual_review_status` only).
- **Scaffold-key chemistry implementation/library** (Task 14 currently uses `algorithm: "fixture_key"` which derives scaffold keys via metadata-based hashing of core_labels identity fields. Precomputed `scaffold_key` values from `metadata` are accepted as overrides. A user-accepted chemistry library such as RDKit Bemis-Murcko is required for production de-warheaded scaffold key generation).
- Covalent docking engine and protocol representation.
- mmCIF writer.
- Initial training loss weights and edge-score threshold calibration.
- Fixture set allowed in git under the data/artifact policy.
