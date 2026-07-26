# Paperless Stack

Docker Compose stack for running Paperless-ngx with local AI capabilities, using llama.cpp for LLM inference and Traefik as a reverse proxy.

This is a fork of [timothystewart6/paperless-stack](https://github.com/timothystewart6/paperless-stack) with the following changes:

- **llama.cpp** replaces Ollama and Open WebUI — runs GGUF models directly via llama-server with CUDA support
- **Traefik** reverse proxy added for TLS termination and routing (services are not exposed on localhost ports)
- **Paperless-ngx native AI** (v3+) points at llama-cpp's OpenAI-compatible API — `paperless-ai` was removed as redundant
- **Valkey** replaces Redis as the broker, matching upstream's v3 compose files
- Ollama, Open WebUI, and llama-swap service definitions are kept commented out as alternatives in `compose.yaml.example`

## Quick Start

1. **Clone and configure**

   ```bash
   git clone <your-fork-url>
   cd paperless-stack
   ```

2. **Create environment and config files from examples**

   ```bash
   # Copy all .env.example files to .env
   for f in $(find . -name '.env.example'); do cp "$f" "${f%.example}"; done

   # Copy compose and traefik configs
   cp compose.yaml.example compose.yaml
   cp traefik/traefik.yml.example traefik/traefik.yml
   cp traefik/traefik.dynamic.yml.example traefik/traefik.dynamic.yml
   ```

3. **Edit configuration**

   - Update hostnames in `compose.yaml` (replace `domain.com` with your domain)
   - Update hostnames in `traefik/traefik.yml` and `traefik/traefik.dynamic.yml`
   - Place your CA certificates in `./traefik/certs/` if you use an internal ACME server, and point `LEGO_CA_CERTIFICATES` in `./traefik/.env` at the root CA
   - Update passwords in `./paperless/.env` and `./postgres/.env` (must match)
   - Set `PAPERLESS_SECRET_KEY` in `./paperless/.env` — required since v3:

     ```bash
     python3 -c "import secrets; print(secrets.token_urlsafe(64))"
     ```

   - Place your GGUF model files in `./llama-cpp/models/` and update the model paths in the llama-cpp command in `compose.yaml`
   - Set `PAPERLESS_AI_LLM_MODEL` in `./paperless/.env` to the same model path, and the `LLM_MODEL` / `VISION_LLM_MODEL` values in `./paperless-gpt/.env` to the GGUF filename

4. **Start the stack**

   ```bash
   docker compose up -d
   ```

5. **Create admin account**

   Access Paperless via your configured hostname and create your admin account.

6. **Configure AI services**

   Native AI (suggestions, similar documents, document chat) is already wired to llama-cpp in `./paperless/.env` — nothing to do beyond having a model loaded.

   For paperless-gpt (vision-LLM OCR):

   - In Paperless, go to Profile > API Tokens > Generate
   - Copy the token into `./paperless-gpt/.env`
   - Restart: `docker compose restart paperless-gpt`

7. **Build the AI index**

   Needed once for document chat and similar-document retrieval:

   ```bash
   docker compose exec paperless document_llmindex rebuild
   ```

**The AI components are entirely optional.** Set `PAPERLESS_AI_ENABLED=0` in `./paperless/.env` and comment out `llama-cpp` and `paperless-gpt` to run a plain stack. Paperless works great without AI.

## Architecture

All services are routed through Traefik and are not exposed directly on localhost ports. Access them via the hostnames you configure.

| Service | Description |
| ------- | ----------- |
| Traefik | Reverse proxy with TLS (ports 80/443) |
| Paperless-ngx | Document management with OCR, search, and native AI features |
| llama-cpp | Local LLM inference via llama-server (CUDA) |
| Paperless-GPT | Vision-LLM OCR for scanned documents |
| Dozzle | Real-time Docker log viewer |
| PostgreSQL | Database for Paperless |
| Valkey | Message broker for Paperless (Redis-protocol compatible) |
| Gotenberg | Document conversion |
| Tika | Content detection and text extraction |

### Commented-out alternatives (in compose.yaml.example)

- **Ollama** — drop-in replacement for llama-cpp if you prefer Ollama's model management
- **Open WebUI** — web UI for interacting with LLMs directly
- **llama-swap** — hot-swaps between multiple GGUF models on demand

## AI Features

Paperless-ngx v3 ships AI natively, so no companion container is needed for suggestions or chat. Everything is configured through the `PAPERLESS_AI_*` variables in `./paperless/.env`:

| Feature | What it does |
| ------- | ------------ |
| AI suggestions | LLM-proposed title, tags, correspondent, type, storage path and dates, via the "Suggest" control on a document. Runs alongside the classic classifier, doesn't replace it. |
| Similar documents | Vector retrieval over the LLM index |
| Document chat | Ask questions about one document or the current view, with links back to sources |

Two backends are involved:

- **LLM** — `openai-like` against llama-cpp at `http://llama-cpp:8080/v1`. llama-server **must** run with `--jinja --reasoning off`. Suggestions use OpenAI tool calling, and llama-server only emits tool calls when the model's own chat template is active (`--jinja`); but that same template turns on Qwen3.5's thinking mode, which burns thousands of reasoning tokens before answering, so `--reasoning off` is equally required.
- **Embeddings** — `huggingface`, running `all-MiniLM-L6-v2` on CPU inside the paperless container. Keeps VRAM free for llama-cpp. The model downloads to `./paperless/data/hf_cache` on first use, so the first index build needs network access.

Managing the index:

```bash
docker compose exec paperless document_llmindex rebuild
```

`rebuild` builds from scratch (first run, or after changing embedding model), `update` indexes new/changed documents (also runs daily per `PAPERLESS_LLM_INDEX_TASK_CRON`), `compact` reclaims disk space.

Settings changed in the admin UI (Settings → Application Configuration) take precedence over these environment variables.

Document content is sent to whatever endpoint you configure. With the defaults here it never leaves the host.

## Upgrading from Paperless-ngx v2

v3 can only be upgraded from **2.20.15** — step through that version first. Back up `./postgres/data/` and `./paperless/data/` before starting. What this stack needed:

- `PAPERLESS_SECRET_KEY` is now **required**. Reuse your old value to keep sessions and API tokens valid, or set a new one and accept that they are invalidated.
- `PAPERLESS_DBENGINE=postgresql` is now explicit — the engine is no longer inferred from `PAPERLESS_DBHOST`.
- Broker moved from `redis:8` to `valkey:9-alpine` with a new `./valkey/data/` directory. `PAPERLESS_REDIS` keeps the `redis://` scheme. The old `./redis/data/` is unused and can be deleted once the stack is healthy.
- Search moved from Whoosh to Tantivy. The index rebuilds itself on first start. Saved views using `note:` / `custom_field:` are migrated automatically, but plain unqualified searches no longer match note or custom field text — use `notes.note:` / `custom_fields.value:` explicitly.
- Duplicates are now accepted and flagged in the UI instead of rejected. Set `PAPERLESS_CONSUMER_DELETE_DUPLICATES=true` to restore the old behavior.
- Task history is dropped during the upgrade, and pre/post-consume scripts no longer get positional arguments (`$1`…`$8`) — use the `DOCUMENT_*` environment variables.
- Removed settings that will log a startup warning if still set: `PAPERLESS_OCR_SKIP_ARCHIVE_FILE` (now `PAPERLESS_ARCHIVE_FILE_GENERATION`), `PAPERLESS_OCR_MODE=skip`/`skip_noarchive` (now `auto`), `CONSUMER_BARCODE_SCANNER`, and the individual `PAPERLESS_DBSSL*` / pooling variables (now `PAPERLESS_DB_OPTIONS`).
- Behind Traefik, login rate limiting may need `PAPERLESS_TRUSTED_PROXIES` or `PAPERLESS_ALLAUTH_TRUSTED_PROXY_COUNT` if you hit `403` on login.

Full details: [v3 migration guide](https://docs.paperless-ngx.com/migration-v3/).

## Basic Usage

- **Add documents**: Drop files in `./paperless/consume/`
- **View logs**: Access Dozzle via its configured hostname, or `docker compose logs [service]`
- **Update images**: `docker compose pull && docker compose up -d`

## Important Notes

- **Security**: Use a VPN or private network for access. Don't expose these services directly to the internet without proper authentication.
- **Backups**: Back up `./paperless/data/`, `./paperless/media/`, `./postgres/data/`, and `./traefik/acme/acme.json` (issued certificates). `./valkey/data/` holds only the transient task queue and does not need backing up.
- **GPU**: llama-cpp is configured for NVIDIA CUDA. Remove the `deploy.resources` section in `compose.yaml` if you don't have an NVIDIA GPU.
- **Models**: Place GGUF model files in `./llama-cpp/models/`. Update the `-m` and `--mmproj` paths in the llama-cpp command in `compose.yaml` to match your model filenames.

## Resources

- **Original guide**: [Self-Hosted Paperless-ngx + Optional Local AI](https://technotim.com/posts/paperless-ngx-local-ai/)
- **Original video**: [Paperless-ngx + Local AI (Optional)](https://www.youtube.com/watch?v=NMAwHjleqHg)

## Troubleshooting

- Check logs: `docker compose logs [service-name]` or use Dozzle
- Check service status: `docker compose ps`
- Verify database credentials match between `paperless/.env` and `postgres/.env`
- For AI issues, ensure llama-cpp is running and the GGUF model files exist in `./llama-cpp/models/`
- AI suggestions failing with a "no tool call" error means llama-cpp is missing `--jinja`
- AI suggestions timing out while llama-cpp shows steady token generation means thinking mode is on — add `--reasoning off`
- Check that `PAPERLESS_AI_LLM_MODEL` matches the id llama-server reports:

  ```bash
  docker compose exec paperless curl -s http://llama-cpp:8080/v1/models
  ```

## Acknowledgments

This stack is built using these open-source projects:

- **[Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx)** - Document management system
- **[llama.cpp](https://github.com/ggerganov/llama.cpp)** - LLM inference in C/C++
- **[Traefik](https://github.com/traefik/traefik)** - Cloud-native reverse proxy
- **[Paperless-GPT](https://github.com/icereed/paperless-gpt)** - Vision OCR for Paperless
- **[PostgreSQL](https://github.com/postgres/postgres)** - Database system
- **[Valkey](https://github.com/valkey-io/valkey)** - Message broker
- **[Gotenberg](https://github.com/gotenberg/gotenberg)** - Document conversion API
- **[Apache Tika](https://github.com/apache/tika)** - Content detection and extraction
- **[Dozzle](https://github.com/amir20/dozzle)** - Real-time log viewer for Docker

Based on [timothystewart6/paperless-stack](https://github.com/timothystewart6/paperless-stack). Thanks to Tim and all contributors.
