# One step of the Shorts pipeline, called by the autobiz `shorts` block (one mode per call).
#   python3 stage.py <mode> --run <run-dir> --state <state-dir> --job job.json --config config.json --out result.json
# Reads the job (JSON), writes {"port": "next"|"invalid"|"missing", "output": {keys to add to the job}, "log": "..."}.
# Modes: feeds, sources, facts, images, brief, render, record; posts and story for the reddit lane (reddit.py). Every judgement happens in agent blocks
# between these steps; this file only fetches, checks, assembles and renders.
import argparse, json, os, re, shutil, subprocess, sys, time, urllib.request

sys.dont_write_bytecode = True  # the engine folder stays clean (no __pycache__ in the repo or the runner checkout)
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

here = Path(__file__).parent.resolve()
sys.path.insert(0, str(here))
import factcheck  # noqa: E402
import newsroom_site  # noqa: E402
import reddit  # noqa: E402

HOOKS = ["masked-number", "countdown-three", "stakes-first", "contradiction", "hidden-thing"]
VOICES = {"tech": {"elevenlabs": "TX3LPaxmHKxFdv7VOQHJ", "kokoro": "am_michael"}, "space": {"elevenlabs": "JBFqnCBsd6RMkjVDRZzb", "kokoro": "bm_george"}}
# the sources website each video's description links to; lanes keep the newsroom site's channel pages
SITE = os.environ.get("NEWSROOM_SITE_URL", "https://jtsr-newsroom.pages.dev").rstrip("/")
CHANNELS = {"tech": {"lane": "technology", "url": "https://www.youtube.com/@JTSRTech", "name": "JTSR Tech"},
            "space": {"lane": "science-space", "url": "https://www.youtube.com/@JTSRScience", "name": "JTSR Science"}}


def sh(*cmd, cwd=None, timeout=1500):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, cwd=cwd, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def jread(p, default=None):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else default


def lane_of(job):
    lane = job.get("lane")
    if lane not in VOICES:
        raise SystemExit(f"job.lane must be one of {', '.join(VOICES)}, got {lane!r}")
    return lane


def feeds(job, cfg, run, state):
    lane = lane_of(job)
    code, out = sh(sys.executable, here / "feeds.py", lane, run / "feeds", "--hours", cfg.get("hours", 72), "--covered", state / "covered.json")
    if code:
        return "missing", {}, out
    cands = jread(run / "feeds" / "candidates.json")["candidates"]
    lane_cfg = jread(here / "lanes" / lane / "lane.json")
    code, catalogue = sh("node", here / "catalog.mjs", lane)
    if code:
        raise SystemExit(f"catalogue failed: {catalogue}")
    context = {"scope": lane_cfg["scope"], "selection": lane_cfg["selection"], "design": (here / "lanes" / lane / "brief.md").read_text(),
               "catalogue": catalogue, "example": jread(here / "lanes" / lane / "example.json")}
    return ("next" if cands else "missing"), {"candidates": cands, "laneContext": context, "recentHooks": (jread(state / "hooks.json", []))[-3:]}, out


def drop_pick(job, why):
    # a dead end for this story: remove it from the candidates and say why, so the next pick cannot repeat it
    pick = job.get("pick") or {}
    cand = next((c for c in job.get("candidates", []) if c["id"] == pick.get("id")), {})
    rest = [c for c in job.get("candidates", []) if c["id"] != pick.get("id")]
    return {"candidates": rest, "agentErrors": [f"{cand.get('title', pick.get('id'))!r} {why}; it was removed from the candidates, so choose a different one"]}


