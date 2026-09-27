import struct
import unittest

from feishu_patcher.arm64 import (
    decode_add_immediate,
    decode_adrp,
    find_string_xrefs,
    is_stack_allocation_prologue,
    nearest_function_start,
)


class Arm64Tests(unittest.TestCase):
    def test_known_update_watermark_reference(self):
        pc = 0x46F25D4
        adrp = 0xF005B301
        add = 0x912C4C21
        self.assertEqual(decode_adrp(adrp, pc), (1, 0xFD55000))
        self.assertEqual(decode_add_immediate(add), (1, 1, 0xB13))

    def test_prologue_detection(self):
        self.assertTrue(is_stack_allocation_prologue(0xD10603FF))
        self.assertTrue(is_stack_allocation_prologue(0xD10643FF))
        self.assertFalse(is_stack_allocation_prologue(0xD65F03C0))

    def test_xref_and_function_start(self):
        text_address = 0x1000
        data = bytearray(0x100)
        struct.pack_into("<I", data, 0x10, 0xD10103FF)  # sub sp, sp, #0x40
        struct.pack_into("<I", data, 0x20, 0x90000001)  # adrp x1, page(pc)
        struct.pack_into("<I", data, 0x24, 0x9100C021)  # add x1, x1, #0x30
        xrefs = find_string_xrefs(bytes(data), 0x1030, text_address, 0, len(data))
        self.assertEqual(xrefs, [0x1020])
        self.assertEqual(nearest_function_start(bytes(data), xrefs[0], text_address, 0), 0x1010)


if __name__ == "__main__":
    unittest.main()
