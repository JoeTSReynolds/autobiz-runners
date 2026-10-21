// A real photo filling the frame, a measure line drawn between two points of it, a size label, a place tag.
BP.define("photo-measure", {
  photo: true, // a photo sits behind the caption band
  ground: "dark",
  slots: {
    image: { type: "image" },
    a: { type: "point" }, b: { type: "point" },    // measure ends, in image coordinates
    label: { type: "text", max: 10 }, labelAt: { type: "anchor" },
    place: { type: "lines", max: 18, lines: 2, opt: true }, placeAt: { type: "anchor", opt: true },
  },
  html(p) {
    const m = kit.cover(p.image, 1080, 1920), [ax, ay] = m.px(p.a), [bx, by] = m.px(p.b), y = (ay + by) / 2;
    return `<img class="pm-img" src="assets/${p.image}" style="position:absolute;left:${m.ox}px;top:${m.oy}px;width:${m.iw}px;height:${m.ih}px" />
      <svg style="position:absolute;left:0;top:0" width="1080" height="1920"><g class="pm-line">
        <line x1="${ax}" y1="${y}" x2="${bx}" y2="${y}" stroke="var(--accent)" stroke-width="8"/>
        <line x1="${ax}" y1="${y - 35}" x2="${ax}" y2="${y + 35}" stroke="var(--accent)" stroke-width="8"/>
        <line x1="${bx}" y1="${y - 35}" x2="${bx}" y2="${y + 35}" stroke="var(--accent)" stroke-width="8"/></g></svg>
      <div class="pad d pm-label" style="top:${y + 105}px;font-size:140px;text-align:center"><div class="line">${p.label}</div></div>
      ${p.place ? `<div class="t pm-place" style="position:absolute;top:150px;left:48px;font-size:56px;background-color:var(--dark);padding:24px 28px">${p.place.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}`;
  },
  animate(c) {
    const { tl, p } = c, m = kit.cover(p.image, 1080, 1920), [ax, ay] = m.px(p.a), [bx, by] = m.px(p.b);
    c.particles("dust", c.start, c.end, { count: 60, seed: 5, color: c.L.particles.dust });
    tl.fromTo(c.sel(".pm-img"), { scale: 1.6 }, { scale: 1.05, duration: 1.4, ease: "expo.out" }, c.start);
    tl.to(c.sel(".pm-img"), { scale: 1.0, duration: Math.max(0.1, c.end - c.start - 1.4), ease: "none", data: "ambient" }, c.start + 1.4);
    const l = c.at(p.labelAt);
    tl.fromTo(c.sel(".pm-line"), { scaleX: 0, transformOrigin: `${(ax + bx) / 2}px ${(ay + by) / 2}px` }, { scaleX: 1, duration: 0.6, ease: "expo.out" }, l);
    c.sfx(l, "click"); c.sfx(l + 0.5, "blip", { step: 2 });
    c.rise(".pm-label", l + 0.1);
    if (p.place) {
      const t = c.at(p.placeAt || p.labelAt);
      tl.fromTo(c.sel(".pm-place"), { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: 0.5, ease: "expo.out" }, t - 0.1);
      c.rise(".pm-place", t);
    }
  },
});
