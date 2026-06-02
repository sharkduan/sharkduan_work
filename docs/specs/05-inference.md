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
# Task 26 (implemented)
python -m covalent_design.inference.validate_request --request request.yml [--rules <path>]
# --rules defaults to data/rules/reaction_family_rule_table.yml (auto-discovered from repo root)
# Output: deterministic JSON to stdout; exit 0 on success; exit 20 on ContractError

# Task 27 (implemented; Python API only — no CLI)
# generate(request, policy, *, output_dir, job_id, sampler, result_sink, ...) -> ContractEnvelope[GenerationRunManifest]

# Task 28 (implemented; Python API only — no CLI)
# Integrates with Task 27 via generate(..., result_sink=ResultWriter().write)

# Task 29 (implemented; Python API only - no CLI)
python -m compileall -q scripts src
```

## Project Structure

```text
src/covalent_design/inference/
  request_schema.py        # Task 26: ReactiveSiteGenerationRequest, ValidatedRequest, ProteinAtomLocator, etc.
  request_validation.py    # Task 26: load, validate, normalized YAML output
  validate_request.py      # Task 26: CLI entry point
  sampler.py               # Task 27 (implemented)
  run_manifest.py           # Task 27 (implemented)
  final_decode.py           # Task 21: in model/, not inference/
  validity_gate.py          # Task 21: in model/, not inference/
  result_schema.py          # Task 28 (implemented)
  result_writer.py          # Task 28 (implemented)
  complex_export.py         # Task 29 (implemented)

src/covalent_design/io/
  structure_reader.py       # Task 26: pure-Python PDB/mmCIF atom-level reader
  mmcif_writer.py           # Task 29 (implemented)
