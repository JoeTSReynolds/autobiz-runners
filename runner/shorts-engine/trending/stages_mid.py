"""Trending stages verify, music, probe, assets. Each is (job, cfg, run, state) -> (port, output, log); run and state are folders.

Spec: docs/plan/nowayclips-trending.plan.md, plan shape: docs/plan/briefs/plan-schema.md. Assumed input shapes (from mediaplan):
job.pool = [{id, url?, duration}], run/captions/<id>.words.json = [{w, s, e}], job.articles = [{outlet, domain, url, text}].
Every `missing` also appends person.qid to rejectedPeople and sets agentErrors to one line, so the route agent sees why.
"""
import copy, datetime as dt, email.utils, json, os, re, subprocess, tempfile, time, urllib.parse, urllib.request
import numpy as np
from collections import Counter
from pathlib import Path
from . import align, net, ytsrc

LEAD, TAIL, CAP = 0.08, 0.15, 0.6   # cut lead-in before a word start, tail after a word end, max end past the last word's start
MOMENT_SPEED = 0.8                  # tribute silent moments are shown at 0.8x
TOPN_CARD, TOPN_CLOSER = 0.8, 3.0   # topn: countdown card per moment, closer card (s)
TOPN_MAX_S = 12                     # topn: longest moment (a roast with its setup runs 10-11 s)
TOPN_MIN_S = 2.5                    # topn: shortest quoted part (the lead-in and the reply lengthen the clip)
TOPN_PRE, TOPN_REPLY, REPLY_GAP = 0.5, 5.0, 1.2   # topn: lead-in, longest reply kept, pause that ends a reply
VERIFY_TRIES = 2                    # fixable shortfalls the agent gets before the person is dropped
EDIT_SLAM, EDIT_HOLD = 1.2, 0.5      # edit: seconds per stat slam (2 beats) and the hold before the tail
EDIT_TAIL = 0.35                    # edit: share of the total that is the speech-free tail
WPS = 2.3                           # casefile narration, words per second (measured: Kokoro bm_george 1.12 with sentence gaps 2.33)
BLOCKED = re.compile(r'\b(super[- ]?injunctions?|injunctions?|anonymity orders?)\b', re.I)
UNNAMED = re.compile(r'\ba (famous|well-known|high-profile|unnamed)\s+\w+', re.I)
DENIAL = re.compile(r'\b(den(y|ies|ied|ying|ial|ials)|reject\w*)\b', re.I)


class _Short(Exception):
    """Too little usable material: fixable by the agent VERIFY_TRIES times, then a dead end for the person."""


class _Missing(Exception):
    pass


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _today():
    return _now().date()


def _fold(s):
    return re.sub(r'\s+', ' ', re.sub(r"[^\w\s]|_", ' ', str(s).lower().replace("'", '').replace('’', ''))).strip()


def _nwords(s):
    return len(re.sub(r'\[[^\]]*\]', ' ', s).split())


def _missing(job, stage, why):
    p, rej = job.get('person') or {}, list(job.get('rejectedPeople') or [])
    if p.get('qid') and p['qid'] not in rej:
        rej.append(p['qid'])
    return 'missing', {'rejectedPeople': rej, 'agentErrors': [f"{p.get('name', 'person')} rejected at {stage}: {why}"]}, why


STORY_TRIES = 3   # storyboards a person gets before verify drops them; route resets the count for each new person


def _invalid(errs):
    return 'invalid', {'agentErrors': errs}, f'{len(errs)} errors: ' + '; '.join(errs)[:200]


def _clip(key, src, start, end, person=True):
    return {'key': key, 'source': {k: src.get(k) for k in ('id', 'url', 'duration')}, 'start': round(start, 3), 'end': round(end, 3), 'person': person}


def _story(job, clips):
    return {**(job.get('story') or {}), 'clips': [{'role': 'moment', 'start': c['start'], 'end': c['end'], 'source': c['source']} for c in clips]}


def _plan_person(p):
    b, d = (p.get('born') or '')[:4], (p.get('died') or '')[:4]
    return {'qid': p.get('qid'), 'name': p.get('name'), 'born': p.get('born'), 'died': p.get('died'), 'years': f'{b} – {d}' if b and d else b}


# ---- words and quotes

def _clean_words(ws):
    """Drop caption tags ([applause], [Music playing]) and speaker markers (>>)."""
    out, intag = [], False
    for w in ws:
        t = w['w'].strip()
        if intag or t.startswith('['):
            intag = not t.endswith(']')
            continue
        t = re.sub(r'^>>+', '', t).strip()
        if t:
            out.append(dict(w, w=t))
    return out


def _clean_quote(q):
    return re.sub(r'\s+', ' ', re.sub(r'>>+|\[[^\]]*\]', ' ', q)).strip()


def _resolve(words, quote):
    """(start, end, words) of a quote in a cleaned word list, end capped at last word start + CAP; None if not found."""
    q = _clean_quote(quote)
    r = ytsrc.find_phrase(words, q) if q else None
    # the matched run by position, not by time: YouTube's word times overlap (a word ending after the next one starts)
    i = next((k for k, w in enumerate(words) if r and w['s'] == r[0]), None)
    j = next((k for k in range(i, len(words)) if words[k]['e'] == r[1]), None) if i is not None else None
    seg = words[i:j + 1] if j is not None else []
    return (r[0], min(r[1], seg[-1]['s'] + CAP), seg) if seg else None


def _cut(s, e, dur=None):
    """Snap a word span to a cut: lead-in before the first word, tail after the last."""
    return max(0.0, s - LEAD), min(e + TAIL, dur) if dur else e + TAIL


class _Ctx:
    def __init__(self, job, run):
        self.job, self.run, self.errs, self._w = job, Path(run), [], {}
        pool = job.get('pool') or []
        self.pool = {p['id']: p for p in (pool.values() if isinstance(pool, dict) else pool)}

    def source(self, sid, where):
        p = self.pool.get(sid)
        if not p:
            self.errs.append(f'{where}: source "{sid}" is not in the pool')
            return None
        return {'id': sid, 'url': p.get('url') or f'https://www.youtube.com/watch?v={sid}', 'duration': p.get('duration')}

    def words(self, sid):
        if sid not in self._w:
            f = self.run / 'captions' / f'{sid}.words.json'
            self._w[sid] = _clean_words(json.loads(f.read_text())) if f.exists() else None
        return self._w[sid]

    def find(self, sid, quote, where, after=None):
        """(src, start, end, words) or None (error recorded)."""
        src = self.source(sid, where)
        if not src:
            return None
        ws = self.words(sid)
        if ws is None:
            self.errs.append(f'{where}: no captions for source "{sid}"')
            return None
        r = _resolve([w for w in ws if after is None or w['s'] >= after], quote)
        if not r:
            self.errs.append(f'{where}: quote not found in the captions of {sid}: "{quote}"')
            return None
        return (src, *r)


# ---- b-roll / photo candidates (network, patched in tests)

def _pexels_candidates(data):
    out = []
    for v in data.get('videos', []):
        fs = [f for f in v.get('video_files', []) if f.get('file_type') == 'video/mp4' and f.get('width') and f['width'] <= 1080 and f['height'] >= f['width']]
        if fs:
            f = max(fs, key=lambda f: f['width'])
            out.append({'provider': 'pexels', 'url': f['link'], 'kind': 'video', 'w': f['width'], 'h': f['height'], 'duration': v.get('duration'),
                        'credit': (v.get('user') or {}).get('name', ''), 'licence': 'Pexels License', 'page': v.get('url')})
    return out


def _pexels_videos(q):
    key = os.environ.get('PEXELS_API_KEY')
    if not key:
        return []
    url = 'https://api.pexels.com/videos/search?' + urllib.parse.urlencode({'query': q, 'per_page': 8, 'orientation': 'portrait'})
    with urllib.request.urlopen(urllib.request.Request(url, headers={'Authorization': key, 'User-Agent': 'autobiz-trending/1.0'}), timeout=30) as r:
        return _pexels_candidates(json.load(r))


