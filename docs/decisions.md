# Architecture Decision Records

Five key decisions made during the build of the Healf Product Intelligence Agent.

---

## ADR-001 — SQLite over PostgreSQL

**Status:** Accepted

**Context:** The agent needs to persist product data, review corpora, embedding vectors, HITL queue entries, and eval run results. A vector database or hosted Postgres instance would offer more scaling headroom, but the primary deployment target is a local or single-server environment where a reviewer should be able to clone the repo and `uv sync` without any infrastructure setup.

**Decision:** Use SQLite with a single `corpus.sqlite` file committed to the repository. Vector kNN is done in Python (cosine similarity over numpy arrays loaded from `BLOB` columns), not via a database extension.

**Consequences:**
- Pro: zero infrastructure; corpus ships in the repo (1.29 MB, 150 products)
- Pro: `sqlite3` is stdlib; no extra dependency
- Pro: `git clone` + `uv sync` is the entire setup story
- Con: kNN performance degrades past ~50k rows (full table scan)
- Upgrade path: swap `Storage.knn()` for `pgvector` or `ChromaDB` when corpus exceeds that threshold; the `Storage` interface isolates callers from this change

---

## ADR-002 — `fastmcp-slim[server]` over bare `fastmcp`

**Status:** Accepted

**Context:** The MCP surface requires `from fastmcp import FastMCP`. PyPI has two packages in this ecosystem: `fastmcp` (legacy 0.x, no `__init__.py` in newer slim distributions) and `fastmcp-slim` (the actively maintained variant). Specifying `fastmcp>=0.2.0` in `pyproject.toml` caused `uv` to install `fastmcp 0.2.0` (legacy) alongside `fastmcp-slim 3.3.0`, corrupting the `fastmcp/` package directory — `from fastmcp import FastMCP` failed with `ImportError`.

**Decision:** Pin to `fastmcp-slim[server]>=3.3.0`. The `[server]` extra is required for the `FastMCP` class; without it, the import raises "FastMCP server support is not installed." The `>=3.3.0` lower bound is required because `mcp_server.py:tool_names()` reads `mcp._tools` (a private dict added in 3.3).

**Consequences:**
- Pro: unambiguous dependency; `uv sync` installs exactly the right package
- Con: `_tools` introspection is private API — if fastmcp-slim changes the internal dict name in a future release, `tool_names()` will break silently
- Mitigation: the `test_mcp.py` test suite calls `tool_names()` on every CI run, so a breakage would be caught before deployment

---

## ADR-003 — JSON-LD as primary ingestion path

**Status:** Accepted

**Context:** Healf uses a Next.js App Router storefront, not a vanilla Shopify JSON endpoint. Three data paths were discovered during development: (1) `<script type="application/ld+json">` blocks pre-rendered in the server-side HTML, (2) RSC flight payloads (`__next_f.push`) carrying metafield JSON, and (3) Playwright browser automation as a fallback.

**Decision:** JSON-LD is the primary ingestion path (`ingest.py`). RSC payloads are parsed as a secondary source for metafields not present in JSON-LD. Playwright is a tertiary fallback triggered only when httpx returns a non-200 or the JSON-LD block is absent.

**Consequences:**
- Pro: JSON-LD is stable, fast (no JS execution), and carries the full `Product` schema including price, images, rating, and review count
- Pro: RSC payloads add metafields (ingredients, claims) that are not in the JSON-LD schema
- Con: if Healf removes server-side JSON-LD pre-rendering (e.g. moves to client-side hydration only), the primary path breaks; Playwright fallback would absorb the impact
- Con: RSC payload parsing is brittle — the minified format varies by Next.js version

---

## ADR-004 — Three surfaces (Streamlit / MCP / webhook)

**Status:** Accepted

**Context:** The assignment brief describes the role as "AI agent as functional colleague." A single-surface demo (Streamlit only) demonstrates conversational use but not workflow integration. The brief also mentions automation and catalog operations, which map naturally to programmatic surfaces.

**Decision:** Expose the same agent core through three surfaces with different reach:
1. **Streamlit** — direct human interaction; chat + HITL review queue
2. **MCP server** — Claude Desktop / Claude Code integration; the agent becomes a tool Claude can call mid-conversation
3. **FastAPI webhook → n8n** — automation; a scheduled workflow can audit the full catalog without human initiation

**Consequences:**
- Pro: demonstrates "AI as colleague" at three levels of autonomy (human-in-loop → AI-assisted → AI-autonomous)
- Pro: the same `healf_agent/` core is unchanged; surfaces are thin adapters
- Con: three surfaces means three test suites, three boot commands, and three points of failure to document
- Con: the n8n JSON workflow requires a running n8n instance that reviewers may not have — mitigated by the webhook being independently testable without n8n

---

## ADR-005 — Tool-use loop over monolithic prompt

**Status:** Accepted

**Context:** The agent could be implemented as a single large prompt instructed to answer questions about product listings using its context window. Alternatively, the Anthropic SDK's native tool-use loop lets Claude decide which tools to invoke per question, with each tool fetching real data at query time.

**Decision:** Use the Anthropic SDK tool-use loop. Claude receives a SYSTEM_PROMPT describing the agent's role and the 11 available tools; it decides which tools to call per turn based on the user's question. The loop runs until Claude returns a `stop_reason == "end_turn"` with no pending tool calls.

**Consequences:**
- Pro: factual queries (`check_field`) invoke only one tool; open-ended analysis chains 4–5 tools automatically — no prompt engineering required per query type
- Pro: tool traces are visible in the Streamlit UI, making the agent's reasoning transparent and debuggable
- Pro: tool schemas enforce typed inputs/outputs, catching errors at the boundary rather than inside the prompt
- Con: multi-tool chains consume more tokens per turn than a monolithic prompt for simple queries
- Con: tool-use loop requires the Anthropic SDK's `messages.create` with `tools=` parameter — not portable to non-Anthropic LLMs without schema translation
