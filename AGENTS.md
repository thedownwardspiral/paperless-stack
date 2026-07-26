# AGENTS.md

This file defines how automated coding agents should work in this repository.

## Repository Overview

- Project type: Docker Compose stack for Paperless-ngx with local AI services.
- Main entrypoint: `compose.yaml` (not tracked; `compose.yaml.example` is the tracked template)
- Core services: `paperless`, `postgres`, `valkey`, `gotenberg`, `tika`
- AI services: `llama-cpp` (LLM backend), `paperless-gpt` (vision-LLM OCR), `open-webui` (conversational UI), `paperless-tools` (OpenAPI tool server)
- Infrastructure: `traefik` (reverse proxy with TLS)
- Utility service: `dozzle`
- Commented-out alternatives in compose.yaml.example: `ollama`, `open-webui`, `llama-swap`

## Key Differences from Upstream

This is a fork of timothystewart6/paperless-stack. Notable changes:

- **llama.cpp** is the active LLM backend (replaces Ollama + Open WebUI)
- **Traefik** reverse proxy handles routing and TLS — services are not exposed on localhost ports
- **Native paperless-ngx AI** (v3+) points at llama-cpp's OpenAI-compatible API; `paperless-ai` was removed as redundant
- **valkey** is the broker (matches upstream v3 compose); the old `./redis/` directory is no longer referenced
- `compose.yaml` is gitignored (contains environment-specific hostnames); only `compose.yaml.example` is tracked
- `traefik/traefik.yml` and `traefik/traefik.dynamic.yml` are gitignored; example files are tracked
- Every service owns a top-level directory (`paperless/`, `postgres/`, `valkey/`, `traefik/`, …) holding its `.env` plus any config and persistent state

## Primary Goals for Agents

1. Keep the stack reliable and easy to run locally.
2. Make minimal, targeted changes that preserve existing behavior.
3. Avoid destructive operations on persistent data directories.
4. Update docs when behavior or setup changes.

## Guardrails

- Do not delete or reset contents under `*/data/`, `paperless/media/`, `paperless/export/`, or `paperless/consume/`.
- Do not commit secrets or real credentials. Only `.env.example` files are tracked; `.env` files are gitignored.
- `compose.yaml`, `traefik/traefik.yml`, and `traefik/traefik.dynamic.yml` are gitignored. Edit the `.example` versions instead.
- Do not delete `traefik/acme/acme.json` (issued certificates) or `traefik/certs/` (trusted CA bundle).
- Prefer editing only files directly related to the user request.
- Do not introduce unrelated refactors.

## Working Conventions

- Use `docker compose` (not legacy `docker-compose`) in commands and docs.
- Keep service names and container names consistent with `compose.yaml.example`.
- Preserve existing YAML style and comments where possible.
- If you add a new service, include:
  - clear comment header
  - restart policy
  - `env_file` usage
  - Traefik labels for routing
  - volume mapping for persistent state (when needed)

## Validation Checklist

After changes, run the smallest relevant checks first:

1. `docker compose config`
2. `docker compose ps` (if stack is running)
3. Service-specific logs when needed: `docker compose logs <service> --tail=100`

For documentation-only changes, skip runtime checks.

## Typical Local Operations

- Start stack: `docker compose up -d`
- Pull latest images: `docker compose pull`
- Recreate with updates: `docker compose up -d`
- Stop stack: `docker compose down`

## Documentation Rules

When changing setup/behavior, update `README.md` with:

- what changed
- required env/config updates
- user-visible impact (hostnames, prerequisites)

## Out of Scope Unless Requested

- Migrating from Docker Compose to Kubernetes
- Large directory restructures
- Swapping core service images/tags across the stack
- Security hardening beyond minimal best-practice edits

## Notes for AI-Feature Changes

- AI services are optional; maintain a working non-AI path. Native AI is off unless `PAPERLESS_AI_ENABLED` is set.
- Native paperless-ngx AI is configured entirely through `PAPERLESS_AI_*` in `paperless/.env`. Values set in the admin UI (Settings → Application Configuration) override the environment, so a setting that appears to be ignored is usually overridden in the database.
- `PAPERLESS_AI_LLM_MODEL` must match the model id llama-server reports at `GET /v1/models` (the full container path, e.g. `/app/models/Qwen3.5-9B-UD-Q6_K_XL.gguf`).
- `PAPERLESS_AI_LLM_CONTEXT_SIZE` must not exceed llama-cpp's per-slot context (`--ctx-size` / `--parallel`).
- llama-cpp is the active LLM backend. Model GGUF files go in `./llama-cpp/models/`.
- Keep model references consistent between `compose.yaml.example` and service `.env.example` files. The `LLM_MODEL` / `VISION_LLM_MODEL` strings in `paperless-gpt/.env` must match the GGUF filename mounted in `llama-cpp/models/`. (llama-server tolerates a mismatch when only one model is loaded, but logs mislabel the model.)
- Avoid assumptions about GPU availability; do not remove existing GPU config unless requested.

## Notes for the Conversational UI (`open-webui` + `paperless-tools`)

