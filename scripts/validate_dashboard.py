#!/usr/bin/env python3
import json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
data=json.loads((BASE/'data/dashboard-data.json').read_text(encoding='utf-8'))
html=(BASE/'index.html').read_text(encoding='utf-8')
for needle in ['Kommunal beskæftigelsesindsats','municipalitySelect','Hele landet','unemploymentChart','newlyChart','durationChart','exitChart']:
    assert needle in html, f'Mangler {needle} i index.html'
for forbidden in ['Danmarkskort','rankingList','leaflet','id="map"']:
    assert forbidden.lower() not in html.lower(), f'Uønsket kort/rangering findes stadig: {forbidden}'
state=data.get('meta',{}).get('updateStatus',{}).get('state')
assert state in {'ok','partial','failed','pending'}
sources=data.get('meta',{}).get('sourceStatus',{})
if sources.get('unemployment',{}).get('state')=='ok':
    valid=[v for v in data.get('municipalities',{}).values() if v.get('unemployment',{}).get('labels')]
    assert len(valid)>=90, f'Kun {len(valid)} kommuner med ledighedsdata'
    latest=max(v['unemployment']['labels'][-1] for v in valid)
    assert latest==sources['unemployment']['latestPeriod']
    assert any(v['unemployment'].get('total',[])[-1] is not None for v in valid)
if sources.get('unemploymentNational',{}).get('state')=='ok':
    nat=data.get('national',{}).get('unemployment',{})
    assert nat.get('labels'), 'National ledighed mangler'
    assert nat['labels'][-1]==sources['unemploymentNational']['latestPeriod']
    assert any(v is not None for v in nat.get('totalRate',[])), 'National ledighedsprocent mangler'
print('Dashboard-validering ok')
