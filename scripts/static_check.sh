#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

clang_format="${CLANG_FORMAT:-clang-format}"

find app/src drivers include soc tests/protocol/src -type f \
  \( -name '*.c' -o -name '*.h' \) -print0 | \
  xargs -0 "$clang_format" --dry-run --Werror

cppcheck --enable=warning,style,performance,portability \
  --error-exitcode=1 --inline-suppr --std=c11 \
  --suppress=missingIncludeSystem \
  app/src/*.c drivers/misc/tinyengine/*.c drivers/pinctrl/*.c \
  drivers/serial/*.c
