# V2 Real Local Data ETL Evidence Review

**Date:** 2026-06-19
**Status:** SUPERSEDED/CORRECTED by `docs/reviews/v2-real-data-import-repair-2026-06-19.md`

This report is retained as historical evidence only. It used repo-derived
staging TSVs and reported CovPDB partial conversion as training eligible.
The authoritative post-repair status is the formal raw-root command:

```powershell
python -m covalent_design.data.cli.v2_run_real_etl --raw-root D:\codex_work\data --staging-root data/v2/staging --out-root data/v2/processed --report-root data/v2/reports --source all
```

The corrected report writes `data/v2/processed/v2_real_etl_manifest.json`
and uses `data/v2/reports/window_c_real_etl_report.json` as the current
machine-readable evidence.

## Sources

| Source | intake_mode | parser_target | Raw Input | V1 TSV Records | SourceIngestRecords | Parse Errors | license | training_eligible |
|--------|-------------|---------------|-----------|----------------|---------------------|-------------|---------|-------------------|
| CovalentInDB | manual | covalentin_db | Covalent_Complex_Records.csv (3,660 rows) | 3,598 | 3,598 | 0 | manual_exempt | yes |
| CovBinderInPDB | manual | covbinder_in_pdb | CovBinderInPDB_2022Q4_AllRecords.csv (7,376 rows) | 7,375 | 7,375 | 0 | manual_exempt | yes |
| CovPDB | manual | covpdb | 2,261 PDB directories (4,535 files) | 10,578 LINK records | 10,515 | 63 | manual_exempt | yes |

**Total: 21,488 SourceIngestRecords across three sources.**

## Pipeline Trace

| Gate | Result |
|------|--------|
| Task 40 (manifest validation) | ALL PASS (3/3) |
| Task 41 (staging) | ALL checksum_verified (3/3) |
| Task 42 (conversion) | 2/3 OK, CovPDB: 63 rows missing resolution or ligand_chain |
| Task 43 (license gate) | ALL training_eligible (manual_exempt per ADR 0038) |

## Format Gaps Resolved

| Gap | Resolution |
|-----|------------|
| CovalentInDB 26-col CSV → v1 TSV | `transform_covalentin_db.py`: ID→compound_id, Warhead→warhead_class, Reaction→reaction_family, atom_name inferred from Resi_name |
| CovBinderInPDB 19-col CSV → v1 TSV | `transform_covbinder_in_pdb.py`: full_residue_name→3-letter, warhead→family+bond_type, 108 unknown warhead types (default UNKNOWN) |
| CovPDB PDB+SDF → v1 TSV | `transform_covpdb.py`: PDB LINK record parser, standard amino acid detection, bond type from distance |

## Parse Error Details (CovPDB)

- 34 rows: missing `resolution` (some PDB files lack REMARK 2 RESOLUTION)
- 29 rows: missing `ligand_chain` (unparseable LINK records)
- All 10,515 valid records were still converted successfully

## Known Limitations

- CovPDB LINK record parsing uses standard amino acid detection — non-standard residues may be missed
- Reaction family inference from residue+atom is heuristic — manual review recommended
- bond_type defaults to "single" for distances < 2.5Å — disulfide bonds not distinguished
- attachment_atom defaults to "C1" for CovalentInDB/CovBinderInPDB — actual attachment atom may differ
- 108 unknown CovBinderInPDB warhead types → UNKNOWN reaction family suffix

## Artifacts Produced

```
data/v2/staging/
  transform_covalentin_db.py          # CovalentInDB transform script
  covalentin_db_v1.tsv                 # 3,599 rows, v1 columns (17 cols)
  transform_covbinder_in_pdb.py        # CovBinderInPDB transform script
  covbinder_in_pdb_v1.tsv              # 7,376 rows, v1 columns (16 cols)
  transform_covpdb.py                  # CovPDB transform script
  covpdb_v1.tsv                        # 10,579 rows, v1 columns (15 cols)

data/v2/manifests/
  covalentin_db_v2_manifest.json       # V2 manifest (SHA-256 verified)
  covbinder_in_pdb_v2_manifest.json
  covpdb_v2_manifest.json
  license_audit.json                   # manual_exempt

data/v2/reports/
  v2-real-data-pipeline-dry-run-2026-06-19.json

src/covalent_design/data/v2_conversion.py  # Extended: TSV parser bridge
```
