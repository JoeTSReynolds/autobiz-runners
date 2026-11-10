# music.analyse finds bpm and drop on a synthetic click track. Run: python3 test_music.py
import os, subprocess, tempfile, wave
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trending import music

SR = 22050
t = np.arange(SR * 24) / SR
x = np.zeros_like(t)
for b in np.arange(0, 24, 0.5):                      # 120 BPM clicks (decaying 1 kHz bursts)
    i = int(b * SR); n = int(0.03 * SR)
    x[i:i + n] += np.sin(2 * np.pi * 1000 * t[:n]) * np.exp(-t[:n] * 120) * 0.5
x += 0.3 * np.sin(2 * np.pi * 50 * t) * (t >= 10)    # bass enters at 10 s
p = os.path.join(tempfile.mkdtemp(), 'syn.wav')
with wave.open(p, 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype('<i2').tobytes())
a = music.analyse(p)
print(a['bpm'], a['drop'], a['drops'])
assert abs(a['bpm'] - 120) <= 2, a['bpm']
assert abs(a['drop'] - 10) <= 0.5, a['drop']
pl = music.place(a, 5, 20); assert abs(pl['music_offset'] - (a['drop'] - 5)) < 1e-2
# vocal_share: YAMNet frames whose top classes include singing/speech/rapping; a sine + noise bed is not vocal
bed = (0.3 * np.sin(2 * np.pi * 110 * t) + 0.05 * np.random.default_rng(0).standard_normal(len(t))) * (np.sin(2 * np.pi * 2 * t) > 0)
pb = os.path.join(tempfile.mkdtemp(), 'bed.wav')
with wave.open(pb, 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((bed * 32767).astype('<i2').tobytes())
models = os.path.join(tempfile.gettempdir(), 'autobiz-yamnet-test')   # downloaded once (16 MB), sha256 checked
assert 'vocal_share' not in music.analyse(p)
ab = music.analyse(pb, models)
assert 0 <= ab['vocal_share'] < music.VOCAL_SHARE_MAX, ab['vocal_share']
sc = np.zeros((10, 521)); sc[:4, 24] = 1; sc[4:, 300] = 1          # frames 0-3: Singing on top; the rest: no vocal class
assert music._share(sc) == 0.4
sc[5:, 0] = 0.9; sc[5:, 301:304] = 1                               # Speech only 4th of the top 5 still counts
assert music._share(sc) == 0.9, music._share(sc)
bad = os.path.join(tempfile.mkdtemp(), music.YAMNET_NAME); open(bad, 'wb').write(b'nope')
try: music.yamnet_path(os.path.dirname(bad)); raise SystemExit('wrong hash accepted')
except RuntimeError: pass
# swell: the music rises from ducked to full over 2 s before a speech pause (the stat slams) and falls back over 2 s
# after it, instead of jumping 12 dB at its edges (owner, 2026-11-10)
_d = tempfile.mkdtemp(); _v, _m, _o = (os.path.join(_d, n) for n in ('v.wav', 'm.wav', 'o.m4a'))
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'sine=f=1000:d=14', '-af', "volume='if(between(t,6,8),0,1)':eval=frame", _v], check=True)
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'anoisesrc=d=16:c=pink:a=0.5', '-af', 'lowpass=f=300', _m], check=True)
def _band(path, a, b):   # music level (dB) in [a, b]: the voice is a 1 kHz tone, filtered out
    r = subprocess.run(['ffmpeg', '-v', 'info', '-ss', str(a), '-t', str(b - a), '-i', path, '-af', 'lowpass=f=250,volumedetect', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    return float(r.split('mean_volume:')[1].split('dB')[0])
music.mix(_v, _m, 0, _o, music_gain_db=-6, duck_db=12, video_duration=14, swell=[(6, 8)])
lo, ramp, full, back, lo2 = _band(_o, 1.5, 3), _band(_o, 4.9, 5.2), _band(_o, 6.4, 7.6), _band(_o, 8.8, 9.1), _band(_o, 10.5, 11.5)
assert full > lo + 6 and lo + 2 < ramp < full - 1 and lo + 2 < back < full - 1 and abs(lo2 - lo) < 2, (lo, ramp, full, back, lo2)
print('ok')
