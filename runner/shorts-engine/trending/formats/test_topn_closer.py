# Top N safe margins, closer text fit, closer frame pick, subscribe/like timing. No render. Run: python3 formats/test_topn_closer.py (from trending/)
import sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trending.formats import topn, safe

tmp = Path(tempfile.mkdtemp())
box = lambda p: Image.open(p).convert("RGBA").point(lambda v: v).getbbox()


def ink(p, bg_black=False):
    """Bounding box of drawn pixels: non-transparent, or (on the black header bar) non-black."""
    im = Image.open(p).convert("RGBA")
    a = np.asarray(im)
    m = (a[..., :3].max(axis=2) > 0) if bg_black else (a[..., 3] > 0)
    ys, xs = np.nonzero(m)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


# 1. one place for the margins
assert (safe.SAFE_X, safe.SAFE_TOP, safe.SAFE_BOTTOM) == (70, 110, 260)

# 2. fit never drops a word, floor 44
t58 = "THIS WEEK HE TURNS 60 AND REUNITES WITH MARCO PIERRE WHITE"
lines, size = safe.fit_lines(t58, 64, 940, 3)
assert " ".join(lines) == t58 and size >= 44 and len(lines) <= 3, (lines, size)
huge = " ".join(["REUNITES"] * 30)
lines, size = safe.fit_lines(huge, 110, 700, 2)
assert " ".join(lines) == huge and size == 44, (len(lines), size)   # floor reached: wraps further, drops nothing

# 3. header inside the margins, theme line shrunk or wrapped but complete
long_theme = "times he roasted a contestant live on air in front of everybody"
h = topn._header([("Top 5", 60, (255, 255, 255)), ("GORDON RAMSAY", 92, topn.RED), (long_theme, 52, (255, 255, 255))], tmp / "h.png")
x0, y0, x1, y1 = ink(tmp / "h.png", True)
assert y0 >= safe.SAFE_TOP and x0 >= safe.SAFE_X and x1 <= topn.W - safe.SAFE_X and y1 <= h, (x0, y0, x1, y1, h)

# 4. rank list box and long labels inside the margins
assert topn.LIST_X >= safe.SAFE_X
topn._rank_list({1: "Called a chef a donkey in front of the whole kitchen brigade", 2: "Short"}, 5, tmp / "l.png")
x0, y0, x1, y1 = ink(tmp / "l.png")
assert topn.LIST_X + x1 <= topn.W - safe.SAFE_X, x1
assert h + 22 + Image.open(tmp / "l.png").height <= 1920 - safe.SAFE_BOTTOM

# 5. closer frame pick
ident = np.array([1.0, 0.0])
S = [("a.mp4", 1.0, [(np.array([0.0, 1.0]), 0.3)]),                 # other person, big
     ("b.mp4", 2.0, [(np.array([1.0, 0.0]), 0.10)]),                # him, small
     ("c.mp4", 3.0, [(np.array([0.9, 0.1]), 0.30)]),                # him, big
     ("d.mp4", 4.0, [])]
assert topn.pick_closer_frame(S, ident) == ("c.mp4", 3.0)
assert topn.pick_closer_frame(S[:1] + S[3:], ident) is None
run = Path(tempfile.mkdtemp())
ms = [("x.mp4", 10.0, 14.0), ("y.mp4", 20.0, 24.0)]
seen = []
look = lambda s, t: (seen.append((s, t)), S[2][2] if (s, round(t, 2)) == ("y.mp4", 21.0) else [])[1]
assert topn.closer_source(ms, run, look) == ("y.mp4", 23.5) and seen == []   # no identity.npy: today's frame, nothing sampled
np.save(run / "identity.npy", ident)
assert topn.closer_source(ms, run, look) == ("y.mp4", 21.0) and len(seen) == 6   # 3 per clip
assert topn.closer_source(ms, run, lambda s, t: []) == ("y.mp4", 23.5)           # no match: today's frame

