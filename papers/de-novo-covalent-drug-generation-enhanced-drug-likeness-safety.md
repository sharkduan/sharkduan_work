---
title: "De novo covalent drug generation with enhanced drug-likeness and safety"
authors: "Wenbo Zhang; Tianxiao Liu; Xiaoying Dong; Saisai Sun; Xiaojun Yao; Pengyong Li; Lin Gao"
journal: "Communications Biology"
date: "2026-02-17"
doi: "10.1038/s42003-026-09725-5"
zotero_parent_key: "7YMCLLHC"
zotero_attachment_key: "JL9IHCMF"
source_pdf: "papers/de-novo-covalent-drug-generation-enhanced-drug-likeness-safety.pdf"
---

**https://doi.org/10.1038/s42003-026-09725-5** 

## **Communications Biology** 

## **Article in Press** 

## **De novo covalent drug generation with enhanced drug-likeness and safety** 

**Received: 26 June 2025 Accepted: 6 February 2026** 

## **Wenbo Zhang, Tianxiao Liu, Xiaoying Dong, Saisai Sun, Xiaojun Yao, Pengyong Li & Lin Gao** 

apply. Review reports will publish with the final article. 

We are providing an unedited version of this manuscript to give early access to its findings. Before final publication, the manuscript will undergo further editing. Please note there may be errors present which affect the content, and all legal disclaimers apply. 

**Cite this article as: Zhang, W., Liu, T., Dong, X. et al. De novo covalent drug generation with enhanced druglikeness and safety. Commun Biol (2026). https://doi.org/10.1038/ s42003-026-09725-5** 

If this paper is publishing under a Transparent Peer Review model then Peer Review reports will publish with the final article. 

> © The Author(s) 2026. **Open Access** This article is licensed under a Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License, which permits any non-commercial use, sharing, distribution and reproduction in any medium or format, as long as you give appropriate credit to the original author(s) and the source, provide a link to the Creative Commons licence, and indicate if you modified the licensed material. You do not have permission under this licence to share adapted material derived from this article or parts of it. The images or other third party material in this article are included in the article's Creative Commons licence, unless indicated otherwise in a credit line to the material. If material is not included in the article's Creative Commons licence and your intended use is not permitted by statutory regulation or exceeds the permitted use, you will need to obtain permission directly from the copyright holder. To view a copy of this licence, visit http://creativecommons.org/licenses/by-nc-nd/4.0/. 

# _De novo_ Covalent Drug Generation with Enhanced Drug-likeness and Safety 

Wenbo Zhang[1] _**[†]**_ , Tianxiao Liu[1] _**[†]**_ , Xiaoying Dong[1] , Saisai Sun[1] , Xiaojun Yao[2] , Pengyong Li[1*] , Lin Gao[1*] 

> 1*School of Computer Science and Technology, Xidian University, Xi'an, 710071, Shaanxi, China. 

- Sciences, Macao Polytechnic University, 999078, Macao, 

- *Corresponding author(s). E-mail(s): lipengyong@xidian.edu.cn; lgao@mail.xidian.edu.cn; 

- _**†**_ These authors contributed equally. **Abstract** 

- drugs have long played an essential role in therapeutics, yet 

- design approaches remain largely confined to virtual screening of Despite recent advances in deep generative models for drug specifically tailored to _de novo_ covalent drug generation are still 

- Here we introduce `CovaGEN` , a conditional latent diffusion framework for 

- novo design of covalent inhibitors with enhanced drug-likeness and generates ligands from a drug-like latent space while conditioning 

- sequences and employing a classifier to guide the formation of 

- covalent warheads. A reinforcement learning strategy further optimizes the safety of generated molecules. Experimental results demonstrate that generates covalent drugs with the desired covalent warheads, 

Covalent drugs have long played an essential role in therapeutics, yet computational design approaches remain largely confined to virtual screening of existing libraries. Despite recent advances in deep generative models for drug discovery, methods specifically tailored to _de novo_ covalent drug generation are still lacking. Here we introduce `CovaGEN` , a conditional latent diffusion framework for the de novo design of covalent inhibitors with enhanced drug-likeness and safety. `CovaGEN` generates ligands from a drug-like latent space while conditioning on target sequences and employing a classifier to guide the formation of desirable covalent warheads. A reinforcement learning strategy further optimizes the safety profiles of generated molecules. Experimental results demonstrate that `CovaGEN` effectively generates covalent drugs with the desired covalent warheads, exhibiting strong target protein affinity, favorable drug-likeness, and low toxicity. When applied to EGFR T790M and Mpro, the generated compounds exhibit higher probabilities of covalent binding. Overall, `CovaGEN` offers a pioneering approach for the _de novo_ design of covalent inhibitors, advancing the discovery of covalent drugs with improved properties. 

**Keywords:** Covalent drug design, diffusion model, reinforcement learning 

> 2Centre for Artificial Intelligence Driven Drug Discovery, Faculty of Applied Sciences, Macao Polytechnic University, 999078, Macao, China. 

## **1 Introduction** 

Covalent drugs form irreversible bonds with electrophilic amino acids on protein targets, leading to prolonged inhibition and enhanced therapeutic efficacy. Since the discovery of aspirin, various covalent drugs have been identified, showing promising results in the treatment of many diseases such as cancer. Traditionally, wet-lab covalent drug discovery typically follows two main strategies: the "ligand-first" approach, which develops a reversible ligand before introducing a covalent warhead, and the "electrophile-first" approach, which designs reactive electrophiles to form covalent bonds with specific residues, followed by optimization of the molecule for binding and selectivity[1] . While wet-lab-based approaches have been foundational in developing therapeutics, it also comes with several challenges and weaknesses such as time and cost-intensive. Then computational methods have become an integral part of covalent drug discovery to enhance the efficiency, safety and precision. 

Existing computational methods for covalent drug discovery primarily rely on virtual screening, particularly docking-based approaches[2][–][4] . However, these methods are limited by their dependence on existing compound libraries and the effectiveness of the screening strategies employed. As a result, they can be time-consuming, costly, and may fail to identify covalent drugs for specific targets. Recently, _de novo_ drug design has gained attention as an alternative, offering the ability to generate novel compounds from scratch and explore vast, uncharted chemical spaces more efficiently[5] . Various deep learning architectures, including recurrent neural networks (RNNs)[6][,][7] , variational autoencoders (VAEs)[[8][,][9]][[,][9]][[9]] , generative adversarial networks (GANs)[10][,][11] , and diffusion models[[12][,][13]][[,][13]][[13]] , have been employed in drug generation. While these methods excel at generating molecules with high binding affinity, they primarily focus on non-covalent drug molecules due to the scarcity of data. 

strategies employed. As a result, they can be to identify covalent drugs for specific targets. gained attention as an alternative, offering the learning architectures, including recurrent neural[[8][,][9]][[,][9]][[9]] models[[12][,][13]][[,][13]][[13]] , have been employed in drug generation. generating molecules with high binding affinity, they drug molecules due to the scarcity of data. current drug design approaches often overemphasize other crucial properties, which can result and limited therapeutic potential. In addition, property affecting clinical translation, and its for covalent drugs. The irreversible nature of covalent[[14]] particularly in the context of covalent drug toxicity is crucial for clinical success. study, we propose `CovaGEN` , a _de novo_ covalent drug reinforced latent model. To the 

Moreover, current drug design approaches often overemphasize the docking affinity, neglecting other crucial properties, which can result in impractical molecules with poor drug-likeness and limited therapeutic potential. In addition, toxicity is another indispensable property affecting clinical translation, and its impact is especially more significant for covalent drugs. The irreversible nature of covalent binding can exacerbate off-target effects, leading to increased toxicity[[14]] . Consequently, there is a pressing need for generative models that can optimize binding affinity, drug-likeness, and safety simultaneously, particularly in the context of covalent drug design, where balancing efficacy and toxicity is crucial for clinical success. 

In this study, we propose `CovaGEN` , a _de novo_ covalent drug generation method based on a reinforced latent diffusion model. To ensure the validity and drug-likeness of the generated molecules, we first construct a latent space of drug-like molecules for the later molecular generation. Specifically, we curate molecules from the large-scale Zinc database that are readily purchasable and meet drug-likeness criteria, such as Lipinski's Rule of Five. A variational autoencoder (VAE) model is then trained on these drug-like molecules to learn a latent representation of the drug-likeness space. Building upon this drug-like latent space, a conditional diffusion model was then trained to generate ligand molecules capable of binding to a given protein target. To guide the reverse process (i.e., the covalent drug generation process), we employ classifier-based sampling, ensuring that the generated molecules contain the desired covalent warheads 

