// The open loop closes (hero): the "?" void from tease-void resolves into a base inside the tube, then up
// to three threats fall and stop at the rock, each with a red spark burst and a label.
BP.define("xsec-reveal", {
  ground: "light",
  slots: {
    headline: { type: "lines", max: 12, lines: 2 }, heroAt: { type: "anchor" },
    threats: { type: "list", min: 0, max: 3, opt: true, of: { label: { type: "text", max: 16 }, at: { type: "anchor" } } },
  },
  html: (p) => `<div class="pad d xr-head" style="top:140px;font-size:150px">${p.headline.map((l) => `<div class="line">${l}</div>`).join("")}</div>
    <svg class="xr-svg" style="position:absolute;left:0;top:560px" width="1080" height="860" viewBox="0 0 1080 860"></svg>
    ${(p.threats || []).map((t, i) => `<div class="lbl xr-lbl" style="position:absolute;left:${72 + i * 320}px;top:470px;font-size:36px;opacity:0;color:var(--ink)">${t.label}</div>`).join("")}`,
  animate(c) {
    const { tl, p } = c, svg = c.q(".xr-svg"), xs = LANE.crossSection(svg), el = xs.el, C = c.L.colors;
    tl.set(xs.mystery, { opacity: 1 }, c.start);
    tl.fromTo(xs.q, { scale: 1 }, { scale: 1.15, duration: 0.3, yoyo: true, repeat: 3, transformOrigin: "540px 600px" }, c.start + 0.3);
    const h = c.at(p.heroAt);
    c.hero(h);
    c.rise(".xr-head", h, { stagger: 0.12 });
    const hab = el("g", { opacity: 0 });
    [[90, 590], [250, 588], [410, 580], [570, 566], [730, 548]].forEach(([x, y]) => { el("rect", { x, y, width: 140, height: 70, rx: 35, fill: C.ink }, hab); el("rect", { x: x + 30, y: y + 28, width: 80, height: 12, fill: C.accent }, hab); });
    tl.to(xs.mystery, { opacity: 0, duration: 0.25 }, h - 0.1);
    tl.fromTo(xs.tube, { opacity: 0 }, { opacity: 1, duration: 0.3 }, h - 0.1);
    tl.fromTo(hab, { opacity: 0, x: -300 }, { opacity: 1, x: 0, duration: 0.9, ease: "expo.out" }, h);
    tl.fromTo(svg, { scale: 1.08 }, { scale: 1, duration: 0.6, ease: "expo.out", transformOrigin: "50% 60%" }, h);
    const lbls = c.qa(".xr-lbl");
    (p.threats || []).forEach((th, i) => {
      const t = c.at(th.at), x = 180 + i * 330, g = el("g", { opacity: 0 });
      el("path", { d: `M${x} -20 L${x} 150 M${x - 25} 120 L${x} 152 L${x + 25} 120`, fill: "none", stroke: C.accent, "stroke-width": 8 }, g);
      el("line", { x1: x - 40, y1: 165, x2: x + 40, y2: 165, stroke: C.ink, "stroke-width": 12 }, g);
      tl.fromTo(g, { opacity: 0, y: -200 }, { opacity: 1, y: 0, duration: 0.45, ease: "power4.in" }, t);
      tl.to(lbls[i], { opacity: 1, duration: 0.2 }, t + 0.35);
      c.particles("burst", t, t + 1.8, { at: t + 0.45, x, y: 720, count: 40, seed: 20 + i, color: c.L.particles.accent, spread: 0.8, g: 1200 });
      c.sfx(t + 0.45, "pop", { step: 3 + i });
    });
  },
});
