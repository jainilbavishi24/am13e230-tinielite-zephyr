# SPDX-License-Identifier: Apache-2.0

zephyr_library()
zephyr_library_sources_ifdef(CONFIG_PINCTRL_AM13E230X pinctrl_am13e230x.c)
