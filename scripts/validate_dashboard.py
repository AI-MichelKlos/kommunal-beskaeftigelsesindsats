#!/usr/bin/env python3
import json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
data=json.loads((BASE/'data/dashboard-data.json').read_text(encoding='utf-8'))
html=(BASE/'index.html').read_text(encoding='utf-8')
for needle in ['Kommunal beskæftigelsesindsats','municipalitySelect','rankingList','unemploymentChart','newlyChart','durationChart','exitChart']:
    assert needle in html, f'Mangler {needle} i index.html'
state=data.get('meta',{}).get('updateStatus',{}).get('state')
assert state in {'ok','partial','failed','pending'}
if data.get('meta',{}).get('sourceStatus',{}).get('unemployment',{}).get('state')=='ok':
    valid=[v for v in data.get('municipalities',{}).values() if v.get('unemployment',{}).get('labels')]
    assert len(valid)>=90, f'Kun {len(valid)} kommuner med ledighedsdata'
    latest=max(v['unemployment']['labels'][-1] for v in valid)
    assert latest==data['meta']['sourceStatus']['unemployment']['latestPeriod']
    assert any(v['unemployment'].get('total',[])[-1] is not None for v in valid)
print('Dashboard-validering ok')
