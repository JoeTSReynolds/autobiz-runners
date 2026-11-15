# ytsrc: json3 parsing, sentences, find_phrase, track choice, probe_frames call shape (no network). Run: python3 test_ytsrc.py
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trending import ytsrc

here = Path(__file__).parent
JSON3 = {'events': [
    {'tStartMs': 0, 'dDurationMs': 1500, 'segs': [{'utf8': 'Hello'}, {'utf8': ' there,', 'tOffsetMs': 500}]},
    {'tStartMs': 1000, 'dDurationMs': 2000, 'segs': [{'utf8': 'there,'}, {'utf8': ' my', 'tOffsetMs': 600}, {'utf8': ' friend.', 'tOffsetMs': 900}]},
    {'tStartMs': 5000, 'dDurationMs': 500, 'segs': [{'utf8': '\n'}, {'utf8': 'Next', 'tOffsetMs': 0}]}]}
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / 'x.en.json3'; p.write_text(json.dumps(JSON3))
    ws = ytsrc.parse_json3(p)
assert [w['w'] for w in ws] == ['Hello', 'there,', 'my', 'friend.', 'Next'], ws  # rolling repeat dropped
assert ws[1]['s'] == 0.5 and ws[0]['e'] == 0.5 and ws[3]['e'] == 3.0, ws

ss = ytsrc.sentences(ws)
assert [s['text'] for s in ss] == ['Hello there, my friend.', 'Next'], ss
assert ss[0]['start'] == 0 and ss[0]['end'] == 3.0

assert ytsrc.find_phrase(ws, 'there, my friend') == (0.5, 3.0)
assert ytsrc.find_phrase(ws, "Hello THERE my") == (0, 1.9)
assert ytsrc.find_phrase(ws, 'hello there zzz') == (0, 1.5)  # one phrase word may be missing from the transcript
assert ytsrc.find_phrase(ws, 'friend next steps now') is None

# track choice: manual English first, then auto English, never a translated track
def tr(lang, tl=False): return [{'ext': 'json3', 'url': f'https://y/t?lang={lang}' + ('&tlang=en' if tl else '')}]
assert ytsrc.pick_track({'subtitles': {'en-GB': tr('en-GB')}, 'automatic_captions': {'en-orig': tr('en')}}) == 'en-GB'
assert ytsrc.pick_track({'subtitles': {}, 'automatic_captions': {'en-orig': tr('en'), 'en': tr('en')}}) == 'en-orig'
assert ytsrc.pick_track({'automatic_captions': {'en': tr('es', True), 'es-orig': tr('es')}}) is None
assert ytsrc.pick_track({'subtitles': {'fr': tr('fr')}}) is None

# probe_frames: one yt-dlp call, one section per window, missing windows are None
calls = []
def fake(cmd, **kw):
    calls.append(cmd)
    out = Path(cmd[cmd.index('-o') + 1].replace('%(section_start)s', '10.0').replace('%(ext)s', 'mp4'))
    out.write_bytes(b'x')
    class R: returncode = 0; stderr = ''
    return R()
ytsrc.ytdlp.run = fake
with tempfile.TemporaryDirectory() as d:
    got = ytsrc.probe_frames('abc', 'https://www.youtube.com/watch?v=abc', [(10, 12), (50, 52)], d)
assert len(calls) == 1 and calls[0].count('--download-sections') == 2, calls
assert '*10.00-12.00' in calls[0] and '*50.00-52.00' in calls[0] and '--no-download-archive' in calls[0], calls
assert got[0].endswith('abc_10.0.mp4') and got[1] is None, got

# search keeps the keys it is given and drops nulls
ytsrc.ytdlp.run = lambda cmd, **kw: type('R', (), {'stdout': '{"id":"a","title":"T","channel":"C","duration":30,"view_count":5,"live_status":null,"timestamp":1}\n\n'})()
assert ytsrc.search('q', 3) == [{'id': 'a', 'title': 'T', 'channel': 'C', 'duration': 30, 'view_count': 5, 'timestamp': 1}]

