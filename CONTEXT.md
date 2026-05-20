# Covalent Inhibitor Design

This context defines the domain language for designing a PMDM-inspired model that generates complete covalent inhibitors for protein targets.

## Language

**De Novo Covalent Inhibitor Generation**:
Generation of a complete ligand from scratch that is intended to form a specified covalent bond with a target protein residue.
_Avoid_: Warhead grafting, fragment optimization, linker replacement

**Covalent Attachment Event**:
The intended bond-forming event between a target residue atom and a ligand warhead atom.
_Avoid_: Covalent docking pose

**Explicit Reactive Site Conditioning**:
Conditioning generation on a user-specified target residue atom that is intended to form the covalent bond.
_Avoid_: Reactive site discovery

**Explicit Covalent Bond Generation**:
Generation in which the ligand-side attachment atom and the protein-ligand covalent bond are modeled as part of the generated structure.
_Avoid_: Post-hoc covalent bond assignment

**Protein-Ligand Complex Graph**:
A molecular graph that includes protein atoms, ligand atoms, and typed cross edges between them.
_Avoid_: Ligand-only graph

**Reaction Family**:
A controlled chemistry category that describes the covalent reaction class independent of a specific residue label. It constrains ligand-side warhead environment, covalent bond type, and local chemistry, but is not the primary request or rule-table key.
_Avoid_: Free-form warhead chemistry, reaction family as the primary generation key

**Residue-Reaction Family**:
A canonical primary label combining the target residue class with the covalent reaction class. This is the primary key for generation requests, rule lookup, result reporting, and family-stratified evaluation.
_Avoid_: Warhead motif as the primary generation condition

**Single Covalent Attachment Event**:
A generated ligand has exactly one ligand-side attachment atom and exactly one covalent cross edge to the specified protein-side atom.
_Avoid_: Multi-warhead generation, multiple covalent attachments

**Fixed-Protein Ligand Diffusion**:
Generation in which protein atoms remain fixed conditioning nodes while ligand atoms and the covalent cross edge are generated.
_Avoid_: Full complex diffusion

**Dynamic Covalent Attachment Prediction**:
Generation in which the ligand-side attachment atom and covalent cross edge are predicted from the generated ligand rather than assigned to a fixed slot.
_Avoid_: Attachment slot

**Stepwise Edge-Aware Diffusion**:
Diffusion in which covalent cross-edge probabilities are predicted during each denoising step and can influence protein-ligand message passing.
_Avoid_: Post-denoising covalent edge head

**Soft Stepwise Cross-Edge Message Passing**:
Message passing that uses covalent cross-edge probabilities as soft weights during denoising.
_Avoid_: Early hard cross-edge sampling

**Final Hard Covalent Edge Decoding**:
Selection of exactly one discrete protein-ligand covalent cross edge after denoising is complete.
_Avoid_: Soft-only covalent attachment

**Covalent Training Corpus**:
The curated union of CovalentInDB, CovPDB, and CovBinderInPDB after normalization into the project's supervision schema.
_Avoid_: Single-source covalent dataset

**CovalentComplexRecord**:
The minimal normalized training record containing protein atoms, ligand atoms, ligand bonds, one covalent attachment label, residue-reaction family, warhead type, coordinates, and quality flags.
_Avoid_: Activity record, ADMET record

**First-Pass Reaction Family Vocabulary**:
The initial supported residue-reaction families: CYS Michael addition, CYS nucleophilic substitution, CYS disulfide exchange, SER acylation, SER phosphonylation, and LYS Schiff base.
_Avoid_: Long-tail residue chemistry, multi-residue mechanisms

**PMDM-Compatible Extension**:
A covalent inhibitor model that keeps PMDM's pocket-conditioned ligand diffusion backbone and adds covalent-aware data, conditioning, cross-edge prediction, and losses.
_Avoid_: Ground-up model rewrite

