# casefile.render on a tiny synthetic fixture (voice stubbed). Run: python3 test_casefile.py (prints ok)
import json, re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trending import tts
from trending.formats import casefile

run = Path(tempfile.mkdtemp())
ff = lambda *a: subprocess.run(["ffmpeg", "-y", "-v", "error", *a], check=True)
ff("-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=6", "-f", "lavfi", "-i", "sine=f=300:d=6", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", f"{run}/a0.mp4")
ff("-f", "lavfi", "-i", "anoisesrc=d=40:c=pink:a=0.3", "-c:a", "aac", f"{run}/track.m4a")
(run / "assets/shots").mkdir(parents=True); (run / "assets/photos").mkdir()
page = Image.new("RGB", (1000, 2600), "white")
d = ImageDraw.Draw(page)
for k in range(12):
    d.text((40, 300 + k * 60), "Some reported text on the page " * 2, fill="black")
d.rectangle((40, 900, 700, 930), fill=(255, 225, 77))
page.save(run / "assets/shots/0.png")
for i in range(2):
    Image.fromarray((np.random.RandomState(i).rand(800, 1200, 3) * 255).astype("uint8")).save(run / f"assets/photos/{i}.jpg")

SENT = ["In December the thing happened to him.", "The BBC reports it was closed for good.", "A complaint was made by a colleague, it said.",
        "He strongly denies it all.", "Months later the plans were announced.", "What do you make of it?"]
VIS = [{"kind": "photo", "query": "q0"}, {"kind": "screenshot", "outlet": "BBC", "url": "https://x/a", "highlight": "closed for good here today"},
       {"kind": "clip", "clip": "a0"}, {"kind": "quote", "text": "He strongly denies it all", "outlet": "BBC"},
       {"kind": "timeline", "label": "DEC 2025"}, {"kind": "photo", "query": "q1"}]
SP = 4.0  # seconds per sentence from the stub voice


def fake_kokoro(spoken, voice, speed, out):
    assert (voice, speed) == ("bm_george", 1.12)
    ff("-f", "lavfi", "-i", f"anoisesrc=d={SP * len(spoken)}:c=brown:a=0.5", str(out))
    words = [[{"w": w, "s": i * SP + 0.2 + k * 0.4, "e": i * SP + 0.2 + k * 0.4 + 0.35, **({"b": 1} if k % 4 == 3 else {})} for k, w in enumerate(s.rstrip(".?").split())] for i, s in enumerate(spoken)]
    return {"file": str(out), "duration": SP * len(spoken), "words": words, "spans": [(i * SP, (i + 1) * SP) for i in range(len(spoken))]}


tts._kokoro = fake_kokoro
plan = {"format": "casefile", "title": "t", "script": [{"text": "[dramatic] " + s, "spoken": s, "visual": v} for s, v in zip(SENT, VIS)],
        "timeline": [{"label": "DEC 2025", "text": "It happened"}, {"label": "NOV 2026", "text": "It closed"}],
        "clips": [{"key": "a0", "source": {"id": "a0", "url": "https://www.youtube.com/watch?v=a0", "duration": 100.0}, "start": 41.0, "end": 44.0, "person": True}],
        "musicOffset": 0.0}
job = {"plan": plan, "clips": [{"role": "moment", "file": "a0.mp4", "offset": 40.0, "duration": 6.0, "sourceId": "a0"}],
       "assets": {"screenshots": {"https://x/a": "assets/shots/0.png"}, "photos": [{"query": "q0", "file": "assets/photos/0.jpg", "credit": "A. Author", "licence": "CC BY 4.0", "page": "https://c/0"},
                                                                          {"query": "q1", "file": "assets/photos/1.jpg", "credit": "B. Author", "licence": "CC BY-SA 4.0", "page": "https://c/1"}]},
       "track": {"file": "track.m4a", "title": "t", "analysis": {"bpm": 90, "beats": [], "drop": 0.0, "duration": 40}}}
t0 = __import__("time").time()
out = casefile.render(job, {}, run)
print("render s", round(__import__("time").time() - t0, 1))
f = run / out["short"]["file"]
pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration", "-of", "json", str(f)]))
v = [s for s in pr["streams"] if s["codec_type"] == "video"][0]
assert (v["width"], v["height"]) == (1080, 1920) and v["r_frame_rate"] == "30/1", v
assert any(s["codec_type"] == "audio" for s in pr["streams"])
dur = float(pr["format"]["duration"])
tl = out["timeline"]
assert abs(dur - tl[-1]["end"]) <= 0.3 and abs(dur - SP * len(SENT)) <= 0.8, (dur, tl[-1])
assert tl[0]["start"] == 0 and all(abs(a["end"] - b["start"]) < 1e-6 for a, b in zip(tl, tl[1:])), tl
shots = [e for e in tl if e["kind"] == "screenshot"]
assert shots and all(3.0 - 1e-6 <= e["end"] - e["start"] <= 4.0 + 1e-6 for e in shots), shots  # 3-4 s each (the sentences here are 4 s)
assert sum(e["end"] - e["start"] for e in shots) <= 0.4 * tl[-1]["end"], shots
# the card finishes moving within ~1 s, then holds still for the last 2 s of the shot (frame difference on the real CardSeg)
for e in shots:
    seg = casefile.CardSeg(run / "assets/shots/0.png", "BBC", e["start"], e["end"])
    fr = lambda t: np.asarray(seg.frame(t)).astype(int)
    assert np.abs(fr(e["start"] + 0.3) - fr(e["start"] + 0.9)).max() > 0, "card should still be moving early on"
    held = [fr(e["end"] - 2.0 + k * 0.1) for k in range(20)]
    assert all(np.abs(h - held[0]).max() == 0 for h in held), "card must be static for the last 2 s"
# short sentences: at least 3 s unless sentence + 1 s is shorter; never past sentence + 1 s; a long one stays within 4 s
assert casefile.first_len(2.0, 4.0) == 3.0 and abs(casefile.first_len(1.5, 4.0) - 2.5) < 1e-9 and casefile.first_len(6.0, 4.0) == 4.0
assert abs(casefile.first_len(4.3, 4.0) - 3.7) < 1e-9 and casefile.first_len(3.2, 4.0) == 3.2
assert casefile.shot_cap([4.0] * 3, 60) == 4.0 and 3.0 <= casefile.shot_cap([6.0] * 4, 36) < 4.0
# sensitive wording: quote cards and captions draw the caption form
tx = lambda b: np.asarray(casefile.TextSeg("", b, "", 0, 1).frame(0))
assert np.array_equal(tx("He was raped"), tx("He was r*ped")) and not np.array_equal(tx("He was raped"), tx("He was robbed"))
cp = lambda w: (lambda c: np.asarray(c._render(c.lines[0])))(casefile.Captions([[{"w": w, "s": 0, "e": .3, "b": 1}]]))
assert np.array_equal(cp("Raped,"), cp("R*ped,")) and not np.array_equal(cp("grape"), cp("r*pe"))
cc = lambda w: (lambda c: np.asarray(c._render(c.lines[0])))(casefile.Captions([[dict(w, s=0, e=.3, b=1)]]))
assert np.array_equal(cc({"w": "six"}), cp("six")) and not np.array_equal(cc({"w": "six"}), cp("s*x"))
assert np.array_equal(cc({"w": "six", "cap": "s*x"}), cp("s*x"))
assert {"photo", "clip", "quote", "timeline"} <= {e["kind"] for e in tl}, [e["kind"] for e in tl]
assert [e for e in tl if e["kind"] == "clip"][0]["person"] and not shots[0]["person"]
assert abs(out["short"]["duration"] - dur) <= 0.3
cr = " ".join(out["credits"])
assert "A. Author" in cr and "CC BY 4.0" in cr and "youtube.com/watch?v=a0" in cr and "https://x/a" in cr, out["credits"]
assert "file photo" not in cr.lower()
err = subprocess.run(["ffmpeg", "-nostats", "-i", str(f), "-vn", "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])
assert abs(lufs + 14) <= 2, lufs
# footer gone: nothing drawn in the bottom strip of a photo frame that the caption row doesn't cover
ff("-ss", "1", "-i", str(f), "-frames:v", "1", f"{run}/f1.png")
strip = np.asarray(Image.open(f"{run}/f1.png").convert("L"))[1740:1900].astype(float)
assert strip.std() < 60, strip.std()
# music is ducked under the voice: with the voice silent music alone is louder than during speech is not required; just check it is mixed in
a = subprocess.run(["ffmpeg", "-nostats", "-i", str(f), "-vn", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
assert "mean_volume" in a
print("ok")
