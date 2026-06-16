# Task 29 mmCIF Export Review

Date: 2026-06-02

## Scope

Task 29 implements the project-owned pure-Python mmCIF writer and immutable
complex-export adapters. It does not implement docking, evaluation, Task 30,
RDKit integration, PDB compatibility output, or sampling orchestration changes.

## Collaboration Record

- Window A completed read-only interface planning.
- Window B completed Plan Mode before writing tests and fixtures.
- Window C completed Plan Mode before implementation authorization, then
  exceeded the controller timeout. The main controller terminated the lingering
  Claude Code process and took over the minimal implementation and verification
  loop.
- Window D completed Plan Mode before synchronizing documentation.
- Window E completed a read-only adversarial review after implementation and
  documentation sync. It reported no blockers.

## Implemented Boundary

- `covalent_design.io.mmcif_writer.write_covalent_complex(...) -> ArtifactRef`
- `covalent_design.inference.complex_export.export_covalent_complex_result(...)`
- `covalent_design.inference.complex_export.adapt_complex_export_failure(...)`

The writer consumes an explicit `ArtifactRef` protein atom table and a
keyword-only `artifact_root`. It rejects absolute, traversal, and root-escaping
paths; validates checksums; writes deterministic UTF-8 LF mmCIF bytes; and
returns a root-relative `complex_mmcif` `ArtifactRef` with exact size and
SHA-256.

The mmCIF contains `_entry.id`, protein `ATOM` and ligand `HETATM`
`_atom_site.*` rows, and exactly one `_struct_conn.*` row with
`conn_type_id = covale`. Ligand identity is deterministic:
element-local atom names, `label_asym_id = L`, `label_seq_id = 1`,
`label_comp_id = LIG`, and ligand entity id `2`.

## Lifecycle Semantics

- Successful export uses immutable `dataclasses.replace()`:
  `exported / eligible / not_run`, with `artifacts["complex_mmcif"]`.
- Failed export uses immutable `dataclasses.replace()`:
  `failed / not_applicable / not_applicable`, with
  `primary_failure_reason = COMPLEX_EXPORT_FAILED`.
- Writer boundary errors are
  `ContractError(code="COMPLEX_EXPORT_FAILED", owner="inference")`.
- Export failure preserves the generation-valid internal result and is not a
  sampling-system failure.

## Source Verification

The implementation and docs are grounded in the official wwPDB PDBx/mmCIF
dictionary:

- <https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Categories/entry.html>
- <https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Categories/atom_site.html>
- <https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Categories/struct_conn.html>
- <https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_struct_conn.conn_type_id.html>

The official RDKit `rdkit.Chem.rdmolfiles` API reference was checked again on
2026-06-02:

- <https://rdkit.org/docs/source/rdkit.Chem.rdmolfiles.html>

No `MolToMMCIFBlock` symbol was found. RDKit remains an optional future backend
requiring source verification and is not a default dependency.

## Verification

- `python -m unittest tests.inference.test_complex_export -v`
- `python -m unittest tests.inference.test_result_writer -v`
- `python -m unittest tests.inference.test_sampling_failures -v`
- `python -m unittest tests.inference.test_request_validation -v`
- `python -m unittest tests.contracts.test_lifecycle -v`
- `python -m unittest discover -s tests -t . -q`
- `python -m compileall -q scripts src`

## Review Result

Task 29 has no blocking findings. Task 30 may start after main-controller
acceptance. No files were staged or committed.
