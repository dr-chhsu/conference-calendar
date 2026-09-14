"""Fetch official pages daily, apply scoped parsers, retain last good data on failure.

Changed dates require two separate successful observations at least six hours apart.
Unmatched, conflicting or newly discovered content is recorded for human review.
No LLM credentials, third-party proxy or paid service required.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import copy
import hashlib
import json
import re
import subprocess
import time
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from calendar_app import ROOT, read_json, write_json, atomic_write, build


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[];self.links=[];self.skip=0;self.json_scripts=[];self.in_json=False;self.json_parts=[]

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ['script','style','noscript']:
            self.skip+=1
            if tag=='script' and attrs.get('type','').lower()=='application/ld+json':
                self.in_json=True;self.json_parts=[]
        if tag=='a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag=='img' and attrs.get('alt') and not self.skip:
            self.parts.append(attrs['alt'])

    def handle_endtag(self,tag):
        if tag in ['script','style','noscript']:
            if tag=='script' and self.in_json:
                self.json_scripts.append(''.join(self.json_parts));self.in_json=False
            self.skip=max(0,self.skip-1)

    def handle_data(self,data):
        if self.in_json:self.json_parts.append(data)
        if not self.skip:self.parts.append(data)

    @property
    def text(self):
        return re.sub(r'\s+',' ',' '.join(self.parts)).strip()


MONTHS={m.lower():i for i,m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'],1)}
MONTH=r'(?:January|February|March|April|May|June|July|August|September|October|November|December)'
DATE=rf'(?:{MONTH}\s+\d{{1,2}}(?:\s*\([A-Za-z]+\))?,?\s+20\d{{2}}|\d{{1,2}}\s+{MONTH}\s+20\d{{2}}|20\d{{2}}-\d{{2}}-\d{{2}})'


def parse_date(value):
    value=re.sub(r'\([A-Za-z]+\)','',value).replace(',',' ').strip()
    value=re.sub(r'\s+',' ',value)
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):return date.fromisoformat(value).isoformat()
    for fmt in ['%B %d %Y','%d %B %Y','%d.%m.%Y']:
        try:return datetime.strptime(value.title(),fmt).date().isoformat()
        except ValueError:pass
    raise ValueError('Not an explicit day, month and year: '+value)


def fetch(url, cache):
    """Use curl with verified TLS and a bounded response size and timeout."""
    key=hashlib.sha256(url.encode()).hexdigest()[:24]
    output=cache/(key+'.html')
    result=subprocess.run(['curl','--location','--fail','--silent','--show-error',
        '--proto','=https,http','--proto-redir','=https,http','--max-time','30','--max-filesize','8000000',
        '--user-agent','GSConferenceCalendar/1.0 (academic date monitor)',
        '--output',str(output),'--write-out','%{http_code}\n%{url_effective}',url],capture_output=True,text=True,timeout=40)
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[-250:] or 'curl failed')
    raw=output.read_bytes().decode('utf-8',errors='replace')
    page=Page();page.feed(raw)
    if len(page.text)<120 or re.search(r'^(Just a moment|Access Denied|Attention Required|Client Challenge)',page.text,re.I):
        raise ValueError('Empty page or anti-bot response; last good dates retained')
    atomic_write(cache/(key+'.txt'),page.text.encode())
    return page,result.stdout.split('\n')[-1]


def extract_rule(rule, text):
    if not re.search(rule['identity'],text,re.I):
        raise ValueError('Edition identity missing; page may have rolled to another year')
    matches=list(re.finditer(rule['pattern'],text,re.I))
    values=[]
    for m in matches:
        data={}
        for field in ['date','start','end']:
            if field in m.groupdict() and m[field]:data[field]=parse_date(m[field])
        if 'month' in m.groupdict():
            mo=MONTHS[m['month'].lower()]; y=int(m['year'])
            data.update(start=date(y,mo,int(m['first'])).isoformat(),end=date(y,mo,int(m['last'])).isoformat())
        if 'startmonth' in m.groupdict():
            y=int(m['year'])
            data.update(start=date(y,MONTHS[m['startmonth'].lower()],int(m['first'])).isoformat(),
                end=date(y,MONTHS[m['endmonth'].lower()],int(m['last'])).isoformat())
        if 'time' in m.groupdict() and m['time']:
            clock=re.sub(r'\s+','',m['time']).upper()
            data['time']=datetime.strptime(clock,'%I:%M%p').strftime('%H:%M')
            abbr=(m.groupdict().get('zone') or '').upper()
            zones={'ET':'America/New_York','EDT':'America/New_York','EST':'America/New_York',
                'PT':'America/Los_Angeles','PDT':'America/Los_Angeles','PST':'America/Los_Angeles',
                'EASTERN TIME':'America/New_York','JST':'Asia/Tokyo','KST':'Asia/Seoul'}
            if abbr not in zones:raise ValueError('Unrecognized or missing deadline timezone')
            data['timezone']=zones[abbr]
        elif rule['kind']=='deadline':
            # Do not retain an old time if the source now only publishes a day.
            data.update(time=None,timezone=rule.get('date_timezone'))
        if data:values.append(data)
    unique={json.dumps(v,sort_keys=True) for v in values}
    if len(unique)!=1:raise ValueError('Expected one unambiguous date; found '+str(len(unique)))
    return json.loads(next(iter(unique)))


def validate_change(record, kind, proposed):
    if kind=='meeting':
        a=date.fromisoformat(proposed['start']); b=date.fromisoformat(proposed['end'])
        if a.year!=record['year'] or not 0<=(b-a).days<=21:
            raise ValueError('Meeting year/range outside expected edition')
    else:
        a=date.fromisoformat(proposed['date'])
        if record.get('start'):
            delta=(date.fromisoformat(record['start'])-a).days
            if not 0<=delta<=730:raise ValueError('Deadline is after the meeting or more than two years before it')


def observe(state, key, proposed, now):
    value=json.dumps(proposed,sort_keys=True)
    old=state.get(key)
    if not old or old['value']!=value:
        state[key]={'value':value,'first':now.isoformat(),'last':now.isoformat()}
        return False
    old['last']=now.isoformat()
    return (now-datetime.fromisoformat(old['first'])).total_seconds()>=6*3600


def update(root=ROOT, only=None, fetch_only=False):
    now=datetime.now(timezone.utc)
    records=read_json(root/'data/conferences.json',[])
    lookup={r['id']:r for r in records}
    rules=read_json(root/'data/rules.json',[])
    state=read_json(root/'data/monitor-state.json',{'pages':{},'pending':{}})
    state.setdefault('pending',{});state.setdefault('pages',{})
    review=[]; changes=[]
    cache=root/'cache';cache.mkdir(exist_ok=True)
    urls=sorted(set(u for r in records if not only or r['series']==only for u in r['monitor_urls']) |
        set(r['url'] for r in rules if not only or lookup[r['record']]['series']==only))
    pages={}; failures=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(fetch,u,cache):u for u in urls}
        for future in concurrent.futures.as_completed(futures):
            url=futures[future]
            old=state['pages'].get(url,{})
            try:
                page,final_url=future.result();pages[url]=page
                h=hashlib.sha256(page.text.encode()).hexdigest()
                changed=bool(old.get('hash') and old['hash']!=h)
                state['pages'][url]={'hash':h,'last_success':now.isoformat(),'last_attempt':now.isoformat(),'error':None,'changed':changed,'final_url':final_url}
                if changed:
                    review.append({'type':'page_changed','url':url,'message':'官方頁面內容變更；可辨識日期會經雙次確認後套用，其餘內容需檢視。'})
            except Exception as exc:
                failures+=1
                old.update(last_attempt=now.isoformat(),error=str(exc))
                state['pages'][url]=old
                review.append({'type':'fetch_failed','url':url,'message':str(exc)})
    if not fetch_only:
        # Group by record+field: contradictory official pages must never win by ordering.
        candidates={};failed_keys=set()
        for rule in rules:
            if rule['url'] not in pages:continue
            key=rule['record']+'/'+rule['kind']+'/'+rule.get('deadline','')
            try:
                value=extract_rule(rule,pages[rule['url']].text)
                validate_change(lookup[rule['record']],rule['kind'],value)
                candidates.setdefault(key,[]).append((rule,value))
            except (ValueError,KeyError) as exc:
                failed_keys.add(key)
                review.append({'type':'parser_review','record':rule['record'],'url':rule['url'],'message':str(exc)})
        for key in failed_keys-candidates.keys():
            state['pending'].pop(key,None)
        for key,items in candidates.items():
            distinct={json.dumps(v,sort_keys=True) for _,v in items}
            if len(distinct)!=1:
                state['pending'].pop(key,None)
                review.append({'type':'conflict','record':items[0][0]['record'],'message':'官方來源日期不同；保留原資料，等待確認。'})
                continue
            rule,value=items[0];r=lookup[rule['record']]
            if rule['kind']=='meeting':target=r
            else:
                target=next((d for d in r['deadlines'] if d['id']==rule['deadline']),None)
            status_key='meeting_status' if rule['kind']=='meeting' else 'status'
            unchanged=target is not None and target.get(status_key)=='official' and all(target.get(k)==v for k,v in value.items())
            if unchanged:
                state['pending'].pop(key,None)
                continue
            if not observe(state['pending'],key,value,now):
                review.append({'type':'pending_confirmation','record':r['id'],'url':rule['url'],'message':'偵測到日期，等待至少六小時後再次確認。','proposed':value})
                continue
            before=copy.deepcopy(target)
            if target is None:
                target={'id':rule['deadline'],'label':rule.get('label','摘要投稿截止')}
                r['deadlines'].append(target)
            target.update(value)
            if rule['kind']=='meeting':
                r.update(meeting_status='official',meeting_sources=[a['url'] for a,_ in items],meeting_verified_at=now.date().isoformat())
            else:
                target.update(status='official',sources=[a['url'] for a,_ in items],verified_at=now.date().isoformat())
            changes.append({'at':now.isoformat(),'record':r['id'],'kind':rule['kind'],'before':before,'after':copy.deepcopy(target),'source':rule['url']})
            state['pending'].pop(key,None)
    # New URLs are suggestions only; never follow an arbitrary page into a submission portal.
    seen=set(urls)
    for url,page in pages.items():
        for link in page.links:
            dest=urljoin(url,link)
            if dest not in seen and re.search(r'(abstract|call-for|submission|202[7-9]|203\d)',dest,re.I) and urlparse(dest).scheme in ['http','https']:
                seen.add(dest)
                review.append({'type':'discovered_link','url':dest,'source':url,'message':'新投稿頁或後續年度連結，需確認會議身分後加入追蹤。'})
    covered={rule['record'] for rule in rules}
    for r in records:
        if (not only or r['series']==only) and r['id'] not in covered:
            review.append({'type':'monitor_only','record':r['id'],'message':'已追蹤官方頁面變更，尚無可自動套用此屆日期的解析規則。'})
    # Carry unresolved date conflicts even if the page has not changed.
    for r in records:
        if any(d['status']=='conflict' for d in r['deadlines']):
            review.append({'type':'date_conflict','record':r['id'],'message':r['deadline_note']})
    state.update(last_run=now.isoformat(),summary={'sources':len(urls),'success':len(pages),'failed':failures,'rules':len(rules),'applied_changes':len(changes),'pending_dates':len(state['pending'])})
    write_json(root/'data/monitor-state.json',state)
    write_json(root/'data/review.json',review)
    if changes:
        history=read_json(root/'data/change-log.json',[])
        write_json(root/'data/change-log.json',history+changes)
        write_json(root/'data/conferences.json',records)
    build(root,now)
    print(json.dumps(state['summary']))
    return state['summary']


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--series')
    parser.add_argument('--fetch-only',action='store_true')
    args=parser.parse_args()
    # Protect local cron/server runs against simultaneous writes.
    import fcntl
    with (ROOT/'.update.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        update(only=args.series,fetch_only=args.fetch_only)
