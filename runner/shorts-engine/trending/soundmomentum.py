"""Momentum trending-sound finder for YouTube Shorts (approximates the app's "trending sounds" list).

Pipeline: seed Shorts (hashtag feeds + channels, via yt-dlp) -> sound() each -> group by source video id ->
probe top N sounds (up to P pages of the sound's page, 15 Shorts/page) -> fetch upload dates for K Shorts
(spread across pages, youtubei /player microformat.publishDate) -> score.

Score (adjust the constants/formula here):
    recent_share_7d = dated Shorts posted in last 7 days / dated Shorts   (30d likewise)
    recent_views    = median views of dated Shorts from the last 30 days
    depth           = Shorts seen on the sound's pages (60+ when more pages exist)
    depth_factor    = min(1, depth / 60)
    momentum        = depth_factor * recent_share_7d * log10(1 + recent_views)
type_hint is a crude title regex (instrumental vs "may have vocals"), not audio analysis.
Caveats: a sound's page is ordered by popularity (old hits), NOT recency, so 7d share is usually ~0 and momentum
collapses; the page header does give total uses ("313K Shorts"). Extra, not in momentum: uses_per_day = total_uses /
age of the sound's source video (crude lifetime rate). Ranking: momentum, then uses_per_day, then seed_count.

Everything it keeps (request cache, uses history, momentum reports) lives in the caller's directory `sdir` (the stages pass <state>/sounds):
    sdir/youtubei/ (cache), sdir/uses-history.json, sdir/momentum-<set>-<date>.json|md

Usage: python -m trending.soundmomentum --dir SDIR --set edit|sad|all [--top 40 --pages 4 --dates 20 --tags a,b --channels h1,h2 --max-requests 1500]
"""
import urllib.parse, argparse, collections, datetime as dt, hashlib, json, math, os, re, statistics, sys, time, urllib.error, urllib.request
from .sound import find, reel_body, sound_from
from shared import ytdlp  # engine folder is on sys.path

CTX = reel_body('x')['context']
PIVOT = 'RkVzZnZfYXVkaW9fcGl2b3Q'  # base64 of FEsfv_audio_pivot
EDIT_TAGS = 'edit edits phonk funk f1edit footballedit nbaedit ufcedit boxingedit carsedit animeedit movieedit celebrityedit podcastclips motivation sigma gymedit aftereffects capcut velocity'.split()
SAD_TAGS = 'rip tribute sadedit restinpeace ripedit memorial sad emotional legend grief'.split()
EDIT_CHANNELS = ['NKByte']
INSTR = re.compile(r'instrumental|slowed|phonk|funk|montagem|beat|remix|bass|ultra', re.I)

class Budget:
    n = 0; cap = 1500; sleep = 0.3
    @classmethod
    def left(cls): return cls.cap - cls.n

def _cached(sdir, key, fn, ttl=86400):
    cache = os.path.join(sdir, 'youtubei')
    os.makedirs(cache, exist_ok=True)
    p = os.path.join(cache, hashlib.sha1(key.encode()).hexdigest() + '.json')
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < ttl: return json.load(open(p))
    v = fn(); json.dump(v, open(p, 'w')); return v

