# V2 Sampling And Evaluation Spec

Date: 2026-06-16
Status: hardened planning spec

## Sampling Request Schema

V2 sampling requests should extend existing reactive-site request semantics with:

- checkpoint ref,
- split or record selector,
- residue-reaction family filter,
- sample count,
- random seed,
- max retry policy,
- baseline mode,
- output root.

The request must remain explicit reactive-site generation, not reference-ligand generation.

## Sampling Outputs

Sampling emits:

- generation run manifest,
- result rows,
- sampling system failures,
- invalid decode diagnostics,
- optional generated complex artifacts,
- sampling summary.

## Validity Metrics

Evaluation must report:

- requested/attempted/valid/invalid/exported counts,
- validity gate pass/fail reasons,
- covalent edge prediction diagnostics,
- bond-type diagnostics,
- family diagnostics,
- lifecycle conservation equations.

## Uniqueness And Novelty

V2-beta should report uniqueness/novelty only when the required scaffold and molecule identity tools are source-verified. If unavailable, the report must say `not_evaluable`, not invent values.

## Covalent Geometry Checks

Report distance and local geometry diagnostics using existing v1 geometry contracts and RDKit-heavy checks only when available.

## Drug-Likeness Checks

RDKit descriptors and simple drug-likeness reports are heavy-profile diagnostics. They are not hard beta gates unless a later accepted decision promotes them.

## Safety Filters

Safety filters are limited to basic chemistry validity and rule-table compatibility in v2-beta. ADMET, toxicity, and selectivity are out of scope.

## Optional Docking Policy

Docking remains feasibility-only:

- source-verify engine and license,
- prove fixture CLI/API execution,
- record runtime and output schema,
- do not block v2-beta if infeasible.

## Evaluation Report

The report must include:

- split-aware metrics,
- per-family metrics,
- failure accounting,
- RDKit validity summary when available,
- docking feasibility status,
- denominator conservation.

## Failure Accounting

Failures must remain separated:

- request validation failure,
- sampling system failure,
- invalid generated sample,
- export failure,
- docking infeasible/not run,
- evaluation artifact corruption.

## Verification Commands

Planned commands:

```bash
python -m covalent_design.inference.cli.v2_sample --request configs/v2_sampling_smoke.yml
python -m covalent_design.evaluation.cli.v2_evaluate --manifest data/v2/runs/<run_id>/run_manifest.yml
```