for effective covalent inhibition. Furthermore, we integrate a reinforcement learning strategy, where toxicity minimization serves as the reward function, allowing the conditional diffusion model to be fine-tuned for lower toxicity. Through this approach, `CovaGEN` not only generates drug-like molecules with covalent binding potential, but also optimizes them for improved safety profiles, addressing both efficacy and toxicity challenges in covalent drug design. 

We demonstrate that `CovaGEN` is capable of generating a diverse array of valid molecules with desirable binding affinity and other drug properties, such as druglikeness and synthetic accessibility that outperforms baseline methods. Utilizing classifier-guidance, `CovaGEN` can not only generate molecules with desired covalent warheads, but maintains drug properties at a considerable level. When further finetuned with reinforcement learning approach, `CovaGEN` produces molecules with lower acute toxicity, thereby enhancing their safety and expanding the therapeutic dose range. When applied to covalent design against EGFR T790M, `CovaGEN` successfully designed molecules with favorable drug properties and specific covalent warheads. To the best of our knowledge, `CovaGEN` represents the first _de novo_ computational method for covalent drug design, offering a distinct alternative to traditional virtual screening approaches that rely on pre-selected compound libraries. 

rely on pre-selected compound libraries. overall framework of `CovaGEN` , a reinforced latent 1. Our approach employs a , and incorporates the information of the protein to ensure that the generated molecules can process of the diffusion model is guided by a resulting molecule has the desired covalent warhead. addresses the scarcity of covalent drug data, non-covalent drugs while still generating covalent lower toxicity. comprehensive experiments to evaluate the . First, we assessed the core generative module, version without 

## **2 Results** 

## **2.1 Overview** 

We present the overall framework of `CovaGEN` , a reinforced latent diffusion model with classifier guidance for covalent drug generation in Fig. 1. Our approach employs a diffusion model to sample the molecules from the drug-like latent space of a pretrained molecular VAE[15] , and incorporates the information of the protein target through ESM-2[16] as a condition to ensure that the generated molecules can bind to the given protein. The sampling process of the diffusion model is guided by a warhead classifier so that the resulting molecule has the desired covalent warhead. This classifier guidance technology addresses the scarcity of covalent drug data, enabling the model to be trained on non-covalent drugs while still generating covalent molecules. The trained diffusion model were fine-tuned by reinforcement learning to produce covalent molecules with lower toxicity. 

We conducted comprehensive experiments to evaluate the capabilities of different modules in `CovaGEN` . First, we assessed the core generative module, the latent diffusion model, by training a version without any conditions, classifier guidance, and reinforcement learning ( `CovaGEN-uncond` ). This allowed us to evaluate the model's essential ability to learn molecular grammar and capture the distribution. Specifically, we focused on assessing the validity, novelty, uniqueness, and diversity of the generated molecules. Subsequently, we introduced conditioning into the latent diffusion model ( `CovaGEN-cond` ) to generate molecules based on given target proteins. This was designed to assess `CovaGEN` 's capacity to generate molecules with high binding affinity to protein targets—critical for covalent bond formation—while maintaining favorable drug-like properties. To further demonstrate `CovaGEN` 's ability to generate molecules with specific covalent warheads, we selected four distinct 

warheads and applied classifier-guidance to steer `CovaGEN-cond` 's sampling process ( `CovaGEN-guide` ). We assessed the effectiveness of the guidance and the model's ability to preserve essential molecular properties during this process. Additionally, to showcase the method's potential in optimizing the safety of the generated molecules, we fine-tuned the model using reinforcement learning ( `CovaGEN-rl` ) to minimize the toxicity of the generated molecules. Finally, to illustrate the method's potential in discovering covalent inhibitors, we applied `CovaGEN` to EGFR T790M and Mpro and demonstrated the covalent binding and inhibitory efficacy of the designed molecules. 

## **2.2 Unconditional molecule generation** 

To design covalent drugs, it is crucial that the model accurately captures the molecular grammar and chemical space underlying valid drug-like molecules, as this forms the foundation for covalent drug design. In `CovaGEN` , the unconditional latent diffusion model ( `CovaGEN-uncond` ) serves as the core component for generating druglike molecules. Therefore, we first evaluated whether `CovaGEN-uncond` could generate valid, novel, and diverse molecules, and if it could effectively learn the distribution of molecules in the training set. In this way, we aim to ensure that the model is well-equipped for the subsequent task of generating molecules with specific covalent warheads and desirable drug-like properties. 

in the training set. In this way, we aim to ensure for the subsequent task of generating molecules desirable drug-like properties. in Fig 2a,a, we evaluated the generated molecules benchmark[[17]] , which include chemically validity of generated molecules not in the training set), molecules generated), and molecular diversity (IntDiv). evaluation of the model's capability to generate viable the product of these four metrics (PM) as an overall `CovaGEN` with five baseline models: VAE[[15]] , the latent space; CharRNN[[6]] , which generates using a recurrent neural network; JT-VAE[[8]] , a adversarial networks to learn the distribution of EDM[[19]] , which generates molecules in 3D space. Our as indicated by the product metric (PM). as depicted in Fig. 2b,b, the different property generated by `CovaGEN-uncond` closely match the distribution of MACCS molecular 

As shown in Fig 2a,a, we evaluated the generated molecules using the metrics from the MOSES benchmark[[17]] , which include chemically validity (Validity), novelty (the proportion of generated molecules not in the training set), uniqueness (the number of unique molecules generated), and molecular diversity (IntDiv). To provide a comprehensive evaluation of the model's capability to generate viable molecules, we also calculated the product of these four metrics (PM) as an overall performance measure. We compared `CovaGEN` with five baseline models: VAE[[15]] , which sample molecules directly from the latent space; CharRNN[[6]] , which generates molecules character-bycharacter using a recurrent neural network; JT-VAE[[8]] , a junction tree variational autoencoder that constructs molecules in a hierarchical manner; Latent GAN[18] , which uses generative adversarial networks to learn the distribution of molecular latent vectors; and EDM[[19]] , which generates molecules in 3D space. Our results showed that `CovaGEN` performed comparably across individual metrics, achieving the highest overall performance, as indicated by the product metric (PM). 

Furthermore, as depicted in Fig. 2b,b, the different property density distributions of molecules generated by `CovaGEN-uncond` closely match those of the training set. We visualized the distribution of MACCS molecular fingerprints[20] in 2D space using UMAP, as illustrated in Supplementary Figure 1. The molecules generated by `CovaGEN-uncond` and the original molecules are distributed in the same space, exhibiting consistent dispersion characteristics. These results demonstrate that the diffusion model effectively learns the distribution of molecular space, enabling the generation of molecules that closely mirror real-world counterparts in various properties. This capability underscores the potential of `CovaGEN-uncond` to generate diverse, valid molecules while accurately capturing the chemical space of the training set, laying a solid foundation for generating covalent drugs with desirable properties. 

## **2.3 Conditional non-covalent ligand generation** 

The ability of molecules to bind non-covalently to target proteins is essential for facilitating subsequent covalent bonding. Thus, we extended the `CovaGEN-uncond` model by integrating a protein sequence encoder, ESM-2[16] , which encodes the amino acid sequences of target proteins into continuous latent vectors. This enhancement allows the model, now referred to as `CovaGEN-cond` , to generate molecules specifically designed to bind non-covalently to the given protein targets. Here, we trained `CovaGEN-cond` on the CrossDock dataset[21] and generated 100 molecules for each of the 100 unique protein targets in the test set. We docked the generated molecules to their respective protein targets using QuickVina2[22] , and evaluated their binding affinity based on Vina scores. However, docking alone cannot fully reflect drug-likeness or synthetic feasibility. Molecules with high docking scores may still contain unrealistic or impractical substructures. To provide a more comprehensive assessment, we further evaluated the generated molecules using Lipinski's Rule of Five, QED, Synthetic Accessibility (SA) scores. In addition, we computed molecular diversity and generation time to reflect chemical novelty and efficiency. To integrate these assessments, we proposed a composite metric, the Tri-Factor Drug Score (TFDS), which combines the Vina score, QED, and SA into a single value. TFDS enables us to jointly evaluate binding potential, drug-likeness, and synthetic tractability, offering a more robust assessment of molecular quality. 

composite metric, the Tri-Factor Drug Score (TFDS), QED, and SA into a single value. TFDS enables us to drug-likeness, and synthetic tractability, offering quality. our method against three baseline methods: 3D-SBDD approach that generates the 3D structure demonstrate that our method produces molecules also employs a diffusion model, its sampling results in molecules with impractical substructures In contrast, `CovaGEN-cond` samples within a that the generated molecules are more rational molecules with high docking affinity in Fig. 2d,d, colored according to its SA score. While many of these molecules performed poorly in terms drug-likeness and synthetic accessibility. 

