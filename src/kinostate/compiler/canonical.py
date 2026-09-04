"""Canonical, model-agnostic entity schema (FR-8).

Nothing in this module may reference a specific vendor's API shape. Model
adapters translate *from* these types *to* a vendor payload — never the
other way around.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BrandReference:
    """REFERENCE tier: brand law (FR-2)."""

    palette_hex: list[str]
    typography: str | None = None
    tone_rules: list[str] = field(default_factory=list)
    forbidden_content: list[str] = field(default_factory=list)


@dataclass
class Entity:
    """WARM tier: one character/product/location (FR-2)."""

    kind: str  # "character" | "product" | "location"
    name: str
    description: str
    canonical_reference_asset: str | None = None  # hash/URI of the primary/frontal approved reference image
    additional_reference_images: list[str] = field(default_factory=list)  # extra angles/poses of the same entity
    forbidden_traits: list[str] = field(default_factory=list)
    approval_status: str = "pending"  # "pending" | "approved" | "rejected"


@dataclass
class GenerationRequest:
    """A brand's request for a shot, independent of which model serves it."""

    brand_id: str
    entities: list[Entity]
    style_prompt: str
    duration_seconds: float = 4.0
    resolution: str = "1080p"
    model_override: str | None = None  # FR-13: manual override of routing
