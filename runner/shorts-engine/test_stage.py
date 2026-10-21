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
print("stage tests ok")
