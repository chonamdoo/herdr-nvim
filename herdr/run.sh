#!/usr/bin/env bash
# Supply common fallback locations without shadowing caller-selected tool
# versions that the portable installer already validated.
set -euo pipefail
export PATH="${PATH:+$PATH:}/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

if [ -n "${HERDR_PLUGIN_ROOT:-}" ]; then
  BIN="$HERDR_PLUGIN_ROOT/bin/herdr-nvim"
else
  BIN="$(cd "$(dirname "$0")/.." && pwd)/bin/herdr-nvim"
fi

exec "$BIN" "$@"
