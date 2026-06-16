# V2 Data Automation Spec

Date: 2026-06-16
Status: hardened planning spec

## Input Data Sources

V2-beta mainline includes only:

- CovalentInDB
- CovPDB
- CovBinderInPDB

Other datasets are out of mainline scope unless a later planning document accepts them.

## Raw Data Layout

Proposed layout:

```text
data/v2/raw/<source_name>/
  source_manifest.json
  license_audit.json
  downloads/
  manual/
  checksums.json
```

No real data file is added by this documentation task.

## Acquisition Modes

### Automatic Download

Allowed only after license and access verification. The downloader must record source URL, retrieval time, checksum, file size, parser target, and license status.

### Manual Staging

Used when download is unavailable or unreliable. The manifest must record manual path, checksum, expected file pattern, and why automatic download was not used.

## Conversion Pipeline

The v2 conversion path should be staged:

1. raw source manifest validation,
2. source-specific decode,
3. schema normalization into v1-compatible records,
4. artifact reference construction,
5. rule and family validation,
6. quality/visual/split gates,
7. family readiness report.

## Schema Normalization

All source-specific records must normalize to existing v1 concepts:

- `CovalentComplexRecord`
- `residue_reaction_family`
- `target_atom`
- ligand attachment atom
- warhead annotation
- covalent edge label
- artifact refs
- quality and visual status

## Structure Cleaning

Cleaning must be explicit and reportable:

- protein atom table normalization,
- ligand atom table normalization,
- ligand bond normalization,
- coordinate frame provenance,
- chemical-state availability,
- failure reason for dropped structures.

## Ligand / Protein Processing

- Protein processing must preserve `Structure Atom Identity`.
- Ligand processing must preserve stable `ligand_atom_index`.
- Multi-linkage records remain excluded from first-core training unless policy changes.
- Chemical-state unavailable records must be reported, not silently repaired.

## Artifact Manifests

Every generated or staged artifact must include:

- role,
- path or URI,
- checksum,
- schema version,
- contract version,
- source provenance,
- license audit reference.

## License Checks

Allowed license statuses:

- `allowed`
- `allowed_with_conditions`
- `unknown`
- `blocked`

Only `allowed` and compatible `allowed_with_conditions` records may enter training.

## Quality Gates

V2 data automation must preserve v1 gates:

- rejected/conflict separation,
- Q0/Q1/Q2 quality tiers,
- visual check blocking,
- leakage-aware split assignments,
- family readiness.

## Verification Commands

Planned commands:

```bash
python -m covalent_design.data.cli.v2_validate_source_manifest --manifest data/v2/raw/<source>/source_manifest.json
python -m covalent_design.data.cli.v2_stage_source --source <source> --path <raw-path> --out-root data/v2/raw
python -m covalent_design.data.cli.v2_convert_source --manifest data/v2/raw/<source>/source_manifest.json --out-root data/v2/processed
python -m covalent_design.data.cli.v2_run_real_etl --raw-root data/v2/raw --out-root data/v2/processed
```

Exact command names are finalized by the implementing tasks, but public CLIs should be package module entrypoints. Standalone scripts may wrap these commands only as developer helpers.