**Covalent Generation Loss Stack**:
The first-pass training objective combining PMDM position loss, PMDM atom loss, covalent edge loss, covalent geometry loss, and reaction-family consistency loss.
_Avoid_: Affinity-first training objective

**PocketFlow-Inspired Edge Supervision**:
Candidate-edge supervision that includes no-edge negative labels and local edge-context features for covalent cross-edge prediction.
_Avoid_: PocketFlow autoregressive backbone, flow likelihood

**Local Covalent Geometry Supervision**:
Supervision over positive covalent-edge bond distance, protein-side anchor angle, ligand-side anchor angle, no-edge candidate contrast or masks, and reaction-family-specific geometry masks.
_Avoid_: Distance-only covalent geometry

**Radius-Bounded Covalent Edge Candidates**:
Candidate protein-ligand covalent edges from the specified target atom to ligand atoms within a local radius, with non-attachment candidates labeled as no-edge negatives.
_Avoid_: All-pairs covalent edge negatives

**Covalent Edge Validity Gate**:
The final decoding gate that accepts one covalent cross edge only if it passes score, reaction-family, valence, and geometry checks.
_Avoid_: Forced top-scoring covalent edge

**Covalent Docking Score**:
An evaluation score from a covalent docking protocol that estimates pose quality and affinity for valid generated covalent complexes. It is defined only for samples with an accepted covalent edge and is reported separately from invalid-sample rates.
_Avoid_: Noncovalent Vina score as the only binding metric, docking invalid samples as if they were valid

**Rule-First Reaction Family Consistency**:
Reaction-family consistency enforced primarily through auditable rule masks for allowed attachment atoms, local warhead environments, covalent bond types, and geometry ranges.
_Avoid_: Classifier-first reaction family consistency

**Reaction Family Rule Table**:
The auditable rule table defining residue, reactive atom, allowed ligand attachment chemistry, covalent bond type, local geometry ranges, valence changes, and notes for each supported residue-reaction family.
_Avoid_: Unstructured reaction-family prompts

**Data-Derived Rules With Manual Curation**:
Reaction-family rules initialized from corpus statistics and then manually corrected for family mapping, reactive atoms, attachment atoms, SMARTS, geometry ranges, valence changes, and abnormal structures.
_Avoid_: Purely manual rules, unreviewed data-derived rules

**Rule Calibration Sheet**:
An auditable ETL artifact summarizing per-family sample counts, representative structures, atom and warhead distributions, geometry summaries, outliers, manual decisions, and notes.
_Avoid_: Hidden rule-calibration scripts

**Leakage-Aware Covalent Splits**:
Dataset splits that include random, protein-cluster, and scaffold splits, with protein-cluster and scaffold splits used as primary generalization evaluations.
_Avoid_: Random split as the only reported split

**Covalent Scaffold Split Unit**:
The ligand grouping unit for scaffold generalization, defined primarily on the de-warheaded ligand scaffold while retaining residue-reaction-family stratification. Whole-ligand scaffold and warhead-scaffold summaries may be reported as diagnostics, but they are not the primary scaffold split key.
_Avoid_: Warhead-only scaffold split, undocumented scaffold key

**Reactive-Site Generation Request**:
The inference request containing protein structure, target chain, target residue, target atom, residue-reaction family, and sample count, with optional pocket and sampling controls.
_Avoid_: Reference ligand requirement, required warhead motif

**Reactive-Site Request Conflict**:
A request validation error where the specified residue, atom, and residue-reaction family are mutually inconsistent or unsupported. This is attributed to the request before sampling, not to model generation or result validity.
_Avoid_: Counting invalid user input as invalid generated samples

**CovalentGenerationResult**:
The per-sample inference output containing generated ligand state, generated covalent complex when exported, predicted attachment atom, predicted covalent edge, residue-reaction family, warhead type evidence, edge score, geometry metrics, lifecycle statuses, failure reasons, molecular quality metrics, and covalent docking score when evaluable.
_Avoid_: Ligand-only SDF output

