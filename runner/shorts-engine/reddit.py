# The Reddit stories lane, called from stage.py (modes posts, story, and record for lane reddit).
# posts: fetch top posts per subreddit (RSS, archive fallback). story: validate the agent's retelling, voice it,
# cut sped-up b-roll, build the one-word captions + hook card and render short.mp4. No PIL here: the card is a prebuilt png.
import collections, html, json, math, os, random, re, subprocess, sys, time, urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

here = Path(__file__).parent.resolve()
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
ATOM = "{http://www.w3.org/2005/Atom}"
SEG_SECONDS, MIN_NARRATION, MAX_NARRATION, TARGET_NARRATION = 2.0, 30.0, 58.0, 44.0  # library sizing unit; each part runs 30 to 58 s
SERIES_MAX_CHARS, SERIES_FETCHES, MAX_PARTS = 9000, 5, 3
NUMBER_WORD = {2: "two", 3: "three"}


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


UPDATE_RE = re.compile(r"\b(update|part\s*2|pt\.?\s*2|final update)\b", re.I)
ORIGINAL_RE = re.compile(r"/comments/([a-z0-9]{5,8})(?![a-z0-9])|redd\.it/([a-z0-9]{5,8})(?![a-z0-9])")


def is_update(title):
    return bool(UPDATE_RE.search(title))


def find_original_id(markup, own_id):
    for m in ORIGINAL_RE.finditer(markup):
        if (m.group(1) or m.group(2)) != own_id:
            return m.group(1) or m.group(2)
    return None


def parse_feed(xml_text, sub):
    out = []
    for e in ET.fromstring(xml_text).iter(ATOM + "entry"):
        pid = (e.findtext(ATOM + "id") or "").removeprefix("t3_")
        link = e.find(ATOM + "link")
        body = (e.findtext(ATOM + "content") or "").split("<!-- SC_ON -->")[0]  # after it: "submitted by ... [link]"
        if pid:
            c = {"id": pid, "subreddit": sub, "title": (e.findtext(ATOM + "title") or "").strip(), "text": html_text(body),
                 "url": link.get("href") if link is not None else f"https://www.reddit.com/comments/{pid}/"}
            if is_update(c["title"]) and find_original_id(body, pid):
                c["originalId"] = find_original_id(body, pid)
            out.append(c)
    return out


def parse_archive(data, sub):
    # shortcut: archive scores are taken at ingest, so ranking by them is weaker than Reddit's weekly top; only a fallback
    posts = sorted(data.get("data", []), key=lambda p: (p.get("score") or 0, p.get("num_comments") or 0), reverse=True)
    out = [{"id": p["id"], "subreddit": sub, "title": (p.get("title") or "").strip(), "text": html_text(p.get("selftext") or ""),
            "url": "https://www.reddit.com" + p["permalink"], "_raw": p.get("selftext") or ""} for p in posts if p.get("id") and p.get("permalink")]
    for c in out:
        raw = c.pop("_raw")
        if is_update(c["title"]) and find_original_id(raw, c["id"]):
            c["originalId"] = find_original_id(raw, c["id"])
    return out


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
            and not c["text"].startswith(("[removed]", "[deleted]")) and not is_update(c["title"])]


def round_robin(by_sub, cap):
    out, lists = [], [list(v) for v in by_sub.values()]
    while len(out) < cap and any(lists):
        for lst in lists:
            if lst and len(out) < cap:
                out.append(lst.pop(0))
    return out


def fetch_post(oid, wait=True):
    # the post's own feed lists the post first, then its comments
    if wait:
        time.sleep(2)
    try:
        first = parse_feed(get(f"https://www.reddit.com/comments/{oid}/.rss"), "")[:1]
        return first[0] if first and first[0]["id"] == oid else None
    except Exception:
        return None


def series_candidate(upd, orig):
    if not orig or not upd["text"] or any(x["text"].startswith(("[removed]", "[deleted]")) for x in (orig, upd)):
        return None
    text = f"{orig['text']}\n\n--- UPDATE ---\n\n{upd['text']}"
    if len(text) > SERIES_MAX_CHARS:
        return None
    return {"id": upd["id"], "originalId": orig["id"], "subreddit": upd["subreddit"], "title": orig["title"], "text": text, "url": upd["url"], "series": True}


