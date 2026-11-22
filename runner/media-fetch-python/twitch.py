"""Twitch helper for media-fetch (stdlib only). Every subcommand prints JSON on stdout.

  clips <login> <period>   viewer clips with the VOD they came from (LAST_DAY, LAST_WEEK, LAST_MONTH, ALL_TIME)
  video <id>               VOD metadata, or null when it does not exist
  vods <login>             the channel's newest archive VODs
  hls <m3u8> <start> <end> <out>   saves the HLS chunks that overlap [start, end] (raw bytes, chunk aligned)
  selftest                 asserts the chunk picking
"""
import json
import re
import sys
import urllib.parse
import urllib.request

GQL = 'https://gql.twitch.tv/gql'
CLIENT_ID = 'kimne78kx3ncx6brgo4mv6wki5h1ko'  # Twitch's public web client id; no login needed
TIMEOUT = 30
PERIODS = {'LAST_DAY', 'LAST_WEEK', 'LAST_MONTH', 'ALL_TIME'}


def gql(query):
    request = urllib.request.Request(GQL, json.dumps({'query': query}).encode(), {'Client-Id': CLIENT_ID})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        body = json.load(response)
    if body.get('errors'):
        raise SystemExit('twitch gql error: %s' % json.dumps(body['errors'])[:300])
    return body['data']


def login_of(value):
    if not re.fullmatch(r'\w{2,25}', value):
        raise SystemExit('bad channel login: %r' % value)
    return value


def clips(login, period):
    if period not in PERIODS:
        raise SystemExit('bad period: %r' % period)
    query = 'query{user(login:"%s"){clips(first:100,criteria:{period:%s,sort:VIEWS_DESC}){edges{node{slug title viewCount durationSeconds videoOffsetSeconds video{id}}}}}}' % (login_of(login), period)
    user = gql(query)['user']
    edges = user['clips']['edges'] if user else []
    # A clip whose VOD was deleted has no video; it cannot be placed in a VOD.
    return [{'slug': n['slug'], 'title': n['title'], 'views': n['viewCount'], 'duration': n['durationSeconds'], 'offset': n['videoOffsetSeconds'], 'vod': n['video']['id']}
            for n in (e['node'] for e in edges) if n.get('video') and n.get('videoOffsetSeconds') is not None]


def video(vod):
    if not re.fullmatch(r'\d+', vod):
        raise SystemExit('bad video id: %r' % vod)
    v = gql('query{video(id:"%s"){id title lengthSeconds createdAt owner{login}}}' % vod)['video']
    return v and {'id': v['id'], 'title': v['title'], 'duration': v['lengthSeconds'], 'created': v['createdAt'], 'channel': (v.get('owner') or {}).get('login')}


def vods(login):
    user = gql('query{user(login:"%s"){videos(first:20,type:ARCHIVE,sort:TIME){edges{node{id title lengthSeconds createdAt}}}}}' % login_of(login))['user']
    return [{'id': n['id'], 'title': n['title'], 'duration': n['lengthSeconds'], 'created': n['createdAt']} for n in (e['node'] for e in (user['videos']['edges'] if user else []))]


def pick(playlist, start, end):
    """(init segment URI or None, [segment URIs overlapping [start, end]], real start of the first one, end of the last one)."""
    init = re.search(r'#EXT-X-MAP:URI="([^"]+)"', playlist)
    t, dur, chosen, first, last = 0.0, None, [], None, None
    for line in playlist.splitlines():
        if line.startswith('#EXTINF:'):
            dur = float(line[8:].split(',')[0])
        elif line and not line.startswith('#') and dur is not None:
            if t + dur > start and t < end:
                chosen.append(line)
                first = t if first is None else first
                last = t + dur
            t += dur
            dur = None
    return (init.group(1) if init else None), chosen, first, last


def hls(url, start, end, out):
    if not url.startswith(('https://', 'http://')):
        raise SystemExit('hls needs an http(s) playlist URL')
    get = lambda u: urllib.request.urlopen(urllib.parse.urljoin(url, u), timeout=TIMEOUT).read()
    init, chosen, first, last = pick(get(url).decode(), start, end)
    if not chosen:
        raise SystemExit('no chunk overlaps %s-%s' % (start, end))
    with open(out, 'wb') as f:  # written chunk by chunk: a whole VOD's audio is hundreds of MB
        if init:
            f.write(get(init))
        for uri in chosen:
            f.write(get(uri))
    return {'start': first, 'end': last}


def selftest():
    playlist = '#EXTM3U\n#EXT-X-MAP:URI="init.mp4"\n' + ''.join('#EXTINF:10.000,\n%d.ts\n' % i for i in range(6))
    assert pick(playlist, 25, 41) == ('init.mp4', ['2.ts', '3.ts', '4.ts'], 20.0, 50.0)
    assert pick(playlist, 30, 40)[1:] == (['3.ts'], 30.0, 40.0)  # touching edges do not pull in neighbours
    assert pick(playlist, 0, 1e9)[1:] == (['%d.ts' % i for i in range(6)], 0.0, 60.0)
    assert pick(playlist, 70, 80)[1:] == ([], None, None)
    assert pick('#EXTINF:2.5,\na.ts\n#EXTINF:2.5,\nb.ts\n', 2.5, 3)[0:3] == (None, ['b.ts'], 2.5)
    print('ok')


if __name__ == '__main__':
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else ''), sys.argv[2:]
    if cmd == 'selftest':
        selftest()
    elif cmd == 'clips' and len(args) == 2:
        print(json.dumps(clips(*args)))
    elif cmd == 'video' and len(args) == 1:
        print(json.dumps(video(*args)))
    elif cmd == 'vods' and len(args) == 1:
        print(json.dumps(vods(*args)))
    elif cmd == 'hls' and len(args) == 4:
        print(json.dumps(hls(args[0], float(args[1]), float(args[2]), args[3])))
    else:
        raise SystemExit(__doc__)
