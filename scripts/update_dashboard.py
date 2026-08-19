#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, math, urllib.request, urllib.error
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE=Path(__file__).resolve().parents[1]
DATA=BASE/'data/dashboard-data.json'; STATUS=BASE/'status/last-run.txt'
ROOT='https://api.jobindsats.dk/v3'
KNOWN={'unemployment':'y25i01','registered':'y25i02','longterm':'y25i09','dagpengeDuration':'y01a21'}

def norm(x):
    return str(x or '').lower().replace('æ','ae').replace('ø','oe').replace('å','aa').strip()

def num(v):
    if v is None or isinstance(v,bool): return None
    if isinstance(v,(int,float)): x=float(v)
    else:
        t=str(v).strip().replace('\xa0','').replace(' ','')
        if t in {'','-','..','.','null'}: return None
        if ',' in t: t=t.replace('.','').replace(',','.')
        try:x=float(t)
        except:return None
    if not math.isfinite(x): return None
    return int(x) if x.is_integer() else round(x,4)

def get(path):
    token=os.environ.get('JOBINDSATS_API_TOKEN') or os.environ.get('API_ADGANG')
    if not token: raise RuntimeError('API_ADGANG mangler')
    req=urllib.request.Request(f"{ROOT}/{path.lstrip('/')}",headers={'Accept':'application/json','Authorization':f'Bearer {token}','User-Agent':'Danske-A-kasser-kommunal-dashboard/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=90) as r:return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body=e.read().decode('utf-8',errors='replace')
        raise RuntimeError(f'HTTP {e.code}: {body[:400]}') from e

def records(path):
    p=get(path); cols=p.get('columns'); rows=p.get('rows')
    if not isinstance(cols,list) or not isinstance(rows,list): raise RuntimeError('Uventet Jobindsats-format')
    return [dict(zip(cols,r)) for r in rows]

def period_key(r):
    return next((k for k in r if 'periode' in norm(k) or norm(k)=='period'),None)

def area_key(r):
    return next((k for k in r if 'kommune' in norm(k) or 'omraade' in norm(k) or norm(k)=='region'),None)

def find_col(r,alts):
    for terms in alts:
        for k in r:
            n=norm(k)
            if all(norm(t) in n for t in terms): return k
    return None

def classify(r,exclude):
    text=' | '.join(str(v) for k,v in r.items() if k not in exclude and not isinstance(v,(int,float))).lower()
    if 'dagpenge' in text or 'a-dagpenge' in text:return 'dagpenge'
    if 'kontanthj' in text or 'uddannelseshj' in text:return 'kontanthjaelp'
    if 'i alt' in text or 'alle' in text or 'total' in text:return 'total'
    return 'other'

def query_candidates(table,months=60,expand_ygrp=True,national=False):
    ygrp='*' if expand_ygrp else '/'; area='/' if national else '*'
    return [
        f'data/{table}?mgroup.*=*&period.M=latest:{months}&hierarchy._nykom={area}&hierarchy._ygrpi09={ygrp}&hierarchy._akassebl=/&format=json',
        f'data/{table}?mgroup.*=*&period.M=latest:{months}&hierarchy._nykom={area}&hierarchy._ygrpi09={ygrp}&format=json',
        f'data/{table}?mgroup.*=*&period.M=latest:{months}&hierarchy._nykom={area}&format=json'
    ]

def fetch_first(table,months=60,expand_ygrp=True,national=False):
    errors=[]
    for q in query_candidates(table,months,expand_ygrp,national):
        try:
            r=records(q)
            if r:return r
        except Exception as e:errors.append(str(e))
    raise RuntimeError(' | '.join(errors[-3:]))

def build_time(rows,kind):
    if not rows:return {}
    pk,ak=period_key(rows[0]),area_key(rows[0])
    if not pk or not ak: raise RuntimeError(f'Mangler periode/område: {list(rows[0])}')
    measures={
      'unemployment':find_col(rows[0],[['fuldtidsled','pct'],['arbejdsstyr','pct']]),
      'count':find_col(rows[0],[['ledige','fuldtidsperson'],['fuldtidsled'],['antal','fuldtidsperson']]),
      'new':find_col(rows[0],[['nytilmeldte'],['nytilmeld']]),
      'long':find_col(rows[0],[['langtidsledige','person'],['langtidsled']])
    }
    mk=measures[kind]; rate=measures['unemployment'] if kind=='count' else None
    if not mk: raise RuntimeError(f'Kunne ikke finde målingskolonne. Kolonner: {list(rows[0])}')
    ex={pk,ak,mk};
    if rate:ex.add(rate)
    g=defaultdict(lambda:defaultdict(lambda:defaultdict(dict))); names={}
    for r in rows:
        area=str(r.get(ak,'')).replace(' Kommune','').strip(); aid=norm(area); p=str(r.get(pk,''))
        if not area or not p:continue
        names[aid]=area; group=classify(r,ex); v=num(r.get(mk)); rv=num(r.get(rate)) if rate else None
        if v is not None:g[aid][p][group]['value']=v
        if rv is not None:g[aid][p][group]['rate']=rv
    out={}
    for aid,ps in g.items():
        labels=sorted(ps); e={'name':names[aid],'labels':labels}
        for group in ['total','dagpenge','kontanthjaelp']:
            vals=[]; rates=[]
            for p in labels:
                d=ps[p].get(group,{})
                v=d.get('value')
                if group=='total' and v is None:
                    parts=[ps[p].get(x,{}).get('value') for x in ['dagpenge','kontanthjaelp']]
                    v=sum(x for x in parts if x is not None) if any(x is not None for x in parts) else None
                vals.append(v); rates.append(d.get('rate'))
            e[group]=vals
            if rate:e[group+'Rate']=rates
        out[aid]=e
    return out

def first_series(series):
    if not series: raise RuntimeError('Ingen data i national serie')
    s=next(iter(series.values())); s['name']='Hele landet'; return s

def find_table(terms):
    payload=get('tables?format=json'); best=[]
    def walk(x):
        if isinstance(x,dict):
            text=norm(json.dumps(x,ensure_ascii=False)); tid=next((str(v) for k,v in x.items() if norm(k) in {'id','tableid','table_id'} and isinstance(v,str) and re.match(r'^[A-Za-z].*\d',v)),None)
            if tid and all(norm(t) in text for t in terms):best.append(tid)
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(payload); return best[0] if best else None

def duration(rows,jobready=False):
    if not rows:return {}
    pk,ak=period_key(rows[0]),area_key(rows[0]); mk=find_col(rows[0],[['antal','forloeb'],['antal']]); dk=find_col(rows[0],[['varighed']])
    if not all([pk,ak,mk,dk]):raise RuntimeError('Varighedskolonner kunne ikke identificeres')
    ex={pk,ak,mk,dk}; g=defaultdict(lambda:defaultdict(float)); names={}; periods={}
    for r in rows:
        txt=' | '.join(str(v) for k,v in r.items() if k not in ex).lower()
        if jobready and not ('jobparat' in txt or 'aabenlyst uddannelsesparat' in norm(txt)):continue
        v=num(r.get(mk)); lab=str(r.get(dk,'')).strip(); area=str(r.get(ak,'')).replace(' Kommune','').strip(); aid=norm(area)
        if v is None or not lab or 'i alt'==norm(lab):continue
        names[aid]=area; periods[aid]=max(periods.get(aid,''),str(r.get(pk,''))); g[aid][lab]+=v
    return {aid:{'name':names[aid],'period':periods[aid],'labels':list(vals),'values':[vals[x] for x in vals]} for aid,vals in g.items()}

def fetch_duration(table,jobready=False,national=False):
    area='/' if national else '*'
    qs=[f'data/{table}?mgroup.*=*&period.M=latest:1&hierarchy._nykom={area}&hierarchy._varighed=*&format=json',f'data/{table}?mgroup.*=*&period.M=latest:1&hierarchy._nykom={area}&format=json']
    last=None
    for q in qs:
        try:return duration(records(q),jobready)
        except Exception as e:last=e
    raise last or RuntimeError('Varighed fejlede')

def exit_series(rows):
    if not rows:return {}
    pk,ak=period_key(rows[0]),area_key(rows[0]); ex={pk,ak}; cols={}
    for m in [3,6,9,12]:
        c=find_col(rows[0],[[str(m),'beskaeftig'],[str(m),'andel']])
        if c:cols[m]=c; ex.add(c)
    if len(cols)<2:raise RuntimeError('Kunne ikke identificere 3/6/9/12-målinger')
    g=defaultdict(lambda:defaultdict(dict)); names={}; periods={}
    for r in rows:
        area=str(r.get(ak,'')).replace(' Kommune','').strip(); aid=norm(area); group=classify(r,ex)
        if group not in {'dagpenge','kontanthjaelp'}:continue
        names[aid]=area; periods[aid]=max(periods.get(aid,''),str(r.get(pk,'')))
        for m,c in cols.items():g[aid][group][m]=num(r.get(c))
    return {aid:{'name':names[aid],'period':periods[aid],'months':[3,6,9,12],'dagpenge':[g[aid]['dagpenge'].get(m) for m in [3,6,9,12]],'kontanthjaelp':[g[aid]['kontanthjaelp'].get(m) for m in [3,6,9,12]]} for aid in g}

def main():
    now=datetime.now(ZoneInfo('Europe/Copenhagen')); sources={}; municipalities={}; national={'name':'Hele landet'}; failures=[]; successful=[]
    def add_source(name,table,series,note=''):
        latest=max((v.get('labels',[''])[-1] if v.get('labels') else v.get('period','') for v in series.values()),default='') or None
        sources[name]={'state':'ok','source':'Jobindsats.dk / STAR','dataset':table,'latestPeriod':latest,'checkedAt':now.isoformat(timespec='seconds'),'note':note};successful.append(name)
    def fail(name,table,e):
        sources[name]={'state':'failed','source':'Jobindsats.dk / STAR','dataset':table,'note':str(e)[:500]};failures.append(name)

    table=KNOWN['unemployment']
    try:
        ser=build_time(fetch_first(table,60,True,False),'count')
        for aid,s in ser.items():municipalities.setdefault(aid,{'name':s['name']})['unemployment']=s
        add_source('unemployment',table,ser,'Faktisk registerbaseret ledighed. Ikke sæsonkorrigeret på kommuneniveau.')
    except Exception as e: fail('unemployment',table,e)
    try:
        ser=build_time(fetch_first(table,60,True,True),'count'); national['unemployment']=first_series(ser); add_source('unemploymentNational',table,{'hele landet':national['unemployment']},'Officielt landstal fra samme Jobindsats-måling.')
    except Exception as e: fail('unemploymentNational',table,e)

    table=KNOWN['registered']
    try:
        ser=build_time(fetch_first(table,36,True,False),'new')
        for aid,s in ser.items():municipalities.setdefault(aid,{'name':s['name']})['newlyRegistered']=s
        add_source('registered',table,ser,'Nytilmeldte ledige på Jobnet.')
    except Exception as e: fail('registered',table,e)
    try:
        ser=build_time(fetch_first(table,36,True,True),'new'); national['newlyRegistered']=first_series(ser); add_source('registeredNational',table,{'hele landet':national['newlyRegistered']})
    except Exception as e: fail('registeredNational',table,e)

    table=KNOWN['longterm']
    try:
        ser=build_time(fetch_first(table,36,True,False),'long')
        for aid,s in ser.items():municipalities.setdefault(aid,{'name':s['name']})['longterm']=s
        add_source('longterm',table,ser)
    except Exception as e: fail('longterm',table,e)
    try:
        ser=build_time(fetch_first(table,36,True,True),'long'); national['longterm']=first_series(ser); add_source('longtermNational',table,{'hele landet':national['longterm']})
    except Exception as e: fail('longtermNational',table,e)

    for name,terms,jobready in [('dagpengeDuration',['forloeb','varighed','dagpenge'],False),('kontanthjaelpDuration',['forloeb','varighed','kontanthjaelp'],True)]:
        table=KNOWN.get(name) or find_table(terms); target='dagpenge' if not jobready else 'kontanthjaelp'
        try:
            if not table:raise RuntimeError('Tabel kunne ikke identificeres via metadata')
            ser=fetch_duration(table,jobready,False)
            for aid,s in ser.items():municipalities.setdefault(aid,{'name':s['name']}).setdefault('duration',{})[target]=s
            add_source(name,table,ser)
        except Exception as e: fail(name,table,e)
        try:
            if not table:raise RuntimeError('Tabel kunne ikke identificeres via metadata')
            ser=fetch_duration(table,jobready,True); national.setdefault('duration',{})[target]=first_series(ser); add_source(name+'National',table,{'hele landet':national['duration'][target]})
        except Exception as e: fail(name+'National',table,e)

    table=find_table(['andel','beskaeftigelse','nyledighed']) or find_table(['beskaeftigelse','nyledighed'])
    try:
        if not table:raise RuntimeError('Tabel kunne ikke identificeres via metadata')
        ser=exit_series(fetch_first(table,1,True,False))
        for aid,s in ser.items():municipalities.setdefault(aid,{'name':s['name']})['employmentExit']=s
        add_source('employmentExit',table,ser)
    except Exception as e: fail('employmentExit',table,e)
    try:
        if not table:raise RuntimeError('Tabel kunne ikke identificeres via metadata')
        ser=exit_series(fetch_first(table,1,True,True)); national['employmentExit']=first_series(ser); add_source('employmentExitNational',table,{'hele landet':national['employmentExit']})
    except Exception as e: fail('employmentExitNational',table,e)

    state='ok' if not failures else ('partial' if successful else 'failed')
    if not municipalities:raise RuntimeError('Ingen kommunedata kunne hentes')
    months=['januar','februar','marts','april','maj','juni','juli','august','september','oktober','november','december']
    data={'meta':{'title':'Kommunal beskæftigelsesindsats','updated':f'{now.day}. {months[now.month-1]} {now.year}','retrievedAt':now.isoformat(timespec='seconds'),'source':'Jobindsats.dk / STAR','sourceStatus':sources,'updateStatus':{'state':state,'successful':successful,'failed':failures,'checkedAt':now.isoformat(timespec='seconds')}},'municipalities':municipalities,'national':national}
    DATA.parent.mkdir(parents=True,exist_ok=True);DATA.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    STATUS.parent.mkdir(parents=True,exist_ok=True);STATUS.write_text(f'status: {state}\ntid_utc: {datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")}\ndato_dk: {now.date()}\n',encoding='utf-8')
    print(f'Opdateret: {state}. Kommuner: {len(municipalities)}. Nationale sektioner: {len(national)-1}')
if __name__=='__main__':main()
