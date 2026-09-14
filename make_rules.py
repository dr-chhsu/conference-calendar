"""Maintain explicit per-edition official-source parsing rules."""
import json,re
from calendar_app import ROOT,write_json,read_json
from monitor import DATE,MONTH,extract_rule
records=read_json(ROOT/'data/conferences.json',[]);rules=[]
lookup={r['id']:r for r in records}
def rule(rid,kind,url,pattern,identity=None,**kwargs):
 r=lookup[rid]
 rules.append(dict(record=rid,kind=kind,url=url,pattern=pattern,identity=identity or re.escape(r['series'])+r'.{0,70}'+str(r['year']),**kwargs))
def deadline(rid,url,anchor,identity=None,timed=False,deadline='abstract',label='摘要投稿截止',**kw):
 pattern=anchor+rf'\s*:?\s*(?:[A-Za-z]+,\s*)?(?P<date>{DATE})'
 if timed:pattern+=r'[,\s]*(?:at|@)?\s*(?P<time>\d{1,2}:\d{2}\s*[AP]M)\s*\(?(?P<zone>PDT|PST|PT|EDT|EST|ET|Eastern Time|JST|KST)\)?'
 rule(rid,'deadline',url,pattern,identity,deadline=deadline,label=label,**kw)

deadline('sages-2027','https://www.sages2027.org/',r'Submission Deadline',timed=True)
deadline('ahpba-2027',lookup['ahpba-2027']['monitor_urls'][1],r'Submission Deadline',timed=True)
deadline('aaes-2027',lookup['aaes-2027']['monitor_urls'][0],r'Submission Deadline')
deadline('ehs-2027',lookup['ehs-2027']['monitor_urls'][0],r'ABSTRACT SUBMISSION DEADLINE')
deadline('a-phpba-2027',lookup['a-phpba-2027']['monitor_urls'][0],r'Abstract Submission Deadline')
deadline('aphs-2026',lookup['aphs-2026']['monitor_urls'][0],r'Abstract Submission Deadline for Oral Presentations',identity=r'APHS\s*2026',deadline='oral',label='口頭報告投稿截止',date_timezone='Asia/Tokyo')
deadline('aphs-2026',lookup['aphs-2026']['monitor_urls'][0],r'Abstract Submission Deadline for E\.Poster Presentations',identity=r'APHS\s*2026',deadline='eposter',label='電子海報投稿截止',date_timezone='Asia/Tokyo')
deadline('st-gallen-2027',lookup['st-gallen-2027']['monitor_urls'][0],r'Abstract submission for SGBCC 2027.{0,110}until',identity='SGBCC 2027')
deadline('asco-gi-2027',lookup['asco-gi-2027']['monitor_urls'][1],r'(?<!Breaking )Abstract Submission Deadline',identity=r'2027 ASCO Gastrointestinal',timed=True)
deadline('asco-gi-2027',lookup['asco-gi-2027']['monitor_urls'][1],r'Late-Breaking Abstract Submission Deadline',identity=r'2027 ASCO Gastrointestinal',timed=True,deadline='late-breaking',label='Late-breaking 投稿截止（需符合資格）')
# Dedicated congress pages may publish the missing deadline later. Do not match a general
# registration deadline or reuse a date without an explicit year.
for rid,ident in [('wctc-2027','World Congress on Thyroid Cancer'),('ills-2027','ILLS 2027'),('gbcc-2027','GBCC 2027'),('ifso-2027','IFSO.*2027')]:
 r=lookup[rid];url=r['monitor_urls'][-1] if rid=='ifso-2027' else r['monitor_urls'][0]
 deadline(rid,url,r'Abstract Submission Deadline',identity=ident)
deadline('wctc-2027','https://thyroidworldcongress.com/abstracts/',r'Abstract submissions close',identity=r'WCTC.{0,100}2027')
deadline('sso-2027',lookup['sso-2027']['monitor_urls'][-1],r'Abstract Submission Deadline',identity=r'SSO.{0,100}2027')
deadline('gbcc-2027',lookup['gbcc-2027']['monitor_urls'][-1],r'Abstract Submission Deadline',identity=r'GBCC.{0,100}2027')

