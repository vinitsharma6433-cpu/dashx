import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import seo_checks as sc

SITE = sc.SITE
HOME = SITE + "/"
BLOG = SITE + "/blog/red-guide"
PROD = SITE + "/p/dashx-red"
GOOD = ('<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width"><meta property="og:image" content="https://x/i.png">'
        '<link rel="icon" href="/f.ico"><link rel="canonical" href="https://x/"><script type="application/ld+json">{"@graph":[{"@type":"BreadcrumbList"},{"@type":"FAQPage"}]}</script>'
        '</head><body><h1>Title</h1><img src="a.png" alt="a ball" width="600"><a href="/blog/one">One guide</a><a href="/blog/two">Two guide</a>'
        '<a href="/p/dashx-red">DASHX Red ball</a></body></html>')
BAD = '<html><head></head><body><h1>A</h1><h1>B</h1><img src="a.png"><a href="/blog/one">click here</a></body></html>'


def check(type, params, scope="all", id="test-check"):
    return {"id": id, "type": type, "params": params, "scope": scope, "level": "WARN"}


def run_one(c, html, url=BLOG, headers=None):
    d = sc.Doc()
    d.feed(html)
    return sc.run_check(c, d, headers or {}, url)


class Validation(unittest.TestCase):
    def test_good_entries(self):
        for c in [check("meta_present", {"attr": "name", "value": "viewport"}), check("html_lang_present", {}), check("img_attr_ratio", {"attr": "alt", "min": 1}),
                  check("h1_count", {"equals": 1}), check("jsonld_type", {"any_of": ["BreadcrumbList", "Product"]}), check("links_min", {"prefix": "/blog/", "min": 2}),
                  check("text_absent", {"phrases": ["click here"]}), check("link_rel_present", {"rel": "icon"}), check("header_present", {"name": "Referrer-Policy"})]:
            self.assertIsNone(sc.validate(c), c)

    def test_bad_entries_are_refused(self):
        bad = [None, "x", {}, dict(check("meta_present", {"attr": "name", "value": "viewport"}), id="Bad Id"), dict(check("html_lang_present", {}), id="x"),
               check("run_python", {}), check("regex_match", {"pattern": ".*"}), dict(check("html_lang_present", {}), level="FAIL"), dict(check("html_lang_present", {}), level="ERROR"),
               check("html_lang_present", {}, scope="admin"), check("meta_present", {"attr": "http-equiv", "value": "x"}), check("meta_present", {"attr": "name", "value": "a b; rm -rf /"}),
               check("header_present", {"name": "X; curl evil"}), check("img_attr_ratio", {"attr": "src", "min": 1}), check("img_attr_ratio", {"attr": "alt", "min": 5}),
               check("h1_count", {"equals": 50}), check("h1_count", {"equals": True}), check("jsonld_type", {"any_of": []}), check("jsonld_type", {"any_of": ["a" * 50]}),
               check("jsonld_type", {"any_of": ["Product"] * 9}), check("links_min", {"prefix": "https://evil", "min": 1}), check("links_min", {"prefix": "/blog/", "min": 99}),
               check("text_absent", {"phrases": ["ab"]}), check("text_absent", {"phrases": "click here"}), check("link_rel_present", {"rel": "stylesheet"}), check("meta_present", "viewport")]
        for c in bad:
            self.assertIsNotNone(sc.validate(c), c)

    def test_no_entry_can_carry_code_or_a_regex(self):
        self.assertEqual(sorted(sc.TYPES), sorted(["header_present", "meta_present", "html_lang_present", "img_attr_ratio", "h1_count", "jsonld_type", "links_min", "text_absent", "link_rel_present"]))
        src = open(sc.__file__, encoding="utf-8").read()
        for forbidden in ("eval(", "exec(", "subprocess", "os.system", "__import__", "pickle"):
            self.assertNotIn(forbidden, src)


