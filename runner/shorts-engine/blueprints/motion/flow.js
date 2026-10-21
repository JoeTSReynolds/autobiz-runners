// Items stream along a winding track from a `source` actor into a `sink` actor, one after another, each
// trailing sparks and shrinking into the sink as it arrives (the sink gulps, the source pulses on each launch).
// `item` is an actor shown small, many copies. A `rate` label (e.g. "3.2M / sec", "1,200 per s") pops in on
// `rateAt` and counts up if it starts with a number. On the `burst` word the flow surges: the track turns
// accent, twice the items pour out at twice the speed, the sink pulses and the frame shakes. A `result` line lands under.
// Cast anything: data from phones to a server (item asset packet; source asset phone; sink asset server),
// solar wind into a planet's field (item asset comet, tint accent; source asset sun; sink
// asset planet), customers into a shop (item asset person; sink asset building), shipments to a rocket.
const FL = { sx: 220, sy: 560, kx: 850, ky: 1120, N: 10, X: 10, P: 3.6, A: 1.2, D: "M220 560 C520 520 900 560 840 740 C780 900 280 780 260 940 C240 1080 560 1170 850 1120" };
BP.define("flow", {
  ground: (p) => p.ground || "dark",
  slots: {
    head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
    source: { type: "actor" }, sink: { type: "actor" }, item: { type: "actor" },
    rate: { type: "text", max: 14, opt: true }, rateAt: { type: "anchor", opt: true },
    burst: { type: "anchor", opt: true },
    result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
    ground: { type: "enum", values: ["dark", "light"], opt: true },
  },
  html(p) {
    const it = { ...p.item, name: undefined };
    return `${p.head ? `<div class="pad d fl-head" style="top:120px;font-size:112px">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
      <svg style="position:absolute;left:0;top:0;overflow:visible" width="1080" height="1920"><path class="fl-path" d="${FL.D}" fill="none" stroke="var(--mid)" stroke-width="5" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/><path class="fl-hot" d="${FL.D}" fill="none" stroke="var(--accent)" stroke-width="10" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>
      ${Array.from({ length: FL.N + FL.X }, (_, k) => ACT.html(it, 110, `fl-i fl-i${k}`, 0, 0)).join("")}
      ${ACT.html(p.source, 320, "fl-source", FL.sx, FL.sy)}${ACT.html(p.sink, 320, "fl-sink", FL.kx, FL.ky)}
      <div class="fl-ring" style="position:absolute;left:${FL.kx - 60}px;top:${FL.ky - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></div>
      ${p.rate ? `<div class="pad d fl-rate" style="top:370px;font-size:130px;text-align:right;color:var(--accent-text)"><div class="line"><span>${p.rate}</span></div></div>` : ""}
      ${p.result ? `<div class="pad d fl-result" style="top:1320px;right:340px;font-size:96px;color:var(--accent-text);opacity:0"><div class="line">${p.result}</div></div>` : ""}`;
  },
  animate(c) {
    const { tl, p } = c, ts = c.start + 1.1, tb = p.burst ? Math.max(c.at(p.burst), ts + 1.2) : 1e9, span = c.end - c.start;
    const path = c.q(".fl-path"), len = path.getTotalLength(), cvEl = kit.canvas("#" + c.box.id), ctx = cvEl.getContext("2d");
    const acc = `rgb(${c.L.particles.accent})`, V = 1 + FL.A;
    const ph = (k, t) => (k < FL.N ? (t - ts) / FL.P - k / FL.N + (t > tb ? (FL.A * (t - tb)) / FL.P : 0) : ((t - tb) * V) / FL.P - ((k - FL.N) * 0.9) / FL.X); // raw laps; an item shows once >= 0
    const at = (f) => { const q = path.getPointAtLength(Math.min(1, Math.max(0, f)) * len); return [q.x, q.y]; };
    const els = Array.from({ length: FL.N + FL.X }, (_, k) => c.q(`.fl-i${k}`)), src = c.q(".fl-source .act-v"), snk = c.q(".fl-sink .act-v");
    const frame = (t) => {
      ctx.clearRect(0, 0, 1080, 1920);
      let gulp = 0, emit = 0;
      els.forEach((e, k) => {
        const f = ph(k, t), u = f - Math.floor(f);
        e.style.visibility = f < 0 || (k >= FL.N && t < tb) ? "hidden" : "visible";
        if (f < 0 || (k >= FL.N && t < tb)) return;
        const [x, y] = at(u), s = Math.min(1, u / 0.07) * (1 - Math.max(0, u - 0.93) / 0.07 * 0.9);
        Object.assign(e.style, { left: x - 55 + "px", top: y - 55 + "px", transform: `scale(${s})`, zIndex: 0 });
        if (u > 0.9) gulp = Math.max(gulp, 1 - Math.abs(u - 0.96) / 0.06); if (u < 0.08) emit = Math.max(emit, 1 - u / 0.08);
        for (let j = 1; j <= 7; j++) { // a short spark trail behind each item
          const uj = u - j * 0.014; if (uj < 0) break;
          const [qx, qy] = at(uj), r = 15 - j * 1.6;
          ctx.fillStyle = t > tb ? acc : `rgba(${c.L.particles.dust},${0.7 - j * 0.09})`;
          ctx.globalAlpha = (1 - j / 8) * 0.8; ctx.fillRect(qx - r / 2 + ((k * 7 + j * 13) % 11) - 5, qy - r / 2 + ((k * 5 + j * 17) % 11) - 5, r, r);
        }
      });
      ctx.globalAlpha = 1;
      snk.style.transform = `scale(${1 + 0.05 * Math.max(0, gulp)})`; src.style.transform = `scale(${1 + 0.04 * emit})`;
    };
    c.particles(c.L.particles.ambient, c.start, c.end, { count: 100, seed: 4, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
    if (p.head) c.rise(".fl-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
    tl.fromTo(c.sel(".fl-source"), { scale: 0.5, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.6, ease: "back.out(1.7)" }, c.start + 0.05);
    tl.fromTo(c.sel(".fl-sink"), { scale: 0.5, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.6, ease: "back.out(1.7)" }, c.start + 0.3);
    tl.fromTo(path, { attr: { "stroke-dashoffset": 1 } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.0, ease: "power2.inOut", immediateRender: false }, c.start + 0.4);
    c.sfx(c.start + 0.05, "pop", { step: 0 }); c.sfx(c.start + 0.3, "pop", { step: 2 }); c.sfx(c.start + 0.4, "whoosh", { dur: 1, gain: 0.08 });
    tl.set(cvEl, { visibility: "hidden" }, 0).set(cvEl, { visibility: "visible" }, c.start).set(cvEl, { visibility: "hidden" }, c.end);
    const o = { t: 0 };
    tl.to(o, { t: span, duration: span, ease: "none", onUpdate: () => frame(c.start + o.t) }, c.start);
    const arr = []; // sound: a soft tick as items land, thinned so it never turns to noise
    for (let k = 0; k < FL.N + FL.X; k++) for (let t = ts, last = Math.floor(ph(k, ts)); t < c.end - 0.3; t += 0.02) { const n = Math.floor(ph(k, t)); if (n > last && n >= 1) arr.push(t); last = n; }
    let last = -1, n = 0;
    for (const t of arr.sort((a, b) => a - b)) if (t - last >= 0.22 && n < 28) { c.sfx(t, "blip", { step: [0, 2, 4, 1][n % 4], dur: 0.12, gain: 0.05 }); last = t; n++; }
    if (p.burst) {
      c.sfx(tb - 0.9, "riser", { dur: 0.9, gain: 0.12 }); c.sfx(tb, "impact", { gain: 0.16 }); c.sfx(tb + 0.05, "whoosh-big", { dur: 0.6, gain: 0.14 });
      tl.fromTo(c.sel(".fl-hot"), { attr: { "stroke-dashoffset": 1 } }, { attr: { "stroke-dashoffset": 0 }, duration: 0.7, ease: "power2.in", immediateRender: false }, tb);
      tl.fromTo(c.sel(".fl-ring"), { scale: 0.3, opacity: 1 }, { scale: 6.5, opacity: 0, duration: 0.9, ease: "power3.out", immediateRender: false }, tb);
      tl.fromTo(c.sel(".fl-sink"), { x: 0 }, { keyframes: [-14, 12, -8, 4, 0].map((x) => ({ x, duration: 0.05 })), immediateRender: false }, tb);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-14, 8], [12, -8], [-8, 4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, tb);
      c.particles("burst", tb - 0.05, tb + 1.7, { at: tb, x: FL.kx, y: FL.ky, spread: 3.1, g: 200, count: 110, seed: 61, color: c.L.particles.accent });
      c.particles("sparks", tb, c.end, { count: 40, seed: 63, color: c.L.particles.accent });
    }
    if (p.rate) {
      const tr = p.rateAt ? c.at(p.rateAt) : c.start + 1.8, m = p.rate.match(/^([\d,]*\.?\d+)(.*)$/);
      c.rise(".fl-rate", tr, { ease: "back.out(1.6)" });
      if (m) {
        const dec = (m[1].split(".")[1] || "").length, to = parseFloat(m[1].replace(/,/g, ""));
        c.count(".fl-rate span", 0, to, tr, 1.1, (v) => (m[1].includes(",") ? v.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec }) : v.toFixed(dec)) + m[2]);
      } else c.sfx(tr, "blip", { step: 3 });
    }
    if (p.result) c.rise(".fl-result", p.resultAt ? c.at(p.resultAt) : (p.burst ? tb : ts) + 1.0, { ease: "power4.out" });
    if (p.result) tl.set(c.sel(".fl-result"), { opacity: 1 }, tl.getChildren(false, true, false).filter((x) => x.targets().some((e) => e.closest && e.closest(c.sel(".fl-result")))).reduce((m, x) => Math.min(m, x.startTime()), 1e9)); // text sits hidden (and not hit-tested) until its reveal
  },
});
