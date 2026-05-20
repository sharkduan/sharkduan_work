# Dynamic Covalent Attachment Prediction for De Novo Generation

The model will not reserve a fixed ligand-side attachment slot. Instead, it will dynamically predict the ligand-side attachment atom and the typed covalent cross edge from the generated ligand, because the project goal is de novo covalent inhibitor generation rather than scaffold, linker, or fragment elaboration. This is less constrained than an attachment slot and may be harder to train, but it preserves the intended de novo generation behavior and aligns better with recent pocket-based ligand generation patterns.