- Built-in Paperless chat retrieves at most 5 chunks (`CHAT_RETRIEVER_TOP_K`, hardcoded upstream, not a setting). Anything needing corpus-wide coverage — counts, "list every", cross-document comparison — must go through `paperless-tools`, not RAG.
- `paperless-tools` is the only place to add new capabilities for the chat UI. It is a FastAPI app; Open WebUI consumes its `/openapi.json`, and `operation_id` becomes the tool name the model sees.
- Tool docstrings and field descriptions are prompt surface, not just documentation — the model chooses tools from them. Edit them with that in mind.
- Keep the tool count small. A 9B model degrades quickly past a handful of tools.
- Tool responses must stay inside the model's context window; `MAX_CONTENT_CHARS` and `MAX_SEARCH_RESULTS` cap them. Raising them past llama-cpp's per-slot context will truncate conversations.
- `paperless-tools` is internal-only by design (no Traefik labels). Open WebUI reaches it over the `backend` network.
- Open WebUI settings are **PersistentConfig**: env vars seed the database on first boot and are ignored afterward, silently. A setting that will not change from `.env` must be changed in the admin UI. This has bitten both `OPENAI_API_BASE_URL` and `ENABLE_SIGNUP` on this stack, because `./open-webui/data/webui.db` predates the current configuration.
- To check what Open WebUI is actually configured with, read its config table directly rather than trusting `.env`:
  `sqlite3 open-webui/data/webui.db "select key, value from config where key like 'openai.%'"`
  Tool server connections live under the `tool_server.connections` key.
- Open WebUI relies on its own account auth; `traefik-auth@file` is intentionally **not** applied to it. Do not add basicAuth in front of it without also exempting `/ws`: WebSocket handshakes carry no cached Basic credentials, so socket.io 401s and retries forever, which the user sees as an endless browser auth prompt.
- Services with no authentication of their own (`dozzle`, `paperless-gpt`, and `llama-cpp` if its route is fixed) currently answer unauthenticated requests. `traefik-auth@file` is the right tool there — they are not SPAs and have no login of their own.
- When a container gains a second or third router, Traefik may serve 404 until it reloads the container's config; `docker compose restart traefik` settles it. Check `docker logs traefik_v3` with `log.level: DEBUG` in `traefik/traefik.yml` before assuming the labels are wrong — the "Configuration received" line prints every router Traefik actually built.
- Exports go to `./paperless/export/`. Formula-leading cells are escaped in `export_csv`; keep that if you touch the CSV writer.

## llama.cpp Batch-Tuning (live `compose.yaml`)

The live `compose.yaml` runs llama-cpp with a config tuned for batch PDF→CSV/XLSX throughput via paperless-gpt's image-mode OCR. Validated on this host (RTX 5060 Ti 16 GB, Ryzen 7 PRO 6850H 8C/16T, 22 GiB RAM); ~3.6× over the prior single-slot default (2 min → 33 s baseline). Do not regress these flags without re-benchmarking.

Active flags and why:

- `--ctx-size 32768 --parallel 4 --cont-batching` — 4 slots, 8192 ctx each. Per-slot ctx must match `OPENAI_CONTEXT_LENGTH` in `paperless-gpt/.env`.
- `--kv-unified --cache-idle-slots` — single dynamic KV pool so large docs can borrow from idle slots; idle slot state is saved to prompt cache.
- `--cache-type-k q8_0 --cache-type-v q8_0` — V-cache is q8_0, NOT q4_0. Workload contains PII and digit-level fidelity matters.
- `--batch-size 2048 --ubatch-size 512` — prefill-dominated PDF text benefits from larger ubatch.
- `-t 8 --threads-batch 8` — match physical cores; SMT siblings hurt on Zen 3+.
- `--sleep-idle-seconds -1` — disabled. (`0` is rejected by llama.cpp; `-1` is the disable sentinel.)
- `--jinja` — **required** for paperless-ngx native AI suggestions. They go through OpenAI tool calling (`tool_required=True`), and llama-server only emits `tool_calls` when the model's own chat template is used. Without it, llama-server returns a plain chat reply and paperless raises on "no tool call". Verified against this host: same request returns `reasoning_content` and no `tool_calls` when `--jinja` is absent.
- `--reasoning off` — **required alongside `--jinja`**. Qwen3.5's own template enables thinking, and `--jinja` activates it. Measured on this host: a single suggestion request ran past 4,500 reasoning tokens with no tool call in sight (well beyond `PAPERLESS_AI_LLM_REQUEST_TIMEOUT`). With reasoning off, the same request returns a tool call in ~22 s. Also removes thinking output from paperless-gpt's OCR responses.
- `--mmproj <projector>.gguf` — vision projector required because paperless-gpt uses image OCR mode. Filename is host-specific; match whatever projector sits in `llama-cpp/models/` (the live host uses `mmproj-F16.gguf`, `compose.yaml.example` ships a placeholder name).
- `cpuset: "0,2,4,6,8,10,12,14"` + `mem_limit: 14g` — pin physical cores, cap RAM so the LLM can't OOM the rest of the stack.

Companion setting in `paperless-gpt/.env`:

- `OCR_PROCESS_MODE: "image"` — rasterizes PDF pages and sends them to the vision LLM ("Parse PDF as image", hardcoded on).

Re-tuning guidance:

- Single-request low-latency chat: drop `--parallel` to 1, raise per-slot ctx, drop `--cache-idle-slots`.
- More concurrency: bump `--parallel` only after verifying VRAM headroom with `nvidia-smi` post-load.
- Different hardware: re-derive thread count from physical cores and ctx from VRAM budget. Do not blindly copy these flags.