**Invalid CovalentGenerationResult**:
A generated sample record that failed validity checks but still preserves enough request, ligand, edge, geometry, and failure metadata to support denominator accounting and error analysis.
_Avoid_: Dropping invalid samples, replacing invalid samples with empty files

**Generation Result Lifecycle State**:
The separated status fields for generation validity, complex export, docking eligibility, and docking run completion.
_Avoid_: A single valid/invalid flag that mixes generation, export, and docking failures

**Denominator Conservation Accounting**:
Evaluation reporting in which requested, accepted, attempted, valid, invalid, exported, docking-evaluable, docked, and failed counts satisfy explicit conservation equations.
_Avoid_: Unreconciled counts, overlapping denominator buckets

**Protein Chemical State**:
The target-side formal charge, protonation state, hydrogen state, preparation policy, and provenance required to evaluate covalent valence and protonation gates with fixed protein coordinates.
_Avoid_: Treating coordinates alone as sufficient protein chemistry

**Mask/Gate Denominator Accounting**:
Training and evaluation reporting that separates candidate, eligible, masked, forced-positive, loss-denominator, message-passing, and gate-evaluated counts.
_Avoid_: Hidden rule masks, unreported denominator changes

**Matched Warhead Type**:
A warhead type assigned by rule or SMARTS matching against the generated ligand structure after sampling.
_Avoid_: Treating matched warhead type as a model prediction

**Predicted Warhead Type**:
An optional model-emitted warhead label used as auxiliary evidence or diagnostics. It does not override residue-reaction-family rules or matched warhead checks.
_Avoid_: Using predicted warhead type as the authority for validity

**Structure Atom Identity**:
The stable atom locator for protein-side and ligand-side covalent atoms, including structure model, chain or asym identifier, residue identifier, insertion or alternate-location qualifiers when present, residue name, atom name, and ligand atom index or name.
_Avoid_: Coordinate-only atom identity, atom serial number as the only identity

**mmCIF-First Covalent Complex Output**:
Output format strategy that stores generated covalent complexes primarily as mmCIF with structured covalent linkage records, with optional PDB LINK/CONECT export for compatibility.
_Avoid_: PDB-only covalent complex output

**Covalent Docking Protocol**:
The minimum evaluation protocol that prepares a covalent protein-ligand complex with an explicit covalent linkage or constraint, records receptor and ligand preparation choices, preserves a protocol manifest with input/output checksums and configuration, and returns a score only for covalently valid docking-successful samples. QuickVina2 may remain a noncovalent baseline or compatibility metric, but it is not by itself the covalent docking protocol.
_Avoid_: Undocumented docking setup, QuickVina2 score reported as covalent docking score

**ETL-First Implementation Plan**:
The implementation sequence that builds and validates covalent records, rules, calibration sheets, candidates, and splits before modifying the PMDM model.
_Avoid_: Model-first covalent implementation

**Independent Covalent ETL Layout**:
Project layout that stores covalent ETL and rules code under `src/covalent_design/` and data artifacts under `data/`, separate from the PMDM paper-code directory.
_Avoid_: ETL code embedded directly in PMDM scripts

**Formal Covalent ETL ADR Set**:
ADR 0021 through ADR 0029 are part of the formal project context for data-source priority, normalized record scope, storage format, smoke tests, raw-data staging, first training core coverage, quality filters, and ETL quality reporting.
_Avoid_: Treating ADR 0021-0029 as informal notes

## Relationships

