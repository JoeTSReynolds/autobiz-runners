# Offline tests for the trending front stages: refresh, people, route, mediaplan. Run: python test_stages_front.py
import os, datetime as dt, json, sys, tempfile, urllib.error
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trending import net, outlets, people, soundmomentum, stages, transcripts, ytsrc
from trending import sourcerules as formats

here = Path(__file__).parent
FX = here / 'fixtures'
load = lambda n: json.loads((FX / n).read_text())
stages.today = lambda: dt.date(2026, 11, 5)
slept = []; stages.sleep = slept.append

# ---- pure helpers
assert people.spike([100] * 29 + [450]) == 4.5 and people.spike([5, 5]) is None
assert people.died_recently('2026-10-28', dt.date(2026, 11, 5)) and not people.died_recently('2026-10-01', dt.date(2026, 11, 5))
assert not people.died_recently('2026-00-00', dt.date(2026, 11, 5)) and not people.died_recently(None, dt.date(2026, 11, 5))
assert outlets.allowed('news.sky.com') and outlets.allowed('www.bbc.co.uk') and not outlets.allowed('dailymail.co.uk') and not outlets.allowed('notbbc.co.uk')
# bbc.com is the BBC's international site and CNBC broke much of the Jensen Huang story (live 2026-11-10: both dropped, case file died)
assert outlets.allowed('www.bbc.com') and outlets.allowed('cnbc.com') and outlets.root('www.bbc.com') == 'bbc.com'
assert outlets.distinct(['www.bbc.co.uk', 'bbc.co.uk', 'x.com', 'news.sky.com']) == {'bbc.co.uk', 'sky.com'}
assert formats.surname('Sir José Müller Jr.') == 'muller' and formats.surname('Madonna') == 'madonna'
assert ytsrc.pick_track(load('info.json')) == 'en'  # the fr->en translated track is never chosen
ws = [{'w': '>> Alas,', 's': 0, 'e': 1}, {'w': '>>', 's': 1, 'e': 1.2}, {'w': '[applause]', 's': 1.2, 'e': 2}, {'w': 'ok', 's': 2, 'e': 3}]
assert [w['w'] for w in transcripts.clean(ws)] == ['Alas,', 'ok']

# ---- transcript windowing: peak and keyword mentions survive, caps hold
sents = [{'start': i * 4.0, 'end': i * 4.0 + 3, 'text': f'sentence number {i} ' + 'filler ' * 20} for i in range(2000)]
sents[1500]['text'] = 'the zebra is mentioned here'
info = {'heatmap': [{'start_time': 300, 'end_time': 310, 'value': 1.0}, {'start_time': 0, 'end_time': 10, 'value': 0.1}]}
body = transcripts.window(sents, info, ['zebra'], 3000)
assert len(body) <= 3000 and 'zebra' in body and '[300.0-303.0]' in body and 'sentence number 1990' not in body, len(body)
meta = dict(id='a', title='T', channel='C', duration=100, uploaded='20260101')
blk = transcripts.block(meta, sents, info, ['zebra'], cap=18000)
assert len(blk) <= 18000 and blk.startswith('### a | T | C | 100 s | 20260101')
many = transcripts.build([(dict(meta, id=f'v{i}'), sents, info) for i in range(6)], ['zebra'])
assert len(many) <= 60000 and many.count('### ') >= 3, len(many)

# ---- people
def per_article(url):
    if 'Alice_Smith' in url: return load('per_article_alice.json')
    base, last = (50000, 60000) if 'Bob_Dead' in url else (10000, 11000)
    return {'items': [{'views': base if i < 29 else last} for i in range(30)]}
calls = []
def fake_json(url, timeout=30):
    calls.append(url)
    if 'pageviews/top' in url:
        if url.endswith('/2026/11/04'): raise urllib.error.HTTPError(url, 404, 'nf', {}, None)
        return load('pageviews_top.json')
    if 'wikidata.org' in url: return load('wbgetentities.json')
    if 'per-article' in url: return per_article(url)
    raise AssertionError(url)
net.get_json = fake_json
net.get_text = lambda url, timeout=30: (FX / 'gnews.xml').read_text()