def sources(job, cfg, run, state):
    pick = job.get("pick") or {}
    cand = next((c for c in job.get("candidates", []) if c["id"] == pick.get("id")), None)
    if not cand:
        return "invalid", {"agentErrors": [f"pick.id {pick.get('id')!r} is not one of the candidate ids"]}, ""
    code, out = sh(sys.executable, here / "sources.py", run / "sources", *[s["url"] for s in cand["sources"]][:3])
    ok = [s for s in jread(run / "sources" / "sources.json", []) if s["ok"]]
    if not ok:
        return "missing", drop_pick(job, "had no readable source pages"), out
    text = "\n\n".join(f"## {s['id']}: {s['title']} ({s['url']})\n" + (run / "sources" / s["file"]).read_text()[:12000] for s in ok)
    (run / "sources.txt").write_text(text)  # one plain file at the run root, for an agent's fileKeys
    return "next", {"sources": [{k: s[k] for k in ("id", "url", "title")} for s in ok], "sourcesText": "sources.txt"}, out


def facts(job, cfg, run, state):
    sheet = job.get("facts") or {}
    kept, errs = factcheck.check_quotes(sheet, run / "sources")
    if len(kept) < cfg.get("minFacts", 5):
        return "invalid", {"agentErrors": [f"only {len(kept)} facts have a quote found word for word in its source page; need {cfg.get('minFacts', 5)}"] + errs}, ""
    return "next", {"facts": {**sheet, "facts": kept}}, f"{len(kept)} facts verified"


def images(job, cfg, run, state):
    sys.path.insert(0, str(here))
    import images as imgs
    found, seen = [], set()
    for q in (job.get("facts") or {}).get("image_queries", [])[:4]:
        for r in imgs.search(q, 8):
            if r["title"] not in seen and (r.get("width") or 2000) >= 1200:
                seen.add(r["title"]); found.append(r)
        time.sleep(1)
    cands, previews = [], []
    for r in found:
        if len(cands) == 8:
            break
        n = len(cands) + 1
        try:
            imgs.get(str(run / "candidates"), r, f"c{n}.jpg")
        except Exception:
            continue
        code, _ = sh("ffmpeg", "-v", "error", "-y", "-i", run / "candidates" / "assets" / f"c{n}.jpg", "-vf", "scale=640:-1", "-q:v", "6", run / f"preview{n}.jpg")
        if not code:
            cands.append({k: r.get(k) for k in ("provider", "title", "page", "license", "artist", "description")} | {"n": n})
            previews.append(f"preview{n}.jpg")
    if not cands:
        return "missing", drop_pick(job, "had no free-licence images"), "0 image candidates"
    return "next", {"imageCandidates": cands, "imagePreviews": previews}, f"{len(cands)} image candidates"


