"""Front stages of the NoWayClips trending graph: refresh, people, route, mediaplan.
Each is (job, cfg, run, state) -> (port, output, log). No stage here downloads video or audio."""
import datetime as dt, itertools, json, os, re, statistics, time, urllib.error, urllib.parse
from pathlib import Path
from . import legal, sourcerules as formats, net, outlets, people as pp, soundmomentum as sm, transcripts, ytsrc

today = lambda: dt.datetime.now(dt.timezone.utc).date()
sleep = time.sleep
HERE = Path(__file__).parent
WIKI = 'https://wikimedia.org/api/rest_v1/metrics/pageviews'
DOC_TAGS = 'documentary truecrime cinematic suspense darkambient'.split()
SETS = {'edit': (sm.EDIT_TAGS, sm.EDIT_CHANNELS), 'sad': (sm.SAD_TAGS, []), 'documentary': (DOC_TAGS, [])}


def jread(p, default):
    try: return json.loads(Path(p).read_text())
    except (OSError, ValueError): return default


def dead_end(job, name, qid, why):
    """Person-level dead end: remember the qid and tell the route agent why (replaces stale errors)."""
    return 'missing', {'rejectedPeople': list(job.get('rejectedPeople', [])) + [qid], 'agentErrors': [f'{name} rejected: {why}']}, why


# ---------- refresh ----------

def refresh(job, cfg, run, state):
    res = {'refreshed': 0, 'discovered': [], 'stoppedBy': None}
    try:
        sdir, now = str(Path(state) / 'sounds'), today()
        hist = sm.load_history(sdir)
        if not any(str(now) in h['uses'] for h in hist.values()) and hist:
            t0 = time.time(); sm.Budget.cap, sm.Budget.n = 400, 0
            for src, h in list(hist.items())[:150]:
                if time.time() - t0 > 180: res['stoppedBy'] = 'time budget'; break
                try:
                    _, _, head = sm.sound_page(sm.pivot_token(sm.yt_reel(h['example'], sdir)), 1, sdir)
                except OSError as e: res['stoppedBy'] = f'{type(e).__name__}: {e}'[:120]; break  # network error or bot check: keep what we have
                except Exception: continue  # one dead sound
                if head.get('total_uses'): h['uses'][str(now)] = head['total_uses']; res['refreshed'] += 1
            os.makedirs(sdir, exist_ok=True); json.dump(hist, open(os.path.join(sdir, 'uses-history.json'), 'w'), indent=1)
        # one set per run, so each gets the whole budget (all three did not fit in one run's 10 minutes); stalest first
        dates = jread(Path(sdir) / 'discovery.json', {})
        dates = {name: dates['date'] for name in SETS} if 'date' in dates else dates  # the old single-date file
        due = sorted((dates.get(name, ''), i, name) for i, name in enumerate(SETS) if not dates.get(name) or (now - dt.date.fromisoformat(dates[name])).days > 7 or not any(Path(sdir).glob(f'momentum-{name}-*.json')))
        if not res['stoppedBy'] and due:
            name = due[0][2]; tags, chans = SETS[name]
            sm.Budget.cap, sm.Budget.n = 450, 0
            try:
                report = sm.run_set(name, tags, chans, 40, 4, 0, now, sdir); res['discovered'].append(name)
                os.makedirs(sdir, exist_ok=True); (Path(sdir) / f'momentum-{name}-{now}.json').write_text(json.dumps(report))  # music reads it
                (Path(sdir) / 'discovery.json').write_text(json.dumps({**dates, name: str(now)}))
            except Exception as e: res['stoppedBy'] = f'{type(e).__name__}: {e}'[:120]
    except Exception as e:  # never raise: the run goes on without fresh sound data
        res['stoppedBy'] = f'{type(e).__name__}: {e}'[:120]
    return 'next', {'soundsRefresh': res}, f"refresh {res}"


# ---------- people ----------

def _top(now):
    for back in (1, 2):
        d = now - dt.timedelta(days=back)
        try: return d, pp.top_articles(net.get_json(f"{WIKI}/top/en.wikipedia/all-access/{d:%Y/%m/%d}"))
        except urllib.error.HTTPError as e:
            if e.code != 404 or back == 2: raise


def _get(url):
    """Wikimedia and Wikidata answers 429 to bursts, so pace the calls and retry once."""
    for attempt in (0, 1):
        sleep(0.25)
        try: return net.get_json(url)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt: raise
            sleep(3)


def _headlines(c):
    try: c['headlines'] = pp.parse_rss(net.get_text('https://news.google.com/rss/search?q=' + urllib.parse.quote(f'"{c["name"]}" when:3d')
                                                      + '&hl=en-GB&gl=GB&ceid=GB:en'))
    except Exception: pass  # headlines are a bonus; casefile routing will reject without them
    # a death in the news before Wikidata has it, confirmed by the person's own Wikipedia lead (a namesake's headline is not theirs)
    if not c.get('died') and (d := pp.death_in_headlines(c['name'], c.get('headlines') or [])) and c.get('title'):
        try:
            lead = net.get_json('https://en.wikipedia.org/api/rest_v1/page/summary/' + urllib.parse.quote(c['title'], safe='')).get('extract')
        except Exception: lead = ''
        if pp.lead_says_dead(lead):
            c['died'] = d
    return c


