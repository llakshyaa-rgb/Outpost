import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.install_kiwix import extract_source


class KiwixInstallerTests(unittest.TestCase):
    def test_extracts_build_inputs_and_excludes_unneeded_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive = base / "source.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("kiwix-js/package.json", "{}")
                bundle.writestr("kiwix-js/package-lock.json", "{}")
                bundle.writestr("kiwix-js/rollup.config.js", "export default {};")
                bundle.writestr("kiwix-js/babel.config.js", "module.exports = {};")
                bundle.writestr("kiwix-js/www/js/app.js", "/* app */")
                bundle.writestr("kiwix-js/i18n/en.json", "{}")
                bundle.writestr("kiwix-js/tests/large-fixture.bin", "not needed")
            source = base / "source"
            extract_source(archive, source)
            self.assertTrue((source / "babel.config.js").is_file())
            self.assertTrue((source / "www/js/app.js").is_file())
            self.assertTrue((source / "i18n/en.json").is_file())
            self.assertFalse((source / "tests/large-fixture.bin").exists())

    def test_rejects_parent_traversal_archive_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive = base / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("kiwix-js/www/../../escape.txt", "unsafe")
            with self.assertRaises(RuntimeError):
                extract_source(archive, base / "source")


if __name__ == "__main__":
    unittest.main()
