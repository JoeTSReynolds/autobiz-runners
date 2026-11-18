# Offline tests for trending/stages_mid.py (verify, music, probe, assets). Run: python3 test_stages_mid.py
import copy, datetime as dt, json, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from trending import stages_mid as sm

NATO = 'alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima'.split()
NOW = dt.datetime(2026, 11, 5, 12, tzinfo=dt.timezone.utc)
sm._now = lambda: NOW


def make_words(n=40):
    """n 12-word sentences, 0.5 s per word; sentence 3 starts with a [tag], sentence 4 with a '>> Alas,' speaker marker."""
    ws, t, sents = [], 0.0, {}
    for i in range(n):
        toks = [f'{w}{i}' for w in NATO]
        first = len(ws) + (1 if i == 3 else 2 if i == 4 else 0)
        pre = ['[applause]'] if i == 3 else ['>>', 'Alas,'] if i == 4 else []
        for k, w in enumerate(pre + toks):
            ws.append({'w': w + ('.' if k == len(pre + toks) - 1 else ''), 's': round(t, 3), 'e': round(t + 0.4, 3)})
            t += 0.5
        sents[i] = (ws[first]['s'], ws[-1]['e'], ' '.join(toks))
    return ws, sents


WORDS, SENT = make_words()
PERSON = {'qid': 'Q1', 'name': 'Callum Turner', 'born': '1990-02-15', 'died': '2026-10-28',
          'headlines': [{'title': 'Turner stuns Bond fans', 'outlet': 'BBC', 'domain': 'bbc.co.uk', 'date': '2026-11-04T09:00:00+00:00'},
                        {'title': 'Old news about Turner', 'outlet': 'BBC', 'domain': 'bbc.co.uk', 'date': '2026-10-20T09:00:00+00:00'}]}
POOL = [{'id': 'vid1', 'url': 'https://www.youtube.com/watch?v=vid1', 'duration': 600.0},
        {'id': 'vid2', 'url': 'https://www.youtube.com/watch?v=vid2', 'duration': 900.0}]
ARTICLES = json.load(open(HERE / 'fixtures' / 'mid-articles.json'))
CAND = {'provider': 'pexels', 'url': 'https://x/v.mp4', 'kind': 'video', 'w': 1080, 'h': 1920, 'duration': 8.0, 'credit': 'P', 'page': 'https://x'}
sm._pexels_videos = lambda q: [] if q.startswith('empty') else [CAND]
sm._commons_images = lambda q, n=6: []
_real_bing, sm._bing_images = sm._bing_images, lambda q: []   # never the real Bing in tests


def mkrun():
    d = Path(tempfile.mkdtemp())
    (d / 'captions').mkdir()
    for s in ('vid1', 'vid2'):
        (d / 'captions' / f'{s}.words.json').write_text(json.dumps(WORDS))
    return d


def job(fmt, sb, **kw):
    return dict({'format': fmt, 'person': PERSON, 'pool': POOL, 'storyboard': sb, 'articles': ARTICLES, 'rejectedPeople': ['Q0']}, **kw)


def verify(j):
    return sm.verify(j, {}, mkrun(), Path(tempfile.mkdtemp()))


def invalid(j, *needles):
    port, out, log = verify(j)
    assert port == 'invalid', (port, out, log)
    text = ' | '.join(out['agentErrors'])
    for n in needles:
        assert n in text, (n, out['agentErrors'])


def missing(j, *needles):
    port, out, log = verify(j)
    assert port == 'missing', (port, out, log)
    assert out['rejectedPeople'] == ['Q0', 'Q1'] and len(out['agentErrors']) == 1, out
    assert 'Callum Turner rejected at verify' in out['agentErrors'][0], out
    for n in needles:
        assert n in out['agentErrors'][0], (n, out)


def sq(i, a=None, b=None):  # quote of sentence i (all words, or words a:b)
    return ' '.join(SENT[i][2].split()[a:b])


def check_story(out):  # invariant: story.clips[i] is built from plan.clips[i]
    cl = out['plan']['clips']
    assert len(out['story']['clips']) == len(cl)
    assert out['download'] == ('yes' if cl else 'no')
    for c, s in zip(cl, out['story']['clips']):
        assert s == {'role': 'moment', 'start': c['start'], 'end': c['end'], 'source': c['source']}, (c, s)


# ---------------- verify: tribute
TRIB = {'name': 'Callum Turner',
        'spine': [{'source': 'vid1', 'quote': sq(10)}, {'source': 'vid2', 'quote': sq(11)}],
        'moments': [{'source': ('vid1', 'vid2')[i % 2], 'start': 100 + 10 * i, 'end': 104.5 + 10 * i} for i in range(6)],
        'closingLine': 'A life on the stage, and a voice for those who had nowhere else.'}
port, out, log = verify(job('tribute', TRIB))
assert port == 'next', (port, out, log)
p = out['plan']
assert p['format'] == 'tribute' and p['person'] == {'qid': 'Q1', 'name': 'Callum Turner', 'born': '1990-02-15', 'died': '2026-10-28', 'years': '1990 – 2026'}
assert [c['key'] for c in p['clips']] == ['m0', 'm1', 'spine0', 'm2', 'm3', 'spine1', 'm4', 'm5'], [c['key'] for c in p['clips']]
sp = next(c for c in p['clips'] if c['key'] == 'spine0')
assert sp['person'] is True and sp['source'] == POOL[0] | {} and abs(sp['start'] - (SENT[10][0] - 0.08)) < 1e-6 and abs(sp['end'] - (SENT[10][1] + 0.15)) < 1e-6, sp
assert p['spine'][0]['clip'] == 'spine0' and p['spine'][0]['text'] == sq(10) and len(p['spine'][0]['words']) == 12
assert [m['clip'] for m in p['moments']] == ['m0', 'm1', 'm2', 'm3', 'm4', 'm5'] and p['name'] == 'Callum Turner' and p['closingLine'].startswith('A life')
assert 40 <= p['predictedDuration'] <= 58 and out['predictedDuration'] == p['predictedDuration'] and out['agentErrors'] == []
check_story(out)
# tag / speaker marker inside a quote: resolved on the cleaned words
t2 = copy.deepcopy(TRIB); t2['spine'][0]['quote'] = '[applause] ' + sq(3)
assert verify(job('tribute', t2))[0] == 'next'
t2['spine'][0]['quote'] = sq(4)
assert verify(job('tribute', t2))[0] == 'next'
t2['spine'][0]['quote'] = '>> Alas, ' + sq(4)
assert verify(job('tribute', t2))[0] == 'next'
# quote not found names the line and the quote
t2 = copy.deepcopy(TRIB); t2['spine'][1]['quote'] = 'nothing like anything said ever'
invalid(job('tribute', t2), 'spine[1]', 'nothing like anything said ever')
t2 = copy.deepcopy(TRIB); t2['spine'][0]['quote'] = sq(10, 0, 8)
invalid(job('tribute', t2), 'spine[0]', 'at least 12 words')
t2 = copy.deepcopy(TRIB); t2['closingLine'] = 'one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen'
invalid(job('tribute', t2), 'closingLine', '14')
t2 = copy.deepcopy(TRIB); t2['moments'][2]['end'] = t2['moments'][2]['start'] + 1.0
invalid(job('tribute', t2), 'moments[2]', '1.5')
t2 = copy.deepcopy(TRIB); t2['moments'] = t2['moments'][:4]
invalid(job('tribute', t2), 'predicted duration')  # 4 x 4.5 s is too short
t2 = copy.deepcopy(TRIB); t2['spine'][0]['source'] = 'nope'
invalid(job('tribute', t2), 'spine[0]', 'nope')
# silent moments all from one video look like one clip (live 2026-11-10: Patrick Stewart, all six from one panel answer)
t2 = copy.deepcopy(TRIB)
for m in t2['moments']: m['source'] = 'vid1'
invalid(job('tribute', t2), 'moments', 'one video')

# ---------------- verify: topn
def moment(i, label='I dont know'):
    return {'source': ('vid1', 'vid2')[i % 2], 'fromQuote': sq(i, 0, 3), 'toQuote': sq(i, -3, None), 'label': label}
TOPN = {'title': 'Top 6 times Callum Turner dodged the Bond question', 'theme': 'dodging',
        'moments': [moment(10 + i) for i in range(6)],
        'closer': {'headline': 'Turner stuns Bond fans', 'line1': 'THIS WEEK', 'line2': 'STILL DODGING?'}}
port, out, log = verify(job('topn', TOPN))
assert port == 'next', (port, out, log)
# a Top N is separate times: moments all from one video are one exchange cut in five (live 2026-11-10: Stephen Miller's
# 'Top 5' was a single Jim Acosta briefing)
t1 = copy.deepcopy(TOPN)
for m in t1['moments']: m['source'] = 'vid1'
invalid(job('topn', t1), 'moments', '2 different')
p = out['plan']
assert p['n'] == 5 and p['title'].startswith('Top 5 times') and len(p['moments']) == 5
assert [m['rank'] for m in p['moments']] == [5, 4, 3, 2, 1] and [m['clip'] for m in p['moments']] == ['t0', 't1', 't2', 't3', 't4']
assert p['moments'][4]['label'] == 'I dont know' and p['moments'][4]['words'] and p['closer'] == TOPN['closer']
# each clip starts a little before the setup and runs on through the reply after the punchline (owner 2026-11-08: "we didn't
# hear one of the guys replies"), within 58 s for the whole Short; at least 35 s predicted (23-28 s felt short)
cl = {c['key']: c for c in p['clips']}
for m in p['moments']:
    c = cl[m['clip']]
    assert c['end'] - m['replyFrom'] > 1.5, (c, m['replyFrom'])             # the reply after the punchline is kept
    assert m['words'][-1]['s'] >= m['replyFrom'], m['words'][-1]            # and subtitled
    assert c['start'] <= m['words'][0]['s'] - 0.4, (c, m['words'][0])       # a lead-in before the setup
assert 35 <= p['predictedDuration'] <= 58, p['predictedDuration']
# the quoted part may be as short as TOPN_MIN_S: the lead-in and the reply make the clip long enough (live 2026-11-08: a 3.8 s
# roast was refused against the old 4 s minimum)
t3 = copy.deepcopy(TOPN); t3['moments'][0]['fromQuote'] = sq(10, 0, 3); t3['moments'][0]['toQuote'] = sq(10, 4, 6)   # words 0-5: 3 s
assert verify(job('topn', t3))[0] == 'next' and sm.TOPN_MIN_S == 2.5
# best N by agent rank: agent's first moment is rank 1 = last on screen
last = next(c for c in p['clips'] if c['key'] == 't4')
assert abs(last['start'] - (SENT[10][0] - 0.08 - sm.TOPN_PRE)) < 1e-6 and 35 <= p['predictedDuration'] <= 58
check_story(out)
# 6 to 8 proposals are required, so spares exist for the identity probe (live 2026-11-08: 5 proposed, 3 off camera, run lost)
t2 = copy.deepcopy(TOPN); t2['moments'] = t2['moments'][:5]
invalid(job('topn', t2), 'moments', '6 to 8')
t2 = copy.deepcopy(TOPN); t2['moments'][4]['fromQuote'] = t2['moments'][5]['fromQuote'] = 'never said anything like this'
port, out, _ = verify(job('topn', t2)); assert port == 'next' and out['plan']['n'] == 4 and out['plan']['title'].startswith('Top 4 ')
t2 = copy.deepcopy(TOPN)
for i in (1, 3, 5): t2['moments'][i]['fromQuote'] = 'never said anything like this'
# too few usable moments is fixable twice (the agent gets each moment's reason), then the person is dropped (live 2026-11-08:
# Gordon Ramsay's 4 quotes were all real but 3 ran 10.5-11 s, and the person was dropped with no chance to fix it)
port, out, _ = verify(job('topn', t2))
assert port == 'invalid' and out['verifyTries'] == 1 and any('3 of 6' in e for e in out['agentErrors']), (port, out)
port, out, _ = verify(job('topn', t2, verifyTries=1)); assert port == 'invalid' and out['verifyTries'] == 2
missing(job('topn', t2, verifyTries=2), '3 of 6', 'topn needs 4')
assert sm.TOPN_MAX_S == 12   # a roast with its setup runs 10-11 s
t2 = copy.deepcopy(TOPN); t2['closer']['headline'] = 'Something invented'
invalid(job('topn', t2), 'closer.headline')
t2 = copy.deepcopy(TOPN); t2['closer']['headline'] = 'Old news about Turner'
invalid(job('topn', t2), 'closer.headline', '72')
t2 = copy.deepcopy(TOPN); t2['moments'][0]['toQuote'] = sq(10, -3, None)
t2['moments'][0]['fromQuote'] = sq(10, 0, 3)  # unchanged: still fine
t2['moments'][0]['source'] = 'vid2'
assert verify(job('topn', t2))[0] == 'next'  # per-source words files

