# Offline tests for trending/stages_end.py (cut, gate, record). Run from trending/: python3 test_stages_end.py
import datetime as dt, json, subprocess, sys, tempfile, types
from pathlib import Path
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trending import stages_end as se

tmp = lambda: Path(tempfile.mkdtemp())
ff = lambda *a: subprocess.run(['ffmpeg', '-y', '-v', 'error', *map(str, a)], check=True)

# ---- cut: dispatch by plan.format
calls = []
def fake(job, cfg, run):
    calls.append((job, cfg, run))
    return {'short': {'file': 'short.mp4', 'duration': 30}, 'timeline': [{'start': 0, 'end': 30, 'kind': 'x', 'person': True}], 'credits': ['c'], 'extra': 1}
sys.modules['trending.formats.casefile'] = types.SimpleNamespace(render=fake)
sys.modules['trending.formats.edit'] = None   # no edit renderer: the import fails as if the file were missing
r = tmp()
job = {'plan': {'format': 'casefile'}}
st = tmp()
port, out, log = se.cut(job, {'voice': 'elevenlabs', 'elevenVoice': 'v1'}, r, st)
assert port == 'next' and set(out) == {'short', 'timeline', 'credits'} and out['short']['duration'] == 30, out
assert calls == [(job, {'voice': 'elevenlabs', 'elevenVoice': 'v1', 'models': str(st / 'models')}, r)], calls
for fmt in ('edit', 'bogus', None):
    try: se.cut({'plan': {'format': fmt}}, {}, r, tmp()); raise AssertionError('cut should fail')
    except SystemExit as e: assert str(fmt) in str(e) and 'renderer' in str(e), e

# ---- gate on a real tiny clip
def clip(path, secs=25, black=None, db=-14):
    vf = 'testsrc=s=160x284:r=10:d=%s' % secs
    if black: vf += ',drawbox=x=0:y=0:w=160:h=284:t=fill:c=black:enable=\'between(t,%s,%s)\'' % black
    ff('-f', 'lavfi', '-i', vf, '-f', 'lavfi', '-i', 'sine=f=300:d=%s' % secs, '-af', f'loudnorm=I={db}:TP=-1:LRA=7',
       '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', path)

def gate(job, run=None, state=None):
    return se.gate({'meta': {'title': 't', 'description': 'story'}, 'credits': ['Footage: https://y/1', 'Music: m'], **job}, {}, run or tmp(), state or tmp())

r0 = tmp(); clip(r0 / 'short.mp4')
_, out0, _ = se.gate({'short': {'file': 'short.mp4'}, 'meta': {'title': 'The Rape Case', 'description': 'A murder.', 'tags': ['rape', 'news'], 'hashtags': ['#murder', '#news']},
                      'credits': ['Footage: https://y/1']}, {}, r0, tmp())
m0 = out0['meta']
assert m0['title'] == 'The R*pe Case' and m0['description'].startswith('A m*rder.') and m0['description'].endswith('Footage: https://y/1'), m0
assert m0['tags'] == ['r*pe', 'news'] and m0['hashtags'] == ['#m*rder', '#news'], m0

r = tmp(); clip(r / 'short.mp4')
base = {'short': {'file': 'short.mp4', 'duration': 25}, 'timeline': [{'start': 0, 'end': 25, 'kind': 'a', 'person': False}]}
port, out, log = gate(base, r)
assert port == 'next' and out['meta']['description'] == 'story\n\nFootage: https://y/1\nMusic: m' and out['meta']['title'] == 't', (port, out, log)

r = tmp(); clip(r / 'short.mp4', secs=12)
port, out, _ = gate({**base, 'short': {'file': 'short.mp4'}}, r)
assert port == 'invalid' and 'duration' in out['agentErrors'][0], out
r = tmp(); clip(r / 'short.mp4', db=-22)
port, out, _ = gate(base, r)
assert port == 'invalid' and 'loudness' in out['agentErrors'][0], out
r = tmp(); clip(r / 'short.mp4', black=(5, 8))
port, out, _ = gate(base, r)
assert port == 'invalid' and 'black' in out['agentErrors'][0], out
r = tmp(); clip(r / 'short.mp4', black=(23, 25))   # black in the last 3 s is allowed
assert gate(base, r)[0] == 'next'

# identity: 10 person shots, each sampled twice; a shot passes when either frame matches
r = tmp(); clip(r / 'short.mp4')
np.save(r / 'identity.npy', np.array([1.0, 0.0]))
tl = [{'start': i * 2, 'end': i * 2 + 2, 'kind': 'm', 'person': True} for i in range(10)] + [{'start': 20, 'end': 25, 'kind': 'card', 'person': False}]
ij = {**base, 'timeline': tl, 'identity': {'file': 'identity.npy'}}
seen = []
def embed(vals):
    it = iter(vals)
    def f(img, models): seen.append(img.shape); return next(it)
    return f
