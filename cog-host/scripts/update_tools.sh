#!/usr/bin/env bash
# Monthly maintenance: refresh pipx tools and re-run the smoke tests.
# Sherlock and Maigret site lists go stale, so do this monthly (Phase 7).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== pipx upgrade-all =="
pipx upgrade-all

echo "== PhoneInfoga version =="
if command -v phoneinfoga >/dev/null 2>&1; then
    phoneinfoga version
else
    echo "phoneinfoga not on PATH - update manually from the official releases page"
fi

echo "== check_keys.py =="
.venv/bin/python scripts/check_keys.py || true

echo "== ruff =="
.venv/bin/ruff check app/ tests/ scripts/

echo "== mypy =="
.venv/bin/mypy app/ --ignore-missing-imports

echo "== pytest =="
.venv/bin/python -m pytest -q

echo "Done. Review any FAIL/timeout output above."
