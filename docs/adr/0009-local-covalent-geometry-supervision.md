# Local Covalent Geometry Supervision

The first model will supervise covalent attachment geometry with bond distance, protein-side anchor angle, ligand-side anchor angle, no-edge candidate negatives, and reaction-family-specific geometry masks. Distance-only supervision is rejected because covalent warheads can be spatially close to a reactive residue while having an invalid attack orientation or local chemical environment.
