"""Model adapter contract (FR-9, FR-10, FR-11).

Adding support for a new video model means writing one new subclass here —
nothing in canonical.py, router, verification, or the API layer changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from kinostate.compiler.canonical import GenerationRequest


class PayloadValidationError(ValueError):
    """Raised when a compiled payload violates the target model's feature set.

    FR-10 requires failing loudly here rather than silently degrading
    fidelity (e.g. dropping reference images past the model's max count).
    """


@dataclass
class CompiledPayload:
    model_name: str
    body: dict[str, Any]
    entity_count: int = 0
    warnings: list[str] = field(default_factory=list)


class ModelAdapter(ABC):
    """Base class every per-model adapter implements."""

    name: str = "unset"
    max_reference_entities: int = 1

    @abstractmethod
    def compile(self, request: GenerationRequest) -> CompiledPayload:
        """Translate a canonical GenerationRequest into this model's native payload."""

    def validate(self, payload: CompiledPayload) -> None:
        """Reject a payload the target model cannot actually serve (FR-10).

        Subclasses should call super().validate(payload) first, then add
        model-specific checks.
        """
        if payload.entity_count > self.max_reference_entities:
            raise PayloadValidationError(
                f"{self.name} supports at most {self.max_reference_entities} "
                f"reference entities per call, got {payload.entity_count}"
            )
