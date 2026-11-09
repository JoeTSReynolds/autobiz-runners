"""YouTube sources through yt-dlp: search, info + English word timings, phrase finding, low-res frame probes."""
import json, os, re, string
from . import align
from .util import run


def search(query, n=15):
    """Flat ytsearch -> [{id, title, channel, duration, view_count, live_status, timestamp, upload_date}] (keys with no value left out)."""
    out = run(['yt-dlp', '--flat-playlist', '--print', '%(.{id,title,channel,duration,view_count,live_status,timestamp,upload_date})j',
               f'ytsearch{n}:{query}'], capture_output=True, text=True).stdout
    return [{k: v for k, v in json.loads(l).items() if v is not None} for l in out.split('\n') if l.strip()]


def _translated(tracks):
    return any('tlang=' in t.get('url', '') for t in tracks)


def pick_track(info):
    """Language key of the English caption track to read: manual English first, then auto English. Never a track translated
    from another language. None if there is none."""
    for key in ('subtitles', 'automatic_captions'):
        langs = [l for l, t in (info.get(key) or {}).items() if re.match(r'en($|[-_])', l) and not _translated(t)]
        if langs:
            return min(langs, key=lambda l: (not l.endswith('-orig'), l))
    return None


_LABEL = re.compile(r"(?:^|\s)(?:>>\s*)?[A-Z][A-Z.'\- ]{1,24}:(?=\s)")  # speaker labels: GORDON:, MR. SMITH:


def parse_json3(path):
    """json3 caption file -> word timings [{w, s, e}] in seconds."""
    out = []
    for ev in sorted(json.load(open(path)).get('events', []), key=lambda e: e.get('tStartMs', 0)):
        segs = [s for s in ev.get('segs', []) if s.get('utf8', '').strip()]
        end = (ev['tStartMs'] + ev.get('dDurationMs', 0)) / 1000
        for i, s in enumerate(segs):
            st = (ev['tStartMs'] + s.get('tOffsetMs', 0)) / 1000
            e = max((ev['tStartMs'] + segs[i + 1].get('tOffsetMs', 0)) / 1000 if i + 1 < len(segs) else end, st)
            # manual captions put a whole line in one segment: split it into words spread evenly over the segment, without
            # speaker labels ("GORDON:") and music notes
            ws = [w for w in _LABEL.sub(' ', s['utf8'].replace('\u266a', ' ')).replace('>>', ' ').split() if w.strip()]
            for k, w in enumerate(ws):
                a = st + (e - st) * k / len(ws)
                out.append(dict(w=w, s=round(a, 3), e=round(st + (e - st) * (k + 1) / len(ws), 3)))
    # rolling captions repeat words across events: drop words that start before the previous one ended and repeat it
    return [w for i, w in enumerate(out) if not (i and w['w'] == out[i - 1]['w'] and w['s'] < out[i - 1]['e'])]


def info_and_words(video_id, out_dir):
    """One yt-dlp call (no video) -> (info dict, words). words is [] when the video has no usable English track.
    Raises RuntimeError when yt-dlp gave no info at all (rate limit, bot check, unavailable)."""
    os.makedirs(out_dir, exist_ok=True)
    info_f = os.path.join(out_dir, f'{video_id}.info.json')
    if not os.path.exists(info_f):
        r = run(['yt-dlp', '--skip-download', '--write-info-json', '--write-subs', '--write-auto-subs', '--sub-langs', 'en,en-orig,en-GB,en-US,en-CA,en-AU',
                 '--sub-format', 'json3', '--no-playlist', '-o', os.path.join(out_dir, '%(id)s.%(ext)s'),
                 f'https://www.youtube.com/watch?v={video_id}'], capture_output=True, text=True)
        if not os.path.exists(info_f):
            why = 'rate-limited (429)' if '429' in r.stderr else 'bot check' if 'Sign in' in r.stderr else 'no info'
            raise RuntimeError(f'info unavailable for {video_id}: {why}\n{r.stderr[-300:]}')
    info = json.load(open(info_f))
    lang = pick_track(info)
    f = os.path.join(out_dir, f'{video_id}.{lang}.json3') if lang else None
    words = parse_json3(f) if f and os.path.exists(f) else []
    # a manual track has one time per line (its words are spread evenly): keep its wording, take the timing of YouTube's own
    # speech recognition. shortcut: only the en-orig track; a plain auto `en` shares the manual track's file name, so it is not read.
    auto = os.path.join(out_dir, f'{video_id}.en-orig.json3')
    if words and lang in (info.get('subtitles') or {}) and lang != 'en-orig' and os.path.exists(auto):
        words = align.merge(words, parse_json3(auto))
    return info, words


def sentences(ws):
    """Split word list into [{start,end,text}] on . ? ! and gaps >= 0.8 s."""
    res, cur = [], []
    for i, w in enumerate(ws):
        cur.append(w)
        gap = ws[i + 1]['s'] - w['e'] if i + 1 < len(ws) else 99
        if w['w'][-1] in '.?!' or gap >= 0.8:
            res.append(dict(start=cur[0]['s'], end=cur[-1]['e'], text=' '.join(x['w'] for x in cur))); cur = []
    return res


def _norm(s): return s.lower().translate(str.maketrans('', '', string.punctuation + '’‘“”'))


def find_phrase(ws, phrase):
    """(start, end) of first run of words matching phrase, allowing one phrase word to be missing; else None."""
    p, norm = [_norm(x) for x in phrase.split()], [_norm(w['w']) for w in ws]
    for i in range(len(ws)):
        pi, wi, miss = 0, i, 0
        while pi < len(p):
            if wi < len(ws) and norm[wi] == p[pi]: pi += 1; wi += 1
            elif miss < 1 and pi > 0: miss += 1; pi += 1
            else: break
        if pi == len(p) and wi > i and norm[i] == p[0]: return ws[i]['s'], ws[wi - 1]['e']
    return None


def probe_frames(video_id, url, windows, out_dir, height=240):
    """Download tiny video-only clips for [(start, end)] windows in ONE yt-dlp call -> list of file paths, None where a window failed."""
    os.makedirs(out_dir, exist_ok=True)
    cmd = ['yt-dlp', '-f', f'bv[height<={height}]/bv*[height<={height}]/worst[vcodec!=none]', '--no-playlist', '--no-download-archive',
           '--force-keyframes-at-cuts', '-o', os.path.join(out_dir, f'{video_id}_%(section_start)s.%(ext)s')]
    for s, e in windows: cmd += ['--download-sections', f'*{s:.2f}-{e:.2f}']
    run(cmd + [url], capture_output=True, text=True)
    found = {}
    for name in os.listdir(out_dir):
        m = re.fullmatch(re.escape(video_id) + r'_(\d+(?:\.\d+)?)\.\w+', name)
        if m: found[float(m.group(1))] = os.path.join(out_dir, name)
    return [next((p for st, p in found.items() if abs(st - s) < 0.01), None) for s, _ in windows]