# the storyboard agent saying the material is not there is a dead end for this person, not a fixable mistake (live
# 2026-11-07: a tribute pool of news obituaries had no on-camera line of the person; two retries changed nothing)
missing(job('tribute', {'error': 'insufficient_source_material', 'reason': 'No transcript has the person speaking on camera.'}),
        'Callum Turner rejected at verify', 'speaking on camera')

# a line keeps exactly the caption words it matched, even when YouTube's times overlap (live 2026-11-12: "fighting" ran to
# 2161.4 s, past the line's end, and was dropped from the on-screen captions; "mistake." ran long and pulled in "Yes. Yes. And")
RW = [{'w': 'experience.', 's': 2157.074, 'e': 2157.994}, {'w': 'I', 's': 2157.994, 'e': 2158.114}, {'w': 'was', 's': 2158.114, 'e': 2158.354},
      {'w': 'fighting', 's': 2158.354, 'e': 2161.394}, {'w': 'acne.', 's': 2158.794, 'e': 2159.634}, {'w': 'I', 's': 2159.634, 'e': 2159.754}]
assert [w['w'] for w in sm._resolve(RW, 'I was fighting acne.')[2]] == ['I', 'was', 'fighting', 'acne.']
RW2 = [{'w': 'a', 's': 0.0, 'e': 0.3}, {'w': 'mistake.', 's': 0.3, 'e': 3.0}, {'w': 'Yes.', 's': 0.9, 'e': 1.2}, {'w': 'And', 's': 1.2, 'e': 1.4}]
assert [w['w'] for w in sm._resolve(RW2, 'a mistake.')[2]] == ['a', 'mistake.']

# a person whose storyboard fails 3 times is dropped and the run moves on to the next person (live 2026-11-11: the run ended
# on Jensen Huang instead); the count is per person (route resets it), so the next person gets their own tries
_bad = {'source': 'nope'}
p1 = verify(job('edit', _bad))
assert p1[0] == 'invalid' and p1[1]['storyTries'] == 1, p1
assert verify(job('edit', _bad, storyTries=1))[1]['storyTries'] == 2
missing(job('edit', _bad, storyTries=2), 'no valid storyboard after 3 tries', 'not in the pool')

# ---------------- verify: edit
def edit_sb(lines, **kw):
    sb = {'source': 'vid1', 'lines': lines, 'dropLine': 2, 'slams': ['28 YEARS', '31,000 MILES ON FOOT'],
          'popups': [{'text': 'HE DID IT. 14 DAYS.', 'line': 1}, {'text': 'NO ONE BELIEVED HIM', 'line': 3}],
          'broll': [{'query': f'sea ice {i}', 'line': i % 6} for i in range(7)], 'tail': [f'glacier {i}' for i in range(6)]}
    return dict(sb, **kw)
EDIT = edit_sb([sq(20 + i, 0, -1) for i in range(6)])  # 33.8 s of speech
# 36.8 s of speech fits the speech range, but with the slam gap after the drop and the 35% tail the video would pass 58 s
invalid(job('edit', edit_sb([sq(20 + i) for i in range(6)])), 'predicted duration', 'slams')
port, out, log = verify(job('edit', EDIT))
assert port == 'next', (port, out, log)
p = out['plan']
assert p['source'] == POOL[0] and [l['clip'] for l in p['lines']] == [f'l{i}' for i in range(6)] and p['dropLine'] == 2
assert p['slams'] == EDIT['slams'] and p['popups'] == EDIT['popups'] and len(p['broll']) == 7 and len(p['tail']) == 6
assert p['broll'][0] == {'query': 'sea ice 0', 'line': 0, 'candidates': [CAND]} and p['tail'][0] == {'query': 'glacier 0', 'candidates': [CAND]}
assert all(c['person'] for c in p['clips']) and 45 <= p['predictedDuration'] <= 58, p['predictedDuration']
check_story(out)
assert p['footage'] == []   # no footage queries: none
# footage: up to 4 YouTube queries for real footage of the person's work; anything but text is ignored
assert verify(job('edit', dict(EDIT, footage=['a scene', 3, ' b ', '', 'c', 'd', 'e'])))[1]['plan']['footage'] == ['a scene', 'b', 'c', 'd']
invalid(job('edit', edit_sb([sq(20 + i) for i in range(12)])), 'speech', '38')  # 73 s of speech
invalid(job('edit', edit_sb([sq(20 + i, 0, 4) for i in range(6)])), 'speech', '25')
invalid(job('edit', edit_sb([sq(20 + i, 0, -1) for i in range(6)], dropLine=9)), 'dropLine')
invalid(job('edit', edit_sb([sq(20 + i, 0, -1) for i in range(5, -1, -1)])), 'order')
# too short is covered by the 25 s speech minimum: with 2+ slams and the tail, 25 s of speech already predicts about 43-45 s
bad = [sq(20 + i, 0, -1) for i in range(6)]; bad[3] = 'alpha99 never said'
invalid(job('edit', edit_sb(bad)), 'lines[3]', 'alpha99 never said')
invalid(job('edit', edit_sb([sq(20 + i, 0, -1) for i in range(6)], slams=['ONE TWO THREE FOUR FIVE SIX', 'OK'])), 'slams[0]')
# b-roll coverage: 13 queries, 4 empty = 69% -> invalid and names them; 3 empty = 77% ok
e = edit_sb([sq(20 + i, 0, -1) for i in range(6)], broll=[{'query': ('empty ' if i < 4 else '') + f'sea {i}', 'line': 0} for i in range(7)])
invalid(job('edit', e), 'b-roll', 'empty sea 0', 'empty sea 3')
e['broll'][3]['query'] = 'sea 3'
assert verify(job('edit', e))[0] == 'next'

# verify writes run/broll.txt for the b-roll agent: every distinct query with its line text and numbered candidate descriptions
_pv, _ci = sm._pexels_videos, sm._commons_images
sm._pexels_videos = lambda q: [dict(CAND, page='https://www.pexels.com/video/a-man-climbing-on-rocks-8726216/'), dict(CAND, page='https://www.pexels.com/video/car-drifting-at-a-crowd-123/')]
sm._commons_images = lambda q, n=6: [{'provider': 'commons', 'kind': 'image', 'title': 'File:Alex_Honnold_on_El_Capitan.jpg', 'url': 'u'}]
r = mkrun()
port, out, _ = sm.verify(job('edit', EDIT), {}, r, Path(tempfile.mkdtemp()))
assert port == 'next' and out['brollText'] == {'file': 'broll.txt'}, out
txt = (r / 'broll.txt').read_text()
assert txt.count('query: ') == 13, txt
assert f'query: sea ice 0\nline: {EDIT['lines'][0]}\n0: a man climbing on rocks\n1: car drifting at a crowd\n' in txt, txt
assert 'query: glacier 0\n0: a man climbing on rocks\n' in txt and 'line:' not in txt.split('query: glacier 0')[1].split('query:')[0], txt
assert sm._describe({'title': 'File:Alex_Honnold_on_El_Capitan.jpg'}) == 'Alex Honnold on El Capitan'
sm._pexels_videos, sm._commons_images = _pv, _ci
# other formats write an empty file and still set brollText (the agent block needs its fileKeys to exist)
r = mkrun()
port, out, _ = sm.verify(job('tribute', TRIB), {}, r, Path(tempfile.mkdtemp()))
assert port == 'next' and out['brollText'] == {'file': 'broll.txt'} and (r / 'broll.txt').read_text() == '', out

# ---------------- verify: casefile
NOSHOT = {'kind': 'photo', 'query': 'turner portrait'}
def cf_sb(**kw):
    texts = ['[dramatic] The BBC reports that Callum Turner faces new claims over a film set dispute.',
             'According to the Guardian, crew on a Turner film were left unpaid for six weeks.',
             'The claims date back to the autumn of 2024.',
             'Documents seen by the Guardian suggest the production company is now under review.',
             'A hearing is expected in January, the BBC says.',
             'Turner denies the allegations and says he has never refused to pay anyone.',
             'His lawyers say he rejects the claims in full.',
             'Colleagues describe weeks of missed payments and unanswered emails.',
             'The production company has not commented on the review.',
             'For now, nothing has been proven in court.']
    vis = [{'kind': 'screenshot', 'outlet': 'BBC', 'highlight': 'crew were left unpaid for six weeks'}, {'kind': 'photo', 'query': 'turner portrait'},
           {'kind': 'timeline', 'label': 'AUG 2024'}, {'kind': 'screenshot', 'outlet': 'Guardian', 'highlight': 'production company was under review'},
           {'kind': 'photo', 'query': 'film set'}, {'kind': 'quote', 'text': 'has never refused to pay', 'outlet': 'BBC'},
           {'kind': 'clip', 'source': 'vid1', 'start': 100.0, 'end': 103.0}, {'kind': 'photo', 'query': 'london court'},
           {'kind': 'timeline', 'label': 'JAN 2025'}, {'kind': 'quote', 'text': 'rejects the claims in full', 'outlet': 'Guardian'}]
    sup = lambda b, g: [{'outlet': 'BBC', 'quote': b}, {'outlet': 'Guardian', 'quote': g}]
    sb = {'title': 'Unpaid crew claims', 'script': [{'text': t, 'visual': v} for t, v in zip(texts, vis)],
          'claims': [{'text': 'crew unpaid', 'support': sup('crew were left unpaid for six weeks', 'crew were left unpaid for six weeks')},
                     {'text': 'hearing', 'support': sup('A hearing is expected in January', 'the production company was under review')},
                     {'text': 'claims', 'support': sup('faces new claims over a 2024 film set dispute', 'seen documents suggesting crew were left unpaid')},
                     {'text': 'denial', 'support': sup('has never refused to pay', 'rejects the claims in full')}],
          'timeline': [{'label': 'AUG 2024', 'text': 'a'}, {'label': 'JAN 2025', 'text': 'b'}]}
    return dict(sb, **kw)