def posts(job, cfg, run, state):
    lane, used = lane_cfg(), set(jread(state / "used.json", []))
    by_sub, updates = {}, []
    for i, sub in enumerate(lane["subreddits"]):
        seen = {c["id"] for v in by_sub.values() for c in v}
        found = fetch_sub(sub, wait=i > 0)
        by_sub[sub] = [c for c in keep(found, used) if c["id"] not in seen]
        updates += [c for c in found if is_update(c["title"]) and c.get("originalId")]
    series, tried = [], set()
    for u in updates:
        if len(tried) >= SERIES_FETCHES:
            break
        if u["id"] in used or u["originalId"] in used or u["id"] in tried:
            continue
        tried.add(u["id"])
        sc = series_candidate(u, fetch_post(u["originalId"]))
        if sc:
            series.append(sc)
    cands = (series + round_robin(by_sub, 25))[:25]
    return ("next" if cands else "missing"), {"candidates": cands, "laneContext": {"channelName": lane["channelName"]}}, f"{len(cands)} candidates, {len(series)} series"


def parse_comments(xml_text):
    out = []
    for e in ET.fromstring(xml_text).iter(ATOM + "entry"):
        author = e.findtext(ATOM + "author/" + ATOM + "name") or ""
        text = html_text((e.findtext(ATOM + "content") or ""))
        if (e.findtext(ATOM + "id") or "").startswith("t1_") and text and not text.startswith("[deleted]") \
                and "automoderator" not in author.lower() and not author.lower().endswith("bot"):
            out.append(text)
    return out


VERDICT_RE = re.compile(r"\b(NTA|YTA|ESH|NAH)\b")
VERDICT_LABEL = {"NTA": "NOT the jerk", "YTA": "they WERE the jerk", "ESH": "everyone sucks here", "NAH": "no jerks here"}


def classify_verdicts(texts, top=15):
    texts = texts[:top]
    counts = collections.Counter(m.group(1) for m in (VERDICT_RE.search(t) for t in texts) if m)
    return dict(counts), len(texts)


def verdict_comment(counts, k):
    if sum(counts.values()) >= 3:
        tok = max(VERDICT_LABEL, key=lambda t: counts.get(t, 0))
        return f"🗳️ Reddit's verdict: {VERDICT_LABEL[tok]} ({counts[tok]} of the top {k} comments said {tok})."
    return None


def is_aita(sub):
    return sub.lower() in ("amitheasshole", "aitah")


def reddit_verdict(sub, pid):
    # a failed fetch never fails the step; the comment just goes without the verdict
    if is_aita(sub):
        try:
            time.sleep(2)
            counts, k = classify_verdicts(parse_comments(get(f"https://www.reddit.com/r/{sub}/comments/{pid}/.rss?sort=top&depth=1&limit=40")))  # top-level comments, best first (the default order is threaded replies)
            return verdict_comment(counts, k)
        except Exception:
            pass
    return None


# ---------- story: validation ----------

def story_parts(st):
    return st["parts"] if "parts" in st else [st]


def check_part(p, label, max_words):
    words = lambda k: len(str(p.get(k) or "").split())
    errs = []
    if not 6 <= words("hook") <= 20:
        errs.append(f"{label}hook is {words('hook')} words; write 6 to 20 (about 8 to 16)")
    if not 110 <= words("script") <= max_words:
        errs.append(f"{label}script is {words('script')} words; write 110 to {max_words}")
    if not 1 <= len(str(p.get("title") or "")) <= 70:
        errs.append(f"{label}title must be 1 to 70 characters")
    return errs


