# edit.render on a tiny synthetic fixture. Run: python3 test_edit.py (prints ok)
import json, numpy as np, re, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trending.formats import edit

run = tempfile.mkdtemp()
ff = lambda *a: subprocess.run(["ffmpeg", "-y", "-v", "error", *a], check=True)
BPM, PER = 120.0, 0.5

# --- pure scheduling: cut rate speeds up after the drop, the tail is on the grid (2 beats, 1 beat, the final beat stutters as 4 quarter shots)
g = [k * PER for k in range(200)]
S = edit.schedule([3.0, 3.0, 3.0, 3.0], 1, 2, g, 3.0)
assert S["shots"][0]["kind"] == "S" and S["shots"][-1]["trans"] == "hit"
pre_len = [s["t1"] - s["t0"] for s in S["shots"] if s["t1"] <= 3.0 + 1e-6 and s["t0"] > 0]
post_len = [s["t1"] - s["t0"] for s in S["shots"] if s["kind"] in "SB" and s["t0"] >= S["slams"][-1][1] - 1e-6 and s["t1"] <= S["tT"] + 1e-6]
assert pre_len and post_len and max(post_len) <= min(pre_len) + 1e-6 and sum(post_len) / len(post_len) < sum(pre_len) / len(pre_len), (pre_len, post_len)
assert S["shots"][[s["t0"] for s in S["shots"]].index(3.0)]["trans"] == "drop"
assert [round(a, 3) for a, b in S["slams"]] == [round(S["slams"][0][0] + 2 * PER * j, 3) for j in range(2)]
assert [round(b - a, 3) for a, b in S["lines"]] == [3.0] * 4 and S["lines"][2][0] == S["lines"][1][1] + S["gap"] and S["lines"][3][0] == S["lines"][2][1]
tail = [s for s in S["shots"] if s["kind"] == "T"]
assert abs(tail[0]["t0"] - S["tT"]) < 1e-6 and abs(tail[-1]["t1"] - S["D"]) < 1e-6
assert abs((S["D"] - S["tT"]) - edit.TAIL_S) <= PER + 1e-6 and S["tT"] >= S["lines"][-1][1], S
dur_ = [round(s["t1"] - s["t0"], 3) for s in tail]
assert all(d >= 0.75 * PER for d in dur_[:-4]) and all(abs(d - PER / 4) < 1e-6 for d in dur_[-4:]), dur_   # no half-beat zone, only the last beat stutters
assert all(abs(d - 2 * PER) < 1e-6 for s, d in zip(tail, dur_) if s["t0"] < S["tT"] + 2.0 - 1e-6 and s["t1"] <= S["tT"] + 2.0 + 1e-6)
assert all(d <= PER + 1e-6 for s, d in zip(tail, dur_) if s["t0"] >= S["tT"] + 2.0)
st = [s for s in tail if s.get("stutter")]
assert len(st) == 4 and st == tail[-4:] and tail[-1]["trans"] == "hit" and all(s["trans"] == "stutter" for s in st[1:3]) and st[0]["trans"] in edit.TAIL_BIG + edit.TAIL_SMALL, st
d0_ = min(range(len(g)), key=lambda i: abs(g[i] - 3.0))
assert all(s["trans"] in edit.TAIL_BIG + edit.TAIL_SMALL + ["stutter", "hit"] for s in tail), [s["trans"] for s in tail]
for s in tail[:-4]:
    i_ = s["t0"] / PER
    assert (s["trans"] in edit.TAIL_BIG) == (abs(i_ - round(i_)) < 1e-6 and (round(i_) - d0_) % 4 == 0), s
assert set(edit.TAIL_BIG) <= {s["trans"] for s in tail} and set(edit.TAIL_SMALL) <= {s["trans"] for s in tail}
assert all(edit.PULSE_W[t] == 1.0 for t in edit.TAIL_BIG) and all(edit.PULSE_W[t] == 0.6 for t in edit.TAIL_SMALL) and edit.PULSE_W["stutter"] == 0.5

