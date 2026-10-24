"""Self-check for sfx_render.py: python3 sfx_render_test.py"""
import json
import os
import subprocess
import sys
import tempfile
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)
import sfx_render  # noqa: E402

KEY = [146.83, 220.0, 293.66, 369.99, 440.0]
CUES = [
    {"t": 0.2, "type": "whoosh", "gain": 0.12, "pan": -0.3, "dur": 0.4, "f0": 500, "f1": 2400},
    {"t": 0.5, "type": "pop", "step": 2},
    {"t": 0.8, "type": "riser", "dur": 1.0},
    {"t": 1.8, "type": "impact"},
    {"t": 2.2, "type": "blip", "step": 7},
    {"t": 2.5, "type": "chime"},
    {"t": 3.0, "type": "click"},
    {"t": 3.2, "type": "scratch", "dur": 0.5},
    {"t": 3.8, "type": "whoosh-big"},
]


def run(project):
    return subprocess.run([sys.executable, os.path.join(HERE, "sfx_render.py"), project], capture_output=True, text=True)


with tempfile.TemporaryDirectory() as d:
    def write(cues, duration=5.0, hero=1.8, **extra):
        with open(os.path.join(d, "sfx-cues.json"), "w") as f:
            json.dump({"duration": duration, "key": KEY, "hero": hero, "cues": cues, **extra}, f)

    write(CUES)
    r = run(d)
    assert r.returncode == 0, r.stderr
    print(r.stdout.strip())
    with wave.open(os.path.join(d, "sfx.wav")) as w:
        assert w.getframerate() == 48000 and w.getnchannels() == 2
        assert abs(w.getnframes() / 48000 - 5.0) < 0.1

    write(CUES + [{"t": 1.0, "type": "bogus"}])
    r = run(d)
    assert r.returncode != 0 and "bogus" in r.stderr, r

    # A run of the same cue type cycles through the recorded sounds, not one synth sample.
    write([{"t": 0.5 + 1.5 * k, "type": "whoosh"} for k in range(8)], duration=13.0, hero=None)
    played = sfx_render.render(d)["played"]
    variants = [v for _, _, v in played]
    assert len(played) == 8 and len(set(variants)) == 8, variants
    assert sfx_render.render(d)["played"] == played, "same cue sheet, same sounds"

    # The same family again too soon is dropped (whoosh and whoosh-big are one family); the hero impact never is.
    write([{"t": 1.0, "type": "whoosh"}, {"t": 1.3, "type": "whoosh-big"}, {"t": 2.5, "type": "whoosh"},
           {"t": 3.0, "type": "impact"}, {"t": 3.6, "type": "impact"}, {"t": 4.2, "type": "impact"}], duration=6.0, hero=3.6)
    kept = [(t, ty) for t, ty, _ in sfx_render.render(d)["played"]]
    assert kept == [(1.0, "whoosh"), (2.5, "whoosh"), (3.0, "impact"), (3.6, "impact")], kept

    # Music is a recorded track from the lane's pool, chosen per video.
    write(CUES, music="space")
    out = sfx_render.render(d)
    assert out["music"] in os.listdir(os.path.join(HERE, "sounds", "music", "space")), out["music"]
    picks = set()
    for k in range(12):
        write([{"t": 0.3 + 0.01 * k, "type": "click"}], duration=3.0, music="space")
        picks.add(sfx_render.render(d)["music"])
    assert len(picks) > 1, picks

    write(CUES, music="nowhere")
    r = run(d)
    assert r.returncode != 0 and "nowhere" in r.stderr, r
print("ok")
