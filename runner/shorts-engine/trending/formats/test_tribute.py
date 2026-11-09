# tribute.render on a tiny synthetic fixture. Run: python3 test_tribute.py (prints ok)
import json, os, re, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trending.formats import tribute

run = tempfile.mkdtemp()
ff = lambda *a: subprocess.run(["ffmpeg", "-y", "-v", "error", *a], check=True)


def clip(name, hz):  # 6 s testsrc2 640x360 with a loud tone
    ff("-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=6", "-f", "lavfi", "-i", f"sine=f={hz}:d=6", "-shortest",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", f"{run}/{name}.mp4")
    return {"role": "moment", "file": f"{name}.mp4", "offset": 0.0, "duration": 6.0, "sourceId": name}


names = ["m0", "m1", "spine0", "spine1"]
clips = [clip(n, 300 + 100 * i) for i, n in enumerate(names)]
ff("-f", "lavfi", "-i", "anoisesrc=d=60:c=pink:a=0.3", "-c:a", "aac", f"{run}/music.m4a")
words = lambda t: [{"w": w, "s": t + i * 0.3, "e": t + i * 0.3 + 0.25} for i, w in enumerate("How would I want to be remembered by the people".split())]
src = lambda n: {"id": n, "url": f"https://www.youtube.com/watch?v={n}", "duration": 100.0}
plan = {"format": "tribute", "person": {"name": "Sir Test", "years": "1940 – 2026"}, "musicOffset": 0.0,
        "clips": [{"key": k, "source": src(k), "start": 1.0, "end": e, "person": True} for k, e in
                  [("m0", 3.0), ("m1", 3.0), ("spine0", 4.0), ("spine1", 4.0)]],
        "name": "Sir Test", "years": "1940 – 2026",
        "spine": [{"clip": "spine0", "text": "How would I want to be remembered by the people", "words": words(1.3)},
                  {"clip": "spine1", "text": "How would I want to be remembered by the people", "words": words(1.3)}],
        "moments": [{"clip": "m0"}, {"clip": "m1"}], "closingLine": "A life on the stage, and a voice for the unheard."}
# plan.clips order must match job.clips (media-fetch output); clips above are in the same order
job = {"plan": plan, "clips": clips, "assets": {}, "track": {"file": "music.m4a", "title": "Fixture", "analysis": {"drop": 20.0}}}
t0 = __import__("time").time()
import numpy as np
np.save(f"{run}/identity.npy", np.ones(128, np.float32))
seen, _track = [], tribute.facecrop.track
tribute.facecrop.track = lambda *a, **k: (seen.append(k), _track(*a, **{**k, "ref": None}))[1]
out = tribute.render(job, {"models": "/nonexistent"}, run)
tribute.facecrop.track = _track
assert seen and all(k.get("ref") is not None and k.get("models") == "/nonexistent" for k in seen), seen  # ref and models reach every track call
print("render s", round(__import__("time").time() - t0, 1))
f = Path(run) / out["short"]["file"]
assert f.exists()
pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration", "-of", "json", str(f)]))
v = [s for s in pr["streams"] if s["codec_type"] == "video"][0]
assert (v["width"], v["height"]) == (1080, 1920) and v["r_frame_rate"] == "30/1", v
assert any(s["codec_type"] == "audio" for s in pr["streams"])
dur = float(pr["format"]["duration"])
tl = out["timeline"]
assert abs(dur - tl[-1]["end"]) <= 0.3 and abs(dur - plan.get("predictedDuration", dur)) <= 0.3, (dur, tl[-1])
assert tl[0]["start"] == 0 and all(abs(a["end"] - b["start"]) < 1e-6 for a, b in zip(tl, tl[1:])), tl
assert [e["kind"] for e in tl] == ["moment", "spine", "spine", "closing"], tl
assert abs(out["short"]["duration"] - dur) <= 0.3 and out["credits"]


def lufs(a, b):
    r = subprocess.run(["ffmpeg", "-nostats", "-ss", str(a), "-t", str(b - a), "-i", str(f), "-vn", "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])


whole = lufs(0, dur)
assert abs(whole + 14) <= 2, whole
sp, mo = tl[1], tl[0]
assert lufs(sp["start"] + 0.8, sp["end"] - 0.8) > lufs(mo["start"] + 0.3, mo["end"] - 0.3) + 3, "spine must be louder than moments"
# sensitive wording: text layers draw the caption form (identical PNG bytes)
png = lambda txt: (tribute._text_png([(txt, 60, False, 900)], p := Path(run) / "s.png"), p.read_bytes())[1]
assert png("He was raped") == png("He was r*ped") and png("He was raped") != png("He was robbed")
print("ok")
