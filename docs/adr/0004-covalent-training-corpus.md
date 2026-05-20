# Covalent Training Corpus from Three Public Sources

The first dataset will be built by normalizing CovalentInDB, CovPDB, and CovBinderInPDB into one covalent supervision corpus. CovalentInDB provides inhibitor, warhead, reaction mechanism, binding-site, and activity-oriented annotations; CovPDB provides high-resolution covalent protein-ligand complexes and mechanism labels; CovBinderInPDB provides atom-level covalent residue-binder records from PDB/mmCIF. No single source directly matches the model schema, so an auditable ETL layer is required.
