# AI Agents Hub

AI Agents Hub is a custom router/supervisor service that exposes an OpenAI-compatible API for Open WebUI and coordinates specialist behavior internally.

## MVP Features

- OpenAI-compatible endpoints:
  - `GET /v1/models`
  - `POST /v1/chat/completions` (streaming and non-streaming)
- Specialist routing with coherent final response synthesis
- Web search augmentation with source-aware output
- Image payload passthrough through `chat/completions`
- Atomic markdown memory store (one memory per file with frontmatter)
- Obsidian daily journal writing (journals are not part of memory store)
- Restart-safe persistence and diagnostics endpoints

## Configuration

Main config file: `config.yaml`

API keys are referenced from environment variables:

- `${ENV:OPENAI_API_KEY}`
- `${ENV:GEMINI_API_KEY}`
- `${ENV:AI_AGENTS_HUB_API_KEY}`

Use:

- `.env` for local development secrets (copy from `.env.example`)
- `/etc/ai-agents-hub/ai-agents-hub.env` for systemd deployments

For local macOS testing, use `config.local.yaml` so data and logs stay under `./data`.

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# edit .env and set keys
export AI_AGENTS_HUB_CONFIG="$(pwd)/config.local.yaml"
ai-agents-hub
```

### Local Debug Modes

You can control debug verbosity and output using config or env overrides.

- Levels: `ERROR`, `WARNING`, `INFO`, `DEBUG`, `TRACE`
- Outputs: `console`, `file`, `both`
- Daily file rotation: `logging.daily_rotation: true`

Quick override examples (without editing YAML):

```bash
AI_AGENTS_HUB_LOG_LEVEL=DEBUG AI_AGENTS_HUB_LOG_OUTPUT=console ai-agents-hub
AI_AGENTS_HUB_LOG_LEVEL=TRACE AI_AGENTS_HUB_LOG_OUTPUT=both AI_AGENTS_HUB_LOG_DIR="$(pwd)/data/logs" ai-agents-hub
```

Tail daily-rotating log file:

```bash
tail -f data/logs/ai-agents-hub.log
```

## Install in Proxmox LXC

### One-liner (Proxmox host)

After this repository is pushed to GitHub, run this on the Proxmox host:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/<YOUR_USER>/<YOUR_REPO>/main/deploy/proxmox/ai-agents-hub-lxc.sh)"
```

Optional overrides:

```bash
CTID=230 MEMORY=8192 CORES=4 DISK=20 REPO_URL=https://github.com/<YOUR_USER>/<YOUR_REPO>.git REPO_REF=main \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/<YOUR_USER>/<YOUR_REPO>/main/deploy/proxmox/ai-agents-hub-lxc.sh)"
```

Defaults used by the script:

- Debian template: latest `debian-12-standard` available
- CT networking: `ip=dhcp` on `vmbr0`
- Rootfs storage: `local-lvm`
- App install path in CT: `/opt/ai-agents-hub`

The script creates the CT, installs AI Agents Hub, and prints next-step commands.

### Manual (inside container)

From repo root inside the LXC container:

```bash
chmod +x deploy/install_lxc.sh
sudo ./deploy/install_lxc.sh
```

Then edit:

- `/etc/ai-agents-hub/config.yaml`
- `/etc/ai-agents-hub/ai-agents-hub.env`

Restart:

```bash
sudo systemctl restart ai-agents-hub
```

Check:

```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/readyz
curl http://localhost:8080/diagnostics
```

## Open WebUI Connection

Point Open WebUI OpenAI connection to:

- Base URL: `http://<ai-agents-hub-host>:8080/v1`
- API Key: one of `server.api_keys` values

## Configure Specialist System Prompts

Prompts are loaded from markdown files in:

- local: `./prompts/specialists`
- LXC service default: `/opt/ai-agents-hub/prompts/specialists`

Config location:

```yaml
specialists:
  prompts:
    directory: ./prompts/specialists
    auto_reload: true
    files:
      supervisor: supervisor.md
      general: general.md
      health: health.md
      parenting: parenting.md
      relationship: relationship.md
      homelab: homelab.md
      personal_development: personal_development.md
```

The master routing/synthesis agent prompt is:

- `supervisor.md`

When `auto_reload: true`, prompt edits are reloaded automatically on next request.
If you changed `config.yaml` itself, restart the service.

```bash
sudo systemctl restart ai-agents-hub
```

## Memory Editing Strategy

Canonical storage is atomic files under:

- `memories/domains/<domain>/<year>/...`

Practical manual editing should happen in Obsidian control notes and/or Dataview dashboards, while the atomic files remain source-of-truth.
