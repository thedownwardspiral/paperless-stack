# Paperless Stack

Docker Compose stack for running Paperless-ngx with local AI capabilities, using llama.cpp for LLM inference and Traefik as a reverse proxy.

This is a fork of [timothystewart6/paperless-stack](https://github.com/timothystewart6/paperless-stack) with the following changes:

- **llama.cpp** replaces Ollama and Open WebUI — runs GGUF models directly via llama-server with CUDA support
- **Traefik** reverse proxy added for TLS termination and routing (services are not exposed on localhost ports)
- **paperless-ai** configured to use llama-cpp as a custom OpenAI-compatible provider instead of Ollama
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
   cp traefik.yml.example traefik.yml
   cp traefik.dynamic.yml.example traefik.dynamic.yml
   ```

3. **Edit configuration**

   - Update hostnames in `compose.yaml` (replace `domain.com` with your domain)
   - Update hostnames in `traefik.yml` and `traefik.dynamic.yml`
   - Update passwords in `./paperless/.env` and `./postgres/.env` (must match)
   - Place your GGUF model files in `./llama-cpp/models/` and update the model paths in the llama-cpp command in `compose.yaml`

4. **Start the stack**

   ```bash
   docker compose up -d
   ```

5. **Create admin account**

   Access Paperless via your configured hostname and create your admin account.

6. **Configure AI services**

   - In Paperless, go to Profile > API Tokens > Generate
   - Copy the token into `./paperless-ai/.env` and `./paperless-gpt/.env`
   - Update `./paperless-ai/.env` with your Paperless username
   - Restart: `docker compose restart paperless-ai paperless-gpt`

**The AI components are entirely optional** and can be disabled by commenting them out. Paperless works great without AI.

## Architecture

All services are routed through Traefik and are not exposed directly on localhost ports. Access them via the hostnames you configure.

| Service | Description |
| ------- | ----------- |
| Traefik | Reverse proxy with TLS (ports 80/443) |
| Paperless-ngx | Document management with OCR and search |
| llama-cpp | Local LLM inference via llama-server (CUDA) |
| Paperless-AI | AI-powered metadata suggestions |
| Paperless-GPT | Vision OCR and metadata suggestions |
| Dozzle | Real-time Docker log viewer |
| PostgreSQL | Database for Paperless |
| Redis | Cache and message broker for Paperless |
| Gotenberg | Document conversion |
| Tika | Content detection and text extraction |

### Commented-out alternatives (in compose.yaml.example)

- **Ollama** — drop-in replacement for llama-cpp if you prefer Ollama's model management
- **Open WebUI** — web UI for interacting with LLMs directly
- **llama-swap** — hot-swaps between multiple GGUF models on demand

## Basic Usage

- **Add documents**: Drop files in `./paperless/consume/`
- **View logs**: Access Dozzle via its configured hostname, or `docker compose logs [service]`
- **Update images**: `docker compose pull && docker compose up -d`

## Important Notes

- **Security**: Use a VPN or private network for access. Don't expose these services directly to the internet without proper authentication.
- **Backups**: Back up `./paperless/data/`, `./paperless/media/`, and `./postgres/data/`
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

## Acknowledgments

This stack is built using these open-source projects:

- **[Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx)** - Document management system
- **[llama.cpp](https://github.com/ggerganov/llama.cpp)** - LLM inference in C/C++
- **[Traefik](https://github.com/traefik/traefik)** - Cloud-native reverse proxy
- **[Paperless-AI](https://github.com/clusterzx/paperless-ai)** - AI-powered metadata suggestions
- **[Paperless-GPT](https://github.com/icereed/paperless-gpt)** - Vision OCR for Paperless
- **[PostgreSQL](https://github.com/postgres/postgres)** - Database system
- **[Redis](https://github.com/redis/redis)** - Cache and message broker
- **[Gotenberg](https://github.com/gotenberg/gotenberg)** - Document conversion API
- **[Apache Tika](https://github.com/apache/tika)** - Content detection and extraction
- **[Dozzle](https://github.com/amir20/dozzle)** - Real-time log viewer for Docker

Based on [timothystewart6/paperless-stack](https://github.com/timothystewart6/paperless-stack). Thanks to Tim and all contributors.
