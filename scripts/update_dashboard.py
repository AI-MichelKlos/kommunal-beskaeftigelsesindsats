#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / 'data/dashboard-data.json'
STATUS = BASE / 'status/last-run.txt'
ROOT = 'https://api.jobindsats.dk/v3'
WEB_ROOT = 'https://jobindsats.dk'
KNOWN = {
    'unemployment': 'y25i01',
    'longterm': 'y25i09',
    'cashAssistance': 'y60a02',
    'activation': 'y60c07',
    'offers': 'y60c02',
    'ordinaryHours': 'y60j01',
}


def norm(x):
    return str(x or '').lower().replace('æ', 'ae').replace('ø', 'oe').replace('å', 'aa').strip()


def num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = float(v)
    else:
        t = str(v).strip().replace('\xa0', '').replace(' ', '')
        if t in {'', '-', '..', '.', 'null'}:
            return None
        if ',' in t:
            t = t.replace('.', '').replace(',', '.')
        try:
            x = float(t)
        except ValueError:
            return None
    if not math.isfinite(x):
        return None
    return int(x) if x.is_integer() else round(x, 4)


def get(path):
    token = os.environ.get('JOBINDSATS_API_TOKEN') or os.environ.get('API_ADGANG')
    if not token:
        raise RuntimeError('API_ADGANG mangler')
    request = urllib.request.Request(
        f"{ROOT}/{path.lstrip('/')}",
        headers={
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}',
            'User-Agent': 'Danske-A-kasser-kommunal-dashboard/1.1',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        body = error.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'HTTP {error.code}: {body[:400]}') from error


