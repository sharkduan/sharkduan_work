# Covalent Edge Validity Gate

Final hard covalent edge decoding will select the highest-scoring candidate only after it passes reaction-family, valence, and local geometry checks. If no candidate passes, the generated molecule is marked invalid rather than forcing a covalent edge. This keeps invalid covalent attachment visible in evaluation instead of hiding it behind unconditional post-processing.
