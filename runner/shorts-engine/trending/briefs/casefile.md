# Case file

A dramatic, informative explainer of what is reported about the person and why they are in the news, narrated by a documentary voice. Every claim comes from the articles in `articlesText`; nothing else. Attribute allegations and quotes to a named outlet the first time they come up ("the BBC reports", "according to the Guardian"), then let the story flow: do not tag every sentence, and never write "both outlets report". A court's verdict or sentence is a fact: state it plainly. Never state an allegation as fact. If an article reports a denial or response from the person, the script must say it.

- `title`: what happened, as a hook (no "case file").
- `script`: 8 to 14 sentences, 110 to 130 words in total (the video must stay under 57 s). Start with the hook, then the timeline of what was reported, then the denial or response, then where it stands now. You may add ElevenLabs v3 delivery tags in square brackets ([dramatic], [serious], [pause]); they are not spoken or captioned. Each sentence has a `visual`:
  - `{"kind": "screenshot", "outlet": "<outlet>", "highlight": "<4-12 words copied exactly from that outlet's article>"}`
  - `{"kind": "photo", "query": "<Wikimedia Commons search, 2-5 words>"}` (people, places, buildings; never a crowd or protest unless the story is about one)
  - `{"kind": "clip", "source": "<id>", "start": s, "end": e}` (the person on camera, 2 to 4 s, shown muted)
  - `{"kind": "timeline", "label": "<MON YYYY>"}` (lights up the next date on the timeline bar)
  - `{"kind": "quote", "text": "<short quote from an article>", "outlet": "<outlet>"}`
  Use at most 5 screenshots, and never two screenshots in a row. Use at least 4 photo visuals with **different** queries (the person at different times or events, the places, the buildings, the show or company involved), never the same query twice: photos of anyone else are left out, so vary them.
- `footage`: 2 to 4 YouTube searches for real footage of the person in their own work or public appearances (a keynote, a stand-up set, a film scene, an interview): "Jensen Huang GTC keynote", "Russell Brand stand-up". Name the person. Shots where only their face shows play under their photo visuals and long sentences.
- `claims`: every factual claim in the script, each with `support` from at least 2 different outlets: `{"outlet", "quote"}` where `quote` is copied exactly from that outlet's article.
- `timeline`: 2 to 4 dated points `{"label": "DEC 2025", "text": "..."}` in order.
