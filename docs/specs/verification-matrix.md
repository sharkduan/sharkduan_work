# Spec: Verification Matrix

## Objective

Tie every development specification to checkable evidence. This document prevents purely narrative implementation by requiring each module to prove its contract through schemas, fixtures, commands, reports, or conservation equations.

## Matrix

| Area | Evidence Required | Primary Command | Blocking For |
| --- | --- | --- | --- |
| Raw source manifests | Manifest schema, checksum fixtures, missing-license fixture | `python -m covalent_design.data.validate_manifests --raw-root data/raw` | Data ingestion |
| Source parsing | 10-record CovBinder fixture, CovPDB fixture, CovalentInDB P0-source fixture | `python -m covalent_design.data.ingest --source <source>` | Normalization |
| Canonical identity | Duplicate merge fixture, linkage conflict fixture | `python -m covalent_design.data.normalize --interim-root data/interim --out-root data/processed` | Record writing |
| Quality filters | Q0/Q1/Q2 fixtures and report section | `python -m covalent_design.data.write_quality_report` | Training core release |
| CovalentComplexRecord | JSONL schema, artifact manifest checksum check | `python -m covalent_design.data.build_record_index` | Model/training input |
| Rule table | Rule schema validation, pending SMARTS fixture, null geometry fixture | `python -m covalent_design.rules.validate_rule_table --rules data/rules/reaction_family_rule_table.yml` | Candidate generation and gates |
| Edge candidates | Positive edge fixture, no-edge negative fixture, empty-radius-window fixture | `python -m covalent_design.candidates.build_edge_candidates --radius 4.0` | Model/training input |
| Final record manifests | Edge-candidate artifact path/checksum present for every accepted record | `python -m covalent_design.data.finalize_record_manifests` | Model/training input |
| Splits | Scaffold key artifact, zero primary overlap check, fallback reason accounting, diagnostic overlap report | `python -m covalent_design.data.build_splits` | Generalization reporting |
| Visual checks | Sampled artifact index with status values, fail/needs-rule-review gate fixtures | `python -m covalent_design.viz.export_visual_checks` | ETL release review |
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
- Accepted, rejected, and conflict records reconcile.
- Rule calibration sheet and rule table are present.
- Edge candidates and splits pass schema and leakage checks.
- Visual check `fail` and `needs_rule_review` statuses block sampled records from first-core release until resolved.

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