DAY=r'\s*(?:\([A-Za-z.]+\))?\s*'
SEP=r'\s*(?:[-–—]|to)\s*'
def mr(rid,url=None,anchor='',order='md',identity=None):
 r=lookup[rid];year=str(r['year']);url=url or r['monitor_urls'][0]
 if order=='md':pat=rf'(?P<month>{MONTH})\s+(?P<first>\d{{1,2}}){DAY}{SEP}(?P<last>\d{{1,2}}){DAY},?\s*(?P<year>{year})'
 elif order=='dm':pat=rf'(?P<first>\d{{1,2}}){DAY}{SEP}(?P<last>\d{{1,2}}){DAY}(?P<month>{MONTH}),?\s+(?P<year>{year})'
 elif order=='cross_dm':pat=rf'(?P<first>\d{{1,2}})\s+(?P<startmonth>{MONTH}){SEP}(?P<last>\d{{1,2}})\s+(?P<endmonth>{MONTH}),?\s+(?P<year>{year})'
 elif order=='cross_md':pat=rf'(?P<startmonth>{MONTH})\s+(?P<first>\d{{1,2}}){DAY}{SEP}(?P<endmonth>{MONTH})\s+(?P<last>\d{{1,2}}){DAY},?\s*(?P<year>{year})'
 rule(rid,'meeting',url,anchor+pat,identity or (re.escape(r['series'])+r'.{0,120}'+year))

mr('sages-2027','https://www.sages2027.org/')
mr('ahpba-2027',anchor=r'AHPBA 2027\s*\|\s*')
mr('aaes-2027',anchor=r'Scientific Meeting:\s*')
mr('a-phpba-2027')
mr('ehs-2027',anchor=r'CONFERENCE DATES\s*',order='dm')
mr('st-gallen-2027',order='dm',identity='SGBCC 2027')
mr('ihpba-2028',anchor=r'World Congress - Vancouver, Canada\s*',order='dm',identity='International Hepato-Pancreato-Biliary')
mr('e-ahpba-2027',anchor=r'E-AHPBA Biennial Congress\s*[-–]\s*',order='dm',identity='E-AHPBA')
mr('ifso-2027',order='dm')
mr('ifso-2028',order='dm')
mr('asmbs-2027',order='cross_md',anchor=r'ASMBS Annual Meeting 2027\s*')
mr('asmbs-2028',anchor=r'ASMBS Annual Meeting 2028\s*')
mr('gbcc-2027')
mr('wctc-2027',identity='World Congress on Thyroid Cancer')
mr('ame e-2027'.replace(' ',''),order='cross_dm',anchor=r'Helsinki, Finland\.\s*')
mr('wcs-2028',order='dm',anchor=r'Join us from\s*',identity='SURGICAL WEEK 2028')
mr('apmec-2027',order='dm',identity='APMEC 2027')
mr('eaes-2027',url=lookup['eaes-2027']['monitor_urls'][1],order='dm',anchor=r'from\s*')
mr('sso-2027');mr('sso-2028',order='cross_md',anchor=r'SSO 2028 Tampa, FL\s*')
mr('s abcs-2026'.replace(' ',''),identity='San Antonio Breast Cancer Symposium')
mr('sabcs-2027',identity='San Antonio Breast Cancer Symposium')
mr('ata-2026',identity='American Thyroid Association')
mr('elsa-2026',order='dm',identity='ELSA 2026')
mr('esa-2027',order='dm',anchor=r'Date:\s*',identity='European Surgical Association')
mr('ills-2027',identity='ILLS 2027')
mr('jgca-2027',order='cross_md',anchor=r'On-site］',identity='99th Annual Meeting')
mr('aamc-2027',anchor='',identity='Learn Serve Lead')
rule('eta-2027','meeting',lookup['eta-2027']['monitor_urls'][0],r'(?P<start>\d{2}\.\d{2}\.2027)\s*[-–]\s*(?P<end>\d{2}\.\d{2}\.2027)',identity='ETA2027')
write_json(ROOT/'data/rules.json',rules)
print('Wrote',len(rules),'scoped source rules')
