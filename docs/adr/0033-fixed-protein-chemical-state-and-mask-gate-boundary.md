# Fixed Protein Chemical State And Mask/Gate Boundary

## Status

Accepted

## Date

2026-05-19

## Context

The first model keeps protein coordinates fixed, but covalent validity depends on protein-side chemical state: target atom formal charge, protonation, hydrogen availability, valence budget, and local anchor geometry. Earlier documents made valence and protonation part of the final gate, but did not make the required state explicit enough to reproduce or audit the gate.

The second-round review also found that rule masks, pending geometry, force-included positives, and hard gates could silently change loss denominators. Without an explicit boundary, a report could claim learned covalent edge performance while rule masks or missing-state exclusions removed difficult examples.

## Decision

Fixed protein coordinates do not imply implicit protein chemistry. Every record or request that uses valence, protonation, or geometry gates must carry protein-side chemical state or a recorded unavailable state.

Protein-side chemical state includes:

- protein preparation policy
- target atom formal charge
- target atom protonation state
- target atom hydrogen state
- state source: explicit, structure-derived, or inferred
- inference tool/version/confidence when inferred

The first model does not learn to repair missing protein chemical state. Required missing state fails with `REQUIRED_GATE_STATE_UNAVAILABLE` or the stage-specific request/ETL equivalent. It must not pass by default.

Rule masks and hard gates must expose denominator counts. At minimum, training and evaluation reports must distinguish candidate count, eligible count, masked count, forced-positive count, loss denominators, message-passing count, and hard-gate evaluated count.

Force-included positive edges are allowed for training label retention and diagnostics, but v1 excludes them from soft edge message passing and geometry regression for the noisy step. Soft edge message passing uses detached predicted probabilities in v1; ground-truth edge labels are not message weights.

## Alternatives Considered

### Treat PDB/mmCIF coordinates as sufficient protein state

Rejected. Most structures do not provide enough hydrogen/protonation information for reproducible valence and protonation gates.

### Let final hard gates infer missing state permissively

Rejected. Permissive inference would make invalid structures pass differently across tools and environments.

### Let the model learn or repair protein-side state

Rejected for v1. The project is a fixed-protein ligand diffusion extension, not protein-state generation or protonation repair.

### Hide masks inside implementation details

Rejected. Hidden masks make loss values and validity metrics incomparable across families, timesteps, and pending-rule states.

## Consequences

ETL records, generation requests, model training reports, and evaluation summaries must carry explicit chemical-state and denominator evidence. This increases schema and reporting complexity, but makes valence/protonation gates reproducible and prevents rule masks from masquerading as learned model behavior.

ADR 0031 remains the authority for stepwise edge supervision. ADR 0032 remains the authority for generation result and evaluation semantics. This ADR governs protein-side chemical state and mask/gate denominator boundaries used by both.
