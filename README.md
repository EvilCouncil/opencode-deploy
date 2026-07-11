# 🐳 opencode-deploy

GitOps deploy repo for the `opencode` stack running on `cortana.evilcouncil.org`. Portainer polls this repo's `main` branch and redeploys the stack whenever `docker-compose.yml` changes — there's nothing to run manually.

📦 **Image:** [`ghcr.io/evilcouncil/opencode-docker`](https://github.com/EvilCouncil/opencode-docker)

## ✨ What's here

- 🧾 `docker-compose.yml` — the single service definition Portainer deploys
- ✅ `.github/workflows/lint.yml` — validates `docker-compose.yml` with `docker compose config` on every push/PR that touches it

## 🚀 How deploys work

1. Bump the `image:` tag in `docker-compose.yml` (see [opencode-docker releases](https://github.com/EvilCouncil/opencode-docker/releases) for available tags)
2. Push to `main`
3. Portainer (endpoint `cortana`, local stack id `34`) polls `main` and redeploys automatically

⏱️ **Heads up:** Portainer's GitOps polling interval is several minutes — a push landing on `main` doesn't mean the stack has redeployed yet. Verify via Portainer (`listLocalStacks` → check `updated_at` for stack id 34) or by exec'ing into the running container and checking the installed version, rather than trusting the tag name alone.

## 🔐 Configuration

- `UI_PASSWORD` — set as a stack environment variable in Portainer, not committed here
- Bind mounts: `/srv/opencode` → `/workspace`, `/srv/opencode-homedir` → `/home/opencode`

## 🩺 Health check

The container exposes `http://localhost:4096/global/health`, polled every 30s (3 retries, 30s start period).