def check_story(story, candidates):
    if not isinstance(story, dict):
        return ["story must be a JSON object with id, hook, script and title (or id and parts)"]
    errs = []
    if story.get("id") not in [c.get("id") for c in candidates]:
        errs.append(f"story.id {story.get('id')!r} is not one of the candidate ids")
    if "parts" in story:
        ps = story["parts"]
        if not isinstance(ps, list) or not 2 <= len(ps) <= MAX_PARTS or not all(isinstance(p, dict) for p in ps):
            return errs + [f"story.parts must be a list of 2 to {MAX_PARTS} objects with hook, script and title"]
        for i, p in enumerate(ps, 1):
            errs += check_part(p, f"parts[{i}] ", 220)
            nxt = NUMBER_WORD.get(i + 1, "")
            tail = str(p.get("script") or "")[-200:].lower()
            if i < len(ps) and not (f"part {nxt}" in tail or f"part {i + 1}" in tail):
                errs.append(f'parts[{i}] script must end on the cliffhanger with a line like "Follow so you don\'t miss part {nxt}!"')
    else:
        errs += check_part(story, "", 180)
    if "question" in story and not (isinstance(story["question"], str) and len(story["question"]) <= 150):
        errs.append("question must be a string of at most 150 characters")
    return errs


def length_error(label, n_words, secs):
    if MIN_NARRATION <= secs <= MAX_NARRATION:
        return None
    fix = int(abs(n_words * TARGET_NARRATION / secs - n_words))
    how = f"add about {fix} words (or merge it into the neighbouring part)" if secs < MIN_NARRATION else f"cut about {fix} words (or move them into another part)"
    return f"{label} narration is {secs:.0f}s; each video must run {MIN_NARRATION:.0f} to {MAX_NARRATION:.0f}s, so {how}"


def make_title(story_title, part=None):
    tail = (f" (Part {part})" if part else "") + lane_cfg()["titleSuffix"]
    t = story_title.strip()
    return (t if len(t) + len(tail) <= 100 else t[:100 - len(tail) - 1].rstrip() + "…") + tail


def build_meta(story_title, comment, part=None):
    title = make_title(story_title, part)
    meta = {"title": title, "description": title, "tags": lane_cfg()["tags"], "hashtags": []}
    return {**meta, "comment": comment} if comment else meta


def part_comments(n, question, verdict, aita):
    # parts publish back to back, so every part gets a comment: an opinion question, then a subscribe ask;
    # an AITA story's last part asks "jerk or not" and then reveals Reddit's own verdict
    ask = question or "What would you have done? 👇"
    first = [f"{ask}\n\nPart {i + 2} is already up on the channel! Subscribe so you never miss a part ❣️" for i in range(n - 1)]
    last = ["Jerk or NOT the jerk? Tell us below 👇", verdict] if aita else [ask]
    return first + ["\n\n".join(x for x in last + ["Subscribe for a new story every day ❣️"] if x)]


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


def follow_start(timing):
    # where the closing "Follow so you don't miss part two!" line starts (None when this part has none)
    words = [w for sc in timing["scenes"] if sc["id"] != "hook" for w in sc["words"]][-12:]
    return next((w["s"] for w in reversed(words) if w["w"].lower().strip("\"'“”").startswith("follow")), None)


def build_ass(timing, hook_text, next_part=None, end=None):
    pop = r"{\an5\pos(540,960)\fscx70\fscy70\t(0,90,\fscx112\fscy112)\t(90,160,\fscx100\fscy100)}"
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Word,Lilita One,120,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,8,3,5,40,40,40,1\n"
            "Style: Card,Lilita One,54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    lines, follow = [], follow_start(timing) if next_part else None
    for sc in timing["scenes"]:
        if sc["id"] == "hook":
            lines.append(f"Dialogue: 1,{ts(0)},{ts(sc['end'])},Card,,0,0,0,,"
                         + "{\\an4\\pos(90,800)\\fs%d\\fad(0,250)}" % wrap_hook(hook_text)[1] + "\\N".join(esc(l) for l in wrap_hook(hook_text)[0]))
            continue
        ws = sc["words"]
        for i, w in enumerate(ws):
            if follow is not None and w["s"] >= follow:
                break  # the follow card says it instead
            stop = ws[i + 1]["s"] if i + 1 < len(ws) else w["e"] + 0.3
            lines.append(f"Dialogue: 0,{ts(w['s'])},{ts(stop)},Word,,0,0,0,,{pop}{esc(w['w'])}")
    if follow is not None:
        lines.append(f"Dialogue: 1,{ts(follow)},{ts(end if end is not None else timing['duration'])},Card,,0,0,0,,"
                     + "{\\an4\\pos(90,800)\\fs64\\fad(200,0)}" + f"Part {next_part} is up next!\\N{{\\fs48}}Follow so you don't miss it")
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


