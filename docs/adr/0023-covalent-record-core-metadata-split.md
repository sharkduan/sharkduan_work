# Covalent Record Core and Metadata Split

CovalentComplexRecord data will be split into core training fields and metadata. Core fields contain structure, atoms, bonds, covalent attachment labels, residue-reaction family, warhead type, coordinates, and quality flags. Activity, assay, clinical status, kinetic, and source-link information may be preserved as metadata but will not enter the first training loss.
