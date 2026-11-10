/* SPDX-License-Identifier: Apache-2.0 */

#include <stddef.h>

/*
 * TI Arm Clang may emit this standard Arm EABI helper when lowering an
 * aligned zero-fill. Zephyr's minimal libc configuration does not provide
 * the symbol, so keep a small freestanding implementation in the app.
 */
void __aeabi_memclr4(void *destination, size_t byte_count)
{
	volatile unsigned char *cursor = destination;

	while (byte_count != 0U) {
		*cursor = 0U;
		cursor++;
		byte_count--;
	}
}