with tempfile.TemporaryDirectory() as d:
    d = Path(d); state = d / 'state'; state.mkdir()
    (state / 'trending-covered.json').write_text(json.dumps([{'qid': 'Q4', 'date': '2026-11-04'}, {'qid': 'Q6', 'date': '2026-08-01'},
                                                             {'qid': 'Q1', 'format': 'edit', 'date': '2026-10-26', 'title': 'Old edit', 'angle': 'a story'}]))
    port, out, log = stages.people({'rejectedPeople': ['Q5']}, {}, d, state)
    cands = out['candidates']
    assert port == 'next' and [c['qid'] for c in cands] == ['Q1', 'Q2'], (port, cands)  # human only; Carl is a village; Dan covered; Eve rejected; Fred has no spike
    a, b = cands
    assert a['spike'] == 9.0 and a['age'] == 46 and a['image'] == 'Alice_Smith.jpg' and a['views'] == 9000 and a['born'] == '1980-03-02', a
    assert b['died'] == '2026-10-28' and b['spike'] < 3  # kept for the recent death alone
    # a published Short does not hide the person: the route agent sees it and the formats still open (no second edit this month)
    assert a['covered'] == [{'format': 'edit', 'date': '2026-10-26', 'title': 'Old edit', 'angle': 'a story'}] and 'edit' not in a['formats'], a
    assert 'topn' in a['formats'] and b['formats'] == ['tribute'] and b['covered'] == [], b
    assert [h['domain'] for h in a['headlines']] == ['bbc.co.uk', 'theguardian.com', 'dailymail.co.uk'] and a['headlines'][0]['outlet'] == 'BBC News'
    assert not any(t in u for u in calls for t in ('Carl_Thing', 'Dan_Covered', 'Eve_Rejected', 'Main_Page', 'Special:')), 'skipped titles must cost nothing'
    # a retry in the same run reuses the trending list: no Wikimedia calls again (live 2026-11-10: 103 s, 35 s, 23 s re-fetching)
    calls.clear()
    port, out, log = stages.people({'rejectedPeople': ['Q5', 'Q1']}, {}, d, state)
    assert port == 'next' and [c['qid'] for c in out['candidates']] == ['Q2'] and not any('wikimedia' in u or 'wikidata' in u for u in calls), calls
    port, out, log = stages.people({'rejectedPeople': ['Q1', 'Q2', 'Q5', 'Q6']}, {}, d, state)
    assert port == 'missing' and out['candidates'] == [] and len(out['agentErrors']) == 1, out
    # the next run the same day skips people rejected today (the cloud would retry them 3x a day); yesterday's are back
    run2 = d / 'run2'; run2.mkdir()
    port, out, log = stages.people({}, {}, run2, state)
    assert port == 'missing', out
    rej = json.loads((state / 'trending-rejected.json').read_text())
    (state / 'trending-rejected.json').write_text(json.dumps({q: (stages.today() - dt.timedelta(days=1)).isoformat() for q in rej}))
    run3 = d / 'run3'; run3.mkdir()
    port, out, log = stages.people({}, {}, run3, state)
    assert port == 'next' and [c['qid'] for c in out['candidates']] == ['Q1', 'Q2'], out

# ---- a chosen person (run input want: {person: name or Qid, format}): one candidate, no spike or covered filter
calls.clear()
def want_json(url, timeout=30):
    calls.append(url)
    if 'wbsearchentities' in url: return {'search': [{'id': 'Q3'}, {'id': 'Q6'}]}   # Carl is a village: the first human wins
    if 'wikidata.org' in url:   # like the real API: only the requested id
        q = url.rsplit('ids=', 1)[1]; e = load('wbgetentities.json')
        return {'entities': {k: v for k, v in e['entities'].items() if k == q}}
    raise AssertionError(url)
