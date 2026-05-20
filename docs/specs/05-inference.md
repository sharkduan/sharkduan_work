# Spec: Inference

## Objective

Implement the `ReactiveSiteGenerationRequest -> CovalentGenerationResult[]` path. Inference validates a user-provided protein reactive site and `residue_reaction_family`, samples complete ligands de novo with optional ligand heavy-atom size controls, predicts soft covalent edges during denoising, performs final hard covalent edge decoding, applies the rule-first validity gate, and writes valid and invalid sample results with complete lifecycle metadata.

Inference does not require a reference ligand, scaffold, warhead motif, or user-provided ligand attachment atom.

## Tech Stack

- Python 3.9-compatible project-owned inference code.
- PyTorch model checkpoint loading.
- Structure parsing and mmCIF export helpers.
- Rule table validator and shared request/result schemas.

## Commands

```bash
python -m covalent_design.inference.validate_request --request request.yml
python -m covalent_design.inference.generate --request request.yml --checkpoint outputs/checkpoints/model.pt --out outputs/generation/<job_id>
python -m covalent_design.inference.export_complexes --results outputs/generation/<job_id>/results.jsonl
python -m covalent_design.inference.summarize --results outputs/generation/<job_id>/results.jsonl
python -m compileall -q scripts src
```

## Project Structure

```text
src/covalent_design/inference/
  request_schema.py
  request_validation.py
  sampler.py
  final_decode.py
  validity_gate.py
  result_schema.py
  result_writer.py
  complex_export.py

src/covalent_design/io/
  structure_reader.py
  mmcif_writer.py
```

## Code Style

Request validation happens before sampling. Sample-level generation failures produce `CovalentGenerationResult` rows.

```python
validation = validate_request(request, rule_table)
if not validation.ok:
    return RequestValidationError(validation.error_code)

for sample_id in range(request.sample_count):
    try:
        result = sampler.sample_one(request, sample_id)
    except SamplingSystemFailure as failure:
        run_writer.write_sampling_system_failure(request, sample_id, failure)
        continue
    result_writer.write(result)
```

Rules:

- Protein atom identity uses model, chain/asym namespace, residue id, insertion or alternate-location qualifiers, residue name, and atom name.
- `num_ligand_heavy_atoms` maps to PMDM-style `num_atom`.
- A size range is sampled before denoising, not repaired after generation.
- Sampler crash, OOM, timeout, and retry exhaustion are `sampling_system_failure_count` events. They are not invalid generated samples because no attempted sample result exists.
- Diagnostic assignment can record matched warhead type and geometry evidence, but cannot create or repair a covalent edge.
- mmCIF is authoritative; PDB LINK/CONECT export is optional compatibility output.

## Testing Strategy

Request fixtures:

- Structure unreadable.
- Target residue not found.
- Target residue ambiguous.
- Target atom not found.
- Residue name mismatch.
- Unsupported family.
- Residue/family conflict.
- Atom/family conflict.
- Invalid sample count.
- Ligand size fixed/range conflict.
- Required chemical state unavailable.

Sampling/result fixtures:

- No covalent edge predicted.
- Edge below threshold.
- Rule failure.
- Warhead match failure.
- Valence failure.
- Geometry failure.
- Sampling system failure artifact for crash, timeout, OOM, or retry exhaustion.
- Valid result with mmCIF export.
- Valid internal result with export failure.
- Invalid result preserving diagnostics.

## Boundaries

Always:

- Reject request conflicts before sampling.
- Return one result row per attempted sample.
- Record a run-level sampling-system-failure artifact for accepted request samples that fail before a sample result exists.
- Preserve invalid sample diagnostics where available.
- Use rule table gates as the authority for family, atom, bond, SMARTS, valence, protonation, geometry, and single-edge representability.

Ask first:

- Requiring reference ligands, scaffolds, or warhead motifs.
- Supporting batch requests with multiple target sites.
- Changing mmCIF-first output policy.
- Adding new request fields that change denominator accounting.

Never:

- Count request validation errors as invalid generated samples.
- Emit ligand-only SDF as the complete result.
- Force the top-scoring covalent edge when no candidate passes the validity gate.
- Treat `predicted_warhead_type` as authoritative validity evidence.
- Convert invalid samples into valid samples during export or diagnostics.

## Success Criteria

- A valid request resolves the target atom and required protein chemical state before sampling.
- Every attempted sample produces exactly one `CovalentGenerationResult`.
- Accepted request sample counts reconcile as `attempted_sample_count + sampling_system_failure_count`.
- Valid results include predicted ligand attachment atom, predicted covalent edge, matched warhead evidence, geometry metrics, and mmCIF export status.
- Invalid results include primary failure reason, secondary failure reasons, edge validity checks when evaluated, and any available ligand/edge diagnostics.
- Sample counts reconcile with evaluation denominator equations.

## Open Questions

- Should request files be YAML, JSON, or both?
- What default pocket radius and sampling step count should be used when omitted?
- How should alternate-location atoms be selected or rejected?
- Should sampling failures be retried, and if so how are retries counted?
- Which mmCIF writer library or internal writer should be used?