def web_json(path, body=None):
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
    headers = {'Accept': 'application/json', 'User-Agent': 'Danske-A-kasser-kommunal-dashboard/1.1'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    last_error = None
    for attempt in range(4):
        request = urllib.request.Request(f'{WEB_ROOT}{path}', data=payload, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                value = json.loads(response.read().decode('utf-8'))
                return json.loads(value) if isinstance(value, str) else value
        except urllib.error.HTTPError as error:
            message = error.read().decode('utf-8', errors='replace')
            last_error = RuntimeError(f'Jobindsats web HTTP {error.code}: {message[:400]}')
            if error.code not in {429, 502, 503, 504} or attempt == 3:
                raise last_error from error
        except urllib.error.URLError as error:
            last_error = RuntimeError(f'Jobindsats web netværksfejl: {error.reason}')
            if attempt == 3:
                raise last_error from error
        time.sleep(2 ** attempt)
    raise last_error or RuntimeError('Ukendt fejl fra Jobindsats web')


def records(path):
    payload = get(path)
    columns, rows = payload.get('columns'), payload.get('rows')
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise RuntimeError('Uventet Jobindsats-format')
    return [dict(zip(columns, row)) for row in rows]


def metadata(table):
    return web_json(f'/Metadata/DatabankElementPage?maalingId={table}')


def metadata_periods(meta, period_type, count):
    values = [
        str(period.get('period', '')).strip()
        for period in meta.get('periodes', [])
        if str(period.get('periodType', '')).strip() == period_type
    ]
    return sorted(value for value in values if value)[-count:]


def metadata_areas(meta):
    for hierarchy in meta.get('maalingHierarchiesContainer', []):
        if hierarchy.get('hierarchyId') == '_nykom':
            return [
                str(member.get('name', '')).strip()
                for member in hierarchy.get('hierarchies', [])
                if str(member.get('name', '')).strip() not in {'', 'Uoplyst område'}
            ]
    raise RuntimeError('Kommunelisten mangler i Jobindsats-metadata')


def frontend_records(table, periods, areas, measures, dimensions=None):
    body = {
        'cube': table,
        'period': json.dumps({'period': periods}, ensure_ascii=False),
        'area': json.dumps({'_nykom': areas}, ensure_ascii=False),
        'measure': json.dumps({'measure': measures}, ensure_ascii=False),
        'dimension': None,
    }
    if dimensions:
        body['dimension'] = json.dumps({'dimension': list(dimensions)}, ensure_ascii=False)
        for index, (hierarchy, members) in enumerate(dimensions.items(), 1):
            body[f'dim{index}'] = json.dumps({hierarchy: members}, ensure_ascii=False)
    payload = web_json('/Metadata/getdata', body)
    header = payload.get('header') or []
    rows = payload.get('data')
    if len(header) < 2 or not isinstance(rows, list):
        raise RuntimeError(f'Uventet datatabel fra Jobindsats for {table}')
    seen, columns = defaultdict(int), []
    for label in header[1]:
        cleaned = str(label or '').strip()
        seen[cleaned] += 1
        columns.append(cleaned if seen[cleaned] == 1 else f'{cleaned} #{seen[cleaned]}')
    return [dict(zip(columns, row)) for row in rows]


def period_key(row):
    return next((key for key in row if 'periode' in norm(key) or norm(key) == 'period'), None)


def area_key(row):
    return next((key for key in row if 'kommune' in norm(key) or 'omraade' in norm(key) or norm(key) == 'region'), None)


def find_col(row, alternatives):
    for terms in alternatives:
        for key in row:
            normalized = norm(key)
            if all(norm(term) in normalized for term in terms):
                return key
    return None


def classify(row, exclude):
    text = ' | '.join(
        str(value) for key, value in row.items()
        if key not in exclude and not isinstance(value, (int, float))
    ).lower()
    if 'dagpenge' in text or 'a-dagpenge' in text:
        return 'dagpenge'
    if 'kontanthj' in text or 'uddannelseshj' in text:
        return 'kontanthjaelp'
    if 'i alt' in text or 'alle' in text or 'total' in text:
        return 'total'
    return 'other'


def query_candidates(table, months=60, expand_ygrp=True, national=False):
    ygrp = '*' if expand_ygrp else '/'
    area = '/' if national else '*'
    return [
        f'data/{table}?mgroup.*=*&period.M=latest:{months}&hierarchy._nykom={area}&hierarchy._ygrpi09={ygrp}&hierarchy._akassebl=/&format=json',
        f'data/{table}?mgroup.*=*&period.M=latest:{months}&hierarchy._nykom={area}&hierarchy._ygrpi09={ygrp}&format=json',
        f'data/{table}?mgroup.*=*&period.M=latest:{months}&hierarchy._nykom={area}&format=json',
    ]


def fetch_first(table, months=60, expand_ygrp=True, national=False):
    errors = []
    for query in query_candidates(table, months, expand_ygrp, national):
        try:
            result = records(query)
            if result:
                return result
        except Exception as error:
            errors.append(str(error))
    raise RuntimeError(' | '.join(errors[-3:]))


def build_time(rows, kind):
    if not rows:
        return {}
    pk, ak = period_key(rows[0]), area_key(rows[0])
    if not pk or not ak:
        raise RuntimeError(f'Mangler periode/område: {list(rows[0])}')
    measures = {
        'unemployment': find_col(rows[0], [['fuldtidsled', 'pct'], ['arbejdsstyr', 'pct']]),
        'count': find_col(rows[0], [['ledige', 'fuldtidsperson'], ['fuldtidsled'], ['antal', 'fuldtidsperson']]),
        'long': find_col(rows[0], [['langtidsledige', 'person'], ['langtidsled']]),
    }
    mk = measures[kind]
    rate = measures['unemployment'] if kind == 'count' else None
    if not mk:
        raise RuntimeError(f'Kunne ikke finde målingskolonne. Kolonner: {list(rows[0])}')
    excluded = {pk, ak, mk}
    if rate:
        excluded.add(rate)
    grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    names = {}
    for row in rows:
        area = str(row.get(ak, '')).replace(' Kommune', '').strip()
        aid, period = norm(area), str(row.get(pk, '')).strip()
        if not area or not period:
            continue
        names[aid] = area
        group = classify(row, excluded)
        value = num(row.get(mk))
        rate_value = num(row.get(rate)) if rate else None
        if value is not None:
            grouped[aid][period][group]['value'] = value
        if rate_value is not None:
            grouped[aid][period][group]['rate'] = rate_value
    output = {}
    for aid, periods in grouped.items():
        labels = sorted(periods)
        entry = {'name': names[aid], 'labels': labels}
        for group in ['total', 'dagpenge', 'kontanthjaelp']:
            values, rates = [], []
            for period in labels:
                data = periods[period].get(group, {})
                value = data.get('value')
                if group == 'total' and value is None:
                    parts = [periods[period].get(item, {}).get('value') for item in ['dagpenge', 'kontanthjaelp']]
                    value = sum(item for item in parts if item is not None) if any(item is not None for item in parts) else None
                values.append(value)
                rates.append(data.get('rate'))
            entry[group] = values
            if rate:
                entry[group + 'Rate'] = rates
        output[aid] = entry
    return output


def build_measure_series(rows, measures):
    if not rows:
        return {}
    pk, ak = period_key(rows[0]), area_key(rows[0])
    columns = {key: find_col(rows[0], alternatives) for key, alternatives in measures.items()}
    missing = [key for key, column in columns.items() if not column]
    if not pk or not ak or missing:
        raise RuntimeError(f'Mangler kolonner {missing}. Fundet: {list(rows[0])}')
    grouped, names = defaultdict(lambda: defaultdict(dict)), {}
    for row in rows:
        area, period = str(row.get(ak, '')).strip(), str(row.get(pk, '')).strip()
        if not area or not period:
            continue
        aid = norm(area)
        names[aid] = area
        for key, column in columns.items():
            grouped[aid][period][key] = num(row.get(column))
    output = {}
    for aid, period_values in grouped.items():
        labels = sorted(period_values)
        entry = {'name': names[aid], 'labels': labels}
        for key in measures:
            entry[key] = [period_values[period].get(key) for period in labels]
        output[aid] = entry
    return output


def build_categories(rows, dimension_terms, categories, measures, period):
    if not rows:
        return {}
    ak = area_key(rows[0])
    dk = find_col(rows[0], [dimension_terms])
    columns = {key: find_col(rows[0], alternatives) for key, alternatives in measures.items()}
    if not ak or not dk or any(column is None for column in columns.values()):
        raise RuntimeError(f'Mangler kategorikolonner. Fundet: {list(rows[0])}')
    values, names = defaultdict(lambda: defaultdict(dict)), {}
    wanted = {norm(source): key for key, source, _ in categories}
    for row in rows:
        area, category = str(row.get(ak, '')).strip(), str(row.get(dk, '')).strip()
        category_key = wanted.get(norm(category))
        if not area or not category_key:
            continue
        aid = norm(area)
        names[aid] = area
        for key, column in columns.items():
            value = num(row.get(column))
            if value is not None or key not in values[aid][category_key]:
                values[aid][category_key][key] = value
    output = {}
    for aid, area_values in values.items():
        entry = {'name': names[aid], 'period': period, 'labels': [label for _, _, label in categories]}
        for measure in measures:
            entry[measure] = [area_values.get(key, {}).get(measure) for key, _, _ in categories]
        output[aid] = entry
    return output


def build_offers(rows, period):
    categories = [
        ('guidance', 'Vejledning og opkvalificering i alt', 'Vejledning og opkvalificering'),
        ('wageSubsidy', 'Ansættelse med løntilskud i alt', 'Løntilskud'),
        ('internship', 'Virksomhedspraktik i alt', 'Virksomhedspraktik'),
        ('utility', 'Nytteindsats i alt', 'Nytteindsats'),
        ('specialUtility', 'Særligt tilrettelagt nytteindsats i alt', 'Særligt tilrettelagt nytteindsats'),
    ]
    all_categories = [('total', 'Tilbud i alt', 'Tilbud i alt'), *categories]
    series = build_categories(
        rows,
        ['tilbud'],
        all_categories,
        {'courses': [['antal', 'aktiveringsforløb']], 'activated': [['antal', 'aktiverede']]},
        period,
    )
    for entry in series.values():
        total_courses, total_activated = entry['courses'][0], entry['activated'][0]
        entry['coursesTotal'] = total_courses
        entry['activatedTotal'] = total_activated
        entry['averageCourses'] = round(total_courses / total_activated, 2) if total_courses is not None and total_activated else None
        entry['labels'] = entry['labels'][1:]
        entry['courses'] = entry['courses'][1:]
        entry['activated'] = entry['activated'][1:]
    return series


def first_series(series):
    if not series:
        raise RuntimeError('Ingen data i national serie')
    result = next(iter(series.values()))
    result['name'] = 'Hele landet'
    return result


def main():
    now = datetime.now(ZoneInfo('Europe/Copenhagen'))
    sources, municipalities, national = {}, {}, {'name': 'Hele landet'}
    failures, successful = [], []

    def add_source(name, table, series, note='', latest=None):
        if latest is None:
            latest = max(
                (value.get('labels', [''])[-1] if value.get('labels') else value.get('period', '') for value in series.values()),
                default='',
            ) or None
        sources[name] = {
            'state': 'ok',
            'source': 'Jobindsats.dk / STAR',
            'dataset': table,
            'latestPeriod': latest,
            'checkedAt': now.isoformat(timespec='seconds'),
            'note': note,
        }
        successful.append(name)

    def fail(name, table, error):
        sources[name] = {
            'state': 'failed',
            'source': 'Jobindsats.dk / STAR',
            'dataset': table,
            'note': str(error)[:500],
        }
        failures.append(name)

    def attach(key, series):
        for aid, entry in series.items():
            if aid == norm('Hele landet'):
                national[key] = entry
            elif aid != norm('Uoplyst område'):
                municipalities.setdefault(aid, {'name': entry['name']})[key] = entry

    table = KNOWN['unemployment']
    try:
        series = build_time(fetch_first(table, 60, True, False), 'count')
        for aid, entry in series.items():
            municipalities.setdefault(aid, {'name': entry['name']})['unemployment'] = entry
        add_source('unemployment', table, series, 'Faktisk registerbaseret ledighed. Ikke sæsonkorrigeret på kommuneniveau.')
    except Exception as error:
        fail('unemployment', table, error)
    try:
        series = build_time(fetch_first(table, 60, True, True), 'count')
        national['unemployment'] = first_series(series)
        add_source('unemploymentNational', table, {'hele landet': national['unemployment']}, 'Officielt landstal fra samme Jobindsats-måling.')
    except Exception as error:
        fail('unemploymentNational', table, error)

    table = KNOWN['longterm']
    try:
        series = build_time(fetch_first(table, 36, True, False), 'long')
        for aid, entry in series.items():
            municipalities.setdefault(aid, {'name': entry['name']})['longterm'] = entry
        add_source('longterm', table, series)
    except Exception as error:
        fail('longterm', table, error)
    try:
        series = build_time(fetch_first(table, 36, True, True), 'long')
        national['longterm'] = first_series(series)
        add_source('longtermNational', table, {'hele landet': national['longterm']})
    except Exception as error:
        fail('longtermNational', table, error)

    cash_meta = None
    table = KNOWN['cashAssistance']
    try:
        cash_meta = metadata(table)
        areas, periods = metadata_areas(cash_meta), metadata_periods(cash_meta, 'M', 60)
        rows = []
        for start in range(0, len(areas), 50):
            rows.extend(frontend_records(
                table,
                periods,
                areas[start:start + 50],
                ['mgrpa02_1', 'mgrpa02_3', 'mgrpa02_4b', 'mgrpa02_5b'],
            ))
        series = build_measure_series(
            rows,
            {
                'persons': [['antal', 'personer']],
                'fullTime': [['antal', 'fuldtidspersoner']],
                'workforceRate': [['fuldtidspersoner', 'pct', 'arbejdsstyrken']],
                'populationRate': [['fuldtidspersoner', 'pct', 'befolkningen']],
            },
        )
        attach('cashAssistance', series)
        add_source('cashAssistance', table, series, 'Kontanthjælp opgjort som personer, fuldtidspersoner og andele.')
    except Exception as error:
        fail('cashAssistance', table, error)

    try:
        if cash_meta is None:
            cash_meta = metadata(table)
        areas, period = metadata_areas(cash_meta), metadata_periods(cash_meta, 'M', 1)[0]
        visitations = [
            ('jobReady', 'Jobparat', 'Jobparat'),
            ('activityReady', 'Aktivitetsparat', 'Aktivitetsparat'),
            ('educationReady', 'Uddannelsesparat', 'Uddannelsesparat'),
            ('obviousEducationReady', 'Åbenlys uddannelsesparat', 'Åbenlys uddannelsesparat'),
            ('unknown', 'Uoplyst visitationskategori', 'Uoplyst'),
        ]
        rows = frontend_records(
            table,
            [period],
            areas,
            ['mgrpa02_3'],
            {'_viskat_1int': [source for _, source, _ in visitations]},
        )
        series = build_categories(rows, ['visitationskategori'], visitations, {'fullTime': [['antal', 'fuldtidspersoner']]}, period)
        attach('cashVisitation', series)
        add_source('cashVisitation', table, series, 'Seneste fordeling af fuldtidspersoner efter visitationskategori.', latest=period)
    except Exception as error:
        fail('cashVisitation', table, error)

    table = KNOWN['activation']
    try:
        meta = metadata(table)
        areas, periods = metadata_areas(meta), metadata_periods(meta, 'M', 60)
        rows = frontend_records(table, periods, areas, ['mgrpc07_1', 'mgrpc07_2'])
        series = build_measure_series(rows, {'degree': [['aktiveringsgrad']], 'affectedShare': [['andel', 'aktiveringsberørte']]})
        attach('activation', series)
        add_source('activation', table, series, 'Aktiveringsgrad og andel aktiveringsberørte for visitationskategori i alt, både jobparate og ikke-jobparate.')
    except Exception as error:
        fail('activation', table, error)

    table = KNOWN['offers']
    try:
        meta = metadata(table)
        areas, period = metadata_areas(meta), metadata_periods(meta, 'M', 1)[0]
        offer_members = [
            'Tilbud i alt',
            'Vejledning og opkvalificering i alt',
            'Ansættelse med løntilskud i alt',
            'Virksomhedspraktik i alt',
            'Nytteindsats i alt',
            'Særligt tilrettelagt nytteindsats i alt',
        ]
        rows = frontend_records(
            table,
            [period],
            areas,
            ['mgrpc02_1', 'mgrpc02_2'],
            {'_tilb_2ptv': offer_members},
        )
        series = build_offers(rows, period)
        attach('offers', series)
        add_source('offers', table, series, 'Aktiveringsforløb for visitationskategori i alt, både jobparate og ikke-jobparate, fordelt på overordnede tilbudstyper.', latest=period)
    except Exception as error:
        fail('offers', table, error)

    table = KNOWN['ordinaryHours']
    try:
        meta = metadata(table)
        areas, periods = metadata_areas(meta), metadata_periods(meta, 'M', 60)
        rows = frontend_records(table, periods, areas, ['mgrpj01_1', 'mgrpj01_2'])
        series = build_measure_series(
            rows,
            {
                'persons': [['antal', 'personer', 'ordinære', 'timer']],
                'share': [['andel', 'personer', 'ordinære', 'timer']],
            },
        )
        attach('ordinaryHours', series)
        add_source('ordinaryHours', table, series, 'Kontanthjælpsmodtagere med ordinære løntimer i måneden.')
    except Exception as error:
        fail('ordinaryHours', table, error)

    municipalities.pop(norm('Hele landet'), None)
    municipalities.pop(norm('Uoplyst område'), None)
    municipalities = {aid: value for aid, value in municipalities.items() if value.get('unemployment', {}).get('labels')}
    state = 'ok' if not failures else ('partial' if successful else 'failed')
    if not municipalities:
        raise RuntimeError('Ingen kommunedata kunne hentes')
    month_names = ['januar', 'februar', 'marts', 'april', 'maj', 'juni', 'juli', 'august', 'september', 'oktober', 'november', 'december']
    data = {
        'meta': {
            'title': 'Kommunal beskæftigelsesindsats',
            'updated': f'{now.day}. {month_names[now.month - 1]} {now.year}',
            'retrievedAt': now.isoformat(timespec='seconds'),
            'source': 'Jobindsats.dk / STAR',
            'sourceStatus': sources,
            'updateStatus': {'state': state, 'successful': successful, 'failed': failures, 'checkedAt': now.isoformat(timespec='seconds')},
        },
        'municipalities': municipalities,
        'national': national,
    }
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(
        f'status: {state}\ntid_utc: {datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}\ndato_dk: {now.date()}\n',
        encoding='utf-8',
    )
    print(f'Opdateret: {state}. Kommuner: {len(municipalities)}. Nationale sektioner: {len(national) - 1}')


if __name__ == '__main__':
    main()