sm._commons_images = lambda q, n=6: [] if 'empty' in q else [dict(CAND, provider='commons', kind='image')]
port, out, log = verify(job('casefile', cf_sb()))
assert port == 'next', (port, out, log)
p = out['plan']
assert p['title'] == 'Unpaid crew claims' and len(p['script']) == 10 and p['script'][0]['spoken'].startswith('The BBC reports') and '[' not in p['script'][0]['spoken']
v = [s['visual'] for s in p['script']]
assert v[0] == {'kind': 'screenshot', 'outlet': 'BBC', 'url': ARTICLES[0]['url'], 'highlight': 'crew were left unpaid for six weeks'}
assert v[1]['kind'] == 'photo' and v[1]['candidates'] and v[2] == {'kind': 'timeline', 'label': 'AUG 2024'}
assert v[5] == {'kind': 'quote', 'text': 'has never refused to pay', 'outlet': 'BBC'} and v[6] == {'kind': 'clip', 'clip': 'a0'}
assert [c['key'] for c in p['clips']] == ['a0'] and p['clips'][0]['person'] is True and p['clips'][0]['source'] == POOL[0]
assert p['claims'][0]['support'][0]['url'] == ARTICLES[0]['url'] and p['claims'][0]['support'][1]['url'] == ARTICLES[1]['url']
assert p['words'] == sum(len(s['spoken'].split()) for s in p['script']) and 0 < p['predictedDuration'] <= 57
check_story(out)
c = cf_sb(); c['claims'][1]['support'][1] = {'outlet': 'BBC', 'quote': 'a hearing is expected in January'}  # same outlet twice
invalid(job('casefile', c), 'claims[1]', '2 different outlets')
c = cf_sb(); c['claims'][2]['support'][0]['quote'] = 'the star was arrested on a yacht in Monaco'
invalid(job('casefile', c), 'claims[2]', 'the star was arrested on a yacht')
c = cf_sb(); c['script'][5]['text'] = 'Turner says he has never refused to pay anyone.'; c['script'][6]['text'] = 'His lawyers are expected to say more.'
invalid(job('casefile', c), 'denial')  # BBC and Guardian report a denial, the script has none
# someone else's denial that merely names the person is not the person's denial (Trump denied this ... Huang would join him)
a2 = copy.deepcopy(ARTICLES)
for a in a2: a['text'] = a['text'].replace('Turner denies the allegations and', 'Turner').replace('he rejects the claims', 'the claims are')
a2[0]['text'] += ' But the studio denied this, writing that Turner would return next year.'
port, out, log = verify(job('casefile', c, articles=a2))
assert port == 'next', (port, out, log)
a2[0]['text'] += " Turner's lawyers have firmly denied wrongdoing."
invalid(job('casefile', c, articles=a2), 'denial')
c = cf_sb(); c['script'][3]['visual'] = dict(c['script'][3]['visual'], highlight='words that are not in the article')
invalid(job('casefile', c), 'script[3]', 'highlight')
c = cf_sb(); c['script'][1]['visual'] = dict(c['script'][0]['visual'])
invalid(job('casefile', c), 'two screenshots in a row')
c = cf_sb(); c['script'][4]['visual'] = {'kind': 'photo', 'query': 'empty film set'}; c['script'][1]['visual']['query'] = 'empty portrait'
invalid(job('casefile', c), 'photo', 'empty film set', 'empty portrait')
c = cf_sb(); c['script'][6]['visual']['end'] = 110.0
invalid(job('casefile', c), 'script[6]', '2 to 4')
c = cf_sb(); c['script'][2]['text'] = 'A super-injunction now stops the press from saying more.'
missing(job('casefile', c), 'blocked')
a2 = copy.deepcopy(ARTICLES); a2[0]['text'] += ' A court granted an injunction against Turner last year.'
missing(job('casefile', cf_sb(), articles=a2), 'injunction')
c = cf_sb(); c['script'] += [{'text': ' '.join(['word'] * 12) + '.', 'visual': {'kind': 'timeline', 'label': 'X'}} for _ in range(4)]
invalid(job('casefile', c), 'script', '57')  # 14 sentences, 16 + words too long at 2.3 words/s
# the length is predicted at the measured narration rate (Kokoro bm_george at 1.12 with sentence gaps: 2.33 words/s)
_p = verify(job('casefile', cf_sb()))[1]['plan']
assert abs(_p['predictedDuration'] - _p['words'] / 2.3) < 0.01, _p['predictedDuration']
c = cf_sb(); c['script'][0]['text'] = ' '.join(['word'] * 130) + '.'
invalid(job('casefile', c), '57')
missing(job('casefile', cf_sb(), articles=ARTICLES[:1]), 'outlets')
# attribution reads naturally: never "both outlets report" on line after line (live 2026-11-10: said 5 times in one Brand script)
c = cf_sb(); c['script'][7]['text'] = 'Colleagues describe weeks of missed payments, both outlets report.'
invalid(job('casefile', c), 'script[7]', 'both outlets')


# ---------------- music
import datetime
sm._today = lambda: datetime.date(2026, 11, 5)
sm._search = lambda q: []   # no YouTube search unless a test sets one
AN = lambda **kw: dict({'duration': 120.0, 'bpm': 128.0, 'beats': [], 'drop': 20.0, 'drops': [{'time': 20.0, 'score': 9.0}], 'vocal_hint': 0.05, 'vocal_share': 0.02,
                        'intensity': [0.2] * 30 + [1.0] * 5, 'build_score': 0.5}, **kw)
OLD = lambda **kw: {k: v for k, v in AN(**kw).items() if k != 'vocal_share'}   # an analysis from before vocal_share
assert sm._passes('edit', OLD()) and not sm._passes('edit', OLD(vocal_hint=0.12)) and not sm._passes('edit', AN(drops=[{'time': 20, 'score': 3.0}]))
assert sm._passes('edit', AN(vocal_hint=0.9)) and not sm._passes('edit', AN(vocal_hint=0.0, vocal_share=0.15)) and sm._passes('edit', AN(vocal_share=0.14))  # the measured share wins over the hint
assert not sm._passes('edit', AN(vocal_share=0.5), labelled=True) and sm._passes('edit', OLD(vocal_hint=0.5), labelled=True)
assert not sm._passes('documentary', AN(bpm=90, vocal_share=0.5), labelled=True)   # a measured vocal beats an 'instrumental' title
# slow piano reads at double time (live 2026-11-10: three vocal-free 'sad emotional piano' tracks at 120-136 bpm), so sad has no bpm cap
assert sm._passes('sad', AN(bpm=80)) and sm._passes('sad', AN(bpm=130)) and not sm._passes('sad', AN(bpm=80, intensity=[0.5] * 35))
assert not sm._passes('sad', OLD(bpm=80, vocal_hint=0.14))   # a slowed vocal funk track is not a tribute bed (live 2026-11-07)
assert sm._passes('documentary', OLD(bpm=90, vocal_hint=0.09, drops=[{'time': 5, 'score': 2.0}])) and not sm._passes('documentary', AN(bpm=90))
assert not sm._passes('documentary', OLD(bpm=90, vocal_hint=0.1, drops=[]) ) and not sm._passes('documentary', AN(bpm=120, drops=[]))
MP = {'format': 'edit', 'dropLine': 2, 'predictedDuration': 50.0, 'clips': [{'key': f'l{i}', 'start': 10, 'end': 16} for i in range(6)]}


def mstate(used=(), rejected=None, tracks=None, hist=True, momentum=None):
    st = Path(tempfile.mkdtemp()); sd = st / 'sounds'; (sd / 'tracks').mkdir(parents=True)
    if hist:
        g = {'A': (1000, 1500), 'B': (1000, 1300), 'C': (1000, 2000), 'D': (1000, 1100), 'E': (1000, 1050)}
        (sd / 'uses-history.json').write_text(json.dumps({k: {'title': f'Song {k}', 'example': 'x', 'uses': {'2026-11-04': a, '2026-11-05': b}} for k, (a, b) in g.items()}))
    (st / 'trending-used-sounds.json').write_text(json.dumps([{'id': i, 'date': d} for i, d in used]))
    if rejected is not None: (sd / 'rejected.json').write_text(json.dumps(rejected))
    for k, a in (tracks or {}).items():
        (sd / 'tracks' / f'{k}.json').write_text(json.dumps(a)); (sd / 'tracks' / f'{k}.m4a').write_bytes(b'x')
    if momentum is None and hist: momentum = ('edit', 'ABCDE')   # edit needs its own report; pass momentum=() for none
    if momentum: (sd / f'momentum-{momentum[0]}-2026-11-05.json').write_text(json.dumps({'sounds': [{'source': s} for s in momentum[1]]}))
    return st


def mrun(st, plan=MP, fmt='edit'):
    return sm.music(dict(job('edit', {}), format=fmt, plan=plan), {}, Path(tempfile.mkdtemp()), st)


ALL = {k: AN() for k in 'ABCDE'}
port, out, log = mrun(mstate(used=[('C', '2026-11-03')], tracks=ALL))   # C grows fastest but was used 2 days ago
assert port == 'next' and out['track']['id'] == 'A' and out['track']['title'] == 'Song A', (port, out)
assert out['track']['file'].endswith('A.m4a') and out['track']['analysis']['bpm'] == 128.0
assert out['plan']['musicOffset'] == 8.0 and out['plan']['clips'] == MP['clips'], out['plan']  # drop 20 s, drop line starts at 12 s
assert mrun(mstate(tracks=ALL))[1]['track']['id'] == 'C'                        # ranking by growth per day
assert mrun(mstate(used=[('C', '2026-11-03'), ('A', '2026-11-04')], tracks=ALL))[1]['track']['id'] == 'B'
assert mrun(mstate(used=[('C', '2025-01-01')], tracks=ALL))[1]['track']['id'] == 'C'   # old use does not count
st = mstate(used=[('C', '2026-11-03'), ('A', '2026-11-04')], rejected={'B': ['edit'], 'D': ['sad']}, tracks=ALL)
assert mrun(st)[1]['track']['id'] == 'D'                                         # B rejected for edit, D only for sad
# failing analysis is rejected for this set and the next candidate is tried
st = mstate(used=[('C', '2026-11-03')], tracks=dict(ALL, A=AN(vocal_share=0.5)))
port, out, _ = mrun(st)
assert out['track']['id'] == 'B' and json.loads((st / 'sounds' / 'rejected.json').read_text()) == {'A': ['edit']}
# at most 4 candidates, all failing: missing, nothing else tried
bad = {k: AN(vocal_share=0.5) for k in 'ABCDE'}
st = mstate(tracks=bad)
port, out, log = mrun(st)
assert port == 'missing' and out['rejectedPeople'] == ['Q0', 'Q1'] and len(out['agentErrors']) == 1 and 'music' in out['agentErrors'][0], out
assert sorted(json.loads((st / 'sounds' / 'rejected.json').read_text())) == ['A', 'B', 'C', 'D'] and 'E' not in json.loads((st / 'sounds' / 'rejected.json').read_text())
# not analysed yet: download + analyse, analysis saved as tracks/<id>.json
calls = []
def fetch(i, d):
    calls.append(i); p = Path(d) / f'{i}.m4a'; p.write_bytes(b'x'); return str(p)