# --- onset snapping: beats move onto kick onsets within +-win, weak/flat envelopes leave them, order is kept
H = 0.01
env = np.full(1000, 0.05); gb = [1.0 + 0.5 * k for k in range(10)]
for t in gb: env[int(round((t + 0.08) / H))] = 3.0
sn = edit.snap(gb, env, H)
assert all(abs(x - (t + 0.08)) < H + 1e-9 for x, t in zip(sn, gb)), sn
assert edit.snap(gb, np.full(1000, 0.05), H) == gb and edit.snap(gb, np.zeros(1000), H) == gb
e2 = np.full(1000, 0.05); e2[int(1.5 / H)] = 3.0; e2[int(1.6 / H)] = 3.0   # two beats 0.1 apart chasing one peak
sn2 = edit.snap([1.45, 1.55], e2, H)
assert sn2[1] - sn2[0] >= 0.1 - 1e-9 and sorted(sn2) == sn2, sn2
assert all(b - a >= 0.1 - 1e-9 for a, b in zip(sn, sn[1:]))

# --- real-first tail: every tail shot is footage while any exists (no file back-to-back), stutter repeats the file and in-point
for n_real in (1, 2, 3, 5):
    pool_ = [{"file": f"f{i}.mp4", "kind": "video"} for i in range(n_real)]
    got = edit.tail_pick(tail, pool_)
    assert len(got) == len(tail) and all(it in pool_ for it, _ in got)
    for k in range(1, len(tail)):
        if tail[k].get("stutter") and tail[k - 1].get("stutter"):
            assert got[k][0]["file"] == got[k - 1][0]["file"] and got[k][1] == got[k - 1][1], (k, got[k], got[k - 1])
        elif n_real > 1:
            assert got[k][0]["file"] != got[k - 1][0]["file"], (n_real, k)
assert len({ss for it, ss in edit.tail_pick(tail, pool_[:2]) if it["file"] == "f0.mp4"}) > 1   # a reused clip starts later

# --- photos and footage of the person also cut in during the speech (owner 2026-11-17: real material first, stock only to fill):
# every b-roll shot, drop cutaway first, never a stat slam (its text sits on a calm stock shot) or a tail shot
sr = edit.speech_real(S["shots"])
bs = [i for i, x in enumerate(S["shots"]) if x["kind"] == "B" and "slam" not in x]
assert sorted(sr) == bs and S["shots"][sr[0]]["trans"] == "drop", (sr, bs)
# speech footage share: enough to fill the speech cutaways after the photos, at least 2, leaving the montage TAIL_MIN_REAL clips
assert edit.speech_footage(nb=8, photos=2, footage=14) == 6 and edit.speech_footage(8, 2, 9) == 3 and edit.speech_footage(8, 2, 3) == 2
assert edit.speech_footage(3, 4, 14) == 2 and edit.speech_footage(8, 0, 1) == 1
# no speaker shot starts after the last line ends (spk.mp4 has nothing there: it rendered black); the payoff line stays on the speaker
for ld_ in ([4.83, 3.65, 4.18, 5.35, 5.13, 6.0], [3.0, 3.0, 3.0, 3.0], [2.2, 4.1, 3.3, 2.9, 3.7]):
    for sh_ in (0.0, 0.11, 0.23, 0.35):
        g_ = [sh_ + 0.4644 * k for k in range(200)]
        S_ = edit.schedule(ld_, 1, 2, g_, ld_[0])
        end_ = S_["lines"][-1][1]
        assert not [x for x in S_["shots"] if x["kind"] == "S" and x["t0"] >= end_ - 1e-6], (ld_, sh_, end_, [(x["t0"], x["kind"]) for x in S_["shots"] if x["t0"] > end_ - 3])
        assert [x for x in S_["shots"] if x["t0"] < end_ - 1e-6][-1]["kind"] == "S"
bts = [1.0, 1.5, 2.0]   # beat pulse: 1 on the beat, gone after BEAT_PULSE, counts beats so far
assert edit.beat_pulse(0.5, bts) == (0.0, 0) and edit.beat_pulse(1.5, bts) == (1.0, 2)
assert 0 < edit.beat_pulse(1.5 + edit.BEAT_PULSE / 2, bts)[0] < 0.5 and edit.beat_pulse(1.5 + edit.BEAT_PULSE, bts)[0] < 1e-9

