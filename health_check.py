"""Read-only production checks. Reports failures; never edits conference dates."""
import argparse
import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse

FEEDS=('all','subsidized','deadlines','subsidized-deadlines','reminders','subsidized-reminders')


def freshness(value, now, hours=36):
    if not value:
        raise ValueError('缺少更新時間')
    when=datetime.fromisoformat(value.replace('Z','+00:00'))
    if when.tzinfo is None:
        raise ValueError('更新時間缺少時區')
    age=now-when
    if age>timedelta(hours=hours):
        raise ValueError(f'更新已超過 {hours} 小時（{age.total_seconds()/3600:.1f} 小時）')
    if age<timedelta(minutes=-10):
        raise ValueError('更新時間異常，位於未來')


def fetch(url):
    errors=[]
    for attempt in range(3):
        try:
            request=Request(url,headers={'User-Agent':'GSCalendarHealth/1.0','Cache-Control':'no-cache'})
            with urlopen(request,timeout=25) as response:
                body=response.read(8_000_001)
                if len(body)>8_000_000:raise ValueError('回應過大')
                if response.status!=200:raise ValueError(f'HTTP {response.status}')
                return body,response.headers.get_content_type(),errors
        except Exception as exc:
            errors.append(str(exc))
            if attempt<2:time.sleep(2**attempt)
    raise RuntimeError('; '.join(errors))


def parse_feed(raw, expected):
    from icalendar import Calendar
    if not raw.startswith(b'BEGIN:VCALENDAR') or not raw.rstrip().endswith(b'END:VCALENDAR'):
        raise ValueError('不是完整 iCalendar 檔案')
    cal=Calendar.from_ical(raw)
    events=cal.walk('VEVENT')
    if len(events)!=expected:raise ValueError(f'事件數 {len(events)} 與狀態檔 {expected} 不同')
    uids=set()
    for e in events:
        for prop in ('UID','DTSTART','DTEND','DTSTAMP','SEQUENCE','SUMMARY'):
            if prop not in e:raise ValueError(f'事件缺少 {prop}')
        uid=str(e['UID'])
        if uid in uids:raise ValueError('重複 UID：'+uid)
        uids.add(uid)
        start,end=e.decoded('DTSTART'),e.decoded('DTEND')
        if type(start)!=type(end) or end<=start:raise ValueError('起迄日期錯誤')
        if isinstance(start,datetime) and (start.tzinfo is None or end.tzinfo is None):
            raise ValueError('投稿時間缺少時區')
    return uids


def check_subsets(feeds):
    for small,big in [('subsidized','all'),('deadlines','all'),('subsidized-deadlines','subsidized'),
                      ('subsidized-deadlines','deadlines'),('subsidized-reminders','reminders')]:
        if not feeds[small]<=feeds[big]:raise ValueError(f'{small} 含不在 {big} 中的事件')
    if feeds['all']&feeds['reminders']:raise ValueError('提醒事件與主要事件 UID 重複')


def browser_check(base, records, output, executable=None):
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as p:
        opts={'headless':True}
        if executable:opts['executable_path']=executable
        browser=p.chromium.launch(**opts)
        context=browser.new_context(viewport={'width':1440,'height':1000})
        context.tracing.start(screenshots=True,snapshots=True,sources=True)
        page=context.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            response=page.goto(base,wait_until='networkidle',timeout=45000)
            assert response and response.status==200,'首頁 HTTP 異常'
            rows=page.locator('#rows tr')
            expect(rows).to_have_count(len(records),timeout=20000)
            assert '無法載入' not in page.locator('#status').inner_text(),'頁面資料載入失敗'
            page.screenshot(path=str(output/'desktop.png'))
            page.locator('#funded').check()
            expect(rows).to_have_count(sum(bool(r['subsidized']) for r in records))
            page.locator('#funded').uncheck()
            page.locator('#verified').check()
            expect(rows).to_have_count(sum(r['meeting_status']=='official' for r in records))
            page.locator('#verified').uncheck()
            sample=records[0]['series']
            page.locator('#search').fill(sample)
            expect(rows).to_have_count(sum(sample.lower() in ' '.join([r['series'],r['location'],r['category']]).lower() for r in records))
            page.locator('#search').fill('zz-no-such-conference-zz')
            expect(rows).to_have_count(0)
            page.locator('#search').fill('')
            category=records[0]['category']
            page.locator('#category').select_option(category)
            expect(rows).to_have_count(sum(r['category']==category for r in records))
            page.locator('#category').select_option('')
            for name in FEEDS:
                link=page.locator(f'a[download][href="{name}.ics"]')
                expect(link).to_have_count(1)
                expected=urljoin(base,name+'.ics').replace('https:','webcal:',1)
                expect(page.locator(f'a[href="{expected}"]')).to_have_count(1)
            origin=urlparse(base);context.grant_permissions(['clipboard-read','clipboard-write'],origin=f'{origin.scheme}://{origin.netloc}')
            page.locator('button.copy[data-feed="all"]').click()
            expect(page.locator('#toast')).to_be_visible()
            assert page.evaluate('navigator.clipboard.readText()')==urljoin(base,'all.ics'),'複製的訂閱網址不正確'
            page.set_viewport_size({'width':390,'height':844})
            expect(rows).to_have_count(len(records))
            assert page.evaluate('document.body.scrollWidth <= innerWidth + 1'),'手機版整頁水平溢出'
            page.screenshot(path=str(output/'mobile.png'))
            if errors:raise ValueError('JavaScript 錯誤：'+'; '.join(errors))
        finally:
            try:page.screenshot(path=str(output/'last-page.png'))
            finally:
                context.tracing.stop(path=str(output/'browser-trace.zip'))
                browser.close()