def _commons_images(q, n=6):
    import commons
    return [{'provider': 'commons', 'url': r['thumb'], 'kind': 'image', 'w': r.get('width'), 'h': r.get('height'), 'credit': r.get('artist', ''),
             'licence': r.get('license', ''), 'title': r['title'], 'page': 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(r['title'].replace(' ', '_'))}
            for r in commons.search(q, n) if (r.get('width') or 0) >= 700 and r.get('thumb')]


def _safe(fn, q, *a):
    try:
        return fn(q, *a)
    except Exception:  # one provider failing must not fail the stage
        return []


def _broll_candidates(q):
    c = _safe(_pexels_videos, q)[:5]
    return c + _safe(_commons_images, q)[:3] if len(c) < 3 else c


# ---- verify

def _describe(c):
    """A candidate as a short readable phrase for the b-roll agent: the Pexels slug words or the Commons title."""
    if c.get('title'):
        return re.sub(r'\.\w{2,5}$', '', re.sub(r'^File:', '', c['title'])).replace('_', ' ').strip()
    slug = urllib.parse.urlparse(c.get('page') or '').path.rstrip('/').rsplit('/', 1)[-1]
    return re.sub(r'-\d+$', '', slug).replace('-', ' ')


def _broll_text(plan):
    """run/broll.txt: each distinct b-roll or tail query with its line text (b-roll only) and its candidates numbered from 0."""
    if plan.get('format') != 'edit':
        return ''
    seen, out = set(), []
    for q, line, cands in [(b['query'], plan['lines'][b['line']]['text'], b['candidates']) for b in plan['broll']] + [(t['query'], None, t['candidates']) for t in plan['tail']]:
        if q not in seen:
            seen.add(q)
            out.append(f'query: {q}\n' + (f'line: {line}\n' if line else '') + ''.join(f'{i}: {_describe(c)}\n' for i, c in enumerate(cands)))
    return '\n'.join(out)


def _v_tribute(cx, sb):
    errs = cx.errs
    sp, ms = sb.get('spine') or [], sb.get('moments') or []
    if len(sp) != 2:
        errs.append(f'spine: need exactly 2 lines, got {len(sp)}')
    spine = []
    for i, l in enumerate(sp):
        r = cx.find(l.get('source'), l.get('quote', ''), f'spine[{i}]')
        if r and len(_clean_quote(l['quote']).split()) < 12:
            errs.append(f'spine[{i}]: "{l["quote"]}" has {len(_clean_quote(l["quote"]).split())} words, at least 12 words needed')
        elif r:
            spine.append((l, *r))
    if not 4 <= len(ms) <= 8:
        errs.append(f'moments: need 4 to 8, got {len(ms)}')
    moments = []
    for i, m in enumerate(ms):
        src = cx.source(m.get('source'), f'moments[{i}]')
        s, e = m.get('start'), m.get('end')
        if not src:
            continue
        if not all(isinstance(x, (int, float)) for x in (s, e)) or not 0 <= s < e or (src['duration'] and e > src['duration']):
            errs.append(f'moments[{i}]: bad window {s}-{e} for source {src["id"]}')
        elif not 1.5 <= e - s <= 5:
            errs.append(f'moments[{i}]: {e - s:.1f} s, must be 1.5 to 5 s')
        else:
            moments.append(_clip(f'm{i}', src, s, e))
    if len({m['source']['id'] for m in moments}) < 2:
        errs.append('moments: all come from one video; take the silent moments from at least 2 different videos')
    n = _nwords(sb.get('closingLine') or '')
    if not 1 <= n <= 14:
        errs.append(f'closingLine: {n} words, must be 1 to 14')
    if errs:
        return None
    sc = [_clip(f'spine{k}', src, *_cut(s, e, src['duration'])) for k, (l, src, s, e, seg) in enumerate(spine)]
    for k, (l, src, s, e, seg) in enumerate(spine):
        sc[k]['words'] = seg
    # on-screen order: m0 m1 spine0 (first half of the rest) spine1 (rest, last one gets the closing card)
    rest = len(moments) - 2
    before = rest - rest // 2
    for i, m in enumerate(moments):
        m['key'] = f'm{i}'
    seq = moments[:2] + [sc[0]] + moments[2:2 + before] + [sc[1]] + moments[2 + before:]
    pred = sum(c['end'] - c['start'] for c in sc) + sum(c['end'] - c['start'] for c in moments) / MOMENT_SPEED
    if not 40 <= pred <= 58:
        errs.append(f'predicted duration {pred:.1f} s, must be 40 to 58 s (add or remove silent moments)')
        return None
    return {'format': 'tribute', 'name': sb.get('name') or cx.job['person']['name'],
            'spine': [{'clip': c['key'], 'text': l['quote'], 'words': c.pop('words')} for c, (l, *_r) in zip(sc, spine)],
            'moments': [{'clip': m['key']} for m in moments], 'closingLine': sb['closingLine'], 'clips': seq, 'predictedDuration': round(pred, 2)}


def _age_hours(date):
    try:
        d = dt.datetime.fromisoformat(date.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        try:
            d = email.utils.parsedate_to_datetime(date)
        except (TypeError, ValueError):
            return None
    return (_now() - (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc))).total_seconds() / 3600


def _v_topn(cx, sb):
    errs, job = cx.errs, cx.job
    ms = sb.get('moments') or []
    if not 6 <= len(ms) <= 8:   # spares stand in for moments the identity probe finds off camera
        errs.append(f'moments: propose 6 to 8 (some are usually off camera), got {len(ms)}')
        return None
    good, why = [], []
    for i, m in enumerate(ms):
        a = cx.find(m.get('source'), m.get('fromQuote', ''), f'moments[{i}].fromQuote')
        b = a and cx.find(m['source'], m.get('toQuote', ''), f'moments[{i}].toQuote', after=a[1])
        if not (a and b):
            why.append(cx.errs.pop())
            continue
        s, e = _cut(a[1], b[2], a[0]['duration'])
        if not TOPN_MIN_S <= e - s <= TOPN_MAX_S:
            why.append(f'moments[{i}]: {e - s:.1f} s, must be {TOPN_MIN_S} to {TOPN_MAX_S} s')
            continue
        ws_all = cx.words(m['source'])
        words = [w for w in ws_all if a[1] - 1e-6 <= w['s'] and w['e'] <= b[2] + 1e-6]
        good.append((a[0], max(0.0, s - TOPN_PRE), e, m.get('label') or '', words, b[2], _reply(ws_all, b[2])))
    if len(good) < 4:
        raise _Short(f'only {len(good)} of {len(ms)} moments found in the captions (topn needs 4): ' + '; '.join(why)[:600])
    if len({g[0]['id'] for g in good}) < 2:   # separate times: one video is usually one exchange cut into pieces
        errs.append('moments: all come from one video; a Top N is separate times, take them from at least 2 different videos')
    good, spare = good[:5], good[5:]   # spares stand in for moments the identity probe removes
    n = len(good)
    c = sb.get('closer') or {}
    heads = {_fold(h['title']): h for h in job['person'].get('headlines') or []}
    h = heads.get(_fold(c.get('headline', '')))
    if not h:
        errs.append(f'closer.headline: "{c.get("headline")}" is not one of person.headlines')
    elif (_age_hours(h.get('date')) or 0) > 72:
        errs.append(f'closer.headline: "{c["headline"]}" is older than 72 h')
    for k in ('line1', 'line2'):
        if not c.get(k):
            errs.append(f'closer.{k}: missing')
    # each clip runs on through the reply after the punchline, as far as the 58 s budget allows (shared evenly)
    fixed = sum(e - s for _, s, e, *_r in good) + n * TOPN_CARD + TOPN_CLOSER
    room = max(0.0, (58 - fixed) / n) if n else 0.0
    good = [_with_reply(g, room) for g in good]
    spare = [_with_reply(g, TOPN_REPLY) for g in spare]
    pred = sum(e - s for _, s, e, *_r in good) + n * TOPN_CARD + TOPN_CLOSER
    if not 35 <= pred <= 58:
        errs.append(f'predicted duration {pred:.1f} s, must be 35 to 58 s' + (': choose longer moments (a setup, the punchline and the reply)' if pred < 35 else ''))
    if errs:
        return None
    order = list(reversed(list(enumerate(good))))   # rank n first on screen, rank 1 (agent's best) last
    clips = [_clip(f't{j}', g[0], g[1], g[2]) for j, (_, g) in enumerate(order)]
    clips += [_clip(f's{j}', g[0], g[1], g[2]) for j, g in enumerate(spare)]
    return {'format': 'topn', 'title': re.sub(r'^\s*Top\s+\d+', f'Top {n}', sb.get('title') or '', flags=re.I), 'n': n,
            'moments': [{'clip': f't{j}', 'rank': r + 1, 'label': g[3], 'words': g[4], 'replyFrom': g[5]} for j, (r, g) in enumerate(order)],
            'spares': [{'clip': f's{j}', 'rank': n + j + 1, 'label': g[3], 'words': g[4], 'replyFrom': g[5]} for j, g in enumerate(spare)],
            'closer': c, 'clips': clips, 'predictedDuration': round(pred, 2)}


