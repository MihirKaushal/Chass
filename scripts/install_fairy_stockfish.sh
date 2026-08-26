#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMIT="6d9d0f5724677dc3aba3c577b0b482b6ec11e44a"
SOURCE_SHA256="42ad01ffd964b0801c9d5f8b1a3a6fea6dc7b0ba66e38740cff852c221aa0228"
DESTINATION="${FAIRY_STOCKFISH_INSTALL_PATH:-$ROOT_DIR/.stockfish/fairy-stockfish}"
BUILD_JOBS="${FAIRY_STOCKFISH_BUILD_JOBS:-2}"

if [[ -x "$DESTINATION" && "${FORCE_FAIRY_STOCKFISH_INSTALL:-0}" != "1" ]]; then
  echo "Fairy-Stockfish is already installed at $DESTINATION"
  exit 0
fi

case "$(uname -s):$(uname -m)" in
  Darwin:arm64)
    ARCH="apple-silicon"
    COMP="clang"
    COMPILER_COMMAND="clang++"
    ;;
  Darwin:x86_64)
    ARCH="x86-64"
    COMP="clang"
    COMPILER_COMMAND="clang++"
    ;;
  Linux:x86_64)
    ARCH="x86-64"
    COMP="gcc"
    COMPILER_COMMAND="g++"
    ;;
  *)
    echo "No verified Fairy-Stockfish build recipe is available for $(uname -s) $(uname -m)." >&2
    echo "Build a largeboard binary manually and set FAIRY_STOCKFISH_PATH." >&2
    exit 1
    ;;
esac

if ! [[ "$BUILD_JOBS" =~ ^[1-9][0-9]*$ ]]; then
  echo "FAIRY_STOCKFISH_BUILD_JOBS must be a positive whole number." >&2
  exit 1
fi

for command_name in curl tar make "$COMPILER_COMMAND"; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
done

TEMP_DIR="$(mktemp -d)"
ARCHIVE="$TEMP_DIR/fairy-stockfish.tar.gz"
EXTRACTED="$TEMP_DIR/extracted"
cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

URL="https://github.com/fairy-stockfish/Fairy-Stockfish/archive/$COMMIT.tar.gz"
echo "Downloading pinned Fairy-Stockfish source for $(uname -s) $(uname -m)..."
curl --fail --location --silent --show-error \
  --connect-timeout 15 --retry 3 --retry-all-errors \
  "$URL" --output "$ARCHIVE"

if command -v shasum >/dev/null 2>&1; then
  ACTUAL_SHA256="$(shasum -a 256 "$ARCHIVE" | awk '{print $1}')"
elif command -v sha256sum >/dev/null 2>&1; then
  ACTUAL_SHA256="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
else
  echo "A SHA-256 utility is required to verify the Fairy-Stockfish source." >&2
  exit 1
fi

if [[ "$ACTUAL_SHA256" != "$SOURCE_SHA256" ]]; then
  echo "Fairy-Stockfish checksum verification failed." >&2
  exit 1
fi

mkdir -p "$EXTRACTED"
tar -xzf "$ARCHIVE" -C "$EXTRACTED"
SOURCE_DIR="$(find "$EXTRACTED" -mindepth 1 -maxdepth 1 -type d -print -quit)"
if [[ -z "$SOURCE_DIR" || ! -d "$SOURCE_DIR/src" ]]; then
  echo "The Fairy-Stockfish source directory was not found." >&2
  exit 1
fi

echo "Building the verified largeboard engine with $BUILD_JOBS job(s)..."
make -C "$SOURCE_DIR/src" -j"$BUILD_JOBS" build \
  ARCH="$ARCH" COMP="$COMP" largeboards=yes

BINARY_PATH="$SOURCE_DIR/src/stockfish"
if [[ ! -x "$BINARY_PATH" ]]; then
  echo "The Fairy-Stockfish executable was not produced." >&2
  exit 1
fi

mkdir -p "$(dirname "$DESTINATION")"
install -m 755 "$BINARY_PATH" "$DESTINATION"
echo "Installed verified Fairy-Stockfish largeboard engine at $DESTINATION"