# manual captions: one segment holds a whole line ("GORDON: BACON, EGGS…\n…") with no word timing. Split into words spread
# evenly over the segment, without speaker labels and music notes, so quotes can be found (live 2026-11-08: The Late Late
# Show's captions held 88 "words" for a 379 s video and no quote matched)
import json, tempfile
from pathlib import Path as _P
_d = _P(tempfile.mkdtemp()) / 'm.json3'
_d.write_text(json.dumps({'events': [
    {'tStartMs': 0, 'dDurationMs': 2000, 'segs': [{'utf8': '\u266a  \nJAMES: WELCOME BACK'}]},
    {'tStartMs': 2000, 'dDurationMs': 3000, 'segs': [{'utf8': 'GORDON: THE EGGS ARE RAW.'}]}]}))
mw = ytsrc.parse_json3(_d)
assert [w['w'] for w in mw] == ['WELCOME', 'BACK', 'THE', 'EGGS', 'ARE', 'RAW.'], [w['w'] for w in mw]
assert mw[0]['s'] == 0 and abs(mw[1]['s'] - 1.0) < 1e-6 and abs(mw[2]['s'] - 2.0) < 1e-6 and abs(mw[5]['e'] - 5.0) < 1e-6, mw
assert ytsrc.find_phrase(mw, 'the eggs are raw') is not None
# manual captions are one timestamp per line; the automatic en-orig track has per-word times: manual wording, automatic timing
import os
def mk(manual, auto):
    d = tempfile.mkdtemp(); vid = 'abc'
    info = {'subtitles': {'en': tr('en')}, 'automatic_captions': {'en-orig': tr('en'), 'en-de': tr('en', True), 'en': tr('en')}}
    json.dump(info, open(f'{d}/{vid}.info.json', 'w'))
    json.dump({'events': manual}, open(f'{d}/{vid}.en.json3', 'w'))
    if auto is not None: json.dump({'events': auto}, open(f'{d}/{vid}.en-orig.json3', 'w'))
    return ytsrc.info_and_words(vid, d)[1]
MAN = [{'tStartMs': 0, 'dDurationMs': 6000, 'segs': [{'utf8': 'Feel the smooth granite.'}]}]
AUTO = [{'tStartMs': 0, 'dDurationMs': 6000, 'segs': [{'utf8': 'feel', 'tOffsetMs': 500}, {'utf8': ' the', 'tOffsetMs': 900}, {'utf8': ' smooth', 'tOffsetMs': 1000},
                                                    {'utf8': ' granite', 'tOffsetMs': 3000}]}]
mg = mk(MAN, AUTO)
assert [w['w'] for w in mg] == ['Feel', 'the', 'smooth', 'granite.'], mg                       # manual wording
assert [w['s'] for w in mg] == [0.5, 0.9, 1.0, 3.0] and all(w['timed'] for w in mg), mg        # automatic timing
# an automatic word the manual line lacks is dropped, a manual word the speech recognition missed is spread between its neighbours
mg = mk(MAN, [{'tStartMs': 0, 'dDurationMs': 6000, 'segs': [{'utf8': 'feel', 'tOffsetMs': 500}, {'utf8': ' granite', 'tOffsetMs': 3000}]}])
assert [w['w'] for w in mg] == ['Feel', 'the', 'smooth', 'granite.'] and mg[0]['s'] == 0.5 and mg[3]['s'] == 3.0 and 0.5 < mg[1]['s'] < mg[2]['s'] < 3.0, mg
# no automatic track: the manual words, spread evenly, not marked timed
mg = mk(MAN, None)
assert [w['w'] for w in mg] == ['Feel', 'the', 'smooth', 'granite.'] and not any('timed' in w for w in mg) and mg[1]['s'] == 1.5, mg
print('ok')
