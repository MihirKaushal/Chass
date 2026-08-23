#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="sf_18"
DESTINATION="${STOCKFISH_INSTALL_PATH:-$ROOT_DIR/.stockfish/stockfish}"

if [[ -x "$DESTINATION" && "${FORCE_STOCKFISH_INSTALL:-0}" != "1" ]]; then
  echo "Stockfish is already installed at $DESTINATION"
  exit 0
fi

case "$(uname -s):$(uname -m)" in
  Darwin:arm64)
    ASSET="stockfish-macos-m1-apple-silicon.tar"
    SHA256="4d77c4aa3ad9bd1ea8111f2ac5a4620fe7ebf998d6893bf828d49ccd579c8cb0"
    ;;
  Darwin:x86_64)
    ASSET="stockfish-macos-x86-64.tar"
    SHA256="e7d7a2bca13915419d41ac6cb8cedb123dd2ba1c39a22c574df7a2aa3f526592"
    ;;
  Linux:x86_64)
    ASSET="stockfish-ubuntu-x86-64.tar"
    SHA256="5c6f38b02a4da5f3ffe763f27da6c3e743eebefd92b50cb3661623b96696adff"
    ;;
  *)
    echo "No pinned Stockfish binary is available for $(uname -s) $(uname -m)." >&2
    echo "Install Stockfish manually and set STOCKFISH_PATH to its executable." >&2
    exit 1
    ;;
esac

for command_name in curl tar; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
done

TEMP_DIR="$(mktemp -d)"
ARCHIVE="$TEMP_DIR/$ASSET"
EXTRACTED="$TEMP_DIR/extracted"
cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

URL="https://github.com/official-stockfish/Stockfish/releases/download/$VERSION/$ASSET"
echo "Downloading Stockfish 18 for $(uname -s) $(uname -m)..."
curl --fail --location --silent --show-error \
  --connect-timeout 15 --retry 3 --retry-all-errors \
  "$URL" --output "$ARCHIVE"

if command -v shasum >/dev/null 2>&1; then
  ACTUAL_SHA256="$(shasum -a 256 "$ARCHIVE" | awk '{print $1}')"
elif command -v sha256sum >/dev/null 2>&1; then
  ACTUAL_SHA256="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
else
  echo "A SHA-256 utility is required to verify the Stockfish download." >&2
  exit 1
fi

if [[ "$ACTUAL_SHA256" != "$SHA256" ]]; then
  echo "Stockfish checksum verification failed." >&2
  exit 1
fi

mkdir -p "$EXTRACTED"
tar -xf "$ARCHIVE" -C "$EXTRACTED"
BINARY_NAME="${ASSET%.tar}"
BINARY_PATH="$(find "$EXTRACTED" -type f -name "$BINARY_NAME" -print -quit)"
if [[ -z "$BINARY_PATH" ]]; then
  echo "The Stockfish executable was not found in $ASSET." >&2
  exit 1
fi

mkdir -p "$(dirname "$DESTINATION")"
install -m 755 "$BINARY_PATH" "$DESTINATION"
echo "Installed verified Stockfish 18 at $DESTINATION"
