"""npm run queue: eligibility, banned words, slots, append-only queue.json, STOP_QUEUE, and a full run against a local bare git remote
(nothing here touches GitHub, the poster or the real dashx repo)."""
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory import queue  # noqa: E402

IST = queue.IST
CFG = {**queue.DEFAULTS}
GOOD_QC = lambda name: {"score": 100.0, "passed": True, "checks": [], "failed": []}  # noqa: E731

OLD_ENTRY = {"title": "old DASHX", "yt_title": "Old", "media": "https://example.test/social/old.mp4", "when": "2026-10-30T19:26:55.417201+05:30",
             "networks": ["youtube"], "caption": "c", "captions": {"youtube": "c"}, "status": "done", "results": {"youtube": {"ok": True}}}


def seo(title="छींक | गली क्रिकेट | DASHX", extra=""):
    desc = (f"छींक! दादाजी ने कैच पकड़ लिया!{extra}\n\nगली क्रिकेट की मज़ेदार कहानी। DASHX by Nav Durga Sports, Meerut.\n\n"
            "Amazon: https://www.amazon.in/dp/B0H4QG8FKG\nFlipkart: https://dl.flipkart.com/dl/product/p/itme?pid=BALHZ5DAYUNTZD82&lid=LSTBALHZ5DAYUNTZD82W6Z0R4\n\n#DASHX #GaliCricket #Shorts")
    return {"title": title, "description": desc, "hashtags": ["#DASHX", "#GaliCricket", "#Shorts"]}


class TestSlots(unittest.TestCase):
    def at(self, y, m, d, h, mi):
        return dt.datetime(y, m, d, h, mi, tzinfo=IST)

    def test_two_slots_per_day_in_order_and_lead_time(self):
        now = self.at(2026, 10, 30, 11, 0)
        got = queue.free_slots([], now, CFG, 5)
        self.assertEqual([g[:16] for g in got], ["2026-10-30T12:30", "2026-10-30T20:30", "2026-10-31T12:30", "2026-10-31T20:30", "2026-11-01T12:30"])
        self.assertTrue(all(g.endswith("+05:30") for g in got))
        # 12:30 is less than 30 minutes away -> not offered
        self.assertEqual(queue.free_slots([], self.at(2026, 10, 30, 12, 10), CFG, 1)[0][:16], "2026-10-30T20:30")

    def test_taken_slots_are_skipped(self):
        now = self.at(2026, 10, 30, 8, 0)
        taken = ["2026-10-30T12:35:00+05:30", "2026-10-31T20:30:00+05:30"]
        got = queue.free_slots(taken, now, CFG, 3)
        self.assertEqual([g[:16] for g in got], ["2026-10-30T20:30", "2026-10-31T12:30", "2026-11-01T12:30"])


class TestText(unittest.TestCase):
    def test_banned_words(self):
        for bad in ("यह बेस्ट गेंद है", "Best ball ever", "premium quality", "100% guaranteed", "No.1 ball", "सिर्फ़ 99 रुपये", "MRF जैसी गेंद", "Dhoni का छक्का"):
            self.assertTrue(queue.banned_problems(bad), bad)
        self.assertEqual(queue.banned_problems(seo()["description"]), [])  # the normal caption with its shop links is fine

    def test_entry_has_the_posters_keys_and_instagram_caption(self):
        e = queue.make_entry("sneeze-talk", seo(), "2026-10-31T12:30:00+05:30", CFG, "दादाजी की छींक ने क्या कमाल कर दिया? 🤧")
        self.assertEqual(list(e), ["title", "yt_title", "media", "when", "networks", "caption", "captions", "comments", "status"])
        self.assertEqual(e["title"], "sneeze-talk DASHX")
        self.assertEqual(e["media"], "https://vinitsharma6433-cpu.github.io/dashx/social/sneeze-talk.mp4")
        self.assertEqual((e["networks"], e["status"]), (["youtube"], "scheduled"))
        self.assertEqual(e["caption"], e["captions"]["youtube"])
        self.assertIn("Amazon, Flipkart, Meesho links: bio me", e["captions"]["instagram"])
        self.assertTrue(e["captions"]["instagram"].endswith("#DASHX #GullyCricket #CricketReels #Meerut"))
        self.assertEqual(e["captions"]["facebook"], e["captions"]["instagram"])
        self.assertNotIn("http", e["captions"]["instagram"])  # no links in IG/FB captions: they are in the bio
        self.assertEqual(len(e["comments"]), 1)  # the first comment carries the shop links
        for shop in ("amazon.in/dp/B0H4QG8FKG", "dl.flipkart.com", "meesho.com", "mystore.in", "vinitsharma6433-cpu.github.io/dashx/"):
            self.assertIn(shop, e["comments"][0])

    def test_long_titles_are_cut_under_60(self):
        self.assertLess(len(queue.youtube_title("शब्द " * 30)), 60)


