# Generation Result and Evaluation Contract

## Status

Accepted

## Date

2026-05-19

## Context

The generation interface will use `residue_reaction_family` as the canonical primary key for requests, rule lookup, result reporting, and family-stratified evaluation. `reaction_family` may be reported as a derived chemistry label, but it cannot replace the residue-aware key because residue identity determines valid target atoms, valence changes, and geometry checks.

## Decision

Request residue, atom, and family conflicts are request validation errors, not invalid generated samples. This keeps user-input errors out of generation denominators and prevents model quality metrics from being distorted by impossible requests.

Every attempted sample will produce a `CovalentGenerationResult`, including invalid samples. Invalid results must retain available ligand, edge, score, geometry, warhead-evidence, and failure metadata so validity rates and failure modes are reviewable. Dropping invalid samples or replacing them with empty files is rejected because it hides denominator accounting.

Generation validity, complex export, docking eligibility, and docking execution are separate lifecycle states. Evaluation reports must satisfy the denominator conservation equations defined in the IO contract.

Warhead evidence is split into matched and predicted fields. `matched_warhead_type` comes from structural rule or SMARTS matching and can support validity checks. `predicted_warhead_type` is diagnostic model output and cannot override residue-reaction-family rules. This avoids treating an auxiliary prediction as chemical proof.

Covalent docking scores are defined only for valid generated covalent complexes that enter a documented covalent docking protocol with a protocol manifest. Invalid samples receive null covalent docking scores and are summarized through validity and failure metrics. QuickVina2-only scores may be retained as noncovalent baselines, but they are not covalent docking scores unless wrapped by a documented covalent-linkage or constrained protocol.

The primary scaffold split unit for chemical generalization is the de-warheaded ligand scaffold with residue-reaction-family stratification. The ETL must preserve the scaffold-key artifact, warhead-removal evidence, algorithm/version, normalization policy, and leakage report. Whole-ligand scaffold and warhead-scaffold reports may be diagnostic summaries, but they are not the primary split key. This balances scaffold generalization against warhead memorization and avoids a split dominated only by recurring electrophile groups.

## Consequences

Evaluation reports must keep request errors, invalid generated samples, valid-but-not-docking-evaluable samples, and docked valid samples in separate denominators. This adds reporting complexity but prevents docking scores, scaffold generalization, and validity rates from being conflated.
