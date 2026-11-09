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
print('ok')