def _reply(words, after):
    """The words that follow a punchline until a pause of REPLY_GAP or TOPN_REPLY seconds: the other person's answer."""
    out, last = [], after
    for w in words:
        if w['s'] < after - 1e-6:
            continue
        if w['s'] - last > REPLY_GAP or w['e'] - after > TOPN_REPLY:
            break
        out.append(w); last = w['e']
    return out


def _with_reply(g, room):
    """A Top N moment extended through as much of its reply as `room` seconds allow."""
    src, s, e, label, words, q_end, reply = g
    keep = [w for w in reply if w['e'] - q_end <= room]
    end = min(max(e, keep[-1]['e'] + TAIL) if keep else e, src.get('duration') or 1e9)
    return src, s, end, label, words + keep, q_end, reply


def _check_list(errs, name, items, lo, hi):
    if not isinstance(items, list) or not lo <= len(items) <= hi:
        errs.append(f'{name}: need {lo} to {hi}, got {len(items) if isinstance(items, list) else items!r}')
        return []
    return items


def _v_edit(cx, sb):
    errs = cx.errs
    sid = sb.get('source')
    src = cx.source(sid, 'source')
    lines = _check_list(errs, 'lines', sb.get('lines'), 6, 12)
    spans, prev = [], -1
    for i, q in enumerate(lines):
        r = src and cx.find(sid, q, f'lines[{i}]')
        if not r:
            continue
        if r[1] < prev:
            errs.append(f'lines[{i}]: out of order, it comes before lines[{i - 1}] in the video')
        prev = r[1]
        spans.append((q, r))
    speech = sum(_cut(r[1], r[2])[1] - _cut(r[1], r[2])[0] for _, r in spans)
    if not errs and not 25 <= speech <= 38:
        errs.append(f'speech {speech:.1f} s, must be 25 to 38 s')
    drop = sb.get('dropLine')
    if not isinstance(drop, int) or not 0 <= drop < max(len(lines), 1):
        errs.append(f'dropLine: {drop!r} is not the index of one of the {len(lines)} lines')
    for i, s in enumerate(_check_list(errs, 'slams', sb.get('slams'), 2, 3)):
        if len(s.split()) > 5:
            errs.append(f'slams[{i}]: "{s}" has {len(s.split())} words, at most 5')
    for i, p in enumerate(_check_list(errs, 'popups', sb.get('popups'), 2, 3)):
        if len(p.get('text', '').split()) > 8 or not isinstance(p.get('line'), int) or not 0 <= p['line'] < len(lines):
            errs.append(f'popups[{i}]: text at most 8 words and line must be a line index')
    broll = _check_list(errs, 'broll', sb.get('broll'), 6, 12)
    for i, b in enumerate(broll):
        if not b.get('query') or not isinstance(b.get('line'), int) or not 0 <= b['line'] < len(lines):
            errs.append(f'broll[{i}]: needs a query and a line index')
    tail = _check_list(errs, 'tail', sb.get('tail'), 6, 10)
    if errs:
        return None
    # the renderer holds the speech for the stat slams after the drop line (2 beats each) and a beat before the tail
    pred = (speech + EDIT_SLAM * len(sb['slams']) + EDIT_HOLD) / (1 - EDIT_TAIL)
    if not 45 <= pred <= 58:
        errs.append(f'predicted duration {pred:.1f} s, must be 45 to 58 s (speech {speech:.1f} s, {len(sb["slams"])} slams after the drop and a {EDIT_TAIL:.0%} edit-only tail): '
                    + ('drop a line or shorten the speech' if pred > 58 else 'add a line'))
        return None
    cache = {}
    for q in [b['query'] for b in broll] + list(tail):
        cache.setdefault(q, _broll_candidates(q))
    empty = [q for q, c in cache.items() if not c]
    total = len(broll) + len(tail)
    have = sum(1 for q in [b['query'] for b in broll] + list(tail) if cache[q])
    if have < 0.7 * total:
        errs.append(f'b-roll: only {have} of {total} queries have results, no results for: ' + ', '.join(f'"{q}"' for q in empty))
        return None
    clips = [_clip(f'l{i}', src, *_cut(r[1], r[2], src['duration'])) for i, (_, r) in enumerate(spans)]
    return {'format': 'edit', 'source': src, 'lines': [{'clip': f'l{i}', 'text': q, 'words': r[3]} for i, (q, r) in enumerate(spans)],
            'dropLine': drop, 'slams': sb['slams'], 'popups': sb['popups'],
            'broll': [{'query': b['query'], 'line': b['line'], 'candidates': cache[b['query']]} for b in broll],
            'tail': [{'query': q, 'candidates': cache[q]} for q in tail], 'clips': clips, 'predictedDuration': round(pred, 2)}


def _overlap(quote, text):
    """Best share of the quote's words found in any same-length window of the text (1.0 for a verbatim quote)."""
    q, t = _fold(quote).split(), _fold(text).split()
    if not q:
        return 0.0
    qc, best = Counter(q), 0.0
    for i in range(max(1, len(t) - len(q) + 1)):
        best = max(best, sum((Counter(t[i:i + len(q)]) & qc).values()) / len(q))
        if best == 1:
            break
    return best


def _sentences(text):
    return re.split(r'(?<=[.!?])\s+', text)


