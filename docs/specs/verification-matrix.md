# Spec: Verification Matrix

## Objective

Tie every development specification to checkable evidence. This document prevents purely narrative implementation by requiring each module to prove its contract through schemas, fixtures, commands, reports, or conservation equations.

## Matrix

| Area | Evidence Required | Primary Command | Blocking For |
| --- | --- | --- | --- |
| Raw source manifests | Manifest schema, checksum fixtures, missing-license fixture | `python -m covalent_design.data.validate_manifests --raw-root data/raw` | Data ingestion |
| Source parsing | 10-record CovBinder fixture, CovPDB fixture, CovalentInDB P0-source fixture | `python -m covalent_design.data.ingest --source <source> --raw-root data/raw` | Normalization |
| Canonical identity | Duplicate merge fixture, linkage conflict fixture, rejected-identity-input fixture | `python -m covalent_design.data.normalize --interim-root data/interim --out-root data/processed` | Record writing |
| Quality filters | Q0/Q1/Q2 fixtures and report section; quality tier/reason/flag summary | `python -m covalent_design.data.normalize --interim-root data/interim --out-root data/processed` (gate routing); `python -m covalent_design.data.cli.write_quality_report --processed-root <processed_root> ...` (release report) | Training core release |
| CovalentComplexRecord | JSONL schema (`schema_version`, `contract_version`, `record_id`, `core_labels`, `lineage`, `metadata`, `artifacts`), 4 required non-edge artifact roles per record (`protein_atom_table`, `ligand_atom_table`, `ligand_bond_table`, `coordinates`), artifact manifest checksum check, `rejected_index.jsonl` and `conflict_index.jsonl` separation, missing-required-artifact hard failure, byte determinism | `python -m covalent_design.data.build_record_index --processed-root data/processed` | Model/training input |
| Rule table | Rule schema validation, pending SMARTS fixture, null geometry fixture | `python -m covalent_design.rules.cli.validate_rule_table --rules data/rules/reaction_family_rule_table.yml` | Candidate generation and gates |
| Rule calibration sheet | 14-column CSV (family_id, sample_count, representative_record_ids, target_atom_distribution, ligand_attachment_element_distribution, warhead_distribution, bond_length_summary, protein_side_angle_summary, ligand_side_angle_summary, outlier_record_ids, manual_decision, notes, pending_smarts_marker, pending_geometry_marker), per-family sample counts, pending SMARTS/geometry markers from rule table status, geometry summaries from records.jsonl metadata.geometry (no 3D recalculation), zero-sample families still produce reviewable rows, byte-deterministic CSV output, no edge_candidates files/dirs/fields generated | `python -m covalent_design.rules.cli.build_calibration_sheet --records <records.jsonl> --rules <rule_table.yml> --out-csv <out-csv> [--out-json <json>]` | Rule curation review |
| Edge candidates | Positive edge fixture, no-edge negative fixture, empty-radius-window fixture | `python -m covalent_design.candidates.cli.build_edge_candidates --records <records.jsonl> --radius 4.0` | Model/training input |
| Final record manifests | Edge-candidate artifact path/checksum present for every accepted record; missing edge-candidate, checksum mismatch, duplicate edge-candidate ref, and obsolete unlinked manifest entry fixtures all fail hard with structured errors; no partial writes on error; byte-deterministic output across repeated runs; CLI prints JSON summary and exits zero on success, non-zero on error | `python -m covalent_design.data.cli.finalize_record_manifests --records <records.jsonl>` | Model/training input |
| Splits | SplitPolicy schema, split_index.json envelope (split_policy, assignment_count, assignments with record_id/split/scaffold_key/protein_cluster_id/residue_reaction_family/fallback_reason/manual_review_status), scaffold_keys.jsonl per-record artifacts (algorithm: "fixture_key", warhead_match sub-object with matched/warhead_type/warhead_smarts/removed_atom_indices, scaffold_key, fallback_reason), fallback_reason enum (`warhead_unmatched`, `missing_scaffold_input`, `missing_protein_cluster_input`, `manual_review_override`), manual_review_status values (`pending`/`approved`/`rejected`), zero primary scaffold overlap across train/val/test, zero protein-cluster overlap, scaffold leakage fixture, scaffold no-leakage fixture, protein-cluster leakage fixture, warhead_unmatched fallback fixture, manual review override fixture, missing_scaffold_input fixture, missing_protein_cluster_input fixture, leakage_report.json with scaffold_overlaps/protein_cluster_overlaps/zero_overlap, fallback_accounting.json with fallback_by_reason (count + record_ids), manual_review_index.json with review_count and reviewed_records, count conservation (accepted = train + val + test + excluded), default ratios 80/10/10 and seed 42, non-mutation of records.jsonl and artifact_manifest.json, no visual check or quality report artifacts, invalid input returns structured errors with no partial output, reviewer/reviewed_at/notes deferred | `python -m covalent_design.data.cli.build_splits --records <records.jsonl> --policy <policy.json> --out-root <out_root>` | Generalization reporting |
| Visual checks | visual_check_index.json envelope (schema_version, contract_version, role, sample_policy with sample_count/seed/total_accepted, status_counts with pending/pass/fail/needs_rule_review, blocking_counts with blocking_first_core/non_blocking, records list with record_id/status/blocking_first_core/artifact_ref), artifacts/<record_id>/visual_check.json per-record artifacts (target_atom, ligand_attachment_atom, covalent_edge with target_atom/ligand_atom/bond_type/bond_length, residue_reaction_family, warhead_annotation with warhead_type/warhead_smarts, distance and local_angles optional/nullable from metadata.geometry, status one of pending/pass/fail/needs_rule_review, blocking_first_core bool), pending/pass/fail/needs_rule_review status fixtures, blocking_first_core gate fixture (pending blocks, fail blocks, needs_rule_review blocks, pass does not block), optional geometry fixture (missing geometry is null, not a failure), deterministic sampling fixture (same seed + same input = same output), --sample-count None includes all records, --seed defaults to 42, non-mutation of records.jsonl and artifact_manifest.json, no ETL quality report artifacts generated (Task 16 scope) | `python -m covalent_design.viz.cli.export_visual_checks --records <records.jsonl> --out-root <out_root> [--sample-count N] [--seed 42]` | ETL release review |
| ETL Quality Report | `quality_report.json` envelope with source coverage, accepted/rejected/conflict summary, family/residue/warhead distributions, linkage/geometry/protein-state quality, candidate statistics, split statistics, visual check summary, per-source `complete_for_v1`, visual-blocked counts, deterministic output, no model/training artifacts, missing input structured errors, unreadable rejected/conflict/visual indexes as structured data errors, and count equations for candidate coverage, split totals, and visual check totals | `python -m covalent_design.data.cli.write_quality_report --processed-root <processed_root> [--ingest-roots <dir> ...] [--splits-root <dir>] [--visual-checks-root <dir>] [--out <path>]` | Data Release Gate |
| Model forward | Batch fixture, tensor shape assertions, forced-positive denominator | `python -m covalent_design.model.forward_smoke --config configs/covalent_model_smoke.yml` | Training |
| Training losses | Tiny batch with natural positive, forced positive, zero negatives, missing state, Q2 keep-with-flag record | `python -m covalent_design.training.train --config configs/covalent_train_smoke.yml` | Model validation |
| Training denominators | Family/timestep denominator report | `python -m covalent_design.training.report_denominators --run outputs/runs/<run_id>` | Training acceptance |
| Request validation | Request error fixtures for all IO contract error codes | `python -m covalent_design.inference.validate_request --request request.yml` | Sampling |
| Sampling system failures | Crash/OOM/timeout/retry-exhausted run artifact and denominator fixture | `python -m covalent_design.inference.generate --request request.yml --checkpoint outputs/checkpoints/model.pt` | Evaluation accounting |
| Final decode | Valid edge fixture and all-candidates-fail fixture | `python -m covalent_design.inference.generate --request request.yml --checkpoint outputs/checkpoints/model.pt` | Result writing |
| mmCIF export | Valid linkage export fixture, export failure fixture | `python -m covalent_design.inference.export_complexes --results outputs/generation/<job_id>/results.jsonl` | Docking eligibility |
| Evaluation denominators | Golden result summaries for all conservation equations | `python -m covalent_design.evaluation.check_denominators --summary outputs/eval/summary.yml` | Evaluation report |
| Docking protocol | Manifest schema, not-evaluable fixture, corrupt succeeded-status fixture, QuickVina2-only rejection fixture | `python -m covalent_design.evaluation.run_covalent_docking --manifest configs/docking_protocol.yml` | Covalent docking score reporting |
| Repository governance | Required docs, ADR filename numbering, cache/binary block, Python compile | GitHub Actions `CI` workflow and `python -m compileall -q scripts src` | Pull request readiness |