We compared our method against three baseline methods: 3D-SBDD[23] , a 3D generative method that leverages graph representations of protein pockets; Pocket2Mol[24] , which generates molecules inside the protein pocket autoregressively; and DiffSBDD[12] , a conditional generation approach that generates the 3D structure of ligands. The results in Fig. 2c demonstrate that our method produces molecules with significantly higher scores in all metrics compared to other methods, notably surpassing DiffSBDD. Although DiffSBDD also employs a diffusion model, its sampling within a discrete 3D space sometimes results in molecules with impractical substructures that are difficult to synthesize. In contrast, `CovaGEN-cond` samples within a continuous drug-like latent space, ensuring that the generated molecules are more rational and align better with the structures of real-world drug-like compounds. Furthermore, we visualized a scatter plot of molecules with high docking affinity in Fig. 2d,d, where each point represents a molecule, colored according to its SA score. While Pocket2Mol achieved great Vina scores, many of these molecules performed poorly in terms of QED and SA. In contrast, our method generated molecules with commendable Vina scores while maintaining superior drug-likeness and synthetic accessibility. Additionally, Fig. 2e demonstrates that the Vina scores of molecules generated by our method exhibit significantly lower variance compared to Pocket2Mol. Pocket2Mol shows a higher number of outliers and greater variance across these metrics, suggesting that our method produces more consistent and reliable molecules. Examples of these generated molecules are provided in Supplementary Figure 2. Besides, we performed cross-docking to evaluate the target-specific bias of CovaGEN-generated molecules (Supplementary Figure 3 and Supplementary Figure 4). Overall, these molecules generally achieved higher docking scores with their intended proteins compared to other targets, and statistical 

analysis suggests a trend toward higher on-target scores, indicating effective conditioning on the target. Nevertheless, some molecules generated for other proteins also exhibited moderately favorable binding, reflecting potential off-target effects as well as the inherent limitations of docking scores in fully capturing specificity. Detailed comparisons are provided in Supplementary Note 4. 

## **2.4 Covalent ligand generation** 

Building on the success of generating non-covalent ligands with `CovaGEN-cond` , we extended the model to covalent ligand generation by incorporating specific warhead guidance. Given the lack of available datasets for covalent ligands, it was not feasible to directly train a model for covalent drug generation. Instead, we employed the classifierguidance technique introduced by[25] to direct the generation process toward molecules containing desired covalent warheads. We selected four commonly used covalent warheads (as shown in Fig. 3 and Supplementary Note 1) and trained binary classifiers to detect the presence of each warhead within the latent vectors during the sampling process of the diffusion model. Using these classifier-guided vectors, we generated 100 molecules for each of the 100 protein targets in the same CrossDock test set. Fig. 3a and Supplementary Table 1 shows the occurrence of covalent warheads in molecules generated under varying classifier guidance scales ( _s_ ). As the scale increases, the number of molecules containing the targeted warheads rises accordingly. However, for higher values of _s_ , particularly for acrylamide and nitrile warheads, a slight decline in occurrence is observed. This reduction is likely due to distortion of the sampling distribution caused by an overly large guidance scale, which shifts the distribution away from its original, more rational form. The effectiveness of classifier guidance varies depending on the covalent warhead used. For example, with a guidance scale of _s_ = 10 _,_ 000, only a small number of generated molecules contain the cyanamide warhead. This is likely due to the fact that the generation process is constrained by multiple factors. In addition to classifier guidance, the given protein target also influences the resulting molecular structures. Furthermore, the drug-like latent space learned by the VAE imposes additional constraints on the decoded molecules. If the latent space contains few molecules with the desired warhead, the performance of classifier guidance will be limited. The proportion of molecules containing each of these four warheads in the VAE training set is shown in Supplementary Figure 5, where it is evident that a higher proportion of warhead-containing molecules correlates with better guidance performance. 

