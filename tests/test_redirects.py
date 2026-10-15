"""Validate the complete retained book route set and fixed redirect scope."""
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]

class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.meta = {}
        self.links = {}
        self.anchors = []
        self.feed(source)
    def handle_starttag(self, tag, pairs):
        values = dict(pairs)
        if tag == "meta":
            self.meta.update({values.get("http-equiv", values.get("name")): values.get("content")})
        if tag == "link":
            self.links[values.get("rel")] = values.get("href")
        if tag == "a":
            self.anchors.append(values.get("href"))

class Redirects(unittest.TestCase):
    def test_all_retained_public_routes_have_fixed_same_origin_targets(self):
        routes = json.loads((ROOT / "tests/legacy-book-paths.json").read_text())
        self.assertEqual(len(routes), 23)
        self.assertIn("index.html", routes)
        self.assertIn("introduction.html", routes)
        self.assertEqual(sorted(p.name for p in (ROOT / "caboodle").glob("*.html")), routes)
        for name in routes:
            with self.subTest(name=name):
                source = (ROOT / "caboodle" / name).read_text()
                page = Page(source)
                target = "https://scbrown.github.io/tambo/" + name
                self.assertEqual(page.meta["refresh"], "0;url=" + target)
                self.assertEqual(page.meta["robots"], "noindex")
                self.assertEqual(page.links["canonical"], target)
                self.assertEqual(page.anchors, [target])
                self.assertEqual(urlsplit(target).netloc, "scbrown.github.io")
                self.assertIn('location.replace("' + target + '" + location.search + location.hash)', source)
                self.assertNotIn("document.write", source)
                self.assertNotIn("location.origin", source)


if __name__ == "__main__":
    unittest.main()
