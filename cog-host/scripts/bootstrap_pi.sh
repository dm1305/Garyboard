#!/usr/bin/env bash
# Bootstrap Cog Host on a Raspberry Pi (or any Debian-based machine).
#
# Fetches the app from GitHub, installs system packages, sets up the Python
# venv and its dependencies, and installs the optional OSINT CLI tools
# (Sherlock, Maigret, Holehe) via pipx. Safe to re-run: it updates in place
# and never touches an existing .env, database, or virtualenv.
#
# Recommended usage - download it, read it, then run it:
#   curl -fsSL -o bootstrap_pi.sh \
#     https://raw.githubusercontent.com/dm1305/Garyboard/OSIN/cog-host/scripts/bootstrap_pi.sh
#   less bootstrap_pi.sh
#   bash bootstrap_pi.sh
#
# This script only ever uses `sudo` for `apt install`. It never touches
# firewall, SSH or network settings, never adds you to the docker group,
# and never enables linger. It does not create API key accounts or start
# any service - see the "Next steps" it prints at the end for those.
set -euo pipefail

REPO_URL="https://github.com/dm1305/Garyboard.git"
REPO_BRANCH="OSIN"
SRC_DIR="${COG_HOST_SRC:-$HOME/.cache/cog-host-src}"
INSTALL_DIR="${COG_HOST_DIR:-$HOME/cog-host}"

log() { printf '\n== %s ==\n' "$1"; }

log "Phase 0: environment"
grep -E '^(PRETTY_NAME|ID)=' /etc/os-release 2>/dev/null || true
echo "arch: $(uname -m)"
command -v python3 >/dev/null && python3 --version

if ! grep -qi 'debian\|raspbian' /etc/os-release 2>/dev/null; then
    echo "WARNING: this doesn't look like a Debian-based OS. Continuing anyway," \
         "but apt-based steps below may fail." >&2
fi

log "Phase 1: system packages"
# apt update returns non-zero if ANY configured source fails, even ones
# unrelated to what we need (e.g. a stale third-party PPA) - don't let that
# alone abort the script. The apt install right after is what actually
# matters, and it stays fatal.
sudo apt update || echo "apt update reported errors from some source - continuing" >&2
sudo apt install -y \
    python3-venv python3-pip pipx git curl rsync sqlite3 build-essential \
    libxml2-dev libxslt1-dev libffi-dev libssl-dev

log "Fetching cog-host (branch: $REPO_BRANCH)"
if [ -d "$SRC_DIR/.git" ]; then
    echo "Updating existing checkout at $SRC_DIR"
    git -C "$SRC_DIR" fetch origin "$REPO_BRANCH"
    git -C "$SRC_DIR" checkout "$REPO_BRANCH"
    git -C "$SRC_DIR" reset --hard "origin/$REPO_BRANCH"
else
    echo "Cloning into $SRC_DIR"
    git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$SRC_DIR"
fi

mkdir -p "$INSTALL_DIR"
echo "Syncing cog-host/ into $INSTALL_DIR (existing .env, database and venv are never touched)"
rsync -a \
    --exclude='.venv/' \
    --exclude='.env' \
    --exclude='*.db' \
    --exclude='*.db-journal' \
    --exclude='.session_secret' \
    --exclude='.audit_salt' \
    --exclude='__pycache__/' \
    --exclude='.pytest_cache/' \
    --exclude='.ruff_cache/' \
    --exclude='.mypy_cache/' \
    "$SRC_DIR/cog-host/" "$INSTALL_DIR/"
# PLAN.md lives one level up from cog-host/ in the git repo (the rsync above
# only takes the cog-host/ subtree) - copy it in too so the install is
# self-contained and the "see PLAN.md" references in its own docs resolve.
cp "$SRC_DIR/PLAN.md" "$INSTALL_DIR/PLAN.md"

cd "$INSTALL_DIR"

log "Python venv and dependencies"
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
. .venv/bin/activate
pip install --upgrade pip -q
pip install -e ".[dev]" -q
echo "Installed: $(python -c 'import fastapi; print(f"fastapi {fastapi.__version__}")')"
deactivate

log "pipx OSINT tools (Sherlock, Maigret, Holehe)"
pipx ensurepath >/dev/null
export PATH="$PATH:$HOME/.local/bin"

install_or_upgrade() {
    local pkg="$1"
    if pipx list --short 2>/dev/null | grep -q "^${pkg} "; then
        echo "$pkg already installed - upgrading"
        pipx upgrade "$pkg"
    else
        # --backend pip: pipx's default uv backend may be older than pipx
        # needs on some systems (seen on this project's dev container);
        # pip is slower but has no version floor.
        pipx install --backend pip "$pkg"
    fi
}
install_or_upgrade sherlock-project
install_or_upgrade maigret
install_or_upgrade holehe

log ".env"
if [ ! -f .env ]; then
    cp .env.example .env
    chmod 600 .env
    echo "Created $INSTALL_DIR/.env (chmod 600). Add your API keys to it yourself - never paste them into a chat."
else
    echo ".env already exists - left untouched"
fi

log "Verifying the install"
. .venv/bin/activate
if python -m pytest -q; then
    echo "All tests passed."
else
    echo "Tests FAILED - see output above before relying on this install." >&2
fi
deactivate

cat <<EOF

== Done. Cog Host files are at $INSTALL_DIR ==

Still to do yourself (deliberately not automated by this script):

1. API keys (human step - see $INSTALL_DIR/PLAN.md section 3):
     cp is already done; edit $INSTALL_DIR/.env and add whichever keys you have.
     Then: cd $INSTALL_DIR && .venv/bin/python scripts/check_keys.py

2. PhoneInfoga (needs its own ARM64 binary + GPG signature check - see
   $INSTALL_DIR/docs/PHONEINFOGA.md):
     Not installed by this script on purpose - verifying a downloaded
     binary's signature is a trust decision only you should make.

3. Vendor htmx (optional UI enhancement, app works fine without it - see
   $INSTALL_DIR/app/static/README.md):
     curl -sSL -o $INSTALL_DIR/app/static/htmx.min.js \\
       https://unpkg.com/htmx.org@2.0.3/dist/htmx.min.js

4. Run it now, in the foreground, to try it:
     cd $INSTALL_DIR && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
   Then open http://localhost:8080

5. Autostart on boot (optional - see $INSTALL_DIR/docs/cog-host.service):
     mkdir -p ~/.config/systemd/user
     cp $INSTALL_DIR/docs/cog-host.service ~/.config/systemd/user/
     systemctl --user daemon-reload
     systemctl --user enable --now cog-host.service
   (Only run 'loginctl enable-linger \$(whoami)' if you want it running
   headless with nobody logged in - that's your call, not the default.)

To update later, just re-run this script - it re-pulls from GitHub and
re-syncs, leaving your .env, database and venv alone.
EOF