def _v_casefile(cx, sb):
    errs, job = cx.errs, cx.job
    arts = job.get('articles') or []
    surname = _fold(job['person']['name']).split()[-1]
    if len({a['domain'] for a in arts}) < 2:
        raise _Missing('fewer than 2 outlets have article text')

    def article(outlet):
        fo = _fold(outlet)
        return next((a for a in arts if fo and (fo in _fold(a['outlet']) or _fold(a['outlet']) in fo or fo.replace(' ', '') in a['domain'].replace('.', ''))), None)

    script = _check_list(errs, 'script', sb.get('script'), 8, 14)
    spoken = [re.sub(r'\s+', ' ', re.sub(r'\[[^\]]*\]', ' ', s.get('text', ''))).strip() for s in script]
    alltext = ' '.join([sb.get('title') or ''] + spoken + [c.get('text', '') for c in sb.get('claims') or []])
    m = BLOCKED.search(alltext) or UNNAMED.search(alltext)
    if m:
        raise _Missing(f'blocked topic ("{m.group(0)}") in the script')
    for a in arts:
        for s in _sentences(a['text']):
            if surname in _fold(s).split() and BLOCKED.search(s):
                raise _Missing(f'blocked topic ("{BLOCKED.search(s).group(0)}") reported by {a["outlet"]}')
    for i, sp in enumerate(spoken):   # name the outlet once, naturally; "both outlets report" on line after line reads robotic
        if re.search(r'\b(both|the two|all) outlets\b|\boutlets (report|say)\b', sp, re.I):
            errs.append(f'script[{i}]: do not write "both outlets" or "outlets report": name the outlet ("the BBC reports") once where it matters, and state court verdicts plainly')
    words = sum(len(s.split()) for s in spoken)
    if words / WPS > 57:
        errs.append(f'script: {words} words is {words / WPS:.0f} s at {WPS} words/s, must be at most 57 s (about {int(57 * WPS)} words)')
    # the person (or their lawyers) must be the one denying: "Turner denies", "Turner's lawyers have denied", not "Trump denied this ... Turner"
    theirs = re.compile(rf'\b{re.escape(surname)}s?\b(?: \w+){{0,4}} {DENIAL.pattern}', re.I)
    den = [a for a in arts if any(theirs.search(_fold(s)) for s in _sentences(a['text']))]
    if den and not any(DENIAL.search(s) for s in spoken):
        errs.append(f'script: {", ".join(a["outlet"] for a in den)} report a denial or rejection by {job["person"]["name"]}, the script must say it')
    claims = _check_list(errs, 'claims', sb.get('claims'), 4, 8)
    out_claims = []
    for i, c in enumerate(claims):
        ok, sup = set(), []
        for j, s in enumerate(c.get('support') or []):
            a = article(s.get('outlet', ''))
            if not a:
                errs.append(f'claims[{i}].support[{j}]: outlet "{s.get("outlet")}" has no article')
            elif _overlap(s.get('quote', ''), a['text']) < 0.8:
                errs.append(f'claims[{i}].support[{j}]: quote not found in the {s["outlet"]} article: "{s.get("quote", "")[:80]}"')
            else:
                ok.add(a['domain']); sup.append({'outlet': s['outlet'], 'url': a['url'], 'quote': s['quote']})
        if len(ok) < 2:
            errs.append(f'claims[{i}]: needs support from 2 different outlets, found {len(ok)}')
        out_claims.append({'text': c.get('text'), 'support': sup})
    if len(sb.get('timeline') or []) not in (2, 3, 4):
        errs.append('timeline: need 2 to 4 points')
    plan_script, clips, shots, photos, empty = [], [], 0, 0, []
    for i, (s, sp) in enumerate(zip(script, spoken)):
        v = s.get('visual') or {}
        k, w = v.get('kind'), f'script[{i}]'
        if k == 'screenshot':
            a = article(v.get('outlet', ''))
            hl = v.get('highlight', '')
            shots += 1
            if i and script[i - 1].get('visual', {}).get('kind') == 'screenshot':
                errs.append(f'{w}: two screenshots in a row')
            if not a:
                errs.append(f'{w}: outlet "{v.get("outlet")}" has no article')
            elif not 4 <= len(hl.split()) <= 12 or _fold(hl) not in _fold(a['text']):
                errs.append(f'{w}: highlight "{hl}" must be 4 to 12 words copied exactly from the {v["outlet"]} article')
            else:
                v = {'kind': 'screenshot', 'outlet': v['outlet'], 'url': a['url'], 'highlight': hl}
        elif k == 'photo':
            photos += 1
            v = {'kind': 'photo', 'query': v.get('query', '')}
        elif k == 'clip':
            src = cx.source(v.get('source'), w)
            st, en = v.get('start'), v.get('end')
            if src and all(isinstance(x, (int, float)) for x in (st, en)) and 0 <= st < en <= (src['duration'] or en):
                if not 2 <= en - st <= 4:
                    errs.append(f'{w}: archive clip is {en - st:.1f} s, must be 2 to 4 s')
                else:
                    clips.append(_clip(f'a{len(clips)}', src, st, en))
                    v = {'kind': 'clip', 'clip': clips[-1]['key']}
            elif src:
                errs.append(f'{w}: bad archive clip window {st}-{en}')
        elif k == 'timeline':
            v = {'kind': 'timeline', 'label': v.get('label', '')}
        elif k == 'quote':
            a = article(v.get('outlet', ''))
            if not a or _overlap(v.get('text', ''), a['text']) < 0.8:
                errs.append(f'{w}: quote "{v.get("text")}" not found in the {v.get("outlet")} article')
            v = {'kind': 'quote', 'text': v.get('text'), 'outlet': v.get('outlet')}
        else:
            errs.append(f'{w}: unknown visual kind {k!r}')
        plan_script.append({'text': s.get('text', ''), 'spoken': sp, 'visual': v})
    if shots > 5:
        errs.append(f'script: {shots} screenshots, at most 5')
    if len(clips) > 2:
        errs.append(f'script: {len(clips)} archive clips, at most 2')
    if errs:
        return None
    for s in plan_script:
        if s['visual']['kind'] == 'photo':
            s['visual']['candidates'] = _safe(_commons_images, s['visual']['query'])
            if not s['visual']['candidates']:
                empty.append(s['visual']['query'])
    if photos - len(empty) < 2:
        errs.append('photo: need at least 2 photo queries with Commons results' + (', no results for: ' + ', '.join(f'"{q}"' for q in empty) if empty else ''))
        return None
    return {'format': 'casefile', 'title': sb.get('title'), 'script': plan_script, 'claims': out_claims, 'timeline': sb['timeline'],
            'words': words, 'clips': clips, 'predictedDuration': round(words / WPS, 2)}


VERIFIERS = {'tribute': _v_tribute, 'topn': _v_topn, 'edit': _v_edit, 'casefile': _v_casefile}


def verify(job, cfg, run, state):
    fmt = job.get('format')
    if fmt not in VERIFIERS:
        return _invalid([f'format: unknown format {fmt!r}'])
    sb = job.get('storyboard') or {}
    if sb.get('error'):   # the agent says the pool cannot make this format: another person, not another try
        return _missing(job, 'verify', f"the storyboard agent found no usable material: {sb.get('reason') or sb['error']}")
    cx = _Ctx(job, run)
    try:
        body = VERIFIERS[fmt](cx, sb)
    except _Missing as e:
        return _missing(job, 'verify', str(e))
    except _Short as e:
        tries = job.get('verifyTries', 0) + 1
        if tries > VERIFY_TRIES:
            return _missing(job, 'verify', str(e))
        return 'invalid', {'agentErrors': [str(e) + ' Fix these moments or choose others from the transcripts.'], 'verifyTries': tries}, str(e)
    if body is None:
        errs, tries = cx.errs or ['storyboard could not be verified'], job.get('storyTries', 0) + 1
        if tries >= STORY_TRIES:   # this person's material does not make a story: the next person (live 2026-11-11: the run ended instead)
            return _missing(job, 'verify', f'no valid storyboard after {tries} tries: {errs[0]}')
        return 'invalid', {'agentErrors': errs, 'storyTries': tries}, f'{len(errs)} errors: ' + '; '.join(errs)[:200]
    clips = body.pop('clips')
    plan = {'format': fmt, 'person': _plan_person(job['person']), **{k: v for k, v in body.items() if k != 'format'}, 'clips': clips}
    if fmt in ('edit', 'casefile'):   # YouTube queries for real footage of the person's work (the assets stage fetches it)
        plan['footage'] = [q.strip() for q in sb.get('footage') or [] if isinstance(q, str) and q.strip()][:4]
    (Path(run) / 'broll.txt').write_text(_broll_text(plan))   # the b-roll agent block needs its fileKeys to exist for every format
    return 'next', {'plan': plan, 'story': _story(job, clips), 'download': 'yes' if clips else 'no', 'predictedDuration': plan['predictedDuration'], 'agentErrors': [],
                    'brollText': {'file': 'broll.txt'}}, f'{fmt}: {len(clips)} clips, predicted {plan["predictedDuration"]} s'


def brollpick(job, cfg, run, state):
    """Keep only the b-roll candidates the agent picked (edit only); too few queries left with a clip sends the storyboard back."""
    plan = job.get('plan') or {}
    if plan.get('format') != 'edit' or not job.get('brollPicks'):
        return 'next', {}, 'b-roll: no picks, unchanged'
    picks = (job['brollPicks'] or {}).get('picks')
    picks = picks if isinstance(picks, dict) else {}

    def keep(q, cands):
        idx = [i for i in dict.fromkeys(picks.get(q) if isinstance(picks.get(q), list) else []) if type(i) is int and 0 <= i < len(cands)]
        return [cands[i] for i in idx]
    new = {**plan, 'broll': [{**b, 'candidates': keep(b['query'], b['candidates'])} for b in plan.get('broll', [])],
           'tail': [{**t, 'candidates': keep(t['query'], t['candidates'])} for t in plan.get('tail', [])]}
    items = new['broll'] + new['tail']
    empty = [x['query'] for x in items if not x['candidates']]
    if len(items) - len(empty) < 0.7 * len(items):
        return 'invalid', {'agentErrors': [f'b-roll: only {len(items) - len(empty)} of {len(items)} queries have a clip that fits, none fits: ' + ', '.join(f'"{q}"' for q in empty)
                                           + '. Write queries that find footage which literally shows the line.']}, f'{len(empty)} of {len(items)} queries without a fitting clip'
    return 'next', {'plan': new}, f'b-roll: {len(items) - len(empty)} of {len(items)} queries kept clips'