def has_overlay_text(boxes):
    # RapidOCR boxes: [points, text, confidence]; a source's @handle watermark is small and allowed
    return any(conf >= 0.8 and sum(c.isalpha() for c in text) >= 3 and not text.strip().startswith("@") for _, text, conf in boxes or [])


_ocr = []


def segment_has_text(seg):
    if not _ocr:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr.append(RapidOCR())
        except ImportError:
            _ocr.append(None)
            print("rapidocr_onnxruntime missing: b-roll is not checked for burned-in text", file=sys.stderr)
    if _ocr[0] is None:
        return False
    frame = seg.with_suffix(".png")
    try:
        for t in (0.3, 1.2, 2.2):  # captions and banners pop in and out, so look at three moments
            code, _ = sh("ffmpeg", "-v", "error", "-y", "-ss", f"{t}", "-i", seg, "-frames:v", "1", "-vf", "scale=480:-2", frame)
            if not code and has_overlay_text(_ocr[0](str(frame))[0]):
                return True
    finally:
        frame.unlink(missing_ok=True)
    return False


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
        seg = lib / f"seg_{tag}_{made:02d}.mp4"
        code, _ = sh("ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-t", "3.2", "-i", src, "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
                     "-crf", "22", "-video_track_timescale", "15360", seg)
        if not code and segment_has_text(seg):
            seg.unlink()
            code = 1
        made += 0 if code else 1
    return made