sm._fetch_track, sm._analyse = fetch, lambda p, m=None: AN()
st = mstate(tracks={})
port, out, _ = mrun(st)
assert calls == ['C'] and out['track']['id'] == 'C' and json.loads((st / 'sounds' / 'tracks' / 'C.json').read_text())['bpm'] == 128.0
# the cloud seed ships analyses without the audio: a passing analysis whose .m4a is missing fetches the audio again
st = mstate(tracks={'C': AN()}); (st / 'sounds' / 'tracks' / 'C.m4a').unlink(); calls.clear()
port, out, _ = mrun(st)
assert port == 'next' and out['track']['id'] == 'C' and calls == ['C'] and (st / 'sounds' / 'tracks' / 'C.m4a').exists(), (port, calls)
assert mrun(st)[1]['track']['id'] == 'C' and calls == ['C']                      # second run reads the saved analysis
# fallback: nothing in the history, an analysed track of the right set that was not used in 3 days
sm._analyse = lambda p, m=None: AN()
st = mstate(hist=False, tracks={'Z1': AN(vocal_share=0.5), 'Z2': AN(), 'Z3': AN()}, used=[('Z2', '2026-11-04')])
assert mrun(st)[1]['track']['id'] == 'Z3'
assert mrun(mstate(hist=False, tracks={'Z1': AN(vocal_share=0.5)}))[0] == 'missing'
# per-set candidates: a momentum report for the set restricts them; sad places the swell on the last clip
SAD = AN(bpm=80)
TP = {'format': 'tribute', 'predictedDuration': 50.0, 'clips': [{'key': 'm0', 'start': 0, 'end': 4}, {'key': 'spine0', 'start': 0, 'end': 10}, {'key': 'm1', 'start': 0, 'end': 4}]}
# a tribute never takes a trending sound or a cached track: the sad tags trend pop songs (live 2026-11-10: "SugarCrash Slowed")
sm._search = lambda q: []
assert mrun(mstate(tracks={k: SAD for k in 'ABCDE'}, momentum=('sad', ['D', 'E'])), plan=TP, fmt='tribute')[0] == 'missing'
sm._search = lambda q: [{'id': 'P0', 'title': 'Emotional Piano Instrumental', 'duration': 200, 'view_count': 9}]
port, out, _ = mrun(mstate(tracks={k: SAD for k in 'ABCDE'} | {'P0': SAD}, momentum=('sad', ['D', 'E'])), plan=TP, fmt='tribute')
assert out['track']['id'] == 'P0' and out['plan']['musicOffset'] == 30 - (4 / 0.8 + 10), (port, out)
sm._search = lambda q: []
# documentary: no placement
DOC = AN(bpm=90, vocal_hint=0.05, drops=[{'time': 5, 'score': 2.0}])
port, out, _ = mrun(mstate(tracks={'A': DOC}), plan=dict(MP, format='casefile'), fmt='casefile')
assert out['track']['id'] == 'A' and out['plan']['musicOffset'] == 0.0
# documentary/sad without their own momentum report never take the (edit-heavy) history; a YouTube search for
# instrumentals of the kind is tried instead, most viewed first, 90 s to 10 min long, skipping rejected and recent ones
searched, calls = [], []
sm._search = lambda q: searched.append(q) or [{'id': 'S1', 'title': 'Dark doc 1', 'duration': 200, 'view_count': 5},
                                              {'id': 'S2', 'title': 'Dark doc 2', 'duration': 200, 'view_count': 50},
                                              {'id': 'S3', 'title': 'Too short', 'duration': 30, 'view_count': 900}]
sm._fetch_track = fetch
sm._analyse = lambda p, m=None: DOC if 'S2' in p else OLD(vocal_hint=0.5)
st = mstate(tracks={})
port, out, _ = mrun(st, plan=dict(MP, format='casefile'), fmt='casefile')
assert port == 'next' and out['track']['id'] == 'S2' and out['track']['title'] == 'Dark doc 2', (port, out)
assert calls == ['S2'] and searched and all('instrumental' in q or 'music' in q for q in searched), (calls, searched)
st = mstate(tracks={}, rejected={'S2': ['documentary']})
calls.clear(); port, out, _ = mrun(st, plan=dict(MP, format='casefile'), fmt='casefile')
assert calls == ['S1'] and port == 'missing', (calls, port)   # S1 fails the test, S3 too short, history never tried
sm._search = lambda q: []
# the vocal hint is calibrated on bass-heavy edit tracks and reads strings and pads as voice: real documentary beds scored
# 0.47-0.68 with strong builds (live 2026-11-07). A search result whose own title says it is instrumental or background
# music is trusted for that; a trending sound still has to pass the analysis
sm._search = lambda q: [{'id': 'B1', 'title': 'REVENGE (Super Slowed)', 'duration': 200, 'view_count': 900},
                        {'id': 'B2', 'title': 'Investigation Music Background | Suspenseful Tension Royalty Free', 'duration': 200, 'view_count': 50}]
sm._analyse = lambda p, m=None: OLD(bpm=120, vocal_hint=0.55, drops=[{'time': 30, 'score': 22.8}])
calls.clear(); port, out, _ = mrun(mstate(tracks={}), plan=dict(MP, format='casefile'), fmt='casefile')
assert port == 'next' and out['track']['id'] == 'B2' and calls == ['B1', 'B2'], (port, calls)
SADL = OLD(bpm=80, vocal_hint=0.6)   # swell present (intensity rises at the end)
sm._search = lambda q: [{'id': 'P1', 'title': 'Sad Emotional Piano Instrumental', 'duration': 200, 'view_count': 9}]
sm._analyse = lambda p, m=None: SADL
port, out, _ = mrun(mstate(tracks={}), plan=TP, fmt='tribute')
assert port == 'next' and out['track']['id'] == 'P1', (port, out)
sm._analyse = lambda p, m=None: OLD(bpm=80, vocal_hint=0.6, intensity=[0.5] * 35)      # labelled, but no swell for the closing card
assert mrun(mstate(tracks={}), plan=TP, fmt='tribute')[0] == 'missing'
sm._search = lambda q: []
# the Dua Lipa case (live 2026-11-08): a cached analysis from before vocal_share (hint 0.084) is analysed again, then rejected
reanalysed = []
sm._analyse = lambda p, m=None: reanalysed.append(m) or AN(vocal_share=0.5 if p.endswith('/A.m4a') else 0.0)
st = mstate(tracks={'A': OLD(vocal_hint=0.084)}, hist=True)
assert mrun(st)[1]['track']['id'] != 'A' and reanalysed[0] == st / 'models', reanalysed
sm._analyse = lambda p, m=None: AN()
assert mrun(mstate(hist=False, tracks={'Z': OLD(vocal_hint=0.084)}))[0] == 'missing'   # the cached-track fallback needs a measured share
# edit never falls back to the whole history: without its own report the instrumental search is used, edit-style titles first,
# live/acoustic/cover/lyrics/karaoke skipped
calls.clear()
sm._search = lambda q: [{'id': 'L1', 'title': 'Training Season (Live from the Royal Albert Hall)', 'duration': 200, 'view_count': 9000},
                        {'id': 'L2', 'title': 'Some Song (Acoustic Cover)', 'duration': 200, 'view_count': 8000},
                        {'id': 'L3', 'title': 'Popular Remix Mashup', 'duration': 200, 'view_count': 7000},
                        {'id': 'L4', 'title': 'Slowed Phonk Bass Drift', 'duration': 200, 'view_count': 10},
                        {'id': 'L5', 'title': 'Lyrics Video', 'duration': 200, 'view_count': 6000},
                        {'id': 'L6', 'title': 'Unrelated Song', 'duration': 200, 'view_count': 5000}]
assert [i for i, _ in sm._searched('edit')] == ['L3', 'L4', 'L6'] or [i for i, _ in sm._searched('edit')] == ['L4', 'L3', 'L6'], sm._searched('edit')
sm._search = lambda q: []
assert sm._ranked(mstate(hist=True, momentum=()) / 'sounds', 'edit') == []                      # no edit report: not the history
st = mstate(hist=True, momentum=('edit', ['A', 'B']))
assert [i for i, _ in sm._ranked(st / 'sounds', 'edit')] == ['A', 'B']
import json as _j
(st / 'sounds' / 'uses-history.json').write_text(_j.dumps({k: {'title': t, 'example': 'x', 'uses': {'2026-11-04': 1000, '2026-11-05': 1000 + g}} for k, t, g in
    [('A', 'Pop Song (Live)', 900), ('B', 'Lyrics: Pop Song', 800), ('C', 'Pop Song', 700), ('D', 'Phonk Slowed', 100), ('E', 'Funk Bass', 50)]}))
(st / 'sounds' / 'momentum-edit-2026-11-05.json').write_text(_j.dumps({'sounds': [{'source': k} for k in 'ABCDE']}))
assert [i for i, _ in sm._ranked(st / 'sounds', 'edit')] == ['D', 'E', 'C'], sm._ranked(st / 'sounds', 'edit')   # style first, live/lyrics out


# ---------------- probe
import numpy as np
VEC = {'target': np.array([1.0, 0, 0]), 'other': np.array([0, 1.0, 0]), 'footage': np.array([0.8, 0, 0.6]),
       'side': np.array([0.3, 0, 0.95])}   # the person from another angle: 0.30 to the photo, 0.81 to the footage
KINDS = {}                      # window start -> frame kinds of that probe
DL = []                         # downloader calls (source id, windows)


def wins(c):  # window starts of a clip's probes (start, middle, end)
    return [round(a, 2) for a, _ in sm._windows(c)]


def stub_download(sid, url, windows, out_dir):
    DL.append((sid, [tuple(round(x, 2) for x in w) for w in windows]))
    return [None if KINDS.get(round(s, 2)) == 'nodl' else str(Path(out_dir) / f'{sid}_{round(s, 2)}.mp4') for s, _ in windows]


def stub_frames(path, n=5):
    k = KINDS[round(float(Path(path).stem.split('_')[1]), 2)]
    return ['none'] * 5 if k == 'wide' else ['none', 'other', k, k, k] if k != 'other' else ['other'] * 5   # wide: no face found


sm._probe_download, sm._frames = stub_download, stub_frames
sm._embed = lambda img, models_dir: VEC.get(img)   # the reference photo
# every face in a probe frame: 'pair' is another person in the foreground with the target smaller behind
sm._frame_embeds = lambda img, models_dir: [VEC['other'], VEC['target']] if img == 'pair' else ([VEC[img]] if img in VEC else [])
sm._reference_image = lambda person: 'target'


def clip(key, sid, a, b, person=True):
    return {'key': key, 'source': {'id': sid, 'url': f'https://www.youtube.com/watch?v={sid}', 'duration': 600.0}, 'start': a, 'end': b, 'person': person}


def tplan(nm=6):
    cl = [clip('spine0', 'vid1', 10, 16), clip('spine1', 'vid2', 20, 26)] + [clip(f'm{i}', 'vid1' if i % 2 else 'vid2', 100 + 10 * i, 104.5 + 10 * i) for i in range(nm)]
    return {'format': 'tribute', 'person': {'name': 'Callum Turner'}, 'clips': cl, 'spine': [{'clip': 'spine0'}, {'clip': 'spine1'}],
            'moments': [{'clip': f'm{i}'} for i in range(nm)], 'predictedDuration': 50.0}


def pj(plan, **kw):
    return dict(job(plan['format'], {}), plan=plan, **kw)


def prb(plan, kinds=None, ref=True, **kw):
    KINDS.clear(); DL.clear()
    KINDS.update({w: 'target' for c in plan['clips'] for w in wins(c)})
    for key, k in (kinds or {}).items():
        if isinstance(k, (tuple, list)):   # (window index, kind), or a list of them: only those windows of the clip
            for i, kk in ([k] if isinstance(k, tuple) else k):
                KINDS[wins(next(c for c in plan['clips'] if c['key'] == key))[i]] = kk
        else:
            KINDS.update({w: k for w in wins(next(c for c in plan['clips'] if c['key'] == key))})
    sm._reference_image = (lambda person: 'target') if ref else (lambda person: None)
    r, st = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
    return sm.probe(pj(plan, **kw), {}, r, st) + (r,)


