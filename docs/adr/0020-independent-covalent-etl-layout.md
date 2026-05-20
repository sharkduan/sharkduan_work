# Independent Covalent ETL Layout

Covalent ETL and rule-building code will live under `src/covalent_design/`, while raw, interim, processed, rule, and report artifacts will live under `data/`. The PMDM directory remains the paper-code backbone until the covalent supervision artifacts are validated. This keeps data engineering, rule calibration, and leakage-aware split generation separate from PMDM training and sampling scripts.