- **De Novo Covalent Inhibitor Generation** produces one complete ligand for one intended **Covalent Attachment Event**.
- **Explicit Reactive Site Conditioning** provides the protein-side atom for a **Covalent Attachment Event**.
- **Explicit Covalent Bond Generation** realizes a **Covalent Attachment Event** by generating the ligand-side attachment atom and its bond to the specified protein-side atom.
- A **Protein-Ligand Complex Graph** represents the covalent bond in a **Covalent Attachment Event** as a typed cross edge.
- A **Reaction Family** describes the chemistry constraints associated with a **Residue-Reaction Family**.
- A **Residue-Reaction Family** is the primary condition used to select the allowed covalent chemistry.
- A **Residue-Reaction Family** is the primary key for **Reactive-Site Generation Request**, **Reaction Family Rule Table**, **CovalentGenerationResult**, and family-stratified evaluation.
- A **Reaction Family** may be derived from a **Residue-Reaction Family**, but it must not replace it as the primary key where residue identity affects validity.
- **Single Covalent Attachment Event** limits each generated ligand to one intended covalent connection.
- **Fixed-Protein Ligand Diffusion** uses the **Protein-Ligand Complex Graph** without diffusing protein atom coordinates.
- **Dynamic Covalent Attachment Prediction** identifies the ligand-side atom and cross edge for the **Single Covalent Attachment Event**.
- **Stepwise Edge-Aware Diffusion** implements **Dynamic Covalent Attachment Prediction** throughout ligand generation.
- **Soft Stepwise Cross-Edge Message Passing** carries **Stepwise Edge-Aware Diffusion** signals during denoising.
- **Final Hard Covalent Edge Decoding** turns soft cross-edge probabilities into the **Single Covalent Attachment Event**.
- The **Covalent Training Corpus** provides supervised examples for **Residue-Reaction Family**, **Single Covalent Attachment Event**, and **Protein-Ligand Complex Graph** construction.
- The **Covalent Training Corpus** is composed of **CovalentComplexRecord** entries.
- The **First-Pass Reaction Family Vocabulary** constrains the supported values of **Residue-Reaction Family**.
- **PMDM-Compatible Extension** implements **De Novo Covalent Inhibitor Generation** by extending PMDM's ligand diffusion backbone.
- **Covalent Generation Loss Stack** trains **PMDM-Compatible Extension** to generate ligand structure, atom types, covalent edges, and reaction-family-consistent attachment geometry.
- **PocketFlow-Inspired Edge Supervision** contributes candidate cross-edge labels and negative examples to the **Covalent Generation Loss Stack**.
- **Local Covalent Geometry Supervision** defines the geometry component of the **Covalent Generation Loss Stack**.
- **Radius-Bounded Covalent Edge Candidates** provide the positive and negative examples for **PocketFlow-Inspired Edge Supervision**.
- **Covalent Edge Validity Gate** performs **Final Hard Covalent Edge Decoding**.
- **Covalent Docking Score** is a primary evaluation metric for generated complexes that pass the **Covalent Edge Validity Gate**.
- **Rule-First Reaction Family Consistency** defines the reaction-family component of the **Covalent Generation Loss Stack** and the **Covalent Edge Validity Gate**.
- **Reaction Family Rule Table** provides the rules used by **Rule-First Reaction Family Consistency**.
- **Data-Derived Rules With Manual Curation** is the source and maintenance process for the **Reaction Family Rule Table**.
- **Rule Calibration Sheet** records the evidence and manual decisions behind **Data-Derived Rules With Manual Curation**.
- **Leakage-Aware Covalent Splits** evaluate whether **De Novo Covalent Inhibitor Generation** generalizes across targets and scaffolds.
- **Covalent Scaffold Split Unit** defines the scaffold key used by **Leakage-Aware Covalent Splits** for chemical generalization.
- **Reactive-Site Generation Request** is the user-facing input for **De Novo Covalent Inhibitor Generation**.
- **Reactive-Site Request Conflict** is rejected before producing **CovalentGenerationResult** samples.
- **CovalentGenerationResult** is the user-facing output of **De Novo Covalent Inhibitor Generation**.
- **Invalid CovalentGenerationResult** is included in result denominators but excluded from **Covalent Docking Score** aggregation.
- **Generation Result Lifecycle State** separates generation validity from complex export and docking evaluation.
- **Denominator Conservation Accounting** defines how **CovalentGenerationResult** counts are summarized.
- **Protein Chemical State** is required before valence and protonation gates can evaluate a **Covalent Attachment Event**.
- **Mask/Gate Denominator Accounting** makes **Rule-First Reaction Family Consistency** auditable during training and evaluation.
- **Matched Warhead Type** is generated by rule matching and can validate or explain a **CovalentGenerationResult**.
- **Predicted Warhead Type** is diagnostic model output and cannot override **Rule-First Reaction Family Consistency**.
- **Structure Atom Identity** anchors **Reactive-Site Generation Request**, **CovalentGenerationResult**, and **mmCIF-First Covalent Complex Output** to the same covalent atoms.
- **mmCIF-First Covalent Complex Output** defines how covalent complexes are represented inside **CovalentGenerationResult**.
- **Covalent Docking Protocol** produces **Covalent Docking Score** for valid covalent complexes.
- **ETL-First Implementation Plan** produces the data artifacts required by **PMDM-Compatible Extension**.
- **Independent Covalent ETL Layout** organizes the implementation of the **ETL-First Implementation Plan**.
- **Formal Covalent ETL ADR Set** makes ADR 0021-0029 part of the project vocabulary governed by this context.

