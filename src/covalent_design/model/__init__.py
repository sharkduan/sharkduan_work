"""Model-stage public APIs for batch, heads, and final decode.

Exports are resolved lazily so importing an early-stage module such as
``covalent_design.model.pmdm_adapter`` does not pull in later Task 20/21
modules.
"""

__all__ = [
    "ALL_PMDM_OUTPUT_KEYS",
    "FinalDecodeResult",
    "ModelConfig",
    "OPTIONAL_PMDM_OUTPUT_KEYS",
    "REQUIRED_PMDM_OUTPUT_KEYS",
    "SMOKE_PLACEHOLDER",
    "apply_edge_message_weights",
    "build_stepwise_candidates",
    "decode_final_edge",
    "forward_covalent",
    "forward_pmdm",
    "inspect_batch",
    "make_model_batch",
    "validate_pmdm_outputs",
    "ValidityGate",
]


_EXPORTS = {
    "ALL_PMDM_OUTPUT_KEYS": ("covalent_design.model.pmdm_adapter", "ALL_PMDM_OUTPUT_KEYS"),
    "FinalDecodeResult": ("covalent_design.model.final_decode", "FinalDecodeResult"),
    "ModelConfig": ("covalent_design.model.config", "ModelConfig"),
    "OPTIONAL_PMDM_OUTPUT_KEYS": ("covalent_design.model.pmdm_adapter", "OPTIONAL_PMDM_OUTPUT_KEYS"),
    "REQUIRED_PMDM_OUTPUT_KEYS": ("covalent_design.model.pmdm_adapter", "REQUIRED_PMDM_OUTPUT_KEYS"),
    "SMOKE_PLACEHOLDER": ("covalent_design.model.pmdm_adapter", "SMOKE_PLACEHOLDER"),
    "ValidityGate": ("covalent_design.model.validity_gate", "ValidityGate"),
    "apply_edge_message_weights": ("covalent_design.model.edge_message_passing", "apply_edge_message_weights"),
    "build_stepwise_candidates": ("covalent_design.model.candidate_builder", "build_stepwise_candidates"),
    "decode_final_edge": ("covalent_design.model.final_decode", "decode_final_edge"),
    "forward_covalent": ("covalent_design.model.covalent_heads", "forward_covalent"),
    "forward_pmdm": ("covalent_design.model.pmdm_adapter", "forward_pmdm"),
    "inspect_batch": ("covalent_design.model.inspect", "inspect_batch"),
    "make_model_batch": ("covalent_design.model.batch", "make_model_batch"),
    "validate_pmdm_outputs": ("covalent_design.model.pmdm_adapter", "validate_pmdm_outputs"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attr_name = _EXPORTS[name]
    import importlib

    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