# ---- music

SETS = {'edit': 'edit', 'topn': 'edit', 'tribute': 'sad', 'casefile': 'documentary'}
DROP_DB = 6.0       # a drop scoring less than this (dB step of the bass) does not count as a drop
USED_DAYS, MAX_TRIES = 3, 4


def _jread(p, default):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return default


def _jwrite(p, data):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(data))


def _drop_ok(a):
    return a.get('drop') is not None and ((a.get('drops') or [{}])[0].get('score') or 0) >= DROP_DB


def _swell(a):
    """Second of the loudest point if it is late (>= 8 s) and clearly louder than what came before, else None."""
    x = a.get('intensity') or []
    if not x:
        return None
    t = max(range(len(x)), key=x.__getitem__)
    return float(t) if t >= 8 and x[t] >= 1.5 * (sum(x[:t]) / t) else None


# a search result whose own title says it is instrumental: the vocal hint reads strings and pads as voice (real documentary
# beds scored 0.47-0.68, live 2026-11-07), so for these the title is trusted on vocals
LABELLED = re.compile(r'instrumental|background music|music background|royalty[ -]free|no copyright|documentary music|soundtrack|score', re.I)


VOCAL_SHARE_MAX = 0.15   # music.VOCAL_SHARE_MAX: share of YAMNet frames with a vocal class (vocal songs 0.32+, instrumentals 0.03-)


def _passes(set_, a, labelled=False):
    bpm = a.get('bpm', 999)
    if 'vocal_share' in a:   # measured: reliable, so an 'instrumental' title does not override it
        free = a['vocal_share'] < VOCAL_SHARE_MAX
    else:                    # an analysis from before vocal_share: the crude hint, with the title trusted when labelled
        free = labelled or a.get('vocal_hint', 1) < (0.1 if set_ == 'documentary' else 0.12)
    if not free:
        return False
    if labelled and set_ == 'documentary':
        return True  # a labelled narration bed: builds are fine under a voice
    if set_ == 'edit':
        return _drop_ok(a)
    if set_ == 'sad':
        return _swell(a) is not None   # no bpm cap: slow piano reads at double time, and sad comes only from instrumental searches
    return bpm <= 100 and not _drop_ok(a)


def _fetch_track(source_id, tracks_dir):
    from . import music as kit
    return kit.fetch(source_id, str(tracks_dir))


def _analyse(path, models_dir):
    from . import music as kit
    return kit.analyse(path, str(models_dir))


def _rejected(sd, set_):
    r = _jread(Path(sd) / 'rejected.json', {})
    return set(r) if isinstance(r, list) else {k for k, v in r.items() if set_ in v}


def _recent(state):
    cut = _today() - dt.timedelta(days=USED_DAYS)
    return {u['id'] for u in _jread(Path(state) / 'trending-used-sounds.json', []) if dt.date.fromisoformat(u['date']) > cut}


def _ranked(sd, set_):
    """[(id, title)] from the uses history, fastest growing first; limited to the set's newest momentum report when there is one."""
    from . import soundmomentum as sk
    reports = sorted(Path(sd).glob(f'momentum-{set_}-*.json'))
    if not reports:
        return []  # the history holds vocal songs of every kind: only a set's own report is trusted, else the instrumental search
    only = {g['source'] for g in _jread(reports[-1], {}).get('sounds', [])}
    rows = []
    for src, h in sk.load_history(str(sd)).items():
        if src in only:
            g = sk.growth(h['uses'], _today())
            rows.append(((-(g[0] if g else -1e18), -h['uses'][max(h['uses'])]), src, h.get('title') or src))
    return _edit_order(set_, [(s, t) for _, s, t in sorted(rows)])


# popular instrumentals of each kind, when no tracked trending sound passes the set's test
# edit sounds: heavy-bass instrumentals. Titles in these styles come first; live/acoustic/cover/lyrics/karaoke are never an edit bed
EDIT_STYLE = re.compile(r'phonk|funk|montagem|slowed|sped up|bass|drift|instrumental|remix|type beat', re.I)
NOT_EDIT = re.compile(r'\b(live|acoustic|cover|lyrics?|karaoke)\b', re.I)


def _edit_order(set_, rows):
    if set_ != 'edit': return rows
    return sorted((r for r in rows if not NOT_EDIT.search(r[1])), key=lambda r: not EDIT_STYLE.search(r[1]))  # stable: keeps the rank within each group


SEARCH = {'documentary': ['dark documentary background music instrumental', 'true crime documentary music instrumental', 'suspense investigation music instrumental'],
          'sad': ['sad emotional piano instrumental', 'emotional orchestral tribute music instrumental'],
          'edit': ['phonk edit audio bass boosted', 'brazilian phonk funk instrumental slowed', 'aggressive phonk drift instrumental', 'heavy bass edit audio no vocals']}


def _search(q):
    return ytsrc.search(q, 15)


def _searched(set_):
    """[(id, title)] of instrumental search results for the set, most viewed first, 90 s to 10 min long."""
    seen, rows = set(), []
    for q in SEARCH[set_]:
        try: found = _search(q)
        except Exception: continue
        for it in found:
            if it['id'] not in seen and 90 <= (it.get('duration') or 0) <= 600:
                seen.add(it['id']); rows.append((-(it.get('view_count') or 0), it['id'], it.get('title') or it['id']))
    return _edit_order(set_, [(i, t) for _, i, t in sorted(rows)])


def _target(plan):
    """Second of the video where the music's drop (edit, topn) or swell (tribute) must land; None when the format has no hit."""
    cl = plan.get('clips') or []
    speed = lambda c: MOMENT_SPEED if plan.get('format') == 'tribute' and c['key'].startswith('m') else 1
    n = {'edit': plan.get('dropLine'), 'topn': len(cl) - 1, 'tribute': len(cl) - 1}.get(plan.get('format'))
    return None if n is None else sum((c['end'] - c['start']) / speed(c) for c in cl[:n])


def _candidates(sd, set_, skip, tried, labelled):
    """Tracked trending sounds of the set first, then (only if none passed) instrumental search results; MAX_TRIES of each."""
    # sad: instrumental search only, the sad/rip tags trend pop songs (live 2026-11-10: "SugarCrash Slowed" under a tribute)
    for searched, source in ((False, lambda: [] if set_ == 'sad' else _ranked(sd, set_)), (True, lambda: _searched(set_))):
        for c in [c for c in source() if c[0] not in skip and c[0] not in tried][:MAX_TRIES]:
            if searched:
                labelled.add(c[0])
            yield c