port, out, log, r = prb(tplan())
assert port == 'next' and out['plan']['clips'] == tplan()['clips'] and out['identity'] == {'file': 'identity.npy'} and out['agentErrors'] == []
assert np.allclose(np.load(r / 'identity.npy'), VEC['target']) and len(out['story']['clips']) == 8   # matched frames are the target itself
assert out['download'] == 'yes'
assert sorted(c[0] for c in DL) == ['vid1', 'vid2'] and sum(len(c[1]) for c in DL) == 24     # one call per source, 3 windows per clip
d1 = dict(DL)['vid2']; assert [(100.0, 101.0), (101.75, 102.75), (103.5, 104.5)] == [w for w in d1 if 100 <= w[0] < 105], d1   # start, middle, end
# a clip whose last second shows someone else fails (live 2026-11-07: a news tribute's slideshow photo of another man
# at the end of a clip passed a middle-only probe and reached the closing card)
port, out, _, _ = prb(tplan(), {'m5': (2, 'other')})
assert port == 'next' and 'm5' not in [m['clip'] for m in out['plan']['moments']] and 'm5' in out['agentErrors'][0], out['agentErrors']
# the gate's reference is the footage itself (the mean of the probe frames that matched the photo), not the photo:
# a Commons photo is another camera, lighting and age, and scored only 0.32-0.38 against the real render (live, 2026-11-07)
port, out, log, r = prb(tplan(), {c['key']: 'footage' for c in tplan()['clips']})
assert port == 'next' and np.allclose(np.load(r / 'identity.npy'), VEC['footage'] / np.linalg.norm(VEC['footage'])), np.load(r / 'identity.npy')
# a failed moment is dropped and named; a moment that could not be downloaded too
port, out, _, _ = prb(tplan(), {'m2': 'other', 'm3': 'nodl'})
assert port == 'next' and [c['key'] for c in out['plan']['clips']].count('m2') == 0 and 'm3' not in [m['clip'] for m in out['plan']['moments']]
assert len(out['plan']['moments']) == 4 and len(out['story']['clips']) == 6 and len(out['agentErrors']) == 2
assert 'm2' in out['agentErrors'][0] and 'm3' in out['agentErrors'][1] and 'Callum Turner' in out['agentErrors'][0], out['agentErrors']
assert out['plan']['predictedDuration'] != 50.0
# minimum broken: 3 moments left -> invalid, naming the failures; a failed spine line -> invalid
port, out, _, _ = prb(tplan(), {'m0': 'other', 'm1': 'other', 'm5': 'other'})
assert port == 'invalid' and any('at least 4' in e for e in out['agentErrors']) and any('m5' in e for e in out['agentErrors']), out
port, out, _, _ = prb(tplan(), {'spine1': 'other'})
assert port == 'invalid' and any('spine1' in e for e in out['agentErrors']), out
# edit: every line is probed; it is his talk when he is on camera in at least 2 lines. A line showing someone else keeps
# its audio and gets a cutaway picture (cover), as the reference edit cuts away while the person talks (owner, 2026-11-09)
eplan = {'format': 'edit', 'person': {'name': 'Callum Turner'}, 'clips': [clip(f'l{i}', 'vid1', 100 + 10 * i, 106 + 10 * i) for i in range(6)], 'lines': []}
port, out, _, _ = prb(eplan, {'l5': 'other'})
assert port == 'next' and len(DL) == 1 and len(DL[0][1]) == 18 and out['agentErrors'] == [], out
assert [c.get('cover', False) for c in out['plan']['clips']] == [False] * 5 + [True]
port, out, _, _ = prb(eplan, {'l0': 'other', 'l1': 'other', 'l5': 'other'})   # live 2026-11-09: Magnus Midtbø on camera with Honnold
assert port == 'next' and [c.get('cover', False) for c in out['plan']['clips']] == [True, True, False, False, False, True]
assert prb(eplan, {'l0': 'wide', 'l5': 'wide'})[0] == 'next'                  # a wide stage shot is not someone else, and no cover
assert prb(eplan, {f'l{i}': 'other' for i in range(1, 6)})[0] == 'invalid'    # on camera in 1 line only: not his talk
# no line shows him (live 2026-11-09: a REEL ROCK behind-the-scenes video, climbing shots and a cameraman talking): back to
# the storyboard for another source; the person is kept
port, out, _, _ = prb(eplan, {'l0': 'wide', 'l1': 'other', 'l2': 'wide', 'l3': 'other', 'l4': 'wide', 'l5': 'wide'})
assert port == 'invalid' and 'rejectedPeople' not in out and 'another source' in out['agentErrors'][-1], out
assert prb(eplan, {f'l{i}': 'wide' for i in range(6)})[0] == 'invalid'
# topn: a failed moment shrinks N and renumbers the ranks
tn = {'format': 'topn', 'person': {'name': 'Callum Turner'}, 'title': 'Top 5 times he dodged', 'n': 5, 'closer': {},
      'clips': [clip(f't{i}', 'vid1', 100 + 10 * i, 106 + 10 * i) for i in range(5)],
      'moments': [{'clip': f't{i}', 'rank': 5 - i, 'label': 'x', 'words': []} for i in range(5)], 'predictedDuration': 40.0}
# Top N is judged on the whole video: at least half the chosen moments must show the person; a moment where the camera
# stays on whoever the roast is aimed at is kept (live 2026-11-08: Hell's Kitchen compilations hold on the contestant while
# Ramsay roasts them, so a per-moment rule failed run after run)
port, out, _, _ = prb(tn, {'t1': 'other'})
p = out['plan']
assert port == 'next' and p['n'] == 5 and [(m['clip'], m['rank']) for m in p['moments']] == [('t0', 5), ('t1', 4), ('t2', 3), ('t3', 2), ('t4', 1)], p
assert prb(tn, {'t1': 'other', 't2': 'other'})[1]['plan']['n'] == 5                # 3 of 5 show him
assert prb(tn, {'t1': 'other', 't2': 'other', 't3': 'other'})[0] == 'invalid'     # 2 of 5: not his video
# speech formats keep a moment when 2 of its 3 windows show the person: a roast cuts to the contestant while he talks (live
# 2026-11-08, Gordon Ramsay: real roasts failed the all-windows rule); one window is not enough
port, out, _, _ = prb(tn, {'t1': (2, 'other')})
assert port == 'next' and out['plan']['n'] == 5, out['agentErrors']
port, out, _, _ = prb(tn, {'t1': (1, 'other'), 't2': (2, 'other')})
assert port == 'next' and out['plan']['n'] == 5
assert prb(tn, {'t1': 'other'})[1]['plan']['n'] == 5                                        # kept: 4 of 5 show him
_k = dict(KINDS); port, out, _, _ = prb(tn, {'t1': (0, 'other')}); assert out['plan']['n'] == 5
# Top N keeps a moment where the person shows in 1 of its 3 windows: a roast stays on its target while they talk
# (live 2026-11-08: Kitchen Nightmares shutdowns, Ramsay off camera in 2 windows); tribute still needs all 3
assert prb(tn, {'t1': [(0, 'other'), (2, 'other')]})[1]['plan']['n'] == 5
assert 'm1' not in [m['clip'] for m in prb(tplan(), {'m1': (1, 'other')})[1]['plan']['moments']]
# two passes: the photo finds the clear frames, their mean (the footage) judges every window (live 2026-11-08: Gordon
# Ramsay's Wikidata photo matched 19 of 96 probe faces, the footage reference 32)
port, out, _, _ = prb(tn, {'t0': 'footage', 't2': 'footage', 't3': 'footage', 't4': 'footage', 't1': 'side'})
assert port == 'next' and out['plan']['n'] == 5, out['agentErrors']
# spares: verify passes every verified moment beyond the best 5 as plan.spares; the probe keeps the first 5 (agent's
# order) that show the person, so off-camera moments need no agent round trip (live 2026-11-08: Hell's Kitchen clips often
# stay on the contestant; two retries ran out)
t7 = copy.deepcopy(TOPN); t7['moments'] = [moment(10 + i) for i in range(7)]   # 7 distinct verified moments
port, out, _ = verify(job('topn', t7))
assert port == 'next' and out['plan']['n'] == 5 and len(out['plan']['spares']) == 2 and len(out['plan']['clips']) == 7, out['plan'].get('spares')
check_story(out)
sp = out['plan']
best = [m['clip'] for m in sorted(sp['moments'] + sp['spares'], key=lambda m: m['rank'])]   # agent's order, best first
port, out, _, _ = prb(sp, {best[0]: 'other', best[2]: 'other', best[3]: 'other'})   # top 5 would show him in only 2
p = out['plan']
assert port == 'next' and p['n'] == 5 and 'spares' not in p and len(p['clips']) == 5 and len(out['story']['clips']) == 5, (port, out['agentErrors'])
kept = [m['clip'] for m in p['moments']]
assert [m['rank'] for m in p['moments']] == [5, 4, 3, 2, 1] and best[3] not in kept and best[5] in kept and best[0] in kept, kept   # the weakest off-camera one makes way for a spare
# no reference image: the biggest face cluster across the probes is the person; a clip with only other faces fails
port, out, _, r = prb(tplan(), {'m3': 'other'}, ref=False)
assert port == 'next' and 'm3' not in [m['clip'] for m in out['plan']['moments']] and np.allclose(np.load(r / 'identity.npy'), VEC['target'])
KINDS_BACKUP = sm._embed, sm._frame_embeds; sm._embed = lambda img, md: None; sm._frame_embeds = lambda img, md: []   # no face anywhere
assert prb(tplan(), ref=False)[0] == 'invalid'
sm._embed, sm._frame_embeds = KINDS_BACKUP
# the person is often the smaller face behind someone in the foreground: every face counts, not only the largest
# (live 2026-11-08: a Ramsay frame had 0.12 for the contestant in front and 0.63 for him behind)
assert prb(tplan(), {'m2': 'pair'})[1]['plan']['moments'][2]['clip'] == 'm2'
# casefile: only archive clips are probed; a failed one leaves the script with a photo instead
cf = {'format': 'casefile', 'person': {'name': 'Callum Turner'}, 'clips': [clip('a0', 'vid1', 100, 103)],
      'script': [{'text': 't', 'spoken': 't', 'visual': {'kind': 'clip', 'clip': 'a0'}}, {'text': 'u', 'spoken': 'u', 'visual': {'kind': 'timeline', 'label': 'X'}}]}
port, out, _, _ = prb(cf, {'a0': 'other'})
assert port == 'next' and out['plan']['clips'] == [] and out['story']['clips'] == [] and out['plan']['script'][0]['visual'] == {'kind': 'photo', 'query': 'Callum Turner', 'candidates': []}
assert out['download'] == 'no'   # media-fetch refuses an empty clip list: the graph skips it (onlyWhen download=yes)
port, out, _, _ = prb(dict(cf, clips=[], script=cf['script'][1:]))
assert port == 'next' and DL == [] and out['identity'] == {'file': 'identity.npy'}              # nothing to probe, reference still saved for the gate


# ---------------- assets
GOT = []


def stub_dl(url, dest):
    if 'bad' in url:
        raise OSError('404')
    Path(dest).parent.mkdir(parents=True, exist_ok=True); Path(dest).write_bytes(b'x'); GOT.append(url)


def stub_shot(url, dest, highlight=None):
    if 'bad' in url:
        return None
    Path(dest).parent.mkdir(parents=True, exist_ok=True); Path(dest).write_bytes(b'png'); return str(dest)


