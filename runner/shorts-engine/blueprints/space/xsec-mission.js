// The lane cross-section with a mission arriving: title, the suspected tube, a lander dropping in a dust
// burst, and up to three instruments (radar / seismic / gravity), each on its word with a label.
BP.define("xsec-mission", {
  ground: "light",
  slots: {
    title: { type: "text", max: 10 }, titleAt: { type: "anchor" },
    sub: { type: "text", max: 48, opt: true },
    tubeAt: { type: "anchor" }, landAt: { type: "anchor" },
    instruments: { type: "list", min: 0, max: 3, opt: true, of: { label: { type: "text", max: 12 }, kind: { type: "enum", values: ["radar", "seismic", "gravity"] }, at: { type: "anchor" } } },
  },
  html: (p) => `<div class="pad d xm-title" style="top:140px;font-size:220px"><div class="line">${p.title}</div></div>
    ${p.sub ? `<div class="pad t xm-sub" style="top:380px"><div class="line">${p.sub}</div></div>` : ""}
    <svg class="xm-svg" style="position:absolute;left:0;top:560px" width="1080" height="860" viewBox="0 0 1080 860"></svg>
    ${(p.instruments || []).map((s, i) => `<div class="lbl xm-lbl" style="position:absolute;left:${72 + i * 300}px;top:1330px;opacity:0;color:var(--ink)">${s.label}</div>`).join("")}`,
  animate(c) {
    const { tl, p } = c, svg = c.q(".xm-svg"), xs = LANE.crossSection(svg), el = xs.el, ink = c.L.colors.ink;
    c.rise(".xm-title", c.at(p.titleAt), { ease: "power4.out" });
    if (p.sub) c.rise(".xm-sub", c.at(p.titleAt) + 0.3);
    const tubeT = c.at(p.tubeAt);
    tl.fromTo(xs.tube, { opacity: 0 }, { opacity: 1, duration: 0.4 }, tubeT);
    tl.fromTo(xs.tube, { attr: { "stroke-dashoffset": 0 } }, { attr: { "stroke-dashoffset": -360 }, duration: Math.max(0.1, c.end - tubeT), ease: "none", data: "ambient" }, tubeT);
    const gear = el("g", {});
    el("path", { d: "M640 170 L665 120 L735 120 L760 170 M665 120 L700 70 L735 120", fill: "none", stroke: ink, "stroke-width": 8 }, gear);
    el("rect", { x: 800, y: 132, width: 90, height: 30, fill: ink }, gear);
    el("circle", { cx: 815, cy: 166, r: 10, fill: ink }, gear); el("circle", { cx: 875, cy: 166, r: 10, fill: ink }, gear);
    const drop = c.at(p.landAt), land = drop + 0.55;
    tl.fromTo(gear, { y: -500 }, { y: 0, duration: 0.55, ease: "power3.in" }, drop);
    tl.fromTo(svg, { y: 0 }, { y: 10, duration: 0.05, repeat: 3, yoyo: true, ease: "none" }, land);
    c.particles("burst", drop, land + 1.7, { at: land, x: 760, y: 730, count: 90, seed: 13, color: "120,118,110", spread: 1.1, g: 1400 });
    c.sfx(land, "whoosh", { dur: 0.3, f0: 120, f1: 600, gain: 0.2 }); c.sfx(land, "click", { f0: 300, gain: 0.2 });
    const lbls = c.qa(".xm-lbl");
    (p.instruments || []).forEach((s, i) => {
      const t = c.at(s.at);
      tl.to(lbls[i], { opacity: 1, duration: 0.2 }, t);
      if (s.kind === "radar") {
        const arcs = [0, 1, 2].map((k) => el("path", { d: `M${845 - 60 - k * 70} ${190 + k * 40} Q 845 ${250 + k * 90} ${845 + 60 + k * 70} ${190 + k * 40}`, fill: "none", stroke: ink, "stroke-width": 6, opacity: 0 }));
        arcs.forEach((a, k) => { tl.fromTo(a, { opacity: 0 }, { opacity: 1, duration: 0.15, repeat: 3, yoyo: true }, t + k * 0.12); c.sfx(t + k * 0.12, "blip", { step: k }); });
        tl.to(arcs, { opacity: 1, duration: 0.2 }, t + 1);
      } else if (s.kind === "seismic") {
        const z = el("polyline", { points: "620,230 660,260 640,290 690,320 660,350 720,380 690,410", fill: "none", stroke: ink, "stroke-width": 6, pathLength: 1, "stroke-dasharray": 1, "stroke-dashoffset": 1 });
        tl.to(z, { attr: { "stroke-dashoffset": 0 }, duration: 0.6 }, t); c.sfx(t, "scratch", { dur: 0.6 });
      } else {
        const g = el("path", { d: "M950 200 L950 330 M925 300 L950 335 L975 300", fill: "none", stroke: ink, "stroke-width": 8, opacity: 0 });
        tl.to(g, { opacity: 1, duration: 0.3 }, t); c.sfx(t, "blip", { step: 0, dur: 0.5 });
      }
    });
  },
});
