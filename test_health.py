import unittest
from datetime import datetime, timedelta, timezone
from health_check import freshness, check_subsets


class HealthTests(unittest.TestCase):
    def test_stalled_update_is_failure(self):
        now=datetime(2026,9,14,tzinfo=timezone.utc)
        freshness((now-timedelta(hours=25)).isoformat(),now)
        with self.assertRaises(ValueError):freshness((now-timedelta(hours=37)).isoformat(),now)
        with self.assertRaises(ValueError):freshness(None,now)
        with self.assertRaises(ValueError):freshness('2026-09-14T00:00:00',now)
        with self.assertRaises(ValueError):freshness((now+timedelta(days=1)).isoformat(),now)

    def test_wrong_subsidy_feed_detected(self):
        feeds={'all':{'a','b'},'subsidized':{'a'},'deadlines':{'a'},'subsidized-deadlines':{'a'},
               'reminders':{'c'},'subsidized-reminders':{'c'}}
        check_subsets(feeds)
        feeds['subsidized']={'z'}
        with self.assertRaises(ValueError):check_subsets(feeds)

    def test_duplicate_reminder_uid_detected(self):
        feeds={'all':{'a'},'subsidized':set(),'deadlines':{'a'},'subsidized-deadlines':set(),
               'reminders':{'a'},'subsidized-reminders':set()}
        with self.assertRaises(ValueError):check_subsets(feeds)
