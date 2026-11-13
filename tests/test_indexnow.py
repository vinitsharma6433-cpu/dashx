import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import indexnow

XML = ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
       '<url><loc>https://x.test/</loc></url>'
       '<url><loc>https://x.test/blog/a</loc><lastmod>2026-11-11</lastmod></url>'
       '<url><loc>https://x.test/blog/b</loc><lastmod>2026-11-12</lastmod></url></urlset>')


class T(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(indexnow.parse_sitemap(XML), {"https://x.test/": "", "https://x.test/blog/a": "2026-11-11", "https://x.test/blog/b": "2026-11-12"})

    def test_first_run_submits_all(self):
        self.assertEqual(len(indexnow.pending(indexnow.parse_sitemap(XML), {})), 3)

    def test_only_new_or_changed(self):
        sm = indexnow.parse_sitemap(XML)
        state = {"https://x.test/": "", "https://x.test/blog/a": "2026-11-11", "https://x.test/blog/b": "2026-11-01"}
        self.assertEqual(indexnow.pending(sm, state), ["https://x.test/blog/b"])  # lastmod moved forward
        state["https://x.test/blog/b"] = "2026-11-12"
        self.assertEqual(indexnow.pending(sm, state), [])  # nothing new, nothing submitted

    def test_state_roundtrip_and_bad_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s", "indexnow.json")
            self.assertEqual(indexnow.load_state(p), {})
            indexnow.save_state(p, {"u": "2026-01-01"})
            self.assertEqual(indexnow.load_state(p), {"u": "2026-01-01"})
            open(p, "w").write("not json")
            self.assertEqual(indexnow.load_state(p), {})

    def test_payload(self):
        p = indexnow.payload("x.test", "abcdef123456", ["https://x.test/"])
        self.assertEqual(p["keyLocation"], "https://x.test/abcdef123456.txt")
        self.assertEqual(p["urlList"], ["https://x.test/"])


if __name__ == "__main__":
    unittest.main()
