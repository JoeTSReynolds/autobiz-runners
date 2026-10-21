# One Claude call the way autobiz's agent block makes it (Claude CLI print mode, no tools or settings,
# stream-json in, optional images as base64 blocks; at most 8 images and 1 MiB, as in the block).
import base64, json, subprocess
from pathlib import Path

SYSTEM = "You are one step of an automated content pipeline. Follow the instructions exactly and reply with only the requested output."


def ask(prompt, model="claude-haiku-5-5", images=(), timeout=600):
    blocks = [{"type": "text", "text": prompt}]
    for p in list(images)[:8]:
        data = Path(p).read_bytes()
        if len(data) > 512 * 1024:
            raise ValueError(f"{p}: over the 512 KiB image limit")
        blocks.append({"type": "image", "source": {"type": "base64", "media_type": "image/png" if data[:4] == b"\x89PNG" else "image/jpeg",
                                                    "data": base64.b64encode(data).decode()}})
    msg = json.dumps({"type": "user", "message": {"role": "user", "content": blocks}})
    if len(msg.encode()) > 1024 * 1024:
        raise ValueError("request over the 1 MiB limit")
    r = subprocess.run(["claude", "-p", "--model", model, "--input-format", "stream-json", "--output-format", "stream-json", "--verbose", "--tools", "",
                        "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence", "--system-prompt", SYSTEM],
                       input=msg + "\n", capture_output=True, text=True, timeout=timeout)
    results = [e for e in (json.loads(l) for l in r.stdout.splitlines() if l.startswith("{")) if e.get("type") == "result"]
    if not results or results[-1].get("is_error") or not isinstance(results[-1].get("result"), str):
        raise RuntimeError(f"Claude CLI failed: {(results[-1].get('result') if results else r.stderr)!s:.300}")
    return results[-1]["result"]


def ask_json(prompt, **kw):
    reply = ask(prompt, **kw)
    return json.loads(reply[reply.index("{"): reply.rindex("}") + 1])
