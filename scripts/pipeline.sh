#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/3] Build"
PRISTINE=always "$repo_root/scripts/build.sh"
echo "[2/3] Flash"
"$repo_root/scripts/flash.sh"
echo "[3/3] Run all six hardware regression vectors"
"$repo_root/scripts/test.sh" "$@"
