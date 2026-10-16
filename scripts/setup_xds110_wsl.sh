#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_rule="$repo_root/scripts/99-xds110-wsl.rules"
target_rule=/etc/udev/rules.d/99-xds110-wsl.rules

sudo install -m 0644 "$source_rule" "$target_rule"
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb --action=add
echo "Installed $target_rule. Reattach XDS110 with usbipd if permissions do not update."
