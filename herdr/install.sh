#!/usr/bin/env bash
# Always build this checkout: a fork's edits must never be replaced by an
# upstream release binary. Build for this host, not a configured cross target.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$ROOT"
export PATH="${PATH:-}:/opt/homebrew/bin:/usr/local/bin:${HOME:?}/.cargo/bin"
if ! command -v cargo >/dev/null 2>&1 || ! command -v rustc >/dev/null 2>&1; then
  printf '%s\n' 'herdr-nvim: Rust/Cargo is required to build this checkout.' >&2
  exit 1
fi
host="$(rustc -vV | sed -n 's/^host: //p')"
cargo build --manifest-path "$ROOT/Cargo.toml" --release --locked --target "$host" --target-dir "$ROOT/target"
mkdir -p "$ROOT/bin"
temporary="$(mktemp "$ROOT/bin/.herdr-nvim.XXXXXX")"
trap 'rm -f "$temporary"' EXIT
cp "$ROOT/target/$host/release/herdr-nvim" "$temporary"
chmod +x "$temporary"
if [ -f "$ROOT/bin/herdr-nvim" ] && ! cmp -s "$temporary" "$ROOT/bin/herdr-nvim"; then
  cp -p "$ROOT/bin/herdr-nvim" "$ROOT/bin/herdr-nvim.bak.$(date +%Y%m%d%H%M%S).$$"
fi
mv -f "$temporary" "$ROOT/bin/herdr-nvim"
