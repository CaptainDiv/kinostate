"""Per-brand wrapper around sibyl_memory_client.MemoryClient.

This is the only module in kinostate that imports sibyl_memory_client
directly. Every other layer (compiler, router, verification, economic, api)
talks to brand memory through BrandMemory, so the rest of the codebase never
depends on the SDK's shape directly (NFR: model/vendor-agnostic core).

Maps PRD's five tiers onto the SDK's five tiers:
    REFERENCE -> set_reference / get_reference   (brand law: palette, tone)
    WARM      -> set_entity / get_entity          (characters, products)
    HOT       -> set_state / get_state             (active campaign/session)
    COLD      -> write_event / read_events         (append-only journal)
    ARCHIVE   -> archive_entity / delete_entity
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sibyl_memory_client import MemoryClient, NotFoundError

from kinostate.config import brand_db_path


def _unwrap_body(record: dict[str, Any] | None) -> dict[str, Any] | None:
    """Unwrap the SDK's {"body": ..., "metadata": ..., "updated_at": ...}
    envelope down to just the body dict.

    The SDK is inconsistent about whether `body` comes back as a dict
    (entities, state) or as a JSON-encoded string (reference) — normalize
    both here so every BrandMemory getter always returns a plain dict.
    """
    if record is None:
        return None
    body = record.get("body", record)
    if isinstance(body, str):
        body = json.loads(body)
    return body


class BrandMemory:
    """One brand's isolated memory tenant (FR-1, FR-2)."""

    def __init__(self, brand_id: str, memory_dir: Path | None = None):
        self.brand_id = brand_id
        self.db_path = brand_db_path(brand_id, memory_dir)
        self._client = MemoryClient.local(str(self.db_path))

    @classmethod
    def open(cls, brand_id: str, memory_dir: Path | None = None) -> "BrandMemory":
        """Open (or create) a brand's memory tenant.

        Calling this again for the same brand_id — even from a brand-new
        process — reconnects to the same SQLite file and recalls the same
        state. This is what "fresh-session recall" (PRD Key User Flow #3)
        relies on.
        """
        return cls(brand_id, memory_dir)

    # ---- REFERENCE tier: brand law (palette, typography, tone) ----------
    def set_reference(self, key: str, body: dict[str, Any]) -> None:
        self._client.set_reference(key, body)

    def get_reference(self, key: str) -> dict[str, Any] | None:
        return _unwrap_body(self._client.get_reference(key))

    # ---- WARM tier: entities (characters/products/locations) ------------
    def set_entity(self, kind: str, name: str, body: dict[str, Any]) -> None:
        self._client.set_entity(kind, name, body)

    def get_entity(self, kind: str, name: str) -> dict[str, Any] | None:
        """Return the entity body, or None if it doesn't exist.

        The underlying SDK raises NotFoundError rather than returning None
        for a missing entity (unlike get_reference/get_state); normalized
        here so every BrandMemory getter has one consistent "missing" value.
        """
        try:
            record = self._client.get_entity(kind, name)
        except NotFoundError:
            return None
        return _unwrap_body(record)

    def search_entities(self, query: str) -> list[dict[str, Any]]:
        return list(self._client.search_entities(query))

    def archive_entity(self, kind: str, name: str) -> None:
        self._client.archive_entity(kind, name)

    def delete_entity(self, kind: str, name: str) -> None:
        self._client.delete_entity(kind, name)

    # ---- HOT tier: current campaign/session state ------------------------
    def set_state(self, key: str, body: dict[str, Any]) -> None:
        self._client.set_state(key, body)

    def get_state(self, key: str) -> dict[str, Any] | None:
        return _unwrap_body(self._client.get_state(key))

    # ---- COLD tier: append-only generation journal (FR-14, FR-16) --------
    def write_event(self, **event: Any) -> None:
        self._client.write_event(**event)

    def read_events(self, **filters: Any) -> list[dict[str, Any]]:
        return self._client.read_events(**filters)

    # ---- Portability (FR-4): export/import is just the file itself -------
    def export_path(self) -> Path:
        """Brand memory is already a single portable file; return it."""
        return self.db_path
