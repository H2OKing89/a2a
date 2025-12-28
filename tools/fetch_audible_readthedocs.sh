#!/usr/bin/env bash
set -euo pipefail

# Fetch upstream Audible (python-audible) ReadTheDocs .rst.txt sources.
# Saves into: docs/Audible/upstream/
# Note: This is intended for LOCAL reference; do not commit third-party docs unless you’ve verified licensing.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/docs/Audible/upstream"

mkdir -p "$OUT_DIR"

fetch() {
  local url="$1"
  local out="$2"

  echo "Fetching: $url"
  curl -fsSL "$url" -o "$OUT_DIR/$out"
}

fetch "https://audible.readthedocs.io/en/latest/_sources/intro/install.rst.txt" "intro_install.rst.txt"
fetch "https://audible.readthedocs.io/en/latest/_sources/intro/getting_started.rst.txt" "intro_getting_started.rst.txt"
fetch "https://audible.readthedocs.io/en/latest/_sources/marketplaces/marketplaces.rst.txt" "marketplaces.rst.txt"
fetch "https://audible.readthedocs.io/en/latest/_sources/auth/authorization.rst.txt" "auth_authorization.rst.txt"
fetch "https://audible.readthedocs.io/en/latest/_sources/auth/authentication.rst.txt" "auth_authentication.rst.txt"
fetch "https://audible.readthedocs.io/en/latest/_sources/auth/register.rst.txt" "auth_register.rst.txt"
fetch "https://audible.readthedocs.io/en/latest/_sources/misc/load_save.rst.txt" "misc_load_save.rst.txt"
fetch "https://audible.readthedocs.io/en/latest/_sources/misc/async.rst.txt" "misc_async.rst.txt"
fetch "https://audible.readthedocs.io/en/latest/_sources/misc/advanced.rst.txt" "misc_advanced.rst.txt"
fetch "https://audible.readthedocs.io/en/latest/_sources/misc/logging.rst.txt" "misc_logging.rst.txt"
fetch "https://audible.readthedocs.io/en/latest/_sources/misc/external_api.rst.txt" "misc_external_api.rst.txt"
fetch "https://audible.readthedocs.io/en/latest/_sources/misc/examples.rst.txt" "misc_examples.rst.txt"
fetch "https://audible.readthedocs.io/en/latest/_sources/modules/audible.rst.txt" "modules_audible.rst.txt"

echo ""
echo "Done. Files written to: $OUT_DIR"
ls -1 "$OUT_DIR" | sed 's/^/  - /'