net.get_json = want_json
with tempfile.TemporaryDirectory() as d:
    d = Path(d); state = d / 'state'; state.mkdir()
    (state / 'trending-covered.json').write_text(json.dumps([{'qid': 'Q6', 'date': '2026-11-04'}]))
    port, out, log = stages.people({'want': {'person': 'Flat Fred', 'format': 'topn'}}, {}, d, state)
    assert port == 'next' and [c['qid'] for c in out['candidates']] == ['Q6'] and out['candidates'][0]['headlines'], out   # covered, no spike: still the one
    assert not any('pageviews' in u for u in calls), calls
    port, out, log = stages.people({'want': {'person': 'Q1'}}, {}, d, state)
    assert port == 'next' and out['candidates'][0]['qid'] == 'Q1' and not any('wbsearchentities' in u for u in calls[-3:]), calls   # an id needs no search
    port, out, log = stages.people({'want': {'person': 'Flat Fred'}, 'rejectedPeople': ['Q6']}, {}, d, state)
    assert port == 'missing' and 'Flat Fred' in out['agentErrors'][0], out                                       # rejected: the run ends
net.get_json = fake_json

# ---- route
ALICE = dict(a, headlines=a['headlines'])
def route(pick, cands=(ALICE, b), rej=()):
    return stages.route({'pick': pick, 'candidates': list(cands), 'rejectedPeople': list(rej)}, {}, Path('.'), Path('.'))
port, out, _ = route({'qid': 'Q1', 'format': 'topn', 'queries': ['q']})
assert port == 'next' and out['format'] == 'topn' and out['person']['qid'] == 'Q1' and out['agentErrors'] == []
assert out['formatContext'] == {'brief': (here / 'briefs/topn.md').read_text(), 'schema': (here / 'briefs/topn.schema.json').read_text()}
# a chosen format (run input want.format) wins over the agent's, but not over the rules
w = lambda pick, fmt: stages.route({'pick': pick, 'candidates': [ALICE, b], 'want': {'format': fmt}}, {}, Path('.'), Path('.'))
assert w({'qid': 'Q1', 'format': 'edit', 'queries': ['q']}, 'topn')[1]['format'] == 'topn'
assert w({'qid': 'Q1', 'format': 'edit', 'queries': ['q']}, 'tribute')[0] == 'invalid'          # no recent death
assert w({'qid': 'Q2', 'format': 'tribute', 'queries': ['q']}, 'topn')[1]['format'] == 'tribute'  # died: tribute
port, out, _ = route({'qid': 'Q2', 'format': 'topn', 'queries': ['q']})
assert port == 'next' and out['format'] == 'tribute', out  # recent death overrides the agent
port, out, _ = route({'qid': 'Q1', 'format': 'tribute', 'queries': ['q']})
assert port == 'invalid' and 'recent death' in out['agentErrors'][0]
port, out, _ = route({'qid': 'Q99', 'format': 'topn', 'queries': ['q']})
assert port == 'invalid' and 'Q99' in out['agentErrors'][0]
port, out, _ = route({'qid': 'Q1', 'format': 'topn'}, rej=['Q1'])
assert port == 'invalid'
port, out, _ = route({'qid': 'Q1', 'format': 'casefile', 'queries': ['q']}, cands=(dict(ALICE, headlines=ALICE['headlines'][:1] + ALICE['headlines'][2:]), b))
assert port == 'invalid' and 'allowlisted' in out['agentErrors'][0], out  # BBC only; the Mail is not on the list
port, out, _ = route({'qid': 'Q1', 'format': 'casefile', 'queries': ['q']})
assert port == 'next' and out['format'] == 'casefile'
port, out, _ = route({'qid': 'Q1', 'format': 'casefile', 'queries': ['q'], 'articles': [{'url': 'https://www.ft.com/x', 'outlet': 'FT'}]}, cands=(dict(ALICE, headlines=ALICE['headlines'][:1]), b))
assert port == 'next', out  # BBC headline + FT article = 2 allowlisted outlets
port, out, _ = route({'qid': 'Q1', 'format': 'nonsense'})
assert port == 'invalid'
# a format that would repeat a published Short is refused at route too (the agent may ignore `formats`); a chosen person is not
with tempfile.TemporaryDirectory() as d:
    (Path(d) / 'trending-covered.json').write_text(json.dumps([{'qid': 'Q1', 'format': 'edit', 'date': (stages.today() - dt.timedelta(days=7)).isoformat()}]))
    port, out, _ = stages.route({'pick': {'qid': 'Q1', 'format': 'edit', 'queries': ['q']}, 'candidates': [ALICE, b]}, {}, Path('.'), Path(d))
    assert port == 'invalid' and 'repeat' in out['agentErrors'][0], out
    assert stages.route({'pick': {'qid': 'Q1', 'format': 'topn', 'queries': ['q']}, 'candidates': [ALICE, b]}, {}, Path('.'), Path(d))[0] == 'next'
    # a new person starts with fresh storyboard tries (verify drops a person after 3)
    assert stages.route({'pick': {'qid': 'Q1', 'format': 'topn', 'queries': ['q']}, 'candidates': [ALICE, b], 'storyTries': 2}, {}, Path('.'), Path(d))[1]['storyTries'] == 0
    assert stages.route({'pick': {'qid': 'Q1', 'format': 'edit', 'queries': ['q']}, 'candidates': [ALICE, b], 'want': {'person': 'Q1'}}, {}, Path('.'), Path(d))[0] == 'next'

