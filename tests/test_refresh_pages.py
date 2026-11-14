import json, os, random, re, sys, tempfile, unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import refresh_pages as rp
import trend_radar as tr

SITE = rp.SITE
TODAY = date(2026, 11, 23)
VOCAB = {
    "a": "rubber core felt cover diameter material build bounce grip softness stitching colour tournament lane ground practice school".split(),
    "b": "weight heavy light pack dozen carry bag team club coach session spare rotate store dry heat water mud cement".split(),
    "c": "yellow green red night evening floodlight visible spot dusk bright fade wash sun shade summer winter autumn".split(),
}


def para(kind, n=300, salt=0):
    """Deterministic pseudo-random text: the same (kind, salt) gives identical text, different ones share almost no 3-word phrases."""
    rnd = random.Random("%s-%s" % (kind, salt))
    w = VOCAB[kind]
    return " ".join(rnd.choice(w) + (str(i) if i % 5 == 0 else "") for i in range(n))


def blog_html(slug, title="A good guide title for a ball", desc=None, body=None, guides=("one", "two"), products=("p-one",), words=300, kind="a", salt=0):
    desc = desc if desc is not None else "d" * 140
    body = body if body is not None else para(kind, words, salt)
    g = "".join('<li><a href="/blog/%s">g</a></li>' % s for s in guides)
    p = "".join('<li><a href="/p/%s">p</a></li>' % s for s in products)
    return ('<!doctype html><html><head><title>%s</title><meta name="description" content="%s"></head><body>'
            '<p><a href="/">Shop</a> | <a href="/blog">Blog</a></p><h1>%s</h1><p>%s</p>'
            '<h2>Related guides</h2><ul>%s</ul><h2>DASHX balls mentioned in this guide</h2><ul>%s</ul>'
            '<nav><a href="/returns">Returns</a> shipping privacy terms contact</nav></body></html>') % (title, desc, title, body, g, p)


def sitemap(slugs, extra=()):
    locs = ["<url><loc>%s/blog/%s</loc><lastmod>2026-11-%02d</lastmod></url>" % (SITE, s, 10 + i) for i, s in enumerate(slugs)]
    locs += ["<url><loc>%s%s</loc></url>" % (SITE, e) for e in extra]
    return '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(locs) + "</urlset>"


def fake_site(pages, extra=None):
    """pages: {slug: html}; extra: {path: html}. Returns (get, sitemap_xml)."""
    htmls = {SITE + "/blog/" + s: h for s, h in pages.items()}
    for path, h in (extra or {}).items():
        htmls[SITE + path] = h
    xml = sitemap(list(pages), list((extra or {}).keys()))

    def get(url, **k):
        return (200, {}, htmls[url]) if url in htmls else (404, {}, "")
    return get, xml


GOOD = {"red-guide": blog_html("red-guide", kind="a", salt=0), "green-guide": blog_html("green-guide", kind="b", salt=3), "yellow-guide": blog_html("yellow-guide", kind="c", salt=5)}


class Reading(unittest.TestCase):
    def test_article_text_drops_the_render_time_blocks_and_nav(self):
        t = rp.article_text(blog_html("x", body="alpha beta gamma"))
        self.assertEqual(t.split()[-3:], ["alpha", "beta", "gamma"])
        self.assertNotIn("Related", t)
        self.assertNotIn("Returns", t)
        self.assertNotIn("shipping", t)

    def test_overlap_numbers(self):
        a = "the quick brown fox jumps over the lazy dog again and again"
        self.assertEqual(rp.overlap(a, a), 1.0)
        self.assertEqual(rp.overlap(a, "completely different words about tennis balls and weights"), 0.0)
        self.assertEqual(rp.overlap("", a), 0.0)