# --- speech picture cuts: no sliver or one-frame flash, and a speaker-to-speaker cut at a line boundary is covered (flash or whip)
for ld in ([3.0] * 4, [3.04, 3.0, 3.0, 3.0], [3.17, 2.9, 3.31, 3.0], [3.43, 2.37, 3.31, 3.0]):
    SW = edit.schedule(ld, 1, 2, g, ld[0])
    sp = [x for x in SW["shots"] if x["kind"] in "SB" and "slam" not in x]
    assert all(x["t1"] - x["t0"] >= edit.MIN_SHOT - 1e-6 for x in sp), [(x["t0"], x["t1"]) for x in sp if x["t1"] - x["t0"] < edit.MIN_SHOT]
    assert all(abs(a["t1"] - b["t0"]) < 1e-9 for a, b in zip(SW["shots"], SW["shots"][1:])) and abs(SW["shots"][-1]["t1"] - SW["D"]) < 1e-6
    for a, b in zip(SW["shots"], SW["shots"][1:]):
        if a["kind"] == b["kind"] == "S" and any(abs(b["t0"] - x) < 0.02 for x, _ in SW["lines"][1:]):
            assert b["trans"] in ("flash", "whip"), ("bare jump cut", b, ld)
# a sliver is absorbed by its neighbour: a b-roll ending 0.04 s before the line boundary runs on to it
sh = [dict(t0=0, t1=1.0, kind="S", trans=None), dict(t0=1.0, t1=2.39, kind="B", trans="blur"), dict(t0=2.39, t1=2.43, kind="S", trans="blur"),
      dict(t0=2.43, t1=4.0, kind="S", trans="blur"), dict(t0=4.0, t1=5.0, kind="T", trans="whip")]
out = edit._tidy(sh, [(0, 2.43), (2.43, 4.0)])
assert [(x["t0"], x["t1"], x["kind"]) for x in out] == [(0, 1.0, "S"), (1.0, 2.43, "B"), (2.43, 4.0, "S"), (4.0, 5.0, "T")], out
out = edit._tidy([dict(t0=0, t1=2.43, kind="S", trans=None), dict(t0=2.43, t1=4.0, kind="S", trans="blur")], [(0, 2.43), (2.43, 4.0)])
assert out[1]["trans"] == "flash"

# --- audio cut points: the quietest 20 ms frame near the planned point, inside the window and the file
hop = edit.RMS_HOP
rms = np.full(100, 0.2)
rms[40:44] = 0.001; rms[10] = 0.0001; rms[90] = 0.0001   # a gap at 0.80-0.88 s, quieter frames far away
q = edit.quiet_point(rms, 0.9, -0.25, 0.35)
assert 0.80 <= q <= 0.88 and abs(edit.quiet_point(rms, 0.9, -0.05, 0.05) - 0.9) <= 0.05 + hop  # nothing quiet in reach: stays near the plan
assert edit.quiet_point(rms, 0.1, -0.35, 0.1) >= 0 and edit.quiet_point(rms, 1.99, -0.1, 0.35) <= 2.0  # never outside the file
q2 = edit.quiet_point(np.full(100, 0.01), 1.0, -0.25, 0.35)
assert abs(q2 - 1.0) <= hop, q2  # a flat floor: keep the planned point
w_ = {"w": "Hi", "s": 5.0, "e": 5.2}
assert abs(edit._words({"words": [w_]}, {"start": 5.0, "end": 6.0}, 10.0, t0=4.9)[0]["s"] - 10.1) < 1e-9  # captions follow the moved in point
# a pause between words (v3: "here" 112.30-112.72, "in" 113.42) splits the caption, so "in" never shows before it is said
pw = [{"w": "here", "s": 112.30, "e": 112.72}, {"w": "in", "s": 113.42, "e": 113.68}, {"w": "the", "s": 113.68, "e": 113.92}]
ws_ = edit._words({"words": pw}, {"start": 112.0, "end": 114.0}, 9.0)
assert abs(ws_[0]["e"] - (9.0 + 0.72)) < 1e-9, ws_   # a word ends where ASR says, not at the next word's start
assert [c["text"] for c in edit.C.group_words(ws_, max_words=2, max_chars=14)] == ["here", "in the"], edit.C.group_words(ws_)
assert edit._words({"words": [{"w": "a", "s": 1.0, "e": 3.0}, {"w": "b", "s": 1.5, "e": 1.8}]}, {"start": 0.0, "end": 4.0}, 0.0)[0]["e"] == 1.5  # capped at the next start
# the zoom on the speaker is capped so the face stays under FACE_MAX of the frame width
assert abs(edit.zoom_cap(100, 1920, 1080) - edit.FACE_MAX * 607.5 / 100) < 1e-6 and edit.zoom_cap(0, 1920, 1080) > 50
for cap in (1.0, 1.3, 1.9, 5.0):
    a_, b_ = edit.zoom_pair(1.24, cap)
    assert 1.0 <= a_ <= b_ <= max(cap, 1.0) + 1e-9, (cap, a_, b_)

