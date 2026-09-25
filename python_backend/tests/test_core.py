"""
Event Watcher - offline self-tests (standard library only).
Run from python_backend/:   python3 -m unittest discover -s tests -v
Uses a throw-away data folder; never touches real data and needs no internet.
"""

import io
import json
import os
import sys
import tempfile
import unittest
import zipfile

_TMP = tempfile.mkdtemp(prefix="ew-test-")
os.environ["EVENTWATCHER_DATA_DIR"] = _TMP
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backup  # noqa: E402
import database  # noqa: E402
import main  # noqa: E402
from netguard import UnsafeURLError, is_public_ip, validate_url  # noqa: E402
from extractors import clean_title, extract, parse_ics  # noqa: E402
import watcher_engine  # noqa: E402
from watcher_engine import test_keywords  # noqa: E402

database.init_db()


class NetGuardTests(unittest.TestCase):
    def test_blocks_private_and_local_addresses(self):
        for url in ("http://127.0.0.1/", "http://localhost:3847/", "http://10.0.0.1/", "http://192.168.1.1/",
                    "http://169.254.169.254/", "http://[::1]/", "http://[::ffff:127.0.0.1]/", "http://100.64.0.1/",
                    "http://printer.local/", "file:///etc/passwd", "ftp://example.com/", "http://u:p@example.com/"):
            with self.assertRaises(UnsafeURLError, msg=url):
                validate_url(url)

    def test_allows_public_urls(self):
        self.assertEqual(validate_url("https://feeds.bbci.co.uk/news/rss.xml"), "https://feeds.bbci.co.uk/news/rss.xml")
        self.assertTrue(is_public_ip("8.8.8.8"))
        self.assertFalse(is_public_ip("224.0.0.1"))


class EngineTests(unittest.TestCase):
    def test_keywords_case_insensitive_and_exclusions_win(self):
        self.assertEqual(test_keywords("Belfast CONCERT announced", ["concert"], [])[:2], (True, ["concert"]))
        self.assertFalse(test_keywords("Concert SOLD OUT", ["concert"], ["sold out"])[0])

    def test_rss_parsing_and_venue(self):
        xml = ("<rss><channel><item><title><![CDATA[The Killers announce Belfast show]]></title>"
               "<link>https://example.com/k</link><description>Live at SSE Arena Belfast on 12 March 2027"
               "</description></item></channel></rss>")
        _, items, _, _ = extract(xml, "rss", "https://example.com/feed")
        self.assertEqual(items[0]["title"], "The Killers announce Belfast show")
        self.assertEqual(items[0]["venue"], "SSE Arena Belfast")
        self.assertEqual(items[0]["date"], "Fri 12 Mar 2027")

    def test_listing_cards_titles_dates_and_past_events(self):
        page = """<html><body><nav><a href="/a">Home page link text here</a></nav><section class="gigs">
          <div class="col"><div class="item"><a href="https://t.example/kingfishr">x</a>
            <span>Thursday 11 June 2099</span><h3>Kingfishr</h3><span>Buy Tickets</span></div></div>
          <div class="col"><div class="item"><a href="https://t.example/take-that">x</a>
            <span>Wednesday 30 June 2099</span><h3>Take That</h3><span>Sold Out</span></div></div>
          <div class="col"><div class="item"><a href="https://t.example/old">x</a>
            <span>Monday 1 June 2020</span><h3>Old Gig</h3></div></div></section></body></html>"""
        _, items, _, read = extract(page, "event_listing", "https://www.belsonic.com/")
        self.assertEqual(read, 3)
        self.assertEqual([i["title"] for i in items], ["Kingfishr", "Take That"])  # past gig dropped
        self.assertEqual(items[0]["date"], "Thu 11 Jun 2099")
        self.assertEqual(items[0]["link"], "https://t.example/kingfishr")

    def test_json_feed_with_pagination(self):
        feed = json.dumps({"data": [{"title": "Megan Moroney", "url": "https://venue.example/events/mm",
                                     "eventStartDate": {"date": "2099-10-01 19:30:00.000000"}}],
                           "meta": {"pagination": {"links": {"next": "https://venue.example/events.json?page=2"}}}})
        detected, items, next_url, _ = extract(feed, "custom_url", "https://venue.example/events.json")
        self.assertEqual(detected, "json_feed")
        self.assertEqual(items[0]["title"], "Megan Moroney")
        self.assertEqual(items[0]["date"], "Thu 01 Oct 2099, 19:30")
        self.assertEqual(next_url, "https://venue.example/events.json?page=2")
        _, _, other_site, _ = extract(feed.replace("venue.example/events.json?page", "evil.example/?p"),
                                      "custom_url", "https://venue.example/events.json")
        self.assertIsNone(other_site)  # never follow pagination to another website

    def test_schema_org_events(self):
        page = """<script type="application/ld+json">[{"@type":"MusicEvent","name":"Calvin Harris @ Boucher Playing Fields",
          "startDate":"2099-08-22T16:00:00","url":"https://sk.example/c/1",
          "location":{"@type":"Place","name":"Boucher Playing Fields","address":{"addressLocality":"Belfast"}}}]</script>"""
        _, items, _, _ = extract(page, "event_listing", "https://sk.example/venue")
        self.assertEqual(items[0]["venue"], "Boucher Playing Fields, Belfast")
        self.assertEqual(items[0]["date"], "Sat 22 Aug 2099, 16:00")

    def test_status_words_do_not_change_titles(self):
        self.assertEqual(clean_title("Westlife SOLD OUT"), clean_title("Westlife – Buy Tickets"))

    def test_ics_unfolding_and_unescaping(self):
        ics = "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Big\\, long\r\n  title\r\nLOCATION:Hall\\; A\r\nEND:VEVENT\r\nEND:VCALENDAR"
        ev = parse_ics(ics)[0]
        self.assertEqual(ev["title"], "Big, long title")
        self.assertEqual(ev["venue"], "Hall; A")


