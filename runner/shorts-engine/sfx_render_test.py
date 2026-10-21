"""Self-check for sfx_render.py: python3 sfx_render_test.py"""
import json
import os
import subprocess
import sys
import tempfile
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
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
    def write(cues):
        with open(os.path.join(d, "sfx-cues.json"), "w") as f:
            json.dump({"duration": 5.0, "key": KEY, "hero": 1.8, "cues": cues}, f)

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
print("ok")
