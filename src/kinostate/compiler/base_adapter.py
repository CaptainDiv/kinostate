"""Model adapter contract (FR-9, FR-10, FR-11).

Adding support for a new video model means writing one new subclass here —
nothing in canonical.py, router, verification, or the API layer changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from kinostate.compiler.canonical import Entity, GenerationRequest


def describe_entity(entity: Entity) -> str:
    """Render an entity's description + forbidden traits as prompt text.

    Reference images alone leave the model with no textual reinforcement
    of what an entity looks like or what to avoid — this closes that gap
    (previously the description/forbidden_traits fields were stored but
    never actually used in a compiled prompt).
    """
    parts = [entity.description] if entity.description else []
    if entity.forbidden_traits:
        parts.append(f"(avoid: {', '.join(entity.forbidden_traits)})")
    return " ".join(parts)


class PayloadValidationError(ValueError):
    """Raised when a compiled payload violates the target model's feature set.

    FR-10 requires failing loudly here rather than silently degrading
    fidelity (e.g. dropping reference images past the model's max count).
    """


def resolve_duration_seconds(model_name: str, duration_seconds: float, allowed_seconds: set[str]) -> str:
    """Round to the nearest whole second and check it against a model's real allowed set.

    Each real model's duration field is a fixed enum of string seconds
    (confirmed against fal.ai's own OpenAPI schema), not a free continuous
    number, and the two live models don't share one valid range — failing
    loudly here (FR-10) avoids silently clamping to a value the caller
    never asked for, or wasting a paid API call on a value fal.ai would
    reject anyway.
    """
    duration = str(round(duration_seconds))
    if duration not in allowed_seconds:
        raise PayloadValidationError(
            f"{model_name} only supports duration_seconds in {sorted(allowed_seconds, key=int)}, got {duration_seconds}"
        )
    return duration


def resolve_duration_in_range(model_name: str, duration_seconds: float, min_seconds: int, max_seconds: int) -> int:
    """Round to the nearest whole second and check it against a model's real integer range.

    Some models (unlike Kling/Seedance's fixed string enums) take a free
    integer duration within a min/max range instead — same fail-loudly
    reasoning as resolve_duration_seconds, just a different real shape.
    """
    duration = round(duration_seconds)
    if not (min_seconds <= duration <= max_seconds):
        raise PayloadValidationError(
            f"{model_name} only supports duration_seconds between {min_seconds} and {max_seconds}, got {duration_seconds}"
        )
    return duration


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
