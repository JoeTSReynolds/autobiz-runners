# topn.render on a tiny synthetic fixture. Run: python3 test_topn.py (prints ok)
import json, re, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trending.formats import topn

run = tempfile.mkdtemp()
ff = lambda *a: subprocess.run(["ffmpeg", "-y", "-v", "error", *a], check=True)
N = 3


def clip(name, hz):  # 6 s testsrc2 640x360 with a tone, as media-fetch would deliver (file time = source time - offset)
    ff("-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=6", "-f", "lavfi", "-i", f"sine=f={hz}:d=6", "-shortest",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", f"{run}/{name}.mp4")
    return {"role": "moment", "file": f"{name}.mp4", "offset": 40.0, "duration": 6.0, "sourceId": name}


keys = [f"t{i}" for i in range(N)]
clips = [clip(k, 300 + 100 * i) for i, k in enumerate(keys)]
words = lambda t: [{"w": w, "s": t + i * 0.3, "e": t + i * 0.3 + 0.25} for i, w in enumerate("Is there a chance of you becoming the next one".split())]
plan = {"format": "topn", "person": {"name": "Sam Test"}, "n": N, "title": "Top 3 times Sam Test dodged the Bond question",
        "clips": [{"key": k, "source": {"id": k, "url": f"https://www.youtube.com/watch?v={k}", "duration": 100.0}, "start": 41.0, "end": 44.0, "person": True} for k in keys],
        "moments": [{"clip": k, "rank": N - i, "label": f"Label {N - i}", "words": words(41.2)} for i, k in enumerate(keys)],
        "closer": {"headline": "x", "line1": "THIS WEEK SOMEONE CALLED HIM SO STRONG", "line2": "STILL DODGING? 👀"}}
job = {"plan": plan, "clips": clips, "assets": {}, "track": None}
t0 = __import__("time").time()
import numpy as np
np.save(f"{run}/identity.npy", np.ones(128, np.float32))
seen = []
_track = topn.facecrop.track
topn.facecrop.track = lambda *a, **k: (seen.append(k), _track(*a, **{**k, "ref": None}))[1]
out = topn.render(job, {"models": "/nonexistent"}, run)
topn.facecrop.track = _track
assert len(seen) == N + 1 and all(k.get("ref") is not None and k.get("models") == "/nonexistent" for k in seen[:N]), seen
print("render s", round(__import__("time").time() - t0, 1))
f = Path(run) / out["short"]["file"]
assert f.exists()
pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration", "-of", "json", str(f)]))
v = [s for s in pr["streams"] if s["codec_type"] == "video"][0]
assert (v["width"], v["height"]) == (1080, 1920) and v["r_frame_rate"] == "30/1", v
assert any(s["codec_type"] == "audio" for s in pr["streams"])
dur = float(pr["format"]["duration"])
tl = out["timeline"]
assert abs(dur - tl[-1]["end"]) <= 0.3 and abs(dur - (3.0 * N + topn.CLOSER)) <= 0.3, (dur, tl[-1])
assert tl[0]["start"] == 0 and all(abs(a["end"] - b["start"]) < 1e-6 for a, b in zip(tl, tl[1:])), tl
assert [e["kind"] for e in tl] == ["moment"] * N + ["closer"], tl
assert abs(out["short"]["duration"] - dur) <= 0.3 and out["credits"]
cut = Path(run) / "cut"
assert all((cut / f"list_{i}.png").exists() for i in range(1, N + 1)) and not (cut / f"list_{N + 1}.png").exists()  # N rank-list states
from PIL import Image
assert Image.open(cut / f"list_{N}.png").height >= 118 * N  # N numbered rows


def lufs(a, b):
    r = subprocess.run(["ffmpeg", "-nostats", "-ss", str(a), "-t", str(b - a), "-i", str(f), "-vn", "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])


assert abs(lufs(0, dur) + 14) <= 2, lufs(0, dur)
# sensitive wording: every label/line drawn is the caption form (identical PNG bytes)
sp = Path(run) / "s.png"
png = lambda call: (call(sp), sp.read_bytes())[1]
W_ = (255, 255, 255)
assert png(lambda o: topn._caption("He raped her", o)) == png(lambda o: topn._caption("He r*ped her", o))
assert png(lambda o: topn._rank_list({1: "Murder claim"}, 1, o)) == png(lambda o: topn._rank_list({1: "M*rder claim"}, 1, o))
assert png(lambda o: topn._header([("The rapist", 80, W_)], o)) == png(lambda o: topn._header([("The r*pist", 80, W_)], o))
assert png(lambda o: topn._stack([("KILLED HIM", W_)], o, 90)) == png(lambda o: topn._stack([("K*LLED HIM", W_)], o, 90))
print("ok")