def music(job, cfg, run, state):
    plan, sd = job.get('plan') or {}, Path(state) / 'sounds'
    set_ = SETS[job['format']]
    skip = _recent(state) | _rejected(sd, set_)
    tried, labelled = [], set()   # ids that came from the instrumental search
    for sid, title in _candidates(sd, set_, skip, tried, labelled):
        tried.append(sid)
        f = sd / 'tracks' / f'{sid}.json'
        a = _jread(f, None)
        if a is None or 'vocal_share' not in a:   # an analysis from before vocal_share is measured again
            try:
                a = _analyse(_fetch_track(sid, sd / 'tracks'), sd.parent / 'models')
            except Exception as e:  # download or analysis failed: try the next sound, do not blame the sound
                continue
            _jwrite(f, a)
        if _passes(set_, a, labelled=sid in labelled and bool(LABELLED.search(title))):
            if not (sd / 'tracks' / f'{sid}.m4a').exists():   # the cloud seed ships analyses without the audio
                try:
                    _fetch_track(sid, sd / 'tracks')
                except Exception:
                    continue
            pick = (sid, title, a)
            break
        rej = _jread(sd / 'rejected.json', {})
        rej = {k: ['edit', 'sad', 'documentary'] for k in rej} if isinstance(rej, list) else rej
        _jwrite(sd / 'rejected.json', {**rej, sid: sorted({*rej.get(sid, []), set_})})
    else:
        pick = None if set_ == 'sad' else next(((f.stem, f.stem, a) for f in sorted((sd / 'tracks').glob('*.json'))
                     if f.stem not in skip | set(tried) and f.with_suffix('.m4a').exists() and 'vocal_share' in (a := _jread(f, {})) and _passes(set_, a)), None)
    if not pick:
        return _missing(job, 'music', f'no {set_} sound passed (tried {", ".join(tried) or "none"})')
    sid, title, a = pick
    tgt = _target(plan)
    from . import music as kit
    off = 0.0 if tgt is None else kit.place({**a, 'drop': _swell(a) if set_ == 'sad' else a['drop']}, tgt, plan.get('predictedDuration') or 50)['music_offset']
    return 'next', {'track': {'id': sid, 'title': title, 'file': str(sd / 'tracks' / f'{sid}.m4a'), 'analysis': a},
                    'plan': {**plan, 'musicOffset': off}, 'agentErrors': []}, f'{set_}: {sid} offset {off}'


# ---- probe

PROBE_FRAMES, PROBE_SECONDS = 3, 1.0
MATCH_PHOTO = 0.363   # faces.MATCH; a photo face below it is someone else
PERSON_FACE = 0.10    # a person photo's face is at least this share of the image width (a 2008 portrait measured 0.118)
POOL_PHOTOS = 6       # distinct photos a case file can cut between, so fillers do not repeat one picture


def _windows(c):
    """Three 1 s probe windows at the start, middle and end of a clip: a shot can change inside a clip."""
    a, b = c['start'], c['end']
    return [(round(t, 3), round(t + PROBE_SECONDS, 3)) for t in (a, max(a, (a + b - PROBE_SECONDS) / 2), max(a, b - PROBE_SECONDS))]


def _probe_download(sid, url, windows, out_dir):
    return ytsrc.probe_frames(sid, url, windows, str(out_dir))


def _frames(path, n=PROBE_FRAMES):
    import cv2
    cap, out = cv2.VideoCapture(path), []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    for k in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((k + 0.5) / n * max(total - 1, 0)))
        ok, f = cap.read()
        if ok:
            out.append(f)
    cap.release()
    return out


def _frame_embeds(img, models_dir):
    """Every face a viewer would notice in a probe frame: the person is often the smaller face behind someone else."""
    from . import faces
    return [e for e, _ in faces.embed_all(img, str(models_dir))]


def _embed(img, models_dir):
    from . import faces
    return faces.embed(img, str(models_dir))


