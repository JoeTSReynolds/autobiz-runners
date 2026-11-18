# facecrop smoothing/crop window, caption curves and grouping, caption scale. Run: python3 test_kit.py
import sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trending import captions as C, facecrop as F

# gold-pop curve
d = 0.8
assert abs(C.gold_scale(0.07, d) - 1.0) < 1e-6, C.gold_scale(0.07, d)
assert abs(C.gold_scale(d, d) - 1 / 3) < 0.01, C.gold_scale(d, d)
assert abs(C.gold_scale(0.0, d) - 0.55) < 1e-6
ss = [C.gold_scale(0.07 + k * (d - 0.07) / 20, d) for k in range(21)]
assert all(a > b for a, b in zip(ss, ss[1:]))
assert (ss[0] - ss[1]) < (ss[-2] - ss[-1])  # accelerating

# group_words
ws = [{"w": "This", "s": 0, "e": .2}, {"w": "is", "s": .2, "e": .3}, {"w": "fucking", "s": .3, "e": .6},
      {"w": "crazy.", "s": .6, "e": 1.0}, {"w": "Shit", "s": 1.0, "e": 1.2}, {"w": "extraordinarily", "s": 1.2, "e": 1.8},
      {"w": "big", "s": 1.9, "e": 2.0}, {"w": "ok", "s": 3.0, "e": 3.2}]
g = C.group_words(ws)
assert [x["text"].upper() for x in g] == ["THIS IS", "F*CKING CRAZY.", "SH*T", "EXTRAORDINARILY", "BIG", "OK"], g
assert g[0]["start"] == 0 and g[0]["end"] == .3
assert C.censor("shit,") == "sh*t,"

# smoothing: noisy path -> bounded movement, jump at cuts
rng = np.random.RandomState(0)
n, W = 300, 1920
cx = 900 + rng.normal(0, 12, n); cy = 400 + rng.normal(0, 12, n); cx[150:] += 500
sx, sy = F.smooth(cx, cy, [150], W)
step = np.abs(np.diff(sx)); step[149] = 0
assert step.max() <= 0.35 * W / 30 + 1e-6
assert np.abs(np.diff(sx[:140])).max() < 1.0, "jitter inside dead zone"
assert abs(sx[150] - cx[150]) < 1e-6, "cut must jump"

# crop window inside frame
for z in (1.0, 1.15, 1.5):
    for x in (-500, 0, 960, 5000):
        for y in (-100, 300, 1080, 4000):
            x0, y0, w, h = F.crop_window(1920, 1080, x, y, z)
            assert 0 <= x0 and x0 + w <= 1920 + 1e-6 and 0 <= y0 and y0 + h <= 1080 + 1e-6 and abs(w / h - 9 / 16) < 1e-6

# caption scale: 0.8 draws a smaller image than 1.0 (person-edit captions)
items = [{"text": "big words", "start": 0, "end": 1}]
full, small = (C.GoldCaptions(items, scale=s).frame(0.5)[0][0] for s in (1.0, 0.8))
assert small.width < full.width and small.height < full.height, (small.size, full.size)
assert C.GoldCaptions(items).frame(0.5)[0][0].size == full.size  # default scale is 1.0
# before a pause the caption keeps shrinking after its end until it is gone: no tiny caption left holding on screen
gc = C.GoldCaptions([{"text": "big words", "start": 0, "end": 1}, {"text": "later", "start": 3, "end": 4}])
ws_ = [gc.frame(1 + k * 0.04)[0][0].width for k in range(5)]   # 1.00 .. 1.16 s
assert all(a > b for a, b in zip(ws_, ws_[1:])), ws_
assert gc.frame(1 + C.GoldCaptions.OUT)  == [] and gc.frame(2.9) == []
# sensitive wording reaches every caption layer: same pixels as the caption form typed directly
g2 = C.group_words([{"w": "Rape,", "s": 0, "e": .3}, {"w": "grape", "s": 1.0, "e": 1.2}])  # a comma splits only after 2+ words, so a pause does it here
assert [x["text"] for x in g2] == ["R*pe,", "grape"], g2  # originals only: a spoken "grape" in a clip is left alone
g3 = C.group_words([{"w": "Six", "s": 0, "e": .3}, {"w": "sex", "s": .3, "e": .5}])
assert [x["text"] for x in g3] == ["Six s*x"], g3
same = lambda a, b: np.array_equal(np.asarray(a), np.asarray(b))
assert same(C.render_gold("rape"), C.render_gold("r*pe")) and not same(C.render_gold("rape"), C.render_gold("rope"))
assert same(C.StatSlams([])._img("Murdered"), C.StatSlams([])._img("M*rdered"))
assert same(C.PopupCards([])._img("he was killed"), C.PopupCards([])._img("he was k*lled"))
# identity follow: faces are (cx, cy, size, matches_ref); the matching smaller face is followed, held ~1 s when it vanishes, then the largest
big, small = (300, 200, 200, False), (1500, 300, 80, True)
fr = lambda i, faces: (i, faces)
fol = F._follow([fr(0, [big, small]), fr(6, [big, small]), fr(12, [big]), fr(24, [big]), fr(45, [big])], 5, 1920)
assert [t[0] for t in fol] == [1500, 1500, 1500, 1500, 300], fol  # t=0.4 s held, 0.8 s held, 1.5 s after last match (1.0 s hold) -> largest
assert F._follow([fr(0, [big, small])], 5, 1920)[0][0] == 1500
assert F._follow([fr(0, [big, (1500, 300, 80, False)])], 5, 1920)[0][0] == 300  # nobody matches: largest, as without ref
print("all ok")
