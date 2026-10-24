"""Render <project>/sfx-cues.json to <project>/sfx.wav (48 kHz stereo) with the vendored sfx engine.

Usage: python3 sfx_render.py <project-dir>

Timing: every cue's `t` is when the sound STARTS, except a riser, which is placed so it ENDS
at t + dur (its build-up runs from t, the payoff lands at t + dur).
"""
import array
import json
import math
import os
import random
import subprocess
import sys
import zlib

sys.dont_write_bytecode = True  # the engine folder stays clean (no __pycache__ in the repo or the runner checkout)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sfx import synth  # noqa: E402
from sfx.mix import Mix  # noqa: E402
from sfx.synth import SR  # noqa: E402


def note(key, step):
    """Key tone for a step: index step % len, raised an octave per full pass."""
    return key[step % len(key)] * 2 ** (step // len(key))


# type -> (default gain, builder(cue, key) -> mono samples)
SOUNDS = {
    "whoosh": (0.12, lambda c, k: synth.whoosh(c.get("dur", 0.4), c.get("f0", 500), c.get("f1", 2400))),
    "whoosh-big": (0.3, lambda c, k: synth.whoosh(c.get("dur", 0.7), c.get("f0", 180), c.get("f1", 1600), peak=0.55)),
    "pop": (0.12, lambda c, k: synth.pop(note(k, c.get("step", 0)) * 2, note(k, c.get("step", 0)), c.get("dur", 0.16))),
    "blip": (0.14, lambda c, k: synth.blip(note(k, c.get("step", 0)), c.get("dur", 0.35))),
    "click": (0.1, lambda c, k: synth.click(c.get("f0", 1800), c.get("dur", 0.05))),
    "chime": (0.12, lambda c, k: synth.chime([note(k, c.get("step", 0) + i) * 2 for i in (0, 2, 4)], c.get("dur", 1.8))),
    "scratch": (0.1, lambda c, k: synth.scratch(c.get("dur", 0.8))),
    "impact": (0.24, lambda c, k: synth.impact(c.get("dur", 1.2))),
    "riser": (0.2, lambda c, k: synth.riser(c.get("dur", 2.5), c.get("f0", 260), c.get("f1", 5200))),
}


# Unpitched sounds vary in speed; pitched ones (pop, blip, chime) stay in the music's key, and a riser keeps
# its length because it must end exactly on its beat.
VARIED = {"whoosh", "whoosh-big", "click", "scratch", "impact"}


SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
SFX_LEVEL = 0.6  # every cue sat too loud against the voiceover
MUSIC_GAIN = 0.5
BED_LUFS = -30.0  # 14 dB under the voiceover, which stage.py levels to -16 LUFS
FAMILY = {"whoosh-big": "whoosh"}  # types that share a thinning family; others are their own
GAP = {"whoosh": 0.9, "impact": 2.5, "riser": 4.0, "chime": 2.0, "scratch": 1.5, "click": 0.1, "pop": 0.12, "blip": 0.12}
RISER_FADE = 0.03  # fade-in where a riser sample is cut short


def decode(path, channels, extra=(), tail=()):
    """Decode an audio file with ffmpeg to float samples at 48 kHz (interleaved when stereo)."""
    cmd = ["ffmpeg", "-v", "error", *extra, "-i", path, *tail, "-ac", str(channels), "-ar", str(SR), "-f", "f32le", "-"]
    out = array.array("f")
    out.frombytes(subprocess.run(cmd, capture_output=True, check=True).stdout)
    return out.tolist()


def track_seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(out.stdout)


def limit(samples, ratio=0.45):
    """Soft-limit a cue to 45% of its own peak (tanh knee), so a sharp transient can't jump far above its body."""
    peak = max((abs(v) for v in samples), default=0.0)
    if peak == 0:
        return samples
    ceil = ratio * peak
    return [ceil * math.tanh(v / ceil) for v in samples]


def render(project):
    with open(os.path.join(project, "sfx-cues.json")) as f:
        sheet = json.load(f)
    dur, key, hero = sheet["duration"], sheet["key"], sheet.get("hero")

    # Validate first so a bad cue or lane fails before the slow work.
    for i, c in enumerate(sheet["cues"]):
        if c.get("type") not in SOUNDS:
            sys.exit(f"sfx_render: cue #{i} at t={c.get('t')} has unknown type {c.get('type')!r}; known: {', '.join(SOUNDS)}")
    lane = sheet.get("music")
    tracks = []
    if isinstance(lane, str):
        lane_dir = os.path.join(SOUNDS_DIR, "music", lane)
        tracks = sorted(os.listdir(lane_dir)) if os.path.isdir(lane_dir) else []
        if not tracks:
            sys.exit(f"sfx_render: music lane {lane!r} has no tracks (looked in {lane_dir}); nowhere to pick from")

    rng = random.Random(zlib.crc32(json.dumps(sheet["cues"], sort_keys=True).encode()))  # per-video, so renders repeat exactly
    mix = Mix(dur)
    # Music bed: fade in 1.5 s, fade out 1.2 s, duck to 35% from 0.3 s before the hero until 1.5 s after.
    fade = synth.envelope([(0, 0), (1.5, 1), (dur - 1.2, 1), (dur, 0)])
    duck = synth.envelope([(-1e9, 1), (hero - 0.4, 1), (hero - 0.3, 0.35), (hero + 1.5, 0.35), (hero + 1.8, 1)]) if hero is not None else (lambda t: 1.0)
    music = None
    if tracks:
        music = rng.choice(tracks)
        path = os.path.join(SOUNDS_DIR, "music", lane, music)
        offset = rng.uniform(0, max(0, track_seconds(path) - dur))  # past the end it loops, so a short track still fills the video
        pcm = decode(path, 2, extra=["-stream_loop", "-1", "-ss", f"{offset:.3f}"], tail=["-t", f"{dur:.3f}"])
        n = min(len(pcm) // 2, mix.n)
        env = [fade(k / SR) * duck(k / SR) * MUSIC_GAIN for k in range(n)]
        mix.put_stereo(0, [a * e for a, e in zip(pcm[0::2], env)], [b * e for b, e in zip(pcm[1::2], env)])
    else:
        left, right = synth.pad(dur, [(0, key)], volume=lambda t: fade(t) * duck(t))
        mix.put_stereo(0, left, right, gain=0.03)

    # Per type: synth first, then the recorded files, shuffled; the k-th played cue uses order[k % len].
    order, files, cache = {}, {}, {}
    for ty in SOUNDS:
        d = os.path.join(SOUNDS_DIR, ty)
        order[ty] = ["synth"] + (sorted(os.listdir(d)) if os.path.isdir(d) else [])
        rng.shuffle(order[ty])

    last = {}  # type -> (time, how many in a row)
    last_family = {}  # family -> time of the last played cue
    count = {}  # type -> played so far
    played = []
    for i, c in enumerate(sheet["cues"]):
        ty, t = c["type"], c["t"]  # riser: t is its START, it ends at t + dur
        fam = FAMILY.get(ty, ty)
        is_hero = ty == "impact" and hero is not None and abs(t - hero) <= 0.01
        if not is_hero and t - last_family.get(fam, -9e9) < GAP[fam]:
            continue
        last_family[fam] = t
        gain, build = SOUNDS[ty]
        variant = order[ty][count.get(ty, 0) % len(order[ty])]
        count[ty] = count.get(ty, 0) + 1
        start = t
        if variant == "synth":
            samples = build(c, key)
        else:
            path = os.path.join(SOUNDS_DIR, ty, variant)
            if path not in cache:
                cache[path] = decode(path, 1)
            samples = cache[path]
            if ty == "riser" and samples:  # land the loudest point on the beat
                begin = t + c.get("dur", 2.5) - max(range(len(samples)), key=lambda k: abs(samples[k])) / SR
                start = max(begin, t, 0.0)
                cut = round((start - begin) * SR)
                samples = samples[cut:]
                if cut:
                    nf = min(len(samples), int(RISER_FADE * SR))
                    samples = [v * k / nf for k, v in enumerate(samples[:nf])] + samples[nf:]
        if ty in VARIED:  # a seeded tape-speed change (±12%), so a repeated sound is never the identical sample
            r = 1 + 0.12 * ((((i + 1) * 2654435761 + int(t * 1000)) % 1001) / 500 - 1)
            samples = [samples[int(k * r)] for k in range(int(len(samples) / r))]
        prev, run = last.get(ty, (-9.0, 0))
        run = run + 1 if t - prev < 0.7 else 0  # the same sound again within 0.7 s plays softer each time
        last[ty] = (t, run)
        mix.put(start, limit(samples), gain=c.get("gain", gain) * SFX_LEVEL * 0.7 ** min(run, 4), pan=c.get("pan", 0.0))
        played.append((t, ty, variant))

    stats = mix.master(target_lufs=BED_LUFS)
    mix.write(os.path.join(project, "sfx.wav"))
    print(f"sfx_render: {len(played)} cues ({len(sheet['cues']) - len(played)} dropped), music {music or 'synth pad'}, {dur}s, {stats['lufs']:.1f} LUFS, peak {stats['peak_db']:.1f} dBFS")
    return {"music": music, "played": played}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    render(sys.argv[1])
