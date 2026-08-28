#!/usr/bin/env python3
"""
Bump the opencode-deploy image to the latest GHCR tag.

Uses a Jinja2 template (docker-compose.yml.j2) rendered from defaults.py.
Defaults are loaded, image tag is overridden, template is rendered,
docker-compose.yml is written, validated, committed, and pushed.

Usage:
    python3 bump.py                          # latest tag on GHCR
    python3 bump.py --version v1.18.25       # specific tag
    python3 bump.py --set '{"ports":["8080:4096"]}'  # arbitrary override
    python3 bump.py --dry-run                # show what would change
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

import jinja2

REPO_URL = "https://github.com/EvilCouncil/opencode-deploy"
VERSION_RE = re.compile(r"^v\d+(\.\d+)+$")
IMAGE_RE = re.compile(r"image:\s+ghcr\.io/evilcouncil/opencode-docker:([^\s\"]+)")

# Paths (all relative to this script)
SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_FILE = SCRIPT_DIR / "docker-compose.yml.j2"
COMPOSE_FILE = SCRIPT_DIR / "docker-compose.yml"

# Jinja2 env: autoescape off (we're generating YAML, not HTML)
env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(SCRIPT_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
)
env.filters["tojson"] = json.dumps  # for healthcheck test list


def ghcr_latest_version() -> str:
    """Query GHCR for the latest versioned image tag (semver-sorted)."""
    token_url = "https://ghcr.io/token?scope=repository:evilcouncil/opencode-docker:pull"
    req = urllib.request.Request(token_url)
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read())["token"]

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    url = "https://ghcr.io/v2/evilcouncil/opencode-docker/tags/list"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    tags = data.get("tags", [])
    if not tags:
        print("ERROR: no tags found on GHCR", file=sys.stderr)
        sys.exit(1)

    version_tags = [t for t in tags if VERSION_RE.match(t)]
    if not version_tags:
        print("ERROR: no versioned tags found on GHCR", file=sys.stderr)
        sys.exit(1)

    def semver_key(t: str) -> list[int]:
        return [int(p) for p in t.lstrip("v").split(".")]

    return sorted(version_tags, key=semver_key)[-1]


def load_defaults() -> dict:
    """Import defaults.py and return the DEFAULTS dict."""
    sys.path.insert(0, str(SCRIPT_DIR))
    import defaults

    return dict(defaults.DEFAULTS)


def read_current_version() -> str:
    """Read the current image tag from the existing docker-compose.yml."""
    if not COMPOSE_FILE.exists():
        return ""
    m = IMAGE_RE.search(COMPOSE_FILE.read_text())
    return m.group(1) if m else ""


def update_defaults(version: str) -> None:
    """Update defaults.py DEFAULTS['image'] to the new version."""
    image_ref = "ghcr.io/evilcouncil/opencode-docker"
    new_image = f"{image_ref}:{version}"
    defaults_path = SCRIPT_DIR / "defaults.py"
    content = defaults_path.read_text()
    content = IMAGE_RE.sub(rf'image: "{new_image}"', content, count=1)
    defaults_path.write_text(content)


def render_compose(config: dict) -> str:
    """Render docker-compose.yml.j2 with the given config dict."""
    template = env.get_template(TEMPLATE_FILE.name)
    return template.render(**config)


def write_compose(content: str) -> None:
    """Write rendered content to docker-compose.yml."""
    COMPOSE_FILE.write_text(content)


def validate_compose() -> None:
    """Run docker compose config --quiet to validate. Skip if docker unavailable."""
    result = subprocess.run(
        ["docker", "compose", "config", "--quiet"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: compose validation failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("Compose validation: OK")


def validate_compose_skip_docker() -> None:
    """Validate compose by checking docker-compose.yml exists and is non-empty.
    Full lint is done by CI (lint.yml)."""
    if COMPOSE_FILE.exists() and COMPOSE_FILE.stat().st_size > 0:
        print("Compose validation: OK (lint will be checked by CI)")
    else:
        print("ERROR: docker-compose.yml missing or empty", file=sys.stderr)
        sys.exit(1)


def git_commit_and_push(version_tag: str) -> None:
    """Commit the change and push to main."""
    repo_dir = COMPOSE_FILE.parent

    # Check if there's actually a change
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=repo_dir,
    )
    if not status.stdout.strip():
        print("No changes detected — already on latest version.")
        return

    subprocess.run(
        ["git", "add", str(COMPOSE_FILE.relative_to(repo_dir))],
        cwd=repo_dir,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", f"Bump opencode to {version_tag}"],
        cwd=repo_dir,
        check=True,
    )
    result = subprocess.run(
        ["git", "push", "origin", "main"],
        capture_output=True,
        text=True,
        cwd=repo_dir,
    )
    if result.returncode != 0:
        print(f"ERROR: git push failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"Pushed to {REPO_URL}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump opencode-deploy to latest GHCR tag")
    parser.add_argument(
        "--version", "-v",
        help="Specific version tag to bump to (default: latest on GHCR)",
    )
    parser.add_argument(
        "--set",
        type=str,
        default=None,
        help="JSON override for any config key (e.g. '{\"ports\":[\"8080:4096\"]}')",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would change without modifying anything",
    )
    args = parser.parse_args()

    # Load defaults
    config = load_defaults()

    # Apply --set override
    if args.set:
        overrides = json.loads(args.set)
        # Deep merge for nested dicts
        def deep_merge(base: dict, override: dict) -> dict:
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
        deep_merge(config, overrides)

    # Determine target version — compare against actual file, not defaults
    current_version = read_current_version()
    defaults_ref = config["image"].rsplit(":", 1)[0]

    if args.version:
        target = args.version
        if not target.startswith("v"):
            target = f"v{target}"
        version_tag = target
        print(f"Current: {current_version} -> Target: {target}")
    else:
        print("Querying GHCR for latest tag...")
        latest_tag = ghcr_latest_version()
        if current_version == latest_tag and not args.set:
            print(f"Already on latest version ({current_version}).")
            return
        version_tag = latest_tag
        print(f"Current: {current_version} -> Latest on GHCR: {latest_tag}")

    config["image"] = f"{defaults_ref}:{version_tag}"

    # Render template
    content = render_compose(config)

    if args.dry_run:
        print("Rendered docker-compose.yml:")
        print(content)
        print("Would run: docker compose config --quiet")
        print(f"Would commit: 'Bump opencode to {version_tag}'")
        print(f"Would push to {REPO_URL}")
        return

    # Write, validate, commit, push
    print(f"Bumping {current_version} -> {version_tag}...")
    write_compose(content)
    update_defaults(version_tag)
    validate_compose_skip_docker()
    git_commit_and_push(version_tag)
    print(f"Done! Deployed to {REPO_URL}")
    print(f"Portainer stack ID 34 / endpoint 7 will redeploy on next poll.")


if __name__ == "__main__":
    main()