## Example dialogue

> **Dev:** "Are we only adding a warhead to an existing scaffold?"
> **Domain expert:** "No. This is **De Novo Covalent Inhibitor Generation**: the full ligand is generated from scratch around the intended **Covalent Attachment Event**."
> **Dev:** "Should the model choose which residue to attack?"
> **Domain expert:** "No. We use **Explicit Reactive Site Conditioning**: the user provides the reactive residue atom."
> **Dev:** "Can we generate a ligand first and decide later whether it is covalent?"
> **Domain expert:** "No. We use **Explicit Covalent Bond Generation**: the protein-ligand covalent bond is part of the generated structure."
> **Dev:** "Should the covalent bond live outside the graph as metadata?"
> **Domain expert:** "No. In a **Protein-Ligand Complex Graph**, the covalent bond is represented as a typed cross edge."
> **Dev:** "Can the model invent any warhead as long as it places an atom near the reactive residue?"
> **Domain expert:** "No. Generation is conditioned on a **Residue-Reaction Family** with associated **Reaction Family** rules, so the warhead chemistry is constrained."
> **Dev:** "Should the user specify acrylamide directly?"
> **Domain expert:** "No. The primary condition is a **Residue-Reaction Family** such as CYS Michael addition; warhead motifs can remain optional sublabels."
> **Dev:** "Can one generated ligand attach to two residues?"
> **Domain expert:** "No. The first version supports a **Single Covalent Attachment Event** per generated ligand."
> **Dev:** "Does a complex graph mean the model moves protein atoms?"
> **Domain expert:** "No. We use **Fixed-Protein Ligand Diffusion**: protein atoms are fixed conditioning nodes."
> **Dev:** "Do we reserve a special atom slot for the covalent attachment?"
> **Domain expert:** "No. We use **Dynamic Covalent Attachment Prediction** so the attachment atom emerges from de novo ligand generation."
> **Dev:** "Is the covalent edge predicted only after ligand generation?"
> **Domain expert:** "No. **Stepwise Edge-Aware Diffusion** predicts covalent cross-edge probabilities during denoising."
> **Dev:** "Do we sample a hard covalent edge at every denoising step?"
> **Domain expert:** "No. We use **Soft Stepwise Cross-Edge Message Passing** and defer discrete selection to **Final Hard Covalent Edge Decoding**."
> **Dev:** "Can one public database provide all supervision directly?"
> **Domain expert:** "No. The **Covalent Training Corpus** combines CovalentInDB, CovPDB, and CovBinderInPDB after normalization."
> **Dev:** "Should activity and ADMET fields be part of the core training record?"
> **Domain expert:** "No. A **CovalentComplexRecord** contains only the fields needed for structure and covalent attachment supervision."
> **Dev:** "Should the first model cover every warhead type in CovalentInDB?"
> **Domain expert:** "No. The **First-Pass Reaction Family Vocabulary** covers six high-value reaction families before long-tail chemistry."
> **Dev:** "Should we rewrite PMDM from scratch?"
> **Domain expert:** "No. This is a **PMDM-Compatible Extension** that keeps the ligand diffusion backbone and adds covalent-aware modules."
> **Dev:** "Should affinity, QED, or toxicity be part of the first training loss?"
> **Domain expert:** "No. The **Covalent Generation Loss Stack** focuses on structure and covalent attachment supervision first."
> **Dev:** "Should PocketFlow replace PMDM as the generation backbone?"
> **Domain expert:** "No. We only borrow **PocketFlow-Inspired Edge Supervision** for covalent cross-edge labels and local edge context."
> **Dev:** "Is covalent geometry just a distance constraint?"
> **Domain expert:** "No. **Local Covalent Geometry Supervision** includes positive-edge bond distance, two anchor angles, no-edge contrast or masks, and reaction-family-specific masks."
> **Dev:** "Should every ligand atom be a negative covalent edge candidate?"
> **Domain expert:** "No. **Radius-Bounded Covalent Edge Candidates** limit negatives to atoms near the specified target atom."
> **Dev:** "Should the highest-scoring cross edge always be forced into the output?"
> **Domain expert:** "No. The **Covalent Edge Validity Gate** rejects samples with no legal covalent edge."
> **Dev:** "Can noncovalent Vina be the only binding metric?"
> **Domain expert:** "No. **Covalent Docking Score** is one of the primary covalent evaluation metrics."
> **Dev:** "Should reaction-family consistency be learned entirely by a classifier?"
> **Domain expert:** "No. **Rule-First Reaction Family Consistency** uses explicit chemistry rules first."
> **Dev:** "Can reaction-family rules live only in prose?"
> **Domain expert:** "No. A **Reaction Family Rule Table** stores them as auditable structured rules."
> **Dev:** "Can we trust geometry ranges directly from database statistics?"
> **Domain expert:** "No. We use **Data-Derived Rules With Manual Curation** to correct labels, geometry, SMARTS, valence, and abnormal structures."
> **Dev:** "Can rule calibration stay hidden in ETL scripts?"
> **Domain expert:** "No. A **Rule Calibration Sheet** is required so reaction-family rules are reviewable and reproducible."
> **Dev:** "Is a random train/test split enough?"
> **Domain expert:** "No. **Leakage-Aware Covalent Splits** require protein-cluster and scaffold splits for primary evaluation."
> **Dev:** "Does inference require a reference ligand or scaffold?"
> **Domain expert:** "No. A **Reactive-Site Generation Request** specifies the protein reactive site and residue-reaction family, not a reference ligand."
> **Dev:** "Is saving only the generated ligand SDF enough?"
> **Domain expert:** "No. A **CovalentGenerationResult** also records the covalent complex, predicted cross edge, validity gate status, failure reason, and covalent docking score."
> **Dev:** "Should generated covalent complexes be PDB-only?"
> **Domain expert:** "No. **mmCIF-First Covalent Complex Output** preserves structured atom-level covalent linkage records."
> **Dev:** "Should we add model losses before building covalent labels?"
> **Domain expert:** "No. The **ETL-First Implementation Plan** validates covalent records, rules, candidates, and splits first."
> **Dev:** "Should ETL scripts be placed directly inside PMDM sampling and training scripts?"
> **Domain expert:** "No. **Independent Covalent ETL Layout** keeps covalent data engineering separate from PMDM paper code."