class Checks(unittest.TestCase):
    def test_page_kind(self):
        self.assertEqual([sc.page_kind(u) for u in (HOME, SITE, BLOG, PROD, SITE + "/blog", SITE + "/returns")], ["home", "home", "blog", "product", "other", "other"])

    def test_meta_lang_h1(self):
        self.assertTrue(run_one(check("meta_present", {"attr": "name", "value": "viewport"}), GOOD)[0])
        self.assertFalse(run_one(check("meta_present", {"attr": "name", "value": "viewport"}), BAD)[0])
        self.assertTrue(run_one(check("meta_present", {"attr": "property", "value": "og:image"}), GOOD)[0])
        self.assertTrue(run_one(check("html_lang_present", {}), GOOD)[0])
        self.assertFalse(run_one(check("html_lang_present", {}), BAD)[0])
        self.assertTrue(run_one(check("h1_count", {"equals": 1}), GOOD)[0])
        self.assertEqual(run_one(check("h1_count", {"equals": 1}), BAD), (False, "2 <h1> (want 1)"))

    def test_images(self):
        self.assertTrue(run_one(check("img_attr_ratio", {"attr": "alt", "min": 1}), GOOD)[0])
        self.assertEqual(run_one(check("img_attr_ratio", {"attr": "alt", "min": 1}), BAD), (False, "0 of 1 images have alt"))
        self.assertTrue(run_one(check("img_attr_ratio", {"attr": "alt", "min": 1}), "<html><body>no images</body></html>")[0])
        self.assertTrue(run_one(check("img_attr_ratio", {"attr": "width", "min": 1}), GOOD)[0])

    def test_jsonld_links_text_rel_header(self):
        self.assertTrue(run_one(check("jsonld_type", {"any_of": ["FAQPage"]}), GOOD)[0])
        self.assertFalse(run_one(check("jsonld_type", {"any_of": ["Product"]}), GOOD)[0])
        self.assertTrue(run_one(check("links_min", {"prefix": "/blog/", "min": 2}), GOOD)[0])
        self.assertFalse(run_one(check("links_min", {"prefix": "/blog/", "min": 2}), BAD)[0])
        self.assertTrue(run_one(check("links_min", {"prefix": "/p/", "min": 1}), GOOD)[0])
        self.assertFalse(run_one(check("links_min", {"prefix": "/p/", "min": 1}), GOOD, url=PROD)[0])          # a page's own link does not count
        self.assertTrue(run_one(check("text_absent", {"phrases": ["click here"]}), GOOD)[0])
        self.assertEqual(run_one(check("text_absent", {"phrases": ["click here"]}), BAD), (False, "link text uses: click here"))
        self.assertTrue(run_one(check("link_rel_present", {"rel": "icon"}), GOOD)[0])
        self.assertFalse(run_one(check("link_rel_present", {"rel": "icon"}), BAD)[0])
        self.assertTrue(run_one(check("header_present", {"name": "referrer-policy"}), GOOD, headers={"Referrer-Policy": "origin"})[0])
        self.assertFalse(run_one(check("header_present", {"name": "Referrer-Policy"}), GOOD, headers={})[0])


class Catalog(unittest.TestCase):
    def test_scope_and_other_pages(self):
        pages = {HOME: ({}, BAD), BLOG: ({}, BAD), SITE + "/returns": ({}, BAD)}
        rows, ignored = sc.run_catalog(pages, [check("html_lang_present", {}, scope="blog", id="lang-blog")])
        self.assertEqual([(r["check"], r["url"]) for r in rows], [("lang-blog", BLOG)])
        self.assertEqual(ignored, [])

    def test_invalid_entries_are_ignored_and_never_run(self):
        rows, ignored = sc.run_catalog({BLOG: ({}, GOOD)}, [check("run_python", {"code": "x"}, id="evil-one"), "junk", check("html_lang_present", {})])
        self.assertEqual(rows, [])
        self.assertEqual(len(ignored), 2)
        self.assertIn("evil-one: type is not in the fixed list", ignored)

    def test_shipped_files_are_valid(self):
        base = os.path.join(os.path.dirname(__file__), "..", "data")
        cat = json.load(open(os.path.join(base, "seo_checks.json"), encoding="utf-8"))["checks"]
        ideas = json.load(open(os.path.join(base, "seo_scout_ideas.json"), encoding="utf-8"))["ideas"]
        self.assertEqual([sc.validate(c) for c in cat], [None] * len(cat))
        ids = [i["id"] for i in ideas]
        self.assertEqual(len(ids), len(set(ids)))
        for i in ideas:
            self.assertIsNone(sc.validate(dict(i["check"], id=i["id"])), i["id"])
            self.assertEqual(i["check"]["level"], "WARN")
            self.assertEqual(i["target"], "data/seo_checks.json")
        for c in cat:
            self.assertEqual(c["level"], "WARN")


class Main(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        os.environ["REPORT"] = os.path.join(self.d, "report.json")

    def tearDown(self):
        os.environ.pop("REPORT", None)
        self.tmp.cleanup()

    def site(self):
        pages = {BLOG: BAD, HOME: GOOD}
        xml = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join("<url><loc>%s</loc></url>" % u for u in pages) + "</urlset>"
        return (lambda url, **k: (200, {"Cache-Control": "x"}, pages[url]) if url in pages else (404, {}, "")), xml

    def test_report_only_run_never_fails(self):
        json.dump({"checks": [check("html_lang_present", {}, id="lang"), check("meta_present", {"attr": "name", "value": "viewport"}, id="viewport")]}, open(os.path.join(self.d, "seo_checks.json"), "w"))
        get, xml = self.site()
        self.assertEqual(sc.main(get, self.d, xml, warm=False), 0)
        rep = json.load(open(os.environ["REPORT"]))
        self.assertEqual((rep["warn"], rep["pages"], rep["checks"]), (2, 2, 2))
        self.assertEqual({r["check"] for r in rep["rows"]}, {"lang", "viewport"})

    def test_unreadable_site_is_not_a_failure(self):
        self.assertEqual(sc.main(lambda url, **k: (500, {}, ""), self.d, None, warm=False), 0)

    def test_pause_file(self):
        open(os.path.join(self.d, "PAUSE_AUTOPILOT"), "w").close()
        get, xml = self.site()
        self.assertEqual(sc.main(get, self.d, xml, warm=False), 0)
        self.assertFalse(os.path.exists(os.environ["REPORT"]))


if __name__ == "__main__":
    unittest.main()
