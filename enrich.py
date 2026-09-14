"""One-time, reviewed source annotations. Does not run on the update schedule."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
p = ROOT / 'data/conferences.json'
records = json.loads(p.read_text())
urls = {
 'ATA': ['https://thyroid.joynmeeting.com/conference/', 'https://www.thyroid.org/'],
 'ETA': ['https://www.eurothyroid.com/events/48th-annual-meeting-of-the-european-thyroid-association.html'],
 'IAES': ['https://2026.iaesurgeons.org/'],
 'AAES': ['https://aaes.memberclicks.net/2027-annual-meeting-home'],
 'WCTC': ['https://thyroidworldcongress.com/'],
 'SABCS': ['https://sabcs.org/media/future-symposia/', 'https://sabcs.org/abstracts/'],
 'St. Gallen': ['https://www.sg-bcc.org/'],
 'ESMO (breast)': ['https://www.esmo.org/meeting-calendar/esmo-breast-cancer-2027'],
 'GBCC': ['https://www.gbcc.kr/main.asp'],
 'ASCO GI': ['https://www.asco.org/gi', 'https://www.asco.org/gi/abstracts-presentations/submission-details/requirements'],
 'ESMO GI': ['https://www.esmo.org/meeting-calendar/esmo-gastrointestinal-cancers-congress-2027'],
 'IGCC': ['https://igcc2027.com/igcc2027', 'https://www.igca.info/'],
 'JGCA': ['https://kwcs.jp/99jgca/e-outl.html', 'https://www.jgca.jp/english/annualcongress/'],
 'KINGCA': ['https://www.kingca.org/', 'https://www.igca.info/'],
 'IHPBA': ['https://www.ihpba.org/19_World-Congress.html'],
 'AHPBA': ['https://www.ahpba.org/future-meetings/', 'https://www.abstractscorecard.com/cfp/submit/login.asp?EventKey=SATWJIGK'],
 'E-AHPBA': ['https://eahpba.org/education-and-training/congress/'],
 'A-PHPBA': ['https://aphpba2027.com/'],
 'ILLS': ['https://www.ills2027.com/'],
 'WCHS': ['https://europeanherniasociety.eu/'],
 'EHS': ['https://europeanherniasociety.eu/ehs2027/'],
 'AHS': ['https://www.americanherniasociety.org/meetings'],
 'APHS': ['https://aphs2026.jp/ap/call-for-papers.html', 'https://aphs2026.jp/ap/'],
 'IFSO': ['https://www.ifso.com/world-congress/', 'https://ifso2027.org/'],
 'ASMBS': ['https://asmbs.org/professional-development/meetings-of-interest/'],
 'SAGES': ['https://www.sages.org/meetings/abstracts/', 'https://www.sages2027.org/', 'https://www.sages.org/meetings/'],
 'WCES': ['https://eaes.eu/'],
 'EAES': ['https://eaes.eu/', 'https://www.duesseldorfcongress.de/en/dusseldorf-congress-brings-international-eaes-2027-surgical-congress-to-the-state-capital/'],
 'ELSA': ['https://elsasociety.org/congress-2/'],
 'JSES': ['https://www.jses.or.jp/'],
 'ASCO': ['https://www.asco.org/meetings-education/meetings/abstract-submissions'],
 'ESMO': ['https://www.esmo.org/meeting-calendar/esmo-congress-2026', 'https://www.esmo.org/meeting-calendar/esmo-congress-2027'],
 'SSO': ['https://surgonc.org/events/sso-annual-meeting/'],
 'ESSO': ['https://www.essoweb.org/'],
 'ACS': ['https://www.facs.org/for-medical-professionals/conferences-and-meetings/clinical-congress-2027/'],
 'ESA': ['https://www.europeansurgicalassociation.org/'],
 'WCS': ['https://www.isw2028.com/'],
 'ASC': ['https://www.academicsurgicalcongress.org/abstract-submission-guidelines/', 'https://academicsurgicalcongress.us/'],
 'AMEE': ['https://amee.org/events/'],
 'AAMC': ['https://www.aamc.org/learn-network/learn-serve-lead'],
 'OTTAWA': ['https://amee.org/events/'],
 'APMEC': ['https://plaza.umin.ac.jp/jsme/eng/activities/apmec2027.html', 'https://medicine.nus.edu.sg/cenmed/sites/apmec2027/index.html'],
}
# Verification applies to each specified edition, not every year on the website.
confirmed = {
 'ATA': [2026], 'ETA': [2027], 'IAES': [2026], 'AAES': [2027], 'WCTC': [2027],
 'SABCS': [2026,2027], 'St. Gallen': [2027], 'GBCC': [2027], 'ASCO GI': [2027],
 'IGCC': [2027], 'JGCA': [2027], 'IHPBA': [2028], 'AHPBA': [2027],
 'E-AHPBA': [2027], 'A-PHPBA': [2027], 'ILLS': [2027], 'EHS': [2027],
 'IFSO': [2027,2028], 'ASMBS': [2027,2028], 'SAGES': [2027], 'EAES': [2027],
 'ELSA': [2026], 'ASCO': [2027], 'SSO': [2027,2028], 'ACS': [2027],
 'ESA': [2027], 'WCS': [2028], 'ASC': [2027], 'AMEE': [2027], 'AAMC': [2027], 'APMEC': [2027],
}
for r in records:
 r['monitor_urls'] = urls[r['series']]
 if r['year'] in confirmed.get(r['series'], []):
  r['meeting_status'] = 'official'
  r['meeting_sources'] = [urls[r['series']][1 if r['series']=='EAES' else 0]]
  r['meeting_verified_at'] = '2026-09-13'
 for d in r['deadlines']:
  if r['series'] in ['SAGES','ASCO GI','ASCO','AHPBA','AAES','EHS','A-PHPBA','St. Gallen','APHS']:
   d['status']='official'; d['verified_at']='2026-09-13'
   d['sources']=[urls[r['series']][1 if r['series'] in ['ASCO GI','AHPBA'] else 0]]
   if r['series'] in ['SAGES','ASCO GI','ASCO','AHPBA']:
    d['time']='23:59';d['timezone']='America/Los_Angeles' if r['series']=='SAGES' else 'America/New_York'
 if r['series']=='ASCO GI':
  r['deadlines'].append(dict(id='late-breaking', label='Late-breaking 投稿截止（需符合資格）', date='2026-10-22', time='12:00', timezone='America/New_York',status='official',verified_at='2026-09-13',sources=[urls['ASCO GI'][1]]))
 if r['series']=='ESA':
  # Site omits deadline year; preserve the conflict for review instead of silently assuming.
  r['deadlines'][0]['status']='conflict'
  r['deadlines'][0]['sources']=urls['ESA']
  r['deadline_note']='簡報：2026/10/15；官網：October 14（未明列年份）；待確認，不建立截止事件。另有 special lectures October 28。'
 if r['series']=='ACS':
  r['deadline_note']='簡報預估 2027/3；2027 官網僅公告摘要／影片／海報徵稿將於 December 開放，尚無確切截止日。'
 if r['series']=='ASC' and r['year']==2027:
  r['deadlines']=[dict(id='abstract',label='摘要投稿截止',date='2026-08-07',time='23:59',timezone='America/New_York',status='official',verified_at='2026-09-13',sources=[urls['ASC'][1]])]
p.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print('Annotated',len(records),'editions with',len(urls),'series source lists.')
