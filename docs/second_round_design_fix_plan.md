# Second-Round Design Fix Plan

This plan converts the second-round review findings into ordered documentation fixes. Each task must produce reviewable evidence, not only clearer prose.

## Dependency Order

```text
Task 1: Verification matrix
  -> Task 2: Result lifecycle and denominator contract
      -> Task 3: Protein chemical state and mask/gate contract
          -> Task 4: Stepwise candidate, loss, and message-passing contract
              -> Task 5: Scaffold split evidence
              -> Task 6: Covalent docking protocol evidence
                  -> Task 7: ADR and context alignment
```

## Task 1: Verification Matrix

**Priority:** P0

**Description:** Establish the artifact-level evidence required for every design contract.

**Acceptance criteria:**
- Every later task names at least one evidence type: schema, report section, fixture, checklist, or conservation equation.
- The plan states which document is authoritative for each contract surface.
- Verification rejects purely narrative fixes with no checkable artifact.

**Verification:** Review this document before editing the contract documents.

**Dependencies:** None.

**Files likely touched:** `docs/second_round_design_fix_plan.md`.

## Task 2: Result Lifecycle And Denominator Contract

**Priority:** P0

**Description:** Split generation validity, export status, docking eligibility, and docking run status so result records and evaluation counts are mutually exclusive and collectively exhaustive.

**Acceptance criteria:**
- `CovalentGenerationResult` has separate fields for generation validity, export, docking eligibility, docking run, primary failure, secondary failures, and edge validity checks.
- Request validation errors do not create sample results and do not enter generation denominators.
- Conservation equations define all evaluation counts.
- Ligand heavy-atom size fields are named consistently across request and model contracts.

**Verification:** Schema table and denominator equations in `docs/covalent_generation_io_contract.md`.

**Dependencies:** Task 1.

**Files likely touched:** `docs/covalent_generation_io_contract.md`, `docs/covalent_model_design.md`, `CONTEXT.md`.

## Task 3: Protein Chemical State And Mask/Gate Input Contract

**Priority:** P0

**Description:** Make fixed-protein chemical state explicit so valence, protonation, and geometry gates can be reproduced.

**Acceptance criteria:**
- Records and requests have explicit protein chemical-state fields or a declared unavailable state.
- Missing required gate state maps to a stage-specific unsupported or invalid reason.
- Rule table and model design both state that protein chemical state is gate input, not learned repair.
- ETL quality reports expose protein preparation and missing-state counts.

**Verification:** Schema/report additions in ETL, rule-table, model, and IO docs.

**Dependencies:** Task 2.

**Files likely touched:** `docs/covalent_etl_plan.md`, `docs/reaction_family_rule_table_schema.md`, `docs/covalent_model_design.md`, `docs/covalent_generation_io_contract.md`, `CONTEXT.md`.

## Task 4: Stepwise Candidate, Loss, And Message-Passing Contract

**Priority:** P0

**Description:** Define how forced positives, pending rules, no-edge candidates, loss masks, and soft edge message passing affect training denominators and gradient paths.

**Acceptance criteria:**
- Candidate, eligible, masked, scored, forced-positive, and gate-evaluated counts are named.
- Forced positives have explicit participation rules for message passing, edge loss, bond-type loss, and geometry loss.
- Pending SMARTS/geometry and missing angle states have explicit loss denominator behavior.
- Soft edge message passing states whether probabilities are detached, teacher-forced, scheduled, or fully predicted.

**Verification:** Loss/mask table and training-report fields in `docs/covalent_model_design.md`.

**Dependencies:** Task 3.

**Files likely touched:** `docs/covalent_model_design.md`, `docs/adr/0031-stepwise-covalent-edge-supervision-contract.md`.

## Task 5: De-Warheaded Scaffold Split Evidence

**Priority:** P1

**Description:** Make scaffold split generation reproducible and leakage-auditable.

**Acceptance criteria:**
- The primary split key is `dewarheaded_scaffold_key` plus residue-reaction-family stratification.
- The ETL plan specifies warhead removal evidence, scaffold algorithm/version, normalization policy, fallback behavior, and overlap checks.
- Split reports include train/val/test overlap counts for primary and diagnostic scaffold keys.

**Verification:** Split artifact schema and quality-report section in `docs/covalent_etl_plan.md`.

**Dependencies:** Task 3.

**Files likely touched:** `docs/covalent_etl_plan.md`, `docs/covalent_generation_io_contract.md`, `docs/adr/0032-generation-result-and-evaluation-contract.md`.

## Task 6: Covalent Docking Protocol Evidence

**Priority:** P1

**Description:** Make covalent docking scores reproducible and separate them from QuickVina2-only baselines.

**Acceptance criteria:**
- A docking protocol manifest schema records engine build, full config, receptor/ligand preparation, charge/protonation policy, covalent constraint representation, input/output checksums, pose selection, and failure logs.
- Docking status fields distinguish not-evaluable, not-run, failed, and succeeded valid samples.
- QuickVina2-only scores remain `noncovalent_vina_score`.

**Verification:** Protocol schema and report fields in `docs/covalent_generation_io_contract.md`.

**Dependencies:** Task 2.

**Files likely touched:** `docs/covalent_generation_io_contract.md`, `docs/adr/0032-generation-result-and-evaluation-contract.md`, `CONTEXT.md`.

## Task 7: ADR And Context Alignment

**Priority:** P1

**Description:** Record the hard-to-reverse decision about fixed-protein chemical state and mask/gate boundaries while keeping process details in design docs.

**Acceptance criteria:**
- Add ADR 0033 for fixed-protein chemical state and mask/gate boundaries.
- Existing ADR 0031 references ADR 0033 for protein-side chemical state rather than expanding into a mixed-purpose ADR.
- Existing ADR 0032 references the result lifecycle, denominator, scaffold, and docking evidence contracts without creating duplicate ADRs.
- `CONTEXT.md` contains glossary terms for result lifecycle, protein chemical state, and loss/gate denominator accounting.

**Verification:** ADR headers, cross-references, and glossary consistency scan.

**Dependencies:** Tasks 2-6.

**Files likely touched:** `CONTEXT.md`, `docs/adr/0031-stepwise-covalent-edge-supervision-contract.md`, `docs/adr/0032-generation-result-and-evaluation-contract.md`, `docs/adr/0033-fixed-protein-chemical-state-and-mask-gate-boundary.md`.

## Checkpoint

After all tasks:

- [ ] No result status term conflates generation validity, export, and docking.
- [ ] Every reported count has a conservation equation or explicit denominator.
- [ ] Protein chemical state is represented before any valence/protonation gate is evaluated.
- [ ] Loss and gate masks expose denominator counts.
- [ ] Scaffold split and docking score are backed by reproducible artifacts.
- [ ] ADRs record decisions only; workflow and test details remain in design docs.
