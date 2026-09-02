# Product Requirements Document
## Kinostate — A Decoupled, Memory-Native AI Video Agent

| | |
|---|---|
| **Status** | Draft v1.0 |
| **Owner** | [Team / Founder name] |
| **Last updated** | September 2, 2026 |
| **Core dependency** | Sibyl-Memory SDK (SQLite + FTS5, local-first, multi-tenant) |
| **Ecosystem integrations** | Base (x402 payments, on-chain provenance) · Virtuals Protocol (ACP, GAME) |

---

## 1. Executive Summary

Brands generating video content with AI models (Runway, Pika, Luma, Kling, etc.) lose visual and stylistic consistency between shots — characters change appearance, colors shift, tone drifts. Existing platforms that address this (LTX Studio, InVideo) solve it by locking brand data inside a single proprietary system: switch models, lose your brand's "memory."

**Kinostate** decouples the memory of "what this brand looks and sounds like" from the act of generating video. Brand memory lives in a local, SQLite-backed, brand-owned file (powered by Sibyl-Memory) and can be pointed at any current or future video generation model. The product's core bet: **the memory is the asset, not the video generator** — and that asset can be made provable (Base) and monetizable to other AI agents (Virtuals Protocol), not just useful inside one app.

## 2. Problem Statement

- **Context drift:** Character faces, brand palettes, and stylistic tone shift between shots and between sessions because there is no persistent, structured source of truth feeding each generation call.
- **Vendor lock-in:** Platforms that do solve consistency (LTX Studio's "Elements," InVideo) store that consistency data inside their own systems. A brand cannot take its "Aria has auburn hair, uses palette #1DB954" knowledge and point it at a different or newer model without starting over.
- **No accountability or provenance:** There is currently no verifiable record of *which* brand-approved state produced a given piece of content, making licensing, audit, and dispute resolution hard.
- **No monetization path for brand knowledge:** A brand's carefully curated style/character data is a dead asset — it only has value inside the one tool it was built in.

## 3. Goals

| Goal | Description |
|---|---|
| G1 | Eliminate context drift by making a single canonical brand-memory record the source of truth for every model call |
| G2 | Make brand memory portable — a single file the brand owns, can move, back up, or hand to any compliant tool |
| G3 | Make the system model-agnostic by design — adding a new video model should require no change to how memory is stored |
| G4 | Make brand-consistency claims verifiable, not just asserted (via journaled QA + on-chain provenance) |
| G5 | Make brand memory an economic asset other agents can pay to use, not just an internal feature |

### Non-Goals (v1)
- Not building a proprietary video generation model — Kinostate is a router/compiler/memory layer over third-party models.
- Not attempting full semantic/visual similarity search (vector embeddings) as a v1 requirement — brand memory is structured, lexical, fact-based data, which FTS5 is well suited for; a hybrid embedding layer is an explicit future consideration, not a launch blocker.
- Not building a general-purpose video editor (trimming, timeline, effects) — scope is generation + consistency, not post-production.

## 4. Target Users

| Persona | Description | Primary need |
|---|---|---|
| **Brand/marketing team** | In-house team producing recurring branded video content (ads, social, product) | Consistent characters/style across campaigns and across whichever model is cheapest/best that week |
| **Agency producing for multiple clients** | Manages several brand identities simultaneously | Strict per-client memory isolation (multi-tenant), fast onboarding of new brand kits |
| **Independent creator/studio** | Builds a recurring character or IP across content | Portable identity data that survives platform changes |
| **Third-party AI agents (via Virtuals ACP)** | Other autonomous agents (copywriting, ad-targeting, social-posting agents) | Read access to a brand's canonical voice/style data to stay on-brand in their own outputs |

## 5. Product Overview

Kinostate has five layers:

1. **Memory Layer (Sibyl-Memory)** — the brand's SQLite-backed, five-tier memory store (REFERENCE, WARM, HOT, COLD, ARCHIVE). Local-first, one file per brand tenant.
2. **Compiler Layer** — translates canonical brand entities (characters, palettes, style rules) into each target model's native conditioning format (Runway References, Pika CREF, Kling Elements, Luma Character Seeds).
3. **Router/Generation Layer** — selects which model to call per job, based on cost, brand-specific historical consistency confidence, and current availability; issues the compiled call; captures the output.
4. **Verification Layer** — automated brand-QA check on every output (palette match, character match against canonical reference), written back into the memory journal; feeds the router's future decisions.
5. **Economic Layer (Base + Virtuals)** — meters generation cost via x402 on Base, anchors provenance hashes on-chain, and exposes the brand's memory as a paid, scoped resource other agents can query via Virtuals' Agent Commerce Protocol (ACP).

## 6. Functional Requirements

### 6.1 Memory Layer

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | System shall store each brand's memory as an isolated SQLite database file (multi-tenant by file, not by row) | P0 |
| FR-2 | System shall implement the five-tier schema: REFERENCE (brand law: palette, typography, tone), WARM (entities: characters/products/locations, with per-model confidence scores), HOT (live campaign/session state), COLD (append-only generation journal), ARCHIVE (retired/superseded records) | P0 |
| FR-3 | System shall support FTS5 full-text queries across WARM and COLD tiers (e.g., "all Aria generations on Runway that failed palette check") | P0 |
| FR-4 | System shall allow export/import of the full memory file with no server dependency | P0 |
| FR-5 | System shall support brand-held encryption at rest for the memory file | P1 |
| FR-6 | System shall support versioned snapshots of memory state, diffable across campaigns | P1 |
| FR-7 | System shall expose the memory store via an MCP server per brand, so external MCP-compatible agents can query it directly | P1 |

### 6.2 Compiler Layer

| ID | Requirement | Priority |
|---|---|---|
| FR-8 | System shall define a canonical entity schema independent of any specific video model | P0 |
| FR-9 | System shall provide a per-model adapter that maps canonical entity data to that model's native conditioning payload | P0 |
| FR-10 | System shall validate a compiled payload against the target model's supported feature set before sending the request (e.g., max reference image count) and fail with a clear error rather than silently degrading fidelity | P0 |
| FR-11 | Adding support for a new video model shall require only a new adapter, with no change to the canonical schema or upstream product logic | P0 |

### 6.3 Router/Generation Layer

| ID | Requirement | Priority |
|---|---|---|
| FR-12 | System shall select a target model per generation job based on configurable priority (cost, historical confidence score, availability) | P0 |
| FR-13 | System shall allow manual override of model selection per job | P0 |
| FR-14 | System shall log every generation event (prompt, compiled payload, model, seed, cost, output asset reference) to the COLD journal | P0 |

### 6.4 Verification Layer

| ID | Requirement | Priority |
|---|---|---|
| FR-15 | System shall run an automated brand-consistency check (palette match against REFERENCE; character match against canonical reference asset) on every generated output | P0 |
| FR-16 | System shall write the check result (pass/fail + reasoning) into the COLD journal, linked to the generation event | P0 |
| FR-17 | System shall update a per-entity, per-model confidence score based on rolling QA outcomes | P0 |
| FR-18 | System shall deprioritize a model for a given entity automatically when its confidence score drops below a configurable threshold | P1 |

### 6.5 Economic Layer (Base)

| ID | Requirement | Priority |
|---|---|---|
| FR-19 | System shall meter each generation call via x402 micropayment on Base, denominated in USDC | P1 |
| FR-20 | System shall record per-call cost in the COLD journal to support cost/quality routing decisions | P1 |
| FR-21 | System shall anchor a hash of (output asset + the exact memory state/compiled payload that produced it) on Base for provenance verification | P1 |
| FR-22 | System shall enforce a configurable spending policy (budget ceiling) stored in HOT state before authorizing payment | P2 |

### 6.6 Economic Layer (Virtuals Protocol)

| ID | Requirement | Priority |
|---|---|---|
| FR-23 | System shall register the video agent as an ACP Provider with a defined job schema (brand_id, entity_ids, model_preference, resolution, duration, style, budget_ceiling) | P1 |
| FR-24 | System shall support scoped, paid, read-only access grants to a brand's REFERENCE/WARM tiers for other ACP agents, settled via ACP escrow | P2 |
| FR-25 | System shall support an independent ACP Evaluator role gating payment release on brand-consistency verification | P2 |

### 6.7 Brand Console (UI)

| ID | Requirement | Priority |
|---|---|---|
| FR-26 | Brand onboarding flow to define REFERENCE data (palette, typography, tone rules) and initial WARM entities (characters, products) | P0 |
| FR-27 | Generation request flow: select entity/entities, style parameters, target model (or auto-route), and submit | P0 |
| FR-28 | Review/approval flow: brand approves or rejects generated output, updating entity approval status and confidence data | P0 |
| FR-29 | Memory browser: searchable view (FTS5-backed) into journal history, entity records, and confidence scores | P1 |
| FR-30 | Provenance viewer: show on-chain verification status for a given asset | P2 |

## 7. Non-Functional Requirements

- **Portability:** Brand memory must remain a self-contained file usable with zero dependency on this product's servers.
- **Data ownership:** No brand memory content is stored on any centralized server the brand does not control, by default.
- **Model-agnosticism:** Core memory schema must never reference a specific vendor's API shape.
- **Auditability:** Every generation decision must be traceable to a journal entry explaining what was sent, to which model, and why.
- **Latency:** Memory reads/writes (SQLite/FTS5, local) should not be a bottleneck relative to video generation API latency (seconds-to-minutes).

## 8. Key User Flows

1. **Brand onboarding** — Brand defines palette, typography, tone, and first characters/products → written to REFERENCE and WARM tiers.
2. **Generation** — Brand requests a shot of "Aria" in a target style → compiler pulls canonical entity → router selects model → compiled payload sent → output generated → QA check run → journal updated → confidence score updated.
3. **Fresh-session recall (proof-of-memory)** — In an entirely new session, request another shot of "Aria," routed to a *different* model → compiler reconstitutes the same canonical identity for the new model's conditioning format → visual consistency holds without any re-entry of brand facts.
4. **Model switch / addition** — A new video model is added via one adapter → no change required to existing brand memory or canonical entities.
5. **Cross-agent memory monetization (Virtuals)** — A third-party ACP agent requests scoped access to the brand's voice/style data → negotiation and escrow via ACP → agent generates on-brand copy or content elsewhere → brand is paid.

## 9. Success Metrics

| Metric | Definition |
|---|---|
| Consistency pass rate | % of generations passing automated brand-QA check, per entity, per model |
| Drift incidents avoided | Count of cases where the compiler blocked a payload that would have violated brand rules |
| Memory portability events | Number of successful memory exports/imports across models or sessions |
| Cost-per-consistent-shot | Generation cost adjusted for QA pass rate, per model, over time (should trend down as router learns) |
| Cross-agent memory revenue | USDC earned by brands from other agents accessing their memory via ACP |

## 10. Data Model Summary (Five-Tier Schema)

- **REFERENCE** — brand-level constants: palette (hex list), typography, tone-of-voice rules, forbidden content list. Low write frequency, high read frequency.
- **WARM** — one row per entity (character/product/location): description, canonical reference asset hash, forbidden traits, per-model confidence scores, approval status.
- **HOT** — current campaign/session state: active entity set, preferred model, remaining budget.
- **COLD** — append-only journal: every generation event, its compiled payload, cost, output hash, and QA result.
- **ARCHIVE** — superseded/retired entity versions and old campaign snapshots, retained for audit and diffing.

## 11. Dependencies

- **Sibyl-Memory SDK** (`sibyl-memory-client`, SQLite + FTS5, local-first, multi-tenant) — core memory substrate.
- **Video generation model APIs** — Runway (Gen-4 References), Pika (CREF), Luma (Character Seeds), Kling (Elements), or an aggregator (fal.ai, WaveSpeed) as an abstraction layer.
- **Base / x402** — payment metering and on-chain provenance anchoring.
- **Virtuals Protocol** — GAME framework (agent runtime) and ACP (Agent Commerce Protocol) for provider registration, cross-agent memory licensing, and evaluator-gated escrow.
- **MCP** — for exposing brand memory to external agent tooling.

## 12. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Video model APIs change conditioning formats frequently | Isolate all model-specific logic in the compiler's adapter layer; canonical schema stays stable |
| FTS5/lexical search insufficient for some future "find visually similar" use cases | Treat as an optional, additive hybrid-embedding index layered on top, not a replacement for the lexical core |
| Cross-agent memory monetization (Virtuals) exposes sensitive brand data broadly | Scope access grants narrowly (specific tiers/entities), require explicit brand opt-in per grant, log all access in the journal |
| On-chain provenance costs scale with generation volume | Batch-anchor hashes rather than one transaction per asset, if volume requires it |
| Brand trust in automated QA accuracy | Make QA reasoning visible/auditable in the journal; allow brand override of confidence scores |

## 13. Open Questions

- What is the default automated QA method (vision-model check vs. simpler heuristic checks) and how is its own accuracy validated?
- What granularity of access control is needed for cross-agent memory licensing (per-tier, per-entity, per-field)?
- Should memory encryption be mandatory by default, or opt-in?
- What is the pricing model for x402-metered generation passed on to the brand (markup vs. pass-through)?
