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

    def test_managed_path_allows_configured_file(self):
        target = self.root / "hello.txt"
        target.write_text("offline", encoding="utf-8")
        self.assertEqual(app.managed_path(str(target)), target)

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

    def test_index_and_remove_unselected_root(self):
        doc = self.root / "manual.md"
        doc.write_text("# Offline\nLocal search works.", encoding="utf-8")
        result = app.index_files()
        self.assertEqual(result["indexed"], 1)
        with app.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 1)
        app.save_config({"index_roots": []})
        result = app.index_files()
        self.assertEqual(result["removed"], 1)
        with app.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