sm._download, sm._screenshot = stub_dl, stub_shot
vid = lambda n: {'provider': 'pexels', 'url': f'https://x/{n}.mp4', 'kind': 'video', 'w': 1080, 'h': 1920, 'credit': 'P', 'licence': 'Pexels License', 'page': f'https://p/{n}'}
img = lambda n: {'provider': 'commons', 'url': f'https://x/{n}.PNG', 'kind': 'image', 'credit': 'A', 'licence': 'CC BY 4.0', 'page': f'https://c/{n}'}


def asr(plan):
    r = Path(tempfile.mkdtemp()); GOT.clear()
    return sm.assets(pj(plan), {}, r, Path(tempfile.mkdtemp())) + (r,)


assert asr({'format': 'tribute'})[:2] == ('next', {'assets': {}, 'agentErrors': [], 'plan': {'format': 'tribute'}})
eb = lambda i, cands: {'query': f'q{i}', 'line': i % 3, 'candidates': cands}
ep = {'format': 'edit', 'broll': [eb(i, [vid(f'b{i}')]) for i in range(6)], 'tail': [{'query': f't{i}', 'candidates': [img(f't{i}')]} for i in range(6)]}
ep['broll'][1]['candidates'] = [vid('bad1'), vid('ok1')]                      # failed candidate: the next one is used
ep['broll'][2]['candidates'] = [vid('bad2')]                                  # no candidate works: this b-roll is left out
port, out, log, r = asr(ep)
a = out['assets']
assert port == 'next' and len(a['broll']) == 5 and len(a['tail']) == 6, out
assert a['broll'][1] == {'line': 1, 'file': 'assets/broll/1.mp4', 'kind': 'video', 'credit': 'P', 'licence': 'Pexels License', 'page': 'https://p/ok1'}, a['broll'][1]
# file paths are relative to the run folder, like every other file key (the renderers join them to run/)
assert [b['file'] for b in a['broll']] == ['assets/broll/0.mp4', 'assets/broll/1.mp4', 'assets/broll/3.mp4', 'assets/broll/4.mp4', 'assets/broll/5.mp4'] and a['tail'][0]['file'] == 'assets/tail/0.png'
assert all((r / x['file']).exists() for x in a['broll'] + a['tail']) and 'https://x/bad1.mp4' not in GOT
for i in (0, 3, 4): ep['broll'][i]['candidates'] = [vid(f'bad{i}')]            # 5 of 12 failed: below 70 %
port, out, log, _ = asr(ep)
assert port == 'missing' and out['rejectedPeople'] == ['Q0', 'Q1'] and len(out['agentErrors']) == 1 and 'assets' in out['agentErrors'][0], out
# casefile: screenshots keyed by url, photos with credits, empty candidates searched again
sm._commons_images = lambda q, n=6: [img('found')]
sh = lambda u: {'kind': 'screenshot', 'outlet': 'BBC', 'url': u, 'highlight': 'a b c d'}
cp = {'format': 'casefile', 'script': [{'visual': v} for v in [
    sh('https://a/1'), {'kind': 'photo', 'query': 'p1', 'candidates': [img('bad'), img('g1')]}, sh('https://a/2'), {'kind': 'timeline', 'label': 'X'},
    {'kind': 'photo', 'query': 'p2', 'candidates': []}, sh('https://a/bad3'), {'kind': 'photo', 'query': 'p3', 'candidates': [img('g3')]}]]}
port, out, _, r = asr(cp)
a = out['assets']
assert port == 'next' and a['screenshots'] == {'https://a/1#a b c d': 'assets/shots/0.png', 'https://a/2#a b c d': 'assets/shots/1.png'}, out
assert a['photos'][0] == {'query': 'p1', 'file': 'assets/photos/0.png', 'credit': 'A', 'licence': 'CC BY 4.0', 'page': 'https://c/g1'}, a['photos'][0]
assert [p['page'] for p in a['photos']] == ['https://c/g1', 'https://c/found', 'https://c/g3'] and (r / 'assets' / 'shots' / '1.png').read_bytes() == b'png'
cp['script'][2]['visual']['url'] = 'https://a/bad2'                              # 2 of 3 screenshots failed: below the 2 needed
port, out, _, _ = asr(cp)
assert port == 'missing' and 'screenshot' in out['agentErrors'][0] and out['rejectedPeople'] == ['Q0', 'Q1'], out
# once the 2 needed can no longer be reached, the rest are not tried (live 2026-11-10: 274 s on hopeless cloud screenshots)
cp['script'][0]['visual']['url'] = 'https://a/bad1'; shot_calls = []
sm._screenshot = lambda u, d, h=None: shot_calls.append(u) or stub_shot(u, d, h)
port, out, _, _ = asr(cp)
assert port == 'missing' and shot_calls == ['https://a/bad1', 'https://a/bad2'], shot_calls
sm._screenshot = stub_shot; cp['script'][0]['visual']['url'] = 'https://a/1'
cp['script'][2]['visual']['url'] = 'https://a/2'; sm._commons_images = lambda q, n=6: []
cp['script'][4]['visual']['candidates'] = []; cp['script'][6]['visual']['candidates'] = [img('bad')]   # only 1 photo left
port, out, _, _ = asr(cp)
assert port == 'missing' and 'photo' in out['agentErrors'][0], out

# two highlights in one article are two screenshots (live 2026-11-10: the second CBS highlight showed the first one's image)
cp1 = {'format': 'casefile', 'script': [{'visual': v} for v in [sh('https://a/1'), dict(sh('https://a/1'), highlight='e f g h'),
       {'kind': 'photo', 'query': 'p1', 'candidates': [img('g1')]}, {'kind': 'photo', 'query': 'p3', 'candidates': [img('g3')]}]]}
port, out, _, r = asr(cp1)
assert port == 'next' and out['assets']['screenshots'] == {'https://a/1#a b c d': 'assets/shots/0.png', 'https://a/1#e f g h': 'assets/shots/1.png'}, out
# case-file photos: every clearly visible face must be the person (live 2026-11-07: a red-carpet photo of Brand beside a young
# woman ran under "the jury convicted him of grabbing a woman's breasts"; complainants have lifelong anonymity in the UK)
FACES = {'https://x/stranger.PNG': [(0.9, 0.2), (0.1, 0.2)], 'https://x/alone.PNG': [(0.8, 0.2)], 'https://x/building.PNG': []}
real_pf = sm._photo_faces
sm._photo_faces = lambda path, ref, models: [(m if ref is not None else 0.0, w) for m, w in FACES.get(GOT[-1], [(0.9, 0.2)])]   # as the real one
sm._commons_images = lambda q, n=6: []
cp2 = {'format': 'casefile', 'script': [{'visual': v} for v in [sh('https://a/1'), sh('https://a/2'),
       {'kind': 'photo', 'query': 'p1', 'candidates': [img('stranger'), img('alone')]},
       {'kind': 'photo', 'query': 'p2', 'candidates': [img('building')]}]]}
r = Path(tempfile.mkdtemp()); GOT.clear(); np.save(r / 'identity.npy', np.ones(3))
port, out, _ = sm.assets(pj(cp2, identity={'file': 'identity.npy'}), {}, r, Path(tempfile.mkdtemp()))
assert port == 'next' and [p['page'] for p in out['assets']['photos']] == ['https://c/alone', 'https://c/building'], out
# without an identity reference only photos with no faces can be trusted
r = Path(tempfile.mkdtemp()); GOT.clear()
port, out, _ = sm.assets(pj(cp2), {}, r, Path(tempfile.mkdtemp()))
assert port == 'missing' and 'photo' in out['agentErrors'][0], out
sm._photo_faces = real_pf
# photos never repeat a picture, and leftover candidates top the pool up to POOL_PHOTOS distinct photos (live 2026-11-07: two
# "Russell Brand" visuals both downloaded the same top result and the case file showed 2 pictures in 10 shots)
sm._photo_faces = lambda path, ref, models: []
_real_pp = sm._person_photos
sm._person_photos = lambda job, run, state, base: [{'file': f'assets/person/{i}.jpg', 'kind': 'image', 'credit': 'C', 'licence': 'CC BY 4.0', 'page': f'https://c/person{i}'} for i in range(4)]
cp3 = {'format': 'casefile', 'script': [{'visual': v} for v in [sh('https://a/1'), sh('https://a/2'),
       {'kind': 'photo', 'query': 'Brand', 'candidates': [img('b1'), img('b2'), img('b3')]},
       {'kind': 'photo', 'query': 'Brand', 'candidates': [img('b1'), img('b2'), img('b3')]},
       {'kind': 'photo', 'query': 'court', 'candidates': [img('c1'), img('c2'), img('c3'), img('c4'), img('c5')]}]]}
r = Path(tempfile.mkdtemp()); GOT.clear()
port, out, _ = sm.assets(pj(cp3), {}, r, Path(tempfile.mkdtemp()))
pages = [p['page'] for p in out['assets']['photos']]
assert port == 'next' and pages[:3] == ['https://c/b1', 'https://c/b2', 'https://c/c1'], pages     # one per visual, no repeat
# the top-up takes at most 2 a query, then face-checked photos of the person (live 2026-11-10: 3 New Scotland Yard photos
# of 6, the court shown 3 times and Brand twice)
assert pages == ['https://c/b1', 'https://c/b2', 'https://c/c1', 'https://c/c2', 'https://c/person0', 'https://c/person1'], pages
sm._person_photos = _real_pp
# person photos search 30 Commons results, not 6 (live 2026-11-12: 6 gave one Hoffman photo, 30 give 21 big enough), and when
# fewer than 3 pass the face check Bing images top them up, behind the same check
_ci, _bi, _pf, _ff = sm._commons_images, sm._bing_images, sm._photo_faces, sm._fetch_first
asked, picked = [], []
sm._commons_images = lambda q, n=6: asked.append(n) or [dict(img('Dustin_Hoffman_1968'), title='Dustin Hoffman 1968')]
sm._bing_images = lambda q: [{'provider': 'bing', 'url': f'https://b/{i}.jpg', 'kind': 'image', 'credit': 'variety.com', 'licence': '',
                              'title': 'x', 'page': f'https://variety.com/{i}'} for i in range(6)]
sm._fetch_first = lambda base, stem, cands, ok=None: picked.append(cands[0]['url']) or {'file': f'assets/{stem}.jpg', 'page': cands[0]['page']}
r = Path(tempfile.mkdtemp()); np.save(r / 'identity.npy', np.ones(3))
got = sm._person_photos({'person': {'name': 'Dustin Hoffman'}, 'identity': {'file': 'identity.npy'}}, r, Path(tempfile.mkdtemp()), r / 'assets')
assert asked == [30] and [g['page'] for g in got] == ['https://c/Dustin_Hoffman_1968', 'https://variety.com/0', 'https://variety.com/1',
                                                    'https://variety.com/2'], got
sm._commons_images, sm._bing_images, sm._fetch_first = _ci, _bi, _ff
# Bing's results page carries each image as JSON in an m="..." attribute: full image (murl), its page (purl), title (t)
BING = ('<a class="iusc" m="{&quot;murl&quot;:&quot;https://img.variety.com/a.jpg&quot;,&quot;purl&quot;:&quot;https://variety.com/2026/a/&quot;,'
        '&quot;t&quot;:&quot;Dustin Hoffman at the Oscars&quot;}" href="#"></a><a class="iusc" m="{&quot;murl&quot;:&quot;https://x.org/b.png&quot;,'
        '&quot;purl&quot;:&quot;https://x.org/p&quot;,&quot;t&quot;:&quot;B&quot;}"></a>')
