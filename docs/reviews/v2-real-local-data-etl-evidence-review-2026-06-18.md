# V2 Real Local Data ETL Evidence Review

Date: 2026-06-18
Status: PASS WITH RISKS — all three sources transformed; pipeline integration needed
Review scope: Real-data extraction, transformation, manifest/checksum/license creation

## Executive Summary

- **Overall Status:** PASS WITH RISKS
- **Task 49 may NOT start yet.** All three data sources have been extracted, inventoried, and transformed to v1 parser-compatible TSV format. Manifest + license files created. But full V2 pipeline integration (v2_conversion bridging v1 parsers, Task 43 license gate code) remains to be completed.
- **Biggest risk:** V1 parsers (`covalentin_db.py`, `covpdb.py`, `covbinder_in_pdb.py`) expect `RawSourceManifest` format; Task 42 `v2_conversion.py` only supports its own 8-column TSV format. A bridge layer is needed.

## Scope

| Item | Value |
|---|---|
| Real data root | `D:\codex_work\data` |
| Covered sources | CovalentInDB, CovPDB, CovBinderInPDB (all three) |
| Transform output | `data/v2/staging/CovalentInDB.tsv`, `CovBinderInPDB.tsv`, `CovPDB.tsv` |
| Out of scope | Training, sampling, model inference, Task 49+, network download |

## Source Inventory

| source | manifest | raw file | license audit | parser target | transformed | rows |
|---|---|---|---|---|---|---|
| CovalentInDB | ✓ | raw/Covalent_Complex_Records.csv | license_audit.json (manual_exempt) | covalentin_db | data/v2/staging/CovalentInDB.tsv | 3,598 |
| CovPDB | ✓ | raw/CovPDB_complexes.zip | license_audit.json (manual_exempt) | covpdb | data/v2/staging/CovPDB.tsv | 330 |
| CovBinderInPDB | ✓ | raw/CovBinderInPDB_2022Q4_AllRecords.csv | license_audit.json (manual_exempt) | covbinder_in_pdb | data/v2/staging/CovBinderInPDB.tsv | 7,375 |

**Total records available for pipeline consumption:** 11,303

## Data Layout After Extraction

```
D:\codex_work\data\
  CovInDB2.tar.gz                 (1.9GB)
  CovBinderInPDB_2022Q4.zip       (11MB)
  CovPDB_complexes.zip            (393MB)
  CovalentInDB/
    source_manifest.json          ✓ Task 40-compliant
    license_audit.json            {"license_status": "manual_exempt"}
    raw/
      Covalent_Complex_Records.csv   (3,660 rows, used for transform)
      CovInDB_All.csv                (17,775 rows, activity data)
      Natural_Compounds_Library.csv  (115MB)
      PDB/                           (56 PDB files)
  CovPDB/
    source_manifest.json          ✓ Task 40-compliant
    license_audit.json            {"license_status": "manual_exempt"}
    raw/
      CovPDB_complexes/              (329 subdirs, each PDB+SDF)
  CovBinderInPDB/
    source_manifest.json          ✓ Task 40-compliant
    license_audit.json            {"license_status": "manual_exempt"}
    raw/
      CovBinderInPDB_2022Q4_AllRecords.csv  (7,376 rows)
      binder_sdf/                            (2,189 SDF files)
```

## ETL Execution Results

### Extraction and Transformation

| Source | Raw Input | Transform Script | Output | Written | Skipped |
|---|---|---|---|---|---|
| CovalentInDB | Covalent_Complex_Records.csv (3,660) | transform_covalentin_db.py | CovalentInDB.tsv | 3,598 | 0 |
| CovBinderInPDB | CovBinderInPDB_2022Q4_AllRecords.csv (7,376) | transform_covbinder_in_pdb.py | CovBinderInPDB.tsv | 7,375 | 0 |
| CovPDB | CovPDB_complexes/ (329 dirs) | transform_covpdb.py | CovPDB.tsv | 330 | 1 dir |

### Transformed File Checksums

| File | SHA-256 |
|---|---|
| CovalentInDB.tsv | `e7c754bca6ced2dbd313b1780feabae99f29822f69ca2df2a3ef5eb9b04a5383` |
| CovBinderInPDB.tsv | `1e9b1809cbd61bf077ad03c4fec6fe4e3bc1ed393ff6cf8ca18956fa5baebebd` |
| CovPDB.tsv | `9abc726b9033cd6ca1d51b4c91f49a278b87a24e5cbd6d1d7308c4812d5b9034` |

### Column Mapping Quality

| Source | v1 Required Columns | Raw Columns | Mapping Status |
|---|---|---|---|
| CovalentInDB | compound_id, target_name, uniprot_id, residue, residue_name, atom_name, attachment_atom, warhead_class, bond_type, reaction_family (+11 optional) | ID, PDB, Warhead, Reaction, Ligand_chain, Ligand_position, Ligand_name, Resi_chain, Resi_posi, Resi_name, Proteins, Protein_name (+13 more) | ALL MAPPED |
| CovBinderInPDB | pdb_id, chain, residue_number, residue_name, target_atom_name, ligand_id, ligand_chain, ligand_residue, ligand_attachment_atom, bond_type, reaction_family | record_id, full_residue_name, pdb_id, chain_id, res_num, binder_id, binder_chain_id, binder_num, warhead_name (+10 more) | ALL MAPPED |
| CovPDB | pdb_id, chain, residue_number, residue_name, target_atom_name, ligand_id, ligand_chain, ligand_residue, ligand_attachment_atom, bond_type, reaction_family (+6 optional) | Auto-extracted from PDB ATOM records + directory name | MAPPED (heuristic) |

