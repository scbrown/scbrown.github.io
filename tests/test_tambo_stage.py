"""Check the canonical book overlay without changing the personal homepage."""
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'tests/tambo-book-manifest.json').read_text())

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        self.urls += [v for k, v in attrs if k in ('href', 'src') and v]

class Book(unittest.TestCase):
    def test_all_23_canonical_targets_and_local_assets(self):
        self.assertEqual(len(MANIFEST['titles']), 23)
        for name, expected in MANIFEST['titles'].items():
            with self.subTest(name=name):
                page = ROOT / 'tambo' / name
                text = page.read_text()
                title = re.search(r'<title>(.*?)</title>', text, re.S | re.I)
                if expected is not None:
                    self.assertIsNotNone(title)
                    self.assertEqual(unescape(title.group(1).strip()), expected)
                else:
                    self.assertIn('class="chapter"', text)
                links = Links()
                links.feed(text)
                for url in links.urls:
                    path = urlsplit(url)
                    if path.scheme or path.netloc or not path.path or path.path.startswith('/'):
                        continue
                    target = (page.parent / unquote(path.path)).resolve()
                    self.assertTrue(target.is_relative_to((ROOT / 'tambo').resolve()), url)
                    self.assertTrue(target.is_file(), (name, url))

    def test_book_files_match_recorded_source_build(self):
        for name, expected in MANIFEST['files'].items():
            self.assertEqual(sha256((ROOT / 'tambo' / name).read_bytes()).hexdigest(), expected, name)

    def test_personal_files_unchanged(self):
        for name, expected in MANIFEST['personal_files'].items():
            self.assertEqual(sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)

if __name__ == '__main__':
    unittest.main()
