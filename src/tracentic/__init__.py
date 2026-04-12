"""Tracentic SDK for Python — LLM observability with scoped tracing and OTLP export."""

from ._client import Tracentic, configure, create_tracentic, get_tracentic
from ._global_context import TracenticGlobalContext
from ._options import AttributeLimits, ModelPricing, TracenticOptions
from ._scope import TracenticScope
from ._span import TracenticSpan

__all__ = [
    # Core API
    "create_tracentic",
    "configure",
    "get_tracentic",
    "Tracentic",
    # Models
    "TracenticScope",
    "TracenticSpan",
    # Configuration
    "TracenticOptions",
    "ModelPricing",
    "AttributeLimits",
    # Global context
    "TracenticGlobalContext",
]
