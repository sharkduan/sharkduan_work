# mmCIF-First Covalent Complex Output

Generated covalent protein-ligand complexes are saved primarily as mmCIF with structured atom-level covalent linkage records. A PDB LINK/CONECT compatibility export may be added later for visualization and older tool compatibility. PDB-only output is rejected because mmCIF better preserves chain, residue, atom, connection type, and distance information for covalent protein-ligand attachments.

## Status: Implemented (Task 29, 2026-06-02)

The project-owned pure-Python mmCIF writer is implemented in `src/covalent_design/io/mmcif_writer.py`. The public adapter boundary is in `src/covalent_design/inference/complex_export.py`.

### Public API

- `write_covalent_complex(result, protein_atom_table, ligand_coords, ligand_atom_types, ligand_bonds, covalent_edge, out_path, *, artifact_root) -> ArtifactRef`
- `export_covalent_complex_result(...) -> CovalentGenerationResult`
- `adapt_complex_export_failure(result) -> CovalentGenerationResult`

### Key design choices

- Project-owned pure-Python writer, deterministic UTF-8 LF bytes; no RDKit, torch, PMDM, or PocketFlow.
- Input protein table is `ArtifactRef` JSON with explicit keyword-only `artifact_root`; no cwd guessing.
- Input and output paths reject absolute, traversing, and root-escaping boundaries.
- Writes `_entry.id`, `_atom_site.*` (protein `ATOM` + ligand `HETATM`), and exactly one `_struct_conn.*` row with `conn_type_id = covale`.
- Ligand identity is deterministic: element-local names (`C1`, `C2`, `N1`), `label_asym_id=L`, `label_seq_id=1`, `label_comp_id=LIG`, entity id `2`.
- Output `ArtifactRef`: `role=complex_mmcif`, `format=mmcif`, root-relative URI, exact bytes, sha256.
- Success and failure adapters are immutable `dataclasses.replace()` updates.
- Success sets exported / eligible / not_run and adds `complex_mmcif` ArtifactRef.
- Failure preserves generation-valid diagnostics, sets failed / not_applicable / not_applicable and `COMPLEX_EXPORT_FAILED`.
- Writer validation/read/write errors raise `ContractError(code=COMPLEX_EXPORT_FAILED, owner=inference)`.
- Export failure is not a sampling-system failure.
- PDB compatibility output (LINK/CONECT) is optional future compatibility output only - not implemented.

### RDKit backend status

The official RDKit `rdkit.Chem.rdmolfiles` API reference was checked on 2026-05-27 and re-checked on 2026-06-02. No `MolToMMCIFBlock` symbol was found. RDKit remains an optional future backend requiring source verification; default CI uses the project-owned writer and does not depend on RDKit.

### Official mmCIF references

- https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Categories/entry.html
- https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Categories/atom_site.html
- https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Categories/struct_conn.html
- https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_struct_conn.conn_type_id.html
- https://rdkit.org/docs/source/rdkit.Chem.rdmolfiles.html
