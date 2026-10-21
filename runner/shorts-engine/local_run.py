# Run a lane's whole business locally, the way the autobiz graph runs it: shorts steps (stage.py) and agent
# steps (static prompts + the job's input keys, as the agent block sends them), with the same retry routes.
# For testing the engine and prompts without the manager. Needs CLAUDE_CODE_OAUTH_TOKEN (run-with-secrets).
# Usage: python3 local_run.py <lane> <work-dir> [--voice kokoro|elevenlabs] [--no-render] [--model claude-haiku-5-5]
import json, subprocess, sys
from pathlib import Path

here = Path(__file__).parent.resolve()
sys.path.insert(0, str(here))
import llm  # noqa: E402

lane, work = sys.argv[1], Path(sys.argv[2]).resolve()
model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "claude-haiku-5-5"
voice = sys.argv[sys.argv.index("--voice") + 1] if "--voice" in sys.argv else "kokoro"
run, state = work / "run", work / "state"
run.mkdir(parents=True, exist_ok=True)
job = {"lane": lane}


def step(mode, **cfg):
    (run / "job.json").write_text(json.dumps(job, ensure_ascii=False)); (run / "config.json").write_text(json.dumps(cfg))
    r = subprocess.run([sys.executable, str(here / "stage.py"), mode, "--run", str(run), "--state", str(state), "--job", str(run / "job.json"),
                        "--config", str(run / "config.json"), "--out", str(run / "result.json")], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"{mode} crashed: {(r.stdout + r.stderr)[-800:]}")
    res = json.loads((run / "result.json").read_text())
    job.update(res["output"])
    print(f"[{mode}] {res['port']} {res['log'][-160:]}", flush=True)
    return res["port"]


def agent(prompt, keys, out_key, files=(), images=()):
    inp = {k: job[k] for k in keys if k in job}
    for k in files:  # like fileKeys: the file's text replaces the reference
        inp[k] = (run / job[k]).read_text()
    text = (here / "prompts" / prompt).read_text() + "\n\nInput: " + json.dumps(inp, ensure_ascii=False) + "\n\nConfiguration: {}"
    job[out_key] = llm.ask_json(text, model=model, images=[run / i for i in images])
    job.pop("agentErrors", None)
    print(f"[agent {prompt}] -> {out_key}", flush=True)


def retry(port, limit, redo):
    for _ in range(limit):
        if port != "invalid" and port != "missing":
            return port
        port = redo()
    return port


if step("feeds", hours=72) != "next":
    raise SystemExit("no candidates")
agent("select.md", ["laneContext", "candidates", "agentErrors"], "pick")


def from_pick():
    port = step("sources")
    if port != "next":
        return port
    agent("facts.md", ["pick", "sourcesText", "agentErrors"], "facts", files=["sourcesText"])
    port = retry(step("facts"), 1, lambda: (agent("facts.md", ["pick", "sourcesText", "agentErrors"], "facts", files=["sourcesText"]), step("facts"))[1])
    if port != "next":
        return port
    return step("images")


port = from_pick()
port = retry(port, 2, lambda: (agent("select.md", ["laneContext", "candidates", "agentErrors"], "pick"), from_pick())[1])
if port != "next":
    raise SystemExit(f"no usable story: {port}")
agent("images.md", ["facts", "imageCandidates"], "imagePicks", images=job["imagePreviews"])
step("brief")
agent("storyboard.md", ["brief", "laneContext", "recentHooks", "storyboard", "agentErrors"], "storyboard")
cfg = {"voice": voice, "render": "--no-render" not in sys.argv}
port = retry(step("render", **cfg), 2, lambda: (agent("storyboard.md", ["brief", "laneContext", "recentHooks", "storyboard", "agentErrors"], "storyboard"), step("render", **cfg))[1])
if port != "next":
    raise SystemExit(f"storyboard failed its checks: {job.get('agentErrors')}")
step("record")
print(f"DONE: {run / job['short']['file']}  title: {job['meta']['title']}")