# --- the tail effects: intensity rises over the tail from K0, peaks at the end, pulses on beats and only there
K = lambda t, pl=(): edit.tail_k(t, 10.0, 12.0, 20.0, pl)
assert K(9.9)[0] == 0 and 0 < K(11.0)[0] < K(12.0)[0] and abs(K(12.0)[0] - edit.TAIL_K0) < 1e-9
ks = [K(12.0 + 8 * u / 40)[0] for u in range(41)]
assert all(b >= a for a, b in zip(ks, ks[1:])) and abs(ks[-1] - 1.0) < 1e-9 and ks[20] < 0.8, ks
pl = [(15.0, 1.0), (16.0, 0.5)]
assert K(15.0, pl)[1] > K(15.0, [(15.0, 0.5)])[1] > 0 and K(15.5, pl)[1] == 0 and K(14.9, pl)[1] == 0 and K(15.0 + edit.PULSE_DUR + .01, pl)[1] == 0
assert K(15.05, pl)[1] > K(15.2, pl)[1] > 0 and max(K(t / 30, pl)[1] for t in range(300, 600)) <= 1.0
fr = np.random.RandomState(0).randint(0, 255, (1920, 1080, 3)).astype(np.uint8)
a, b = edit._tail_fx(fr.copy(), 0.0, 0.0, 0.0), edit._tail_fx(fr.copy(), 1.0, 0.5, 0.01)
assert np.array_equal(a, fr) and b.shape == fr.shape and b.dtype == np.uint8 and np.abs(b.astype(int) - fr).mean() > 3
assert np.array_equal(edit._tail_fx(fr.copy(), 0.6, 0.3, 0.01), edit._tail_fx(fr.copy(), 0.6, 0.3, 0.01))  # deterministic

