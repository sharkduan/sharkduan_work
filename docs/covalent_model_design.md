# Covalent Model Design Contract

This document defines the model-side contract for the first covalent inhibitor generator. It starts after the ETL has produced accepted monodentate `CovalentComplexRecord` rows, radius-bounded edge candidates, reaction-family rules, and quality flags. It does not change the ETL plan, the rule table schema, or the global project context.

## Scope

The first model is a PMDM-compatible fixed-protein ligand diffusion extension. It generates ligand atoms and ligand coordinates, predicts soft covalent cross-edge probabilities during denoising, and performs one final hard covalent edge decode after denoising.

The first training core is monodentate: one protein atom and one ligand atom form one covalent cross edge. Multi-linkage records are outside the first training core even when they belong to known chemistry families.

## Contract Inputs

Each training example must provide:

- fixed protein atom types, coordinates, residue ids, chain ids, and target residue metadata
- target atom id, target atom element, target residue name, target atom coordinates, and residue-reaction family
- protein preparation policy, target atom formal charge, target atom protonation state, target atom hydrogen state, and chemical-state provenance when required by the rule table
- ligand heavy atom graph, ligand atom types, ligand coordinates, and ligand bonds from the reaction-product adduct complex
- one positive covalent cross edge `(target_atom_id, ligand_attachment_atom_id, covalent_bond_type)`
- radius-bounded no-edge candidate cross edges from the same target atom to nearby non-attachment ligand atoms
- reaction-family rule row resolved by `residue_reaction_family`
- `warhead_type` and source confidence metadata when available from source annotations or rule matching
- local covalent geometry metrics for the positive edge and for candidate negatives where computable

Inference requires the same protein-side conditioning fields except ligand fields are generated. Optional size controls are expressed as ligand heavy-atom counts.

## Coordinate Frame And Candidate Set

Stepwise covalent edge candidates are defined against the current denoising state, not against a hidden final structure.

At training step `t`:

- protein coordinates are fixed in the input frame
- ligand coordinates are noisy denoising coordinates `x_t`
- candidate edges connect the fixed target atom to ligand atoms whose current noisy coordinate lies within the candidate radius
- the positive edge is always included even if noise moves it outside the radius, and it carries a `positive_forced_into_candidate_set` flag for diagnostics
- no-edge negatives are non-attachment ligand atoms from the same local candidate set

The natural candidate set and the force-included positive set must be counted separately. A force-included positive is available for edge-existence supervision and recall diagnostics, but v1 excludes it from soft edge message passing and geometry regression for that noisy step. Bond-type loss on force-included positives is disabled by default; if an implementation enables it later, it must report a separate `forced_positive_bond_type_loss_denominator`.

At inference step `t`:

- candidate edges connect the fixed target atom to currently generated ligand atoms within the candidate radius
- no hidden ground-truth attachment atom exists
- the model emits soft edge logits for all current candidates
- soft edge probabilities may weight protein-ligand message passing

In v1, message-passing weights use predicted soft edge probabilities with stop-gradient from coordinate denoising losses. Ground-truth edge labels must not be used as message weights during training. Scheduled sampling or non-detached edge-message gradients require a later ADR or an explicit experiment section because they change the training/inference exposure boundary.

The initial candidate radius is 4.0 Angstrom. In PocketFlow this radius describes local bond-candidate construction around generated atoms. In this covalent extension it has a narrower meaning: it bounds candidate protein-ligand cross edges from the specified reactive target atom to ligand atoms in the current protein-ligand coordinate frame. It is not a pocket crop radius, not a guarantee of final covalent bond length, and not an all-pairs negative mining radius.

## Supervision Targets

The model has three learnable covalent heads:

- edge existence: binary target for each candidate cross edge
- covalent bond type: target bond type for the positive edge and masked null target for no-edge candidates
- optional reaction-family auxiliary head: predicts the conditioned family only as a diagnostic regularizer, not as the source of truth

The model also has geometry losses:

