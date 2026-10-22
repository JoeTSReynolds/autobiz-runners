// One `unit` actor trembles and charges, then on the `at` word it multiplies: about 34 small copies erupt from it
// with a ring and a burst and spread across the frame in a seeded scatter, while a big figure counts up to `count`
// (with `label` after it). With a `target` actor the swarm then converges on it in waves (the target pulses and
// shakes on every hit, `convergeAt` is the word the first wave goes, default 1.8 s after `at`); without one the
// copies bob and twinkle across the sky. A `result` line lands under the figure.
// Cast anything: bots flooding a site (unit asset robot, target asset server, count 2400000, label "requests"),
// Starlink satellites filling the sky (unit asset satellite, count 6000, label "satellites"; target asset planet),
// customers rushing a shop (unit asset person -> target asset building), spores spreading (label "Spore").
(() => {
  const HX = [540, 720, 420], TX = [540, 640, 400], TH = [540, 1090, 300], CZ = 96, P = 3.6;
  const clamp = (x) => Math.max(0, Math.min(1, x)), ease = (u) => 1 - (1 - u) ** 3;
  const slots = (n, ytop, target, seed0) => { // seeded dart-throwing scatter that avoids the target (and its name) and the figure
    let seed = seed0; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647), pts = [];
    for (let tries = 0, md = 128; pts.length < n && tries < 4000; tries++) {
      if (tries % 60 === 59) md *= 0.97;
      const x = 70 + CZ / 2 + rnd() * (940 - CZ), y = ytop + CZ / 2 + rnd() * (1120 - ytop - CZ);
      if (target && x > 270 && x < 810 && y > 400 && y < 960) continue;
      if (!target && Math.hypot(x - HX[0], y - HX[1]) < 150) continue;
      if (pts.every(([a, b]) => Math.hypot(a - x, b - y) > md)) pts.push([x, y]);
    }
    return pts;
  };
  BP.define("swarm", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      unit: { type: "actor" }, count: { type: "number", min: 10, max: 999999999 }, label: { type: "text", max: 12, opt: true },
      at: { type: "anchor" }, // it multiplies
      target: { type: "actor", opt: true }, convergeAt: { type: "anchor", opt: true },
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      const h = p.target ? TH : HX, N = p.target ? 32 : 36;
      return `${p.head ? `<div class="pad d sw-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        ${p.target ? ACT.html(p.target, TX[2], "sw-target", TX[0], TX[1]) : ""}
        ${Array.from({ length: N }, (_, i) => ACT.html({ ...p.unit, name: undefined }, CZ, `act-copy sw-c sw-c${i}`, CZ / 2, CZ / 2)).join("")}
        ${ACT.html(p.unit, h[2], "sw-hero", h[0], h[1])}
        <div class="sw-ring" style="position:absolute;left:${h[0] - 60}px;top:${h[1] - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></div>
        <div class="pad d sw-count" style="top:1140px;z-index:2;font-size:130px;text-align:center;white-space:nowrap;opacity:0"><span class="sw-n" style="color:var(--accent-text)">${p.count.toLocaleString("en-US")}</span><span style="font-size:64px;margin-left:20px">${p.label || ""}</span></div>
        ${p.result ? `<div class="pad d sw-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, t = Math.max(c.at(p.at), c.start + 1.4), span = c.end - c.start, tgt = !!p.target, h = tgt ? TH : HX;
      const tc = tgt ? Math.max(p.convergeAt ? c.at(p.convergeAt) : t + 1.8, t + 1.6) : 1e9, ytop = p.head ? 440 : 340;
      const sl = slots(tgt ? 32 : 36, ytop, tgt, 29), N = sl.length;
      c.qa(".sw-c").forEach((e, i) => { if (i >= N) e.remove(); });
      let seed = 37; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
      const cp = sl.map(([x, y], i) => ({ x, y, dly: Math.hypot(x - h[0], y - h[1]) / 1800, d: rnd() * 2.4, spin: (rnd() - 0.5) * 500, ph: rnd() * 6.283 }));
      const els = cp.map((_, i) => c.q(`.sw-c${i}`)), tv = tgt ? c.q(".sw-target .act-v") : null, hv = c.q(".sw-hero .act-v"), nEl = c.q(".sw-n");
      els.forEach((e) => (e.style.visibility = "hidden"));
      const cv = kit.canvas("#" + c.box.id), cx = cv.getContext("2d"), hot = `rgb(${c.L.particles.accent})`;
      const pos = (i, tt) => { // [x, y, scale, visible] of copy i
        const q = cp[i], a = tt - t - q.dly;
        if (a < 0) return [h[0], h[1], 0, 0];
        const u = clamp(a / 0.9), e = ease(u), bob = u >= 1 ? Math.sin(tt * 2 + q.ph) * 8 : 0;
        let x = h[0] + (q.x - h[0]) * e, y = h[1] + (q.y - h[1]) * e + bob, s = Math.min(1, a / 0.2) * (0.88 + 0.12 * Math.sin(tt * 3 + q.ph));
        if (tgt && tt > tc + q.d) {
          const ph = (tt - tc - q.d) % P;
          if (ph < 0.9) { const w = (ph / 0.9) ** 2.2; x = q.x + (TX[0] - q.x) * w; y = q.y + (TX[1] - q.y) * w; s *= 1 - 0.7 * w; }
          else if (ph < 1.9) return [TX[0], TX[1], 0, 0];
          else if (ph < 2.3) s *= (ph - 1.9) / 0.4;
        }
        return [x, y, s, 1];
      };
      const frame = (tt) => {
        cx.clearRect(0, 0, 1080, 1920);
        const n = Math.min(1, Math.max(0, (tt - t) / 1.4));
        nEl.textContent = (tt >= t + 1.4 ? p.count : Math.max(1, Math.round(p.count * n ** 1.6))).toLocaleString("en-US");
        let pulse = 0;
        cp.forEach((q, i) => {
          const [x, y, s, on] = pos(i, tt), e = els[i];
          e.style.visibility = on && s > 0.02 ? "visible" : "hidden";
          if (!on) return;
          e.style.transform = `translate(${x - CZ / 2}px,${y - CZ / 2}px) rotate(${q.spin * (1 - (1 - clamp((tt - t - q.dly) / 0.9)) ** 2)}deg) scale(${s})`;
        });
        if (tgt && tt > tc) {
          cp.forEach((q) => { const arr = ((tt - tc - q.d) % P) - 0.9; if (tt > tc + q.d && Math.abs(arr) < 0.12) pulse = Math.max(pulse, 1 - Math.abs(arr) / 0.12); });
          cp.forEach((q) => { const arr = ((tt - tc - q.d) % P) - 0.9; if (arr > 0 && arr < 0.3 && tt > tc + q.d) { const a = Math.atan2(q.y - TX[1], q.x - TX[0]); cx.globalAlpha = 1 - arr / 0.3; cx.fillStyle = hot;
            for (let j = 0; j < 4; j++) cx.fillRect(TX[0] + Math.cos(a) * 190 + Math.cos(a + j * 1.57 + 0.4) * arr * 260 - 5, TX[1] + Math.sin(a) * 190 + Math.sin(a + j * 1.57 + 0.4) * arr * 260 - 5, 10, 10); } });
          cx.globalAlpha = 1;
          tv.style.transform = `translate(${Math.sin(tt * 90) * pulse * 8}px,${Math.cos(tt * 70) * pulse * 5}px) scale(${1 + 0.07 * pulse})`;
        }
        if (tt < t) hv.style.transform = `translate(${Math.sin(tt * 60) * 6 * clamp((tt - t + 1.4) / 1.4)}px,0px) scale(${1 + 0.03 * Math.sin(tt * 9)})`;
      };
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 97, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".sw-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      if (tgt) tl.fromTo(c.sel(".sw-target"), { scale: 0.6, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "back.out(1.6)" }, c.start + 0.05);
      tl.fromTo(c.sel(".sw-hero"), { scale: 0.6, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "back.out(1.6)" }, c.start + (tgt ? 0.3 : 0.05));
      c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 });
      if (p.unit.name) tl.to(c.sel(".sw-hero .act-name"), { autoAlpha: 0, duration: 0.2 }, t - 0.25);
      tl.to(c.sel(".sw-hero"), { scale: 0.25, autoAlpha: 0, duration: 0.25, ease: "power2.in", immediateRender: false }, t - 0.02);
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", onUpdate: () => frame(c.start + o.t) }, c.start);
      c.sfx(t - 1.4, "riser", { dur: 1.4, gain: 0.15 });
      tl.fromTo(c.sel(".sw-ring"), { scale: 0.3, opacity: 1 }, { scale: 9, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, t);
      tl.fromTo(c.sel(".sw-count"), { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.5, ease: "power3.out" }, t);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-14, 8], [12, -8], [-7, 4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, t);
      c.particles("burst", t - 0.05, t + 1.8, { at: t, x: h[0], y: h[1], spread: 3.1, g: 0, count: 150, seed: 99, color: c.L.particles.accent });
      c.sfx(t, "impact", { gain: 0.16 }); c.sfx(t + 0.02, "whoosh-big", { dur: 0.8, gain: 0.16 });
      for (let k = 0; k < 6; k++) c.sfx(t + 0.1 + k * 0.2, "pop", { step: k % 5, dur: 0.1, gain: 0.07 });
      if (tgt) {
        c.sfx(tc - 0.4, "riser", { dur: 1.2, gain: 0.12 });
        tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-10, 6], [8, -6], [-5, 3], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, tc + 0.9);
        c.sfx(tc + 0.9, "impact", { gain: 0.12 });
      }
      if (p.result) c.rise(".sw-result", p.resultAt ? c.at(p.resultAt) : (tgt ? tc + 1.6 : t + 1.8), { ease: "power4.out" });
    },
  });
})();