def _reference_image(person):
    """Commons photo of the person (640 px) as a BGR image, or None."""
    f = person.get('image')
    if not f:
        return None
    try:
        import commons, cv2
        url = f if f.startswith('http') else 'https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(f.replace(' ', '_')) + '?width=640'
        return cv2.imdecode(np.frombuffer(commons.fetch(url, 60), np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None


def _cluster_reference(embs):
    """Mean of the biggest group of mutually matching faces, or None without faces."""
    from . import faces
    if not embs:
        return None
    best = max(embs, key=lambda e: sum(faces.match(e, o) >= faces.MATCH for o in embs))
    return np.mean([e for e in embs if faces.match(e, best) >= faces.MATCH], axis=0)


def _probe_targets(plan):
    cl = plan['clips']
    if plan['format'] == 'edit':
        return cl   # every line: 3 sampled lines can all be face-free b-roll inside the source (live 2026-11-09)
    return [c for c in cl if c.get('person')]


def probe(job, cfg, run, state):
    from . import faces
    plan, run = copy.deepcopy(job['plan']), Path(run)
    name, fmt = (job.get('person') or plan.get('person') or {}).get('name', 'the person'), plan['format']
    targets = _probe_targets(plan)
    by_src = {}
    for c in targets:
        for w in _windows(c):
            by_src.setdefault(c['source']['id'], []).append((c, w))
    windows, reason = {}, {}   # key -> embeddings per probe window
    for sid, items in by_src.items():
        try:
            paths = _probe_download(sid, items[0][0]['source']['url'], [w for _, w in items], run / 'probes')
        except Exception as e:
            paths = [None] * len(items)
        for (c, _), p in zip(items, paths):
            if p is None:
                reason[c['key']] = 'could not be downloaded'
            windows.setdefault(c['key'], []).append([] if p is None else [e for f in _frames(p) for e in _frame_embeds(f, Path(state) / 'models')])
    embs = {k: [e for w in ws for e in w] for k, ws in windows.items()}
    ref_img = _reference_image(job.get('person') or {})
    ref = _embed(ref_img, Path(state) / 'models') if ref_img is not None else None
    if ref is None:
        ref = _cluster_reference([e for v in embs.values() for e in v])
    # second pass: the frames the photo finds clearly are averaged into a footage reference (same camera, light and age as the
    # clips), which then judges every window; the photo alone missed most of a TV chef (live 2026-11-08: 19 of 96 faces vs 32)
    seen = [e / np.linalg.norm(e) for v in embs.values() for e in v if ref is not None and faces.match(e, ref) >= faces.MATCH]
    if seen:
        m = np.mean(seen, axis=0); ref = m / np.linalg.norm(m)
    # silent shots of the person (tribute, casefile) need them in every window: a shot can change to someone else inside the
    # clip; an edit's speaker 2 of 3; a Top N moment 1 of 3, as a roast or a dodge stays on whoever it is aimed at
    need = {'tribute': 3, 'casefile': 3, 'edit': 2}.get(fmt, 1)   # of the 3 windows; topn: a roast stays on its target
    seen_in = lambda k: sum(any(faces.match(e, ref) >= faces.MATCH for e in w) for w in windows[k])
    failed = [c['key'] for c in targets if ref is None or seen_in(c['key']) < need]
    notes = [f'{k} removed by the identity probe: ' + (reason.get(k) or f'no sampled frame matched {name}') for k in failed]
    bad = lambda *why: _invalid(notes + list(why))
    keep = [c for c in plan['clips'] if c['key'] not in failed]
    if fmt == 'edit':
        # his talk when he is on camera in at least 2 lines; a line showing someone else keeps its audio under a cutaway
        # picture (cover), and a line with no face found (a wide shot) is no evidence either way
        failed = [k for k in failed if any(windows[k])]
        if len(targets) - len(failed) - sum(not any(windows[c['key']]) for c in targets) < 2:
            return _invalid([f'{name} is on camera in fewer than 2 of the {len(targets)} lines: choose another source where {name} speaks on camera'])
        keep = [dict(c, cover=True) if c['key'] in failed else c for c in plan['clips']]
        notes = []
    elif fmt == 'tribute':
        if any(c['clip'] in failed for c in plan['spine']):
            return bad('a spine line failed the identity check: choose other lines of the person on camera')
        plan['moments'] = [m for m in plan['moments'] if m['clip'] not in failed]
        if len(plan['moments']) < 4:
            return bad(f'tribute needs at least 4 silent moments of {name}, only {len(plan["moments"])} left: choose others')
        d = {c['key']: c['end'] - c['start'] for c in keep}
        plan['predictedDuration'] = round(sum(d[s['clip']] for s in plan['spine']) + sum(d[m['clip']] for m in plan['moments']) / MOMENT_SPEED, 2)
    elif fmt == 'topn':
        # judged on the whole video: the best 5 in the agent's order, as long as at least half show the person; a moment where
        # the camera stays on whoever the roast is aimed at is fine, and the weakest off-camera ones make way for spares that
        # show them (live 2026-11-08: Hell's Kitchen holds on the contestant while Ramsay roasts them)
        cand = sorted(plan['moments'] + plan.pop('spares', []), key=lambda m: m['rank'])
        ms, rest = cand[:5], cand[5:]
        shown = lambda m: m['clip'] not in failed
        while sum(map(shown, ms)) * 2 < len(ms) and any(map(shown, rest)):
            ms.remove([m for m in ms if not shown(m)][-1])
            ms.append(rest.pop(next(i for i, m in enumerate(rest) if shown(m))))
            ms.sort(key=lambda m: m['rank'])
        if len(ms) < 4 or sum(map(shown, ms)) * 2 < len(ms):
            return bad(f'topn needs at least 4 moments and {name} on camera in at least half of them: only {sum(map(shown, ms))} of {len(ms)} show {name}; choose others')
        notes = [x for x in notes if not any(x.startswith(m['clip'] + ' removed') for m in ms)]   # kept off-camera moments are not errors
        n, chosen = len(ms), {m['clip'] for m in ms}
        keep = [c for c in plan['clips'] if c['key'] in chosen]
        plan['moments'] = [dict(m, rank=n - i) for i, m in enumerate(reversed(ms))]   # rank n first on screen, the best last
        plan.update(n=n, title=re.sub(r'^\s*Top\s+\d+', f'Top {n}', plan.get('title', ''), flags=re.I))
        plan['predictedDuration'] = round(sum(c['end'] - c['start'] for c in keep) + n * TOPN_CARD + TOPN_CLOSER, 2)
    else:
        for s in plan.get('script', []):
            if s['visual'].get('kind') == 'clip' and s['visual']['clip'] in failed:
                s['visual'] = {'kind': 'photo', 'query': name, 'candidates': []}   # assets searches Commons for it
    plan['clips'] = keep
    out = {'plan': plan, 'story': _story(job, keep), 'download': 'yes' if keep else 'no', 'agentErrors': notes}   # media-fetch refuses no clips
    # the gate checks the render against the same footage reference (the photo scored only 0.32-0.38 against a real render)
    if ref is not None:
        np.save(run / 'identity.npy', ref)
        out['identity'] = {'file': 'identity.npy'}
    return 'next', out, f'{len(targets)} probed, {len(failed)} removed'


# ---- assets

def _download(url, dest):
    import commons
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_bytes(commons.fetch(url, 120))


def _screenshot(url, dest, highlight=None):
    from . import screenshot
    return screenshot.article(url, dest, highlight)


def _ext(c):
    if c.get('kind') == 'video':
        return '.mp4'
    e = os.path.splitext(urllib.parse.urlparse(c['url']).path)[1].lower()
    return e if e in ('.jpg', '.jpeg', '.png', '.webp') else '.jpg'


_STOP = {'the', 'and', 'for', 'with', 'from', 'photo', 'image', 'picture', 'outside', 'inside', 'near', 'building'}


def _relevant(c, query):
    """The candidate's Commons file name (or its title) carries at least 60 % of the query's key words: Commons search matches
    loosely. A candidate with neither is kept."""
    page = urllib.parse.unquote(c.get('page') or '')
    label = page.split('File:', 1)[1] if 'File:' in page else c.get('title') or ''
    words = [w for w in re.findall(r'[a-z0-9]+', query.lower()) if len(w) >= 3 and w not in _STOP]
    name = re.findall(r'[a-z0-9]+', label.lower())
    return not words or not label or sum(w in name for w in words) >= max(1, -(-len(words) * 3 // 5))


def _photo_faces(path, ref, models):
    """(match score against the person, face width share) of every face a viewer would notice (score 0.0 without a reference)."""
    import cv2
    from . import faces
    return [(faces.match(e, ref) if ref is not None else 0.0, w) for e, w in faces.embed_all(cv2.imread(str(path)), str(models))]


def _fetch_first(base, stem, cands, ok=lambda path: True):
    """Download the first candidate that works and passes ok(path) -> {file, kind, credit, licence, page} (file relative to
    the run folder), or None."""
    for c in cands:
        rel = f'{stem}{_ext(c)}'
        try:
            _download(c['url'], base / rel)
        except Exception:
            continue
        if not ok(base / rel):
            continue
        return {'file': f'assets/{rel}', 'kind': c['kind'], 'credit': c.get('credit', ''), 'licence': c.get('licence', ''), 'page': c.get('page')}
    return None


ROWS = {'edit': 'lines', 'topn': 'moments', 'tribute': 'spine'}   # the plan lists whose rows hold clip words
PERSON_PHOTOS = 4


def _retimed(plan, clips, run):
    """plan with every row's words re-timed on its downloaded clip (job.clips[i] is plan.clips[i]); one whisper run at a time."""
    plan = copy.deepcopy(plan)
    by_key = {c['key']: clips[i] for i, c in enumerate(plan.get('clips') or []) if i < len(clips)}
    cut = {c['key']: c for c in plan.get('clips') or []}
    for row in plan.get(ROWS[plan['format']]) or []:
        f = by_key.get(row.get('clip'))
        if f and row.get('words') and not all(w.get('timed') for w in row['words']):   # timed: mediaplan took YouTube's per-word times
            row['words'] = ws = align.retime(row['words'], str(Path(run) / f['file']), f.get('offset') or 0)
            lo, hi = f.get('offset') or 0, (f.get('offset') or 0) + (f.get('duration') or 1e9)
            # the renderer cuts at the clip's start/end: put them on the real words, inside the downloaded section
            cut[row['clip']]['start'], cut[row['clip']]['end'] = round(max(lo, ws[0]['s'] - LEAD), 3), round(min(hi, ws[-1]['e'] + TAIL), 3)
    return plan


def _person_photos(job, run, state, base):
    """2-4 Commons photos of the person that show their face and nobody else's ([] when none pass)."""
    name = (job.get('person') or {}).get('name')
    idf = (job.get('identity') or {}).get('file')
    ref = np.load(Path(run) / idf) if idf and (Path(run) / idf).is_file() else None
    if not name or ref is None:
        return []

    def theirs(path):
        fs = _photo_faces(path, ref, Path(state) / 'models')
        return bool(fs) and all(m >= MATCH_PHOTO for m, _ in fs) and any(w >= PERSON_FACE for _, w in fs)
    out = []
    for c in [c for c in _safe(_commons_images, name, 30) if _relevant(c, name)] + [None] + _safe(_bing_images, name):
        if c is None:   # Commons exhausted: Bing only tops up a thin set
            if len(out) >= 3:
                break
            continue
        got = _fetch_first(base, f'person/{len(out)}', [c], theirs)
        if got:
            out.append(got)
        if len(out) == PERSON_PHOTOS:
            break
    return out


def _bing_images(q):
    """Bing image results for q, large first: news and agency photos, NOT freely licensed (owner 2026-11-12: accepted as a
    fallback for more photos of the person). Credited to the site the image is on."""
    import html
    page = net.get_text('https://www.bing.com/images/search?form=HDRSC2&qft=+filterui:imagesize-large&q=' + urllib.parse.quote(q))
    out = []
    for m in re.findall(r'\bm="(\{[^"]*\})"', page):
        try: d = json.loads(html.unescape(m))
        except ValueError: continue
        if d.get('murl', '').startswith('http'):
            out.append({'provider': 'bing', 'url': d['murl'], 'kind': 'image', 'credit': urllib.parse.urlparse(d.get('purl') or d['murl']).netloc.removeprefix('www.'),
                        'licence': '', 'title': d.get('t', ''), 'page': d.get('purl') or d['murl']})
    return out


FOOTAGE_MAX, FOOTAGE_PER_VIDEO, FOOTAGE_S, FOOTAGE_BUDGET = 6, 2, 3.0, 240   # shots, shots a video, seconds a shot, seconds in all


def _footage(job, run, state, base, strict=False):
    """Shots of the person from YouTube footage of their work (plan.footage queries: film scenes, performances, speeches), 9:16
    around their face -> [{file, kind, credit, page}]. Per query the first video with the surname in its title or channel that
    gives a shot (2 tried at most); four FOOTAGE_S windows from each, kept when _shot_ok;
    strict (case file): nobody else's face either. NOT freely licensed (owner 2026-11-13: accepted, a few shots a video)."""
    idf = (job.get('identity') or {}).get('file')
    ref = np.load(Path(run) / idf) if idf and (Path(run) / idf).is_file() else None
    queries, models = (job['plan'].get('footage') or [])[:4], Path(state) / 'models'
    if not queries or ref is None:
        return []
    surname = _fold((job.get('person') or {}).get('name') or '').split()[-1:]
    out, seen, t0 = [], set(), time.time()
    for q in queries:
        tried = 0   # a video that gives no shot hands over to the next result, 2 videos a query at most
        for e in [e for e in _safe(ytsrc.search, q, 8) if 30 <= (e.get('duration') or 0) <= 3 * 3600   # full specials and films count
                  and e.get('live_status') not in ('is_live', 'is_upcoming')
                  and surname and surname[0] in _fold(f"{e.get('title', '')} {e.get('channel', '')}").split()]:   # someone else's video otherwise
            if tried == 2:
                break
            if e['id'] in seen:
                continue
            seen.add(e['id'])
            tried += 1
            url, d = f"https://www.youtube.com/watch?v={e['id']}", e['duration']
            try:
                files = ytsrc.probe_frames(e['id'], url, [(d * f, d * f + FOOTAGE_S) for f in (0.2, 0.4, 0.6, 0.8)], str(base / 'footage' / 'raw'), height=720)
            except Exception:
                continue
            got = 0
            for f in files:
                if not f or got == FOOTAGE_PER_VIDEO or len(out) == FOOTAGE_MAX or not _shot_ok(f, ref, models, strict):
                    continue
                rel = f'footage/{len(out)}.mp4'
                try:
                    _vertical(f, base / rel, ref, models)
                except Exception:
                    continue
                out.append({'file': f'assets/{rel}', 'kind': 'video', 'credit': f"Footage: {url} ({e.get('channel') or 'YouTube'})", 'page': url})
                got += 1
            if got:
                break
        if len(out) == FOOTAGE_MAX or time.time() - t0 > FOOTAGE_BUDGET:
            break
    return out


def _shot_ok(path, ref, models, strict=False):
    """The person's face, big enough to read, in a frame near each end of the shot (a scene cut inside it fails); strict: no other face."""
    with tempfile.TemporaryDirectory() as d:
        for k, t in enumerate((0.6, FOOTAGE_S - 0.6)):
            png = Path(d) / f'{k}.png'
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(t), '-i', str(path), '-frames:v', '1', str(png)], capture_output=True)
            fs = _photo_faces(png, ref, models) if png.exists() else []
            if not any(m >= MATCH_PHOTO and w >= PERSON_FACE for m, w in fs) or (strict and any(m < MATCH_PHOTO for m, _ in fs)):
                return False
    return True


def _vertical(src, dst, ref, models):
    from . import facecrop
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    facecrop.render(str(src), str(dst), face_y=0.40, ref=ref, models=str(models))


from .formats.casefile import shot_key


def assets(job, cfg, run, state):
    plan, base = job['plan'], Path(run) / 'assets'
    if plan['format'] in ROWS:
        plan = _retimed(plan, job.get('clips') or [], run)
    if plan['format'] == 'edit':
        wanted = [('broll', i, b) for i, b in enumerate(plan['broll'])] + [('tail', i, t) for i, t in enumerate(plan['tail'])]
        out = {'broll': [], 'tail': []}
        for kind, i, b in wanted:
            got = _fetch_first(base, f'{kind}/{i}', b.get('candidates') or [])
            if got:
                out[kind].append(({'line': b['line']} if kind == 'broll' else {}) | got)
        have = len(out['broll']) + len(out['tail'])
        if have < 0.7 * len(wanted):
            return _missing(job, 'assets', f'only {have} of {len(wanted)} b-roll shots could be downloaded')
        out['person'] = _person_photos(job, run, state, base)
        out['footage'] = _footage(job, run, state, base)
        return 'next', {'assets': out, 'plan': plan, 'agentErrors': []}, f'{have} of {len(wanted)} b-roll shots, {len(out["person"])} photos and {len(out["footage"])} footage shots of the person'
    if plan['format'] != 'casefile':
        return 'next', {'assets': {}, 'agentErrors': [], **({'plan': plan} if plan['format'] in ROWS else {})}, 'no assets for this format'
    visuals = [s['visual'] for s in plan['script']]
    keys = list(dict.fromkeys(shot_key(v) for v in visuals if v['kind'] == 'screenshot'))   # one per highlight
    by_key = {shot_key(v): v for v in visuals if v['kind'] == 'screenshot'}
    need, shots = min(2, len(keys)), {}
    for k in keys:
        if sum(1 for f in shots.values() if not f) > len(keys) - need:
            break   # the 2 needed can no longer be reached: the rest would only cost time (274 s in the cloud, live 2026-11-10)
        v = by_key[k]
        png = _screenshot(v['url'], base / 'shots' / f'{len(shots)}.png', v.get('highlight'))
        shots[k] = f'assets/shots/{len(shots)}.png' if png else None
    done = {u: f for u, f in shots.items() if f}
    if len(done) < need:
        return _missing(job, 'assets', f'only {len(done)} of {len(keys)} article screenshots could be taken ({need} needed)')
    # every face a viewer would notice must be the person: an unrelated face under a line about a case can read as naming
    # someone (complainants in UK sexual offence cases have lifelong anonymity); without a reference only faceless photos pass
    idf = (job.get('identity') or {}).get('file')
    ref = np.load(Path(run) / idf) if idf and (Path(run) / idf).is_file() else None
    surname = ((job.get('person') or {}).get('name') or '').split()[-1:] or ['']

    def alone(path, query=''):
        fs = _photo_faces(path, ref, Path(state) / 'models')
        if any(m < MATCH_PHOTO for m, _ in fs):
            return False
        # a photo searched by the person's name must show them clearly, not a stage with their legs
        return not surname[0] or surname[0].lower() not in query.lower() or any(w >= PERSON_FACE for _, w in fs)
    photos, seen = [], set()
    fresh = lambda cands: [c for c in cands if c.get('page') not in seen]   # never the same picture twice
    lists = [(v['query'], [c for c in (v.get('candidates') or _safe(_commons_images, v['query'])) if _relevant(c, v['query'])])
             for v in visuals if v['kind'] == 'photo']

    def take(query, cands):
        got = _fetch_first(base, f'photos/{len(photos)}', fresh(cands), lambda path: alone(path, query))
        if got:
            seen.add(got['page'])
            photos.append({'query': query, **{k: got[k] for k in ('file', 'credit', 'licence', 'page')}})
        return got

    for q, cands in lists:   # one photo per photo visual first
        take(q, cands)
    cap = {q: max(2, sum(x == q for x, _ in lists)) for q, _ in lists}   # one place or object never fills the pool
    room = lambda q, cands: fresh(cands) and sum(p['query'] == q for p in photos) < cap[q]
    while len(photos) < POOL_PHOTOS and any(room(q, c) for q, c in lists):   # then top the pool up, round robin over the queries
        for q, cands in lists:
            if len(photos) < POOL_PHOTOS and room(q, cands) and not take(q, fresh(cands)[:1]):
                seen.add(fresh(cands)[0].get('page'))   # failed or refused: do not try it again
    if len(photos) < POOL_PHOTOS:   # then the person themselves: face-checked photos, the case is about them
        name = (job.get('person') or {}).get('name', '')
        photos += [{'query': name, **{k: p[k] for k in ('file', 'credit', 'licence', 'page')}}
                   for p in _person_photos(job, run, state, base) if p['page'] not in seen][:POOL_PHOTOS - len(photos)]
    if len(photos) < 2:
        return _missing(job, 'assets', f'only {len(photos)} photos could be downloaded (2 needed)')
    footage = _footage(job, run, state, base, strict=True)
    return 'next', {'assets': {'screenshots': done, 'photos': photos, 'footage': footage}, 'agentErrors': []}, f'{len(done)} screenshots, {len(photos)} photos, {len(footage)} footage shots'
