# Offline tests for trending/align.py (retime). Run: python3 test_align.py
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trending import align

W = lambda w, s, e: {'w': w, 's': s, 'e': e}
# caption words spread evenly over a 4 s line (source seconds); the clip file starts at source 100
cap = [W('Imagine', 100.0, 101.0), W('being', 101.0, 102.0), W('um-ish', 102.0, 103.0), W('alone,', 103.0, 104.0)]
# whisper (file seconds): no "um-ish", punctuation and case differ, speech is uneven
heard = [W('imagine', 0.2, 0.9), W('being', 0.9, 2.5), W('Alone', 3.0, 3.6)]
align._whisper = lambda path: heard
out = align.retime(cap, 'x.mp4', 99.5)          # file time t is source time 99.5 + t
assert [w['w'] for w in out] == ['Imagine', 'being', 'um-ish', 'alone,'], out          # caption text untouched
assert (out[0]['s'], out[0]['e']) == (99.7, 100.4) and (out[1]['s'], out[1]['e']) == (100.4, 100.85), out   # matched: whisper's times + offset
assert (out[3]['s'], out[3]['e']) == (102.5, 103.1), out
assert (out[2]['s'], out[2]['e']) == (100.85, 102.5), out                              # unmatched: between its matched neighbours (a heard word's long end is cut to 0.45 s)
assert cap[0]['s'] == 100.0                                                             # input is not modified

# a gap: several unmatched words in a row share the space evenly; a leading unmatched word ends where the first match starts
cap2 = [W('so', 10.0, 10.5), W('well', 10.5, 11.0), W('yes', 11.0, 11.5), W('the', 11.5, 12.0), W('end', 12.0, 12.5)]
align._whisper = lambda path: [W('yes', 1.0, 1.4), W('the', 1.4, 1.6)]
out = align.retime(cap2, 'x.mp4', 10.0)
assert [(w['s'], w['e']) for w in out] == [(10.0, 10.5), (10.5, 11.0), (11.0, 11.4), (11.4, 11.6), (11.6, 12.5)], out
assert all(a['e'] <= b['s'] + 1e-9 for a, b in zip(out, out[1:])), out                  # never out of order

# a heard word that runs past the next word's start (an automatic event's last word) ends where the next begins
align._whisper = lambda path: [W('so', 0.0, 3.0), W('well', 1.0, 1.5)]
out = align.retime(cap2[:2], 'x.mp4', 10.0)
assert [(w['s'], w['e']) for w in out] == [(10.0, 11.0), (11.0, 11.5)], out

# nothing matches: unchanged
align._whisper = lambda path: [W('zebra', 0.0, 1.0)]
assert align.retime(cap, 'x.mp4', 0) == cap

# whisper fails or is missing: the words come back unchanged and never raises
def boom(path): raise RuntimeError('model download failed')
align._whisper = boom
assert align.retime(cap, 'x.mp4', 99.5) == cap
del align._whisper
os.environ['PATH'] = ''                          # no whisper-ctranslate2 on PATH
import importlib; importlib.reload(align)
assert align.retime(cap, 'x.mp4', 99.5) == cap
assert align.retime([], 'x.mp4', 0) == []
print('ok')