for each of the 100 protein targets in the same and Supplementary Table 1 shows the occurrence of molecules generated under varying classifier guidance scales ( _s s_ is observed. This reduction is likely due to caused by an overly large guidance scale, which its original, more rational form. The effectiveness on the covalent warhead used. For example, 000, only a small number of generated molecules This is likely due to the fact that the generation factors. In addition to classifier guidance, the given the resulting molecular structures. Furthermore, the the VAE imposes additional constraints on the contains few molecules with the desired warhead, in the VAE training set is shown in Supplementary that a higher proportion of warhead-containing performance. random of molecules 

Fig. 3b provides random examples of molecules generated with different classifier guidance at _s_ = 10 _,_ 000, with the warheads highlighted in blue. We further compared the properties of molecules generated with and without classifier guidance. As shown in Fig. 3c, the properties of the generated molecules were not adversely impacted by the introduction of classifier guidance, indicating that `CovaGEN-guide` can successfully incorporate desired covalent warheads while preserving key bioactivity and drug-likeness. 

## **2.5 Toxicity optimization with reinforcement learning** 

While covalent drugs hold the potential for enhanced efficacy through prolonged target inhibition, safety concerns such as dose-limiting toxicity have long posed challenges in their design[26] . To address this issue, we applied a reinforcement learningbased approach to fine-tune the trained conditional latent diffusion model, aiming to reduce the acute toxicity of the generated molecules. The median lethal dose (LD50) was used as an intermediary measure of acute toxicity, which were negatively logtransformed as –log(mol/kg) to align higher values with greater toxicity. An XGBoost regressor was trained to predict LD50, which was then served as the reward function for fine-tuning the model using policy gradient methods (see Section 4.5). In addition to acute toxicity, we also considered two clinically relevant endpoints—hepatotoxicity and cardiotoxicity. To this end, random forest classifiers were independently trained for each endpoint and incorporated as reward signals to further fine-tune the model toward generating safer compounds. After the fine-tuning process, the model was used to generate 100 molecules for each protein target in the same crossdocked test set. 

Fig. 4a shows the distribution of predicted LD50 values for molecules generated with and without fine-tuning. The fine-tuned model produced molecules with lower LD50 values, indicating a reduction in acute toxicity. In Fig. 4b, the increased proportion of predicted non-toxic molecules of different toxicity endpoints further suggests that the model effectively avoids generating toxic structures. Additionally, we selected a subset of acute toxicity alert structures from[[27]] and compared their occurrence in the generated molecules. As shown in Fig. 4c,c, the presence of these toxic alert structures was significantly reduced, further demonstrating the model's ability to decrease toxicity. More examples of generated molecules can be found in Supplementary Figure 6. 

fine-tuning. The fine-tuned model produced non-toxic molecules of different toxicity endpoints toxicity alert structures from[[27]] and compared their molecules. As shown in Fig. 4c,c, the presence of these reduced, further demonstrating the model's model. Notably, there were minimal differences generated by the fine-tuned and non-fine-tuned QED, SA, and molecular diversity. The Vina model, which might suggest a trade-off **drug design against specific protein** 

Fig. 4d provides an overview of the drug-like properties of the molecules generated by the fine-tuned model. Notably, there were minimal differences between the properties of molecules generated by the fine-tuned and non-fine-tuned models, including metrics like Lipinski, QED, SA, and molecular diversity. The Vina score was slightly higher for the fine-tuned model, which might suggest a trade-off between toxicity and binding affinity, where the reduction in toxicity led to the rejection of some high-affinity substructures. 

## **2.6 Covalent drug design against specific protein targets** 

Here, we selected two distinct targets: the Human Epidermal Growth Factor Receptor (EGFR) with the T790M mutation and the SARS-CoV-2 Main Protease (Mpro), and employed `CovaGEN` to design covalent drug molecules against them. EGFR is a critical target in cancer therapy due to its key role in regulating cell proliferation and growth[28] , while Mpro is an essential enzyme required for viral replication and transcription[29] , making it a prime target for the development of covalent inhibitors to address COVID-19. Substantial efforts have been devoted to the discovery and design of inhibitors for these targets, leading to the development of FDA-approved drugs, such as those illustrated in Fig. 5b and f. These drugs act as covalent inhibitors through different covalent warheads, highlighted in blue. EGFR inhibitors utilize acrylamide 

warheads that form irreversible bonds with Cys797, while Mpro inhibitors employ nitrile warheads that establish reversible covalent bonds with Cys145. Fig. 5a and e provides a depiction of the molecular structures and covalent binding poses of these inhibitors. 

In our experiment, we utilized `CovaGEN` to generate 100 molecules with certain warheads for each protein target. For comparison, we also generated non-covalent ligands using `CovaGEN-cond` , and manually added warheads to these molecules. This approach serves as an approximation of the "ligand-first" covalent drug design paradigm. As expected, the basic properties of the generated molecules align with earlier experiments (Supplementary Figure 7): `CovaGEN` -produced molecules show lower toxicity and higher QED, though optimizing for toxicity slightly reduced the docking scores. 

To further assess the likelihood of covalent bond formation, we calculated the distances between the warhead atoms and the target residue for docked molecules. For EGFR, the measured distance was between the sulfur atom of the cysteine residue and the _α_ -carbon of the acrylamide warhead's C=C double bond. For Mpro, the distance was measured between the nitrogen atom of the warhead and the sulfur atom of the cysteine residue. Shorter distances indicate a higher likelihood of covalent bond formation between the ligand and the protein. Molecules with distances below 4[˚] A were classified as successful in forming covalent bonds.[[30]] . As shown in Fig. 5c and g, covalent ligands generated by our method exhibit smaller atom distances, with a higher proportion of successful molecules. We also performed covalent docking targeting the cystine residue using Maestro software and calculated the RMSD between covalent and non-covalent poses. Lower RMSD values suggest the molecule fits better into the protein pocket for covalent inhibition[[31]] . Comparing to adding warheads randomly, molecules generated with `CovaGEN` has lower RMSD values, indicating better tendancy to form covalent bonds. Fig. 5dd and h highlights the top three molecules with the highest docking scores, all of which exhibit small differences between covalent and noncovalent docking poses and short atom distances. The performance in both RMSD and distance indicates that our method effectively learns ligand-pocket interaction patterns, enhancing the likelihood of covalent inhibition. 

between the ligand and the protein. Molecules with as successful in forming covalent bonds.[[30]] . As of successful molecules. We also performed covalent using Maestro software and calculated the poses. Lower RMSD values suggest the molecule for covalent inhibition[[31]] . Comparing to adding `CovaGEN` bonds. Fig. 5dd and h highlights the top three poses and short atom distances. The indicates that our method effectively learns enhancing the likelihood of covalent inhibition. idea of `CovaGEN` is to emulate the"ligand-first" A generative model is first trained on non-covalent binders for a target protein, after which classifier 

## **3 Discussion** 

The core idea of `CovaGEN` is to emulate the"ligand-first" strategy used in medicinal chemistry. A generative model is first trained on non-covalent ligands to produce high-affinity binders for a target protein, after which classifier guidance introduces a covalent warhead. This avoids reliance on scarce covalent ligand–target data while preserving binding affinity, drug-likeness, and other key properties. In doing so, `CovaGEN` expands the design space for covalent drugs and enables discovery of novel candidates. 

Although classifier-guidance can be used for controllable molecular generation and optimization of specific properties, it relies on an effective classifier with high accuracy and differentiability. While toxicity optimization could theoretically be approached using this method, we opted for a reinforcement learning strategy instead. For complex properties like LD50, which are influenced by a multitude of factors including molecular properties, metabolism, and experimental conditions, training an effective 

classifier is challenging. In our preliminary trials, we found that it was difficult to train a classification model based on the molecular latent vectors. As a result, we opted for reinforcement learning method to optimize the toxicity of the generated molecules, which is also a effective approach for optimizing molecular properties, but may lack the plug-and-play convenience offered by the classifier-guided method. 

`CovaGEN` takes protein sequences as input and generates covalent drug candidates in SMILES format, utilizing only 2D information. While 3D molecular generation may provide an advantage in modeling protein-ligand interactions more accurately, it requires additional computational resources and may not always be feasible, especially for proteins with uncharacterized structures. The use of sequence-based input allows for drug design targeting these unknown proteins. However, this approach does not fully capture the 3D interactions between molecules, which may limit its ability to optimize the binding process. Future work that incorporates 3D interaction data could provide a more detailed understanding of the binding environment and further improve the design of covalent inhibitors. Another fundamental limitation is our reliance on docking scores and distance-based metrics to approximate covalent binding potential. While these in silico methods provide useful filters, they cannot fully capture the reactivity and kinetics of covalent bond formation. Thus, they should be viewed as preliminary proxies rather than definitive evidence of covalent binding. In addition, the validity domain of our models must be carefully considered. Since the generative model is trained on non-covalent ligands, extrapolation to novel covalent scaffolds or warheads outside the training distribution may introduce uncertainty. This highlights the need for cautious interpretation of results and for complementary validation strategies. At the same time, the large number of candidate molecules generated poses challenges for downstream prioritization. To address these issues, several strategies can be adopted: multi-criteria scoring functions (e.g., TFDS) to balance affinity, drug-likeness, and synthetic accessibility; pocket-specific pharmacophore constraints or covalent docking to enrich for reactive candidates; ADMET predictors to eliminate unsafe compounds; and clustering or diversity analysis to reduce redundancy while maintaining chemical diversity. Together, these approaches can refine the candidate pool, ensuring that selected molecules are both reliable and experimentally tractable. 

kinetics of covalent bond formation. Thus, they should rather than definitive evidence of covalent binding. the validity domain of our models must be carefully is trained on non-covalent ligands, extrapolation need for cautious interpretation of results and for At the same time, the large number of candidate for downstream prioritization. To address these adopted: multi-criteria scoring functions (e.g., and synthetic accessibility; pocket-specific docking to enrich for reactive candidates; ADMET compounds; and clustering or diversity analysis to chemical diversity. Together, these approaches ensuring that selected molecules are both reliable and of five main modules: a variational autoencoder 

## **4 Methods** 

`CovaGEN` consists of five main modules: a variational autoencoder (Section 4.1), a diffusion model (Section 4.2), a condition module (Section 4.3), classifier guidance (Section 4.4), and reinforcement learning (Section 4.5). The VAE maps SMILES strings into the latent space, while the diffusion model learns this space and generates molecular latent vectors. Protein target sequences are incorporated into the diffusion process as condition. Classifier guidance introduces specific covalent warheads, and reinforcement learning enhances the safety of the generated molecules. Below, we will provide a detailed description of each module. 

## **4.1 Variational autoencoder for drug-like molecules** 

We employed a variational autoencoder (VAE)[15] with an attention mechanism to learn a continuous latent representation of molecular structures from their SMILES strings and reconstruct them back into valid SMILES. The VAE uses an RNN-based encoder–decoder architecture, where SMILES are tokenized at a near-character level to preserve chemical specificity (e.g., keeping multi-character elements such as "Cl" and "Br" intact). Both the encoder and decoder comprise three stacked GRU layers, and an attention head is applied after the final GRU layer in the encoder to allow the model to selectively focus on relevant parts of the input sequence during encoding. 

**Dataset.** To obtain the training molecules for the VAE model, we downloaded "instock" and "drug-like" molecules from the ZINC database[32] , representing compounds that are readily purchasable and adhere to drug-likeness criteria such as Lipinski's Rule of Five[33] . We randomly selected 1,200,000 molecules from the molecules downloaded as the training data for the VAE. 

**Training.** The VAE is trained to optimize its evidence lower bound, and the training objective is 

_L_ VAE = E E _qϕϕ_ ( _z|x|xx_ )[log[log _pθθ_ ( _x|z|zz_ )] _− D_ KL(( _qϕϕ_ ( _z|x|xx_ ) _||pp_ ( _z_ the reconstruction loss E _qϕϕ_ ( _z|x|xx_ )[log[log _pθθ_ ( _x|z|zz_ )] for the loss for encoder's output and standard Gaussian More details on the training can be found in accuracy and training loss curve of VAE is shown **diffusion model (CovaGEN-uncond)** diffusion models are a class of powerful likelihood-based we used the latent diffusion framework to fit the VAE. The latent space provided by the trained VAE the input data while reducing its dimensionality. _z_ 0 over a series of _T_ time steps until it becomes _∈_ (0 _,_ 1), _αtt_ = 1 _− βtt_ . 

_L_ VAE = E E _qϕϕ_ ( _z|x|xx_ )[log[log _pθθ_ ( _x|z|zz_ )] _− D_ KL(( _qϕϕ_ ( _z|x|xx_ ) _||pp_ ( _z_ )) (1) Where the reconstruction loss E _qϕϕ_ ( _z|x|xx_ )[log[log _pθθ_ ( _x|z|zz_ )] for the decoder _pθ_ ( _x|z_ ) and KL-divergence loss for encoder's output and standard Gaussian are minimized concurrently. More details on the training can be found in Supplementary Note 2. The reconstruction accuracy and training loss curve of VAE is shown in Supplementary Figure 8. 

## **4.2 Latent diffusion model (CovaGEN-uncond)** 

Latent diffusion models are a class of powerful likelihood-based generative models[34] . Here, we used the latent diffusion framework to fit the latent space of the pretrained VAE. The latent space provided by the trained VAE captures the essential features of the input data while reducing its dimensionality. Within this latent space, a forward diffusion process is applied, which involves gradually adding Gaussian noise to the latent vectors _z_ 0 over a series of _T_ time steps until it becomes _zt_ which is indistinguishable from pure Gaussian noise, governed by a forward diffusion noise schedule _β_ 1 _...βt_ ( _βt ∈_ (0 _,_ 1), _αtt_ = 1 _− βtt_ . 

New samples are generated through the reverse process. Starting from pure Gaussian noise in the latent space, the model tries to recover noiseless latent vectors by reversing the forward diffusion process iteratively. This reverse process is learned using a neural network that approximates the reverse diffusion distribution, where _µθ_ denotes the 

network to approximate the mean and the variance is deemed as a scalar value . 

Following[35] , here the network _µθ_ is parameterized as 

Where _ϵθ_ is a multi-layer perceptron parameterized to predict the noise added to the latent vector. Once the reverse diffusion process produces the denoised latent vector, this latent variable is then passed through a decoder, which maps it back to the original data space, generating a new sample that resembles the training data. 

**Training.** During training, we randomly select a molecule from the ZINC dataset and a timestep _t_ . The molecule is passed through the VAE's encoder to produce the molecular latent vector _z_ 0. Then _z_ 0 is noised following the forward process to _zt_ . The overall training objective is 

Which means that the latent diffusion model's network _ϵθ_ is trained to predict the noise _ϵ_ added to the molecular latent vector. For `CovaGEN-uncond` , we employed a learning rate of 1e-3, a batch size of 65536, and T=200 timesteps. **Sampling.** To generate new samples, we first randomly sampled a latent vector _zT ∼N_ (0 _, I_ ). The latent vector _zt_ is passed through the trained noise prediction network _ϵθ_ along with the timestep _t_ within specified timesteps _T_ to obtain _zt−_ 1. Finally, the denoised latent vector _z_ 0 is decoded into its corresponding molecule's SMILES representation using the trained VAE decoder. 

## **4.3 Conditional latent diffusion model (CovaGEN-cond)** 

To generate the ligand molecules that bind to the given protein, we incorporate the protein information into the latent diffusion model. Here, our noise prediction network _ϵθ_ is designed as a multi-layer perceptron with the multi-head cross-attention mechanism to incorporate the encoded protein conditional information[34][,][36] . Specifically, we first employed a pretrained protein encoding model ESM-2[16] , a pretrained language model designed specifically for protein sequence modeling and analysis, to encode the target protein's amino acid sequence representation into the continuous vector as the conditional information _C_ = _{c_ 1 _, c_ 2 _, ..., cn}_ , where _n_ represents the number of amino acids of the protein. After we obtain the positional protein representation _C_ , we feed it along with the molecular vector _zt_ into the cross-attenion layer to obtain a global 

protein representation vector _a_ . The cross-attention layer is 

where _WQ_ , _WK_ , _WV_ are learnable weight matrices. Concatenate _a_ with _zt_ and have the combine vector fed through another multi-layer perceptron MLPout, the output latent vector is obtained. 

**Dataset.** For the conditional latent diffusion model to learn the relationship between ligands and protein targets to incorporate protein information, we employed the protein-ligand paired dataset CrossDocked2020, as previously proposed in[21] . For a fair comparison, we employed the same preprocessing procedure as in[23][,][37] and splitting method as in[38] . The original dataset contains 22.5 million docked protein–ligand pairs at varying levels of quality. These data points are filtered with a binding pose RMSD greater than 1[˚] A, resulting in a refined subset of 184,057 data points. To reduce redundancy, MMseqs2 was used to cluster the data with 30% sequence identity. From this, we randomly sampled 100,000 protein–ligand pairs for training and select 100 proteins from the remaining clusters for testing. 

was sampled 100,000 protein–ligand pairs for the remaining clusters for testing. During training, we randomly select a a timestep _t_ . The protein sequence is passed through the condition _c_ , and the ligand is passed through _z_ 0. Then. Then _z_ 0 overall training objective is _L_ = _EE_ ( _x_ ) _,ε∼N_ (0 _,_ 1) _, t_ � _||ϵ − ϵθ_ ( _zt, t, c_ ) _||_ 2[2] � means that the latent diffusion model's network _ϵθθ_ added to the molecular latent vector. For of 3e-3, a batch size of 1024, and T=300 timesteps. in Supplementary Figure 9. To generate new samples, we first choose a protein _c_ . We then randomly sample a latent vector _zTT_ passed through the trained noise prediction network _ϵθ t_ within specified timesteps _T_ to obtain _zt−t−−_ 1.. _z_ 0 is decoded into its corresponding molecule's 

**Training.** During training, we randomly select a protein-ligand pair from the dataset and a timestep _t_ . The protein sequence is passed through the ESM-2 encoder to produce the condition _c_ , and the ligand is passed through the VAE's encoder to produce the molecular latent vector _z_ 0. Then. Then _z_ 0 is noised following the forward process to _zt_ . The overall training objective is 

Which means that the latent diffusion model's network _ϵθθ_ is trained to predict the noise _ϵ_ added to the molecular latent vector. For `CovaGEN-cond` , we employed a learning rate of 3e-3, a batch size of 1024, and T=300 timesteps. The training loss curve is shown in Supplementary Figure 9. 

**Sampling.** To generate new samples, we first choose a protein target and encode it as condition _c_ . We then randomly sample a latent vector _zTT ∼N_ (0 _, I_ ). The latent vector _zt_ is passed through the trained noise prediction network _ϵθ_ along with _t_ and _c_ at each timestep _t_ within specified timesteps _T_ to obtain _zt−t−−_ 1.. Finally, the denoised latent vector _z_ 0 is decoded into its corresponding molecule's SMILES representation using the trained VAE decoder. 

## **4.4 Classifier-guidance** 

To further guide the sampling process in generating molecules with desired covalent warheads, we employed the classifier-guidance mechanism for diffusion models[25] . The classifier is trained to determine whether the molecules corresponding to the noisy latent vectors, generated using the same forward diffusion process as the diffusion model it guides, contain the covalent warhead or not. 

**Dataset.** We selected four different covalent warheads for covalent ligand generation: acrylamide, cyanamide, nitrile, and methyl acrylate. To curate the binary classification dataset for each covalent warhead, for each type of covalent warhead, we randomly selected 80,000 molecules from the previously downloaded Zinc dataset. Each Covalent warhead was then randomly appended to half of these molecules, resulting in four balanced datasets containing both warhead-modified and unmodified molecules. 

**Training.** Binary classifiers were trained for each of the warheads. These classifiers are multi-layer perceptrons trained to minimize the binary cross-entropy loss between the true labels of the latent vectors which correspond to the label of the original molecule, regardless of the noise applied. The accuracy of the classifier models for the four warheads is shown in Supplementary Figure 5. For classifiers training, we employed a learning rate of 3e-4, a batch size of 1000. 

**Sampling.** To guide the sampling process, at each timestep, we calculated the gradient _∇zt_ of the classifier _pϕ_ with respect to the latent vector for the given class _y_ , which is used to perturb the mean of the reverse distribution. 

## **4.5 Policy gradient optimization** 

To optimize drug properties that are of relatively more complexity, such as acute toxicity, the classifier-guidance technique encounters barriers such as the difficulty in training a classifier that is strong enough to perform guidance. Inspired by[39] , here we model the latent diffusion process as a Markov decision process, hence reinforcement learning algorithms such as policy gradient can be employed. Denote a Markov decision process with _T_ timesteps as 

To optimize a given rewarding function _R_ ( _st, at_ ), the objective can be denoted as 

where _π_ is the policy that takes action given state _st_ . The inference process of latent diffusion models is a process that predicts noise added to the latent vection _zt_ in _T_ timesteps. According to the diffusion process itself, it has the Markov characteristic. Then when the diffusion model is given, the whole inference process can be defined as 

_zt−_ 1 is sampled from such distribution instead. Here _s_ is the scaling factor for the classifier's guidance, the higher the factor _s_ is, the stronger the guidance provided by the classifier. The final denoised latent vector _z_ 0 is decoded to its SMILES representation with the VAE decoder. 

a Markov decision process 

Here the state _st_ is denoted by the condition _c_ , time-step _t_ and the latent vector _zt_ . Then the policy is the model _pθ_ . The action _at_ is proposed by the model as the latent vector at the previous timestep _zt−_ 1. _δ_ is a distribution that takes value 1 only at the value on its subscript. The distribution of the initial state _s_ 0 is similarly defined as _ρ_ 0. The scoring function _r_ , which serves as the reward signal, includes multiple predictive models trained on molecular toxicity data, including a regression predictor for acute toxicity (LD50)[40] , as well as binary classification models for specific toxicity endpoints such as hepatotoxicity and cardiotoxicity (see Supplementary Note 3 for details). The rewarding function provides a reward prediction only at time-step 0 after decoding _z_ 0 with the decoder _D_ . Henceforth, to optimize a specific rewarding function, the objective can be denoted as 

With the gradient ascent algorithm, _pθ_ can be updated toward the direction that produces molecules with higher desired properties. 

where _β_ denotes a scalar scaling factor. The gradient here is in the form of likelihood ratio 

In such manner, the network _pθ_ of the latent diffusion model can be optimized to produce latent vectors with expected lower acute toxicity when decoded into molecules. 

## **4.6 Metrics** 

We employed metrics used in[17] to evaluate methods' capability in generating molecules from scratch, including (1) Validity, the fraction of chemically valid molecules among generated molecules. (2) Novelty, which calculates the fraction of generated molecules that do not appear in the training set. (3) Unique@1000, which calculates the fraction of unique molecules for the first 1000 valid generated molecules. (4) IntDiv1 calculates the inner chemical diversity of the generated set of molecules. To reflect the model's ability in learning the chemical space of the training set, we included four molecule properties metrics: (1) Quantitative estimate of drug-likeness 

(QED), which scores between 0 and 1, with higher score indicating better drug-likeness of a compound. (2) Synthetic accessibility (SA), which scores between 0 and 1, with a higher score indicating that a compound is easier to synthesize. (3) Oil-water partition coefficient (LogP), which describes how hydrophilic or hydrophobic a molecule is. (4) Weight, the relative molecular mass of a molecule. 

To evaluate generated molecules' biological activity and drug properties, aside from QED, SA, we employed three more metrics: (1) Vina score, which evaluates the affinity of molecules binding to the protein target, the lower the score is, the higher the binding affinity; (2) Lipinski's 5 rules, a set of criteria used to measure the druglikeness of a molecule; (3) Diversity, which measures the average pairwise similarity between molecules sampled from a pocket; (4) TFDS, Which combines each molecule's p Vina score, QED and SA, described as below 

Here _k_ = 0 _._ 2 is a scaling norm and _vina_ denotes the vina score. For acute toxicity, we employed median lethal dose (LD50), which indicating the dose required for a substance to cause death in 50% of a test population. Note that the LD50 values employed in this study is dimensionless values provided by TOXRIC, which involves converting the original LD50 value into -log(mol/kg) units. We use -log(LD50) to specifically refer to the dimensionless LD50 value. A smaller -log(LD50) indicates lower toxicity, which translates to a better score for the measured molecule. 

lethal dose (LD50), which indicating the dose death in 50% of a test population. Note that study is dimensionless values provided by TOXRIC, original LD50 value into -log(mol/kg) units. We use translates to a better score for the measured molecule. **and reproducibility** No data were excluded from the analyses. Sample using statistical methods. All experiments and data and outcome assessments. To ensure experiment are reported in the corresponding figure **summary** on research design is available in the 

## **4.7 Statistics and reproducibility** 

Data analyses were performed using Python 3.7, PyTorch 1.10.0, RDKit 2023.03.2, and QuickVina2. No data were excluded from the analyses. Sample sizes were not pre-determined using statistical methods. All experiments and data analyses were conducted in a randomized manner, and investigators were blinded to allocation during both the experiments and outcome assessments. To ensure reproducibility, statistical details for each experiment are reported in the corresponding figure legends and main text. 

## **4.8 Reporting summary** 

Further information on research design is available in the Nature Portfolio Reporting Summary linked to this article. 

## **Data availability** 

Source data for Figs. 2-5 are provided with this paper in Supplementary Data. All of the datasets used in this study are publicly available. The molecules used for the training of the molecular VAE and `CovaGEN-cond` are downloaded from the ZINC database (https://zinc.docking.org/). The raw data of the CrossDocked 2020 dataset were obtained from https://github.com/gnina/models/tree/master/data/ 

CrossDocked2020. The small mouse intraperitoneal LD50 subdataset was obtained from TOXRIC (https://toxric.bioinforai.tech/home). 

## **Code availability** 

The source codes are available on GitHub: https://github.com/BioChemAI/ CovaGEN and deposited on Zenodo at https://doi.org/10.5281/zenodo.18374022 (ref.[41] ). 

## **Acknowledgments** 

This work was supported in part by the National Natural Science Foundation of China (Grants 62572374, U22A2037, 62202353 and 62132015), and the Natural Science Basic Research Program of Shaanxi Province (2023-JC-QN-0707). 

## **Author contribution** 

led the manuscript writing. T.L., X.D. and S.S. evaluation. X.Y. provided expert guidance on manuscript. All authors discussed the results and the manuscript. **interests** declare no competing interests. L., Henning, N. J. & Nomura, D. K. Advances in _Reviews Drug Discovery_ **21** , 881–898 (2022). _et al._ Fragment-based covalent ligand discovery. _RSC_ (2021). 

- P.L. and L.G. conceived and supervised the research project. W.Z. and P.L. jointly 

- designed and implemented the overall framework. W.Z. and T.L. conducted the experiments and led the manuscript writing. T.L., X.D. and S.S. contributed to model training, and evaluation. X.Y. provided expert guidance on covalent drug design and revised the manuscript. All authors discussed the results and contributed to the final version of the manuscript. 

## **Competing interests** 

The authors declare no competing interests. 

## **References** 

- [1] Boike, L., Henning, N. J. & Nomura, D. K. Advances in covalent drug discovery. _Nature Reviews Drug Discovery_ **21** , 881–898 (2022). 

- [2] Lu, W. _et al._ Fragment-based covalent ligand discovery. _RSC chemical biology_ **2** , 354–367 (2021). 

- [3] Rachman, M. _et al._ Duckcov: a dynamic undocking-based virtual screening protocol for covalent binders. _ChemMedChem_ **14** , 1011–1021 (2019). 

- [4] Soul`ere, L., Barbier, T. & Queneau, Y. Docking-based virtual screening studies aiming at the covalent inhibition of sars-cov-2 mpro by targeting the cysteine 145. _Computational Biology and Chemistry_ **92** , 107463 (2021). 

- [5] Zeng, X. _et al._ Deep generative molecular design reshapes drug discovery. _Cell Reports Medicine_ 100794 (2022). 

- [6] Segler, M. H., Kogej, T., Tyrchan, C. & Waller, M. P. Generating focused molecule libraries for drug discovery with recurrent neural networks. _ACS central science_ **4** , 120–131 (2018). 

- [7] Gupta, A. _et al._ Generative recurrent networks for de novo drug design. _Molecular informatics_ **37** , 1700111 (2018). 

- [8] Jin, W., Barzilay, R. & Jaakkola, T. Dy, J. & Krause, A. (eds) _Junction tree variational autoencoder for molecular graph generation_ . (eds Dy, J. & Krause, A.) _Proceedings of the 35th International Conference on Machine Learning_ , Vol. 80 of _Proceedings of Machine Learning Research_ , 2323–2332 (PMLR, 2018). URL https://proceedings.mlr.press/v80/jin18a.html. 

- [9] Liu, Q., Allamanis, M., Brockschmidt, M. & Gaunt, A. Constrained graph variational autoencoders for molecule design. _Advances in neural information processing systems_ **31** (2018). 

- [10] De Cao, N. & Kipf, T. Molgan: An implicit generative model for small molecular graphs. _arXiv preprint arXiv:1805.11973_ (2018). 

   - _preprint arXiv:1805.11973_ (2018). 

   - _et al._ Mol-cyclegan: a generative model for molecular 

   - _Cheminformatics_ **12** , 2 (2020). A. _et al._ Structure-based drug design with _Computational Science_ 1–11 (2024). 

   - _al._ A dual diffusion model enables 3d molecule based on target pockets. _Nature Communications_ **15** 

   - C. & Guengerich, F. P. Elucidating mechanisms of _reviews Drug discovery_ **4** , 410–420 (2005). 

   - Joshi, N., Beck, D. A. & Pfaendtner, J. novo molecular design. _Chemical Science_ **12** , 

   - Evolutionary-scale prediction of atomic-level protein 

   - model. _Science_ **379** , 1123–1130 (2023). 

- [11] Maziarka, �L. _et al._ Mol-cyclegan: a generative model for molecular optimization. _Journal of Cheminformatics_ **12** , 2 (2020). 

- [12] Schneuing, A. _et al._ Structure-based drug design with equivariant diffusion models. _Nature Computational Science_ 1–11 (2024). 

- [13] Huang, L. _et al._ A dual diffusion model enables 3d molecule generation and lead optimization based on target pockets. _Nature Communications_ **15** , 2657 (2024). 

- [14] Liebler, D. C. & Guengerich, F. P. Elucidating mechanisms of drug-induced toxicity. _Nature reviews Drug discovery_ **4** , 410–420 (2005). 

- [15] Dollar, O., Joshi, N., Beck, D. A. & Pfaendtner, J. Attention-based generative models for de novo molecular design. _Chemical Science_ **12** , 8362–8372 (2021). 

- [16] Lin, Z. _et al._ Evolutionary-scale prediction of atomic-level protein structure with a language model. _Science_ **379** , 1123–1130 (2023). 

- [17] Polykovskiy, D. _et al._ Molecular sets (moses): a benchmarking platform for molecular generation models. _Frontiers in pharmacology_ **11** , 565644 (2020). 

- [18] Prykhodko, O. _et al._ A de novo molecular generation method using latent vector based generative adversarial network. _Journal of Cheminformatics_ **11** , 1–13 (2019). 

- [19] Hoogeboom, E., Satorras, V. G., Vignac, C. & Welling, M. Chaudhuri, K. _et al._ (eds) _Equivariant diffusion for molecule generation in 3D_ . (eds Chaudhuri, K. _et al._ ) _Proceedings of the 39th International Conference on Machine Learning_ , 

Vol. 162 of _Proceedings of Machine Learning Research_ , 8867–8887 (PMLR, 2022). URL https://proceedings.mlr.press/v162/hoogeboom22a.html. 

- [20] Durant, J. L., Leland, B. A., Henry, D. R. & Nourse, J. G. Reoptimization of mdl keys for use in drug discovery. _Journal of chemical information and computer sciences_ **42** , 1273–1280 (2002). 

- [21] Francoeur, P. G. _et al._ Three-dimensional convolutional neural networks and a cross-docked data set for structure-based drug design. _Journal of chemical information and modeling_ **60** , 4200–4215 (2020). 

- [22] Alhossary, A., Handoko, S. D., Mu, Y. & Kwoh, C.-K. Fast, accurate, and reliable molecular docking with quickvina 2. _Bioinformatics_ **31** , 2214–2216 (2015). 

- [23] Luo, S., Guan, J., Ma, J. & Peng, J. A 3d generative model for structure-based drug design. _Advances in Neural Information Processing Systems_ **34** , 6229–6239 (2021). 

- [24] Peng, X. _et al._ Chaudhuri, K. _et al._ (eds) _Pocket2Mol: Efficient molecular sampling based on 3D protein pockets_ . (eds Chaudhuri, K. _et al._ ) _Proceedings of the 39th International Conference on Machine Learning_ , Vol. 162 of _Proceedings of Machine Learning Research_ , 17644–17655 (PMLR, 2022). URL https://proceedings.mlr.press/v162/peng22b.html. 

- [25] Dhariwal, P. & Nichol, A. Diffusion models beat gans on image synthesis. _Advances in Neural Information Processing Systems_ **34** , 8780–8794 (2021). 

- [26] Singh, J., Petter, R. C., Baillie, T. A. & Whitty, A. The resurgence of covalent drugs. _Nature reviews Drug discovery_ **10** , 307–317 (2011). 

- [27] Fan, T., Sun, G., Zhao, L., Cui, X. & Zhong, R. Qsar and classification study on prediction of acute oral toxicity of n-nitroso compounds. _International journal of molecular sciences_ **19** , 3015 (2018). 

- [28] Uribe, M. L., Marrocco, I. & Yarden, Y. Egfr in cancer: Signaling mechanisms, drugs, and acquired resistance. _Cancers_ **13** , 2748 (2021). 

- [29] Jin, Z. _et al._ Structure of mpro from sars-cov-2 and discovery of its inhibitors. 

- [25] Dhariwal, P. & Nichol, A. Diffusion models beat gans on image synthesis. _Advances in Neural Information Processing Systems_ **34** , 8780–8794 (2021). 

- [26] Singh, J., Petter, R. C., Baillie, T. A. & Whitty, A. The resurgence of covalent drugs. _Nature reviews Drug discovery_ **10** , 307–317 (2011). 

- [27] Fan, T., Sun, G., Zhao, L., Cui, X. & Zhong, R. Qsar and classification study on prediction of acute oral toxicity of n-nitroso compounds. _International journal of molecular sciences_ **19** , 3015 (2018). 

- [28] Uribe, M. L., Marrocco, I. & Yarden, Y. Egfr in cancer: Signaling mechanisms, drugs, and acquired resistance. _Cancers_ **13** , 2748 (2021). 

- [29] Jin, Z. _et al._ Structure of mpro from sars-cov-2 and discovery of its inhibitors. _Nature_ **582** , 289–293 (2020). 

- [30] Soul`ere, L., Barbier, T. & Queneau, Y. Docking-based virtual screening studies aiming at the covalent inhibition of sars-cov-2 mpro by targeting the cysteine 145. _Computational Biology and Chemistry_ **92** , 107463 (2021). 

- [31] Hongyu, H. _et al._ The binding mechanism of failed, in processing and succeed inhibitors target sars-cov-2 main protease. _Journal of Biomolecular Structure and Dynamics_ 1–12 (2023). 

- [32] Irwin, J. J. & Shoichet, B. K. Zinc- a free database of commercially available compounds for virtual screening. _Journal of chemical information and modeling_ **45** , 177–182 (2005). 

- [33] Lipinski, C. A. Lead-and drug-like compounds: the rule-of-five revolution. _Drug discovery today: Technologies_ **1** , 337–341 (2004). 

- [34] Rombach, R., Blattmann, A., Lorenz, D., Esser, P. & Ommer, B. IEEE (ed.) _High-resolution image synthesis with latent diffusion models_ . (ed.IEEE) _Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)_ , 10684–10695 (2022). 

- [35] Ho, J., Jain, A. & Abbeel, P. Denoising diffusion probabilistic models. _Advances in Neural Information Processing Systems_ **33** , 6840–6851 (2020). 

- [36] Vaswani, A. _et al._ Attention is all you need. _Advances in neural information processing systems_ **30** (2017). 

Antigen-specific antibody design and optimization models. _bioRxiv_ 2022–07 (2022). _Nature biotechnology_ **35** learning. _arXiv preprint arXiv:2305.13301 al._ Toxric: a comprehensive database of _Nucleic Acids Research_ **51** , D1432–D1445 (2023). & Li, P. CovaGen: De novo covalent drug generation and safety. Zenodo (2026). URL **of the** `CovaGEN` **framework. (a)** Model structure of `CovaGEN` . _E_ and 

- [37] Luo, S. _et al._ Antigen-specific antibody design and optimization with diffusionbased generative models. _bioRxiv_ 2022–07 (2022). 

- [38] Steinegger, M. & S¨oding, J. Mmseqs2 enables sensitive protein sequence searching for the analysis of massive data sets. _Nature biotechnology_ **35** , 1026–1028 (2017). 

- [39] Black, K., Janner, M., Du, Y., Kostrikov, I. & Levine, S. Training diffusion models with reinforcement learning. _arXiv preprint arXiv:2305.13301_ (2023). 

- [40] Wu, L. _et al._ Toxric: a comprehensive database of toxicological data and benchmarks. _Nucleic Acids Research_ **51** , D1432–D1445 (2023). 

- [41] Zhang, W. & Li, P. CovaGen: De novo covalent drug generation with enhanced drug-likeness and safety. Zenodo (2026). URL https://doi.org/10.5281/zenodo. 18374022. 

## **Figure captions** 

**Fig. 1** : **Overview of the** `CovaGEN` **framework. (a)** Conceptual pipeline of `CovaGEN` for covalent drug generation. **(b)** Model structure of `CovaGEN` . _E_ and _D_ are the pretrained encoder and decoder of the molecular VAE we employed (Section 4.1). _z_ stands for the latent vector, while _zT_ is the noised version of _z_ . _ϵθ_ is the noise prediction network of the latent diffusion model, conditioned on the protein representation _C_ as input (Section 4.2 and 4.3). _∇_ is the gradient of warhead classifiers _pϕ_ ( _y|zt_ ) (Section 4.4). _ς_ denotes a Markov decision process used for reinforcement learning (Section 4.5). 

**Fig. 2** : **Results on** _**de novo**_ **molecule generation and protein target-based molecule generation metrics. (a)** Results of molecules generated with our de novo generation model and VAE, as well as other baseline models on MOSES metrics. **(b)** Properties' density distribution of molecules generated with our VAE and de novo generation model, as well as molecules of corresponding training set. (N=10,000 molecules) **(c)** Performance of molecules generated by different protein target-based molecule design methods on various metrics. **(d)** Scatter plot of molecules generated by Pocket2Mol and our method. Each spot represents a molecule, colored by their corresponding SA score. **(e)** Box plot of properties of molecules generated by Pocket2Mol and our method. Center lines denote median values, boxes represent the interquartile range, and whiskers extend to 1.5 times the interquartile range. 

**Fig. 3** : **Results of molecules generated with classifier-guidance. (a)** Occurrence of warheads with the guidance of different classifiers under different classifier scale _s_ settings in the range of [0, 1, 10, 100, 1,000, 10,000]. **(b)** Examples of molecules generated with different warheads. **(c)** Properties of molecules generated with/without the classifier-guidance. Box plots show the median (center line) and interquartile range (box), with whiskers extending to 1.5× the interquartile range. The bar plot for Lipinski values is shown as mean ± s.d. (N = 10,000 molecules). 

is shown as mean ± s.d. (N = 10,000 molecules). **of molecules generated with the toxicity** of non-hepatotoxic and non-cardiotoxic **(c)** Occurance of acute toxicity alert structures of in **(d)** fine-tuning. Box plots show the median (center × the interquartile range. The bar plot for is shown as mean ± s.d. (N = 10,000 molecules). **inhibitor desgin against EGFR T790M.** Neratinib covalent binded to Cys797 of EGFR **(b,f) (c,g)** Comparison of covalent and non-covalent generated with our method (blue) and randomly generated (grey) on three metrics. **(d,h)** Examples of 

**Fig. 4** : **Results of molecules generated with the toxicity fine-tuned model. (a)** Predicted LD50 value of molecules generated with model before/after fine-tuning. (b) Proportion of non-hepatotoxic and non-cardiotoxic molecules before and after fine-tuning **(c)** Occurance of acute toxicity alert structures of in molecules generated with model before/after fine-tuning. **(d)** Properties of molecules generated with model before/after fine-tuning. Box plots show the median (center line) and interquartile range (box), with whiskers extending to 1.5× the interquartile range. The bar plot for Lipinski values is shown as mean ± s.d. (N = 10,000 molecules). 

**Fig. 5** : **Covalent inhibitor desgin against EGFR T790M. (a,e)** FDA approved covalent drug Neratinib covalent binded to Cys797 of EGFR T790M and Nirmatrelvir covalent binded to Cys145 of Mpro. **(b,f)** Warhead and properties of Neratinib and Nirmatrelvir. **(c,g)** Comparison of covalent and non-covalent docking poses of molecules generated with our method (blue) and randomly adding the warhead to molecules generated (grey) on three metrics. **(d,h)** Examples of designed molecules. 

## **a** 

**----- Start of picture text -----**<br>
Warheads<br>R N R NH O N R [2] O R<br>N R [1] O<br>Guidance<br>O<br>N<br>O<br>N<br>N O<br>Protein targets Drug-like latent space Covalent drug<br>Toxicity control<br>SMILES Space 𝑧𝑧 Drug-Like Latent Space 𝑧𝑧𝑇𝑇<br>H<br>H N N Ε Forward Diffusion Process<br>O<br>O ∇ Warhead Classifier 𝑝𝑝𝜙𝜙 𝑦𝑦𝑧𝑧𝑡𝑡 𝑧𝑧𝑇𝑇<br>N<br>N O N O D ϵ𝜃𝜃 Denoising Network With Cross-Attention ϵ𝜃𝜃<br>𝐶𝐶 Condition<br>𝜏𝜏<br>Policy Gradient  ESM-2<br>Encoder<br>Toxicity Control Reward SGEAPNQALLAAQ……<br>ARTICLE IN PRESS<br>**----- End of picture text -----**<br>

**----- Start of picture text -----**<br>
b<br>**----- End of picture text -----**<br>

## **a** 

## **b** 

**----- Start of picture text -----**<br>
Model Validity Novelty Unique IntDiv PM<br>CharRNN 97.5% 84.2% 100% 0.856 0.703<br>JTN-VAE 100% 91.4% 100% 0.856 0.782<br>LatentGAN 89.7% 94.9%  100%  0.857 0.730<br>EDM 91.3% 64.3% 98.4%  0.917 0.530<br>VAE 97.3% 98.3%  100% 0.890 0.851<br>CovaGEN-<br>97.6% 100%  100%  0.877 0.856<br>uncond<br>c<br>Model TFDS Vina Score(↓) QED(↑) SA(↑) Lipinski(↑) Diversity(↑)  Time(s,↓)<br>Reference 0.650 ± 0.10 -7.242 ± 2.11 0.476 ± 0.21 0.728 ± 0.14 4.270 ± 1.16  —— ——<br>3D-SBDD 0.619 ± 0.09 -6.620 ± 1.59 0.509 ± 0.12 0.633 ± 0.10 4.764 ± 0.33  0.696 ± 0.12 19659±14704<br>Pocket2Mol 0.680 ± 0.07 -7.221 ± 2.13 0.585 ± 0.10 0.767 ± 0.09 4.831 ± 0.37  0.727 ± 0.16 2504±2207<br>DiffSBDD 0.594 ± 0.08 -6.929 ± 1.53 0.469 ± 0.09 0.579 ± 0.13 4.530 ± 0.37 0.728 ± 0.07 1634±769<br>CovaGEN-cond 0.785 ± 0.05 -7.390 ± 1.08 0.769 ± 0.01 0.825 ± 0.06 4.991 ± 0.10 0.730 ± 0.01 403±8<br>d<br>e<br>ARTICLE IN PRESS<br>**----- End of picture text -----**<br>

**----- Start of picture text -----**<br>
a<br>b<br>Substructures Samples<br>S O H O N NH OS N<br>N N O O<br>R N F N H O N N S NH NH N<br>C l<br>R NH N N NH N N O O N N NH C l O N ONH N H O H O OH ONH N NNH N<br>O RN [1] R [2] O NH NO H N O O H O OONH ON N N N O O NHN NH O<br>O<br>O<br>O O R OH N N O O O NHCNl O O O O O ON N N S NH ONH O OO<br>ARTICLE IN PRESS<br>**----- End of picture text -----**<br>

**----- Start of picture text -----**<br>
c<br>**----- End of picture text -----**<br>

**----- Start of picture text -----**<br>
a b<br>c<br>Alert Structures Example Structures Description CovaGEN-cond CovaGEN-rl<br>O<br>Tertiary aliph amine N N N Metabolite toxicity<br>O<br>Alkylchloride NN Genotoxicity<br>Cl<br>N<br>Heteroaromatic N Metabolite toxicity<br>N O<br>N<br>Hetero N nonbasic N Metabolite toxicity<br>O<br>d<br>ARTICLE IN PRESS<br>**----- End of picture text -----**<br>

**----- Start of picture text -----**<br>
a e<br>Cys797<br>Cys145<br>b f NH<br>Cl<br>N O Neratinib N O Nirmatrelvir<br>N N<br>N<br>O H N O H Docking score(Kcal/mol):   -7.9 O O NH Docking score(Kcal/mol):   -6.1<br>N SA:               0.60<br>SA:               0.72<br>Lipinski:       5 O NH Lipinski:       5<br>N F F<br>c g F<br>d h<br>OF NN O ONH ON ONH O NH O NH N NS F N N N O N OH F O NOHO FF F S N N N<br>Docking score Docking score Docking score Docking score Docking score Docking score<br>(Kcal/mol):  -8.2 (Kcal/mol):  -7.2 (Kcal/mol):  -7.0 (Kcal/mol):  -7.8 (Kcal/mol):  -7.7 (Kcal/mol):  -7.6<br>QED:        0.87 QED:        0.72 QED:        0.84 QED:        0.66 QED:        0.87 QED:        0.92<br>SA:           0.88 SA:           0.86 SA:           0.89 SA:           0.87 SA:           0.78 SA:           0.81<br>RMSD:     3.07 RMSD:     0.13 RMSD:     0.13 RMSD:     1.67 RMSD:     1.36 RMSD:     0.28<br>Distance:  3.05 Distance:  2.76 Distance:  3.01 Distance:  3.84 Distance:  3.40 Distance:  2.84<br>ARTICLE IN PRESS<br>**----- End of picture text -----**<br>