_gt = sm.net.get_text
sm.net.get_text = lambda url, timeout=30: BING
bi = _real_bing('Dustin Hoffman')
sm.net.get_text = _gt
assert bi == [{'provider': 'bing', 'url': 'https://img.variety.com/a.jpg', 'kind': 'image', 'credit': 'variety.com', 'licence': '',
               'title': 'Dustin Hoffman at the Oscars', 'page': 'https://variety.com/2026/a/'},
              {'provider': 'bing', 'url': 'https://x.org/b.png', 'kind': 'image', 'credit': 'x.org', 'licence': '', 'title': 'B', 'page': 'https://x.org/p'}], bi
# a photo's file name must carry most of its query's key words (live 2026-11-07: "Southwark Crown Court" returned the Shard
# and HMS Belfast skyline, which ran under "found guilty of rape and sexual assault in")
cm = lambda name: {'provider': 'commons', 'url': f'https://x/{name}.jpg', 'kind': 'image', 'credit': 'A', 'licence': 'CC BY 4.0',
                   'page': f'https://commons.wikimedia.org/wiki/File:{name}.jpg'}
assert not sm._relevant(cm('HMS_Belfast_stern'), 'Southwark Crown Court')
assert sm._relevant(cm('Southwark_Crown_Court_in_London_%2814089475185%29'), 'Southwark Crown Court')
assert sm._relevant(cm('Russell_Brand_2008'), 'Russell Brand comedian')            # 2 of 3 key words
assert not sm._relevant(cm('Shard_London_Bridge'), 'Russell Brand comedian')
assert sm._relevant(cm('New_Scotland_Yard_sign'), 'New Scotland Yard')
sm._photo_faces = lambda path, ref, models: []
cp4 = {'format': 'casefile', 'script': [{'visual': v} for v in [sh('https://a/1'), sh('https://a/2'),
       {'kind': 'photo', 'query': 'Southwark Crown Court', 'candidates': [cm('HMS_Belfast_stern'), cm('Southwark_Crown_Court_entrance')]},
       {'kind': 'photo', 'query': 'New Scotland Yard', 'candidates': [cm('New_Scotland_Yard')]}]]}
r = Path(tempfile.mkdtemp()); GOT.clear()
port, out, _ = sm.assets(pj(cp4), {}, r, Path(tempfile.mkdtemp()))
assert port == 'next' and [p['page'].rsplit(':', 1)[1] for p in out['assets']['photos']] == ['Southwark_Crown_Court_entrance.jpg', 'New_Scotland_Yard.jpg'], out
assert 'https://x/HMS_Belfast_stern.jpg' not in GOT                                  # irrelevant candidates are not even downloaded
# a photo searched by the person's name must show their face clearly (live 2026-11-07: "Russell Brand comedian" returned a
# stage shot with only his legs in yellow trousers, shown 3 times; even the camera pan never showed him)
FACES = {'https://x/legs.PNG': [], 'https://x/Callum_Turner_tiny.PNG': [(0.8, 0.08)], 'https://x/clear.PNG': [(0.8, 0.2)], 'https://x/hall.PNG': []}
sm._photo_faces = lambda path, ref, models: FACES.get(GOT[-1], [])
cp5 = {'format': 'casefile', 'script': [{'visual': v} for v in [sh('https://a/1'), sh('https://a/2'),
       {'kind': 'photo', 'query': 'Callum Turner red carpet', 'candidates': [img('legs'), img('tiny'), img('clear')]},
       {'kind': 'photo', 'query': 'Royal Albert Hall', 'candidates': [img('hall')]}]]}
r = Path(tempfile.mkdtemp()); GOT.clear(); np.save(r / 'identity.npy', np.ones(3))
port, out, _ = sm.assets(pj(cp5, identity={'file': 'identity.npy'}), {}, r, Path(tempfile.mkdtemp()))
assert port == 'next' and [p['page'] for p in out['assets']['photos']] == ['https://c/clear', 'https://c/hall'], out   # a place needs no face
sm._photo_faces = real_pf


# caption words are re-timed with whisper on every downloaded clip, through the clip's offset (job.clips[i] is plan.clips[i])
CALLS = []
def stub_retime(words, audio, offset):
    CALLS.append((audio, offset)); return [dict(w, s=round(w['s'] + 0.5, 3), e=round(w['e'] + 0.5, 3)) for w in words]
real_retime, sm.align.retime = sm.align.retime, stub_retime
ws = lambda a: [{'w': 'x', 's': a, 'e': a + 1}]
jc = [{'role': 'moment', 'file': f'clip-{i}.mp4', 'offset': 10.0 * i, 'duration': 5.0, 'sourceId': 's'} for i in range(3)]
for fmt, plan in {
    'edit': {'format': 'edit', 'clips': [{'key': f'l{i}'} for i in range(3)], 'broll': [], 'tail': [], 'lines': [{'clip': f'l{i}', 'words': ws(10 * i)} for i in range(3)]},
    'topn': {'format': 'topn', 'clips': [{'key': f't{i}'} for i in range(3)], 'moments': [{'clip': f't{i}', 'words': ws(10 * i)} for i in range(3)]},
    'tribute': {'format': 'tribute', 'clips': [{'key': 'spine0'}, {'key': 'm0'}, {'key': 'spine1'}],
                'spine': [{'clip': 'spine0', 'words': ws(0)}, {'clip': 'spine1', 'words': ws(20)}], 'moments': [{'clip': 'm0'}]}}.items():
    CALLS.clear(); r = Path(tempfile.mkdtemp())
    port, out, _ = sm.assets(pj(plan, clips=jc), {}, r, Path(tempfile.mkdtemp()))
    rows = out['plan']['lines' if fmt == 'edit' else 'moments' if fmt == 'topn' else 'spine']
    assert port == 'next' and [w['words'][0]['s'] for w in rows] == ([0.5, 10.5, 20.5] if fmt != 'tribute' else [0.5, 20.5]), (fmt, out)
    assert CALLS == [(str(r / f'clip-{i}.mp4'), 10.0 * i) for i in range(3) if fmt != 'tribute' or i != 1], CALLS
    assert plan['lines' if fmt == 'edit' else 'moments' if fmt == 'topn' else 'spine'][-1]['words'][0]['s'] in (20, 0), 'input plan untouched'
# a clip the caption words do not belong to is left alone: no clips downloaded, no calls
CALLS.clear(); assert sm.assets(pj(plan, clips=[]), {}, Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp()))[1]['plan'] == plan and not CALLS
sm.align.retime = real_retime

# re-timed words move the clip's cut points to the real words (LEAD before the first, TAIL after the last), inside the downloaded section
sm.align.retime = stub_retime
jc2 = [{'role': 'moment', 'file': f'c{i}.mp4', 'offset': 100.0, 'duration': 5.0, 'sourceId': 's'} for i in range(3)]
pl = {'format': 'edit', 'broll': [], 'tail': [], 'clips': [{'key': f'l{i}', 'start': 100.9, 'end': 102.0, 'source': {'id': 's'}} for i in range(3)],
      'lines': [{'clip': 'l0', 'words': ws(101)}, {'clip': 'l1', 'words': ws(104)}, {'clip': 'l2', 'words': [dict(w, timed=True) for w in ws(101)]}]}
CALLS.clear()
out = sm.assets(pj(pl, clips=jc2), {}, Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp()))[1]['plan']
c = out['clips']
assert (c[0]['start'], c[0]['end']) == (round(101.5 - sm.LEAD, 3), round(102.5 + sm.TAIL, 3)), c[0]          # moved to the words
assert (c[1]['start'], c[1]['end']) == (round(104.5 - sm.LEAD, 3), 105.0), c[1]                                  # end clamped to the section
assert (c[2]['start'], c[2]['end']) == (100.9, 102.0) and len(CALLS) == 2, (c[2], CALLS)                         # already timed: untouched
assert pl['clips'][0]['end'] == 102.0                                                                            # input plan untouched
sm.align.retime = real_retime

# edit: 2-4 photos of the person, only with their face (score >= MATCH_PHOTO, face >= PERSON_FACE, no other noticeable face)
PF = {'https://x/Callum_Turner_crowd.PNG': [(0.9, 0.2), (0.1, 0.2)], 'https://x/Callum_Turner_tiny.PNG': [(0.9, 0.05)], 'https://x/Callum_Turner_no.PNG': []}
sm._photo_faces = lambda path, ref, models: PF[GOT[-1]]
QS = []
cm2 = lambda n: {**img(n), 'title': f'File:{n}.jpg', 'page': f'https://commons.wikimedia.org/wiki/File:{n}.jpg', 'credit': f'by {n}'}
sm._commons_images = lambda q, n=6: QS.append(q) or [cm2(n) for n in ('Callum_Turner_' + k for k in 'crowd tiny no a b c d e'.split())]
PF.update({f'https://x/Callum_Turner_{k}.PNG': [(0.8, 0.2)] for k in 'abcde'})
ep2 = {'format': 'edit', 'broll': [], 'tail': []}
r = Path(tempfile.mkdtemp()); GOT.clear(); np.save(r / 'identity.npy', np.ones(3))
port, out, _ = sm.assets(pj(ep2, identity={'file': 'identity.npy'}), {}, r, Path(tempfile.mkdtemp()))
pp = out['assets']['person']
assert port == 'next' and QS == ['Callum Turner'] and len(pp) == 4, (out, QS)                  # capped at 4; crowd, tiny and no-face photos refused
assert pp[0] == {'file': 'assets/person/0.png', 'kind': 'image', 'credit': 'by Callum_Turner_a', 'licence': 'CC BY 4.0',
                 'page': 'https://commons.wikimedia.org/wiki/File:Callum_Turner_a.jpg'} and (r / pp[0]['file']).exists(), pp
# nothing passes (or no identity reference): an empty list, and the edit still goes on
r = Path(tempfile.mkdtemp()); GOT.clear()
assert sm.assets(pj(ep2), {}, r, Path(tempfile.mkdtemp()))[1]['assets']['person'] == []
sm._commons_images = lambda q, n=6: (_ for _ in ()).throw(OSError('offline'))
assert sm.assets(pj(ep2), {}, r, Path(tempfile.mkdtemp()))[1]['assets']['person'] == []
sm._photo_faces, sm._commons_images = real_pf, lambda q: []

# ---------------- footage: real clips of the person's work from YouTube, face-checked, cropped 9:16 (owner 2026-11-13: the
# Graduate edit had stock shots of a cinema and the Hollywood sign, nothing from the film; edit and case file)
import subprocess
_srch, _frames, _sok, _vert = sm.ytsrc.search, sm.ytsrc.probe_frames, sm._shot_ok, sm._vertical
# a full special (2 h) is a good source; a title without the surname is someone else's video (live 2026-11-13: "women winning
# 99.9% of all fights" came up for a Dane Cook stand-up search); a video that gives no shot hands over to the next result
FS = {'graduate scene': [{'id': 'other1', 'title': 'Funny fails', 'channel': 'C', 'duration': 300}, {'id': 'huge1', 'title': 'Turner marathon', 'duration': 4 * 3600},
                         {'id': 'g1', 'title': 'The Graduate - Callum Turner', 'channel': 'Movieclips', 'duration': 7200}],
      'rain man scene': [{'id': 'live1', 'title': 'Turner live', 'duration': 200, 'live_status': 'is_live'}, {'id': 'none1', 'title': 'Turner far away', 'channel': 'R', 'duration': 120},
                         {'id': 'r1', 'title': 'x', 'channel': 'Callum Turner', 'duration': 120}],
      'tootsie scene': [{'id': 'g1', 'title': 'The Graduate - Callum Turner', 'channel': 'Movieclips', 'duration': 7200}]}   # g1 already used