## Flagged ambiguities

- "Design covalent inhibitors" was resolved as **De Novo Covalent Inhibitor Generation**, not warhead grafting, fragment optimization, or linker replacement.
- "Reactive residue" was resolved as a user-provided condition, not a prediction target.
- "Generate covalent inhibitors" was resolved as **Explicit Covalent Bond Generation**, not post-hoc covalent bond assignment.
- "Covalent graph representation" was resolved as a **Protein-Ligand Complex Graph**, not a ligand-only graph with covalent metadata.
- "Warhead chemistry" was resolved as **Reaction Family** constrained, not free-form warhead generation.
- "Reaction family granularity" was resolved as **Residue-Reaction Family** first, with warhead motif as an optional sublabel.
- "Number of covalent events" was resolved as **Single Covalent Attachment Event** per generated ligand.
- "Protein-ligand complex graph" was resolved as compatible with **Fixed-Protein Ligand Diffusion**, not full complex coordinate diffusion.
- "Ligand-side attachment selection" was resolved as **Dynamic Covalent Attachment Prediction**, not a fixed attachment slot.
- "Covalent edge timing" was resolved as **Stepwise Edge-Aware Diffusion**, not a post-denoising covalent edge head.
- "Cross-edge sampling" was resolved as **Soft Stepwise Cross-Edge Message Passing** with **Final Hard Covalent Edge Decoding**, not early hard edge sampling.
- "Training data source" was resolved as a **Covalent Training Corpus** built from CovalentInDB, CovPDB, and CovBinderInPDB.
- "Training sample schema" was resolved as **CovalentComplexRecord** with minimal structure and covalent supervision fields.
- "Initial reaction family coverage" was resolved as the **First-Pass Reaction Family Vocabulary**, excluding long-tail, multi-residue, cofactor, and metal coordination cases.
- "Model implementation strategy" was resolved as a **PMDM-Compatible Extension**, not a ground-up rewrite.
- "Training objective" was resolved as the **Covalent Generation Loss Stack**, excluding affinity, docking, ADMET, toxicity, and selectivity losses from the first version.
- "PocketFlow reuse" was resolved as **PocketFlow-Inspired Edge Supervision**, not adopting PocketFlow's autoregressive backbone or flow likelihood.
- "Covalent geometry supervision" was resolved as **Local Covalent Geometry Supervision**, not distance-only supervision.
- "Covalent edge negative sampling" was resolved as **Radius-Bounded Covalent Edge Candidates**, not all-pairs negative supervision.
- "Final hard covalent edge decoding" was resolved as a **Covalent Edge Validity Gate**, not forced top-scoring edge selection.
- "Covalent evaluation" was updated to include **Covalent Docking Score** as a primary metric.
- "Reaction-family consistency" was resolved as **Rule-First Reaction Family Consistency**, not classifier-first consistency.
- "Reaction-family rule schema" was resolved as a structured **Reaction Family Rule Table**.
- "Reaction-family rule source" was resolved as **Data-Derived Rules With Manual Curation**, including R0 manual checks for family mapping, target atom, ligand attachment atom, allowed SMARTS, and valence delta.
- "Rule calibration artifact" was resolved as a required **Rule Calibration Sheet** produced by the first ETL.
- "Dataset splitting" was resolved as **Leakage-Aware Covalent Splits**, not random-only evaluation.
- "Inference input" was resolved as a **Reactive-Site Generation Request**, not a reference-ligand or warhead-template request.
- "Inference output" was resolved as **CovalentGenerationResult**, not ligand-only SDF output.
- "Covalent complex output format" was resolved as **mmCIF-First Covalent Complex Output**, with optional PDB LINK/CONECT export.
- "Implementation order" was resolved as **ETL-First Implementation Plan**, not model-first implementation.
- "First-phase project layout" was resolved as **Independent Covalent ETL Layout**, using `src/covalent_design/` and `data/`.
