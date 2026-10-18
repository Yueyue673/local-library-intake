import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import intake


def make_epub(path):
    """Entirely original synthetic content; ZIP order differs from reading order."""
    with zipfile.ZipFile(path, "w") as book:
        book.writestr("mimetype", "application/epub+zip")
        book.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OEBPS/package.opf"/></rootfiles></container>')
        book.writestr("OEBPS/package.opf", '''<package xmlns="http://www.idpf.org/2007/opf">
          <manifest><item id="one" href="one.xhtml" media-type="application/xhtml+xml"/>
          <item id="two" href="two.xhtml" media-type="application/xhtml+xml"/></manifest>
          <spine><itemref idref="one"/><itemref idref="two"/></spine></package>''')
        book.writestr("OEBPS/two.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>Chapter two</h1><p>A seed needs water.</p></body></html>')
        book.writestr("OEBPS/one.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Hidden book title</title><style>hidden-style</style></head><body><h1>Chapter one</h1><p>Original synthetic garden notes. 2 &lt; 3.</p><img src="https://example.invalid/pixel"/><script>hidden-script</script></body></html>')


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "input"
        self.source.mkdir()
        self.output = self.root / "output"

    def test_utf8_originals_preserved_and_repeat_outputs_identical(self):
        (self.source / "notes.md").write_bytes(b"\xef\xbb\xbf# Notes\r\nOriginal text.\r\n")
        initial = (self.source / "notes.md").read_bytes()
        first = intake.run(self.source, self.output)
        second = intake.run(self.source, self.root / "second")
        self.assertEqual(first, second)
        self.assertEqual((self.source / "notes.md").read_bytes(), initial)
        row = first[0]
        self.assertEqual((self.output / row["archive"]).read_bytes(), initial)
        self.assertEqual(row["archived_sha256"], hashlib.sha256(initial).hexdigest())
        self.assertEqual((self.output / row["text"]).read_bytes(), b"# Notes\nOriginal text.\n")
        self.assertEqual(json.loads((self.output / "manifest.json").read_text(encoding="utf-8")), first)

    def test_epub_reads_spine_and_omits_nontext_resources(self):
        make_epub(self.source / "garden.epub")
        rows = intake.run(self.source, self.output)
        self.assertEqual(rows[0]["status"], "converted")
        text = (self.output / rows[0]["text"]).read_text(encoding="utf-8")
        self.assertLess(text.index("Chapter one"), text.index("Chapter two"))
        self.assertIn("2 < 3", text)
        for hidden in ("hidden-script", "hidden-style", "Hidden book title", "example.invalid"):
            self.assertNotIn(hidden, text)

    def test_unsupported_file_archived_and_identified(self):
        (self.source / "not-a-real-pdf.pdf").write_bytes(b"Synthetic unsupported format, not a PDF")
        row = intake.run(self.source, self.output)[0]
        self.assertEqual(row["status"], "unsupported")
        self.assertTrue((self.output / row["archive"]).is_file())
        self.assertNotIn("text", row)

    def test_bad_book_is_error_and_does_not_hide_success(self):
        (self.source / "broken.epub").write_bytes(b"not an EPUB")
        (self.source / "good.txt").write_text("Valid original note.", encoding="utf-8")
        rows = intake.run(self.source, self.output)
        self.assertEqual([row["status"] for row in rows], ["error", "converted"])
        self.assertTrue(all(row["source_sha256"] == row["archived_sha256"] for row in rows))

    def test_invalid_utf8_is_reported_without_guessing(self):
        (self.source / "legacy.txt").write_bytes(b"caf\xe9")
        row = intake.run(self.source, self.output)[0]
        self.assertEqual(row["status"], "error")
        self.assertNotIn("text", row)

    def test_existing_or_nested_output_rejected(self):
        self.output.mkdir()
        marker = self.output / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        for target in (self.output, self.source / "nested", self.source):
            with self.assertRaises(ValueError):
                intake.run(self.source, target)
        self.assertEqual(marker.read_text(), "keep")

    def test_html_names_escaped_and_duplicate_basenames_kept_separate(self):
        (self.source / "a").mkdir()
        (self.source / "b").mkdir()
        (self.source / "a" / "same&name.txt").write_text("A", encoding="utf-8")
        (self.source / "b" / "same&name.txt").write_text("B", encoding="utf-8")
        rows = intake.run(self.source, self.output)
        self.assertNotEqual(rows[0]["archive"], rows[1]["archive"])
        self.assertEqual([(self.output / row["text"]).read_text() for row in rows], ["A", "B"])
        page = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertIn("same&amp;name.txt", page)

    def test_size_limit_fails_before_creating_output(self):
        (self.source / "a.txt").write_text("too long", encoding="utf-8")
        with patch.object(intake, "MAX_FILE_BYTES", 3):
            with self.assertRaises(ValueError):
                intake.run(self.source, self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