class Audit(unittest.TestCase):
    def audit(self, pages, extra=None):
        get, xml = fake_site(pages, extra)
        return rp.audit(rp.load_pages(get, xml))

    def rules(self, findings, slug=None):
        return sorted(f["rule"] for f in findings if slug is None or f.get("slug") == slug)

    def test_healthy_site_has_no_findings(self):
        self.assertEqual(self.audit(GOOD), [])

    def test_thin_page(self):
        f = self.audit(dict(GOOD, thin=blog_html("thin", words=60, kind="c", salt=9)))
        self.assertEqual(self.rules(f, "thin"), ["thin"])

    def test_weak_links(self):
        f = self.audit(dict(GOOD, nolinks=blog_html("nolinks", guides=("one",), products=(), kind="c", salt=11)))
        self.assertEqual(self.rules(f, "nolinks"), ["weak_links"])
        self.assertIn("1 related guides and 0 product links", f[0]["detail"])

    def test_self_link_does_not_count_as_a_related_guide(self):
        f = self.audit(dict(GOOD, selfie=blog_html("selfie", guides=("selfie", "one"), kind="c", salt=13)))
        self.assertEqual(self.rules(f, "selfie"), ["weak_links"])

    def test_title_and_meta(self):
        f = self.audit(dict(GOOD, long=blog_html("long", title="T" * 61, desc="short", kind="c", salt=15)))
        self.assertEqual(self.rules(f, "long"), ["meta", "title"])

    def test_non_blog_pages_are_reported_but_have_no_slug(self):
        prod = '<html><head><title>%s</title></head><body><h1>x</h1></body></html>' % ("P" * 70)
        f = self.audit(GOOD, extra={"/p/some-ball": prod})
        self.assertEqual([(x["rule"], x.get("slug")) for x in f], [("title", None)])

    def test_overlap_tells_the_newer_post_to_differentiate(self):
        same = para("a", 300, salt=40)
        pages = dict(GOOD)
        pages["old-weights"] = blog_html("old-weights", body=same)
        pages["new-weights"] = blog_html("new-weights", body=same + " plus a few new words here")
        get, xml = fake_site(pages)
        f = [x for x in rp.audit(rp.load_pages(get, xml)) if x["rule"] == "overlap"]
        self.assertEqual(len(f), 1)
        self.assertEqual((f[0]["slug"], f[0]["other"]), ("new-weights", "old-weights"))     # sitemap lastmod: the later one is newer
        self.assertGreater(f[0]["priority"], rp.PRIORITY["overlap"])

    def test_overlap_table_lists_the_closest_pairs(self):
        pages = dict(GOOD, twin=blog_html("twin", body=para("a", 300, salt=0)))
        get, xml = fake_site(pages)
        top = rp.overlap_table(rp.load_pages(get, xml))
        self.assertEqual({top[0]["a"], top[0]["b"]}, {"red-guide", "twin"})
        self.assertEqual(top[0]["overlap"], 1.0)


class Tasks(unittest.TestCase):
    F = lambda self, slug, rule, pr, **k: dict({"rule": rule, "page": SITE + "/blog/" + slug, "slug": slug, "detail": rule + " problem", "priority": pr}, **k)
    KW = [{"keyword": "red tennis ball cricket", "target_page": "/blog/red-tennis-ball-cricket-110g", "trend_score": 80}]

    def test_strongest_finding_per_page_and_priority_order(self):
        findings = [self.F("red-tennis-ball-cricket-110g", "meta", 20), self.F("red-tennis-ball-cricket-110g", "thin", 70), self.F("light-tennis-ball-cricket-90g", "title", 50)]
        q, added, _ = rp.build_tasks(findings, [], self.KW, TODAY)
        self.assertEqual([t["target_page"] for t in added], ["/blog/red-tennis-ball-cricket-110g", "/blog/light-tennis-ball-cricket-90g"])
        self.assertEqual(added[0]["source"], "refresh:thin")                 # thin (70) beat meta (20) for the same page
        self.assertEqual(added[0]["keyword"], "red tennis ball cricket")     # radar keyword for that page
        self.assertEqual(added[1]["keyword"], "light tennis ball cricket")   # no radar keyword: built from the slug, 90g dropped

    def test_at_most_three_tasks_per_run(self):
        findings = [self.F("page-%d-tennis-ball" % i, "thin", 70 - i) for i in range(6)]
        q, added, skipped = rp.build_tasks(findings, [], [], TODAY)
        self.assertEqual(len(added), 3)
        self.assertEqual(len(skipped), 3)
        self.assertTrue(all(s[1] == "weekly cap" for s in skipped))

    def test_one_intent_per_page_with_the_existing_queue(self):
        queue = [{"id": "radar", "type": "update", "keyword": "cricket tennis ball weight", "target_page": "/blog/cricket-tennis-ball-weights-packs-variants", "status": "queued"}]
        q, added, skipped = rp.build_tasks([self.F("cricket-tennis-ball-weights-packs-variants", "overlap", 80)], queue, [], TODAY)
        self.assertEqual((added, q), ([], queue))
        self.assertEqual(skipped, [("cricket-tennis-ball-weights-packs-variants", "already has a queued task")])

    def test_existing_queue_entries_are_kept_untouched(self):
        queue = [{"id": "keep", "type": "new", "keyword": "tennis ball care", "target_page": "", "status": "queued"}, {"id": "old", "status": "done"}]
        q, added, _ = rp.build_tasks([self.F("red-tennis-ball-cricket-110g", "thin", 70)], queue, self.KW, TODAY)
        self.assertEqual(q[:2], queue)
        self.assertEqual(len(q), 3)

    def test_tasks_fit_what_autopilot_f2_expects(self):
        d = self.F("red-tennis-ball-cricket-110g", "overlap", 70, other="light-tennis-ball-cricket-90g", focus="links+title")
        _, added, _ = rp.build_tasks([d], [], self.KW, TODAY)
        t = added[0]
        self.assertEqual((t["type"], t["language"], t["status"]), ("update", "en", "queued"))
        self.assertRegex(t["target_page"], r"^/blog/[a-z0-9-]+$")
        self.assertRegex(t["keyword"], r"^[a-z0-9][a-z0-9 ,'()+/.&-]{2,79}$")      # the keyword check autopilot.py applies
        self.assertTrue(tr.keyword_ok(t["keyword"]))
        self.assertEqual((t["differentiate_from"], t["focus"]), ("/blog/light-tennis-ball-cricket-90g", "links+title"))
        for k in ("id", "type", "keyword", "language", "intent", "cluster", "target_page", "source", "trend_score", "added", "status"):
            self.assertIn(k, t)

    def test_page_without_an_on_topic_keyword_is_skipped(self):
        q, added, skipped = rp.build_tasks([self.F("kit", "thin", 70)], [], [], TODAY)
        self.assertEqual((added, skipped), ([], [("kit", "no on-topic keyword")]))