def run(base, output, browser=True, executable=None):
    output.mkdir(parents=True,exist_ok=True)
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'url':base,'checks':[],'warnings':[]}
    def check(name,fn):
        try:
            result=fn();report['checks'].append({'name':name,'ok':True});return result
        except Exception as exc:
            report['checks'].append({'name':name,'ok':False,'error':str(exc)});return None
    def get(path,kind):
        raw,content_type,retries=fetch(urljoin(base,path))
        if retries:report['warnings'].append(f'{path} 經重試恢復：{retries}')
        if content_type!=kind:raise ValueError(f'{path} Content-Type 為 {content_type}，應為 {kind}')
        return raw
    check('首頁可讀取',lambda:get('','text/html'))
    status=check('狀態 JSON',lambda:json.loads(get('status.json','application/json')))
    records=check('會議 JSON',lambda:json.loads(get('conferences.json','application/json')))
    if status is not None:
        now=datetime.now(timezone.utc)
        check('日曆 36 小時內更新',lambda:freshness(status.get('built_at'),now))
        check('官網追蹤 36 小時內執行',lambda:freshness(status.get('monitor_last_run'),now))
        def metadata():
            assert status.get('automation_active'),'更新排程未啟用'
            summary=status['monitor_summary']
            assert summary.get('success',0)>0,'所有官網來源都讀取失敗'
            if summary.get('failed',0):report['warnings'].append(f"官網來源 {summary['failed']}/{summary['sources']} 讀取失敗，請看網站待確認清單。")
            if records is not None:
                assert len(records)>0 and status['editions']==len(records),'會議筆數不一致或資料為空'
                assert status['series']==len({r['series'] for r in records}),'會議系列數不一致'
        check('資料與排程狀態',metadata)
        feeds={}
        for name in FEEDS:
            parsed=check(name+'.ics',lambda name=name:parse_feed(get(name+'.ics','text/calendar'),status['counts'][name]))
            if parsed is not None:feeds[name]=parsed
        if len(feeds)==len(FEEDS):check('日曆子集合與 UID 一致',lambda:check_subsets(feeds))
    if browser and records:
        check('桌面／手機互動與 JavaScript',lambda:browser_check(base,records,output,executable))
    report['ok']=all(c['ok'] for c in report['checks'])
    (output/'health.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# 日曆網站健康檢查',f"檢查時間：{report['checked_at']}",f'網站：{base}','']
    for c in report['checks']:lines.append(f"- {'✅' if c['ok'] else '❌'} {c['name']}"+(f"：{c['error']}" if not c['ok'] else ''))
    if report['warnings']:lines+=['','## 需留意的來源問題']+['- '+w for w in report['warnings']]
    lines+=['','這是自動檢查與診斷，不會自動改寫程式或確認未公告的會議日期。']
    summary='\n'.join(lines)+'\n';(output/'summary.md').write_text(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write(summary)
    print(summary)
    return 0 if report['ok'] else 1


if __name__=='__main__':
    args=argparse.ArgumentParser()
    args.add_argument('--url',default='https://dr-chhsu.github.io/conference-calendar/')
    args.add_argument('--output',type=Path,default=Path('health-results'))
    args.add_argument('--no-browser',action='store_true')
    args.add_argument('--browser-executable')
    a=args.parse_args()
    raise SystemExit(run(a.url.rstrip('/')+'/',a.output,not a.no_browser,a.browser_executable))
