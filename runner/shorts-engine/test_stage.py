# Offline tests for stage.py: a pick with no readable sources is dropped from the candidates, with a reason,
# so the retry cannot choose it again. Run: python3 test_stage.py
import json, subprocess, sys, tempfile
from pathlib import Path

here = Path(__file__).parent
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    job = {"lane": "tech", "pick": {"id": "c2"}, "candidates": [
        {"id": "c1", "title": "Kept", "sources": [{"url": "http://127.0.0.1:9/a"}]},
        {"id": "c2", "title": "Dead links", "sources": [{"url": "http://127.0.0.1:9/b"}]}]}
    (d / "job.json").write_text(json.dumps(job)); (d / "cfg.json").write_text("{}")
    subprocess.run([sys.executable, "-B", str(here / "stage.py"), "sources", "--run", str(d), "--state", str(d / "state"),
                    "--job", str(d / "job.json"), "--config", str(d / "cfg.json"), "--out", str(d / "out.json")], check=True, capture_output=True)
    res = json.loads((d / "out.json").read_text())
    assert res["port"] == "missing", res
    assert [c["id"] for c in res["output"]["candidates"]] == ["c1"], res["output"]
    assert "Dead links" in res["output"]["agentErrors"][0], res["output"]

# The voiceover is levelled to VOICE_LUFS, so the sound bed (mastered at a fixed level under it) never drowns it.
sys.dont_write_bytecode = True
sys.path.insert(0, str(here))
import re, stage  # noqa: E402
lufs = lambda f: float(re.findall(r"I:\s+(-?[\d.]+) LUFS", subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(f), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr)[-1])
with tempfile.TemporaryDirectory() as d:
    v = Path(d) / "voice.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=220:d=4", "-af", "volume=-24dB", str(v)], check=True)
    before = (lufs(v), float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)], capture_output=True, text=True).stdout))
    stage.level_voice(v)
    after = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)], capture_output=True, text=True).stdout)
    assert before[0] < -30 and abs(lufs(v) - stage.VOICE_LUFS) < 1.0, (before, lufs(v))
    assert abs(after - before[1]) < 0.05, "levelling must not move the word timings"
# The Reddit lane is wired into stage.py: its modes exist and record dispatches on job.lane.
assert "posts" in stage.MODES and "story" in stage.MODES
with tempfile.TemporaryDirectory() as d:
    assert stage.record({"lane": "reddit", "story": {"id": "r1"}}, {}, Path(d), Path(d) / "state")[0] == "next"
    assert json.loads((Path(d) / "state" / "used.json").read_text()) == ["r1"]
print("stage tests ok")