def top_up(lib, need, state, run, sources):
    lib.mkdir(parents=True, exist_ok=True)
    archive = state / "broll-archive.txt"
    done = set(archive.read_text().split()) if archive.exists() else set()
    pool = [i for i in source_ids(state, sources) if i not in done]
    random.shuffle(pool)
    error, fails = "", 0
    for vid in pool[:max(12, need // 2)]:  # a video gives at most 4 shots, about 2 after the text filter
        if len(list(lib.glob("seg_*.mp4"))) >= need or fails >= 5:  # 5 failures in a row: blocked, don't burn more sources
            break
        code, out = ytdlp("-f", "bv*[height<=1280][height>=640]/bv*", "--no-playlist", "-o", str(run / f"src_{vid}.%(ext)s"), f"https://www.youtube.com/shorts/{vid}")
        fails = fails + 1 if code else 0
        if code:
            error = (out.strip().splitlines() or [""])[-1][:300]
        with archive.open("a") as f:
            f.write(vid + "\n")
        for src in run.glob(f"src_{vid}.*"):
            if not code:
                cut_source(src, lib, vid)
            src.unlink()
    have = len(list(lib.glob("seg_*.mp4")))
    if have < need and have < 0.6 * need:
        raise SystemExit(f"b-roll library has {have} segments, need {need}; downloads failed or sources are used up (check YTDLP_COOKIES_FILE)" + (f"; last yt-dlp error: {error}" if error else ""))


# ---------- story: render ----------

def ffesc(p):
    return str(p).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def narrate(proj, hook, script, lane, level_voice, label):
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "script.json").write_text(json.dumps([{"id": "hook", "text": hook}, {"id": "body", "text": script}]))
    code, out = sh(sys.executable, here / "tts.py", proj, lane["voice"], lane["speed"])
    if code:
        raise SystemExit(f"voice failed: {out[-500:]}")
    level_voice(proj / "voice.mp3")
    timing = json.loads((proj / "timing.js").read_text()[len("window.TIMING = "):].rstrip().rstrip(";"))
    code, vd = sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", proj / "voice.mp3")
    end = min(timing["duration"], float(vd) + 0.4) if not code else timing["duration"]  # tts.py adds a 1.2 s hold the audio does not have; cut it
    return timing, end, length_error(label, len((hook + " " + script).split()), end)


def render_part(proj, hook, timing, end, lib, seed, out_file, next_part=None):
    chosen = pick_segments([p.name for p in lib.glob("seg_*.mp4")], math.ceil(end / 2.3), seed)
    (proj / "list.txt").write_text("".join(f"file '{lib / n}'\n" for n in chosen))
    code, out = sh("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", proj / "list.txt", "-c", "copy", proj / "broll.mp4")
    if code:
        raise SystemExit(f"b-roll concat failed: {out[-500:]}")
    hook_end = next(s["end"] for s in timing["scenes"] if s["id"] == "hook")
    (proj / "captions.ass").write_text(build_ass(timing, hook, next_part, end), encoding="utf-8")
    follow = follow_start(timing) if next_part else None
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
    if follow is not None:  # the end card (same panel, a Subscribe pill) under the "Part N is up next!" text, from "Follow" to the end
        n = inputs.count("-i")
        inputs += ["-framerate", "30", "-loop", "1", "-t", f"{end + 1:.2f}", "-i", here / "lanes" / "reddit" / "card_follow.png"]
        fc = fc.replace("[o];[o]subtitles", f"[o];[{n}:v]format=rgba,fade=t=in:st={follow:.2f}:d=0.2:alpha=1[fc];[o][fc]overlay=0:0:enable='gte(t,{follow:.2f})'[o2];[o2]subtitles")
    code, out = sh("ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", audio, "-t", f"{end:.2f}",
                   "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_file)
    if code:
        raise SystemExit(f"render failed: {out[-800:]}")
    for n in set(chosen):  # each segment is used once ever, so later parts never reuse it
        (lib / n).unlink(missing_ok=True)
    return len(set(chosen))


def story(job, cfg, run, state, level_voice):
    st, cands = job.get("story"), job.get("candidates", [])
    errs = check_story(st, cands)
    if errs:
        return "invalid", {"agentErrors": errs}, ""
    lane, ps = lane_cfg(), story_parts(st)
    multi = "parts" in st
    voiced, errs = [], []
    for i, p in enumerate(ps, 1):
        proj = run / ("reddit" if i == 1 else f"reddit{i}")
        timing, end, err = narrate(proj, p["hook"], p["script"], lane, level_voice, f"parts[{i}]" if multi else "script")
        errs += [err] if err else []
        voiced.append((proj, p, timing, end))
    if errs:
        return "invalid", {"agentErrors": errs}, ""
    lib = state / "broll"
    top_up(lib, sum(math.ceil(t["duration"] / SEG_SECONDS) + 4 for _, _, t, _ in voiced), state, run, lane["brollSources"])
    out_parts, used_segs = [], 0
    for i, (proj, p, timing, end) in enumerate(voiced, 1):
        name = "short.mp4" if i == 1 else f"short{i}.mp4"
        used_segs += render_part(proj, p["hook"], timing, end, lib, f"{st['id']}-{i}", run / name, i + 1 if i < len(voiced) else None)
        out_parts.append((name, p))
    sub = next(c["subreddit"] for c in cands if c["id"] == st["id"])
    q = st.get("question")
    comments = part_comments(len(ps), q, reddit_verdict(sub, st["id"]), is_aita(sub))
    parts = [{"short": {"file": name}, "meta": build_meta(p["title"], comments[i], i + 1 if multi else None)} for i, (name, p) in enumerate(out_parts)]
    out = {"short": parts[0]["short"], "meta": parts[0]["meta"]}
    if multi:
        out.update(parts=parts, partIndex=0)
    return "next", out, f"rendered {len(ps)} part(s), {sum(v[3] for v in voiced):.1f}s from {used_segs} segments"


def nextpart(job, cfg, run, state):
    ids = list(job.get("partVideoIds") or []) + [(job.get("youtube") or {}).get("videoId")]
    parts, i = job.get("parts") or [], (job.get("partIndex") or 0) + 1
    if i >= len(parts):
        return "missing", {}, "no more parts"
    meta = dict(parts[i]["meta"])
    if ids[0]:
        meta["description"] += f"\n\nPart 1: https://youtube.com/shorts/{ids[0]}"
    return "next", {"partVideoIds": ids, "partIndex": i, "short": parts[i]["short"], "meta": meta}, f"part {i + 1} of {len(parts)}"


def record(job, cfg, run, state):
    state.mkdir(parents=True, exist_ok=True)
    sid = job["story"]["id"]
    orig = job["story"].get("originalId") or next((c.get("originalId") for c in job.get("candidates", []) if c["id"] == sid), None)
    used = jread(state / "used.json", []) + [sid] + ([orig] if orig else [])
    (state / "used.json").write_text(json.dumps(used[-3000:]))
    return "next", {}, f"recorded; {len(used)} stories used"