# ---- mediaplan
SEARCH = load('ytsearch.json')
fetched, flaky = [], {'vid8': 1}
ytsrc.search = lambda q, n=15: [dict(e) for e in SEARCH]
def fake_info(vid, out_dir):
    fetched.append(vid)
    if flaky.get(vid): flaky[vid] -= 1; raise RuntimeError(f'info unavailable for {vid}: rate-limited (429)')
    return load('info.json'), ytsrc.parse_json3(FX / 'captions.json3')
ytsrc.info_and_words = fake_info
HTML = '<html><head><title>T</title></head><body><article><p>' + 'Alice Smith was reported to have done a thing. ' * 5 + '</p></article></body></html>'
net.get_text = lambda url, timeout=30: HTML
pick = {'qid': 'Q1', 'queries': ['alice smith interview', 'alice smith moments'], 'angle': 'Zebra tour'}
def plan(fmt, pick=pick, job=None, archive='youtube vid6\n', rejected_sources=('vid7',)):
    d = Path(tempfile.mkdtemp()); state = d / 'state'; state.mkdir(); (state / 'archive.txt').write_text(archive)
    fetched.clear(); slept.clear(); flaky['vid8'] = 1
    j = dict(person=dict(ALICE), format=fmt, pick=pick, rejectedSources=list(rejected_sources), rejectedPeople=['Q9'], **(job or {}))
    return d, stages.mediaplan(j, {}, d, state)

d, (port, out, log) = plan('topn')
assert port == 'missing', (port, log)  # vid1, vid2, vid8 survive the filters; topn needs 4
assert out['rejectedPeople'] == ['Q9', 'Q1'] and len(out['agentErrors']) == 1 and 'Alice Smith rejected at mediaplan' in out['agentErrors'][0] and 'needs 4' in out['agentErrors'][0], out
d, (port, out, log) = plan('tribute')
assert port == 'next' and [p['id'] for p in out['pool']] == ['vid1', 'vid2', 'vid8'], out['pool']  # no live, no 20 s clip, no wrong name, archived or rejected sources; ranked by views
assert out['agentErrors'] == [] and out['pool'][0]['words'] == 'captions/vid1.words.json' and slept == [30], slept  # one 429 waited out, then retried
assert fetched.count('vid8') == 2 and 'vid3' not in fetched and 'vid6' not in fetched and 'vid7' not in fetched and 'vid4' not in fetched
words = json.loads((d / 'captions/vid1.words.json').read_text())
assert [w['w'] for w in words] == ['Hello', 'there', 'Alice', 'Smith', 'here.'], words  # speaker marker and [applause] cleaned
txt = (d / 'transcripts.txt').read_text()
assert out['transcripts'] == {'file': 'transcripts.txt'} and '### vid1 | Alice Smith full interview | Chat Show | 1800 s | 20260101' in txt and '[0.0-1.0] Hello there' in txt
assert out['articles'] == [] and out['articlesText'] == {'file': 'articles.txt'} and (d / 'articles.txt').read_text() == ''
# YouTube blocking the runner: stop after 3 sources in a row give no info, say yt-dlp's reason, and do not reject the person
# (live 2026-11-12: 3 people rejected for "0 usable sources" over 14 min, the reason thrown away, each banned for the day)
ytsrc.info_and_words = lambda vid, out_dir: fetched.append(vid) or (_ for _ in ()).throw(
    RuntimeError(f"info unavailable for {vid}: bot check\nERROR: [youtube] {vid}: Sign in to confirm you're not a bot"))
