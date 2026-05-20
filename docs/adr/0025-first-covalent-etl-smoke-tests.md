# First Covalent ETL Smoke Tests

The first ETL implementation must pass a small but strict smoke test suite before scaling. It should parse 10 CovBinderInPDB records, map target and ligand attachment atoms, filter or mark multi-covalent-link samples, construct one positive cross edge plus radius-bounded no-edge negatives, compute local covalent geometry, export visual checks, and validate `records.jsonl` rows against the CovalentComplexRecord schema.
