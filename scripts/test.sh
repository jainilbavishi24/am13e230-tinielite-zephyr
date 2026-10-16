#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON_BIN:-python3}"

selection=(--all)
for argument in "$@"; do
    if [[ "$argument" == "--index" || "$argument" == --index=* ||
          "$argument" == "--clock-status" ]]; then
        selection=()
        break
    fi
done

exec "$python_bin" "$repo_root/tools/send_tensor.py" "${selection[@]}" "$@"
