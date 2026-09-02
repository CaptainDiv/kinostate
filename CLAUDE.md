# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Kinostate is a decoupled, memory-native AI video agent. The
full product spec lives in `PRD.md` — read it for any question about *why* a layer exists
or what a requirement (`FR-n`) means. The core bet: brand memory ("what this brand looks
and sounds like") is stored locally and portably via the `sibyl-memory-client` SDK,
decoupled from whichever third-party video generation model actually renders the shot.

## Commands

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows; source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"       # re-run this after adding/removing files under src/

pytest                                              # full test suite
pytest tests/test_memory_roundtrip.py::test_fresh_session_recall  # single test

python scripts/demo.py        # end-to-end pipeline demo, prints the journal
uvicorn kinostate.api.main:app --reload             # run the API backend
```

There is no separate lint/build step configured yet.

## Architecture

Five layers under `src/kinostate/`, mirroring PRD.md §5. Each is its own subpackage;
higher layers depend on lower ones, never the reverse:

- **`memory/`** — `tenant_store.py` is the *only* module that imports `sibyl_memory_client`
  directly. Every other layer talks to brand memory through `BrandMemory`, so the rest of
  the codebase stays vendor-agnostic. One SQLite file per brand (`brand_id` maps to a
  filename via `config.brand_db_path`), so multi-tenancy is by file, not by row.
  - The SDK maps its own five tiers onto PRD's: `set_reference`/`get_reference` ≈
    REFERENCE, `set_entity`/`get_entity` ≈ WARM, `set_state`/`get_state` ≈ HOT,
    `write_event`/`read_events` ≈ COLD, `archive_entity`/`delete_entity` ≈ ARCHIVE.
  - **SDK quirk handled in `tenant_store._unwrap_body`**: `get_entity`/`get_state` return
    `{"body": <dict>, ...metadata}`, but `get_reference` returns `{"body": <JSON string>,
    ...}` — inconsistent dict-vs-string encoding across tiers. `_unwrap_body` normalizes
    all three to a plain dict; don't call the raw SDK client methods elsewhere.
  - **`get_entity` raises `NotFoundError` on a miss** (unlike `get_reference`/`get_state`,
    which return `None`) — `BrandMemory.get_entity` catches this and returns `None` so
    every getter has one consistent "missing" value. Preserve that if you touch it.

- **`compiler/`** — `canonical.py` defines the model-agnostic schema (`Entity`,
  `BrandReference`, `GenerationRequest`); nothing in this file may reference a vendor's API
  shape. `base_adapter.py` defines the `ModelAdapter` contract (`compile()` →
  `validate()`); `adapters/` holds one file per video model (Runway/Pika/Luma/Kling), each
  ~20 lines mapping canonical fields to that vendor's documented conditioning shape and
  declaring its own `max_reference_entities` cap (e.g. Pika caps at 1, so a multi-entity
  request must raise `PayloadValidationError`, not silently drop entities). Adding a new
  model means adding one adapter file and registering it in `adapters/__init__.py`'s
  `ADAPTERS` dict — nothing upstream changes.

- **`router/`** — `route_and_generate()` picks a model via `pick_model()` (highest
  per-entity, per-model confidence score stored on the WARM entity's `confidence` dict,
  honoring `RoutingPolicy.min_confidence_threshold`), or honors `GenerationRequest.
  model_override` for manual selection. `_call_model()` is a stub returning a `mock://`
  URI — no live model API calls happen anywhere in this codebase yet. Every call writes
  one COLD journal event via `memory.write_event`, win or lose.

- **`verification/`** — `run_qa()` is a heuristic stand-in for real brand-consistency
  checking (palette-presence + entity-approval-status checks, not actual image analysis —
  see PRD's open question on QA method). It journals the pass/fail + reasoning linked to
  the generation, then updates the entity's per-model confidence via an exponential moving
  average (`CONFIDENCE_LEARNING_RATE`), which is what `router.pick_model` reads next time.

- **`economic/`** — `base_x402.py` (Base/x402 metering + provenance) and
  `virtuals_acp.py` (Virtuals ACP provider registration + access grants) are fully stubbed;
  every function returns a fixed mock value tagged `"mock": True`. No live credentials are
  configured. Wire real integrations in here without changing callers.

- **`api/main.py`** — FastAPI backend exposing brand onboarding, entity creation,
  generation requests, and review, wired straight to the layers above. No frontend UI
  exists yet.

## Working conventions specific to this repo

- Never import `sibyl_memory_client` outside `memory/tenant_store.py`.
- When adding a new video model adapter, subclass `ModelAdapter`, set `name` and
  `max_reference_entities`, implement `compile()`, and register it in `ADAPTERS` — follow
  the existing adapters in `compiler/adapters/` as the template.
- Functions/modules that are intentionally mocked (no live external account) are commented
  as such and return values containing a `"mock": True` marker or a `mock://` URI —
  preserve that marker when extending them so it stays obvious what isn't real yet.
- `PRD.md`'s `FR-n` requirement IDs are referenced in code comments throughout; when
  implementing a requirement, cite its ID the same way so the mapping stays traceable.

# Development Rules & Architecture Control
- **Architectural Approval:** Never create core system files, introduce new dependencies, or alter database schemas without presenting options first.
- **Decision Format:** For any system design choice, provide 2–3 options with plain-English pros, cons, complexity rating (Low/Medium/High), and cost implications. Wait for user selection before writing code.
- **Explain Simply:** Avoid unexplained jargon. Break down system choices using clear analogies.