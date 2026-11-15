# tts.narrate: ElevenLabs path (HTTP stubbed) and cache. Run: python3 test_tts.py (prints ok)
import base64, json, os, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trending import tts

run, cache2 = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
os.environ["AUTOBIZ_TTS_CACHE"] = str(cache2)
os.environ["ELEVEN_LABS_API_KEY"] = "test"
texts = ["[dramatic] In December, it began.", "He denies it. [pause] Fully."]
full = " ".join(texts)
mp3 = run / "x.mp3"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=f=200:d=5", str(mp3)], check=True)
al = {"characters": list(full), "character_start_times_seconds": [i * 0.1 for i in range(len(full))], "character_end_times_seconds": [i * 0.1 + 0.09 for i in range(len(full))]}
calls = []


def fake(url, body, key):
    calls.append((url, json.loads(body)))
    return json.dumps({"audio_base64": base64.b64encode(mp3.read_bytes()).decode(), "alignment": al}).encode()


tts._post = fake
out = tts.narrate(texts, ["In December, it began.", "He denies it. Fully."], {"voice": "elevenlabs"}, run)
assert len(calls) == 1 and "JBFqnCBsd6RMkjVDRZzb" in calls[0][0] and calls[0][1]["model_id"] == "eleven_v4_turbo", calls
assert calls[0][1]["text"] == full  # tags go to ElevenLabs
ws = [[w["w"] for w in item] for item in out["words"]]
assert ws == [["In", "December", "it", "began"], ["He", "denies", "it", "Fully"]], ws  # no tags, no punctuation
assert all("[" not in w["w"] for item in out["words"] for w in item)
assert out["words"][0][0]["s"] == al["character_start_times_seconds"][len("[dramatic] ")]
assert out["spans"][0][0] == 0 and out["spans"][0][1] == out["spans"][1][0] and out["spans"][1][1] == out["duration"], out["spans"]
assert Path(out["file"]).exists() and out["duration"] > 4.9
assert list((run / "cut" / "tts-cache").glob("*.json")) and list(cache2.glob("*.json"))  # both caches written
# re-render costs nothing, from either cache
import shutil
tts.narrate(texts, ["a", "b"], {"voice": "elevenlabs"}, run)
shutil.rmtree(run / "cut" / "tts-cache")
tts.narrate(texts, ["a", "b"], {"voice": "elevenlabs"}, Path(tempfile.mkdtemp()))
assert len(calls) == 1, calls
# other voice id / model are honoured and change the cache key
tts.narrate(texts, ["a", "b"], {"voice": "elevenlabs", "elevenVoice": "V2", "elevenModel": "m2"}, Path(tempfile.mkdtemp()))
assert len(calls) == 2 and "/V2/" in calls[1][0] and calls[1][1]["model_id"] == "m2"
# sensitive terms: the voice gets the spoken form, tags are kept, alignment is checked against the substituted text
n0 = len(calls)
sub = "[dramatic] He graped her. [pause] It was unalive."
al2 = {"characters": list(sub), "character_start_times_seconds": [i * 0.1 for i in range(len(sub))], "character_end_times_seconds": [i * 0.1 + 0.09 for i in range(len(sub))]}
tts._post = lambda url, body, key: calls.append((url, json.loads(body))) or json.dumps({"audio_base64": base64.b64encode(mp3.read_bytes()).decode(), "alignment": al2}).encode()
o2 = tts.narrate(["[dramatic] He raped her. [pause] It was murder."], ["He raped her. It was murder."], {"voice": "elevenlabs"}, Path(tempfile.mkdtemp()))
assert len(calls) == n0 + 1 and calls[-1][1]["text"] == sub, calls[-1]
assert [w["w"] for w in o2["words"][0]] == ["He", "graped", "her", "It", "was", "unalive"], o2["words"]
# captions come from the original words: a genuine "six" stays, a substituted "sex" gets its caption form
sx = "Six women alleged six."
al3 = {"characters": list(sx), "character_start_times_seconds": [i * 0.1 for i in range(len(sx))], "character_end_times_seconds": [i * 0.1 + 0.09 for i in range(len(sx))]}
tts._post = lambda url, body, key: json.dumps({"audio_base64": base64.b64encode(mp3.read_bytes()).decode(), "alignment": al3}).encode()
o3 = tts.narrate(["Six women alleged sex."], ["Six women alleged sex."], {"voice": "elevenlabs"}, Path(tempfile.mkdtemp()))
assert [w["cap"] for w in o3["words"][0]] == ["Six", "women", "alleged", "s*x"], o3["words"]
# mismatched alignment is refused
tts._post = lambda *a: json.dumps({"audio_base64": "", "alignment": {**al, "characters": list("zz")}}).encode()
try:
    tts.narrate(["zzz"], ["zzz"], {"voice": "elevenlabs"}, Path(tempfile.mkdtemp()))
    raise SystemExit("expected failure")
