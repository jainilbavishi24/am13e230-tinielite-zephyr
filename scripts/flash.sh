#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
user_home="$(getent passwd "$(id -u)" | cut -d: -f6)"
uniflash_root="${TI_UNIFLASH_ROOT:-$user_home/ti/uniflash_9.7.0}"
dslite="${DSLITE_LINUX_PATH:-$uniflash_root/dslite.sh}"
hex_file="${1:-$repo_root/build/zephyr/zephyr.hex}"
ccxml="${CCXML_PATH:-$repo_root/config/AM13E23019_Zephyr.ccxml}"

for required in "$dslite" "$hex_file" "$ccxml"; do
    if [[ ! -e "$required" ]]; then
        echo "error: required file not found: $required" >&2
        exit 1
    fi
done

ccs_base="$uniflash_root/deskdb/content/TICloudAgent/linux/ccs_base"
common_bin="$ccs_base/common/bin"
debug_bin="$ccs_base/DebugServer/bin"

echo "Flashing and verifying with TI UniFlash/DSLite from WSL"
env TI_APPDATA_DIR="${TI_APPDATA_DIR:-$user_home/ti/appdata}" \
    LD_LIBRARY_PATH="$common_bin:$debug_bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    "$dslite" -c "$ccxml" -f -v -u -e "$hex_file"

echo "If READY does not appear, press the LaunchPad RESET button once."
