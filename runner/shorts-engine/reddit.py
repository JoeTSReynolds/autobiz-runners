# The Reddit stories lane, called from stage.py (modes posts, story, and record for lane reddit).
# posts: fetch top posts per subreddit (RSS, archive fallback). story: validate the agent's retelling, voice it,
# cut sped-up b-roll, build the one-word captions + hook card and render short.mp4. No PIL here: the card is a prebuilt png.
import html, json, math, os, random, re, subprocess, sys, time, urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

here = Path(__file__).parent.resolve()
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
ATOM = "{http://www.w3.org/2005/Atom}"
SEG_SECONDS, MAX_NARRATION = 2.0, 59.0  # library sizing unit; Shorts stay under 60 s


def lane_cfg():
    return json.loads((here / "lanes" / "reddit" / "lane.json").read_text())


def jread(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def sh(*cmd, timeout=1500):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


# ---------- posts ----------

class _Text(HTMLParser):
    BLOCK = {"p", "div", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "br", "hr", "tr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK:
            self.out.append("\n\n")

    def handle_endtag(self, tag):
        self.handle_starttag(tag, None)

    def handle_data(self, data):
        self.out.append(data)


def html_text(markup):
    p = _Text()
    p.feed(markup)
    paras = [re.sub(r"\s+", " ", x).strip() for x in "".join(p.out).split("\n\n")]
    return "\n\n".join(x for x in paras if x)


def parse_feed(xml_text, sub):
    out = []
    for e in ET.fromstring(xml_text).iter(ATOM + "entry"):
        pid = (e.findtext(ATOM + "id") or "").removeprefix("t3_")
        link = e.find(ATOM + "link")
        body = (e.findtext(ATOM + "content") or "").split("<!-- SC_ON -->")[0]  # after it: "submitted by ... [link]"
        if pid:
            out.append({"id": pid, "subreddit": sub, "title": (e.findtext(ATOM + "title") or "").strip(), "text": html_text(body),
                        "url": link.get("href") if link is not None else f"https://www.reddit.com/comments/{pid}/"})
    return out


def parse_archive(data, sub):
    # shortcut: archive scores are taken at ingest, so ranking by them is weaker than Reddit's weekly top; only a fallback
    posts = sorted(data.get("data", []), key=lambda p: (p.get("score") or 0, p.get("num_comments") or 0), reverse=True)
    return [{"id": p["id"], "subreddit": sub, "title": (p.get("title") or "").strip(), "text": html_text(p.get("selftext") or ""),
             "url": "https://www.reddit.com" + p["permalink"]} for p in posts if p.get("id") and p.get("permalink")]


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def fetch_sub(sub, wait=True):
    if wait:
        time.sleep(2)
    try:
        found = parse_feed(get(f"https://www.reddit.com/r/{sub}/top/.rss?t=week"), sub)
        if found:
            return found
    except Exception:
        pass
    try:
        return parse_archive(json.loads(get(f"https://arctic-shift.photon-reddit.com/api/posts/search?subreddit={sub}&limit=50&sort=desc")), sub)
    except Exception:
        return []


def keep(cands, used):
    return [c for c in cands if c["id"] not in used and 600 <= len(c["text"]) <= 5000
            and not c["text"].startswith(("[removed]", "[deleted]")) and not c["title"].lower().startswith("update")]


def round_robin(by_sub, cap):
    out, lists = [], [list(v) for v in by_sub.values()]
    while len(out) < cap and any(lists):
        for lst in lists:
            if lst and len(out) < cap:
                out.append(lst.pop(0))
    return out


def posts(job, cfg, run, state):
    lane, used = lane_cfg(), set(jread(state / "used.json", []))
    by_sub = {}
    for i, sub in enumerate(lane["subreddits"]):
        seen = {c["id"] for v in by_sub.values() for c in v}
        by_sub[sub] = [c for c in keep(fetch_sub(sub, wait=i > 0), used) if c["id"] not in seen]
    cands = round_robin(by_sub, 25)
    return ("next" if cands else "missing"), {"candidates": cands, "laneContext": {"channelName": lane["channelName"]}}, f"{len(cands)} candidates"


# ---------- story: validation ----------

def check_story(story, candidates):
    if not isinstance(story, dict):
        return ["story must be a JSON object with id, hook, script and title"]
    words = lambda k: len(str(story.get(k) or "").split())
    errs = []
    if story.get("id") not in [c.get("id") for c in candidates]:
        errs.append(f"story.id {story.get('id')!r} is not one of the candidate ids")
    if not 6 <= words("hook") <= 20:
        errs.append(f"hook is {words('hook')} words; write 6 to 20 (about 8 to 16)")
    if not 110 <= words("script") <= 180:
        errs.append(f"script is {words('script')} words; write 110 to 180")
    if not 1 <= len(str(story.get("title") or "")) <= 70:
        errs.append("title must be 1 to 70 characters")
    return errs


# ---------- captions and hook card ----------

def ts(t):
    cs = round(t * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def esc(w):
    return w.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def wrap_hook(text):
    # shortcut: no font metrics at runtime (no PIL); 0.5 em per character is a safe average for Lilita One
    for size in range(60, 31, -4):
        lines, cur = [], ""
        for w in text.split():
            if cur and len(cur) + 1 + len(w) > 900 / (0.5 * size):
                lines.append(cur); cur = w
            else:
                cur = f"{cur} {w}".strip()
        lines.append(cur)
        if len(lines) <= 3:
            return lines, size
    return lines, size


def build_ass(timing, hook_text):
    pop = r"{\an5\pos(540,960)\fscx70\fscy70\t(0,90,\fscx112\fscy112)\t(90,160,\fscx100\fscy100)}"
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Word,Lilita One,120,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,8,3,5,40,40,40,1\n"
            "Style: Card,Lilita One,54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    lines = []
    for sc in timing["scenes"]:
        if sc["id"] == "hook":
            lines.append(f"Dialogue: 1,{ts(0)},{ts(sc['end'])},Card,,0,0,0,,"
                         + "{\\an4\\pos(90,800)\\fs%d\\fad(0,250)}" % wrap_hook(hook_text)[1] + "\\N".join(esc(l) for l in wrap_hook(hook_text)[0]))
            continue
        ws = sc["words"]
        for i, w in enumerate(ws):
            end = ws[i + 1]["s"] if i + 1 < len(ws) else w["e"] + 0.3
            lines.append(f"Dialogue: 0,{ts(w['s'])},{ts(end)},Word,,0,0,0,,{pop}{esc(w['w'])}")
    return head + "\n".join(lines) + "\n"


# ---------- b-roll library ----------

def source_of(name):
    return name[4:15]  # seg_<11-char YouTube id>_<nn>.mp4


def pick_segments(names, n, seed):
    names = sorted(names)
    random.Random(seed).shuffle(names)
    left, order = {}, []
    for x in names:
        left.setdefault(source_of(x), []).append(x)
    while left:  # take from the fullest other source, so no two shots of one video play back to back
        last = source_of(order[-1]) if order else None
        src = max((s for s in left if s != last), key=lambda s: len(left[s]), default=last)
        order.append(left[src].pop())
        if not left[src]:
            del left[src]
    return [order[i % len(order)] for i in range(n)]  # cycles (repeats footage) only when the library is short


def ytdlp(*args):
    cookies = os.environ.get("YTDLP_COOKIES_FILE")
    exe = [__import__("shutil").which("yt-dlp") or "yt-dlp"]
    return sh(*exe, *(["--cookies", cookies] if cookies else []), *args, timeout=900)


def source_ids(state, sources):
    cache = jread(state / "broll-ids.json", {})
    if time.time() - cache.get("at", 0) > 7 * 86400 or set(cache.get("ids", {})) != set(sources):
        ids = {}
        for src in sources:
            code, out = ytdlp("--flat-playlist", "--print", "id", "--playlist-end", "200", src)
            ids[src] = [l for l in out.splitlines() if re.fullmatch(r"[\w-]{11}", l)] if not code else []
        if any(ids.values()):
            cache = {"at": time.time(), "ids": ids}
            (state / "broll-ids.json").write_text(json.dumps(cache))
    return sorted({i for v in cache.get("ids", {}).values() for i in v})


def cut_source(src, lib, tag):
    code, out = sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src)
    dur, made = float(out) if not code and out else 0, 0
    slots = int((dur - 2.0) // 3.2)
    # at most 4 shots per video, spread over it, so one craft doesn't fill the Short
    for k in range(min(4, slots)):
        t = 1.0 + (k * slots // min(4, slots)) * 3.2
        # setpts first (1.3x faster), then centre 9:16, zoom to drop corner logos and the bottom-centre channel watermark
        vf = ("setpts=PTS/1.3,crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',crop=iw*0.88:ih*0.88:(iw-ow)/2:ih*0.02,scale=720:1280:flags=lanczos,setsar=1,"
              "eq=saturation=1.2:contrast=1.05,fps=30,format=yuv420p")
        code, _ = sh("ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-t", "3.2", "-i", src, "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
                     "-crf", "22", "-video_track_timescale", "15360", lib / f"seg_{tag}_{made:02d}.mp4")
        made += 0 if code else 1
    return made


def top_up(lib, need, state, run, sources):
    lib.mkdir(parents=True, exist_ok=True)
    archive = state / "broll-archive.txt"
    done = set(archive.read_text().split()) if archive.exists() else set()
    pool = [i for i in source_ids(state, sources) if i not in done]
    random.shuffle(pool)
    for vid in pool[:12]:
        if len(list(lib.glob("seg_*.mp4"))) >= need:
            break
        code, out = ytdlp("-f", "bv*[height<=1280][height>=640]/bv*", "--no-playlist", "-o", str(run / f"src_{vid}.%(ext)s"), f"https://www.youtube.com/shorts/{vid}")
        with archive.open("a") as f:
            f.write(vid + "\n")
        for src in run.glob(f"src_{vid}.*"):
            if not code:
                cut_source(src, lib, vid)
            src.unlink()
    have = len(list(lib.glob("seg_*.mp4")))
    if have < need and have < 0.6 * need:
        raise SystemExit(f"b-roll library has {have} segments, need {need}; downloads failed or sources are used up (check YTDLP_COOKIES_FILE)")


# ---------- story: render ----------

def ffesc(p):
    return str(p).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def story(job, cfg, run, state, level_voice):
    st, cands = job.get("story"), job.get("candidates", [])
    errs = check_story(st, cands)
    if errs:
        return "invalid", {"agentErrors": errs}, ""
    lane, proj = lane_cfg(), run / "reddit"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "script.json").write_text(json.dumps([{"id": "hook", "text": st["hook"]}, {"id": "body", "text": st["script"]}]))
    code, out = sh(sys.executable, here / "tts.py", proj, lane["voice"], lane["speed"])
    if code:
        raise SystemExit(f"voice failed: {out[-500:]}")
    level_voice(proj / "voice.mp3")
    timing = json.loads((proj / "timing.js").read_text()[len("window.TIMING = "):].rstrip().rstrip(";"))
    dur = timing["duration"]
    code, vd = sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", proj / "voice.mp3")
    end = min(dur, float(vd) + 0.4) if not code else dur  # tts.py adds a 1.2 s hold the audio does not have; cut it
    if dur > MAX_NARRATION:
        n = len(st["script"].split())
        return "invalid", {"agentErrors": [f"narration is {dur:.0f}s; shorten the script to about {int(n * 56 / dur)} words"]}, ""
    lib = state / "broll"
    top_up(lib, math.ceil(dur / SEG_SECONDS) + 4, state, run, lane["brollSources"])
    chosen = pick_segments([p.name for p in lib.glob("seg_*.mp4")], math.ceil(end / 2.3), st["id"])
    (proj / "list.txt").write_text("".join(f"file '{lib / n}'\n" for n in chosen))
    code, out = sh("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", proj / "list.txt", "-c", "copy", proj / "broll.mp4")
    if code:
        raise SystemExit(f"b-roll concat failed: {out[-500:]}")
    hook_end = next(s["end"] for s in timing["scenes"] if s["id"] == "hook")
    (proj / "captions.ass").write_text(build_ass(timing, st["hook"]), encoding="utf-8")
    music = sorted((here / "lanes" / "reddit" / "music").glob("*.mp3"))
    fc = (f"[0:v]scale=1080:1920:flags=lanczos,setsar=1,fps=30[b];[1:v]format=rgba,fade=t=out:st={max(hook_end - 0.25, 0):.2f}:d=0.25:alpha=1[card];"
          f"[b][card]overlay=0:0:enable='lt(t,{hook_end:.2f})'[o];[o]subtitles=filename='{ffesc(proj / 'captions.ass')}':fontsdir='{ffesc(here / 'fonts')}'[v]")
    inputs = ["-i", proj / "broll.mp4", "-framerate", "30", "-loop", "1", "-t", f"{hook_end + 1:.2f}", "-i", here / "lanes" / "reddit" / "card.png", "-i", proj / "voice.mp3"]
    if music:  # music bed ducked under the voice
        inputs += ["-stream_loop", "-1", "-i", random.choice(music)]
        fc += ";[2:a]asplit=2[vs][vk];[3:a]volume=0.2[mu];[mu][vk]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md];[vs][md]amix=inputs=2:duration=first:dropout_transition=0,volume=2[a]"
        audio = "[a]"
    else:
        audio = "2:a"
    code, out = sh("ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", audio, "-t", f"{end:.2f}",
                   "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", run / "short.mp4")
    if code:
        raise SystemExit(f"render failed: {out[-800:]}")
    for n in set(chosen):  # each segment is used once ever
        (lib / n).unlink(missing_ok=True)
    sub = next(c["subreddit"] for c in cands if c["id"] == st["id"])
    desc = f"{st['hook']}\n\nStory from r/{sub}, retold.\n\n" + "#redditstories #reddit #shorts"
    return "next", {"short": {"file": "short.mp4"}, "meta": {"title": st["title"], "description": desc, "hashtags": lane["hashtags"]}}, f"rendered {end:.1f}s from {len(set(chosen))} segments"


def record(job, cfg, run, state):
    state.mkdir(parents=True, exist_ok=True)
    used = jread(state / "used.json", []) + [job["story"]["id"]]
    (state / "used.json").write_text(json.dumps(used[-3000:]))
    return "next", {}, f"recorded; {len(used)} stories used"