d, (port, out, log) = plan('tribute')
assert port == 'missing' and len(fetched) == 3 and slept == [], (fetched, slept)
assert 'rejectedPeople' not in out and 'YouTube' in out['agentErrors'][0] and "Sign in to confirm you're not a bot" in out['agentErrors'][0], out
ytsrc.info_and_words = fake_info
d, (port, out, log) = plan('edit')
assert port == 'next' and len(out['pool']) == 3 and len(set(fetched)) == 3  # edit: K = 3, minimum 1
d, (port, out, log) = plan('tribute', archive='youtube vid1\nyoutube vid2\n')
assert port == 'missing' and out['rejectedPeople'][-1] == 'Q1'  # archive.txt sources are skipped, 1 left < 3
ytsrc.search = lambda q, n=15: [dict(e, duration=0) for e in SEARCH]
d, (port, out, log) = plan('tribute')
assert port == 'missing'  # no duration, nothing passes the range
# each query gets a turn: the pool takes the best-viewed of every query before the second of any, so viral chat-show clips
# under one query cannot crowd out the speeches another query asked for (live 2026-11-10: Patrick Stewart tribute)
VIRAL = [dict(SEARCH[0], id=f'big{i}', title=f'Alice Smith viral {i}', view_count=10**9 - i) for i in range(6)]
ytsrc.search = lambda q, n=15: [dict(e) for e in (VIRAL if 'interview' in q else [dict(SEARCH[0], id='speech', title='Alice Smith acceptance speech', view_count=5)])]
d, (port, out, log) = plan('tribute', rejected_sources=())
assert port == 'next' and 'speech' in [p['id'] for p in out['pool']] and [p['id'] for p in out['pool']][:2] == ['big0', 'speech'], out['pool']
ytsrc.search = lambda q, n=15: [dict(e) for e in SEARCH]
cpick = dict(pick, articles=[{'url': 'https://www.bbc.co.uk/n/1', 'outlet': 'BBC'}, {'url': 'https://www.theguardian.com/n/2', 'outlet': 'Guardian'}, {'url': 'https://dailymail.co.uk/n/3', 'outlet': 'Mail'}])
d, (port, out, log) = plan('casefile', cpick)
assert port == 'next' and [x['domain'] for x in out['articles']] == ['bbc.co.uk', 'theguardian.com'] and len(fetched) == 2, out['articles']
assert out['articles'][0]['outlet'] == 'BBC' and out['articles'][0]['text'].startswith('Alice Smith was reported')
assert '### BBC | https://www.bbc.co.uk/n/1' in (d / 'articles.txt').read_text()
# a site that refuses the direct fetch (cloud IPs) is read through Jina when a key is set; without a key it is skipped
def blocked(url, timeout=30):
    if 'theguardian' in url: raise urllib.error.HTTPError(url, 403, 'forbidden', {}, None)
    return HTML
net.get_text, jina_calls = blocked, []
net.jina = lambda url, fmt, timeout=90: jina_calls.append((url, fmt)) or HTML
os.environ.pop('JINA_API_KEY', None)
d, (port, out, log) = plan('casefile', cpick)
assert port == 'missing' and jina_calls == [], (port, jina_calls)
os.environ['JINA_API_KEY'] = 'k'
d, (port, out, log) = plan('casefile', cpick)
assert port == 'next' and [x['domain'] for x in out['articles']] == ['bbc.co.uk', 'theguardian.com'] and jina_calls == [('https://www.theguardian.com/n/2', 'html')], (port, jina_calls)
del os.environ['JINA_API_KEY']; net.get_text = lambda url, timeout=30: HTML
d, (port, out, log) = plan('casefile', dict(cpick, articles=cpick['articles'][:1] + cpick['articles'][2:]))
assert port == 'missing' and out['rejectedPeople'][-1] == 'Q1' and 'allowlisted' in out['agentErrors'][0], out
assert (d / 'articles.txt').exists()
# an active court case (charged, no verdict) is refused before any storyboard (UK contempt of court)
net.get_text = lambda url, timeout=30: HTML.replace('was reported to have done a thing.', 'has been charged with fraud and is due to appear in court.')
d, (port, out, log) = plan('casefile', cpick)
assert port == 'missing' and 'contempt' in out['agentErrors'][0] and out['rejectedPeople'][-1] == 'Q1', out
net.get_text = lambda url, timeout=30: HTML

