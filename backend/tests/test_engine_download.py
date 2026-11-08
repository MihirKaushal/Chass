import hashlib
import os
import subprocess
from pathlib import Path

import pytest

HELPER = Path(__file__).resolve().parents[2] / "scripts/engine_download.sh"
PAYLOAD = b"verified engine fixture"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


@pytest.fixture
def downloader(tmp_path):
    executable = tmp_path / "curl"
    executable.write_text("""#!/bin/sh
printf '%s\n' "$*" >> "$CURL_LOG"
while [ "$#" -gt 0 ]; do
  case "$1" in
    https://*) url="$1" ;;
    --output) shift; output="$1" ;;
  esac
  shift
done
case "$url" in
  *unavailable*) exit 22 ;;
  *corrupt*) printf 'wrong archive' > "$output" ;;
  *) printf 'verified engine fixture' > "$output" ;;
esac
""")
    executable.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "CHASS_ENGINE_CACHE_DIR": str(tmp_path / "cache"),
        "CURL_LOG": str(tmp_path / "curl.log"),
    }

    def download(*urls):
        output = tmp_path / "engine archive.tar"
        result = subprocess.run(
            [
                "bash",
                "-euo",
                "pipefail",
                "-c",
                'source "$1"; shift; download_engine_archive "$@"',
                "test",
                str(HELPER),
                str(output),
                DIGEST,
                *urls,
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        return result, output

    return download, tmp_path


@pytest.mark.parametrize("failure", ["unavailable", "corrupt"])
def test_official_fallback_is_verified_after_failed_download(downloader, failure):
    download, folder = downloader
    result, output = download(f"https://example.test/{failure}", "https://example.test/good")
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == PAYLOAD
    assert (folder / "cache" / DIGEST).read_bytes() == PAYLOAD
    assert len((folder / "curl.log").read_text().splitlines()) == 2


def test_verified_cache_avoids_network(downloader):
    download, folder = downloader
    assert download("https://example.test/good")[0].returncode == 0
    result, output = download("https://example.test/unavailable")
    assert result.returncode == 0 and output.read_bytes() == PAYLOAD
    assert len((folder / "curl.log").read_text().splitlines()) == 1


def test_corrupt_cache_is_replaced_only_after_verification(downloader):
    download, folder = downloader
    (folder / "cache").mkdir()
    (folder / "cache" / DIGEST).write_bytes(b"corrupt")
    result, _ = download("https://example.test/good")
    assert result.returncode == 0
    assert (folder / "cache" / DIGEST).read_bytes() == PAYLOAD


def test_failure_never_installs_or_caches_unverified_content(downloader):
    download, folder = downloader
    result, output = download("https://example.test/unavailable", "https://example.test/corrupt")
    assert result.returncode != 0
    assert not output.exists() and not (folder / "cache" / DIGEST).exists()
    assert "No verified engine archive" in result.stderr


def test_curl_has_bounded_timeouts_and_spaced_retries(downloader):
    download, folder = downloader
    assert download("https://example.test/good")[0].returncode == 0
    flags = (folder / "curl.log").read_text()
    for flag in [
        "--fail",
        "--max-time 120",
        "--retry 5",
        "--retry-delay 5",
        "--retry-max-time 180",
    ]:
        assert flag in flags