```

## Request Schema And Validation (Task 26)

### Public Types

`ReactiveSiteGenerationRequest` fields:
- `request_id: str`
- `protein_structure_uri: str`
- `protein_structure_format: str` — `"pdb"` or `"mmcif"`
- `target_atom_identity_request: ProteinAtomLocator` — chain_id, residue_number, residue_name, atom_name, insertion_code, structure_model, asym_id
- `residue_reaction_family: str`
- `sample_count: int`
- `size_control: LigandSizeControl | None` — fixed (num_ligand_heavy_atoms), range (min/max), or absent
- `protein_chemical_state_request: ProteinChemicalStateRequest | None`
- `target_altloc: str | None` — explicit altloc override

`ValidatedRequest` fields:
- `request: ReactiveSiteGenerationRequest`
- `resolved_target_atom_identity: ProteinAtomIdentity`
- `resolved_target_altloc: str | None`
- `rule_table_version: int`

### Error Codes

Exactly 13 `REQUEST_*` error codes (defined in `contracts/types.py`).  No 14th code.
Unknown extension and malformed request files both map to `REQUEST_STRUCTURE_UNREADABLE`.
Each raises `ContractError(owner="request", code=...)`.

### Structure Reader

`structure_reader.py` is pure Python with PDB/mmCIF atom-level boundary only.
Preserves `structure_model`, `atom_serial`, `altloc`, `occupancy`, `insertion_code`,
`asym_id`.  No RDKit, no torch.

### Normalized Output

`write_normalized_request(validated, path)` writes deterministic UTF-8 YAML.
It is a public API callable by Task 27 — Task 26 validation does not write
generation, checkpoint, sampling, or normalized artifacts.

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

Request fixtures (all 13 REQUEST_* error codes, no 14th code):

- Structure unreadable (unknown extension, malformed YAML/JSON, missing file, no ATOM/HETATM records).
- Target residue not found.
- Target residue ambiguous.
- Target atom not found (including nonexistent altloc override).
- Residue name mismatch.
- Unsupported family.
- Residue/family conflict.
- Atom/family conflict.
- Invalid sample count (zero, negative, non-integer, bool).
- Ligand size invalid (fixed: zero, negative, non-integer).
- Ligand size range invalid (min>max, non-positive, non-integer, missing bound).
- Ligand size conflict (fixed + range).
- Required chemical state unavailable (missing entirely or partial).

Sampling/result fixtures:

- No covalent edge predicted.
- Edge below threshold.
- Rule failure.
- Warhead match failure.
- Valence failure.
- Geometry failure.
- Sampling system failure artifact for crash, timeout, OOM, retry_exhausted, checkpoint_load_failed, or sampler_invariant_violation.
- Valid result with mmCIF export.
- Valid internal result with export failure.
- Invalid result preserving diagnostics.

## Boundaries

Task 26 (implemented):
- Validate `ReactiveSiteGenerationRequest` before any sampling.
- 13 REQUEST_* error codes; request validation failure is a request contract error, not an invalid generated sample.
- Structure reader is pure Python (PDB/mmCIF atom-level); no RDKit, no torch.
- `write_normalized_request()` is a deterministic UTF-8 YAML writer callable by Task 27.
- Task 26 does not write generation, checkpoint, sampling, or normalized artifacts.
- CLI: `python -m covalent_design.inference.validate_request --request <path> [--rules <path>]`. Default rules: `data/rules/reaction_family_rule_table.yml`.

Task 27 (implemented):
- `generate(request, policy, *, output_dir, job_id, sampler, result_sink, checkpoint_ref=None, checkpoint_loader=None, clock=None, traceback_normalizer=None) -> ContractEnvelope[GenerationRunManifest]`.
- `SamplingPolicy` requires `max_retries: int` and `retry_on_categories: tuple[str, ...]` explicitly. Retry defaults remain deliberately unfrozen.
- `SamplingSystemFailure` events use 6 categories: `crash`, `oom`, `timeout`, `retry_exhausted`, `checkpoint_load_failed`, `sampler_invariant_violation`.
- `retry_exhausted` is an emitted terminal sentinel and cannot be configured as a retry trigger.
- Generation writes `request.normalized.yml` first (before checkpoint loading), then creates sibling layout: `run_manifest.yml`, `results.jsonl`, `sampling_system_failures.jsonl`, `logs/`.
- `result_sink` is wired to ``ResultWriter.write()`` through ``generate(result_sink=writer.write)``.  See `implementation-plan.md` Task 28.
- `sampler`, `checkpoint_loader`, `clock`, and `traceback_normalizer` are injectable boundaries. No real PMDM, PocketFlow, torch, RDKit, Task 29 export, or Task 30 evaluation implementation.
- Accounting at sample_id granularity: `accepted_request_sample_count = attempted_sample_count + sampling_system_failure_count`. Retries do not change the denominator.
- Every intermediate failure attempt row remains in `sampling_system_failures.jsonl`. A fully exhausted sample adds an extra `retry_exhausted` terminal sentinel row, but `sampling_system_failure_count` counts that failed sample once.
- `checkpoint_load_failed` rows are emitted per accepted sample id.
- No standalone CLI for Task 27.

Task 29 (implemented):
- Project-owned pure-Python mmCIF writer (`io/mmcif_writer.py`), deterministic UTF-8 LF bytes; no RDKit, torch, PMDM, or PocketFlow.
- `write_covalent_complex(result, protein_atom_table, ligand_coords, ligand_atom_types, ligand_bonds, covalent_edge, out_path, *, artifact_root) -> ArtifactRef`.
  - Input protein table is ``ArtifactRef`` JSON with explicit keyword-only ``artifact_root``; no cwd guessing.
  - Input and output paths reject absolute, traversing, and root-escaping boundaries.
  - Writes ``_entry.id``, ``_atom_site.*`` (protein ``ATOM`` + ligand ``HETATM``), and exactly one ``_struct_conn.*`` row with ``conn_type_id = covale``.
  - Ligand identity: element-local names (``C1``, ``C2``, ``N1``), ``label_asym_id=L``, ``label_seq_id=1``, ``label_comp_id=LIG``, entity id ``2``.
  - Output ``ArtifactRef``: ``role=complex_mmcif``, ``format=mmcif``, root-relative URI, exact bytes, sha256.
  - Writer validation/read/write errors raise ``ContractError(code=COMPLEX_EXPORT_FAILED, owner=inference)``.
- `export_covalent_complex_result(...) -> CovalentGenerationResult`: success adapter using ``dataclasses.replace`` - sets exported/eligible/not_run and adds ``complex_mmcif`` ArtifactRef.
- `adapt_complex_export_failure(result) -> CovalentGenerationResult`: failure adapter - preserves generation-valid diagnostics, sets failed/not_applicable/not_applicable and ``COMPLEX_EXPORT_FAILED``.
- Export failure is not a sampling-system failure.
- PDB compatibility output is optional future compatibility output only - not implemented.
- RDKit was re-verified on 2026-06-02: ``rdkit.Chem.rdmolfiles`` contains no ``MolToMMCIFBlock`` symbol. RDKit remains an optional future backend requiring source verification; default CI uses the project-owned writer and does not depend on RDKit.
- No standalone CLI for Task 29.
- No Task 30 behavior, docking, PMDM, or PocketFlow.

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

Resolved (2026-05-26 contract freeze, Task 26 implemented; 2026-06-02 Task 27, Task 28, Task 29 implemented):

- **Request file format:** YAML (`.yml`/`.yaml`) authoritative; JSON (`.json`) accepted. CLI auto-detects by extension. Unknown extension → `REQUEST_STRUCTURE_UNREADABLE`.
- **Default pocket radius:** 4.0 angstroms (same as candidate_radius). Sampling steps: TBD.
- **Altloc policy:** Highest occupancy or `A`; `target_altloc` override field. Single-conformer resolves to `None`. See `interface-design.md`.
- **Retry policy:** sample_id granularity; retries do not change denominator equations. `SamplingPolicy` requires `max_retries` (int) and `retry_on_categories` (tuple[str, ...]) explicitly. Retry defaults remain deliberately unfrozen. `retry_exhausted` is an emitted terminal sentinel and cannot be configured as a retry trigger.
- **mmCIF writer:** project-owned writer/adapter boundary implemented (Task 29). RDKit is a future optional backend only after the exact API is source-verified; default CI uses the project-owned writer. Source-verification status (2026-06-02): the official RDKit `rdkit.Chem.rdmolfiles` API reference (`https://rdkit.org/docs/source/rdkit.Chem.rdmolfiles.html`) was re-checked and no `MolToMMCIFBlock` symbol was found. RDKit remains an optional future backend requiring source verification.
- **Normalized request output:** `write_normalized_request()` produces deterministic UTF-8 YAML. Called by Task 27 `generate()`, not an implicit side effect of Task 26 validation.
- **Generation run manifest:** `generate()` returns `ContractEnvelope[GenerationRunManifest]`. `SamplingSystemFailure` is a 9-field frozen dataclass with 6 failure categories: `crash`, `oom`, `timeout`, `retry_exhausted`, `checkpoint_load_failed`, `sampler_invariant_violation`. Artifacts use `run_manifest.yml`, not `generation_manifest.yml`. ``result_sink``, ``sampler``, ``checkpoint_loader``, ``clock``, and ``traceback_normalizer`` are injectable boundaries.
- **No Task 27 CLI:** `generate()` is a Python API called from orchestration code.
- **Complex export adapter (Task 29):** `export_covalent_complex_result(...)` and `adapt_complex_export_failure(...)` are immutable `dataclasses.replace()` adapters. Export failure is `ContractError(code=COMPLEX_EXPORT_FAILED, owner=inference)`, not a sampling-system failure.

Still open for v1:

- What default sampling step count should be used when omitted?
- What concrete ``max_retries`` and ``retry_on_categories`` defaults should ship for v1?
- Exact ``SamplingPolicy`` defaults beyond the required fields.