class SearchConsole(unittest.TestCase):
    P = SITE + "/blog/red-guide"

    def row(self, **k):
        return dict({"query": "red tennis ball", "page": self.P, "clicks": 1, "impressions": 50, "position": 12.0}, **k)

    def pages(self):
        get, xml = fake_site(GOOD)
        return rp.load_pages(get, xml)

    def test_position_8_to_20_means_refresh(self):
        f, _ = rp.gsc_findings([self.row()], self.pages(), [], TODAY, ["red-guide"])
        self.assertEqual([(x["rule"], x["focus"]) for x in f], [("gsc_position", "links+title")])
        f, _ = rp.gsc_findings([self.row(position=3.0), self.row(position=40.0)], self.pages(), [], TODAY, ["red-guide"])
        self.assertEqual([x["rule"] for x in f if x["rule"] == "gsc_position"], [])

    def test_low_ctr_rewrites_one_variant_at_a_time(self):
        rows = [self.row(impressions=500, clicks=3, position=3.0)]
        f, _ = rp.gsc_findings(rows, self.pages(), [], TODAY, ["red-guide"])
        self.assertEqual([x["rule"] for x in f], ["gsc_ctr"])
        recent = [{"page": self.P, "date": "2026-11-10"}]                      # a variant went live 13 days ago: wait and measure it
        f, _ = rp.gsc_findings(rows, self.pages(), recent, TODAY, ["red-guide"])
        self.assertEqual(f, [])
        old = [{"page": self.P, "date": "2026-10-01"}]
        f, _ = rp.gsc_findings(rows, self.pages(), old, TODAY, ["red-guide"])
        self.assertEqual([x["rule"] for x in f], ["gsc_ctr"])

    def test_no_impressions_after_90_days(self):
        get, xml = fake_site(GOOD)
        xml = xml.replace("2026-11-10", "2026-06-01")
        pages = rp.load_pages(get, xml)
        f, _ = rp.gsc_findings([self.row(page=SITE + "/blog/green-guide")], pages, [], TODAY, ["red-guide", "green-guide", "yellow-guide"])
        self.assertEqual([(x["slug"], x["rule"]) for x in f if x["rule"] == "gsc_no_impressions"], [("red-guide", "gsc_no_impressions")])

    def test_query_with_impressions_and_no_page_becomes_a_new_topic_if_on_topic(self):
        rows = [{"query": "Tennis Ball Care", "page": "", "impressions": 40, "clicks": 0, "position": 30},
                {"query": "tennis ball price", "page": "", "impressions": 90, "clicks": 0, "position": 30},
                {"query": "tennis ball care", "page": "", "impressions": 5, "clicks": 0, "position": 30}]
        _, topics = rp.gsc_findings(rows, self.pages(), [], TODAY, [])
        self.assertEqual({t["keyword"] for t in topics}, {"tennis ball care"})      # 'price' is dropped by the radar keyword rule
        q, added = rp.new_topic_tasks(topics, [], TODAY, 2)
        self.assertEqual((len(added), added[0]["source"]), (1, "refresh:gsc_query_without_page"))


