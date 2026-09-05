#!/usr/bin/env bash
# First-run helper for MOW Tracker.
#   deploy/setup.sh            Docker: writes .env, builds the image, creates the first admin, starts it
#   deploy/setup.sh --bare     Bare metal: writes .env and creates the first admin (then start the service)
#   add --demo to either       Seeds the demo dataset (demo/data) so there is something to look at
set -euo pipefail
cd "$(dirname "$0")/.."

MODE=docker
DEMO=0
for arg in "$@"; do
  case "$arg" in
    --bare) MODE=bare ;;
    --demo) DEMO=1 ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg"; exit 1 ;;
  esac
done

if [ ! -f .env ]; then
  cp .env.example .env
  KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$KEY|" .env
  read -rp "Public host name for HTTPS (use localhost for a trial) [localhost]: " DOMAIN
  DOMAIN=${DOMAIN:-localhost}
  sed -i "s|^TRACKWORK_DOMAIN=.*|TRACKWORK_DOMAIN=$DOMAIN|" .env
  if [ "$MODE" = bare ]; then
    sed -i "s|^DATA_DIR=.*|DATA_DIR=$(pwd)/data|" .env
  fi
  echo "Wrote .env with a fresh SECRET_KEY."
else
  echo ".env already exists; leaving it alone."
fi

run_cli() {
  if [ "$MODE" = docker ]; then
    docker compose run --rm "${EXTRA_MOUNT[@]}" web python scripts/cli.py "$@"
  else
    .venv/bin/python scripts/cli.py "$@"
  fi
}
EXTRA_MOUNT=()

if [ "$MODE" = docker ]; then
  command -v docker >/dev/null || { echo "Docker is not installed. See deploy/bare-metal.md for the other path."; exit 1; }
  docker compose build
fi

if [ "$DEMO" = 1 ]; then
  if [ -d demo/data ]; then
    if [ "$MODE" = docker ]; then
      EXTRA_MOUNT=(-v "$(pwd)/demo/data:/seed:ro")
      run_cli import /seed --overwrite
      EXTRA_MOUNT=()
    else
      run_cli import demo/data --overwrite
    fi
  else
    echo "No demo/data directory found; skipping the demo seed."
  fi
fi

if ! run_cli user list 2>/dev/null | grep -q '@'; then
  echo "Create the first admin account (you will be asked for a password):"
  read -rp "  Email: " EMAIL
  read -rp "  Name: " NAME
  run_cli user add "$EMAIL" "$NAME" --role admin
fi

if [ "$MODE" = docker ]; then
  docker compose up -d
  echo "Running. Open https://$(grep '^TRACKWORK_DOMAIN=' .env | cut -d= -f2)/ and sign in."
else
  echo "Configured. Start the service next (deploy/bare-metal.md, step 4)."
fi
