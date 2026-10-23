#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
explanation_dir="$repo_root/explanation"
source_dir="$explanation_dir/source"
chrome="${CHROME_BIN:-google-chrome}"
profile_dir="$(mktemp -d /tmp/am13e230-pdf-profile.XXXXXX)"

cleanup() {
    rm -rf -- "$profile_dir"
}
trap cleanup EXIT

for source in "$source_dir"/[0-9][0-9]_*.html; do
    name="$(basename -- "${source%.html}")"
    "$chrome" --headless --no-sandbox --disable-gpu \
        --disable-software-rasterizer --allow-file-access-from-files \
        --user-data-dir="$profile_dir" \
        --no-pdf-header-footer \
        --print-to-pdf="$explanation_dir/$name.pdf" \
        "file://$source"
done

printf 'Generated PDFs in %s\n' "$explanation_dir"

