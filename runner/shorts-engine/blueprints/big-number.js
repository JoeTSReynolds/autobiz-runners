// One huge number counting up from 0 to `to` on its word, with an optional prefix ("$") and suffix ("km", "%")
// in the accent colour, and a context line rising under it. Optional dimmed `image` behind. `hero: true` makes it
// the video's one big moment: a riser through the count, an impact and a burst when it lands. Use for the one
// number the story is about; for comparing numbers use bars, for a share of 100 use dot-grid.
BP.define("big-number", {
  photo: (p) => !!p.image,
  ground: "dark",
  slots: {
    to: { type: "number", min: 0, max: 999999 },
    prefix: { type: "text", max: 4, opt: true }, suffix: { type: "text", max: 4, opt: true },
    at: { type: "anchor" },
    line: { type: "text", max: 24, opt: true }, lineAt: { type: "anchor", opt: true },
    image: { type: "image", opt: true }, focus: { type: "point", opt: true },
    hero: { type: "bool", opt: true },
  },
  html(p) {
    let img = "";
    if (p.image) {
      const m = kit.cover(p.image, 1080, 1920), [fx, fy] = m.px(p.focus || { x: 0.5, y: 0.5 });
      const x = Math.min(0, Math.max(1080 - m.iw, 540 - fx + m.ox)), y = Math.min(0, Math.max(1920 - m.ih, 960 - fy + m.oy));
      img = `<img class="bn-img" src="assets/${p.image}" style="position:absolute;left:${x}px;top:${y}px;width:${m.iw}px;height:${m.ih}px;opacity:0.3;filter:grayscale(1)" />`;
    }
    const acc = (s, k) => (s ? `<span class="bn-${k}" style="color:var(--accent-text)">${s}</span>` : "");
    return `${img}<div class="pad d bn-num" style="top:140px;height:680px;display:flex;align-items:flex-end;font-size:520px;white-space:nowrap"><div class="line">${acc(p.prefix, "pre")}<span class="bn-n">${Math.round(p.to).toLocaleString("en-US")}</span>${acc(p.suffix, "suf")}</div></div>
      <div class="pad d bn-q" style="top:140px;height:680px;display:flex;align-items:flex-end;font-size:520px"><div class="line">???</div></div>
      ${p.line ? `<div class="pad d bn-line" style="top:860px;font-size:104px"><div class="line">${p.line}</div></div>` : ""}`;
  },
  animate(c) {
    const { tl, p } = c, t = c.at(p.at), dur = p.hero ? 2.4 : 1.4, land = t + dur, span = c.end - c.start;
    if (p.image) tl.fromTo(c.sel(".bn-img"), { scale: 1.15 }, { scale: 1, duration: span, ease: "none", data: "ambient" }, c.start);
    else c.particles(c.L.particles.ambient, c.start, c.end, { count: 100, seed: 23, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
    const [num] = c.lines(".bn-num");
    const enter = Math.max(c.start + 0.1, t - 0.35); // the number arrives with its count, never parked at 0
    tl.fromTo(num, { yPercent: 170 }, { yPercent: 0, duration: 0.6, ease: "expo.out" }, enter);
    c.sfx(enter, "whoosh", { gain: 0.08 });
    // a late number: a masked "???" holds its place (and the riser) until the count takes over
    if (enter - c.start > 1) {
      const [q] = c.lines(".bn-q"), o = { p: 0 }, node = c.q(".bn-q .line"), d = enter - c.start - 0.25;
      tl.fromTo(q, { yPercent: 170 }, { yPercent: 0, duration: 0.6, ease: "expo.out" }, c.start + 0.1);
      tl.to(o, { p: 1, duration: d, ease: "none", onUpdate: () => { node.textContent = ["???", "?#?", "%??", "??&", "?!?"][Math.floor(o.p * d * 8) % 5]; } }, c.start + 0.15);
      tl.set(c.sel(".bn-q"), { autoAlpha: 0 }, enter);
      c.sfx(c.start + 0.1, "whoosh", { gain: 0.06 });
    } else tl.set(c.sel(".bn-q"), { autoAlpha: 0 }, 0);
    c.count(".bn-n", 0, Math.round(p.to), t, dur, (v) => Math.round(v).toLocaleString("en-US"));
    tl.fromTo(c.sel(".bn-num"), { scale: 1, transformOrigin: "0% 100%" }, { scale: 1.06, duration: 0.14, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, land);
    if (p.hero) {
      c.hero(land);
      tl.fromTo(c.box, { x: 0 }, { x: 12, duration: 0.05, repeat: 7, yoyo: true, ease: "none", immediateRender: false }, land);
      c.particles("burst", land - 0.1, land + 1.8, { at: land, x: 540, y: 480, spread: 3.2, g: 700, count: 90, seed: 31, color: c.L.particles.accent });
    } else c.sfx(land, "pop", { step: 6 });
    if (p.line) c.rise(".bn-line", p.lineAt ? c.at(p.lineAt) : land + 0.2);
  },
});