def _wanted(job, now):
    """The run input's chosen person (want.person: a name or a Wikidata id) as the only candidate, with no spike or covered
    filter: for testing a format or a one-off request. Rejected for this run means the run ends."""
    who = str(job['want']['person']).strip()
    ids = [who] if re.fullmatch(r'Q\d+', who) else [r['id'] for r in _get('https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json'
                                                                           f'&language=en&type=item&limit=5&search={urllib.parse.quote(who)}').get('search', [])]
    for q in ids:
        found = pp.humans(_get(f'https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&languages=en'
                               f'&props=claims|descriptions|labels|sitelinks&ids={q}'))
        title, h = next(((t, h) for t, h in found.items() if h['qid'] == q), (None, None))
        if h:
            if h['qid'] in job.get('rejectedPeople', []):
                break
            c = _headlines(dict(h, title=title.replace(' ', '_'), views=0, spike=None, age=pp.age(h['born'], h['died'], now), headlines=[]))
            return 'next', {'candidates': [c]}, f"wanted: {c['name']} ({c['qid']})"
    why = f'{who} rejected at people: not found as a person on Wikidata, or already rejected in this run'
    return 'missing', {'candidates': [], 'agentErrors': [why]}, why


def people(job, cfg, run, state):
    now = today()
    if (job.get('want') or {}).get('person'):
        return _wanted(job, now)
    day, rows = _top(now)
    rows = rows[:200]
    humans = {}
    for i in range(0, len(rows), 50):
        titles = '|'.join(t.replace('_', ' ') for t, _ in rows[i:i + 50])
        humans.update(pp.humans(_get('https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&sites=enwiki&languages=en'
                                             f'&props=claims|descriptions|labels|sitelinks&titles={urllib.parse.quote(titles)}')))
    covered = jread(Path(state) / 'trending-covered.json', [])
    skip = set(job.get('rejectedPeople', [])) | {c['qid'] for c in covered   # a Short in the last 2 days: skipped before any lookup
                                                  if (now - dt.date.fromisoformat(c['date'])).days < pp.GAP_DAYS}
    kept = []
    for title, views in rows:
        h = humans.get(title.replace('_', ' '))
        if not h or h['qid'] in skip or len(kept) >= 40: continue
        try:
            daily = _get(f"{WIKI}/per-article/en.wikipedia/all-access/user/{urllib.parse.quote(title, safe='')}/daily/"
                                 f"{day - dt.timedelta(days=29):%Y%m%d}/{day:%Y%m%d}")
            sp = pp.spike([x['views'] for x in daily['items']])
        except Exception: sp = None
        died = pp.died_recently(h['died'], now)
        if died or (sp or 0) >= 3:
            kept.append(dict(h, title=title, views=views, spike=sp, age=pp.age(h['born'], h['died'], now), headlines=[]))
    for c in sorted(kept, key=lambda c: -c['views'])[:12]:
        _headlines(c)
    for c in kept:   # earlier Shorts of the person: shown to the route agent, and the formats that would not repeat one
        c['covered'] = [{k: e.get(k) for k in ('format', 'date', 'title', 'angle')} for e in covered if e.get('qid') == c['qid']]
        fmts = ['tribute'] if pp.died_recently(c['died'], now) else [f for f in formats.FORMATS if f != 'tribute']
        c['formats'] = [f for f in fmts if not pp.repeat_block(c['qid'], f, covered, c['headlines'], now)]
    kept = [c for c in kept if c['formats']]
    cands = sorted(kept, key=lambda c: -c['views'] * min(c['spike'] or 1, 10))[:10]
    if not cands: return 'missing', {'candidates': [], 'agentErrors': ['no trending person left after filters']}, 'no candidates'
    return 'next', {'candidates': cands}, f"{len(humans)} humans, {len(kept)} trending, {len(cands)} candidates"


# ---------- route ----------