def brief(job, cfg, run, state):
    lane, sheet = lane_of(job), job.get("facts") or {}
    picks = [p for p in (job.get("imagePicks") or {}).get("images", []) if p.get("keep") and 1 <= p.get("n", 0) <= len(job.get("imageCandidates", []))][:4]
    proj = run / "short"
    if proj.exists():
        shutil.rmtree(proj)
    (proj / "assets").mkdir(parents=True)
    imgs = []
    for k, p in enumerate(picks):
        c, name = job["imageCandidates"][p["n"] - 1], f"img{k + 1}.jpg"
        shutil.copy(run / "candidates" / "assets" / f"c{c['n']}.jpg", proj / "assets" / name)
        _, wh = sh("ffprobe", "-v", "quiet", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", proj / "assets" / name)
        imgs.append({"file": name, "what": ("Artist's illustration: " if p.get("illustration") else "") + p.get("what", ""), "size": [int(x) for x in wh.split(",")[:2]],
                     "points": p.get("points") or {"subject": {"x": 0.5, "y": 0.5}}, "credit": f"{c.get('artist') or c['provider']} ({c['license']})", "page": c.get("page")})
    src = {s["id"]: s["url"] for s in job.get("sources", [])}
    b = {"lane": lane, "voice": VOICES[lane]["elevenlabs"], "story": sheet.get("story", ""), "date": sheet.get("date", ""),
         "facts": [{"id": f["id"], "text": f["text"], "source": src.get(f.get("source"), "")} for f in sheet.get("facts", [])],
         "whatif": sheet.get("whatif", ""), "caution": sheet.get("caution", ""), "images": imgs}
    (proj / "brief.json").write_text(json.dumps(b, indent=1, ensure_ascii=False))
    return "next", {"brief": b}, f"brief with {len(b['facts'])} facts and {len(imgs)} images"


def fake_timing(sb):
    # ~2.7 words/s with sentence pauses: checks anchors exist before a voice is made
    t, scenes = 0.2, []
    for s in sb["scenes"]:
        words, start = [], t
        for m in re.finditer(r"\[[^\]]*\]|\S+", s["say"]):
            if m.group().startswith("["):
                continue
            w = m.group().strip(".,!?;:\"“”'’…—")
            if w:
                words.append({"w": w, "s": round(t, 3), "e": round(t + 0.3, 3)})
            t += 0.37 + (0.35 if re.search(r"[.!?]$", m.group()) else 0)
        scenes.append({"id": s["id"], "start": round(start - 0.15 if scenes else 0, 3), "words": words})
    for i, s in enumerate(scenes):
        s["end"] = scenes[i + 1]["start"] if i + 1 < len(scenes) else round(t + 1.5, 3)
    return {"duration": scenes[-1]["end"], "scenes": scenes}


def page_errors(out):
    return out.replace("page errors: ", "").replace("storyboard: ", "").replace("pacing: ", "").split("; ")


def render(job, cfg, run, state):
    lane, proj, sb = lane_of(job), run / "short", job.get("storyboard")
    bad = lambda errs: ("invalid", {"agentErrors": errs}, "")
    if not isinstance(sb, dict) or not isinstance(sb.get("scenes"), list):
        return bad(["storyboard must be a JSON object with a scenes list"])
    recent = job.get("recentHooks") or []
    if sb.get("hook") not in HOOKS:
        return bad([f"hook must be one of {', '.join(HOOKS)}, got {sb.get('hook')!r}"])
    if sb["hook"] in recent:
        return bad([f"hook {sb['hook']!r} was used recently ({', '.join(recent)}); pick a different pattern"])
    sb["lane"] = lane
    (proj / "storyboard.json").write_text(json.dumps(sb, indent=1, ensure_ascii=False))
    code, out = sh(sys.executable, here / "compile.py", proj)
    if code:
        return bad([l[2:] for l in out.splitlines() if l.startswith("- ")] or [out])
    errs = factcheck.check_numbers(sb, job["brief"]["facts"])
    if errs:
        return bad(errs + ["use only numbers that appear in the brief's facts, written the same way"])
    src = run / job.get("sourcesText", "sources.txt")
    errs = factcheck.check_quote_parts(sb, src.read_text() if src.is_file() else "")
    if errs:
        return bad(errs)
    (proj / "timing.js").write_text("window.TIMING = " + json.dumps(fake_timing(sb)) + ";\n")
    sh(sys.executable, here / "compile.py", proj)
    code, out = sh("node", here / "check.mjs", proj)
    if code and "pacing:" not in out:  # pacing on estimated timings is a guess; slot and anchor errors are real
        return bad(page_errors(out))
    engine = cfg.get("voice", "kokoro")
    if engine == "elevenlabs":
        code, out = sh(sys.executable, here / "tts_el.py", proj, VOICES[lane]["elevenlabs"], cfg.get("elevenModel", "eleven_v4_turbo"))
    else:
        code, out = sh(sys.executable, here / "tts.py", proj, VOICES[lane]["kokoro"])
    if code:
        raise SystemExit(f"voice failed: {out[-500:]}")
    level_voice(proj / "voice.mp3")
    sh(sys.executable, here / "compile.py", proj)
    code, out = sh("node", here / "check.mjs", proj)
    if code:  # the model never hears the voice: give it the real word times so it can re-anchor
        t = json.loads((proj / "timing.js").read_text()[len("window.TIMING = "):].rstrip().rstrip(";"))
        times = " | ".join(f"scene {x['id']} runs {x['start']:.1f}-{x['end']:.1f}s: " + " ".join(f"{w['w']}@{w['s']:.1f}" for w in x["words"]) for x in t["scenes"])
        return bad(page_errors(out) + [f"(the narration's real word times; keep `say` unchanged if you only need to move anchors) {times}"])
    code, out = sh(sys.executable, here / "sfx_render.py", proj)
    if code:
        raise SystemExit(f"sound failed: {out[-500:]}")
    hf = ["npx", "--yes", f"hyperframes@{cfg.get('hyperframes', '0.8.174')}"]
    for _ in range(2):  # HyperFrames' Chrome sometimes fails to shut down; that is not the storyboard's fault
        code, out = sh(*hf, "check", proj, timeout=900)
        finds = [l.strip() for l in out.splitlines() if "✗" in l]
        if not any("check_cleanup_failure" in f or "check_runtime_failure" in f for f in finds):
            break
    if finds and all("check_cleanup_failure" in f for f in finds):
        finds = []  # the check itself ran; only the browser cleanup failed twice
    if finds:
        return bad(finds)
    if cfg.get("render", True):
        code, out = sh(*hf, "render", proj, "--quality", "high", "--output", run / "short.mp4", timeout=3000)
        if code:
            raise SystemExit(f"render failed: {out[-800:]}")
    return "next", publish_meta(job, sb, lane), f"rendered ({engine} voice)"


VOICE_LUFS = -16.0  # sfx_render.py masters the bed at a fixed level under this


def level_voice(path):
    """Set the voiceover to VOICE_LUFS with one linear gain (timing untouched), peaks held under -1.5 dBFS."""
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    gain = VOICE_LUFS - float(re.findall(r"I:\s+(-?[\d.]+) LUFS", log)[-1])
    tmp = path.with_suffix(".levelled.mp3")
    code, out = sh("ffmpeg", "-v", "error", "-y", "-i", path, "-af", f"volume={gain:.2f}dB,alimiter=limit=0.84:level=false", "-c:a", "libmp3lame", "-b:a", "192k", tmp)
    if code:
        raise SystemExit(f"voice levelling failed: {out[-500:]}")
    tmp.replace(path)


def publish_meta(job, sb, lane):
    # sources and credits live on the video's website page (mode `site`); the description only links to it
    title = sb.get("title", "")[:95]
    slug = time.strftime("%Y-%m-%d") + "-" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60].strip("-")
    desc = f"{job['brief'].get('story', '')}\n\nSources and media credits: {SITE}/videos/{slug}/"
    # the first two also go into the title (youtube-publish): the topic, then #shorts
    tags = {"tech": ["technews", "shorts", "tech", "ai"], "space": ["space", "shorts", "science", "nasa"]}[lane]
    # the shape youtube-publish reads: job.short.file (a file in the run folder) and job.meta
    return {"short": {"file": "short.mp4"}, "meta": {"title": title, "description": desc[:4800], "hashtags": tags}, "siteSlug": slug}


