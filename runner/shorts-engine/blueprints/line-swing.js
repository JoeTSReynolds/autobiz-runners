// A wild swing between two extremes, drawn along the narration. Optional question first ("Why does it
// matter?"), which clears when the label arrives. Pair with line-flat for "but here it stays steady".
BP.define("line-swing", {
  ground: "dark",
  slots: {
    ask: { type: "lines", max: 12, lines: 2, opt: true },
    label: { type: "text", max: 40 }, labelAt: { type: "anchor" },
    drawAt: { type: "anchor" },
    high: { type: "object", of: { text: { type: "text", max: 8 }, at: { type: "anchor" } } },
    low: { type: "object", of: { text: { type: "text", max: 8 }, at: { type: "anchor" } } },
  },
  html: (p) => `${p.ask ? `<div class="pad d ls-ask" style="top:640px;font-size:150px">${p.ask.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
    <div class="pad d ls-high" style="top:150px;font-size:210px;color:var(--accent-text)">${p.high.text}</div>
    <div class="pad d ls-low" style="top:1090px;font-size:210px">${p.low.text}</div>
    <div class="pad t ls-label" style="top:390px;color:var(--dim, #9a988f)"><div class="line">${p.label}</div></div>
    <svg style="position:absolute;left:72px;top:560px" width="936" height="480" viewBox="0 0 936 480"><polyline class="ls-line" fill="none" stroke="var(--light)" stroke-width="10" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" points="${BP.swingPoints()}"/></svg>`,
  animate(c) {
    const { tl, p } = c, lab = c.at(p.labelAt);
    c.particles(c.L.particles.ambient, c.start, c.end, { count: 160, seed: 9 });
    if (p.ask) {
      c.rise(".ls-ask", c.start + 0.1, { until: lab, ease: "power4.out" });
      tl.to(c.sel(".ls-ask"), { opacity: 0, y: -80, duration: 0.3, ease: "power2.in" }, lab - 0.3);
    }
    c.rise(".ls-label", lab);
    const d = c.at(p.drawAt);
    tl.to(c.sel(".ls-line"), { attr: { "stroke-dashoffset": 0 }, duration: Math.max(0.5, c.end - d), ease: "none" }, d);
    [["high", ".ls-high", 40, 6], ["low", ".ls-low", -40, 0]].forEach(([k, s, y, step]) => {
      const t = c.at(p[k].at);
      tl.fromTo(c.sel(s), { opacity: 0, y }, { opacity: 1, y: 0, duration: 0.5, ease: "expo.out" }, t);
      c.sfx(t, "pop", { step });
    });
  },
});
