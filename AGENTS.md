# AGENTS.md

This file defines how automated coding agents should work in this repository.

## Repository Overview

- Project type: Docker Compose stack for Paperless-ngx and optional local AI services.
- Main entrypoint: `compose.yaml`
- Core services: `paperless`, `postgres`, `redis`, `gotenberg`, `tika`
- Optional AI services: `ollama`, `open-webui`, `paperless-ai`, `paperless-gpt`
- Utility service: `dozzle`

## Primary Goals for Agents

1. Keep the stack reliable and easy to run locally.
2. Make minimal, targeted changes that preserve existing behavior.
3. Avoid destructive operations on persistent data directories.
4. Update docs when behavior or setup changes.

## Guardrails

- Do not delete or reset contents under `*/data/`, `paperless/media/`, `paperless/export/`, or `paperless/consume/`.
- Do not commit secrets or real credentials to `.env` files.
- Prefer editing only files directly related to the user request.
- Do not introduce unrelated refactors.
- Do not change published port mappings unless explicitly requested.

## Working Conventions

- Use `docker compose` (not legacy `docker-compose`) in commands and docs.
- Keep service names and container names consistent with `compose.yaml`.
- Preserve existing YAML style and comments where possible.
- If you add a new service, include:
  - clear comment header
  - restart policy
  - `env_file` usage where appropriate
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
- user-visible impact (ports, URLs, prerequisites)

## Out of Scope Unless Requested

- Migrating from Docker Compose to Kubernetes
- Large directory restructures
- Swapping core service images/tags across the stack
- Security hardening beyond minimal best-practice edits

## Notes for AI-Feature Changes

- AI services are optional; maintain a working non-AI path.
- Keep model references consistent with service env docs.
- Avoid assumptions about GPU availability; do not remove existing GPU config unless requested.
