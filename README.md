# Kinostate

A decoupled, memory-native AI video agent. Brand memory ("what this brand
looks and sounds like") is stored locally and portably via
[Sibyl-Memory](https://github.com/Sibyl-Labs/Sibyl-Memory), decoupled from
whichever video generation model (Runway, Pika, Luma, Kling, ...) is used to
render it. See [`PRD.md`](./PRD.md) for the full product spec.

## Architecture

Five layers, mirroring `PRD.md` §5:

| Layer | Module | Status |
|---|---|---|
| Memory | `kinostate.memory` | Real — wraps `sibyl_memory_client.MemoryClient`, one SQLite file per brand |
| Compiler | `kinostate.compiler` | Real canonical schema + adapter contract; 4 stub adapters (Runway/Pika/Luma/Kling) that produce correctly-shaped mock payloads |
| Router | `kinostate.router` | Real selection/journaling logic; generation calls are mocked (no live model API calls) |
| Verification | `kinostate.verification` | Heuristic QA stand-in (not a real vision-model check yet — see PRD open questions) |
| Economic (Base + Virtuals) | `kinostate.economic` | Fully stubbed — no live Base/x402 or Virtuals ACP credentials configured |
| API | `kinostate.api` | FastAPI backend covering brand onboarding, generation requests, and review (no frontend UI yet) |

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # optional — defaults work out of the box
```

Core dependency: [`sibyl-memory-client`](https://pypi.org/project/sibyl-memory-client/)
(real PyPI package, MIT license). Its free tier caps local memory at 5 MB and
gates the self-learning/linter add-ons behind a paid plan — irrelevant for
this scaffold, but worth knowing before scaling up brand memory size.

## Run the demo

```bash
python scripts/demo.py
```

Onboards a brand, defines a character, generates one shot on Runway, then —
from a **brand-new** in-process `BrandMemory` instance, simulating a fresh
session — generates another shot of the same character on Luma with no
brand data re-entered. Prints the resulting journal, demonstrating PRD Key
User Flow #3 (fresh-session recall across a model switch).

## Run the tests

```bash
pytest
```

`tests/test_memory_roundtrip.py` proves the same fresh-session-recall
property directly against the real SDK, plus per-brand file isolation
(FR-1).

## Run the API

```bash
uvicorn kinostate.api.main:app --reload
```

```bash
curl -X POST localhost:8000/brands -H "Content-Type: application/json" \
  -d '{"brand_id": "acme", "palette_hex": ["#1DB954", "#191414"]}'

curl -X POST localhost:8000/brands/acme/entities -H "Content-Type: application/json" \
  -d '{"kind": "character", "name": "aria", "description": "Brand mascot"}'

curl -X POST localhost:8000/generate -H "Content-Type: application/json" \
  -d '{"brand_id": "acme", "entity_names": ["aria"], "style_prompt": "Aria waving at the camera"}'
```

## What's stubbed vs. real

Everything that depends on an external account or credential (video model
APIs, Base/x402, Virtuals ACP) is mocked with clearly-labeled placeholder
return values (`"mock": True` / `mock://` URIs). Everything else — memory
persistence, the canonical schema, the adapter contract and validation,
routing/confidence logic, and journaling — runs for real against the
installed `sibyl-memory-client` SDK.
