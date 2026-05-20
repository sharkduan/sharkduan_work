# PocketFlow-Inspired Edge Supervision

The covalent model will borrow PocketFlow's candidate-edge supervision pattern: construct candidate edges, label true edges and no-edge negatives, and use local edge-context features when predicting bond existence and type. It will not adopt PocketFlow's autoregressive generation backbone or conditional normalizing-flow likelihoods, because the project remains a PMDM-compatible ligand diffusion extension.
