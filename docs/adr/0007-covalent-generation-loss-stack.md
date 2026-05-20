# Covalent Generation Loss Stack

The first model will train with PMDM position denoising loss, PMDM atom-type denoising loss, covalent edge supervision, covalent geometry supervision, and reaction-family consistency supervision. Affinity, docking, QED, SA, logP, kinetic, toxicity, and selectivity objectives are excluded from the first training loss so the model can first validate structure generation and explicit covalent attachment before adding property guidance or reranking.