except RuntimeError:
    pass
# Kokoro is the default path
seen = []
tts._kokoro = lambda spoken, voice, speed, out: seen.append((voice, speed)) or {"file": "k", "duration": 1, "words": [], "spans": []}
assert tts.narrate(texts, ["a", "b"], {}, run)["file"] == "k" and seen == [("bm_george", 1.12)]

ks = []
tts._kokoro = lambda spoken, voice, speed, out: ks.append(spoken) or {"file": "k", "duration": 1, "words": [], "spans": []}
tts.narrate(["x"], ["He raped her. It was murder."], {}, run)
assert ks == [["He graped her. It was unalive."]], ks

# Kokoro path: punctuation kept as the word had it, grouped by sentence
sixw = lambda t: {"w": t, "s": 0, "e": 1}
tts._kokoro = lambda spoken, voice, speed, out: {"file": "k", "duration": 1, "words": [[sixw("Six"), sixw("women"), sixw("alleged"), sixw("six.")], [sixw("Six"), sixw("again")]], "spans": [(0, .5), (.5, 1)]}
o4 = tts.narrate(["x", "y"], ["Six women alleged sex.", "Six again"], {}, run)
assert [[w["cap"] for w in s] for s in o4["words"]] == [["Six", "women", "alleged", "s*x."], ["Six", "again"]], o4["words"]

# narration over the limit is sped up a little (at most 8%) instead of failing the gate after paid synthesis
import subprocess, tempfile as _t
r2 = Path(_t.mkdtemp()); long = r2 / "long.wav"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=220:d=60", "-ar", "24000", str(long)], check=True)
tts._kokoro = lambda spoken, voice, speed, out: {"file": str(long), "duration": 60.0, "words": [{"w": "end", "s": 59.0, "e": 59.5}], "spans": [(0, 60.0)]}
v = tts.narrate(texts, ["a"], {}, r2)
assert abs(v["duration"] - tts.MAX_VOICE) < 0.15 and abs(tts.media.duration(v["file"]) - tts.MAX_VOICE) < 0.15, v["duration"]
assert abs(v["words"][0]["s"] - 59.0 * tts.MAX_VOICE / 60) < 0.01 and abs(v["spans"][0][1] - v["duration"]) < 0.01, v
# Kokoro returns words per sentence: the speed-up must scale them too (it crashed on the nested lists before)
tts._kokoro = lambda spoken, voice, speed, out: {"file": str(long), "duration": 60.0, "words": [[{"w": "a", "s": 1.0, "e": 1.5}], [{"w": "end", "s": 59.0, "e": 59.5}]], "spans": [(0, 30.0), (30.0, 60.0)]}
v = tts.narrate(["A.", "End."], ["A.", "End."], {}, r2)
assert abs(v["words"][1][0]["s"] - 59.0 * tts.MAX_VOICE / 60) < 0.01 and v["words"][0][0]["cap"] == "a", v["words"]
tts._kokoro = lambda spoken, voice, speed, out: {"file": str(long), "duration": 70.0, "words": [], "spans": [(0, 70.0)]}
assert abs(tts.narrate(texts, ["a"], {}, r2)["duration"] - 70 / 1.08) < 0.01  # capped: the gate then refuses it
# several voices (comma separated): one per run, the same run always the same one (its cached audio stays valid)
picks = {tts.pick_voice("A,B", f"/runs/r{i}") for i in range(40)}
assert picks == {"A", "B"}, picks
assert tts.pick_voice("A, B", "/runs/x") == tts.pick_voice("A, B", "/runs/x") and tts.pick_voice("A", "/runs/x") == "A"
assert tts.pick_voice("", "/runs/x") == tts.VOICE
print("ok")
