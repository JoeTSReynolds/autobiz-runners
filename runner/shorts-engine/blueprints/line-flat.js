// Follows line-swing: the old swing dims and a steady line is drawn at `level` (0 = top of the swing,
// 1 = bottom), with a big figure and a two-line label.
BP.define("line-flat", {
  ground: "dark",
  slots: {
    big: { type: "text", max: 6 }, bigAt: { type: "anchor" },
    label: { type: "lines", max: 36, lines: 2 }, labelAt: { type: "anchor" },
    dimAt: { type: "anchor" }, drawAt: { type: "anchor" },
    level: { type: "number", min: 0, max: 1 },
  },
  html: (p) => `<div class="pad d lf-big" style="top:150px;font-size:300px;color:var(--accent-text)"><div class="line">${p.big}</div></div>
    <div class="pad t lf-label" style="top:540px">${p.label.map((l) => `<div class="line">${l}</div>`).join("")}</div>
    <svg style="position:absolute;left:72px;top:740px" width="936" height="480" viewBox="0 0 936 480">
      <polyline class="lf-swing" fill="none" stroke="#55534e" stroke-width="10" stroke-linejoin="round" points="${BP.swingPoints()}"/>
      <line class="lf-flat" x1="0" y1="${20 + p.level * 440}" x2="936" y2="${20 + p.level * 440}" stroke="var(--accent)" stroke-width="14" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>`,
  animate(c) {
    const { tl, p } = c;
    c.particles(c.L.particles.ambient, c.start, c.end, { count: 160, seed: 9, vx: -6 });
    c.rise(".lf-label", c.at(p.labelAt));
    tl.to(c.sel(".lf-swing"), { opacity: 0.35, duration: 0.6 }, c.at(p.dimAt));
    tl.to(c.sel(".lf-flat"), { attr: { "stroke-dashoffset": 0 }, duration: 1.6, ease: "power2.out" }, c.at(p.drawAt));
    c.rise(".lf-big", c.at(p.bigAt), { ease: "power4.out" });
    c.sfx(c.at(p.bigAt), "chime", { step: 2 });
  },
});
