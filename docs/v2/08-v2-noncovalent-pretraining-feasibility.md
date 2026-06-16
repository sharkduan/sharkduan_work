# V2 Noncovalent Pretraining Feasibility

Date: 2026-06-16
Status: experimental, non-blocking

## Pretraining Verdict

Noncovalent pretraining is experimental and is not part of the v2-beta mainline. It must not block v2-beta completion.

## Transfer Hypothesis

The hypothesis is that noncovalent protein-ligand pretraining may improve geometric and interaction representations before covalent fine-tuning. This is unverified for this project.

## Candidate Datasets

Potential future datasets require official source and license verification before use:

- PDBbind
- CrossDocked2020
- ChEMBL-derived ligand or complex sets
- Binding MOAD
- other source-verified protein-ligand corpora

No candidate dataset is accepted into v2-beta mainline by this document.

## Label Compatibility

Before implementation, prove:

- input structures can map to `Protein-Ligand Complex Graph`,
- noncovalent labels do not conflict with covalent edge supervision,
- pretraining targets transfer to the PMDM-compatible extension,
- covalent fine-tuning can still preserve residue-reaction family conditioning.

## License Risk

Any dataset with unknown or incompatible license status is excluded. License audit is mandatory before download, training, or publication use.

## License Status

No candidate dataset currently has an accepted license status for v2-beta. Each future candidate must record license status, evidence URL, allowed use, redistribution constraints, and citation requirements before data is downloaded or used.

## Ablation Plan

A later experimental plan must compare:

- no pretraining baseline,
- noncovalent pretraining,
- covalent fine-tuning performance,
- validity and geometry metrics,
- compute cost.

## Rejection Criteria

Reject or defer pretraining if:

- data is unavailable,
- license is unknown or blocked,
- labels are incompatible,
- transfer hypothesis fails a small pilot,
- evaluation cannot prove benefit,
- effort slows the v2-beta minimum closed loop.

## Fallback Plan

Proceed with v2-beta PMDM or `non_pmdm_baseline` training without pretraining.

## Feasibility Checklist

Task 57 must fill every item before a verdict:

- transfer hypothesis,
- candidate datasets,
- license status,
- label compatibility,
- pretraining objective,
- fine-tuning strategy,
- ablation plan,
- rejection criteria,
- compute budget,
- evaluation metrics,
- final verdict.

Allowed final verdict values:

- `accepted`: may open a separate implementation task/checkpoint.
- `experimental`: may run only in an explicitly approved optional track.
- `rejected`: no implementation task should be opened.
- `unresolved`: remains deferred and non-blocking for v2-beta.

## Final Verdict

Current verdict: `unresolved`.

Reason: source/license verification and label compatibility are not complete. This does not block v2-beta.
