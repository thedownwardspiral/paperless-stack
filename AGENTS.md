# AGENTS.md

This file defines how automated coding agents should work in this repository.

## Repository Overview

- Project type: Docker Compose stack for Paperless-ngx with local AI services.
- Main entrypoint: `compose.yaml` (not tracked; `compose.yaml.example` is the tracked template)
- Core services: `paperless`, `postgres`, `redis`, `gotenberg`, `tika`
- AI services: `llama-cpp`, `paperless-ai`, `paperless-gpt`
- Infrastructure: `traefik` (reverse proxy with TLS)
- Utility service: `dozzle`
- Commented-out alternatives in compose.yaml.example: `ollama`, `open-webui`, `llama-swap`

## Key Differences from Upstream

This is a fork of timothystewart6/paperless-stack. Notable changes:

- **llama.cpp** is the active LLM backend (replaces Ollama + Open WebUI)
- **Traefik** reverse proxy handles routing and TLS — services are not exposed on localhost ports
- **paperless-ai** uses the `custom` AI provider pointing to llama-cpp's OpenAI-compatible API
- `compose.yaml` is gitignored (contains environment-specific hostnames); only `compose.yaml.example` is tracked
- `traefik.yml` and `traefik.dynamic.yml` are gitignored; example files are tracked

## Primary Goals for Agents

1. Keep the stack reliable and easy to run locally.
2. Make minimal, targeted changes that preserve existing behavior.
3. Avoid destructive operations on persistent data directories.
4. Update docs when behavior or setup changes.

## Guardrails

- Do not delete or reset contents under `*/data/`, `paperless/media/`, `paperless/export/`, or `paperless/consume/`.
- Do not commit secrets or real credentials. Only `.env.example` files are tracked; `.env` files are gitignored.
- `compose.yaml`, `traefik.yml`, and `traefik.dynamic.yml` are gitignored. Edit the `.example` versions instead.
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

- AI services are optional; maintain a working non-AI path.
- llama-cpp is the active LLM backend. Model GGUF files go in `./llama-cpp/models/`.
- Keep model references consistent between `compose.yaml.example` and service `.env.example` files.
- Avoid assumptions about GPU availability; do not remove existing GPU config unless requested.
