# Covalent Record Storage Format

CovalentComplexRecord outputs will use a JSONL index plus external structure and tensor artifacts. JSONL rows provide reviewable metadata, core labels, quality flags, and paths to artifacts, while large arrays such as atom tables, coordinates, and edge candidates are stored separately as tensor or columnar files. This keeps records inspectable without making training data inefficient to load.