# 6. subscribe and like timing, inside the closer
T = topn.closer_times()
assert 0 < T["line1"] < T["line2"] < T["button"] < T["hand"] < T["press"] < T["thumb"] and T["end"] <= topn.CLOSER
assert 1.5 <= T["thumb"] + 0.3 - T["button"] <= 2.0, T
ev = topn.audio_events([5.0, 9.0], 12.0)
clicks = [(Path(f).parent.name, round(t, 2)) for f, t, _ in ev if "click" in str(f)]
assert clicks == [("click", round(12.0 + T["press"], 2)), ("click", round(12.0 + T["thumb"], 2))], clicks
assert all(Path(f).exists() for f, _, _ in ev) and len([e for e in ev if "whoosh" in str(e[0])]) == 2
fc = topn.mix_filter(ev)
assert fc.count("adelay=") == 4 and "amix=inputs=5:" in fc and fc.count("volume=") == 4, fc

# 7. closer cards: subscribe, subscribed, hand, thumb; all inside the safe box and timed on the same clock
png = lambda n, w, h: (Image.new("RGBA", (w, h), (255, 0, 0, 255)).save(tmp / n), str(tmp / n))[1]
cards = topn.closer_cards(dict(line1=t58, line2="STILL DODGING? 👀"), tmp, 12.0, 12.0 + topn.CLOSER, emoji=lambda ch, dest: png(dest.name, 150, 150))
by = {c["name"]: c for c in cards if c.get("name")}
assert {"subscribe", "subscribed", "hand", "thumb"} <= set(by), set(by)
assert by["subscribe"]["start"] == 12.0 + T["button"] and by["subscribed"]["start"] == 12.0 + T["press"]
assert by["hand"]["start"] == 12.0 + T["hand"] and abs(by["hand"]["start"] + by["hand"]["glide"] - (12.0 + T["press"])) < 1e-6
assert by["thumb"]["start"] == 12.0 + T["thumb"]
for c in cards:
    wi, hi = Image.open(c["image"]).size
    hh = round(hi * c["w"] / wi)
    for x, y in [(c["x"], c["y"])] + ([(c["x0"], c["y0"])] if "x0" in c else []):
        if x != "center" and c["x"] != 0:
            assert x >= safe.SAFE_X and x + c["w"] <= topn.W - safe.SAFE_X, (c, x)
        assert y + hh <= 1920 - safe.SAFE_BOTTOM + 60, (c["image"], y, hh)   # glide start may dip 60 px while the hand fades in
# no network: emoji None -> button only
cards = topn.closer_cards(dict(line1="A B", line2="C D"), tmp, 12.0, 12.0 + topn.CLOSER, emoji=lambda ch, dest: None)
assert {c.get("name") for c in cards} >= {"subscribe", "subscribed"} and not {c.get("name") for c in cards} & {"hand", "thumb"}

# 8. the other renderers keep text inside the same margins
from trending.formats import casefile, tribute
assert casefile.CARD_X >= safe.SAFE_X and casefile.CARD_X + casefile.CARD_W <= 1080 - safe.SAFE_X
tl = casefile.Timeline([dict(label="DEC 2025", pos=0, at=0), dict(label="NOV 2026", pos=1, at=0)])
a = np.asarray(tl.frame(1.0))[..., 3] > 0
ys, xs = np.nonzero(a)
assert xs.min() >= safe.SAFE_X and xs.max() + 1 <= 1080 - safe.SAFE_X and ys.min() >= safe.SAFE_TOP, (xs.min(), xs.max(), ys.min())
tribute._text_png([("A very long name that goes on and on and on across the whole frame", 80, False, 800)], tmp / "t.png")
a = np.asarray(Image.open(tmp / "t.png"))[..., 3] > 128
ys, xs = np.nonzero(a)
assert xs.min() >= safe.SAFE_X and xs.max() + 1 <= 1080 - safe.SAFE_X, (xs.min(), xs.max())
print("ok")
