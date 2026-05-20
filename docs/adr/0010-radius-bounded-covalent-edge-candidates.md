# Radius-Bounded Covalent Edge Candidates

The model will train covalent cross-edge prediction on candidates from the specified target atom to ligand atoms within a local radius, initially 4.0 Angstroms. The true ligand attachment atom is the positive edge and nearby non-attachment atoms are no-edge negatives. All-pairs target-to-ligand negatives are rejected because they would create severe class imbalance and reward the model for predicting no covalent edge everywhere.