HIT, MISS = np.array([1.0, 0.0]), np.array([0.0, 1.0])
se._embed = embed([HIT] * 10)                            # the first frame of each shot matches, so one frame per shot
assert gate(ij, r)[0] == 'next' and len(seen) == 10 and seen[0][1] == 160, seen[:1]
se._embed = embed([MISS, None] * 8 + [HIT, MISS, HIT])   # 2 of 10 shots match
port, out, _ = gate(ij, r)
assert port == 'invalid' and 'identity' in out['agentErrors'][0] and '2/10' in out['agentErrors'][0], out
assert gate({**ij, 'identity': None}, r)[0] == 'next'    # no identity file: nothing to compare against
# every face in a frame counts (the person can be the smaller face beside a host), and Top N looks at 4 frames per shot,
# as a moment the probe accepted may show the person in only part of it (live 2026-11-08: Ramsay beside James Corden)
seen.clear(); se._embed = embed([[MISS, HIT]] * 10)
assert gate(ij, r)[0] == 'next' and len(seen) == 10
seen.clear(); se._embed = embed(([MISS] * 3 + [HIT]) * 10)
assert gate({**ij, 'plan': {'format': 'topn'}}, r)[0] == 'next' and len(seen) == 40, len(seen)
# Top N cuts to the person being roasted while they talk: 75 % of moments is enough there (90 % elsewhere)
se._embed = embed([HIT] * 5 + [MISS] * 4 * 5)                            # half the moments show the person: enough for Top N (4 frames a shot)
assert gate({**ij, 'plan': {'format': 'topn'}}, r)[0] == 'next'
se._embed = embed([HIT] * 4 + [MISS] * 4 * 6)
assert gate({**ij, 'plan': {'format': 'topn'}}, r)[0] == 'invalid'
se._embed = embed([HIT] * 8 + [MISS, MISS] * 2)
assert gate({**ij, 'plan': {'format': 'tribute'}}, r)[0] == 'invalid'

# a person edit's shot where no face can be found (a wide stage shot) is left out of the count, as in the probe; a shot of
# someone else still counts (live 2026-11-08: Alex Honnold's TED edit failed at 8/9, the ninth a wide shot)
se._embed = embed([HIT] * 8 + [[], []] + [HIT])
assert gate({**ij, 'plan': {'format': 'edit'}}, r)[0] == 'next'
se._embed = embed([HIT] * 8 + [MISS, MISS] * 2)                         # 2 shots of someone else: 8/10
assert gate({**ij, 'plan': {'format': 'edit'}}, r)[0] == 'invalid'
# one missed shot is allowed in an edit: every line already passed the probe, and the person climbing with the face turned
# away scores below the match line (live 2026-11-09: CBS's Alex Honnold edit failed at 7/8 on its one climbing shot)
se._embed = embed([HIT] * 7 + [[], []] * 2 + [MISS, MISS])   # 2 faceless shots left out: 7/8
assert gate({**ij, 'plan': {'format': 'edit'}}, r)[0] == 'next'

# ---- record
st = tmp() / 'state'
job = {'person': {'qid': 'Q1', 'name': 'A B'}, 'plan': {'format': 'tribute'}, 'track': {'id': 's9'}, 'pick': {'angle': 'why'}, 'meta': {'title': 'T'}}
se._today = lambda: dt.date(2026, 11, 6)
assert se.record(job, {}, tmp(), st)[0] == 'next'
assert json.loads((st / 'trending-covered.json').read_text()) == [{'qid': 'Q1', 'name': 'A B', 'format': 'tribute', 'date': '2026-11-06', 'title': 'T', 'angle': 'why'}]
assert json.loads((st / 'trending-used-sounds.json').read_text()) == [{'id': 's9', 'date': '2026-11-06'}]
(st / 'trending-covered.json').write_text(json.dumps([{'qid': f'Q{i}', 'date': '2026-01-01'} for i in range(500)]))
se.record({**job, 'person': {'qid': 'NEW', 'name': 'N'}, 'plan': {'format': 'topn'}}, {}, tmp(), st)
cov = json.loads((st / 'trending-covered.json').read_text())
assert len(cov) == 500 and cov[-1]['qid'] == 'NEW' and cov[0]['qid'] == 'Q1', (len(cov), cov[0])   # only the last 500 are kept
(st / 'trending-covered.json').write_text(json.dumps([{'qid': 'T0', 'format': 'tribute', 'date': '2025-01-01'}] + [{'qid': f'Q{i}', 'date': '2026-01-01'} for i in range(500)]))
se.record({**job, 'person': {'qid': 'NEW2', 'name': 'N'}, 'plan': {'format': 'topn'}}, {}, tmp(), st)
cov = json.loads((st / 'trending-covered.json').read_text())
assert cov[0]['qid'] == 'T0' and len(cov) == 501 and cov[-1]['qid'] == 'NEW2', (len(cov), cov[0])   # tributes are kept: one per person, ever
st2 = tmp() / 'state'
se.record({'person': {'qid': 'Q2', 'name': 'N'}, 'plan': {'format': 'topn'}}, {}, tmp(), st2)   # no track: no sound entry
assert not (st2 / 'trending-used-sounds.json').exists()
print('ok')
