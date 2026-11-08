#!/usr/bin/env bash
# Sourced by the installers. Cache only archives verified against pinned digests.

engine_archive_sha256() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    echo "A SHA-256 utility is required to verify engine downloads." >&2
    return 1
  fi
}

download_engine_archive() {
  local output="$1" expected="$2"
  shift 2
  local cache_dir="${CHASS_ENGINE_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/chass-engines}"
  local cached="$cache_dir/$expected" url digest cache_temp

  if [[ -f "$cached" ]]; then
    digest="$(engine_archive_sha256 "$cached")" || return 1
    if [[ "$digest" == "$expected" ]]; then
      echo "Using checksum-verified cached engine archive."
      cp "$cached" "$output"
      return
    fi
    echo "Ignoring an invalid engine archive cache entry." >&2
  fi

  for url in "$@"; do
    echo "Downloading engine archive: $url"
    if curl --fail --location --silent --show-error \
      --header 'Accept: application/octet-stream' \
      --connect-timeout 15 --max-time 120 \
      --retry 5 --retry-delay 5 --retry-max-time 180 --retry-all-errors \
      "$url" --output "$output"; then
      digest="$(engine_archive_sha256 "$output")" || return 1
      if [[ "$digest" == "$expected" ]]; then
        # Cache writes are optional; a read-only cache must not prevent installation.
        if mkdir -p "$cache_dir" && cache_temp="$(mktemp "$cache_dir/.download.XXXXXX")"; then
          if ! cp "$output" "$cache_temp" || ! mv -f "$cache_temp" "$cached"; then
            rm -f "$cache_temp"
            echo "Could not cache the verified engine archive; continuing." >&2
          fi
        fi
        return 0
      fi
      echo "Engine checksum verification failed for $url" >&2
    else
      echo "Engine download failed after retries: $url" >&2
    fi
    rm -f "$output"
  done
  echo "No verified engine archive was available. Retry the deployment when GitHub downloads recover. No unverified binary will be installed." >&2
  return 1
}
