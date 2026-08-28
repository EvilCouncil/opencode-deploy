#!/usr/bin/env python3
"""
Bump the opencode-deploy image to the latest GHCR tag.

Usage:
    python3 bump.py                          # latest tag on GHCR
    python3 bump.py --version v1.18.23       # specific tag
    python3 bump.py --dry-run                # show what would change

Flow:
    1. Query GHCR for latest (or given) image tag
    2. Update docker-compose.yml
    3. Validate with `docker compose config --quiet`
    4. Commit + push to main
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

REPO_URL = "https://github.com/EvilCouncil/opencode-deploy"
IMAGE_REF = "ghcr.io/evilcouncil/opencode-docker"
COMPOSE_FILE = Path(__file__).parent / "docker-compose.yml"
COMPOSE_PATTERN = re.compile(
    r"(image:\s+)" + re.escape(IMAGE_REF) + r":([^\s\"\']+)"
)
VERSION_RE = re.compile(r"^v\d+(\.\d+)+$")


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


def read_compose_version() -> str:
    """Read the current image version from docker-compose.yml."""
    content = COMPOSE_FILE.read_text()
    m = COMPOSE_PATTERN.search(content)
    if not m:
        print(f"ERROR: could not find image in {COMPOSE_FILE}", file=sys.stderr)
        sys.exit(1)
    return m.group(2)


def bump_compose(new_version: str) -> str:
    """Update docker-compose.yml and return the old version."""
    content = COMPOSE_FILE.read_text()
    old_version = read_compose_version()
    new_content = COMPOSE_PATTERN.sub(
        rf"\g<1>{IMAGE_REF}:{new_version}", content
    )
    COMPOSE_FILE.write_text(new_content)
    return old_version


def validate_compose() -> None:
    """Run docker compose config --quiet to validate."""
    result = subprocess.run(
        ["docker", "compose", "config", "--quiet"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: compose validation failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("Compose validation: OK")


def git_commit_and_push(old_version: str, new_version: str) -> None:
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
        ["git", "commit", "-m", f"Bump opencode to {new_version}"],
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
        "--dry-run", "-n",
        action="store_true",
        help="Show what would change without modifying anything",
    )
    args = parser.parse_args()

    if args.version:
        target = args.version
        if not target.startswith("v"):
            target = f"v{target}"
        current = read_compose_version()
        print(f"Current: {current} -> Target: {target}")
    else:
        print("Querying GHCR for latest tag...")
        current = read_compose_version()
        latest = ghcr_latest_version()
        if current == latest:
            print(f"Already on latest version ({current}).")
            return
        target = latest
        print(f"Current: {current} -> Latest on GHCR: {target}")

    if args.dry_run:
        print(f"Would update docker-compose.yml to {target}")
        print("Would run: docker compose config --quiet")
        print(f"Would commit: 'Bump opencode to {target}'")
        print(f"Would push to {REPO_URL}")
        return

    # Bump
    print(f"Bumping {current} -> {target}...")
    bump_compose(target)

    # Validate
    validate_compose()

    # Commit + push
    git_commit_and_push(current, target)

    print(f"Done! Deployed to {REPO_URL}")
    print(f"Portainer stack ID 34 / endpoint 7 will redeploy on next poll.")


if __name__ == "__main__":
    main()
