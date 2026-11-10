# Host and probe configuration

| Directory | Contents |
|---|---|
| `debug/` | TI UniFlash/DSLite XDS110 target configuration used by `scripts/flash.sh` |
| `udev/` | Restricted XDS110 USB permission rule installed by `scripts/setup_xds110_wsl.sh` |

These files configure host-side access to the board. They are not Zephyr
firmware configuration; application Kconfig lives in `app/prj.conf` and the
board defaults live under `boards/`.