sm.ytsrc.search = lambda q, n=15: FS.get(q, [])
WINS, OK = [], []
def fake_frames(vid, url, wins, out_dir, height=240):
    WINS.append((vid, wins, height)); Path(out_dir).mkdir(parents=True, exist_ok=True)
    fs = [Path(out_dir) / f'{vid}_{i}.mp4' for i in range(len(wins))]
    for f in fs: f.write_bytes(b'v')
    return [str(f) for f in fs]
sm.ytsrc.probe_frames = fake_frames
sm._shot_ok = lambda path, ref, models, strict: OK.append(strict) or not path.endswith('_1.mp4') and 'none1' not in path   # window 2 misses them
sm._vertical = lambda src, dst, ref, models: (Path(dst).parent.mkdir(parents=True, exist_ok=True), Path(dst).write_bytes(b'v'))
FQ = ['graduate scene', 'rain man scene', 'tootsie scene']
r = Path(tempfile.mkdtemp()); np.save(r / 'identity.npy', np.ones(3))
fj = lambda fmt, q=FQ: pj({'format': fmt, 'footage': q}, identity={'file': 'identity.npy'})
ft = sm._footage(fj('edit'), r, Path(tempfile.mkdtemp()), r / 'assets')
assert [w[0] for w in WINS] == ['g1', 'none1', 'r1'] and all(h == 720 and len(ws) == 8 and abs(ws[0][1] - ws[0][0] - 3.0) < 1e-6 for _, ws, h in WINS), WINS
assert len(ft) == 8 and ft[0] == {'file': 'assets/footage/0.mp4', 'kind': 'video', 'credit': 'Footage: https://www.youtube.com/watch?v=g1 (Movieclips)',
                                  'page': 'https://www.youtube.com/watch?v=g1'} and (r / ft[7]['file']).exists() and OK and not any(OK), ft   # 8 windows, 4 a video
OK.clear()
assert len(sm._footage(fj('casefile'), r, Path(tempfile.mkdtemp()), r / 'assets', strict=True)) == 4 and OK and all(OK) and all(len(w[1]) == 4 for w in WINS[3:])   # strict keeps 4 windows, 2 a video; every face must be them
assert sm._footage(fj('edit', []), r, Path(tempfile.mkdtemp()), r / 'assets') == []                     # no queries
assert sm._footage(fj('edit'), Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp()), r / 'assets') == []   # no identity reference
# the assets stage hands the footage to both renders
real_footage, sm._footage = sm._footage, lambda job, run, state, base, strict=False: [{'file': 'F', 'strict': strict}]
sm._photo_faces = lambda path, ref, models: []
assert sm.assets(pj({'format': 'edit', 'broll': [], 'tail': []}), {}, r, Path(tempfile.mkdtemp()))[1]['assets']['footage'] == [{'file': 'F', 'strict': False, 'who': PERSON['name']}]
r2 = Path(tempfile.mkdtemp()); GOT.clear(); np.save(r2 / 'identity.npy', np.ones(3))
port, out, _ = sm.assets(pj(cp2, identity={'file': 'identity.npy'}), {}, r2, Path(tempfile.mkdtemp()))
assert port == 'next' and out['assets']['footage'] == [{'file': 'F', 'strict': True}], out
sm._photo_faces = real_pf
sm.ytsrc.search, sm.ytsrc.probe_frames, sm._shot_ok, sm._vertical = _srch, _frames, _sok, _vert
sm._footage = real_footage
# _shot_ok: the person's face, big enough, in both sampled frames; a case file also refuses anyone else's face
v = r / 'shot.mp4'
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=s=640x360:d=3', str(v)], check=True)
def faces_seq(*frames):
    it = iter(frames); sm._photo_faces = lambda path, ref, models: next(it)
faces_seq([(0.5, 0.1), (0.1, 0.05)], [(0.6, 0.1)], [(0.6, 0.1)]); assert sm._shot_ok(str(v), np.ones(3), r, False)
faces_seq([(0.5, 0.2), (0.1, 0.15)], [(0.6, 0.2)]); assert not sm._shot_ok(str(v), np.ones(3), r, True)   # a co-star's face
faces_seq([(0.5, 0.2)], [(0.2, 0.3)]); assert not sm._shot_ok(str(v), np.ones(3), r, True)               # gone by the second sample
faces_seq([(0.5, 0.05)], [(0.6, 0.05)]); assert not sm._shot_ok(str(v), np.ones(3), r, True)              # strict: too small to read
# non-strict: a matching face of 0.035-0.17 in 2 of 3 frames (stage footage has small, turned faces; wider is a close-up)
faces_seq([], [(0.5, 0.05)], [(0.5, 0.05)]); assert sm._shot_ok(str(v), np.ones(3), r, False)               # 2 of 3 passes
faces_seq([], [(0.5, 0.05)], []); assert not sm._shot_ok(str(v), np.ones(3), r, False)                      # 1 of 3 is a false match
faces_seq([(0.5, 0.3)], [(0.5, 0.3)], [(0.5, 0.3)]); assert not sm._shot_ok(str(v), np.ones(3), r, False)   # macro close-up
faces_seq([(0.5, 0.1), (0.1, 0.05)], [(0.5, 0.1)], [(0.5, 0.1), (0.1, 0.12)]); assert sm._shot_ok(str(v), np.ones(3), r, False)  # co-star bigger in 1 frame only
faces_seq([(0.5, 0.06), (0.1, 0.12)], [(0.5, 0.1)], [(0.5, 0.06), (0.1, 0.1)]); assert not sm._shot_ok(str(v), np.ones(3), r, False)  # co-star bigger in 2
faces_seq([(0.5, 0.06)], [(0.1, 0.1)], [(0.5, 0.06), (0.1, 0.1)]); assert not sm._shot_ok(str(v), np.ones(3), r, False)  # co-star dominates 2 frames
faces_seq([], [(0.5, 0.05)], []); assert not sm._shot_ok(str(v), np.ones(3), r, True)                       # strict needs both ends
faces_seq([(0.1, 0.2)], [(0.5, 0.02)], [(0.2, 0.2)]); assert not sm._shot_ok(str(v), np.ones(3), r, False)  # wrong face / too small
sm._photo_faces = real_pf

# others: people the story is about get footage too (their own surname gate, 4 shots at most, tagged with who)
FS.update({'billie scene': [{'id': 'b1', 'title': 'Billie Eilish Met Gala', 'channel': 'X', 'duration': 600}, {'id': 'sw', 'title': 'Callum Turner', 'channel': 'X', 'duration': 600}]})
sm.ytsrc.search = lambda q, n=15: FS.get(q, [])
sm.ytsrc.probe_frames = fake_frames
sm._shot_ok = lambda path, ref, models, strict: True
sm._vertical = lambda src, dst, ref, models: (Path(dst).parent.mkdir(parents=True, exist_ok=True), Path(dst).write_bytes(b'v'))
WINS.clear()
oj = lambda **kw: pj({'format': 'edit', 'broll': [], 'tail': [], 'footage': ['graduate scene'], **kw}, identity={'file': 'identity.npy'})
real_or, REFS = sm._other_ref, []
sm._other_ref = lambda name, state, base: REFS.append(name) or (np.ones(3) if name == 'Billie Eilish' else None)
res = sm.assets(oj(others=[{'name': 'Billie Eilish', 'footage': ['billie scene']}, {'name': 'No Photo', 'footage': ['billie scene']}]), {}, r, Path(tempfile.mkdtemp()))[1]['assets']['footage']
who = [x['who'] for x in res]
assert REFS == ['Billie Eilish', 'No Photo'] and who == [PERSON['name']] * who.count(PERSON['name']) + ['Billie Eilish'] * 4, who
assert who[0] == PERSON['name'] and {w[0] for w in WINS} == {'g1', 'b1'}, WINS   # Turner's video is not Eilish's: surname gate
assert len({x['file'] for x in res}) == len(res), res   # no file clobbered between people
sm._other_ref = real_or
sm.ytsrc.search, sm.ytsrc.probe_frames, sm._shot_ok, sm._vertical = _srch, _frames, _sok, _vert

# verify keeps up to 2 others with up to 2 searches; schema allows the same
others = [{'name': 'Billie Eilish', 'footage': ['Billie Eilish Met Gala 2024', ' ', 'b', 'c']}, {'name': 'A B', 'footage': ['x']}, {'name': 'C D', 'footage': ['y']}, {'name': '', 'footage': ['z']}]
assert verify(job('edit', dict(EDIT, others=others)))[1]['plan']['others'] == [{'name': 'Billie Eilish', 'footage': ['Billie Eilish Met Gala 2024', 'b']}, {'name': 'A B', 'footage': ['x']}]
assert verify(job('edit', EDIT))[1]['plan']['others'] == []
import jsonschema
SCH = json.loads((Path(__file__).parent / 'briefs/edit.schema.json').read_text())
jsonschema.validate(dict(EDIT, others=[{'name': 'A B', 'footage': ['x', 'y']}, others[1]]), SCH); jsonschema.validate(EDIT, SCH)
for bad_others in (others[1:4], [{'name': 'A', 'footage': ['x'], 'extra': 1}], [{'name': 'A', 'footage': ['x', 'y', 'z']}]):
    try: jsonschema.validate(dict(EDIT, others=bad_others), SCH); raise SystemExit('schema accepted ' + repr(bad_others))
    except jsonschema.ValidationError: pass

# ---------------- brollpick
def bp(picks=None, fmt='edit', n=6, **kw):
    plan = {'format': fmt, 'broll': [{'query': f'b{i}', 'line': 0, 'candidates': [{'page': f'p{i}{k}'} for k in range(4)]} for i in range(n)],
            'tail': [{'query': f't{i}', 'candidates': [{'page': f'q{i}{k}'} for k in range(4)]} for i in range(n)]}
    j = {'plan': plan, **kw}
    if picks is not None:
        j['brollPicks'] = {'picks': picks}
    return sm.brollpick(j, {}, Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp()))
# keeps only the picked candidates, in the agent's order; a query with no picks loses its candidates
port, out, _ = bp({**{f'b{i}': [2, 0] for i in range(6)}, **{f't{i}': [3] for i in range(5)}})
assert port == 'next', (port, out)
assert [c['page'] for c in out['plan']['broll'][0]['candidates']] == ['p02', 'p00'] and out['plan']['broll'][0]['line'] == 0
assert [c['page'] for c in out['plan']['tail'][0]['candidates']] == ['q03'] and out['plan']['tail'][5]['candidates'] == []
# bad indices (out of range, repeats, not ints) are ignored
assert [c['page'] for c in bp({**{f'b{i}': [9, 1, 1, '2', -1] for i in range(6)}, **{f't{i}': [0] for i in range(3)}})[1]['plan']['broll'][0]['candidates']] == ['p01']
# 70 %: 12 queries, 4 without picks is 66 % -> invalid naming them, 3 without is 75 % -> ok
port, out, _ = bp({f'b{i}': [0] for i in range(6)} | {f't{i}': [0] for i in range(2)})
assert port == 'invalid' and len(out['agentErrors']) == 1 and all(f'"t{i}"' in out['agentErrors'][0] for i in range(2, 6)) and '"b0"' not in out['agentErrors'][0], out
assert bp({f'b{i}': [0] for i in range(6)} | {f't{i}': [0] for i in range(3)})[0] == 'next'
# not edit, or no picks: next and nothing changes
assert bp({}, fmt='tribute') == ('next', {}, bp({}, fmt='tribute')[2])
assert bp(None)[:2] == ('next', {})

print('ok')
