"""Narration with per-word timings: ElevenLabs (one request for the whole script, cached) or local Kokoro.

    tts.narrate(texts, spoken, cfg, run) -> {"file": path, "duration": s, "words": [[{w, s, e, b?}] per sentence], "spans": [(start, end)] per sentence}

`texts` may carry v3 audio tags like [dramatic] (sent to ElevenLabs, never in `words`); `spoken` is the same text without tags (Kokoro).
`b` marks a word that ends a clause or sentence. ElevenLabs request/cache/alignment approach follows shorts-engine/tts_el.py; Kokoro follows
shorts-engine/tts.py. Responses are cached by request hash in run/cut/tts-cache/ and in $AUTOBIZ_TTS_CACHE when set, so a re-render costs no credits.
"""
import base64, hashlib, json, os, re, subprocess, urllib.request, wave, zlib
from pathlib import Path
from shared import media  # engine folder is on sys.path
from .sensitive import cap_words, spoken_map

VOICE, MODEL, KOKORO_VOICE, KOKORO_SPEED, SR, GAP = "JBFqnCBsd6RMkjVDRZzb", "eleven_v4_turbo", "bm_george", 1.12, 24000, 0.12
TAG = re.compile(r"\[[^\]]*\]")


def _post(url, body, key):
    req = urllib.request.Request(url, data=body, headers={"xi-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def _eleven(texts, voice, model, run):
    full = " ".join(texts)
    body = {"text": full, "model_id": model, "voice_settings": {"stability": 0.5}}
    name = hashlib.sha256(json.dumps([voice, body]).encode()).hexdigest()[:16] + ".json"
    dirs = [Path(run) / "cut" / "tts-cache"] + ([Path(os.environ["AUTOBIZ_TTS_CACHE"])] if os.environ.get("AUTOBIZ_TTS_CACHE") else [])
    raw = next((d / name for d in dirs if (d / name).exists()), None)
    raw = raw.read_bytes() if raw else _post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps", json.dumps(body).encode(),
                                           os.environ["ELEVEN_LABS_API_KEY"])
    resp = json.loads(raw)
    al = resp["alignment"]
    if "".join(al["characters"]) != full:
        raise RuntimeError("alignment does not match the request text")  # word times would be wrong
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_bytes(raw)
    mp3 = Path(run) / "cut" / "voice.mp3"
    mp3.write_bytes(base64.b64decode(resp["audio_base64"]))
    dur = media.duration(mp3)
    st, en, words, offset = al["character_start_times_seconds"], al["character_end_times_seconds"], [], 0
    for t in texts:
        ws = []
        for m in re.finditer(r"\[[^\]]*\]|\S+", t):
            w = m.group().strip(".,!?;:\"“”'’…—")
            if not m.group().startswith("[") and w:
                ws.append({"w": w, "s": round(st[offset + m.start()], 3), "e": round(en[offset + m.end() - 1], 3),
                           **({"b": 1} if re.search(r"[.,!?;:…]$", m.group()) else {})})
        words.append(ws)
        offset += len(t) + 1
    return mp3, dur, words


def _spans(words, dur):
    starts = [0.0] + [max(ws[0]["s"] - 0.15, 0) for ws in words[1:]]
    return list(zip(starts, starts[1:] + [dur]))


def _kokoro(spoken, voice, speed, out):
    import numpy as np
    from kokoro import KPipeline
    pipe = KPipeline(lang_code="b" if voice[0] == "b" else "a")
    audio, words, spans, t = [], [], [], 0.0
    for text in spoken:
        ws, chunks, n = [], [], 0
        for r in pipe(text, voice=voice, speed=speed, split_pattern=None):
            off = t + n / SR
            chunks.append(r.audio.numpy())
            n += len(chunks[-1])
            for tok in r.tokens or []:
                if tok.start_ts is None or not tok.phonemes.strip(".,?!;:—- "):
                    if tok.text in (".", "!", "?", ",", ";", ":") and ws:
                        ws[-1]["b"] = 1
                    continue
                ws.append({"w": tok.text, "s": round(off + tok.start_ts, 3), "e": round(off + tok.end_ts, 3)})
        clip = np.concatenate(chunks)
        spans.append((t, t + len(clip) / SR + GAP))
        audio += [clip, np.zeros(int(GAP * SR), dtype=clip.dtype)]
        words.append(ws)
        t += len(clip) / SR + GAP
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(np.concatenate(audio), -1, 1) * 32767).astype("<i2").tobytes())
    return {"file": str(out), "duration": t, "words": words, "spans": spans}


MAX_VOICE, MAX_SPEEDUP = 58.0, 1.08  # the Short must end by 59 s; a slightly faster read beats failing the gate after paid synthesis


def _scale(w, k):
    """One word, or a sentence's list of words (Kokoro), with its times divided by k."""
    return [_scale(x, k) for x in w] if isinstance(w, list) else dict(w, s=round(w["s"] / k, 3), e=round(w["e"] / k, 3))


def _fit(v, out):
    """Speed the narration up by at most MAX_SPEEDUP so it ends by MAX_VOICE; word times and spans scale with it."""
    k = min(v["duration"] / MAX_VOICE, MAX_SPEEDUP)
    if k <= 1:
        return v
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", v["file"], "-af", f"atempo={k:.5f}", str(out)], check=True)
    return {"file": str(out), "duration": round(v["duration"] / k, 3),
            "words": [_scale(w, k) for w in v["words"]],
            "spans": [(a / k, b / k) for a, b in v["spans"]]}


def pick_voice(voices, run):
    """One of the comma-separated ElevenLabs voice ids, chosen by the run folder: random across runs, stable within one."""
    ids = [v.strip() for v in (voices or "").split(",") if v.strip()] or [VOICE]
    return ids[zlib.crc32(Path(run).name.encode()) % len(ids)]


def narrate(texts, spoken, cfg, run):
    cut = Path(run) / "cut"
    cut.mkdir(parents=True, exist_ok=True)
    tm, sm = [spoken_map(t) for t in texts], [spoken_map(t) for t in spoken]  # demonetisation-safe wording; the alignment check and word times use it
    texts, spoken = [t for t, _ in tm], [t for t, _ in sm]
    caps = [c for _, c in (tm if cfg.get("voice") == "elevenlabs" else sm)]
    if cfg.get("voice") == "elevenlabs":
        mp3, dur, words = _eleven(texts, pick_voice(cfg.get("elevenVoice"), run), cfg.get("elevenModel") or MODEL, run)
        v = {"file": str(mp3), "duration": dur, "words": words, "spans": _spans(words, dur)}
    else:
        v = _kokoro(spoken, KOKORO_VOICE, KOKORO_SPEED, cut / "voice.wav")
    w = v["words"]  # per sentence already, or flat (then grouped by the spans)
    for ws, c in zip(w if w and isinstance(w[0], list) else [[x for x in w if a <= x["s"] < b] for a, b in v["spans"]], caps):
        cap_words(ws, c)
    return _fit(v, cut / "voice-fit.wav")
