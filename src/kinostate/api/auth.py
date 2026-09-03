"""Per-brand API key issuance and verification.

Each brand gets its own key at onboarding, stored (hashed) in that brand's
own REFERENCE tier under "_api_key" — reusing the existing multi-tenant-
by-file isolation (FR-1/FR-2) rather than a separate user/session system.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import HTTPException

from kinostate.memory.tenant_store import BrandMemory

_API_KEY_REFERENCE_KEY = "_api_key"


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def issue_api_key(memory: BrandMemory) -> str | None:
    """Generate and store a new API key for this brand, unless one already exists.

    Returns the raw key (shown to the caller exactly once) or None if this
    brand was already issued one — re-onboarding to update brand law
    shouldn't silently invalidate a live key.
    """
    if memory.get_reference(_API_KEY_REFERENCE_KEY) is not None:
        return None
    key = generate_api_key()
    memory.set_reference(_API_KEY_REFERENCE_KEY, {"key_hash": hash_api_key(key)})
    return key


def verify_api_key(memory: BrandMemory, presented_key: str | None) -> None:
    record = memory.get_reference(_API_KEY_REFERENCE_KEY)
    if record is None:
        raise HTTPException(status_code=401, detail="brand has no API key on file")
    if presented_key is None:
        raise HTTPException(status_code=401, detail="missing X-API-Key header")
    if not hmac.compare_digest(hash_api_key(presented_key), record["key_hash"]):
        raise HTTPException(status_code=401, detail="invalid API key")
