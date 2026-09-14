import copy
import json
import tempfile
import unittest
import io
from contextlib import redirect_stdout
from unittest.mock import patch
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from calendar_app import ROOT, events_for, render_calendar, deadline_start, build
from monitor import extract_rule, observe, validate_change, Page, update


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.records=json.loads((ROOT/'data/conferences.json').read_text())
        self.now=datetime(2026,9,13,tzinfo=timezone.utc)

    def test_known_deadline_timezone_and_dst(self):
        d={'date':'2026-09-22','time':'23:59','timezone':'America/New_York'}
        self.assertEqual(deadline_start(d).astimezone(timezone.utc).isoformat(),'2026-09-23T03:59:00+00:00')
        d['date']='2027-01-26'
        self.assertEqual(deadline_start(d).astimezone(timezone.utc).isoformat(),'2027-01-27T04:59:00+00:00')

    def test_all_day_end_exclusive_and_month_crossing(self):
        sample=next(r for r in self.records if r['id']=='asmbs-2027')
        sample.update(start='2027-06-27',end='2027-07-01')
        events=events_for(self.records)
        ev=next(e for e in events if e['key']=='asmbs-2027/meeting')
        self.assertEqual(ev['start'],date(2027,6,27))
        self.assertEqual(ev['end'],date(2027,7,2))

    def test_no_fabricated_or_conflicting_deadlines(self):
        # Fixed fixtures: future legitimate official updates must not break the scheduler.
        for r in self.records:
            if r['id']=='eta-2027':r['deadlines']=[];r['deadline_note']='2027/3'
            if r['id'] in ['esa-2027','asc-2027']:
                r['deadlines']=[dict(id='abstract',label='摘要投稿截止',status='conflict',date='2026-10-15')]
            if r['id']=='kingca-tbd':r['start']=None;r['end']=None
        events=events_for(self.records)
        keys={e['key'] for e in events}
        self.assertNotIn('eta-2027/abstract',keys)
        self.assertNotIn('esa-2027/abstract',keys)
        self.assertNotIn('asc-2027/abstract',keys)
        self.assertNotIn('kingca-tbd/meeting',keys)
        self.assertIn('aphs-2026/oral',keys)
        self.assertIn('aphs-2026/eposter',keys)

    def test_uid_stability_sequence_and_utf8(self):
        ev=events_for(self.records)[0];state={}
        first=render_calendar('中文測試',[ev],state,self.now)
        self.assertEqual(first,render_calendar('中文測試',[ev],state,self.now+timedelta(days=1)))
        changed=copy.deepcopy(ev);changed['start']+=timedelta(days=1);changed['end']+=timedelta(days=1)
        second=render_calendar('中文測試',[changed],state,self.now+timedelta(days=1))
        self.assertEqual(len(state),1)
        self.assertIn(b'SEQUENCE:1',second)
        self.assertIn(b'LAST-MODIFIED:20260914T000000Z',second)
        for line in first.split(b'\r\n'):
            self.assertLessEqual(len(line),75);line.decode('utf-8')

    def test_parser_scope_and_ambiguity(self):
        rule={'identity':'SAGES 2027','kind':'deadline','pattern':r'Deadline: (?P<date>September \d+, 2026)'}
        self.assertEqual(extract_rule(rule,'SAGES 2027 Deadline: September 11, 2026')['date'],'2026-09-11')
        with self.assertRaises(ValueError):extract_rule(rule,'SAGES 2028 Deadline: September 11, 2026')
        with self.assertRaises(ValueError):extract_rule(rule,'SAGES 2027 Deadline: September 11, 2026 Deadline: September 18, 2026')
        with self.assertRaises(ValueError):extract_rule(rule,'SAGES 2027 Registration Deadline TBD')

    def test_change_requires_separated_observations(self):
        state={};v={'date':'2026-10-01'}
        self.assertFalse(observe(state,'x',v,self.now))
        self.assertFalse(observe(state,'x',v,self.now+timedelta(minutes=1)))
        self.assertTrue(observe(state,'x',v,self.now+timedelta(hours=7)))
        self.assertFalse(observe(state,'x',{'date':'2026-10-02'},self.now+timedelta(hours=8)))

    def test_invalid_date_not_applied(self):
        record={'year':2027,'start':'2027-04-06'}
        with self.assertRaises(ValueError):validate_change(record,'deadline',{'date':'2027-04-07'})
        with self.assertRaises(ValueError):validate_change(record,'meeting',{'start':'2026-04-06','end':'2026-04-09'})

    def test_funded_identity_and_separate_milestones(self):
        funded={r['series'] for r in self.records if r['subsidized']}
        self.assertEqual(funded,{'SAGES','ACS','EAES','ELSA','IHPBA','A-PHPBA','AHPBA','EHS','AHS','APHS'})
        es=events_for(self.records,True)
        a=next(e for e in es if e['key']=='sages-2027/abstract')
        b=next(e for e in es if e['key']=='sages-2027/abstract/reminder-7')
        self.assertEqual(a['start']-b['start'],timedelta(days=7))

    def test_html_noise_is_not_deadline(self):
        p=Page();p.feed('<style>Deadline: May 1, 2027</style><h1>SAGES 2027</h1><script>Deadline: May 2, 2027</script>')
        self.assertEqual(p.text,'SAGES 2027')

    def test_cancelled_meeting_and_deadlines(self):
        records=copy.deepcopy(self.records);r=next(r for r in records if r['id']=='sages-2027');r['cancelled']=True
        self.assertTrue(all(e['status']=='CANCELLED' for e in events_for([r],True)))

    def test_update_applies_extension_and_failure_retains_feed(self):
        record=copy.deepcopy(next(r for r in self.records if r['id']=='sages-2027'))
        record['monitor_urls']=['https://example.org/2027']
        rule={'record':record['id'],'kind':'deadline','deadline':'abstract','url':record['monitor_urls'][0],
            'identity':'SAGES 2027','pattern':r'Deadline: (?P<date>September \d+, 2026)'}
        proposed={'date':'2026-09-18','time':None,'timezone':None}
        page=Page();page.feed('<h1>SAGES 2027</h1><p>Deadline: September 18, 2026</p>')
        with tempfile.TemporaryDirectory() as temp,redirect_stdout(io.StringIO()):
            root=Path(temp);(root/'data').mkdir()
            (root/'data/conferences.json').write_text(json.dumps([record]))
            fallback=copy.deepcopy(rule);fallback['pattern']='no longer used on this page'
            (root/'data/rules.json').write_text(json.dumps([fallback,rule]))
            build(root)
            original=(root/'public/all.ics').read_bytes()
            first=datetime.now(timezone.utc)-timedelta(hours=7)
            (root/'data/monitor-state.json').write_text(json.dumps({'pages':{},'pending':{
                'sages-2027/deadline/abstract':{'value':json.dumps(proposed,sort_keys=True),'first':first.isoformat(),'last':first.isoformat()}}}))
            with patch('monitor.fetch',return_value=(page,rule['url'])):
                result=update(root)
            self.assertEqual(result['applied_changes'],1)
            saved=json.loads((root/'data/conferences.json').read_text())
            self.assertEqual(saved[0]['deadlines'][0]['date'],'2026-09-18')
            modified=(root/'public/all.ics').read_bytes()
            self.assertNotEqual(original,modified)
            with patch('monitor.fetch',side_effect=RuntimeError('HTTP 403')):
                result=update(root)
            self.assertEqual(result['failed'],1)
            self.assertEqual(modified,(root/'public/all.ics').read_bytes())


if __name__=='__main__':unittest.main()
