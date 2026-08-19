#!/usr/bin/env python3
import json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
data=json.loads((BASE/'data/dashboard-data.json').read_text(encoding='utf-8'))
html=(BASE/'index.html').read_text(encoding='utf-8')
for needle in ['Kommunal beskæftigelsesindsats','municipalitySelect','compareNational','Hele landet','unemploymentChart','compositionChart','longtermChart','unemploymentIndexChart','longtermIndexChart','longtermShareChart','benefitShareChart','indexComparison']:
    assert needle in html, f'Mangler {needle} i index.html'
for forbidden in ['Danmarkskort','rankingList','leaflet','id="map"','newlyChart','durationChart','exitChart','Nytilmeldte ledige','Andel i beskæftigelse efter nyledighed']:
    assert forbidden.lower() not in html.lower(), f'Uønsket kort/rangering findes stadig: {forbidden}'
state=data.get('meta',{}).get('updateStatus',{}).get('state')
assert state=='ok', f'Aktive kilder er ikke fuldt opdateret: {state}'
assert not data.get('meta',{}).get('updateStatus',{}).get('failed',[]), 'Fejllisten skal være tom ved ok-status'
sources=data.get('meta',{}).get('sourceStatus',{})
required={'unemployment','unemploymentNational','longterm','longtermNational'}
assert set(sources)==required, f'Kilderegisteret skal kun indeholde aktive kilder: {set(sources)}'
for key in required:
    assert sources[key].get('state')=='ok', f'Kilden {key} er ikke ok'
    assert sources[key].get('latestPeriod'), f'Kilden {key} mangler seneste periode'
if sources.get('unemployment',{}).get('state')=='ok':
    valid=[v for v in data.get('municipalities',{}).values() if v.get('unemployment',{}).get('labels')]
    assert len(valid)==98, f'Forventede 98 kommuner med ledighedsdata, fandt {len(valid)}'
    assert all(v.get('name') not in {'Hele landet','Uoplyst område'} for v in valid), 'Landstal og uoplyst område må ikke ligge blandt kommunerne'
    latest=max(v['unemployment']['labels'][-1] for v in valid)
    assert latest==sources['unemployment']['latestPeriod']
    assert any(v['unemployment'].get('total',[])[-1] is not None for v in valid)
if sources.get('unemploymentNational',{}).get('state')=='ok':
    nat=data.get('national',{}).get('unemployment',{})
    assert nat.get('labels'), 'National ledighed mangler'
    assert nat['labels'][-1]==sources['unemploymentNational']['latestPeriod']
    assert any(v is not None for v in nat.get('totalRate',[])), 'National ledighedsprocent mangler'
valid_long=[v for v in data.get('municipalities',{}).values() if v.get('longterm',{}).get('labels')]
assert len(valid_long)>=90, f'Kun {len(valid_long)} kommuner med langtidsledighed'
nat_long=data.get('national',{}).get('longterm',{})
assert nat_long.get('labels'), 'National langtidsledighed mangler'
assert nat_long['labels'][-1]==sources['longtermNational']['latestPeriod']
for area in data.get('municipalities',{}).values():
    for retired in ('newlyRegistered','duration','employmentExit'):
        assert retired not in area, f'Udgået modul ligger stadig i kommunedata: {retired}'
for retired in ('newlyRegistered','duration','employmentExit'):
    assert retired not in data.get('national',{}), f'Udgået modul ligger stadig i landstal: {retired}'
print('Dashboard-validering ok')