class CheckCycleTests(unittest.TestCase):
    """Baseline, new announcement, then a broken source - with a fake website, no internet."""

    def setUp(self):
        from netguard import FetchResult
        self.FetchResult = FetchResult
        self.page = {"body": ""}
        self.sent = []
        self._fetch, self._notify = watcher_engine.safe_fetch, watcher_engine.send_desktop_notification
        watcher_engine.safe_fetch = lambda url, ua, timeout=15: FetchResult(True, 200, self.page["body"], 5, None, url)
        watcher_engine.send_desktop_notification = lambda title, body: self.sent.append((title, body)) or (True, "test")
        database.save_settings({"desktop_notifications": True})

    def tearDown(self):
        watcher_engine.safe_fetch, watcher_engine.send_desktop_notification = self._fetch, self._notify

    def _feed(self, titles):
        items = "".join(f"<item><title>{t}</title><link>https://news.example/{i}</link></item>"
                        for i, t in enumerate(titles))
        return f"<rss><channel>{items}</channel></rss>"

    def test_baseline_then_new_then_broken(self):
        w = database.create_watcher({"name": "Venue", "source_url": "https://news.example/feed", "source_type": "rss"})
        self.page["body"] = self._feed(["Show A", "Show B"])
        self.assertEqual(watcher_engine.check_single_watcher(w["id"]), (0, None))
        self.assertEqual([t for t, _ in self.sent], ["Now watching Venue"])  # one summary, not two alerts
        events, _ = database.get_events(watcher_id=w["id"])
        self.assertTrue(all(e["notification_status"] == "read" for e in events))

        self.page["body"] = self._feed(["Show A", "Show B", "Show C announced"])
        self.assertEqual(watcher_engine.check_single_watcher(w["id"]), (1, None))
        self.assertEqual(self.sent[-1][0], "New event found")
        self.assertIn("Show C announced", self.sent[-1][1])

        self.page["body"] = "<html><body>redesigned</body></html>"
        for _ in range(3):
            new, err = watcher_engine.check_single_watcher(w["id"])
            self.assertEqual(new, 0)
            self.assertIn("no events could be read", err)
        self.assertEqual(self.sent[-1][0], "Event Watcher: a source needs attention")
        self.assertEqual(sum(1 for t, _ in self.sent if "needs attention" in t), 1)  # warned once


class ExportTests(unittest.TestCase):
    EVENT = {"id": "event-1", "title": "=HYPERLINK(\"http://x\")", "category": "Concerts", "venue": "A,B;C",
             "event_date": None, "detected_at": "2026-09-25T10:00:00.000Z", "source_name": "S",
             "source_url": "https://example.com/e", "matched_keywords": ["x"],
             "short_description": "line1\r\nEND:VEVENT\r\nBEGIN:VEVENT"}

    def test_csv_neutralises_formulas(self):
        csv_text = main.events_to_csv([self.EVENT])
        self.assertIn("\"'=HYPERLINK", csv_text)

    def test_ics_cannot_inject_components(self):
        ics = main.events_to_ics([self.EVENT])
        self.assertEqual([l for l in ics.split("\r\n") if l == "BEGIN:VEVENT"], ["BEGIN:VEVENT"])
        self.assertIn("LOCATION:A\\,B\\;C", ics)


class SettingsAndBackupTests(unittest.TestCase):
    def test_settings_validation(self):
        with self.assertRaises(database.ValidationError):
            database.save_settings({"check_interval_minutes": 0})
        self.assertNotIn("\n", database.save_settings({"user_agent": "a\r\nX: y"})["user_agent"])

    def test_backup_roundtrip_and_rejections(self):
        database.create_watcher({"name": "Test", "source_url": "https://example.com/feed", "source_type": "rss"})
        before = database.counts()["total_watchers"]
        _, data = backup.create_backup()
        result = backup.restore_backup(data)
        self.assertEqual(result["restoredWatchersCount"], before)

        with self.assertRaises(backup.BackupError):
            backup.restore_backup(b"not a zip")
        fake = io.BytesIO()
        with zipfile.ZipFile(fake, "w") as zf:
            zf.writestr("data/eventwatcher.db", b"garbage" * 10)
        with self.assertRaises(backup.BackupError):
            backup.restore_backup(fake.getvalue())
        self.assertEqual(database.counts()["total_watchers"], before)  # failed restores change nothing

    def test_watcher_rejects_private_url(self):
        with self.assertRaises(database.ValidationError):
            database.create_watcher({"name": "LAN", "source_url": "http://192.168.1.10/", "source_type": "webpage"})


if __name__ == "__main__":
    unittest.main()
