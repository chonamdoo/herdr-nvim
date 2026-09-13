#!/usr/bin/env bash
# Select Python with stdlib TOML support without installing anything.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
for python in "${PYTHON:-python3}" python3.13 python3.14 python3.12 python3.11 \
  /opt/homebrew/opt/python@3.13/bin/python3.13 \
  /usr/local/opt/python@3.13/bin/python3.13 \
  /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if command -v "$python" >/dev/null 2>&1 && \
    "$python" -c 'import sys, tomllib; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    exec "$python" "$ROOT/setup/install.py" "$@"
  fi
done
printf '%s\n' 'setup: Python 3.11+ is required (for example: brew install python@3.13).' >&2
exit 1
