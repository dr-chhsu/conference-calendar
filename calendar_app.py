"""Build RFC 5545 feeds and a static subscription page. Python standard library only."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
REMINDER_DAYS = [30, 14, 7, 1]


def read_json(path, default):
    return json.loads(path.read_text()) if path.exists() else copy.deepcopy(default)


def write_json(path, value):
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_bytes(data)
    os.replace(temp, path)


def escape(s):
    return str(s).replace('\\', '\\\\').replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def fold(line):
    """75 OCTETS, without splitting a UTF-8 codepoint (RFC 5545 section 3.1)."""
    result, chunk, size = [], '', 0
    for c in line:
        n = len(c.encode('utf-8'))
        if size + n > 75:
            result.append(chunk)
            chunk, size = ' ', 1
        chunk += c
        size += n
    return '\r\n'.join(result + [chunk])


def stamp(now):
    return now.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')


def date_property(key, val):
    if isinstance(val, datetime):
        if val.tzinfo is None:
            raise ValueError('Floating deadline is prohibited')
        return f'{key}:{stamp(val)}'
    return f'{key};VALUE=DATE:{val:%Y%m%d}'


def deadline_start(d):
    day = date.fromisoformat(d['date'])
    if d.get('time') and d.get('timezone'):
        return datetime.fromisoformat(f"{d['date']}T{d['time']}").replace(tzinfo=ZoneInfo(d['timezone']))
    return day


def description(r, d=None):
    lines = [f"領域：{r['category']}", f"會議：{r['series']} {r['year'] or '待公告'}", f"地點：{r['location']}"]
    lines.append('院內補助：列於一般外科補助名單（簡報第12頁；適用年度及申請條件未載明）' if r['subsidized'] else '院內補助：未列於提供的名單')
    status = d['status'] if d else r['meeting_status']
    labels = {'official':'官方資料已核對','slide_only':'僅據簡報，尚待官方核實','conflict':'來源有差異，待確認'}
    lines.append('資料狀態：' + labels.get(status,status))
    if d:
        if d.get('time') and d.get('timezone'):
            dt = deadline_start(d)
            lines += [f"官方截止：{d['date']} {d['time']} ({d['timezone']})", f"台灣時間：{dt.astimezone(ZoneInfo('Asia/Taipei')):%Y-%m-%d %H:%M}"]
        else:
            lines.append(f"截止日期：{d['date']}；未公告確切時間，全天顯示不代表可等到台灣午夜。")
            if d.get('timezone'):
                lines.append('公告時區：' + d['timezone'])
    else:
        lines.append('投稿補充紀錄：' + r['deadline_note'])
        for item in r['deadlines']:
            lines.append(f"{item['label']}：{item['date']} {item.get('time') or ''} {item.get('timezone') or ''} ({labels.get(item['status'],item['status'])})")
    sources = d.get('sources',[]) if d else r['meeting_sources']
    lines.extend(['來源：'+s for s in sources])
    if not sources:
        lines.append(f"來源：使用者提供的 Schedule of international conference - GS.pptx，第{r['slide']}頁")
    verified = d.get('verified_at') if d else r.get('meeting_verified_at')
    if verified:
        lines.append('日期核對紀錄：' + verified)
    if r['notes']:
        lines.append('備註：'+r['notes'])
    return '\n'.join(lines)


def events_for(records, include_milestones=False):
    events = []
    for r in records:
        prefix = '【院內補助】' if r['subsidized'] else ''
        tentative = '【待核實】' if r['meeting_status']!='official' else ''
        common = dict(subsidized=r['subsidized'], series=r['series'], category=r['category'],location=r['location'])
        if r.get('start') and r.get('end'):
            events.append(dict(**common, key=r['id']+'/meeting',kind='meeting',
                summary=f"{prefix}{tentative}{r['series']} {r['year']} 開會",
                start=date.fromisoformat(r['start']),end=date.fromisoformat(r['end'])+timedelta(days=1),
                description=description(r),url=next(iter(r['meeting_sources'] or r['monitor_urls']),''),
                status='CANCELLED' if r.get('cancelled') else ('CONFIRMED' if r['meeting_status']=='official' else 'TENTATIVE'), alarms=[30,7]))
        for d in r['deadlines']:
            if d['status']=='conflict' or not d.get('date'):
                continue
            start=deadline_start(d)
            end=start+timedelta(minutes=1) if isinstance(start,datetime) else start+timedelta(days=1)
            marker='【待核實】' if d['status']!='official' else ''
            ev=dict(**common,key=r['id']+'/'+d['id'],kind='deadline',
                summary=f"{prefix}{marker}{r['series']} {r['year']}｜{d['label']}",
                start=start,end=end,description=description(r,d),url=next(iter(d.get('sources') or r['monitor_urls']),''),
                status='CANCELLED' if d.get('cancelled') or r.get('cancelled') else ('CONFIRMED' if d['status']=='official' else 'TENTATIVE'), alarms=REMINDER_DAYS)
            events.append(ev)
            if include_milestones:
                # Separate events work even when a subscription client ignores VALARM.
                for days in REMINDER_DAYS:
                    m=copy.deepcopy(ev)
                    m.update(key=ev['key']+f'/reminder-{days}',kind='reminder',
                        start=start-timedelta(days=days),end=end-timedelta(days=days),
                        summary=f"{prefix}{marker}{r['series']} {r['year']}｜{d['label']}前 {days} 天",alarms=[])
                    events.append(m)
    return events


def render_event(ev, state, now):
    uid=hashlib.sha256(ev['key'].encode()).hexdigest()[:32]+'@gs-conference-calendar'
    lines=['BEGIN:VEVENT','UID:'+uid, date_property('DTSTART',ev['start']),date_property('DTEND',ev['end']),
        'SUMMARY:'+escape(ev['summary']),'DESCRIPTION:'+escape(ev['description']),'LOCATION:'+escape(ev.get('location','')),
        'CATEGORIES:'+escape(ev['category'])+','+escape(ev['kind']), 'STATUS:'+ev['status'],'TRANSP:TRANSPARENT']
    if ev.get('url'):
        lines.append('URL:'+ev['url'])
    for days in ev['alarms']:
        lines.extend(['BEGIN:VALARM','ACTION:DISPLAY',f'TRIGGER:-P{days}D','DESCRIPTION:'+escape(ev['summary']),'END:VALARM'])
    fingerprint=hashlib.sha256('\n'.join(lines).encode()).hexdigest()
    prev=state.get(uid)
    if not prev or prev['hash']!=fingerprint:
        state[uid]={'hash':fingerprint,'sequence':prev['sequence']+1 if prev else 0,'modified':stamp(now),'created':prev['created'] if prev else stamp(now)}
    meta=state[uid]
    lines[2:2]=['DTSTAMP:'+meta['modified'],'CREATED:'+meta['created'],'LAST-MODIFIED:'+meta['modified'],'SEQUENCE:'+str(meta['sequence'])]
    lines.append('END:VEVENT')
    return lines


def render_calendar(name, events, state, now):
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//GS Academic Conferences//ZH-TW','CALSCALE:GREGORIAN',
        'X-WR-CALNAME:'+escape(name),'X-WR-TIMEZONE:Asia/Taipei',
        'REFRESH-INTERVAL;VALUE=DURATION:PT12H','X-PUBLISHED-TTL:PT12H']
    for ev in sorted(events,key=lambda e:e['key']):
        lines.extend(render_event(ev,state,now))
    lines.append('END:VCALENDAR')
    return ('\r\n'.join(fold(line) for line in lines)+'\r\n').encode('utf-8')


def build(root=ROOT, now=None):
    now=now or datetime.now(UTC)
    records=read_json(root/'data/conferences.json',[])
    if not records:
        raise ValueError('Refusing to publish empty source data')
    state=read_json(root/'data/event-state.json',{})
    events=events_for(records,True)
    # Keep original UIDs and increasing sequence for the lifetime of the feed.
    specs={
      'all':('一般外科國際會議與投稿截止',lambda e:e['kind']!='reminder'),
      'subsidized':('院內補助｜國際會議與投稿截止',lambda e:e['subsidized'] and e['kind']!='reminder'),
      'deadlines':('國際會議｜投稿截止',lambda e:e['kind']=='deadline'),
      'subsidized-deadlines':('院內補助｜投稿截止',lambda e:e['subsidized'] and e['kind']=='deadline'),
      'reminders':('國際會議｜投稿準備提醒',lambda e:e['kind']=='reminder'),
      'subsidized-reminders':('院內補助｜投稿準備提醒',lambda e:e['subsidized'] and e['kind']=='reminder'),
    }
    counts={}
    for filename,(name,predicate) in specs.items():
        selected=[e for e in events if predicate(e)]
        atomic_write(root/f'public/{filename}.ics',render_calendar(name,selected,state,now))
        counts[filename]=len(selected)
    write_json(root/'data/event-state.json',state)
    write_json(root/'public/conferences.json',records)
    monitor=read_json(root/'data/monitor-state.json',{})
    write_json(root/'public/status.json',{
        'built_at':now.isoformat(),'series':len(set(r['series'] for r in records)), 'editions':len(records),
        'counts':counts,'meeting_verified':sum(r['meeting_status']=='official' for r in records),
        'deadline_verified':sum(d['status']=='official' for r in records for d in r['deadlines']),
        'monitor_last_run':monitor.get('last_run'),'monitor_summary':monitor.get('summary',{}),
        'automation_active':(root/'data/automation-active.json').exists(),
        'review':read_json(root/'data/review.json',[]),
    })
    print(json.dumps(counts,ensure_ascii=False))
    return counts


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['build'],nargs='?',default='build')
    parser.parse_args()
    build()
