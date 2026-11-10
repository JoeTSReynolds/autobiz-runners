"""Pure helpers for the `people` stage: pageview rows, Wikidata claims, spike maths, Google News RSS."""
import datetime as dt, email.utils, re, statistics
import xml.etree.ElementTree as ET
from .outlets import domain

SKIP = ('Main_Page', 'Special:', 'Wikipedia:', 'File:', 'Portal:', '-')


def top_articles(resp):
    """Pageviews top response -> [(title, views)] without the non-article rows."""
    rows = resp['items'][0]['articles']
    return [(r['article'], r['views']) for r in rows if r['article'] != '-' and not r['article'].startswith(SKIP)]


def _ids(claims, pid): return [c['mainsnak']['datavalue']['value'].get('id') for c in claims.get(pid, []) if 'datavalue' in c['mainsnak']]
def _date(claims, pid):
    for c in claims.get(pid, []):
        m = re.match(r'\+?(\d{4})-(\d\d)-(\d\d)', c.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('time', ''))
        if m: return '-'.join(m.groups())  # imprecise dates keep 00 parts
    return None


def humans(resp):
    """wbgetentities response -> {enwiki title: person} for entities that are P31 = Q5."""
    out = {}
    for q, e in resp.get('entities', {}).items():
        cl = e.get('claims', {})
        if 'Q5' not in _ids(cl, 'P31') or 'enwiki' not in e.get('sitelinks', {}): continue
        img = next((c['mainsnak']['datavalue']['value'] for c in cl.get('P18', []) if 'datavalue' in c['mainsnak']), None)
        out[e['sitelinks']['enwiki']['title']] = dict(
            qid=e.get('id', q), name=e.get('labels', {}).get('en', {}).get('value', e['sitelinks']['enwiki']['title']),
            description=e.get('descriptions', {}).get('en', {}).get('value', ''), born=_date(cl, 'P569'), died=_date(cl, 'P570'),
            image=img, occupations=[i for i in _ids(cl, 'P106') if i])
    return out


def spike(views):
    """Last day's views over the median of the days before it; None with fewer than 10 days of data."""
    return round(views[-1] / max(statistics.median(views[:-1]), 1), 2) if len(views) >= 10 else None


def _parse(d):
    try: return dt.date.fromisoformat(d)
    except (TypeError, ValueError): return None


def died_recently(died, today, days=14):
    d = _parse(died)
    return bool(d) and 0 <= (today - d).days <= days


def age(born, died, today):
    b = _parse(born)
    if not b: return None
    end = _parse(died) or today
    return end.year - b.year - ((end.month, end.day) < (b.month, b.day))


def parse_rss(xml_text, limit=10):
    out = []
    for it in ET.fromstring(xml_text).iter('item'):
        src = it.find('source')
        out.append(dict(title=(it.findtext('title') or '').strip(), outlet=(src.text or '').strip() if src is not None else '',
                        domain=domain(src.get('url', '')) if src is not None else '', date=(it.findtext('pubDate') or '').strip()))
    return out[:limit]


DEATH = re.compile(r"\b(dies|has died|passes away|has passed away|dead at \d+)\b", re.I)


def death_in_headlines(name, headlines):
    """ISO date of the first headline reporting the person's death (Wikidata lags a day or two), or None."""
    last = name.split()[-1].lower()
    for h in headlines:
        if last in h['title'].lower() and DEATH.search(h['title']):
            try: return email.utils.parsedate_to_datetime(h['date']).date().isoformat()
            except (TypeError, ValueError): return None
    return None


GAP_DAYS, SAME_FORMAT_DAYS = 2, 30


def _hdate(h):
    try: return email.utils.parsedate_to_datetime(h['date']).date()
    except (TypeError, ValueError, KeyError): return None


def repeat_block(qid, fmt, covered, headlines, today):
    """Why a Short of this person in this format would repeat a published one, or None. covered: published Shorts
    [{qid, format, date}]; an entry without a format counts as every format."""
    mine = [(c, (today - dt.date.fromisoformat(c['date'])).days) for c in covered if c.get('qid') == qid]
    if fmt == 'tribute':   # one per person, whatever else was made
        return 'already has a tribute' if any(c.get('format') == 'tribute' for c, _ in mine) else None
    if any(d < GAP_DAYS for _, d in mine):
        return f'had a Short in the last {GAP_DAYS} days'
    same = [(c, d) for c, d in mine if c.get('format') in (fmt, None) and d <= SAME_FORMAT_DAYS]
    if not same:
        return None
    last = max(dt.date.fromisoformat(c['date']) for c, _ in same)
    if fmt == 'casefile':   # a new development (a verdict, a sentence) is a new case file
        return None if any((_hdate(h) or last) > last for h in headlines) else f'casefile on {last} and no news since'
    return f'{fmt} on {last}: one {fmt} a month'


def lead_says_dead(extract):
    """The person's own Wikipedia lead speaks of them in the past tense ("X was an English presenter"): a death headline
    found by name can be about a namesake, the article cannot."""
    return bool(re.match(r"[^.]{0,150}?\bwas (a|an|the)\b", extract or ''))
