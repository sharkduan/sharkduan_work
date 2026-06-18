# V2 Project Map

Date: 2026-06-16
Status: planning draft
Scope: v2-beta documentation only

## Current V1 Surface

The repository is organized around explicit contracts and release gates:

- `src/covalent_design/contracts/`: shared public contract types and lifecycle validation.
- `src/covalent_design/data/`: ETL records, manifests, splits, and quality reporting.
- `src/covalent_design/rules/`: residue-reaction family rule-table validation.
- `src/covalent_design/candidates/`: static covalent edge candidate artifacts.
- `src/covalent_design/viz/`: sampled visual inspection artifacts.
- `src/covalent_design/model/`: model batch contracts, stepwise candidates, PMDM adapter skeleton, covalent heads, and final decode.
- `src/covalent_design/training/`: split-specific dataset filtering, masks, denominators, losses, smoke train loop, checkpoint manifests.
- `src/covalent_design/inference/`: request validation, request processing, result writing, and mmCIF export.
- `src/covalent_design/evaluation/`: split-aware evaluation, lifecycle metrics, leakage reports, and docking protocol metadata.
- `tests/`: pure-Python fixture-driven coverage for contracts, ETL, model, training, inference, evaluation, CLI, and governance.

## V2 Overlay Authority

The files under `docs/v2/` are a planning overlay for Task 37 and later. They do not replace the canonical v1 specs under `docs/specs/` until an implementation task lands and explicitly synchronizes the accepted v2 decision back into the canonical docs.

ADR 0037 is the accepted authority for the v2 environment boundary and smoke profile vocabulary. `docs/specs/key-design-decisions.md` indexes that decision so implementers can find it from the canonical decision list.

`docs/v2/13-v2-task-adr-coverage.md` is the V2 governance map from Task 37+ slices to accepted ADRs, key decisions, and future ADR triggers. It is the authority for why V2 does not create one ADR per task.

## V1 Capabilities

V1 establishes a contract-complete scaffold:

- ETL-first data records and artifact manifests.
- Leakage-aware splits and Data Release Gate reporting.
- Visual inspection gates.
- Explicit target atom and ligand attachment atom contracts.
- Model batch construction from finalized `records.jsonl`.
- Stepwise covalent candidate rebuilding.
- PMDM-compatible adapter boundary with a deterministic fake backbone.
- Covalent head interface with anti-leakage message weight provenance.
- Final decode and validity gate diagnostics.
- Training dataset filtering, masks, denominators, and pseudo-loss contracts.
- Smoke training manifests and checkpoint metadata.
- Inference request/result contracts and project-owned mmCIF writer boundary.
- Evaluation, denominator, lifecycle, and docking-protocol metadata checks.

## Smoke Or Fixture Boundaries

The following areas are intentionally not production scientific implementations yet:

- PMDM backbone is represented by a fake deterministic adapter.
- Tensor behavior is represented by light tensor-like helpers, not PyTorch.
- Losses are pseudo-loss contract checks, not optimized training objectives.
- Training loop is smoke-only.
- Data fixtures are synthetic or minimal.
- Only the initial rule-table coverage is exercised.
- Chemical state unavailable is a contract state, not resolved by a chemistry tool.
- Protein clustering uses fixture keys or metadata, not a production clustering pipeline.
- Docking is protocol metadata and validation only.
- mmCIF output uses a project-owned writer boundary, not a verified RDKit backend.

## V2 Extension Points

V2-beta should extend these seams without breaking v1:

- Real Linux/WSL2 Conda environment with CUDA-capable PyTorch, RDKit, and PMDM compatibility.
- PMDM submodule/API smoke integration or clearly labeled non-PMDM PyTorch baseline.
- User-provided local real data under `D:\codex_work\data`, with manifest, checksum, license, and provenance gates.
- Real ETL run over validated local raw files staged from the user-provided data root.
- Family readiness gate for the six v1 residue-reaction families.
- RDKit-backed basic chemical validity and scaffold checks.
- Budget-controlled training and tuning sweep.
- Held-out and per-family stratified sampling evaluation.
- Docking feasibility gate only, not a required v2-beta release gate unless later proven viable.

## Dependency Boundary Map

| Dependency | First v2 role | Default CI | Heavy profile | Boundary |
| --- | --- | --- | --- | --- |
| RDKit | molecule normalization, scaffold keys, basic chemical validity, light descriptors | no | yes | data and evaluation adapters only; not model forward/loss |
| PyTorch | tensor backend, PMDM adapter, training loop, checkpoint smoke | no | yes | model/training adapters only; contracts stay serializable |
| CUDA | single-GPU training and smoke probes | no | yes | optional heavy runtime capability |
| PMDM | preferred diffusion backbone | no | yes | adapter behind existing PMDM output vocabulary |
| Docking engine | feasibility assessment only | no | optional/manual | not a v2-beta release gate unless later promoted |
| User-provided local source data | local real data staging from `D:\codex_work\data` | no network | manual/local | manifest, checksum, parser validation, provenance, and license-audited source seam with ADR 0038 manual-exemption caveat |

## Non-Negotiable Boundaries

- Preserve ETL-first source accountability.
- Preserve explicit reactive-site conditioning.
- Preserve single covalent attachment semantics.
- Preserve residue-reaction family as a first-class axis.
- Preserve rule-first consistency checks and denominator conservation.
- Preserve anti-leakage message weight provenance.
- Preserve lightweight default CI.
- Preserve heavy v2 checks as opt-in/manual until dependencies are locked.
- Preserve ADRs as decision records, not task records.
- Preserve noncovalent pretraining as optional/non-blocking unless a later ADR promotes it.
- Preserve the v2-beta data path as user-provided local real data. Agents must not manage network download of real source data by default.
- Treat files under `D:\codex_work\data` as untrusted until manifest, checksum, parser, license, and provenance checks pass.  For
  `intake_mode = "manual"` data with `license_status = "manual_exempt"`,
  the license step records the exemption rather than blocking (ADR 0038).
- Never commit real raw data, real model weights, or real docking outputs to git.

## Architecture Risks

- Real PMDM compatibility may diverge from the fake adapter boundary.
- `contracts/types.py` remains large and may need later partitioning.
- Family coverage may be uneven after real-source ingestion.
- CUDA/PyTorch/RDKit version solving may be fragile.
- User-provided local data availability, checksums, source provenance, and data licenses are not yet verified.
- Docking engine choice and licensing are unresolved.
- Noncovalent pretraining remains speculative and out of v2-beta mainline.
