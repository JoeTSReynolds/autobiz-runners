# edit.render on a tiny synthetic fixture. Run: python3 test_edit.py (prints ok)
import json, numpy as np, re, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trending.formats import edit

run = tempfile.mkdtemp()
ff = lambda *a: subprocess.run(["ffmpeg", "-y", "-v", "error", *a], check=True)
BPM, PER = 120.0, 0.5

# --- pure scheduling: cut rate speeds up after the drop, the tail is on the grid (2 beats, then 1 beat in the last 5 s)
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
for s in tail:
    n = (s["t1"] - s["t0"]) / PER
    assert abs(n - round(n)) < 1e-6 and round(n) == (1 if s["t0"] >= S["D"] - 5 - 1e-6 else 2), s
assert 0.30 <= (S["D"] - S["tT"]) / S["D"] <= 0.40 and S["tT"] >= S["lines"][-1][1], S
assert {"whip", "punch", "flash", "shake"} <= {s["trans"] for s in tail}

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

# --- person photos: about 1 in 3 tail shots, never adjacent; without photos one or two speaker moments, spread
for nT in range(3, 40):
    sl = sorted(edit.tail_slots(nT, True))
    assert sl and all(b - a >= 3 for a, b in zip(sl, sl[1:])) and abs(len(sl) - nT / 3) <= 1 and max(sl) < nT, (nT, sl)
    sp = sorted(edit.tail_slots(nT, False))
    assert 1 <= len(sp) <= 2 and all(b - a >= 2 for a, b in zip(sp, sp[1:])) and max(sp) < nT, (nT, sp)
assert edit.tail_slots(0, True) == set() and edit.tail_slots(2, False) == set()
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
          "person": [{"file": "p1.png", "kind": "image", "credit": "Photo: Sam Test / CC BY"}]}
an = {"bpm": BPM, "beats": [k * PER for k in range(180)], "drop": 20.0, "duration": 90.0}
job = {"plan": plan, "clips": [{"role": "moment", "file": "speaker.mp4", "offset": 40.0, "duration": 14.0, "sourceId": "spk"}] * 3,
       "assets": assets, "track": {"file": "music.m4a", "title": "Fixture", "analysis": an}}
t0 = __import__("time").time()
import numpy as np
np.save(f"{run}/identity.npy", np.ones(128, np.float32))
seen, _track = [], edit.facecrop.track
edit.facecrop.track = lambda *a, **k: (seen.append(k), _track(*a, **{**k, "ref": None}))[1]
out = edit.render(job, {"models": "/nonexistent"}, run)
edit.facecrop.track = _track
assert seen and all(k.get("ref") is not None and k.get("models") == "/nonexistent" for k in seen), seen  # ref and models reach every track call
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
assert tailE["start"] >= last_speech and (tailE["end"] - tailE["start"]) / dur >= 0.30, (tailE, dur)
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
print("ok")