def posts(job, cfg, run, state):
    return reddit.posts(job, cfg, run, state)


def story(job, cfg, run, state):
    return reddit.story(job, cfg, run, state, level_voice)


def record(job, cfg, run, state):
    if job.get("lane") == "reddit":
        return reddit.record(job, cfg, run, state)
    state.mkdir(parents=True, exist_ok=True)
    cand = next((c for c in job.get("candidates", []) if c["id"] == (job.get("pick") or {}).get("id")), {})
    covered, hooks = jread(state / "covered.json", []), jread(state / "hooks.json", [])
    if cand:
        covered.append({"url": cand["sources"][0]["url"], "title": cand["title"], "date": time.strftime("%Y-%m-%d")})
    if (job.get("storyboard") or {}).get("hook"):
        hooks.append(job["storyboard"]["hook"])
    (state / "covered.json").write_text(json.dumps(covered[-300:], indent=1, ensure_ascii=False))
    (state / "hooks.json").write_text(json.dumps(hooks[-20:]))
    wish = (job.get("storyboard") or {}).get("wish")
    if wish:  # the animation the storyboard writer wanted and did not have: what to build next
        wishes = jread(state / "wishes.json", [])
        wishes.append({"date": time.strftime("%Y-%m-%d"), "lane": job.get("lane"), "wish": wish})
        (state / "wishes.json").write_text(json.dumps(wishes[-200:], indent=1, ensure_ascii=False))
    return "next", {}, f"recorded; {len(covered)} stories covered"