class Run(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, name):
        return json.load(open(os.path.join(self.d, name), encoding="utf-8"))

    def test_full_run_adds_tasks_and_writes_the_report(self):
        pages = dict(GOOD, **{"red-thin-tennis-ball": blog_html("red-thin-tennis-ball", words=40, kind="c", salt=21)})
        get, xml = fake_site(pages)
        self.assertEqual(rp.run(TODAY, get, self.d, xml, warm=False), 0)
        q, rep = self.read("topic_queue.json"), self.read("refresh_report.json")
        self.assertEqual([t["target_page"] for t in q], ["/blog/red-thin-tennis-ball"])
        self.assertEqual(rep["search_console"], "no data (data/gsc_queries.json missing)")
        self.assertEqual(rep["blog_pages"], 4)
        self.assertIn("overlap_top", rep)

    def test_running_twice_does_not_add_a_second_task_for_the_same_page(self):
        pages = dict(GOOD, **{"red-thin-tennis-ball": blog_html("red-thin-tennis-ball", words=40, kind="c", salt=21)})
        get, xml = fake_site(pages)
        rp.run(TODAY, get, self.d, xml, warm=False)
        rp.run(date(2026, 11, 30), get, self.d, xml, warm=False)
        self.assertEqual(len(self.read("topic_queue.json")), 1)

    def test_pause_file_changes_nothing(self):
        open(os.path.join(self.d, "PAUSE_AUTOPILOT"), "w").close()
        get, xml = fake_site(GOOD)
        self.assertEqual(rp.run(TODAY, get, self.d, xml, warm=False), 0)
        self.assertEqual(os.listdir(self.d), ["PAUSE_AUTOPILOT"])

    def test_unreadable_site_fails_red_and_writes_nothing(self):
        self.assertEqual(rp.run(TODAY, lambda url, **k: (500, {}, ""), self.d, None, warm=False), 1)
        self.assertEqual(os.listdir(self.d), [])

    def test_too_few_blog_pages_is_not_trusted(self):
        get, xml = fake_site({"red-guide": GOOD["red-guide"]})
        self.assertEqual(rp.run(TODAY, get, self.d, xml, warm=False), 1)
        self.assertEqual(os.listdir(self.d), [])

    def test_gsc_file_is_used_when_present(self):
        json.dump([{"query": "red tennis ball", "page": SITE + "/blog/red-guide", "clicks": 1, "impressions": 50, "position": 12.0}], open(os.path.join(self.d, "gsc_queries.json"), "w"))
        json.dump([{"keyword": "red tennis ball cricket", "target_page": "/blog/red-guide", "trend_score": 70}], open(os.path.join(self.d, "keywords.json"), "w"))
        get, xml = fake_site(GOOD)
        rp.run(TODAY, get, self.d, xml, warm=False)
        t = self.read("topic_queue.json")[0]
        self.assertEqual((t["source"], t["focus"], t["keyword"]), ("refresh:gsc_position", "links+title", "red tennis ball cricket"))
        self.assertEqual(self.read("refresh_report.json")["search_console"], "used")

    def test_ctr_rewrite_is_logged_as_a_variant(self):
        json.dump([{"query": "red tennis ball", "page": SITE + "/blog/red-guide", "clicks": 2, "impressions": 500, "position": 3.0}], open(os.path.join(self.d, "gsc_queries.json"), "w"))
        json.dump([{"keyword": "red tennis ball cricket", "target_page": "/blog/red-guide", "trend_score": 70}], open(os.path.join(self.d, "keywords.json"), "w"))
        get, xml = fake_site(GOOD)
        rp.run(TODAY, get, self.d, xml, warm=False)
        v = self.read("variants_log.json")
        self.assertEqual((len(v), v[0]["page"], v[0]["date"]), (1, SITE + "/blog/red-guide", "2026-11-23"))


if __name__ == "__main__":
    unittest.main()
