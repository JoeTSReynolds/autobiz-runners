# Narrate <project>/script.json with ElevenLabs in ONE request (so delivery flows across scenes),
# writing <project>/voice.mp3 and <project>/timing.js (scene + word times, from ElevenLabs' character timestamps).
# Scene text may carry v3 audio tags like [excited] or [whispers]; they steer delivery and never reach captions.
# Responses are cached by request hash, so re-running an unchanged script spends no credits.
# Usage: ./run-with-secrets python tts_el.py <project-dir> <voice-id> [model]
import base64, hashlib, json, os, re, sys, urllib.request
from pathlib import Path
from shared import media

root, voice = Path(sys.argv[1]), sys.argv[2]
model = sys.argv[3] if len(sys.argv) > 3 else "eleven_v4_turbo"  # half the credits of v3/v4
scenes = json.loads((root / "script.json").read_text())
full = " ".join(s["text"] for s in scenes)
body = {"text": full, "model_id": model, "voice_settings": {"stability": 0.5}}
cache = Path(__file__).parent / ".tts-cache" / (hashlib.sha256(json.dumps([voice, body]).encode()).hexdigest()[:16] + ".json")
if not cache.exists():
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps",
        data=json.dumps(body).encode(),
        headers={"xi-api-key": os.environ["ELEVEN_LABS_API_KEY"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        cache.parent.mkdir(exist_ok=True)
        cache.write_bytes(r.read())
resp = json.loads(cache.read_text())
al = resp["alignment"]
if "".join(al["characters"]) != full:
    sys.exit("alignment does not match the request text")  # word times would be wrong
(root / "voice.mp3").write_bytes(base64.b64decode(resp["audio_base64"]))
audio_len = media.duration(root / "voice.mp3")

starts, ends, out, offset = al["character_start_times_seconds"], al["character_end_times_seconds"], [], 0
for s in scenes:
    words = []
    for m in re.finditer(r"\[[^\]]*\]|\S+", s["text"]):
        if m.group().startswith("["):
            continue  # audio tag
        a, b = offset + m.start(), offset + m.end() - 1
        w = m.group().strip(".,!?;:\"“”'’…—")
        if w:
            words.append({"w": w, "s": round(starts[a], 3), "e": round(ends[b], 3), **({"p": 1} if re.search(r"[.!?…:]$", m.group()) else {})})
    if not words:
        sys.exit(f"scene {s['id']} has no spoken words")
    out.append({"id": s["id"], "words": words})
    offset += len(s["text"]) + 1
for i, s in enumerate(out):  # a scene runs from its first word to the next scene's first word
    s["start"] = 0.0 if i == 0 else round(s["words"][0]["s"] - 0.15, 3)
for i, s in enumerate(out):
    s["end"] = out[i + 1]["start"] if i + 1 < len(out) else round(audio_len + 1.5, 3)  # hold the end card
timing = {"duration": out[-1]["end"], "scenes": out}
(root / "timing.js").write_text("window.TIMING = " + json.dumps(timing) + ";\n")
print(f"{timing['duration']:.1f}s, {len(full)} chars", [(s["id"], round(s["end"] - s["start"], 1)) for s in out])