# ---- refresh never raises
def boom(sdir): raise OSError('network down')
real = soundmomentum.load_history; soundmomentum.load_history = boom
with tempfile.TemporaryDirectory() as t:
    port, out, log = stages.refresh({}, {}, Path(t), Path(t) / 'state')
assert port == 'next' and 'network down' in str(out['soundsRefresh']['stoppedBy']), out
soundmomentum.load_history = real
with tempfile.TemporaryDirectory() as t:  # nothing due: today's snapshot and a fresh discovery exist, so no network call
    sd = Path(t) / 'state' / 'sounds'; sd.mkdir(parents=True)
    (sd / 'uses-history.json').write_text(json.dumps({'s': {'title': 't', 'example': 'x', 'uses': {'2026-11-05': 5}}}))
    (sd / 'discovery.json').write_text(json.dumps({'date': '2026-11-03'}))
    for n in ('edit', 'sad', 'documentary'): (sd / f'momentum-{n}-2026-11-03.json').write_text('{}')
    port, out, log = stages.refresh({}, {}, Path(t), Path(t) / 'state')
    assert port == 'next' and out['soundsRefresh'] == {'refreshed': 0, 'discovered': [], 'stoppedBy': None}, out
# discovery: one set per run (each set gets the whole time budget), the stalest first, each set dated on its own;
# the old one-date file counts for every set
ran = []
real_run = soundmomentum.run_set
soundmomentum.run_set = lambda name, *a: ran.append(name) or {'set': name, 'sounds': [{'source': f'{name}-1'}]}
with tempfile.TemporaryDirectory() as t:
    sd = Path(t) / 'state' / 'sounds'; sd.mkdir(parents=True)
    (sd / 'uses-history.json').write_text(json.dumps({'s': {'title': 't', 'example': 'x', 'uses': {'2026-11-05': 5}}}))
    out = stages.refresh({}, {}, Path(t), Path(t) / 'state')[1]['soundsRefresh']
    assert ran == ['edit'] and out['discovered'] == ['edit'], (ran, out)          # never discovered: the first set
    assert json.loads((sd / 'discovery.json').read_text()) == {'edit': '2026-11-05'}
    # the report is saved, so music can keep each set's candidates to its own sounds
    assert json.loads((sd / 'momentum-edit-2026-11-05.json').read_text())['sounds'] == [{'source': 'edit-1'}]
    stages.refresh({}, {}, Path(t), Path(t) / 'state'); stages.refresh({}, {}, Path(t), Path(t) / 'state')
    assert ran == ['edit', 'sad', 'documentary'], ran                               # next runs take the sets not yet done
    stages.refresh({}, {}, Path(t), Path(t) / 'state')
    assert ran == ['edit', 'sad', 'documentary'], ran                               # all fresh: nothing to discover
    (sd / 'discovery.json').write_text(json.dumps({'edit': '2026-10-20', 'sad': '2026-10-25', 'documentary': '2026-11-01'}))
    stages.refresh({}, {}, Path(t), Path(t) / 'state')
    assert ran[-1] == 'edit', ran                                                   # stalest set over 7 days old
    (sd / 'discovery.json').write_text(json.dumps({'date': '2026-11-03'}))
    stages.refresh({}, {}, Path(t), Path(t) / 'state')
    assert len(ran) == 4, ran                                                       # old format: every set fresh
    # a set whose report file is missing is due again, whatever the date says (live: edit was dated with no report saved)
    (sd / 'discovery.json').write_text(json.dumps({'edit': '2026-11-05', 'sad': '2026-11-05', 'documentary': '2026-11-05'}))
    for f in sd.glob('momentum-sad-*.json'): f.unlink()
    stages.refresh({}, {}, Path(t), Path(t) / 'state')
    assert ran[-1] == 'sad' and len(ran) == 5, ran
soundmomentum.run_set = real_run

# _get: a 429 is waited out once, then retried
n = []
def flaky_json(url, timeout=30):
    n.append(1)
    if len(n) == 1: raise urllib.error.HTTPError(url, 429, 'slow', {}, None)
    return {'items': []}