- positive-edge distance loss against family-specific covalent bond length range or target statistic
- positive-edge protein-side anchor angle loss when required atoms are available
- positive-edge ligand-side anchor angle loss when required atoms are available
- optional torsion or plane losses only for families whose rule row declares computable geometry fields

No-edge negatives participate in edge existence loss and may participate in margin-style geometry contrast only. They do not receive bond length regression, angle regression, or torsion regression targets because there is no true covalent geometry for a non-edge. If a training implementation includes a negative geometry term, it must be a non-regression penalty such as "do not score invalid near-contact geometry as covalent."

## Reaction-Family Consistency

Reaction-family consistency is represented in two forms.

Learnable losses:

- edge existence loss: computed over candidate edges that remain after non-chemical structural pruning
- bond-type loss: computed only over positive eligible edges with calibrated allowed bond types
- optional family auxiliary loss: predicts the input `residue_reaction_family` from local features for representation checking, but it cannot override the conditioning family

Non-loss gates:

- warhead SMARTS compatibility
- forbidden SMARTS rejection
- valence and protonation feasibility
- local geometry range checks
- family-specific single-edge representability checks

The rule table is the authority for both forms. A consistency failure at a hard gate is reported as invalid generation, not silently repaired into a different family.

## Loss Mask And Denominator Contract

Masking must be reported with explicit denominator counts. The implementation must distinguish:

| Count | Meaning |
| --- | --- |
| `candidate_count` | All target-to-ligand candidate edges built from the current coordinate state |
| `natural_candidate_count` | Candidates found by radius before force-including the positive edge |
| `forced_positive_count` | Positive edges appended because noise moved them outside the radius |
| `eligible_edge_count` | Candidates eligible for edge existence loss after structural validity checks |
| `masked_candidate_count` | Candidates excluded by rule masks or missing required state |
| `edge_loss_denominator` | Candidate count contributing to edge existence loss |
| `bond_type_loss_denominator` | Positive eligible edge count contributing to bond-type loss |
| `geometry_loss_denominator` | Positive edge count contributing to geometry regression losses |
| `message_passing_candidate_count` | Candidate count allowed to influence soft edge message passing |
| `gate_evaluated_count` | Final candidates evaluated by hard validity gate |

Default v1 behavior:

| Condition | Edge loss | Bond-type loss | Geometry loss | Message passing | Gate |
| --- | --- | --- | --- | --- | --- |
| natural eligible candidate | Included | Positive edge only | Positive edge only when calibrated | Included with detached predicted probability | Evaluated at final decode |
| force-included positive | Included with reported forced count | Excluded by default | Excluded | Excluded | Not applicable during training step |
| no-edge negative | Included as negative | Excluded | Excluded except optional non-regression contrast | Included when natural and eligible | Evaluated only if final candidate |
| pending geometry | Included | Included if bond type calibrated | Excluded from geometry denominator | Included when otherwise eligible | Not used for geometry-gated pass |
| pending SMARTS | Excluded from family-consistency loss | Included only if bond type calibrated | Included only if geometry calibrated | Included only for non-SMARTS components | Cannot pass SMARTS gate |
| missing required protein state | Excluded | Excluded | Excluded | Excluded | Fails with `REQUIRED_GATE_STATE_UNAVAILABLE` |

Rule masks are applied in this order:

```text
1. structural candidate construction
2. required protein chemical-state availability
3. residue-reaction-family eligibility
4. ligand atom class eligibility
5. bond-type eligibility
6. geometry availability/calibration
7. SMARTS gate availability/calibration
```

Training reports must include the denominator counts above by residue-reaction family and diffusion timestep bucket.

## Warhead Type And SMARTS Source

Training records use reaction-product adduct structures for ligand graph and geometry supervision. The `warhead_type` field is metadata and conditioning/evaluation support, not a generated label that the model is required to invent from nothing.

Source priority:

1. curated source annotation from CovalentInDB, CovPDB, or CovBinderInPDB after normalization
2. rule-table SMARTS match on the pre-reaction ligand when available
3. rule-table SMARTS match on the adduct ligand local environment when pre-reaction ligand is unavailable
4. manually curated fallback in the Rule Calibration Sheet
5. `unknown` with a low-confidence flag

During inference, `matched_warhead_type` is assigned as post-generation diagnostic evidence from generated ligand structure and the selected final covalent edge by applying the rule-table SMARTS patterns. The generator may be conditioned on a requested family, but the final `warhead_type` is not trusted until this diagnostic match succeeds.

## Final Validity Gate Versus Diagnostic Assignment

Final hard decoding occurs once after ligand denoising:

1. rebuild the candidate set from final ligand coordinates
2. score candidates with the edge and bond-type heads
3. sort candidates by valid edge score
4. apply the final validity gate
5. select the highest-scoring candidate that passes
6. if none pass, mark the sample invalid with failure reasons

The final validity gate decides whether a candidate edge can be emitted. It checks:

- target atom and residue match the requested reaction family
- ligand attachment atom class is allowed
- covalent bond type is allowed
- SMARTS compatibility and forbidden SMARTS
- valence, protonation, and local geometry feasibility
- single-cross-edge representability

Diagnostic assignment records descriptors after a candidate has passed or failed. It may assign `matched_warhead_type`, diagnostic geometry metrics, and failure reasons. It must not create a new edge, switch reaction family, alter generated ligand bonds, add or delete atoms, or convert an invalid sample into a valid one.

## Fixed Protein State, Valence, Protonation, And Geometry

Protein coordinates are fixed, but protein-side chemical state is still part of the model state and gate inputs.

The model state includes:

- target residue name and atom name
- target atom element and formal valence budget from the rule row
- target atom formal charge from the normalized record or request
- target-side expected protonation or leaving-proton state when specified
- target atom hydrogen state: `explicit`, `inferred`, `absent`, or `not_applicable`
- protein preparation policy, pH assumption when known, inference tool/version when state is inferred, and confidence flag
- required protein-side anchor atoms for angle checks
- local protein geometry derived from fixed coordinates

The model does not diffuse protein atoms and does not learn to repair protein protonation. Valence, protonation, and local geometry enter as conditioning features, masks, and hard gates. When a record or request lacks enough state to evaluate a required gate, the sample fails with `REQUIRED_GATE_STATE_UNAVAILABLE` rather than being accepted by default.

## Single Cross Edge And Reaction Families

The first model uses one protein-ligand covalent cross edge per generated complex. This is sufficient for monodentate examples of Michael addition, nucleophilic substitution, disulfide exchange, serine acylation, serine phosphonylation, and lysine Schiff base only when the reaction-product adduct can be represented as one direct protein-ligand bond plus ligand-internal bonds.

The single edge is not sufficient for:

- bidentate or tridentate binders
- multi-residue crosslinks
- metal- or cofactor-mediated covalent attachments
- families requiring two simultaneous protein-ligand bonds
- records where phosphonylation or disulfide chemistry is annotated but the product graph needs more than one protein-ligand linkage

Such records are preserved as metadata or evaluation exclusions according to ETL quality policy, but they do not enter the first training core.

## Ligand Size Sampling Contract

PMDM-style `num_atom` is the generated ligand heavy-atom count. The public request fields use `num_ligand_heavy_atoms`, `min_ligand_heavy_atoms`, and `max_ligand_heavy_atoms`; internally these map to PMDM-style `num_atom` controls.

Training:

- `num_atom` equals the heavy-atom count of the accepted ligand adduct graph
- the size predictor or size prior is trained on accepted monodentate records only
- the covalent cross edge does not add a ligand atom and does not change `num_atom`

Inference:

- if `num_ligand_heavy_atoms` is provided, sample exactly that many ligand heavy atoms
- if a size range `[min_ligand_heavy_atoms, max_ligand_heavy_atoms]` is provided, sample one heavy-atom count from the learned size prior truncated to that inclusive range
- if neither is provided, sample from the learned size prior conditioned on the pocket and reaction family
- generated samples outside the requested range are invalid sampler failures, not post-generation filtered successes

## Training Pseudoflow

```text
for each accepted CovalentComplexRecord:
    load fixed protein pocket and target atom
    load ligand adduct graph, atom types, and coordinates
    load reaction-family rule row
    sample diffusion step t
    create noisy ligand coordinates x_t
    build target-to-ligand candidate cross edges using x_t and radius
    force-include the positive edge if radius noise excluded it
    label positive edge and no-edge negatives
    run PMDM ligand denoising network with soft covalent edge head
    compute PMDM coordinate and atom-type losses
    compute edge existence loss over candidates
    compute bond-type loss on positive eligible natural edges
    compute positive geometry losses where masks are available
    compute optional no-edge contrast penalties, not regression geometry losses
    apply reaction-family masks to losses and record denominator counts
    log hard-gate diagnostics without using them to hide training labels
```

## Inference Pseudoflow

```text
input protein, target atom, residue-reaction family, sample count, optional size controls
resolve reaction-family rule row
sample num_atom from fixed value, truncated range, or learned prior
initialize ligand state

for each denoising step:
    build target-to-current-ligand candidate cross edges
    predict soft edge probabilities and bond-type logits
    use detached predicted soft edge probabilities for protein-ligand message passing
    update ligand atom and coordinate state

reconstruct final ligand graph
build final target-to-ligand candidate cross edges
score candidates
for candidate in descending score order:
    apply final validity gate
    if candidate passes:
        emit selected covalent edge and complex
        assign matched_warhead_type and diagnostics after generation
        return valid sample

return invalid sample with no emitted covalent edge and gate failure reasons
```

## Model Behavior Versus Non-Learnable Constraints

Model behavior:

- ligand atom count sampling or conditioning
- ligand atom-type denoising
- ligand coordinate denoising
- soft cross-edge existence scoring during denoising
- bond-type scoring for eligible candidate edges
- local representation learning from reaction-family conditioning

Non-learnable constraints:

- accepted reaction-family vocabulary
- target residue and target atom eligibility
- allowed and forbidden warhead SMARTS
- valence and protonation feasibility gates
- final local geometry validity ranges
- monodentate-only first training core
- single final hard edge emission
- invalid sample reporting when no candidate passes

The implementation may expose non-learnable constraints as masks during training, but masked feasibility must not be described as learned chemical understanding.

## Acceptance Checklist

- [ ] Stepwise candidates are built from fixed protein coordinates and current noisy or generated ligand coordinates.
- [ ] The positive training edge is force-included when diffusion noise moves it outside the radius.
- [ ] Force-included positives are counted separately and excluded from v1 soft edge message passing and geometry regression.
- [ ] No-edge negatives train edge existence and optional contrast terms only, not bond or angle regression.
- [ ] The 4.0 Angstrom radius is documented as covalent cross-edge candidate radius, not pocket radius.
- [ ] Final validity gate can reject every candidate and produce an invalid sample.
- [ ] Diagnostic assignment cannot create, repair, or switch covalent edges.
- [ ] Reaction-family consistency has explicit loss masks and explicit non-loss gates.
- [ ] Loss reports include candidate, eligible, masked, forced-positive, and denominator counts by family and timestep bucket.
- [ ] Warhead type source priority is recorded and post-generation inference matching is separated from generation.
- [ ] Fixed-protein valence, protonation, and local geometry are available as state, masks, or hard gates.
- [ ] Single-cross-edge limitations are enforced for disulfide, phosphonylation, and other edge cases.
- [ ] `num_ligand_heavy_atoms` maps to PMDM-style `num_atom`, remains ligand heavy-atom count, and optional size ranges are sampled before denoising.
- [ ] Evaluation reports separate model failures from non-learnable gate failures.
