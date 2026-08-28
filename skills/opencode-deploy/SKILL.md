# opencode-deploy

Bump the opencode container image on cortana.evilcouncil.org via the `bump.py` script.
This is a GitOps deploy repo — Portainer polls `main` and redeploys the `opencode` stack
(stack ID 34, endpoint ID 7 / `cortana`) when `docker-compose.yml` changes.

## Quick Reference

| Item | Value |
|------|-------|
| Repo | `github.com/EvilCouncil/opencode-deploy` |
| Stack | Portainer stack ID **34**, endpoint ID **7** |
| Image source | `ghcr.io/evilcouncil/opencode-docker` (from `opencode-docker` repo) |
| Template | `docker-compose.yml.j2` rendered from `defaults.py` |
| CI lint | `docker compose config --quiet` (`.github/workflows/lint.yml`) |

## Bump Workflow

### Prerequisites

- The new image must already be built and pushed to GHCR by the `opencode-docker` repo.
- **Never trust tag names alone** — `v1.17.18` was once built with a wrong `opencode-ai` version
  (fixed by `v1.17.18.1`). Verify the running container's actual version when debugging.

### Bump to latest

```bash
python3 bump.py
```

This queries GHCR for the latest semver-sorted versioned tag, updates `defaults.py`, renders the
Jinja2 template to `docker-compose.yml`, validates, commits, and pushes to `main`. Portainer
will redeploy on its next poll (can take longer than the nominal 1-2 minute window).

### Bump to a specific version

```bash
python3 bump.py --version v1.18.25
```

The `--version` flag auto-prepends `v` if missing (e.g. `1.18.25` becomes `v1.18.25`).

### Dry run

```bash
python3 bump.py --dry-run
```

Shows the rendered `docker-compose.yml`, what version would change to, and what commands would run
— without modifying any files.

### Override arbitrary config

```bash
python3 bump.py --set '{"ports":["8080:4096"]}'
```

The `--set` flag accepts a JSON string that deeply merges into the defaults before rendering.
Useful for temporary port changes or other ad-hoc adjustments.

### Full bump with override

```bash
python3 bump.py --version v1.19.0 --set '{"ports":["8080:4096"]}'
```

### No-op detection

If the current `docker-compose.yml` already has the target version and no `--set` overrides are
provided, `bump.py` prints `Already on latest version` and exits without committing.

## After Pushing

Portainer polls `main` and auto-deploys. Verify it's live by checking:

1. **Portainer stack** — `updated_at` on stack ID 34 via Portainer MCP tools (`listLocalStacks`)
2. **Running container** — exec into the container and check the actual installed version

Portainer may take longer than 1-2 minutes to redeploy. Don't declare success until the running
container matches the new version.

## Important Details

- **SELinux labels**: Volumes use `:z` suffix (`/srv/opencode:/workspace:z`). Never remove it.
- **Secrets**: `UI_PASSWORD` is a Portainer stack env var, never committed.
- **`defaults.py`**: The `DEFAULTS["image"]` key tracks the pinned version. `bump.py` updates
  this automatically during a bump.
- **`docker-compose.yml`**: The rendered output file. Portainer reads this from `main`.
- **`docker-compose.yml.j2`**: The Jinja2 template. Normally never edited directly — all config
  goes through `defaults.py` (or `--set` overrides).

## When NOT to Use `bump.py`

- Editing non-version config (ports, volumes, environment): modify `defaults.py` directly or
  use `--set`, then commit + push manually. There is no other automation for config changes.
- Building images: that happens in the `opencode-docker` repo, not here.
