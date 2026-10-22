# Static catalogue site (JTSR Newsroom) built from published-video entries; stdlib only. Port of newsroom video_catalog.build_catalog_site.
import html, json, re, shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

_UP_RIGHT_ICON = (
    '<svg class="diagonal-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true" focusable="false"><path d="M5 15 15 5M6 5h9v9"/></svg>'
)
_DOWN_RIGHT_ICON = (
    '<svg class="diagonal-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true" focusable="false"><path d="m5 5 10 10M15 6v9H6"/></svg>'
)


def e(value):
    return html.escape(value, quote=True)


def _dt(video):
    return datetime.fromisoformat(video["publishedAt"])


def merge(live: list[dict], own: list[dict]) -> list[dict]:
    return list({v["slug"]: v for v in [*live, *own]}.values())  # own wins


def build(entries: list[dict], target: Path) -> None:
    if target.is_symlink():
        raise ValueError("catalogue output must not be a symlink")
    if target.exists():
        shutil.rmtree(target)
    for v in entries:  # slugs and lanes become folder names
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", v["slug"]) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", v["lane"]):
            raise ValueError(f"catalogue entry has an unsafe slug or lane: {v['slug']!r} {v['lane']!r}")
    videos = sorted(entries, key=lambda v: (v["publishedAt"], v["slug"]), reverse=True)
    (target / "assets").mkdir(parents=True)
    here = Path(__file__).parent
    shutil.copyfile(here / "site_style.css", target / "assets" / "style.css")
    shutil.copyfile(here / "site_catalog.js", target / "assets" / "catalog.js")
    (target / "index.html").write_text(_index_page(videos, None), encoding="utf-8")
    for lane in sorted({v["lane"] for v in videos}):
        (target / "channels" / lane).mkdir(parents=True)
        (target / "channels" / lane / "index.html").write_text(_index_page(videos, lane), encoding="utf-8")
    for v in videos:
        (target / "videos" / v["slug"]).mkdir(parents=True)
        (target / "videos" / v["slug"] / "index.html").write_text(_video_page(v), encoding="utf-8")
    (target / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    (target / "catalog.json").write_text(json.dumps({"videos": videos}, ensure_ascii=False, indent=1), encoding="utf-8")


def _lane_name(lane: str) -> str:
    return lane.replace("_", " ").replace("-", " ").title()


def _youtube_video_url(video_id: str) -> str:
    return f"https://www.youtube.com/shorts/{video_id}"


def _page(title: str, description: str, body: str, *, script: bool = False) -> str:
    script_tag = '<script src="/assets/catalog.js" defer></script>' if script else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#101b1b">
  <meta name="description" content="{e(description)}">
  <title>{e(title)} · JTSR Newsroom</title>
  <link rel="preconnect" href="https://i.ytimg.com">
  <link rel="stylesheet" href="/assets/style.css">
  {script_tag}
</head>
<body>
  <div class="site-shell">
    <header class="site-header">
      <a class="brand" href="/" aria-label="JTSR Newsroom home"><span class="brand-mark">J</span><span class="brand-name">JTSR <em>NEWSROOM</em></span></a>
      <nav aria-label="Main navigation"><a href="/">All stories</a><a href="/#channels">Channels</a></nav>
      <span class="header-note">INDEPENDENT VIDEO JOURNAL</span>
    </header>
    {body}
    <footer class="site-footer"><div class="footer-brand">JTSR <span>NEWSROOM</span></div><p>Curious stories, clearly told. Sources and media credits are listed with each video.</p><a href="/">Back to all stories ↑</a></footer>
  </div>
</body>
</html>"""


def _index_page(videos: list[dict], lane: str | None) -> str:
    selected = tuple(video for video in videos if lane is None or video["lane"] == lane)
    heading = "The stories behind the scroll." if lane is None else f"{_lane_name(lane)} stories."
    eyebrow = (
        "THE JTSR VIDEO ARCHIVE" if lane is None else f"THE {_lane_name(lane).upper()} CHANNEL"
    )
    subtitle = (
        "Discover the latest videos across our channels. Every story has a trail back to its sources."
        if lane is None
        else "Every video, its original reporting, and the people behind the visuals."
    )
    featured = selected[0] if selected else None
    channel_link = (
        f'<a class="channel-hero-link" href="{e(featured["channelUrl"])}" target="_blank" rel="noopener noreferrer">Visit {e(featured["channelName"])} on YouTube <span>{_UP_RIGHT_ICON}</span></a>'
        if lane is not None and featured is not None
        else ""
    )
    feature_html = (
        _featured(featured)
        if featured
        else '<div class="empty-feature">The first story is on its way.<span>Check back soon.</span></div>'
    )
    lanes = sorted({video["lane"] for video in videos})
    chips = (
        '<a class="filter-chip'
        + (" active" if lane is None else "")
        + '" href="/">All channels</a>'
    )
    chips += "".join(
        f'<a class="filter-chip{" active" if item == lane else ""}" href="/channels/{e(item)}/">{e(_lane_name(item))}</a>'
        for item in lanes
    )
    cards = "".join(_card(video, index) for index, video in enumerate(selected))
    if not cards:
        cards = '<p class="empty-list">No public videos yet. New stories will appear here after publication.</p>'
    body = f"""
    <main>
      <section class="hero" aria-labelledby="hero-title">
        <div class="hero-copy"><span class="eyebrow"><span class="pulse"></span>{e(eyebrow)}</span><h1 id="hero-title">{e(heading)}</h1><p>{e(subtitle)}</p><a class="hero-jump" href="#latest">Explore the archive <span>{_DOWN_RIGHT_ICON}</span></a>{channel_link}</div>
        <div class="hero-visual">{feature_html}<div class="hero-orbit orbit-one"></div><div class="hero-orbit orbit-two"></div><span class="hero-index">ISSUE 001 <span>—</span> OPEN ARCHIVE</span></div>
      </section>
      <section class="archive" id="latest" aria-labelledby="archive-title">
        <div class="section-top"><div><span class="section-kicker">FIND YOUR NEXT STORY</span><h2 id="archive-title">Latest dispatches<span class="dot">.</span></h2></div><span class="story-count">{len(selected):02d} STORIES</span></div>
        <div class="archive-tools"><div class="channel-filters" aria-label="Channels">{chips}</div><label class="search-box"><span aria-hidden="true">⌕</span><span class="sr-only">Search videos</span><input id="catalog-search" type="search" placeholder="Search stories" autocomplete="off"></label></div>
        <div class="video-grid" id="video-grid">{cards}</div><p class="empty-list" id="search-empty" hidden>No matching stories. Try another search.</p>
      </section>
      {_channel_section(videos) if lane is None else ""}
      <section class="about-strip"><span class="about-asterisk">✳</span><div><span class="section-kicker">OUR APPROACH</span><h2>Follow the story.<br><em>Find the source.</em></h2></div><p>Every video in this archive comes with its original reporting and media credits. The links live on each story page, ready when you want to look deeper.</p></section>
    </main>"""
    return _page("All stories" if lane is None else _lane_name(lane), subtitle, body, script=True)


def _featured(video: dict) -> str:
    return f'<a class="feature-card" href="/videos/{e(video["slug"])}/"><img src="https://i.ytimg.com/vi/{e(video["videoId"])}/hqdefault.jpg" alt="" fetchpriority="high"><span class="feature-shade"></span><span class="feature-label">LATEST STORY <span>{_UP_RIGHT_ICON}</span></span><strong>{e(video["title"])}</strong><span class="feature-date">{_dt(video):%d %b %Y} · {e(_lane_name(video["lane"]))}</span></a>'


def _channel_section(videos: list[dict]) -> str:
    channels: dict[str, dict] = {}
    for video in videos:
        channels.setdefault(video["lane"], video)
    cards = "".join(
        f'<article class="channel-card"><span class="channel-card-index">CHANNEL {index:02d}</span><h3>{e(_lane_name(lane))}</h3><p>Watch the videos, then follow the reporting and media credits behind each story.</p><div class="channel-card-actions"><a href="/channels/{e(lane)}/">Explore stories <span>→</span></a><a href="{e(video["channelUrl"])}" target="_blank" rel="noopener noreferrer">Visit {e(video["channelName"])} on YouTube <span>{_UP_RIGHT_ICON}</span></a></div></article>'
        for index, (lane, video) in enumerate(sorted(channels.items()), 1)
    )
    if not cards:
        cards = '<p class="empty-list">Channel links will appear here after the first video is published.</p>'
    return f'<section class="channels-section" id="channels" aria-labelledby="channels-title"><div class="section-top"><div><span class="section-kicker">FIND US ON YOUTUBE</span><h2 id="channels-title">Our channels<span class="dot">.</span></h2></div></div><div class="channel-grid">{cards}</div></section>'


def _card(video: dict, index: int) -> str:
    searchable = e(f"{video["title"]} {video["summary"]} {_lane_name(video["lane"])}".lower())
    return f'<article class="video-card" data-search="{searchable}"><a class="card-story" href="/videos/{e(video["slug"])}/" aria-label="Read about {e(video["title"])}"><div class="card-image"><img src="https://i.ytimg.com/vi/{e(video["videoId"])}/hqdefault.jpg" alt="" loading="lazy"><span class="card-number">{index + 1:02d}</span><span class="card-arrow">{_UP_RIGHT_ICON}</span></div><div class="card-meta"><span>{e(_lane_name(video["lane"]))}</span><time datetime="{_dt(video).date()}">{_dt(video):%d %b %Y}</time></div><h3>{e(video["title"])}</h3><p>{e(video["summary"])}</p><span class="card-link">Explore story <span>→</span></span></a><a class="card-youtube" href="{_youtube_video_url(e(video["videoId"]))}" target="_blank" rel="noopener noreferrer" aria-label="Watch {e(video["title"])} on YouTube (opens in a new tab)">Watch on YouTube <span>{_UP_RIGHT_ICON}</span></a></article>'


def _video_page(video: dict) -> str:
    source_items = _links(video["sources"])
    credit_items = _links(video["credits"])
    limitation_items = "".join(
        f'<li><p>{e(item["text"])}</p><div class="limitation-sources">'
        + " ".join(
            f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">{e(urlsplit(url).netloc)} {_UP_RIGHT_ICON}</a>'
            for url in item["sources"]
        )
        + "</div></li>"
        for item in video["limitations"]
    )
    body = f"""
    <main class="story-page"><a class="back-link" href="/channels/{e(video["lane"])}/">← All {e(_lane_name(video["lane"]))} stories</a>
      <div class="story-heading"><div class="story-overline"><span class="pulse"></span>{e(_lane_name(video["lane"]))} / {_dt(video):%d %b %Y}</div><h1>{e(video["title"])}</h1><p>{e(video["summary"])}</p></div>
      <div class="story-layout"><div class="story-main"><div class="player-frame"><iframe src="https://www.youtube-nocookie.com/embed/{e(video["videoId"])}" title="{e(video["title"])}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe></div><a class="watch-link" href="{_youtube_video_url(e(video["videoId"]))}" target="_blank" rel="noopener noreferrer">Watch on YouTube <span>{_UP_RIGHT_ICON}</span></a></div>
      <aside class="story-aside"><p>The original reporting and visual sources behind this video.</p><div class="aside-rule"></div><span class="aside-small">PUBLISHED</span><strong>{_dt(video):%d %B %Y}</strong><span class="aside-small">CHANNEL</span><strong><a class="aside-channel-link" href="{e(video["channelUrl"])}" target="_blank" rel="noopener noreferrer">{e(_lane_name(video["lane"]))} {_UP_RIGHT_ICON}</a></strong></aside></div>
      <div class="references"><section aria-labelledby="sources-title"><span class="section-kicker">01 / THE REPORTING</span><h2 id="sources-title">Sources<span class="dot">.</span></h2>{source_items or '<p class="no-links">No source links were saved for this video.</p>'}</section><section aria-labelledby="credits-title"><span class="section-kicker">02 / THE VISUALS</span><h2 id="credits-title">Media credits<span class="dot">.</span></h2>{credit_items or '<p class="no-links">No external media credits were recorded.</p>'}</section><section class="limitations-section" aria-labelledby="limitations-title"><span class="section-kicker">03 / THE CONTEXT</span><h2 id="limitations-title">Context and limitations<span class="dot">.</span></h2>{f'<ul class="limitations-list">{limitation_items}</ul>' if limitation_items else '<p class="no-links">No limitations were recorded for this video.</p>'}</section></div>
    </main>"""
    return _page(video["title"], video["summary"], body)


def _links(links: list[dict]) -> str:
    links = {link["url"]: link for link in links}.values()  # dedupe by url, order kept
    return "".join(
        f'<a class="reference-link" href="{e(link["url"])}" target="_blank" rel="noopener noreferrer"><span><strong>{e(link["label"])}</strong><small>{e(link["detail"] or urlsplit(link["url"]).netloc)}</small></span><span class="reference-arrow">{_UP_RIGHT_ICON}</span></a>'
        for link in links
    )
