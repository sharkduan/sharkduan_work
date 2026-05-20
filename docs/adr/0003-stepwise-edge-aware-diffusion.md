# Stepwise Edge-Aware Diffusion

The first model predicts covalent cross-edge probabilities during each denoising step rather than only after ligand generation is complete. These probabilities are used as soft weights in protein-ligand message passing, and the model performs final hard covalent edge decoding only after denoising. This makes the covalent bond part of the generative trajectory while avoiding early hard edge sampling errors.
