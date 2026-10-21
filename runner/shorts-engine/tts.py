# Free local stand-in for tts_el.py (Kokoro): same outputs, voice.mp3 + timing.js, so storyboards can be
# tested without spending ElevenLabs credits. Delivery tags like [excited] are dropped (Kokoro can't act).
# Usage: <newsroom venv>/python tts.py <project-dir> <kokoro-voice>
import json, re, subprocess, sys, wave
from pathlib import Path
import numpy as np
from kokoro import KPipeline

root, voice = Path(sys.argv[1]), sys.argv[2]
SR, GAP, SPEED = 24000, 0.3, 1.12
pipe = KPipeline(lang_code="a")
audio, scenes, t = [], [], 0.0
for scene in json.loads((root / "script.json").read_text()):
    words, chunks, pending = [], [], ""
    text = re.sub(r"\[[^\]]*\]\s*", "", scene["text"])
    for r in pipe(text, voice=voice, speed=SPEED, split_pattern=None):
        offset = t + sum(len(c) for c in chunks) / SR
        chunks.append(r.audio.numpy())
        for tok in r.tokens or []:
            if tok.start_ts is None or not tok.phonemes.strip(".,?!;:—- "):
                pending += tok.text if tok.text in "$£€" else ""  # unvoiced symbols join the next word
                if tok.text in ".!?" and words: words[-1]["p"] = 1  # sentence end, for caption breaks
                continue
            words.append({"w": pending + tok.text, "s": round(offset + tok.start_ts, 3), "e": round(offset + tok.end_ts, 3)})
            pending = ""
    clip = np.concatenate(chunks)
    dur = len(clip) / SR + GAP
    scenes.append({"id": scene["id"], "start": round(t, 3), "end": round(t + dur, 3), "words": words})
    audio += [clip, np.zeros(int(GAP * SR), dtype=clip.dtype)]
    t += dur
pcm = (np.clip(np.concatenate(audio), -1, 1) * 32767).astype("<i2")
with wave.open(str(root / "voice.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(root / "voice.wav"), "-b:a", "128k", str(root / "voice.mp3")], check=True)
(root / "voice.wav").unlink()
scenes[-1]["end"] = round(scenes[-1]["end"] + 1.2, 3)  # hold the end card, as tts_el.py does
t = scenes[-1]["end"]
timing = {"duration": round(t, 3), "scenes": scenes}
(root / "timing.js").write_text("window.TIMING = " + json.dumps(timing) + ";\n")
print(f"{t:.1f}s", [(s["id"], round(s["end"] - s["start"], 1)) for s in scenes])