# --- speed ramp: fast start, slow middle, fast end; the source needed is the integral of the curve; scaled down when the clip is short
FP = edit.FPS
pos, v, need = edit.speed_curve(3.0)
n = len(pos)
assert n == 3 * FP and len(v) == n and abs(v[0] - edit.RAMP_FAST) < 1e-6 and abs(v[n // 2] - edit.RAMP_SLOW) < 1e-6
lo = edit.RAMP_SLOW + 0.9 * (edit.RAMP_FAST - edit.RAMP_SLOW)
assert v[-1] > lo and v[-3] > lo - 0.5, v[-3:]
assert all(b <= a + 1e-9 for a, b in zip(v[:int(edit.RAMP_IN * FP)], v[1:])), "eases down over the first RAMP_IN"
assert all(abs(x - edit.RAMP_SLOW) < 1e-6 for x in v[int(edit.RAMP_IN * FP) + 1:n - int(edit.RAMP_OUT * FP) - 1]), "slow in the middle"
assert all(b >= a - 1e-9 for a, b in zip(v[n - int(edit.RAMP_OUT * FP) - 1:], v[n - int(edit.RAMP_OUT * FP):])), "eases up over the last RAMP_OUT"
tt = np.linspace(0, 3.0, 30001)
vv = np.interp(tt, np.arange(n) / FP, v)
assert abs(need - float(np.sum((vv[1:] + vv[:-1]) / 2 * np.diff(tt)))) < 0.03 * need and all(np.diff(pos) > 0) and abs(pos[-1] - (need - v[-1] / FP)) < 0.15, (need, pos[-1])
assert all(abs((b - a) * FP - x) < 0.35 * x + 0.05 for a, b, x in zip(pos, pos[1:], v))  # position advances at the speed
p2, v2, need2 = edit.speed_curve(3.0, avail=need / 2)
assert abs(need2 - need / 2) < 1e-6 and abs(v2[0] - v[0] / 2) < 1e-6 and abs(p2[-1] * 2 - pos[-1]) < 1e-6
assert edit.speed_curve(3.0, avail=need * 2)[2] == need   # a long clip is left alone
ps, vs_, ns_ = edit.speed_curve(0.5)  # a 1-beat shot is shorter than the ramps: still fast -> slow -> fast
assert len(ps) == 15 and vs_[0] > vs_[7] < vs_[-1] and ns_ > 0

# --- no picture twice in a row, even from a pool of two
pool, uses, prev, seq = [{"file": "a.jpg", "line": 0}, {"file": "b.jpg", "line": 0}], {}, None, []
for _ in range(8):
    it, _ss = edit._pick(pool, uses, 0, prev=prev)
    seq.append(it["file"]); prev = it["file"]
assert all(a != b for a, b in zip(seq, seq[1:])) and uses == {"a.jpg": 4, "b.jpg": 4}, seq
assert edit._pick(pool[:1], {}, 0, prev="a.jpg")[0]["file"] == "a.jpg"  # a pool of one cannot avoid it

fr0 = np.random.RandomState(1).randint(0, 255, (1920, 1080, 3)).astype(np.uint8)
assert np.abs(edit._tail_fx(fr0.copy(), 0.0, 0.0, 0.0, 1.0).astype(int) - fr0).mean() > 1  # speed alone blurs, even before the tail

# --- full render
def clip(name, w, h, d, hz=None):
    a = ["-f", "lavfi", "-i", f"sine=f={hz}:d={d}"] if hz else []
    ff("-f", "lavfi", "-i", f"testsrc2=s={w}x{h}:r=30:d={d}", *a, "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", *(["-c:a", "aac"] if hz else []), f"{run}/{name}.mp4")


clip("speaker", 640, 360, 14, 1000)
for i in range(3):
    clip(f"b{i}", 360, 640, 4)
    clip(f"t{i}", 640, 360, 4)
clip("f0", 1080, 1920, 3); clip("f1", 1080, 1920, 3)   # footage shots, already cropped 9:16 by the assets stage
for i in range(2):
    ff("-f", "lavfi", "-i", f"testsrc=s=800x600:d=1", "-frames:v", "1", f"{run}/p{i}.png")
ff("-f", "lavfi", "-i", "anoisesrc=d=90:c=pink:a=1.0", "-c:a", "aac", f"{run}/music.m4a")
words = lambda t, txt="They walked across the frozen sea for days": [{"w": w, "s": t + i * 0.3, "e": t + i * 0.3 + 0.25} for i, w in enumerate(txt.split())]
src = {"id": "spk", "url": "https://www.youtube.com/watch?v=spk", "duration": 100.0}
starts = [41.0, 45.0, 49.0]
plan = {"format": "edit", "musicOffset": 17.0, "dropLine": 1, "slams": ["28 YEARS", "31,000 MILES"],
        "popups": [{"text": "HE DID IT. 14 DAYS.", "line": 0}], "person": {"name": "Sam Test"},
        "clips": [{"key": f"l{i}", "source": src, "start": s, "end": s + 3.0, "person": True} for i, s in enumerate(starts)],
        "lines": [{"clip": f"l{i}", "text": "They walked across the frozen sea for days", "words": words(s + 0.2, "They walked across um the frozen sea for days" if i == 0 else "They walked across the frozen sea for days")} for i, s in enumerate(starts)]}
assets = {"broll": [{"line": i, "file": f"b{i}.mp4", "kind": "video"} for i in range(3)],
          "tail": [{"file": "p0.png", "kind": "image"}, {"file": "t0.mp4", "kind": "video"}, {"file": "t1.mp4", "kind": "video"}],
          "person": [{"file": "p1.png", "kind": "image", "credit": "Photo: Sam Test / CC BY", "licence": "CC BY"}],
          "footage": [{"file": f"f{i}.mp4", "kind": "video", "credit": f"Footage: https://www.youtube.com/watch?v=f{i} (Movieclips)", "page": "u"} for i in range(2)]}
an = {"bpm": BPM, "beats": [k * PER for k in range(180)], "drop": 20.0, "duration": 90.0}
job = {"plan": plan, "clips": [{"role": "moment", "file": "speaker.mp4", "offset": 40.0, "duration": 14.0, "sourceId": "spk"}] * 3,
       "assets": assets, "track": {"file": "music.m4a", "title": "Fixture", "analysis": an}}
t0 = __import__("time").time()
import numpy as np
np.save(f"{run}/identity.npy", np.ones(128, np.float32))
seen, _track = [], edit.facecrop.track
edit.facecrop.track = lambda *a, **k: (seen.append(k), _track(*a, **{**k, "ref": None}))[1]
used, _asm = [], edit._assemble
edit._assemble = lambda shots, *a, **k: (used.extend((x["kind"], Path(x.get("file") or "").name) for x in shots), _asm(shots, *a, **k))[1]
import hashlib
_fx_ = edit.editfx
_orig = (_fx_.subject, _fx_.transition, _fx_.fry, edit._tail_fx, _fx_.look)
tr_calls, tail_in, n_fry, tot, looks = [], [], [0], [], []
H_ = lambda x: hashlib.md5(np.ascontiguousarray(x).tobytes()).hexdigest()
def _tr(kind, out_fr, in_fr, u, *a, **k):
    tr_calls.append((kind, u, H_(out_fr), tail_in[-1] if tail_in else None))
    return _orig[1](kind, out_fr, in_fr, u, *a, **k)
def _fry(fr):
    n_fry[0] += 1
    return _orig[2](fr)
def _tfx(fr, *a, **k):
    tail_in.append(H_(fr))
    return _orig[3](fr, *a, **k)
def _subj(fr, models, prev=None):   # no models in tests: a centred box as the subject
    m = np.zeros(fr.shape[:2], np.float32); m[fr.shape[0] // 4:3 * fr.shape[0] // 4, fr.shape[1] // 4:3 * fr.shape[1] // 4] = 1
    return m
def _look(kind, fr, m, hist=(), bgs=(), t=0.0, pulse=0.0, n=0):
    looks.append((kind, round(t, 3), pulse, n, len(bgs)))
    return _orig[4](kind, fr, m, hist, bgs, t, pulse, n)
_fx_.subject, _fx_.transition, _fx_.fry, edit._tail_fx, _fx_.look = _subj, _tr, _fry, _tfx, _look
_asm2 = edit._assemble
edit._assemble = lambda shots, spk, dst, total, *a, **k: (tot.append(total), _asm2(shots, spk, dst, total, *a, **k))[1]
out = edit.render(job, {"models": "/nonexistent"}, run)
edit.facecrop.track, edit._assemble = _track, _asm
_fx_.subject, _fx_.transition, _fx_.fry, edit._tail_fx, _fx_.look = _orig
# real-first: every tail shot is the person's footage or photo, and the speech cuts away to it too
real = ("f0.mp4", "f1.mp4", "p1.png")
assert all(f in real for k, f in used if k == "T") and any(k == "B" and f in real for k, f in used), used   # real material in every tail shot and the speech
assert "Footage: https://www.youtube.com/watch?v=f0 (Movieclips)" in out["credits"]
assert seen and all(k.get("ref") is not None and k.get("models") == "/nonexistent" for k in seen), seen  # ref and models reach every track call
# effects: fry once per output frame; transitions only for tail kinds, each starting from the previous shot's last pre-_tail_fx frame
assert n_fry[0] == tot[0] == len(tail_in), (n_fry, tot, len(tail_in))
got = {c[0] for c in tr_calls}
want = set(edit.TAIL_BIG + edit.TAIL_SMALL + ["stutter"])
assert got <= want and got >= want - {"stutter"} and tr_calls, (got, want)
# montage looks: every look in turn, on every frame of the non-stutter tail shots, flaring on the beats
assert {x[0] for x in looks} == set(_fx_.LOOKS), {x[0] for x in looks}
assert max(x[2] for x in looks) > 0.9 and min(x[2] for x in looks) < 0.1 and len({x[3] for x in looks}) >= 6, looks[:5]
assert any(x[0] == "swap" and x[4] for x in looks)   # swap gets earlier shots as backgrounds
first = [c for i, c in enumerate(tr_calls) if i == 0 or c[1] <= tr_calls[i - 1][1]]
assert len(first) >= 6 and all(c[2] == c[3] for c in first), [c[:2] for c in first if c[2] != c[3]]
print("render s", round(__import__("time").time() - t0, 1))
f = Path(run) / out["short"]["file"]
assert f.exists()
pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration", "-of", "json", str(f)]))
v = [s for s in pr["streams"] if s["codec_type"] == "video"][0]
assert (v["width"], v["height"]) == (1080, 1920) and v["r_frame_rate"] == "30/1", v
assert "Photo: Sam Test / CC BY" in out["credits"]
assert any(s["codec_type"] == "audio" for s in pr["streams"])
dur = float(pr["format"]["duration"])
tl = out["timeline"]
assert abs(dur - tl[-1]["end"]) <= 0.3 and abs(out["short"]["duration"] - dur) <= 0.3 and out["credits"], (dur, tl[-1])
assert tl[0]["start"] == 0 and all(abs(a["end"] - b["start"]) < 1e-6 for a, b in zip(tl, tl[1:])), tl
kinds = [e["kind"] for e in tl]
assert kinds[-1] == "tail" and "slam" in kinds and kinds.index("slam") > 0 and set(kinds) <= {"speech", "slam", "hold", "tail"}, kinds
# b-roll cutaways inside the speech are not person shots: the gate must not look for the speaker in stock footage (live
# 2026-11-08: Alex Honnold's edit failed the gate on a stock climber and a gloved hand)
assert any(e["kind"] == "speech" and not e["person"] for e in tl) and any(e["kind"] == "speech" and e["person"] for e in tl), tl
last_speech = max(e["end"] for e in tl if e["kind"] == "speech")
tailE = tl[-1]
assert tailE["start"] >= last_speech and abs(tailE["end"] - tailE["start"] - edit.TAIL_S) <= 1.0, (tailE, dur)
# the "um" (0.25 s) is cut from line 0: the line is that much shorter and the music shifts with it, so the drop line still starts on the music's drop
cut0 = out["musicOffset"] - plan["musicOffset"]
assert abs(cut0 - 0.25) <= 0.06, cut0
assert any(abs(e["start"] - (an["drop"] - out["musicOffset"])) < 1e-6 for e in tl) and abs((an["drop"] - out["musicOffset"]) - (3.0 - cut0)) <= 0.06  # line 0 really is shorter


def lufs(a, b, af=""):
    r = subprocess.run(["ffmpeg", "-nostats", "-ss", str(a), "-t", str(b - a), "-i", str(f), "-vn", "-af", af + "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])


assert abs(lufs(0, dur) + 14) <= 2, lufs(0, dur)
tone = "bandpass=f=1000:width_type=h:w=30,"   # the speech fixture is a 1 kHz sine, the music is pink noise
assert lufs(0.3, 2.5, tone) > lufs(tailE["start"] + 0.5, tailE["end"] - 0.5, tone) + 6, "voice must stop in the tail"
assert lufs(tailE["start"] + 0.5, tailE["end"] - 0.5) > lufs(0, dur) - 4, "music keeps its intensity in the tail"
# sensitive wording: slams and pop-ups draw the caption form
from trending import captions as _C
import numpy as _np
assert _np.array_equal(_np.asarray(_C.StatSlams([])._img("Raped")), _np.asarray(_C.StatSlams([])._img("R*ped")))
assert _np.array_equal(_np.asarray(_C.PopupCards([])._img("A murder")), _np.asarray(_C.PopupCards([])._img("A m*rder")))
# a line marked cover (someone else on camera) shows no speaker shot: its audio stays, the picture is a cutaway
sh = [dict(t0=0, t1=1, kind="S"), dict(t0=1, t1=2, kind="B"), dict(t0=2, t1=3.5, kind="S"), dict(t0=3.5, t1=4, kind="S")]
edit.cover(sh, [(0, 1.5), (1.5, 3.2), (3.2, 4)], [False, True, False])
assert [x["kind"] for x in sh] == ["S", "B", "B", "S"], sh
# stock clips that fade in or out of black: shots use only the picture between (live 2026-11-09: a Pexels clip black for its
# first 1.2 s left a black tail shot and the gate failed)
_bp = Path(tempfile.mkdtemp()) / "fade.mp4"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=black:s=160x284:r=30:d=1.2", "-f", "lavfi", "-i", "testsrc=s=160x284:r=30:d=3",
                "-f", "lavfi", "-i", "color=black:s=160x284:r=30:d=0.8", "-filter_complex", "[0][1][2]concat=n=3:v=1", "-pix_fmt", "yuv420p", str(_bp)], check=True)
a_, b_ = edit.picture_span(str(_bp))
assert abs(a_ - 1.2) < 0.1 and abs(b_ - 4.2) < 0.1, (a_, b_)
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=black:s=160x284:r=30:d=3", "-f", "lavfi", "-i", "testsrc=s=160x284:r=30:d=0.6",
                "-filter_complex", "[0][1]concat=n=2:v=1", "-pix_fmt", "yuv420p", str(_bp)], check=True)
assert edit.picture_span(str(_bp)) is None   # 0.6 s of picture: not usable
# lines that run on in the source play as one stretch: the next line's start is the join, neither side is moved to a quiet
# point and there is no fade (live 2026-11-09: "building" and "notified" played twice where the snapped edges overlapped)
src_ = lambda a, b, sid="v1": {"start": a, "end": b, "source": {"id": sid}}
assert edit.runs_on(src_(456.78, 457.99), src_(457.839, 460.0))          # overlap
assert edit.runs_on(src_(456.0, 457.0), src_(457.2, 460.0))              # a short gap
assert not edit.runs_on(src_(456.0, 457.0), src_(458.0, 460.0))          # a skipped sentence
assert not edit.runs_on(src_(456.0, 457.0), src_(457.0, 460.0, "v2"))    # another video
# a line that stops mid-phrase runs on through the words that follow closely, up to a phrase starter (live 2026-11-18: "obsessed" was clipped)
W_ = lambda *a: [dict(w=w, s=s, e=e) for w, s, e in a]
ws_ = W_(("it", 6.96, 7.08), ("just", 7.08, 7.259), ("said", 7.259, 7.379), ("obsessed", 7.379, 7.9), ("with", 7.98, 8.04), ("you", 8.04, 8.22), ("and", 8.22, 8.4), ("I", 8.4, 8.5))
e_, add_ = edit.phrase_end(ws_, 7.59)
assert abs(e_ - 8.22) < 0.02 and [w["w"] for w in add_] == ["with", "you"], (e_, add_)
assert edit.phrase_end(W_(("it", 6.96, 7.08), ("obsessed", 7.379, 7.7), ("with", 8.5, 8.6)), 7.59) == (7.59, [])   # a pause: unchanged
e2_, a2_ = edit.phrase_end(W_(("a", 7.0, 7.2), ("b", 7.3, 7.5), ("and", 7.5, 7.8), ("c", 7.8, 8.0)), 7.4)
assert a2_ == [] and e2_ == 7.4, (e2_, a2_)   # stops before "and": unchanged
long_ = W_(*[(f"w{k}", 7.0 + 0.3 * k, 7.0 + 0.3 * k + 0.3) for k in range(12)])
e3_, a3_ = edit.phrase_end(long_, 7.1, max_ext=1.2)
assert e3_ <= 8.3 + 1e-6 and len(a3_) >= 2, (e3_, a3_)   # capped at end + max_ext
print("ok")
