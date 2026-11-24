import tempfile
import unittest
from pathlib import Path

from outpost_modules.wiki_compact import _clean_wikitext, _enforce_database_limit, article, import_dump, search, stats
from unittest.mock import patch


class WikiCompactTests(unittest.TestCase):
    def test_cleaner_keeps_article_text_and_curated_image_references(self):
        text, images = _clean_wikitext(
            "The Earth is a planet. [[File:Earth_diagram.png|thumb]] "
            "It orbits the Sun. {{cite web|title=ignored}}"
        )
        self.assertIn("Earth is a planet", text)
        self.assertIn("orbits the Sun", text)
        self.assertEqual(images, ["Earth diagram.png"])
        self.assertNotIn("cite web", text)

    def test_database_storage_limit_is_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "wiki.db"
            db.write_bytes(b"x" * 20)
            with patch("outpost_modules.wiki_compact.MAX_WIKI_DB_BYTES", 10):
                with self.assertRaises(ValueError):
                    _enforce_database_limit(str(db))

    def test_stream_import_search_and_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dump = root / "sample.xml"
            db = root / "wiki.db"
            dump.write_text("""<?xml version="1.0"?>
<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">
<page><title>Earth</title><ns>0</ns><revision><text>The Earth is a rocky planet orbiting the Sun. It has one natural satellite, the Moon. [[File:Earth_diagram.png|thumb]]</text></revision></page>
<page><title>Category:Planets</title><ns>14</ns><revision><text>ignored namespace</text></revision></page>
</mediawiki>""", encoding="utf-8")
            result = import_dump(str(dump), str(db))
            self.assertEqual(result["articles_saved"], 1)
            self.assertGreater(result["size_bytes"], 0)
            self.assertTrue(stats(str(db))["ready"])
            rows = search(str(db), "rocky planet")
            self.assertEqual(rows[0]["title"], "Earth")
            item = article(str(db), rows[0]["id"])
            self.assertIn("orbiting the Sun", item["body"])
            self.assertEqual(item["images"], ["Earth diagram.png"])

    def test_failed_import_preserves_previous_library(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            good = root / "good.xml"
            bad = root / "broken.xml"
            db = root / "wiki.db"
            good.write_text("""<?xml version="1.0"?>
<mediawiki><page><title>Earth</title><ns>0</ns><revision><text>The Earth is a rocky planet orbiting the Sun and has a natural satellite called the Moon.</text></revision></page></mediawiki>""", encoding="utf-8")
            import_dump(str(good), str(db))
            before = search(str(db), "rocky planet")
            self.assertEqual(before[0]["title"], "Earth")
            bad.write_text("<mediawiki><page>", encoding="utf-8")
            with self.assertRaises(Exception):
                import_dump(str(bad), str(db))
            after = search(str(db), "rocky planet")
            self.assertEqual(after[0]["title"], "Earth")


if __name__ == "__main__":
    unittest.main()