def _post(ep, body):
    if Budget.n >= Budget.cap: raise RuntimeError('request budget exhausted')
    for attempt in (0, 1):
        Budget.n += 1; time.sleep(Budget.sleep)
        r = urllib.request.Request(f'https://www.youtube.com/youtubei/v1/{ep}?prettyPrint=false', data=json.dumps(body).encode(),
                                   headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        try: return json.load(urllib.request.urlopen(r, timeout=30))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0: time.sleep(20); continue
            raise

def yt_reel(vid, sdir): return _cached(sdir, 'reel' + vid, lambda: _post('reel/reel_item_watch', reel_body(vid)))
def yt_browse(token, sdir, vd=None):
    """Page 2+ returns an empty body unless the previous response's visitorData is sent in the client context."""
    ctx = {'client': dict(CTX['client'], visitorData=vd)} if vd else CTX
    return _cached(sdir, 'browse2' + token + (vd or ''), lambda: _post('browse', {'context': ctx, 'continuation': token}))
def upload_date(vid, sdir):
    """'YYYY-MM-DD' via youtubei /player microformat (works even when playability is UNPLAYABLE); None if missing."""
    def go():
        p = _post('player', {'context': CTX, 'videoId': vid})
        d = next(iter(find(p, 'publishDate')), None) or next(iter(find(p, 'uploadDate')), None)
        return {'d': d[:10] if d else None}
    return _cached(sdir, 'date' + vid, go)['d']

def parse_views(s):
    """'7.3 million views' -> 7300000; '812K views'; '1,234 views'; 'No views' -> 0; unparseable -> None."""
    s = (s or '').strip().lower()
    if s.startswith('no view'): return 0
    m = re.match(r'([\d.,]+)\s*(k|m|b|thousand|million|billion)?', s)
    if not m: return None
    try: n = float(m.group(1).replace(',', ''))
    except ValueError: return None
    return int(round(n * {None: 1, 'k': 1e3, 'thousand': 1e3, 'm': 1e6, 'million': 1e6, 'b': 1e9, 'billion': 1e9}[m.group(2)]))

def pivot_token(d):
    """The continuation token that leads to the audio-pivot (sound page), or None."""
    for c in find(d, 'continuationEndpoint'):
        t = c.get('continuationCommand', {}).get('token')
        if t and PIVOT in t: return t

def momentum(depth, share7, views):
    return min(1, depth / 60) * share7 * math.log10(1 + views)

def group_sounds(items):
    """items: [{vid, views, title, source}] -> ranked groups (seed count, ties by summed views). Skips 'Original Sound'."""
    g = {}
    for it in items:
        t = it.get('title') or ''
        if not t or t.lower().startswith('original sound'): continue
        k = it.get('source') or 't:' + re.sub(r'\W+', ' ', t.lower()).strip()
        x = g.setdefault(k, dict(key=k, title=t, source=it.get('source'), meta=it.get('meta') or [], seed_count=0, seed_views=0, seed_shorts=[]))
        x['seed_count'] += 1; x['seed_views'] += it.get('views') or 0; x['seed_shorts'].append(it['vid'])
    return sorted(g.values(), key=lambda x: (-x['seed_count'], -x['seed_views']))

def sound_page(token, pages, sdir):
    """-> (shorts[{vid,views,title}] in page order, more_pages, header{artist,total_uses,page_source}). Stops at `pages` pages."""
    out, more, head, vd = [], False, {}, None
    for i in range(pages):
        b = yt_browse(token, sdir, vd)
        vd = urllib.parse.unquote(b.get('responseContext', {}).get('visitorData', '')) or None
        if not head:  # header repeats title, artist, "313K Shorts" (total uses) and the sound's source video
            h = next(find(b, 'pageHeaderViewModel'), {}); c = [x for x in find(h, 'content') if isinstance(x, str)]
            head = dict(page_source=next(find(h, 'watchEndpoint'), {}).get('videoId'),
                        artist=c[1] if len(c) > 2 else None, total_uses=parse_views(c[-1]) if len(c) > 2 and 'short' in c[-1].lower() else None)
        for it in find(b, 'shortsLockupViewModel'):
            vid = next(find(it, 'videoId'), None)
            m = re.search(r',\s*([^,]*?views?)\s*-\s*play Short', it.get('accessibilityText', ''))
            out.append(dict(vid=vid, views=parse_views(m.group(1)) if m else None, title=it.get('accessibilityText', '').split(',')[0]))
        token = next((c['token'] for c in find(b, 'continuationCommand') if c.get('token')), None)
        more = bool(token)
        if not token: break
    return out, more, head

def spread(xs, k):
    if len(xs) <= k: return list(xs)
    return [xs[int(i * len(xs) / k)] for i in range(k)]

def score(shorts, dates, more, today):
    dated = [(s, dt.date.fromisoformat(dates[s['vid']])) for s in shorts if dates.get(s['vid'])]
    age = lambda d: (today - d).days
    n = len(dated)
    r7 = sum(age(d) <= 7 for _, d in dated); r30 = [s for s, d in dated if age(d) <= 30]
    depth = len(shorts)
    rv = statistics.median([s['views'] or 0 for s in r30]) if r30 else 0
    sh7 = r7 / n if n else 0
    return dict(depth=depth, more_pages=more, dated=n, recent_share_7d=round(sh7, 3), recent_share_30d=round(len(r30) / n, 3) if n else 0,
                recent_views=rv, momentum=round(momentum(depth, sh7, rv), 3))

def ytdlp_ids(url, n, sdir):
    def go():
        out = ytdlp.run(['--flat-playlist', '-I', f'1:{n}', '--print', '%(id)s %(view_count)s', url], capture_output=True, text=True).stdout
        return [l.split() for l in out.split('\n') if l.strip()]
    return _cached(sdir, 'ids' + url + str(n), go, ttl=6 * 3600)

def seed(tags, channels, sdir):
    shorts = {}
    urls = [(f'https://www.youtube.com/hashtag/{t}/shorts', 40) for t in tags] + [(f'https://www.youtube.com/@{c}/shorts', 30) for c in channels]
    for u, n in urls:
        for row in ytdlp_ids(u, n, sdir):
            v = row[1] if len(row) > 1 and row[1].isdigit() else '0'
            shorts.setdefault(row[0], int(v))
    items = []
    for vid, views in shorts.items():
        if Budget.left() <= 0: break
        try: s = sound_from(yt_reel(vid, sdir))
        except Exception as e: print('seed skip', vid, e, file=sys.stderr); continue
        if s: items.append(dict(vid=vid, views=views, **s))
    return items, len(shorts)

def run_set(name, tags, channels, top, pages, ndates, today, sdir):
    items, nseed = seed(tags, channels, sdir)
    groups = [g for g in group_sounds(items) if g['source']][:top]  # sourceless = not a reusable track (a Short's own title), dropped
    for gi, g in enumerate(groups):
        tok = None
        for v in g['seed_shorts'][:3]:
            try: tok = pivot_token(yt_reel(v, sdir))
            except Exception: tok = None
            if tok: break
        if not tok or Budget.left() < pages: g.update(depth=0, momentum=0, note='no sound page / budget'); continue
        try: shorts, more, head = sound_page(tok, pages, sdir)
        except Exception as e: g.update(depth=0, momentum=0, note=str(e)); continue
        k = max(0, min(ndates, (Budget.left() - 0) // max(1, len(groups) - gi) - pages))
        dates = {}
        for s in spread(shorts, k):
            try: dates[s['vid']] = upload_date(s['vid'], sdir)
            except Exception: pass
        extra = {}
        try:
            sd = upload_date(head.get('page_source') or g['source'], sdir)
            if sd and head.get('total_uses'):
                extra = dict(source_age_days=(today - dt.date.fromisoformat(sd)).days)
                extra['uses_per_day'] = round(head['total_uses'] / max(1, extra['source_age_days']), 1)
        except Exception: pass
        g.update(score(shorts, dates, more, today), **head, **extra, examples=[s['vid'] for s in shorts[:3]], shorts=shorts, dates=dates)
        print(f"[{name}] {gi + 1}/{len(groups)} {g['title'][:40]!r} depth={g['depth']} m={g['momentum']} req={Budget.n}", file=sys.stderr)
    for g in groups:
        g['type_hint'] = 'instrumental' if INSTR.search(g['title']) else 'may have vocals'
        g.setdefault('momentum', 0)
    record(groups, today, load_history(sdir), sdir)
    groups.sort(key=rank_key)
    return dict(set=name, date=str(today), seed_shorts=nseed, seed_named=len(items), requests=Budget.n, sounds=groups)

def _history(sdir): return os.path.join(sdir, 'uses-history.json')

def load_history(sdir):
    try: return json.load(open(_history(sdir)))
    except (OSError, ValueError): return {}

def growth(uses_by_date, today):
    """Shorts added per day since the latest earlier snapshot -> (per_day, pct_per_day, days) or None."""
    t = str(today)
    if t not in uses_by_date: return None
    prev = [d for d in uses_by_date if d < t]
    if not prev: return None
    d0 = max(prev); days = (today - dt.date.fromisoformat(d0)).days
    a, b = uses_by_date[d0], uses_by_date[t]
    return round((b - a) / days, 1), round(100 * (b - a) / max(1, a) / days, 2), days

def record(groups, today, hist, sdir):
    """Save today's total uses per source into the history and attach growth to each group."""
    for g in groups:
        if not g.get('total_uses'): continue
        h = hist.setdefault(g['source'], dict(title=g['title'], example=(g.get('examples') or g['seed_shorts'])[0], uses={}))
        h['uses'][str(today)] = g['total_uses']
        gr = growth(h['uses'], today)
        if gr: g['growth_per_day'], g['growth_pct_day'], g['growth_days'] = gr
    os.makedirs(sdir, exist_ok=True); json.dump(hist, open(_history(sdir), 'w'), indent=1)

def rank_key(g):
    # Real momentum = growth in total uses between snapshots; until a 2nd snapshot exists, fall back to how often the sound shows up in today's (recent) hashtag sample.
    return (-(g.get('growth_per_day') or -1e18), -g['seed_count'], -(g.get('total_uses') or 0))

def refresh(today, sdir):
    """Cheap daily update (~2 requests per tracked sound): re-read total uses for every sound in the history."""
    hist = load_history(sdir); out = []
    for src, h in hist.items():
        try:
            tok = pivot_token(yt_reel(h['example'], sdir))
            _, _, head = sound_page(tok, 1, sdir)
        except Exception as e: print('refresh skip', src, e, file=sys.stderr); continue
        if head.get('total_uses'):
            h['uses'][str(today)] = head['total_uses']
            gr = growth(h['uses'], today)
            out.append(dict(source=src, title=h['title'], total_uses=head['total_uses'], seed_count=0,
                            **(dict(zip(('growth_per_day', 'growth_pct_day', 'growth_days'), gr)) if gr else {})))
    os.makedirs(sdir, exist_ok=True); json.dump(hist, open(_history(sdir), 'w'), indent=1)
    return sorted(out, key=rank_key)

def md(res):
    L = [f"# Sound momentum: {res['set']} ({res['date']})", '',
         'momentum = min(1, depth/60) x recent_share_7d x log10(1 + median views of dated Shorts from last 30d). '
         'Pages are popularity-ordered so momentum is mostly 0; uses/day = total uses / source video age (crude). type_hint is a crude title regex. Dates sampled (spread across pages), so shares are estimates.', '',
         'RANKING: growth/day = Shorts added per day since the previous snapshot in uses-history.json (the real trending signal); until a sound has 2 snapshots it ranks by seed count (how often it appears in today\'s hashtag sample).', '',
         '| # | title | artist | source | growth/day | growth %/day | seed | depth | total uses | uses/day | 7d | 30d | med views | momentum | type | examples |', '|' + '---|' * 16]
    for i, g in enumerate(res['sounds'], 1):
        L.append(f"| {i} | {g['title']} | {g.get('artist') or ''} | {g['source']} | {g.get('growth_per_day', '')} | {g.get('growth_pct_day', '')} | {g['seed_count']} | {g.get('depth', 0)}{'+' if g.get('more_pages') else ''} | {g.get('total_uses') or ''} | {g.get('uses_per_day', '')} | "
                 f"{g.get('recent_share_7d', '')} | {g.get('recent_share_30d', '')} | {int(g.get('recent_views', 0))} | {g['momentum']} | {g['type_hint']} | {', '.join(g.get('examples', []))} |")
    return '\n'.join(L) + '\n'

def main(argv=None):
    a = argparse.ArgumentParser()
    a.add_argument('--dir', required=True, help='state directory for cache, history and reports')
    a.add_argument('--set', default='edit', choices=['edit', 'sad', 'all'])
    a.add_argument('--tags'); a.add_argument('--channels')
    a.add_argument('--top', type=int, default=40); a.add_argument('--pages', type=int, default=4); a.add_argument('--dates', type=int, default=0)  # sampled upload dates: pages are popularity-ordered, so this adds cost but little signal
    a.add_argument('--max-requests', type=int, default=1500)
    a.add_argument('--refresh', action='store_true', help='only re-read total uses of tracked sounds (cheap daily run)')
    a = a.parse_args(argv)
    if a.refresh:
        Budget.cap, Budget.n = a.max_requests, 0
        for i, g in enumerate(refresh(dt.date.today(), a.dir), 1):
            print(f"{i:2} +{g.get('growth_per_day', '-')}/day ({g.get('growth_pct_day', '-')}%) uses={g['total_uses']} {g['source']} {g['title'][:50]}")
        print(f'requests={Budget.n}'); return
    Budget.cap, Budget.n = a.max_requests, 0
    tags = a.tags.split(',') if a.tags else {'edit': EDIT_TAGS, 'sad': SAD_TAGS, 'all': EDIT_TAGS + SAD_TAGS}[a.set]
    chans = a.channels.split(',') if a.channels else (EDIT_CHANNELS if a.set in ('edit', 'all') else [])
    today = dt.date.today(); t0 = time.time()
    res = run_set(a.set, tags, chans, a.top, a.pages, a.dates, today, a.dir)
    res['seconds'] = round(time.time() - t0)
    base = os.path.join(a.dir, f'momentum-{a.set}-{today}')
    os.makedirs(os.path.dirname(base), exist_ok=True)
    json.dump(res, open(base + '.json', 'w'), indent=1); open(base + '.md', 'w').write(md(res))
    for i, g in enumerate(res['sounds'][:20], 1):
        print(f"{i:2} +{g.get('growth_per_day', '-')}/d {g['momentum']:5} d={g.get('depth', 0):2} uses={g.get('total_uses')} u/d={g.get('uses_per_day')} 7d={g.get('recent_share_7d', '-')} seed={g['seed_count']} {g['source']} {g['title'][:45]} [{g['type_hint']}]")
    print(f"requests={res['requests']} seconds={res['seconds']} -> {base}.md")

if __name__ == '__main__': main()
