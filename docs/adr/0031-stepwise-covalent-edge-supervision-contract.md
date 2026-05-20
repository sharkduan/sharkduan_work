# Stepwise Covalent Edge Supervision Contract

## Status

Accepted

## Date

2026-05-19

## Context

The first model will supervise covalent cross-edge prediction at each denoising step using candidates from the fixed target protein atom to ligand atoms in the current noisy ligand coordinate state. The ground-truth ligand attachment atom is the positive edge and must be force-included if noise moves it outside the candidate radius; other local candidates are no-edge negatives for edge-existence learning, not bond-geometry regression targets.

## Decision

This decision makes stepwise covalent supervision part of the PMDM diffusion trajectory rather than a final-only annotation task. It also fixes the meaning of the migrated 4.0 Angstrom radius: it is a local covalent cross-edge candidate radius around the specified target atom in the current protein-ligand frame, not a pocket crop radius and not an all-pairs negative sampler.

Final hard edge emission remains a non-learnable decode-and-gate step after denoising. Reaction-family rules, valence and protonation feasibility, warhead SMARTS compatibility, local geometry ranges, and single-cross-edge representability may mask losses or reject decoded candidates, but diagnostic assignment may only label matched warhead type and failure reasons. It must not create, repair, or switch the selected covalent edge.

Protein-side chemical state, forced-positive participation, and loss/gate denominator reporting are governed by ADR 0033.

## Consequences

The consequence is that the first model learns soft edge scoring and ligand geometry under explicit supervision, while chemical validity remains auditable through rule-backed gates. This is harder to implement than final-only assignment because candidate sets must be rebuilt at every denoising step, but it prevents a model that appears covalent only because a post-processor attaches an edge after generation.
