"""Render <project>/sfx-cues.json to <project>/sfx.wav (48 kHz stereo) with the vendored sfx engine.

Usage: python3 sfx_render.py <project-dir>

Timing: every cue's `t` is when the sound STARTS, except a riser, which is placed so it ENDS
at t + dur (its build-up runs from t, the payoff lands at t + dur).
"""
import json
import math
import os
import sys

sys.dont_write_bytecode = True  # the engine folder stays clean (no __pycache__ in the repo or the runner checkout)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sfx import synth  # noqa: E402
from sfx.mix import Mix  # noqa: E402


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

    # Validate first so a bad cue fails before the slow pad render.
    for i, c in enumerate(sheet["cues"]):
        if c.get("type") not in SOUNDS:
            sys.exit(f"sfx_render: cue #{i} at t={c.get('t')} has unknown type {c.get('type')!r}; known: {', '.join(SOUNDS)}")

    mix = Mix(dur)
    # Pad bed: fade in 1.5 s, fade out 1.2 s, duck to 35% from 0.3 s before the hero until 1.5 s after.
    fade = synth.envelope([(0, 0), (1.5, 1), (dur - 1.2, 1), (dur, 0)])
    duck = synth.envelope([(-1e9, 1), (hero - 0.4, 1), (hero - 0.3, 0.35), (hero + 1.5, 0.35), (hero + 1.8, 1)]) if hero is not None else (lambda t: 1.0)
    music = sheet.get("music")
    if music:  # a moving bed: chord progression + plucked arpeggio (+ off-beat ticks), looping to the end
        beat = 60 / music["bpm"]; bar = beat * music["beatsPerChord"]; chords = music["chords"]
        prog = [(k * bar, chords[k % len(chords)]) for k in range(int(dur / bar) + 1)]
        left, right = synth.pad(dur, prog, volume=lambda t: fade(t) * duck(t))
        mix.put_stereo(0, left, right, gain=0.022)
        step = beat / 2 if music.get("arp") == "eighths" else beat
        for k in range(int(dur / step)):
            t = k * step
            ch = chords[int(t / bar) % len(chords)]
            f = ch[k % len(ch)] * 2  # an octave above the pad
            mix.put(t, synth.blip(f, dur=0.3, tau=0.09 if step < beat else 0.22), gain=0.03 * fade(t) * duck(t), pan=-0.3 + 0.6 * ((k % 4) / 3))
            if music.get("ticks") and k % 2 == 1:
                mix.put(t, synth.click(6200, 0.03), gain=0.012 * fade(t) * duck(t))
    else:
        left, right = synth.pad(dur, [(0, key)], volume=lambda t: fade(t) * duck(t))
        mix.put_stereo(0, left, right, gain=0.03)

    last = {}  # type -> (time, how many in a row)
    for i, c in enumerate(sheet["cues"]):
        gain, build = SOUNDS[c["type"]]
        t = c["t"]  # riser: t is its START, it ends at t + dur
        samples = build(c, key)
        if c["type"] in VARIED:  # a seeded tape-speed change (±12%), so a repeated sound is never the identical sample
            r = 1 + 0.12 * ((((i + 1) * 2654435761 + int(t * 1000)) % 1001) / 500 - 1)
            samples = [samples[int(k * r)] for k in range(int(len(samples) / r))]
        prev, run = last.get(c["type"], (-9.0, 0))
        run = run + 1 if t - prev < 0.7 else 0  # the same sound again within 0.7 s plays softer each time
        last[c["type"]] = (t, run)
        mix.put(t, limit(samples), gain=c.get("gain", gain) * 0.7 ** min(run, 4), pan=c.get("pan", 0.0))

    stats = mix.master(target_lufs=-20.0)  # -20, not -14: this sits under a voiceover
    mix.write(os.path.join(project, "sfx.wav"))
    print(f"sfx_render: {len(sheet['cues'])} cues, {dur}s, {stats['lufs']:.1f} LUFS, peak {stats['peak_db']:.1f} dBFS")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    render(sys.argv[1])