def https(url):
    return isinstance(url, str) and urlsplit(url).scheme == "https" and bool(urlsplit(url).netloc)


def site(job, cfg, run, state):
    # a Pages deploy replaces the whole site, so it is rebuilt from the live catalogue plus this lane's own entries
    lane, slug, video = lane_of(job), job.get("siteSlug"), (job.get("youtube") or {}).get("videoId")
    if not slug or not video:
        raise SystemExit("site needs siteSlug (from render) and youtube.videoId (from youtube-publish)")
    ch, b, caution = CHANNELS[lane], job.get("brief") or {}, (job.get("facts") or {}).get("caution")
    entry = {"slug": slug, "lane": ch["lane"], "channelUrl": ch["url"], "channelName": ch["name"], "title": (job.get("meta") or {}).get("title", ""),
             "summary": b.get("story", ""), "publishedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "videoId": video,
             "sources": [{"label": s.get("title") or s["url"], "url": s["url"], "detail": ""} for s in job.get("sources", []) if https(s.get("url"))],
             "credits": [{"label": i.get("credit", ""), "url": i["page"], "detail": ""} for i in b.get("images", []) if https(i.get("page"))],
             "limitations": [{"text": caution, "sources": []}] if caution else []}
    state.mkdir(parents=True, exist_ok=True)
    own = [e for e in jread(state / "site-entries.json", []) if e["slug"] != slug] + [entry]
    # saved before deploying: an entry a failed or overlapping deploy missed goes up again with the lane's next run
    (state / "site-entries.json").write_text(json.dumps(own[-300:], indent=1, ensure_ascii=False))
    project = os.environ.get("NEWSROOM_SITE_CLOUDFLARE_PROJECT", "")
    if not project:
        raise SystemExit("NEWSROOM_SITE_CLOUDFLARE_PROJECT is not set")
    try:
        # Cloudflare answers urllib's default User-Agent with 403
        with urllib.request.urlopen(urllib.request.Request(f"{SITE}/catalog.json", headers={"User-Agent": "autobiz-shorts"}), timeout=30) as r:
            live = json.load(r)["videos"]
    except Exception as e:
        raise SystemExit(f"could not read the live catalog.json ({e}); not deploying, as that would drop every other video")
    videos = newsroom_site.merge(live, own)
    newsroom_site.build(videos, run / "site")
    code, out = sh("npx", "--yes", "wrangler@4.138.0", "pages", "deploy", run / "site", "--project-name", project, "--branch", "main", "--commit-dirty=true", timeout=600)
    if code:
        raise SystemExit(f"wrangler pages deploy failed: {out[-800:]}")
    return "next", {"siteUrl": f"{SITE}/videos/{slug}/"}, f"site deployed with {len(videos)} videos"


MODES = {f.__name__: f for f in (feeds, posts, story, sources, facts, images, brief, render, record, site)}

if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("mode", choices=MODES)
    for k in ("run", "state", "job", "config", "out"):
        a.add_argument(f"--{k}", required=True)
    args = a.parse_args()
    run, state = Path(args.run).resolve(), Path(args.state).resolve()
    port, output, log = MODES[args.mode](jread(args.job, {}), jread(args.config, {}), run, state)
    Path(args.out).write_text(json.dumps({"port": port, "output": output, "log": log[-2000:]}, ensure_ascii=False))
    print(f"{args.mode}: {port} {log[-300:]}")