net.get_json = flaky_json; slept.clear()
assert stages._get('u') == {'items': []} and 3 in slept
# a death in the news before Wikidata has it (live 2026-11-10: "Tommy Walsh, co-presenter of BBC's Ground Force, dies aged
# 68" while Wikidata had no date of death, so no tribute was possible)
H = lambda t, d='Mon, 09 Nov 2026 18:24:55 GMT': {'title': t, 'outlet': 'BBC', 'domain': 'bbc.co.uk', 'date': d}
assert people.death_in_headlines('Tommy Walsh', [H("Tommy Walsh, co-presenter of BBC's Ground Force, dies aged 68 - BBC")]) == '2026-11-09'
assert people.death_in_headlines('Tommy Walsh', [H('Tributes paid as Tommy Walsh has died')]) == '2026-11-09'
assert people.death_in_headlines('Tommy Walsh', [H('Tommy Walsh says he nearly died on set')]) is None   # not a death
assert people.death_in_headlines('Tommy Walsh', [H('Gardener dies aged 90')]) is None                  # someone else
assert people.death_in_headlines('Tommy Walsh', []) is None
# a name in a headline can be a namesake: the person's own Wikipedia lead must also speak of them in the past tense (live
# 2026-11-10: a search for Tommy Walsh found a 23-year-old Gaelic footballer, and the Ground Force headlines marked him dead)
assert people.lead_says_dead('Tommy Walsh was an English television personality, presenter and builder best known for Ground Force')
assert not people.lead_says_dead('Tommy Walsh is an Irish Gaelic footballer. At club level he plays with Kanturk')
assert not people.lead_says_dead('')
DEATH_H = [H("Tommy Walsh, co-presenter of BBC's Ground Force, dies aged 68")]
_gt, _gj, _pr = net.get_text, net.get_json, stages.pp.parse_rss
net.get_text = lambda url, timeout=30: ''
stages.pp.parse_rss = lambda x: DEATH_H
for title, lead, want in (('Tommy_Walsh_(builder)', 'Tommy Walsh was an English television personality.', '2026-11-09'),
                          ('Tommy_Walsh_(Cork_Gaelic_footballer)', 'Tommy Walsh is an Irish Gaelic footballer.', None)):
    net.get_json = lambda url, timeout=30, lead=lead: {'extract': lead}
    assert stages._headlines({'name': 'Tommy Walsh', 'title': title, 'died': None})['died'] == want, title
net.get_text, net.get_json, stages.pp.parse_rss = _gt, _gj, _pr
# repeats: one tribute ever; nobody twice in 2 days; the same format again within 30 days only for a case file with news
# since the last one (owner, 2026-11-10: a sentencing after the verdict is a new video, a second edit next week is not)
T = dt.date(2026, 11, 10)
C = lambda fmt, d, q='Q1': {'qid': q, 'format': fmt, 'date': d}
rb = lambda fmt, cov, heads=(): people.repeat_block('Q1', fmt, cov, list(heads), T)
assert rb('edit', []) is None and rb('tribute', [C('edit', '2026-11-09')]) is None          # a tribute is never blocked by other formats
assert 'tribute' in rb('tribute', [C('tribute', '2025-01-01')])                              # one tribute, ever
assert '2 days' in rb('topn', [C('edit', '2026-11-09')])                                     # not the same person two days running
assert rb('topn', [C('edit', '2026-11-07')]) is None                                         # another format after 2 days
assert 'edit' in rb('edit', [C('edit', '2026-10-20')]) and rb('edit', [C('edit', '2026-10-01')]) is None   # one edit a month
assert rb('edit', [C('edit', '2026-11-01', 'Q2')]) is None                                   # someone else's
assert 'no news' in rb('casefile', [C('casefile', '2026-11-05')], [H('Brand verdict', 'Wed, 04 Nov 2026 10:00:00 GMT')])
assert rb('casefile', [C('casefile', '2026-11-05')], [H('Brand sentenced', 'Mon, 09 Nov 2026 10:00:00 GMT')]) is None   # new reporting
assert 'casefile' in rb('casefile', [{'qid': 'Q1', 'date': '2026-11-01'}])                   # an old entry without a format counts as every format
print('ok')
