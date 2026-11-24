import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class OutpostCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.data = self.base / "data"
        self.data.mkdir()
        self.root = self.base / "shared"
        self.root.mkdir()
        self.knowledge = self.base / "knowledge"
        self.knowledge.mkdir()
        self.config = self.data / "config.json"
        self.db = self.data / "outpost.db"
        self.patches = [
            patch.object(app, "ROOT", self.base),
            patch.object(app, "DATA", self.data),
            patch.object(app, "DB", self.db),
            patch.object(app, "CONFIG", self.config),
        ]
        for item in self.patches:
            item.start()
        self.addCleanup(self.cleanup_patches)
        app.save_config({"index_roots": [str(self.root)]})
        app.init_db()

    def cleanup_patches(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_managed_path_allows_root_only_when_explicit(self):
        self.assertEqual(app.managed_path(str(self.root), allow_root=True), self.root)
        with self.assertRaises(ValueError):
            app.managed_path(str(self.root))

    def test_managed_path_allows_configured_file(self):
        target = self.root / "hello.txt"
        target.write_text("offline", encoding="utf-8")
        self.assertEqual(app.managed_path(str(target)), target)

    def test_managed_path_allows_outpost_zim_library(self):
        zim_root = self.data / "zim"
        zim_root.mkdir()
        archive = zim_root / "offline.zim"
        archive.write_bytes(b"ZIM")
        self.assertEqual(app.managed_path(str(archive)), archive)

    def test_managed_path_rejects_outside_file(self):
        outside = self.base / "private.txt"
        outside.write_text("no", encoding="utf-8")
        with self.assertRaises(ValueError):
            app.managed_path(str(outside))

    def test_managed_path_rejects_symlink(self):
        target = self.root / "real.txt"
        target.write_text("safe", encoding="utf-8")
        link = self.root / "alias.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are unavailable on this device")
        with self.assertRaises(ValueError):
            app.managed_path(str(link))

    def test_html_index_extracts_visible_text_only(self):
        page = self.root / "orbit.html"
        page.write_text("""<!doctype html>
<html><head><title>Orbit hidden title</title><style>.secret-css { color: red; }</style></head>
<body><h1>Orbit</h1><p>Searchable visible knowledge.</p>
<script>const secretScript = "do not index this";</script></body></html>""", encoding="utf-8")
        extracted = app.extract_document(page)
        self.assertIn("Orbit", extracted)
        self.assertIn("Searchable visible knowledge.", extracted)
        self.assertNotIn("secret-css", extracted)
        self.assertNotIn("secretScript", extracted)
        self.assertNotIn("<p>", extracted)
        result = app.index_files()
        self.assertGreaterEqual(result["indexed"], 1)
        with app.connect() as conn:
            row = conn.execute("SELECT content FROM documents WHERE path=?", (str(page),)).fetchone()
        self.assertIn("Searchable visible knowledge.", row["content"])
        self.assertNotIn("secretScript", row["content"])

    def test_index_and_remove_unselected_root(self):
        doc = self.root / "manual.md"
        doc.write_text("# Offline\nLocal search works.", encoding="utf-8")
        result = app.index_files()
        self.assertGreaterEqual(result["indexed"], 1)
        with app.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM documents WHERE path=?", (str(doc),)).fetchone()[0], 1)
        app.save_config({"index_roots": []})
        result = app.index_files()
        self.assertEqual(result["removed"], 1)
        with app.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM documents WHERE path=?", (str(doc),)).fetchone()[0], 0)

    def test_zim_header_validation_checks_signature_and_complete_header(self):
        header = bytearray(80)
        header[:4] = b"ZIM\\x04"
        struct.pack_into("<HH", header, 4, 6, 3)
        struct.pack_into("<II", header, 24, 1234, 56)
        parsed = app.parse_zim_header(header)
        self.assertTrue(parsed["valid_header"])
        self.assertEqual(parsed["version"], "6.3")
        self.assertEqual(parsed["articles"], 1234)
        self.assertIsNone(app.parse_zim_header(b"not a zim header".ljust(80, b" ")))
        self.assertIsNone(app.parse_zim_header(b"ZIM\\x04"))


if __name__ == "__main__":
    unittest.main()