## Checkpoints

### Data Release Gate

- All three required sources report `complete_for_v1: true`.
- `complete_for_v1` is a per-source raw manifest coverage signal; the release gate is the all-source ETL quality report after accepted, rejected, and conflict records reconcile.
- Accepted, rejected, and conflict records reconcile.
- Candidate coverage, split totals, and visual check status/blocking totals reconcile in the ETL quality report.
- Rule calibration sheet and rule table are present.
- Edge candidates and splits pass schema and leakage checks.
- Visual check `pending`, `fail`, and `needs_rule_review` statuses all block sampled records from first-core release until resolved; only `pass` is non-blocking.

### Model/Training Gate

- Model forward smoke test passes on accepted fixture records.
- Training smoke run logs every required loss and denominator.
- No rejected or conflict records enter the training dataset.

### Inference/Evaluation Gate

- Request validation fixtures cover every request error.
- Valid and invalid generated samples both write complete result rows.
- Sampling system failures reconcile outside attempted result rows.
- Evaluation denominator equations pass.
- Docking scores are reported only for successfully docked valid samples.

## Open Questions

- Which tests remain lightweight CI checks and which become manual or scheduled scientific workflows?
- What minimum fixture set can be committed without violating data/artifact policy?
- Which generated report sections should be required before a PR can merge?
