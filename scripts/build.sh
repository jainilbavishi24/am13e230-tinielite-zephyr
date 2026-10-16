#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
west_bin="${WEST_BIN:-west}"
west_topdir="$("$west_bin" topdir)"
cmsis_dir="$west_topdir/modules/hal/cmsis"
cmsis6_dir="$west_topdir/modules/hal/cmsis_6"

for required_dir in "$cmsis_dir" "$cmsis6_dir"; do
    if [[ ! -d "$required_dir" ]]; then
        echo "error: required west module is missing: $required_dir" >&2
        echo "run 'west update cmsis cmsis_6' from $west_topdir" >&2
        exit 1
    fi
done

export ZEPHYR_TOOLCHAIN_VARIANT="${ZEPHYR_TOOLCHAIN_VARIANT:-gnuarmemb}"
export GNUARMEMB_TOOLCHAIN_PATH="${GNUARMEMB_TOOLCHAIN_PATH:-/usr}"

exec "$west_bin" build -p "${PRISTINE:-auto}" \
    -b lp_am13e230/am13e23019 \
    "$repo_root/app" \
    -d "$repo_root/build" \
    -- -DZEPHYR_MODULES="$repo_root;$cmsis_dir;$cmsis6_dir" "$@"
