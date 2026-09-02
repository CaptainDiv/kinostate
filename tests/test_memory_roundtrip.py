"""Proves PRD Key User Flow #3: fresh-session recall.

Write brand REFERENCE + WARM data in one BrandMemory instance, then open a
brand-new instance against the same SQLite file (simulating a new process /
new session / different model call) and confirm the same facts come back
identically, with no re-entry of brand data.
"""

from __future__ import annotations

from kinostate.memory.tenant_store import BrandMemory


def test_fresh_session_recall(tmp_path):
    memory_dir = tmp_path / "brands"

    session_one = BrandMemory.open("acme", memory_dir=memory_dir)
    session_one.set_reference(
        "palette",
        {"palette_hex": ["#1DB954", "#191414"], "typography": "Inter", "tone_rules": ["confident", "warm"]},
    )
    session_one.set_entity(
        "character",
        "aria",
        {
            "kind": "character",
            "description": "Auburn hair, green jacket, brand mascot",
            "canonical_reference_asset": "sha256:deadbeef",
            "approval_status": "approved",
            "confidence": {},
        },
    )

    # Simulate a fresh session / different process by opening a brand-new
    # MemoryClient against the same underlying file.
    session_two = BrandMemory.open("acme", memory_dir=memory_dir)

    recalled_palette = session_two.get_reference("palette")
    recalled_entity = session_two.get_entity("character", "aria")

    assert recalled_palette["palette_hex"] == ["#1DB954", "#191414"]
    assert recalled_entity["description"] == "Auburn hair, green jacket, brand mascot"
    assert recalled_entity["canonical_reference_asset"] == "sha256:deadbeef"


def test_brand_isolation_by_file(tmp_path):
    memory_dir = tmp_path / "brands"

    acme = BrandMemory.open("acme", memory_dir=memory_dir)
    acme.set_entity("character", "aria", {"kind": "character", "description": "Acme's Aria"})

    globex = BrandMemory.open("globex", memory_dir=memory_dir)

    assert globex.get_entity("character", "aria") is None
    assert acme.db_path != globex.db_path
