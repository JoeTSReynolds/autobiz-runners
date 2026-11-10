"""Outlet allowlist for casefile: domains whose reporting we may rely on."""
from urllib.parse import urlsplit

ALLOWLIST = ('bbc.co.uk theguardian.com thetimes.co.uk telegraph.co.uk independent.co.uk standard.co.uk sky.com itv.com channel4.com ft.com '
             'reuters.com apnews.com bloomberg.com nytimes.com washingtonpost.com cnn.com nbcnews.com cbsnews.com abcnews.go.com npr.org '
             'theatlantic.com politico.com politico.eu economist.com latimes.com wsj.com variety.com hollywoodreporter.com deadline.com '
             'bbc.com cnbc.com axios.com usatoday.com time.com fortune.com wired.com theverge.com').split()


def domain(url):
    return (urlsplit(url).netloc or url).lower().removeprefix('www.')


def root(dom):
    """The allowlist entry a domain belongs to (news.sky.com -> sky.com), else None."""
    dom = dom.lower().removeprefix('www.')
    return next((a for a in ALLOWLIST if dom == a or dom.endswith('.' + a)), None)


def allowed(dom): return root(dom) is not None


def distinct(domains): return {r for r in map(root, domains) if r}
