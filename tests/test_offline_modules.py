import struct
import unittest

from outpost_modules.retrieval import match_expressions, split_sections
from outpost_modules.cyberdesk import analyze, carve, elf_header, pcap_summary, strings


class RetrievalTests(unittest.TestCase):
    def test_query_is_quoted_and_has_and_or_fallback(self):
        expressions = match_expressions('hello OR world "test"')
        self.assertEqual(len(expressions), 2)
        self.assertIn('"OR"', expressions[0])
        self.assertNotIn(" OR ", expressions[0])

    def test_split_sections_is_bounded_and_overlapping(self):
        chunks = split_sections(("a" * 900) + "\n\n" + ("b" * 900), 600, 80)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(len(chunk) <= 681 for chunk in chunks))


class CyberDeskTests(unittest.TestCase):
    def test_strings_and_hex(self):
        result = analyze("strings", b"\x00hello world\x00")
        self.assertEqual(result["strings"][0]["text"], "hello world")
        dump = analyze("hexdump", b"ABC")
        self.assertIn("41 42 43", dump["hexdump"][0])

    def test_signature_carving(self):
        found = carve(b"prefix" + b"%PDF-" + b"middle" + b"PK\x03\x04")
        self.assertEqual([x["format"] for x in found], ["PDF", "ZIP/APK/Office"])

    def test_elf64_header(self):
        raw = bytearray(64)
        raw[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<HHIQQQIHHHHHH", raw, 16, 2, 62, 1, 0x401000, 64, 0, 0, 64, 56, 0, 64, 0, 0)
        result = elf_header(bytes(raw))
        self.assertEqual(result["class"], 64)
        self.assertEqual(result["machine"], "x86-64")
        self.assertEqual(result["entry_point"], "0x401000")

    def test_pcap_decodes_ethernet_ipv4_udp(self):
        ethernet = bytes.fromhex("00112233445566778899aabb0800")
        ip = bytes.fromhex("4500001c0001000040110000c0a80102c0a80101")
        udp = bytes.fromhex("1f90003500080000")
        frame = ethernet + ip + udp
        record = struct.pack("<IIII", 1, 2, len(frame), len(frame)) + frame
        raw = bytes.fromhex("d4c3b2a1") + struct.pack("<HHiIII", 2, 4, 0, 0, 65535, 1) + record
        packet = pcap_summary(raw)["packet_samples"][0]
        self.assertEqual(packet["network"], "IPv4")
        self.assertEqual(packet["protocol"], "UDP")
        self.assertEqual(packet["source_port"], 8080)
        self.assertEqual(packet["destination_port"], 53)

    def test_pe_header_lists_section_metadata(self):
        raw = bytearray(512)
        raw[:2] = b"MZ"
        struct.pack_into("<I", raw, 0x3c, 0x80)
        raw[0x80:0x84] = b"PE\x00\x00"
        struct.pack_into("<HHIIIHH", raw, 0x84, 0x8664, 1, 0, 0, 0, 0xF0, 0x22)
        raw[0x98:0x9a] = b"\x0b\x02"
        raw[0x188:0x190] = b".text\x00\x00\x00"
        struct.pack_into("<IIII", raw, 0x190, 0x100, 0x1000, 0x200, 0x400)
        struct.pack_into("<I", raw, 0x1b0, 0x60000020)
        from outpost_modules.cyberdesk import pe_header
        section = pe_header(bytes(raw))["section_table"][0]
        self.assertEqual(section["name"], ".text")
        self.assertEqual(section["raw_size"], 0x200)

    def test_pcap_header(self):
        raw = b"\xd4\xc3\xb2\xa1" + struct.pack("<HHiIII", 2, 4, 0, 0, 65535, 1)
        result = pcap_summary(raw)
        self.assertEqual(result["format"], "PCAP")
        self.assertEqual(result["packets"], 0)


if __name__ == "__main__":
    unittest.main()
