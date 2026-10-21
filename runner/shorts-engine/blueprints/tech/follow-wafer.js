// Outro (tech): the wafer falls in and lights from the centre while "Follow" and a short promise rise.
BP.define("follow-wafer", {
  ground: "light",
  slots: { sub: { type: "text", max: 34 }, followAt: { type: "anchor" } },
  html: (p) => `<div class="pad d fw-follow" style="top:1000px;font-size:330px"><div class="line">Follow</div></div>
    <div class="pad t fw-sub" style="top:1300px"><div class="line">${p.sub}</div></div>
    <svg class="fw-wafer" viewBox="-450 -450 900 900" style="position:absolute;left:90px;top:330px;width:900px;height:900px;visibility:hidden"></svg>`,
  animate(c) {
    const { tl, p } = c, t = c.at(p.followAt), svg = c.sel(".fw-wafer"), wafer = c.L.drawWafer(c.q(".fw-wafer"), 440, 68, 8);
    c.particles(c.L.particles.ambient, c.start, c.end, { count: 30, seed: 4, color: c.L.particles.accent });
    tl.set(svg, { visibility: "visible" }, c.start);
    tl.fromTo(svg, { y: -700, rotation: -90, scale: 0.72 }, { y: -130, rotation: 0, scale: 0.72, duration: 0.8, ease: "expo.out", immediateRender: false }, c.start);
    tl.to(wafer.dies, { attr: { fill: c.L.colors.accent }, duration: 0.03, stagger: { each: 0.012, from: "center" } }, c.start + 0.4);
    c.rise(".fw-follow", t, { ease: "back.out(1.3)" });
    c.rise(".fw-sub", t + 0.1);
    c.sfx(t, "chime", { step: 0 });
  },
});
