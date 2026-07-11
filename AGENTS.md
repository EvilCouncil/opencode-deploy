# Agent Instructions

This is `opencode-deploy` (`github.com/EvilCouncil/opencode-deploy`), a GitOps deploy repo for the `opencode` container running on `cortana.evilcouncil.org`. It holds nothing but a `docker-compose.yml` — there is no build, no local run step, and no CI/CD beyond compose linting.

## Key Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | The only file that matters. Portainer polls this repo's `main` branch and redeploys the `opencode` stack whenever it changes. |
| `.github/workflows/lint.yml` | Validates `docker-compose.yml` (`docker compose config --quiet`) on push/PR that touches it |

## Deployment Model

- **No manual deploy step** — Portainer GitOps polling on `main` is the only deploy mechanism. Editing and pushing `docker-compose.yml` *is* the deploy.
- Portainer stack: local stack id **34**, endpoint id **7** (`cortana`, docker-agent). See the `portainer-ops` agent memory (`reference_opencode_stack`) for exec/verification commands.
- **Polling lag**: Portainer does not redeploy instantly — it can take longer than the nominal 1-2 minute polling window. Don't assume a push has taken effect; verify via `listLocalStacks` (`updated_at` on stack id 34) or by exec'ing into the running container and checking the actual installed version before declaring a change live.
- **Image source**: image tags come from the separate `opencode-docker` repo (`docker/opencode-docker/` in the main homelab monorepo, published at `github.com/EvilCouncil/opencode-docker`). Bump the `image:` tag here only after a corresponding image has actually been built and pushed to GHCR there.

## Patterns

- **Version mismatches happen**: `v1.17.18` was once built with the wrong `opencode-ai` version baked in (fixed by `v1.17.18.1`). Never trust the tag name alone — verify the running container's actual version when debugging.
- **Secrets**: `UI_PASSWORD` is supplied as a Portainer stack environment variable, never committed to `docker-compose.yml`.
- **SELinux volume labels**: bind mounts use the `:z` suffix (`/srv/opencode:/workspace:z`, `/srv/opencode-homedir:/home/opencode:z`) — keep this when editing volumes on this host.

## Tool Usage

Prefer MCP filesystem/ripgrep tools over Bash for file reads/searches. Use Bash for `git` and any `docker compose config` validation.