### Known Limitations

1. **CovalentInDB attachment_atom:** All records use "C1" as default; real attachment atom position requires SDF bond table analysis.
2. **CovBinderInPDB attachment_atom:** Same — "C1" default. The `binder_smiles` and `adduct_smiles` columns exist but are not used for atom-level identification.
3. **CovPDB residue assignment:** Uses first ATOM record's residue as representative. For multi-chain complexes this may be incorrect. Full implementation should parse SDF bond table.
4. **CovPDB ligand_residue:** All set to "1" — actual residue number not extracted from SDF.

## Parser Support Review

| parser_target | v1 Parser File | Required Cols | Transform Completeness | Status |
|---|---|---|---|---|
| covalentin_db | `src/covalent_design/data/sources/covalentin_db.py` | 10 required + 11 optional | 21/21 mapped | READY |
| covpdb | `src/covalent_design/data/sources/covpdb.py` | 12 required + 6 optional | 18/18 mapped | READY WITH CAVEATS |
| covbinder_in_pdb | `src/covalent_design/data/sources/covbinder_in_pdb.py` | 11 required + 1 optional | 12/12 mapped | READY |

## License Gate Review

| Source | License Status | Training Eligible |
|---|---|---|
| CovalentInDB | manual_exempt | YES (ADR 0038) |
| CovPDB | manual_exempt | YES (ADR 0038) |
| CovBinderInPDB | manual_exempt | YES (ADR 0038) |

All use `manual_exempt`. No `unknown` or `blocked`. No `allowed_with_conditions`. Cross-validation rule satisfied (all are `intake_mode = "manual"`).

## V2 Pipeline Integration Status

| Pipeline Step | CovalentInDB | CovBinderInPDB | CovPDB |
|---|---|---|---|
| Task 40 (manifest validation) | ✓ | ✓ | ✓ |
| Task 41 (staging + checksum) | ✓ (on transformed TSV) | ✓ | ✓ |
| Task 42 (conversion to SourceIngestRecord) | ⚠️ FORMAT GAP | ⚠️ FORMAT GAP | ⚠️ FORMAT GAP |
| Task 43 (license gate) | ⚠️ NOT IMPLEMENTED | ⚠️ NOT IMPLEMENTED | ⚠️ NOT IMPLEMENTED |

**Critical Gap:** Task 42 `v2_conversion.py` implements a fixed 8-column TSV parser for `covalentin_db` only. The v1 parsers (`covalentin_db.py`, `covpdb.py`, `covbinder_in_pdb.py`) are a different ingestion path through `ingest.py`. The transformed TSV files are formatted for v1 parsers, not for the Task 42 8-column format. Resolution options:
- (A) Extend `v2_conversion.py` to support v1 parser column schemas
- (B) Create a bridge: transform TSV → v1 `parse_*_records()` → `SourceIngestRecord` → `normalize_linkages()`

## Git Hygiene

- Real raw data (`D:\codex_work\data`) is outside the git repo — no raw data tracked
- Transformed TSV files (`data/v2/staging/`) not committed
- Transformation scripts (`data/v2/staging/transform_*.py`) not committed
- No `.sdf`, `.pdb`, `.mol2`, `.cif`, `.csv`, `.tsv` tracked in git

## Training Readiness

- **Task 49 may NOT start.**
- **Which sources are data-ready:** All three (11,303 total records)
- **Which sources may enter training:** None — pipeline integration gap
- **Why:** Pipeline code needs extension to consume v1-formatted TSV through v2 conversion path; Task 43 license gate code not implemented.

## Blocking Issues

| # | Issue | Severity |
|---|---|---|
| 1 | `v2_conversion.py` only supports 8-column format; needs v1 parser column format support | P0 |
| 2 | Task 43 `v2_license.py` not yet implemented | P0 |
| 3 | CovPDB residue assignment is first-ATOM heuristic | P1 |
| 4 | Windows-side pytest baseline not verified (Linux sandbox network-restricted) | P2 |

## Important Issues (Non-Blocking)

| # | Issue |
|---|---|
| 5 | `attachment_atom = "C1"` default for all three sources |
| 6 | Transformation scripts are one-shot, not integrated into v2 CLI |
| 7 | CovalentInDB `CovInDB_All.csv` (17,775 activity rows) not used; `Covalent_Complex_Records.csv` (PDB-linked) preferred |

## Final Verdict

**NOT READY FOR TASK 49.**

必须先完成:
1. Bridge v1 parser column formats into v2 conversion pipeline
2. Implement Task 43 license gate code
3. Run Windows pytest baseline
4. Full pipeline integration test for all three sources

**已完成:**
- Three-source extraction and format transformation (11,303 records)
- Manifest + license audit file creation per ADR 0038
- Column mapping validated against v1 parser contracts
- Evidence review document generated
