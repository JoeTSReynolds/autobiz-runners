// One thing slams into another. The `mover` flies in along an arc with a motion trail, cracks appear on
// the `target`, and on the impact word it shatters into flying shards with a shockwave, a flash and a debris
// burst. Optionally something forms from the debris (`after`), and a `result` line lands under it.
// Cast anything: a rock hitting Mars (asset asteroid -> asset planet, tint accent; after: two moons), a
// ransomware attack hitting a hospital (label "Ransomware" -> image of the building), a price cut hitting a
// rival (label -> asset building), a cosmic ray hitting a chip. `shatter` picks what breaks: the target
// (default), the mover (it breaks up against something that holds: a shield, an atmosphere) or both.
const COL = { tx: 540, ty: 900, ts: 600, ms: 270, as: 380 };
const colStart = { left: [-260, 260], right: [1340, 260], top: [540, -300] };
BP.define("collide", {
  ground: (p) => p.ground || "dark",
  slots: {
    head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
    mover: { type: "actor" }, target: { type: "actor" },
    at: { type: "anchor" }, // the impact
    from: { type: "enum", values: ["left", "right", "top"], opt: true },
    shatter: { type: "enum", values: ["target", "mover", "both"], opt: true },
    after: { type: "actor", opt: true }, afterAt: { type: "anchor", opt: true },
    result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
    ground: { type: "enum", values: ["dark", "light"], opt: true },
  },
  html(p) {
    const [sx, sy] = colStart[p.from || "left"];
    return `${p.head ? `<div class="pad d co-head" style="top:120px;font-size:112px">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
      ${ACT.html(p.target, COL.ts, "co-target", COL.tx, COL.ty)}
      ${p.after ? ACT.html(p.after, COL.as, "co-after", COL.tx, COL.ty) : ""}
      ${[3, 2, 1].map((k) => ACT.html({ ...p.mover, name: undefined }, COL.ms, `co-ghost co-ghost${k}`, sx, sy)).join("")}
      ${ACT.html(p.mover, COL.ms, "co-mover", sx, sy)}
      <div class="co-ring" style="position:absolute;left:${COL.tx - 60}px;top:${COL.ty - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></div>
      <div class="co-flash" style="position:absolute;left:${COL.tx - 150}px;top:${COL.ty - 150}px;width:300px;height:300px;border-radius:50%;background-color:#fff;opacity:0"></div>
      ${p.result ? `<div class="pad d co-result" style="top:1250px;font-size:104px;color:var(--accent-text)"><div class="line">${p.result}</div></div>` : ""}`;
  },
  animate(c) {
    const { tl, p } = c, t = c.at(p.at), [sx, sy] = colStart[p.from || "left"], breaks = p.shatter || "target";
    const span = c.end - c.start, dir = [COL.tx - sx, COL.ty - sy], dl = Math.hypot(...dir), ux = dir[0] / dl, uy = dir[1] / dl;
    const hitX = COL.tx - ux * (COL.ts / 2 - 10), hitY = COL.ty - uy * (COL.ts / 2 - 10); // where the mover meets the target's rim
    c.particles(c.L.particles.ambient, c.start, c.end, { count: 120, seed: 5, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
    if (p.head) c.rise(".co-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
    // the target settles in, then breathes and turns slowly
    tl.fromTo(c.sel(".co-target"), { scale: 0.7, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "back.out(1.6)" }, c.start + 0.05);
    tl.fromTo(c.sel(".co-target .act-v"), { rotation: -4 }, { rotation: 4, duration: span, ease: "none", data: "ambient" }, c.start);
    c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 });
    // the mover drifts in from off-frame, then accelerates along a slight arc into the rim, trailed by ghosts
    const fly = Math.min(2.4, Math.max(0.9, t - c.start - 0.5)), go = t - fly;
    const path = (x0, y0) => [{ x: 0, y: 0 }, { x: (hitX - x0) * 0.55, y: (hitY - y0) * 0.55 - 90 }, { x: hitX - x0, y: hitY - y0 }];
    const travel = (sel, lag, alpha, keep = false) => {
      tl.set(c.sel(sel), { autoAlpha: 0 }, 0).set(c.sel(sel), { autoAlpha: alpha }, go + lag);
      const [a, b, e] = path(sx, sy);
      tl.fromTo(c.sel(sel), { x: a.x, y: a.y }, { keyframes: [{ x: b.x, y: b.y, duration: fly * 0.62, ease: "power2.in" }, { x: e.x, y: e.y, duration: fly * 0.38, ease: "none" }], immediateRender: false }, go + lag);
      tl.fromTo(c.sel(sel + " .act-v"), { rotation: 0 }, { rotation: 220, duration: fly, ease: "power1.in", immediateRender: false }, go + lag); // the visual spins, its name stays upright
      if (!keep) tl.set(c.sel(sel), { autoAlpha: 0 }, t);
    };
    travel(".co-mover", 0, 1, breaks !== "target"); // a mover that shatters stays put: its shards live inside it
    tl.set(c.sel(".co-mover .act-name"), { autoAlpha: 0 }, t);
    if (breaks !== "mover") tl.set(c.sel(".co-target .act-name"), { autoAlpha: 0 }, t);
    [[".co-ghost1", 0.05, 0.4], [".co-ghost2", 0.1, 0.22], [".co-ghost3", 0.15, 0.1]].forEach(([s, lag, a]) => travel(s, lag, a));
    c.sfx(go, "riser", { dur: fly, gain: 0.14 });
    // impact: the target (and/or the mover) shatters from the hit point, shockwave ring, white flash, shake, burst
    const local = [(hitX - (COL.tx - COL.ts / 2)) / COL.ts, (hitY - (COL.ty - COL.ts / 2)) / COL.ts];
    if (breaks !== "mover") ACT.shatter(c, ".co-target", t, { ix: local[0], iy: local[1], seed: 17, force: 620, gravity: c.L.id === "space" ? 160 : 520 });
    else tl.fromTo(c.sel(".co-target"), { x: 0 }, { keyframes: [-26, 20, -12, 6, 0].map((x) => ({ x, duration: 0.06 })), immediateRender: false }, t);
    if (breaks !== "target") {
      ACT.shatter(c, ".co-mover", t, { ix: 0.5 + ux * 0.4, iy: 0.5 + uy * 0.4, sectors: 7, seed: 29, force: 380, gravity: c.L.id === "space" ? 120 : 480 });
    }
    tl.fromTo(c.sel(".co-ring"), { scale: 0.2, opacity: 1, x: hitX - COL.tx, y: hitY - COL.ty }, { scale: 7, opacity: 0, duration: 0.9, ease: "power3.out", immediateRender: false }, t);
    tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-22, 10], [18, -12], [-12, 6], [8, -4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, t);
    tl.fromTo(c.sel(".co-flash"), { opacity: 1, scale: 0.15, x: hitX - COL.tx, y: hitY - COL.ty }, { opacity: 0, scale: 1.6, duration: 0.32, ease: "power2.out", immediateRender: false }, t); // a white burst at the hit point
    tl.set(c.sel(".co-flash"), { opacity: 0 }, 0);
    c.particles("burst", t - 0.05, t + 2.2, { at: t, x: hitX, y: hitY, spread: 3.1, dir: Math.atan2(-uy, -ux), g: c.L.id === "space" ? 120 : 600, count: 160, seed: 41, color: c.L.particles.accent });
    c.particles("dust", t, c.end, { count: 70, seed: 43, color: c.L.particles.dust });
    c.sfx(t, "impact"); c.sfx(t + 0.02, "whoosh-big", { dur: 0.6, gain: 0.18 });
    // aftermath: something forms from the debris, then the result line
    if (p.after) {
      const a = p.afterAt ? c.at(p.afterAt) : t + 1.1;
      tl.fromTo(c.sel(".co-after"), { scale: 0.1, autoAlpha: 0, rotation: -40 }, { scale: 1, autoAlpha: 1, rotation: 0, duration: 0.9, ease: "back.out(1.4)", immediateRender: false }, a);
      tl.set(c.sel(".co-after"), { autoAlpha: 0 }, 0);
      c.particles("burst", a - 0.05, a + 1.4, { at: a, x: COL.tx, y: COL.ty, spread: 3.1, g: -60, count: 70, seed: 47, color: c.L.particles.dust });
      c.sfx(a, "chime", { step: 2, gain: 0.08 });
    }
    if (p.result) {
      const r = p.resultAt ? c.at(p.resultAt) : t + 0.6;
      tl.to(c.sel(".co-target .act-name"), { autoAlpha: 0, duration: 0.2 }, r - 0.2); // a surviving target's name sits where the result lands
      c.rise(".co-result", r, { ease: "power4.out" });
    }
  },
});
