// The camera dives from an `outer` actor into a detail inside it and lands on an `inner` actor, optionally diving
// once more into a `deeper` one. `where` is the point on the outer actor (x, y from 0 to 1, top-left is 0,0) the
// camera falls into: a targeting reticle locks on, the outer actor rushes up and away, and the inner actor grows out
// of that spot and lands exactly on the `at` word with a ring, a flash and a burst. For a second dive give
// `deeperWhere` (a point on the inner actor), `deeperAt` and the `deeper` actor. `outerLabel`, `innerLabel` and
// `deeperLabel` (up to 14 chars) are solid tags above the actor that is on screen. A `result` line lands under it.
// Cast anything: phone -> chip -> transistor (outer image of a phone or asset phone, where on its chip, inner asset
// chip, deeper label "Transistor"), planet -> crater -> rock (asset planet tint accent, inner asset moon,
// deeper asset rock), a city -> a data centre -> a server (asset building -> asset server -> asset database).
(() => {
  const CX = 540, CY = 840, SZ = [560, 520, 480], K = 6;
  const clamp = (x) => Math.max(0, Math.min(1, x));
  BP.define("zoom-into", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      outer: { type: "actor" }, where: { type: "point" }, inner: { type: "actor" },
      at: { type: "anchor" }, // landing on the inner actor
      outerLabel: { type: "text", max: 14, opt: true }, innerLabel: { type: "text", max: 14, opt: true },
      deeper: { type: "actor", opt: true }, deeperWhere: { type: "point", opt: true }, deeperAt: { type: "anchor", opt: true }, deeperLabel: { type: "text", max: 14, opt: true },
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    validate(p) { return [!!p.deeper, !!p.deeperWhere, !!p.deeperAt].some(Boolean) && ![!!p.deeper, !!p.deeperWhere, !!p.deeperAt].every(Boolean) ? ["deeper, deeperWhere and deeperAt go together"] : []; },
    html(p) {
      const lv = [p.outer, p.inner, p.deeper].filter(Boolean), lb = [p.outerLabel, p.innerLabel, p.deeperLabel];
      return `${p.head ? `<div class="pad d zi-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        ${lv.map((a, i) => ACT.html(a, SZ[i], `zi-l zi-l${i}`, CX, CY)).reverse().join("")}
        ${lv.map((_, i) => lb[i] ? `<b class="d zi-tag zi-tag${i}" style="position:absolute;left:0;right:0;margin:0 auto;width:max-content;top:${CY - SZ[i] / 2 - 96}px;height:76px;padding:0 26px;display:flex;align-items:center;font-size:54px;white-space:nowrap;background-color:var(--accent);color:var(--ink);opacity:0;z-index:2">${lb[i]}</b>` : "").join("")}
        ${lv.slice(0, -1).map((_, i) => `<div class="zi-ret zi-ret${i}" style="position:absolute;left:0;top:0;width:200px;height:200px;opacity:0;z-index:2">${[[0, 0], [1, 0], [0, 1], [1, 1]].map(([a, b]) => `<i style="position:absolute;${a ? "right" : "left"}:0;${b ? "bottom" : "top"}:0;width:64px;height:64px;border:0 solid var(--accent);border-${b ? "bottom" : "top"}-width:12px;border-${a ? "right" : "left"}-width:12px"></i>`).join("")}</div>`).join("")}
        <i class="zi-ring" style="position:absolute;left:${CX - 60}px;top:${CY - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></i>
        <div class="zi-flash" style="position:absolute;left:${CX - 220}px;top:${CY - 220}px;width:440px;height:440px;border-radius:50%;background-color:#fff;opacity:0"></div>
        ${p.result ? `<div class="pad d zi-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, span = c.end - c.start;
      const lv = [p.outer, p.inner, p.deeper].filter(Boolean), wh = [p.where, p.deeperWhere], at = [c.at(p.at), p.deeperAt ? c.at(p.deeperAt) : 0];
      const D = 1.2, land = [Math.max(at[0], c.start + 2.4), p.deeper ? Math.max(at[1], at[0] + 2.4) : 0];
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 171, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".zi-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".zi-l0"), { scale: 0.65, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.8, ease: "back.out(1.5)" }, c.start + 0.05);
      tl.set(c.sel(".zi-l1"), { autoAlpha: 0 }, 0); if (p.deeper) tl.set(c.sel(".zi-l2"), { autoAlpha: 0 }, 0);
      if (p.outerLabel) tl.fromTo(c.sel(".zi-tag0"), { autoAlpha: 0, y: -30 }, { autoAlpha: 1, y: 0, duration: 0.4, ease: "back.out(2)" }, c.start + 0.6);
      c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 });
      // each dive: reticle locks on, the current actor rushes up and out, the next one grows out of the spot and lands
      lv.slice(0, -1).forEach((_, k) => {
        const T = land[k], a = T - D, s = SZ[k], w = wh[k], px = CX + (w.x - 0.5) * s, py = CY + (w.y - 0.5) * s;
        const L = c.sel(`.zi-l${k}`), N = c.sel(`.zi-l${k + 1}`), R = c.sel(`.zi-ret${k}`);
        tl.set(R, { x: px - 100, y: py - 100 }, 0);
        tl.fromTo(R, { autoAlpha: 0, scale: 3 }, { autoAlpha: 1, scale: 1, duration: 0.6, ease: "power3.out", immediateRender: false }, a - 0.7);
        tl.to(R, { autoAlpha: 0, duration: 0.2 }, a + 0.3);
        tl.to(c.sel(`.zi-l${k} .act-name`), { autoAlpha: 0, duration: 0.2 }, a - 0.1);
        if (lv.length && [p.outerLabel, p.innerLabel, p.deeperLabel][k]) tl.to(c.sel(`.zi-tag${k}`), { autoAlpha: 0, duration: 0.2 }, a - 0.1);
        tl.to(L, { scale: K, x: -(w.x - 0.5) * s, y: -(w.y - 0.5) * s, duration: D, ease: "power3.in", transformOrigin: `${w.x * 100}% ${w.y * 100}%`, immediateRender: false }, a);
        tl.to(L, { autoAlpha: 0, duration: 0.3 }, T - 0.35);
        tl.fromTo(N, { scale: 0.16, autoAlpha: 0, rotation: -14 }, { scale: 1, autoAlpha: 1, rotation: 0, duration: 0.85, ease: "power2.out", immediateRender: false }, T - 0.8);
        tl.fromTo(c.sel(`.zi-l${k + 1}`), { scale: 1 }, { scale: 1.07, duration: 0.15, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, T + 0.05);
        const lab = [p.outerLabel, p.innerLabel, p.deeperLabel][k + 1];
        if (lab) tl.fromTo(c.sel(`.zi-tag${k + 1}`), { autoAlpha: 0, scale: 1.6, rotation: -6 }, { autoAlpha: 1, scale: 1, rotation: 0, duration: 0.35, ease: "back.out(2.4)", immediateRender: false }, T + 0.1);
        tl.fromTo(c.sel(".zi-ring"), { scale: 0.3, opacity: 1 }, { scale: 8, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, T);
        tl.fromTo(c.sel(".zi-flash"), { opacity: 1, scale: 0.2 }, { opacity: 0, scale: 1.7, duration: 0.35, ease: "power2.out", immediateRender: false }, T);
        tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-14, 8], [12, -8], [-7, 4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, T);
        c.particles("burst", T - 0.05, T + 1.8, { at: T, x: CX, y: CY, spread: 3.1, g: 150, count: 130, seed: 173 + k, color: c.L.particles.accent });
        c.sfx(a - 0.7, "blip", { step: 2, dur: 0.3 }); c.sfx(a, "riser", { dur: D, gain: 0.16 }); c.sfx(a, "whoosh-big", { dur: D, gain: 0.14 }); c.sfx(T, "impact"); c.sfx(T + 0.1, "chime", { step: 2 + k * 2, gain: 0.1 });
      });
      tl.set(c.sel(".zi-flash"), { opacity: 0 }, 0);
      // the landed actor breathes; a ring pings every 2.4 s from the first moment (real beats)
      for (let u = c.start + 1.2; u < c.end - 0.5; u += 2.4) tl.fromTo(c.sel(".zi-ring"), { scale: 0.3, opacity: 0.55 }, { scale: 4.5, opacity: 0, duration: 1.1, ease: "power3.out", immediateRender: false }, u);
      const o = { t: 0 }, rot = lv.map((_, i) => c.q(`.zi-l${i} .act-v`));
      tl.to(o, { t: span, duration: span, ease: "none", data: "ambient", onUpdate: () => { const u = c.start + o.t; rot.forEach((e, i) => { if (!(i && u < land[i - 1] + 0.9)) e.style.transform = `translateY(${Math.sin(u * 1.5 + i) * 8}px) rotate(${Math.sin(u * 1.1 + i) * 2}deg)`; else e.style.transform = ""; }); } }, c.start);
      if (p.result) c.rise(".zi-result", p.resultAt ? c.at(p.resultAt) : land[p.deeper ? 1 : 0] + 1.2, { ease: "power4.out" });
    },
  });
})();