def route(job, cfg, run, state):
    pick, cands = job.get('pick') or {}, {c['qid']: c for c in job.get('candidates', [])}
    bad = lambda why: ('invalid', {'agentErrors': [why]}, why)
    qid, fmt = pick.get('qid'), pick.get('format')
    if qid not in cands: return bad(f'{qid} is not one of the candidates')
    if qid in job.get('rejectedPeople', []): return bad(f'{qid} was rejected already; pick someone else')
    if fmt not in formats.FORMATS: return bad(f'unknown format {fmt!r}; use one of {sorted(formats.FORMATS)}')
    want = (job.get('want') or {}).get('format')
    if want in formats.FORMATS and fmt != want:   # a chosen format wins over the agent's; the rules below still apply
        fmt = want
    person, note = cands[qid], ''
    if pp.died_recently(person.get('died'), today()):
        note, fmt = ('' if fmt == 'tribute' else f'died {person["died"]}: format overridden to tribute'), 'tribute'
    elif fmt == 'tribute': return bad(f'{person["name"]} has no recent death (14 days); tribute is not possible')
    covered = jread(Path(state) / 'trending-covered.json', [])
    if not (job.get('want') or {}).get('person') and (why := pp.repeat_block(qid, fmt, covered, person.get('headlines') or [], today())):
        return bad(f'{person["name"]} as {fmt} would repeat a published Short ({why}): pick a format in their `formats` or someone else')
    if fmt == 'casefile':
        doms = [h['domain'] for h in person.get('headlines', [])] + [outlets.domain(a['url']) for a in pick.get('articles', []) if a.get('url')]
        if len(outlets.distinct(doms)) < 2:
            return bad(f'casefile needs 2 distinct allowlisted outlets for {person["name"]}; found {sorted(outlets.distinct(doms))}')
    b = HERE / 'briefs'
    ctx = {'brief': (b / f'{fmt}.md').read_text(), 'schema': (b / f'{fmt}.schema.json').read_text()}
    return 'next', {'verifyTries': 0, 'person': person, 'format': fmt, 'formatContext': ctx, 'agentErrors': []}, note or f'{person["name"]} as {fmt}'


# ---------- mediaplan ----------

def _info(vid, out_dir):
    for attempt in (0, 1):
        try: return ytsrc.info_and_words(vid, out_dir)
        except RuntimeError as e:
            if '429' not in str(e): break
            if attempt == 0: sleep(30)  # rate limited: wait once, then give up on this source
    return None, []


def _articles(arts):
    out = []
    for a in arts:
        dom = outlets.domain(a.get('url', ''))
        if not outlets.allowed(dom) or any(o['domain'] == dom for o in out): continue
        try:
            import sources  # engine folder is on sys.path
            text = '\n\n'.join(sources.extract(net.get_text(a['url']))[2])[:12000]
        except Exception: continue
        if text: out.append(dict(outlet=a.get('outlet') or dom, domain=dom, url=a['url'], text=text))
    return out


def mediaplan(job, cfg, run, state):
    run, person, fmt, pick = Path(run), job['person'], job['format'], job.get('pick') or {}
    rule, sur = formats.FORMATS[fmt], formats.surname(job['person']['name'])
    arts = _articles(pick.get('articles', [])) if fmt == 'casefile' else []
    (run / 'articles.txt').write_text('\n\n'.join(f"### {a['outlet']} | {a['url']}\n{a['text']}" for a in arts))
    out = {'articles': arts, 'articlesText': {'file': 'articles.txt'}, 'transcripts': {'file': 'transcripts.txt'}}
    def dead(why):
        port, o, _ = dead_end(job, person['name'], person['qid'], why)
        return port, {**out, **o, 'agentErrors': [f"{person['name']} rejected at mediaplan: {why}"]}, why
    if fmt == 'casefile' and len(outlets.distinct([a['domain'] for a in arts])) < 2:
        return dead(f'fewer than 2 readable articles from distinct allowlisted outlets ({len(arts)} found)')
    if fmt == 'casefile' and (why := legal.active_case([a['text'] for a in arts])):
        return dead(why)   # UK contempt of court: checked on the article text, before any storyboard
    archived = {l.split()[-1] for l in (Path(state) / 'archive.txt').read_text().splitlines() if l.strip()} if (Path(state) / 'archive.txt').exists() else set()
    excluded = archived | set(job.get('rejectedSources', []))
    # each query in turn, most viewed first: one query's viral clips must not crowd out what the other queries asked for
    lists = [sorted((e for e in ytsrc.search(q, 20) if formats.usable(e, fmt, sur, excluded)), key=lambda e: -(e.get('view_count') or 0))
             for q in pick.get('queries', [])[:6]]
    found = {}
    for row in itertools.zip_longest(*lists):
        for e in row:
            if e: found.setdefault(e['id'], e)
    cand = list(found.values())[:rule['k']]
    cap_dir = run / 'captions'; cap_dir.mkdir(parents=True, exist_ok=True)
    kw = [sur] + [w for w in formats.fold(f"{pick.get('angle', '')} {pick.get('theme', '')}").split() if len(w) >= 5]
    pool, blocks = [], []
    for e in cand:
        info, words = _info(e['id'], str(cap_dir / 'info'))
        words = transcripts.clean(words)
        if not words: continue
        meta = dict(id=e['id'], title=e['title'], channel=e.get('channel', ''), duration=round(e['duration']), uploaded=e.get('upload_date') or (info or {}).get('upload_date', ''))
        (cap_dir / f"{e['id']}.words.json").write_text(json.dumps(words))
        pool.append(dict(meta, url=f"https://www.youtube.com/watch?v={e['id']}", views=e.get('view_count'), words=f"captions/{e['id']}.words.json"))
        blocks.append((meta, ytsrc.sentences(words), info or {}))
    (run / 'transcripts.txt').write_text(transcripts.build(blocks, kw))
    if len(pool) < rule['min']:
        return dead(f"only {len(pool)} usable sources with English captions ({fmt} needs {rule['min']})")
    return 'next', {**out, 'pool': pool, 'agentErrors': []}, f"{len(pool)} sources, {len(arts)} articles"
