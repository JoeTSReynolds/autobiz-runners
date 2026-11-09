import datetime as dt, json, math, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trending.soundmomentum import parse_views, momentum, pivot_token, group_sounds, score, spread, PIVOT
H = os.path.dirname(os.path.abspath(__file__))

assert parse_views('7.3 million views') == 7_300_000
assert parse_views('812K views') == 812_000
assert parse_views('1,234 views') == 1234
assert parse_views('No views') == 0
assert parse_views('313K Shorts') == 313_000
assert parse_views('1 view') == 1 and parse_views('garbage') is None and parse_views(None) is None

assert abs(momentum(60, 0.5, 99_999) - 0.5 * 5) < 1e-9
assert abs(momentum(30, 1.0, 9) - 0.5 * 1) < 1e-9      # depth_factor 0.5
assert momentum(120, 0.5, 9) == 0.5                      # depth_factor capped at 1
assert momentum(60, 0, 1e6) == 0

d = json.load(open(os.path.join(H, 'fixture_reel.json')))
assert len(d['contents']) >= 1
t = pivot_token(d); assert t and PIVOT in t
assert pivot_token({'continuationEndpoint': {'continuationCommand': {'token': 'abc'}}}) is None

g = group_sounds([
    dict(vid='a', views=10, title='Song', source='S1'), dict(vid='b', views=5, title='Song (alt)', source='S1'),
    dict(vid='c', views=100, title='Other', source='S2'), dict(vid='d', views=1, title='Original Sound', source=None),
    dict(vid='e', views=7, title='No Source!', source=None), dict(vid='f', views=7, title='no  source', source=None)])
assert [x['key'] for x in g] == ['S1', 't:no source', 'S2'] and g[0]['seed_count'] == 2 and g[0]['seed_views'] == 15

today = dt.date(2026, 11, 5)
sh = [dict(vid=str(i), views=1000 * (i + 1)) for i in range(4)]
dates = {'0': '2026-11-04', '1': '2026-10-20', '2': '2026-01-01', '3': None}
r = score(sh, dates, True, today)
assert r['dated'] == 3 and r['recent_share_7d'] == 0.333 and r['recent_share_30d'] == 0.667 and r['recent_views'] == 1500
assert r['depth'] == 4 and r['more_pages']
assert spread(list(range(100)), 4) == [0, 25, 50, 75]
import datetime as _dt
from trending import soundmomentum as sm
assert sm.growth({'2026-11-05': 1000}, _dt.date(2026, 11, 5)) is None
assert sm.growth({'2026-11-03': 1000, '2026-11-05': 1300}, _dt.date(2026, 11, 5)) == (150.0, 15.0, 2)
assert sm.growth({'2026-11-01': 10, '2026-11-04': 1000, '2026-11-05': 1100}, _dt.date(2026, 11, 5)) == (100.0, 10.0, 1)
assert sm.rank_key({'growth_per_day': 5, 'seed_count': 1}) < sm.rank_key({'seed_count': 99})

# history and caches live in the directory the caller passes, nothing else is written
with tempfile.TemporaryDirectory() as sd:
    assert sm.load_history(sd) == {}
    g1 = [dict(source='S1', title='Song', total_uses=1000, seed_shorts=['v'], examples=['v'])]
    sm.record(g1, dt.date(2026, 11, 4), sm.load_history(sd), sd)
    g2 = [dict(source='S1', title='Song', total_uses=1300, seed_shorts=['v'], examples=['v'])]
    sm.record(g2, dt.date(2026, 11, 5), sm.load_history(sd), sd)
    assert g2[0]['growth_per_day'] == 300.0, g2
    assert sm.load_history(sd)['S1']['uses'] == {'2026-11-04': 1000, '2026-11-05': 1300}
    assert sm._cached(sd, 'k', lambda: {'a': 1}) == {'a': 1} and sm._cached(sd, 'k', lambda: 1 / 0) == {'a': 1}
    assert sorted(os.listdir(sd)) == ['uses-history.json', 'youtubei']
print('ok')
