import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
os.environ["SITE"] = "https://s.test"
import seo_health as h


class T(unittest.TestCase):
    def test_discount(self):
        self.assertEqual(h.discount_pct('<s>Rs. 600</s><span class="off">62% off</span>'), 62)
        self.assertEqual(h.discount_pct("<p>no discount</p>"), 0)

    def test_orphans(self):
        locs = ["https://s.test/", "https://s.test/blog", "https://s.test/blog/a", "https://s.test/p/x", "https://s.test/p/lonely"]
        links = {
            "https://s.test/": ["/blog", "/p/x", "https://s.test/blog/a#top"],
            "https://s.test/blog": ["/blog/a", "/"],
            "https://s.test/blog/a": ["/blog/a", "/p/x?ref=1"],   # self link does not count
            "https://s.test/p/x": ["/"],
            "https://s.test/p/lonely": ["/p/lonely"],
        }
        self.assertEqual(h.find_orphans(locs, links), ["https://s.test/p/lonely"])

    def test_page_collects_links(self):
        p = h.Page(); p.feed('<title>t</title><a href="/blog/a">x</a><a name="n">y</a>')
        self.assertEqual(p.links, ["/blog/a"])

    def test_issue_body(self):
        h.ISSUE_FILE = os.path.join(os.environ.get("TMPDIR", "/tmp"), "issue-test.md")
        h.write_issue_body({"time": "t"}, [{"check": "sitemap", "detail": "HTTP 500"}], [{"check": "w", "detail": ""}])
        s = open(h.ISSUE_FILE).read()
        self.assertIn("**sitemap**: HTTP 500", s); self.assertIn("### WARN", s)


if __name__ == "__main__":
    unittest.main()