class TestAppendOnly(unittest.TestCase):
    def test_old_text_is_untouched_and_crlf_is_kept(self):
        old = json.dumps({"posts": [OLD_ENTRY]}, indent=2).replace("\n", "\r\n")
        new_entries = [queue.make_entry("a", seo(), "2026-10-31T12:30:00+05:30", CFG, "सचिन की मोच सच्ची थी या बहाना? 😅"), queue.make_entry("b", seo(), "2026-10-31T20:30:00+05:30", CFG, "एक सीटी, दो दावेदार, फ़ैसला किसका? 🤔")]
        new = queue.append_entries(old, new_entries)
        queue.verify_append_only(old, new, 2)
        keep = old[: old.rstrip().rfind("]")].rstrip()
        self.assertTrue(new.startswith(keep))
        self.assertNotIn("\n", new.replace("\r\n", ""))  # every line break is CRLF like the original
        posts = json.loads(new)["posts"]
        self.assertEqual(posts[0], OLD_ENTRY)
        self.assertEqual([p["status"] for p in posts[1:]], ["scheduled", "scheduled"])

    def test_verify_stops_if_an_old_entry_changed(self):
        old = json.dumps({"posts": [OLD_ENTRY]}, indent=2)
        changed = json.loads(old)
        changed["posts"][0]["status"] = "scheduled"
        with self.assertRaises(RuntimeError):
            queue.verify_append_only(old, json.dumps(changed, indent=2), 0)


def sh(*a, cwd=None):
    subprocess.run(a, cwd=cwd, check=True, capture_output=True, text=True)


class TestFullRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        t = self.tmp
        # a bare "GitHub" and a clone of it with poster/queue.json (CRLF like the real one) and social/
        sh("git", "init", "--bare", "-b", "main", str(t / "remote.git"))
        sh("git", "clone", str(t / "remote.git"), str(t / "seed"))
        (t / "seed" / "poster").mkdir()
        (t / "seed" / "social").mkdir()
        self.old_text = json.dumps({"posts": [OLD_ENTRY]}, indent=2).replace("\n", "\r\n")
        (t / "seed" / "poster" / "queue.json").write_bytes(self.old_text.encode())
        (t / "seed" / "poster" / "poster.py").write_text("# the poster, must never change\n")
        (t / "seed" / "social" / "existing.mp4").write_bytes(b"existing")
        sh("git", "-C", str(t / "seed"), "add", "-A")
        sh("git", "-C", str(t / "seed"), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "seed")
        sh("git", "-C", str(t / "seed"), "push", "origin", "main")
        self.cfg = {**queue.DEFAULTS, "repo_dir": str(t / "work"), "remote": str(t / "remote.git")}
        # the project side
        (t / "proj" / "output" / "ready" / "2026-10-30").mkdir(parents=True)
        (t / "proj" / "output" / "reels").mkdir(parents=True)
        self.patches = [mock.patch.object(queue, "ROOT", t / "proj"), mock.patch.object(queue, "READY", t / "proj" / "output" / "ready"),
                        mock.patch.object(queue, "REPORTS", t / "proj" / "output" / "reports"), mock.patch.object(queue, "LEDGER", t / "proj" / "queued.json"),
                        mock.patch.object(queue, "STOP_FILE", t / "proj" / "STOP_QUEUE")]
        for p in self.patches:
            p.start()
        self.now = dt.datetime(2026, 10, 30, 21, 0, tzinfo=IST)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    HOOKS16 = ["सचिन की मोच सच्ची थी या बहाना? 😅", "एक सीटी, दो दावेदार, फ़ैसला किसका? 🤔", "दादाजी की छींक ने क्या कमाल कर दिया? 🤧", "गोलू ने कोच से उनके जूते क्यों माँगे? 👟",
               "ब्रूनो पूरी पिच क्यों खोद रहा है? 🐶", "अंपायर साहब की चाय पर किसकी नज़र थी? 🍵", "आंटी का अचार बचेगा या गेंद भारी पड़ेगी? 😬", "गेंद अटकी आम के पेड़ में, फिर गिरा क्या? 🥭",
               "तीन छक्कों का वादा, कितने निकले? 🏏", "नियम बनाने वाली ख़ुद फँस जाए तो? 😜", "बत्ती गुल, पर खेल चालू! गेंद कहाँ गई? 🔦", "नींद में बल्ला घुमाया तो क्या होगा? 😴",
               "घंटी बजी, पर आख़िरी गेंद अभी बाक़ी है! 🔔", "आंटी की चादर पर गेंद, सूर्या कहाँ छुपा? 👀", "गोलू की गिनती कभी सही निकली है? 🔢", "दादाजी का चश्मा आख़िर है कहाँ? 👓"]
    hook_no = 0

    def add_reel(self, name, dialogue=True, desc_extra="", lines=None, hook="auto"):
        t = self.tmp / "proj"
        (t / "reels" / name).mkdir(parents=True)
        sc = [{"id": 1, "template": "face-off", "params": {}, "dialogue": [{"speaker": "surya", "line": x} for x in (lines or ["दादाजी, आपको ज़ुकाम है क्या?"])], "voice": "x"}]
        if hook == "auto":
            hook = self.HOOKS16[TestFullRun.hook_no % 16]
            TestFullRun.hook_no += 1
        script = {"title": "छींक", "scenes": sc, "story": {"hook": hook, "closing": "छींक का आशीर्वाद मिला!"} if hook else {"closing": "x"}, **({"dialogue_format": 2} if dialogue else {})}
        (t / "reels" / name / "script.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
        rd = t / "output" / "ready" / "2026-10-30"
        (rd / f"{name}.mp4").write_bytes(b"video-" + name.encode())
        (t / "output" / "reels" / f"{name}.mp4").write_bytes(b"video-" + name.encode())
        s = seo(extra=desc_extra)
        (rd / f"{name}.seo.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
        (rd / f"{name}.seo.md").write_text("# " + s["title"], encoding="utf-8")

    n_checks = 0

    def remote_file(self, path):
        TestFullRun.n_checks += 1
        dest = self.tmp / f"check{TestFullRun.n_checks}"  # a fresh clone every time (Windows keeps read-only .git files)
        sh("git", "clone", str(self.tmp / "remote.git"), str(dest))
        return (dest / path).read_bytes()

    def test_good_reel_is_queued_and_pushed_and_nothing_old_changes(self):
        self.add_reel("sneeze-talk")
        self.add_reel("old-style", dialogue=False)
        res = queue.run(inspector=GOOD_QC, now=self.now, cfg=self.cfg)
        self.assertEqual([e["title"] for e in res.queued], ["sneeze-talk DASHX"])
        self.assertEqual(res.old_format, 1)
        self.assertTrue(res.pushed)
        self.assertEqual(res.queued[0]["when"], "2026-10-31T12:30:00+05:30")
        remote_q = self.remote_file("poster/queue.json")
        queue.verify_append_only(self.old_text, remote_q.decode(), 1)
        self.assertEqual(self.remote_file("social/sneeze-talk.mp4"), b"video-sneeze-talk")
        self.assertEqual(self.remote_file("poster/poster.py").replace(b"\r\n", b"\n"), b"# the poster, must never change\n")  # (Windows may check out CRLF)
        self.assertEqual(self.remote_file("social/existing.mp4"), b"existing")
        # a second run queues nothing new
        res2 = queue.run(inspector=GOOD_QC, now=self.now, cfg=self.cfg)
        self.assertEqual((len(res2.queued), len(res2.skipped)), (0, 1))

    def test_banned_word_blocks_and_is_reported(self):
        self.add_reel("bad", lines=["यह premium गेंद है, सबसे बेस्ट!"])  # a banned word in a spoken line (captions are built from the title only)
        self.add_reel("fine")
        res = queue.run(inspector=GOOD_QC, now=self.now, cfg=self.cfg)
        self.assertEqual([e["title"] for e in res.queued], ["fine DASHX"])
        self.assertEqual([n for n, _ in res.blocked], ["bad"])
        report = (self.tmp / "proj" / "output" / "reports" / "2026-10-30.md").read_text(encoding="utf-8")
        self.assertIn("NOT QUEUED bad", report)
        self.assertNotIn(b"video-bad", self.remote_file("social/existing.mp4"))

    def test_reel_without_a_hook_or_with_a_bad_hook_is_not_queued(self):
        self.add_reel("nohook", hook=None)
        self.add_reel("twoemoji", hook="टमाटर 🍅 की गेंद 😂 पर क्या हुआ आख़िर?")
        self.add_reel("template", hook="कुल्फ़ी की घंटी 😂 आख़िर में क्या हुआ? देखो!")
        res = queue.run(inspector=GOOD_QC, now=self.now, cfg=self.cfg)
        self.assertEqual(res.queued, [])
        self.assertEqual(sorted(n for n, _ in res.blocked), ["nohook", "template", "twoemoji"])

    def test_two_reels_with_the_same_hook_wording_do_not_both_go(self):
        self.add_reel("one", hook="टमाटर की जगह गेंद? अंपायर का क्या हुआ? 🍅")
        self.add_reel("two", hook="टमाटर की जगह गेंद? अंपायर का क्या हुआ? 😂")
        res = queue.run(inspector=GOOD_QC, now=self.now, cfg=self.cfg)
        self.assertEqual([e["title"] for e in res.queued], ["one DASHX"])
        self.assertEqual(res.blocked[0][0], "two")
        self.assertIn("too close", res.blocked[0][1][0])

    def test_low_qc_blocks(self):
        self.add_reel("weak")
        res = queue.run(inspector=lambda n: {"score": 85.0, "passed": False, "checks": [], "failed": [{"id": "loudness"}]}, now=self.now, cfg=self.cfg)
        self.assertEqual((len(res.queued), [n for n, _ in res.blocked]), (0, ["weak"]))

    def test_stop_file_does_nothing_and_dry_run_changes_nothing(self):
        self.add_reel("sneeze-talk")
        (self.tmp / "proj" / "STOP_QUEUE").write_text("")
        res = queue.run(inspector=GOOD_QC, now=self.now, cfg=self.cfg)
        self.assertEqual((res.queued, res.pushed), ([], False))
        self.assertIn("STOP_QUEUE", res.note)
        (self.tmp / "proj" / "STOP_QUEUE").unlink()
        res = queue.run(dry_run=True, inspector=GOOD_QC, now=self.now, cfg=self.cfg)
        self.assertEqual(len(res.queued), 1)
        self.assertEqual(self.remote_file("poster/queue.json"), self.old_text.encode())  # the remote is unchanged

    def test_max_14_per_run(self):
        for i in range(16):
            self.add_reel(f"r{i:02d}")
        res = queue.run(inspector=GOOD_QC, now=self.now, cfg=self.cfg)
        self.assertEqual(len(res.queued), 14)
        whens = [e["when"] for e in res.queued]
        self.assertEqual(len(set(whens)), 14)
        per_day = {}
        for w in whens:
            per_day[w[:10]] = per_day.get(w[:10], 0) + 1
        self.assertTrue(all(v <= 2 for v in per_day.values()))


if __name__ == "__main__":
    unittest.main()


class TestCaptions(unittest.TestCase):
    GOOD = "टमाटर की जगह गेंद? अंपायर का क्या हुआ? 🍅"
    SCRIPT = {"title": "टमाटर की गेंद", "story": {"closing": "टमाटर की चटनी बन गई!"},
              "scenes": [{"dialogue": [{"speaker": "sachin", "line": "सूर्या, गेंद कहाँ है?"}, {"speaker": "surya", "line": "गेंद नहीं मिली, टमाटर चलेगा!"}]}]}

    def test_good_hook_passes(self):
        from factory import seo as S
        self.assertEqual(S.hook_problems(self.GOOD, self.SCRIPT), [])

    def test_hook_rules(self):
        from factory import seo as S
        bad = {
            None: "no reel-specific hook",
            "": "no reel-specific hook",
            "टमाटर 🍅 की गेंद 😂 पर अंपायर का क्या हुआ आख़िर?": "2 emoji",
            "टमाटर की जगह गेंद? अंपायर का क्या हुआ?": "0 emoji",
            "यह एक बहुत ही लंबा हुक है जो साठ अक्षरों से ज़्यादा है और चलता ही जा रहा है 😂": "characters",
            "टमाटर की गेंद 😂 आख़िर में क्या हुआ? देखो!": "removed template phrase",
            "टमाटर की गेंद 😂 मिस मत करना": "removed template phrase",
            "सबसे बेस्ट टमाटर वाली गेंद 😂 देखो": "best",
            "Tomato ball ka funny scene 😂": "not Hindi",
            "सूर्या, गेंद कहाँ है? 🍅": "repeats a dialogue line",
            "टमाटर की चटनी बन गई 🍅": "gives away the ending",
        }
        for h, want in bad.items():
            probs = S.hook_problems(h, self.SCRIPT)
            self.assertTrue(probs, h)
            if want in ("2 emoji", "0 emoji", "characters", "removed template phrase", "repeats a dialogue line", "gives away the ending", "no reel-specific hook", "not Hindi"):
                self.assertTrue(any(want.split()[0] in p or want in p for p in probs), (h, probs))

    def test_every_dialogue_bank_hook_passes_and_all_are_different(self):
        import sys as _s
        _s.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import daily
        from factory import seo as S, story
        hooks = []
        for b in daily.parse_dialogue_bank():
            self.assertEqual(S.hook_problems(b["hook"]), [], b["title_en"])
            hooks.append(b["hook"])
        self.assertGreaterEqual(len(hooks), 35)
        for i, a in enumerate(hooks):
            for b2 in hooks[i + 1:]:
                self.assertFalse(S.hooks_clash(a, b2), (a, b2))

    def test_template_functions_are_gone(self):
        from factory import seo as S
        self.assertFalse(hasattr(S, "HOOKS"))
        self.assertFalse(hasattr(S, "hook"))

    def test_instagram_caption_layout(self):
        from factory import seo as S
        lines = S.instagram_caption(self.GOOD).split("\n")
        self.assertEqual(lines[0], self.GOOD)
        self.assertEqual(lines[1], "")
        self.assertEqual(lines[2], "DASHX ball - Meerut se.")
        self.assertEqual(lines[3], "Amazon, Flipkart, Meesho links: bio me")
        self.assertEqual(lines[-1], "#DASHX #GullyCricket #CricketReels #Meerut")
        self.assertNotIn("http", "\n".join(lines))

    def test_youtube_caption_has_the_same_hook_and_the_buy_links(self):
        from factory import seo as S
        yt = S.youtube_caption(self.GOOD)
        self.assertEqual(yt.split("\n")[0], self.GOOD)
        for shop in ("amazon.in/dp/B0H4QG8FKG", "dl.flipkart.com", "meesho.com", "mystore.in"):
            self.assertIn(shop, yt)
        self.assertIn("BUY LINKS", yt)
        self.assertIn("https://vinitsharma6433-cpu.github.io/dashx/", yt)
        self.assertTrue(yt.endswith("#DASHX #GullyCricket #CricketReels #Meerut"))
        self.assertEqual(queue.banned_problems(yt), [])


