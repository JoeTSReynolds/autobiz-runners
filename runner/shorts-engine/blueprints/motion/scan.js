// A large `subject` is swept by a scanning beam (a bright line with sparks flying off it). The beam moves from
// one find to the next and reaches each of the 2..4 `marks` exactly on its word: a pin ringed on the subject
// pulses, a leader line draws and a tag with the mark's `text` snaps in. `where` is the pin on the subject
// ({x, y} 0..1 across it, top-left is 0,0); keep marks at least 0.15 apart in height. After the last find the
// beam runs off the bottom, and a `result` line lands.
// Cast anything: a scanner finding hidden code in a web page (asset document, marks "Hidden text", "Tracker"),
// a probe mapping a surface (image of Mars or asset planet, marks "Ice", "Canyon", "Landing site"), a chip with
// a flaw (asset chip, marks "Defect"), a phone checked for spyware (asset phone).
const SCN = { cx: 540, cy: 820, size: 800 };
BP.define("scan", {
  ground: (p) => p.ground || "dark",
  slots: {
    head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
    subject: { type: "actor" },
    marks: { type: "list", min: 2, max: 4, of: { text: { type: "text", max: 14 }, at: { type: "anchor" }, where: { type: "point" } } },
    result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
    ground: { type: "enum", values: ["dark", "light"], opt: true },
  },
  validate(p) {
    const e = [], m = p.marks || [];
    for (let i = 0; i < m.length; i++) for (let j = i + 1; j < m.length; j++) if (Math.abs(m[i].where?.y - m[j].where?.y) < 0.15) e.push(`marks "${m[i].text}" and "${m[j].text}" sit at nearly the same height; move them at least 0.15 apart in y`);
    return e;
  },
  html(p) {
    const x0 = SCN.cx - SCN.size / 2, y0 = SCN.cy - SCN.size / 2;
    return `${p.head ? `<div class="pad d sn-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
      ${ACT.html({ ...p.subject, name: undefined }, SCN.size, "sn-subject", SCN.cx, SCN.cy)}${p.subject.name ? `<div class="t sn-name" style="position:absolute;left:0;right:0;top:${SCN.cy + SCN.size / 2 + 20}px;text-align:center;z-index:2;opacity:0">${p.subject.name}</div>` : ""}
      <div class="sn-beam" style="position:absolute;left:${x0 - 50}px;top:0;width:${SCN.size + 100}px;height:0;opacity:0"><i style="position:absolute;left:0;right:0;top:-3px;height:6px;background-color:currentColor"></i><i style="position:absolute;left:0;right:0;top:3px;height:14px;background-color:var(--accent)"></i><i style="position:absolute;left:0;top:-22px;width:8px;height:56px;background-color:var(--accent)"></i><i style="position:absolute;right:0;top:-22px;width:8px;height:56px;background-color:var(--accent)"></i></div>
      ${p.marks.map((m, i) => { const px = x0 + m.where.x * SCN.size, py = y0 + m.where.y * SCN.size; return `<div class="sn-m sn-m${i}" style="position:absolute;left:0;top:0;opacity:0;z-index:2">
        <i class="sn-ring" style="position:absolute;left:${px - 26}px;top:${py - 26}px;width:52px;height:52px;border-radius:50%;border:8px solid var(--accent)"></i><i class="sn-dot" style="position:absolute;left:${px - 9}px;top:${py - 9}px;width:18px;height:18px;border-radius:50%;background-color:var(--accent)"></i>
        <i class="sn-lead" style="position:absolute;left:0;top:${py - 2}px;height:4px;background-color:var(--accent)"></i><b class="d sn-tag" style="position:absolute;left:0;top:${py - 38}px;height:76px;padding:0 20px;display:flex;align-items:center;white-space:nowrap;font-size:48px;background-color:var(--accent);color:var(--ink)">${m.text}</b></div>`; }).join("")}
      ${p.result ? `<div class="pad d sn-result" style="top:1318px;font-size:96px;color:var(--accent-text);z-index:2"><div class="line">${p.result}</div></div>` : ""}`;
  },
  animate(c) {
    const { tl, p } = c, x0 = SCN.cx - SCN.size / 2, y0 = SCN.cy - SCN.size / 2;
    const ms = p.marks.map((m, i) => ({ ...m, i, t: c.at(m.at), px: x0 + m.where.x * SCN.size, py: y0 + m.where.y * SCN.size })).sort((a, b) => a.t - b.t);
    const tB = Math.max(c.start + 1.0, ms[0].t - 1.8), tE = Math.min(c.end - 0.2, Math.max(ms.at(-1).t + 1.4, ms.at(-1).t + 0.7));
    const way = [[tB, y0 - 20], ...ms.map((m) => [m.t, m.py]), [tE, y0 + SCN.size + 30]];
    const beamY = (t) => { // eases between finds, so it settles on each one exactly on its word
      if (t <= way[0][0]) return way[0][1];
      for (let i = 1; i < way.length; i++) if (t <= way[i][0]) { const [a, ya] = way[i - 1], [b, yb] = way[i], k = (t - a) / (b - a); return ya + (yb - ya) * (k < 0.5 ? 2 * k * k : 1 - 2 * (1 - k) ** 2) ; }
      return way.at(-1)[1];
    };
    const beam = c.q(".sn-beam"), cvEl = kit.canvas("#" + c.box.id), cv = cvEl.getContext("2d"), hot = c.L.particles.accent;
    c.box.appendChild(cvEl); cvEl.style.zIndex = 1; // sparks and pin bursts draw over the subject
    const frame = (t) => {
      beam.style.top = beamY(t) + "px"; cv.clearRect(0, 0, 1080, 1920);
      ms.forEach((m, k) => { const a = t - m.t; if (a < 0 || a > 0.9) return; for (let j = 0; j < 14; j++) { const an = (j / 14) * 6.283 + k, r = 30 + 170 * a ** 0.6 * (0.6 + (j % 3) * 0.25); cv.globalAlpha = 1 - a / 0.9; cv.fillStyle = `rgb(${hot})`; cv.fillRect(m.px + Math.cos(an) * r, m.py + Math.sin(an) * r, 8 - a * 6, 8 - a * 6); } });
      cv.globalAlpha = 1;
      if (t < tB || t > tE) return;
      for (let k = 0; k < 46; k++) { // sparks leave the beam and drift away from it, fading
        const f = t * 1.6 + k * 0.618, cyc = Math.floor(f), ph = f - cyc, h = ((k * 9301 + cyc * 49297) % 233280) / 233280, e = beamY(t - ph * 0.6);
        cv.globalAlpha = 1 - ph; cv.fillStyle = k % 3 ? `rgb(${hot})` : `rgb(${c.L.particles.dust})`;
        cv.fillRect(x0 - 40 + h * (SCN.size + 80), e - (k % 2 ? 1 : -1) * ph * 90 - 3, 7 - ph * 4, 7 - ph * 4);
      }
      cv.globalAlpha = 1;
    };
    c.particles(c.L.particles.ambient, c.start, c.end, { count: 100, seed: 21, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
    if (p.head) c.rise(".sn-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
    tl.fromTo(c.sel(".sn-subject"), { scale: 0.7, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.8, ease: "back.out(1.5)" }, c.start + 0.05);
    tl.fromTo(c.sel(".sn-subject .act-v"), { rotation: -2 }, { rotation: 2, duration: c.end - c.start, ease: "none", data: "ambient" }, c.start);
    c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 });
    if (p.subject.name) tl.fromTo(c.sel(".sn-name"), { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.4 }, c.start + 0.5);
    const o = { t: 0 };
    tl.to(o, { t: c.end - c.start, duration: c.end - c.start, ease: "none", onUpdate: () => frame(c.start + o.t) }, c.start);
    tl.set(beam, { opacity: 0 }, 0).set(beam, { opacity: 1 }, tB).set(beam, { opacity: 0 }, tE);
    c.sfx(tB, "riser", { dur: ms[0].t - tB, gain: 0.1 }); c.sfx(tB, "whoosh", { f0: 300, f1: 2800, dur: 0.5, gain: 0.1 }); c.sfx(tE - 0.3, "whoosh", { dur: 0.5, gain: 0.08 });
    ms.forEach((m, k) => {
      const M = c.sel(`.sn-m${m.i}`), w = c.q(`.sn-m${m.i} .sn-tag`).offsetWidth, fitR = m.px + 60 + w <= 1056, fitL = m.px - 60 - w >= 24;
      const right = fitR && (m.px >= SCN.cx || !fitL), tx = right ? m.px + 60 : m.px - 60 - w, lx = right ? m.px + 14 : tx + w, lw = right ? tx - lx : m.px - 14 - lx;
      c.q(`.sn-m${m.i} .sn-tag`).style.left = tx + "px";
      Object.assign(c.q(`.sn-m${m.i} .sn-lead`).style, { left: lx + "px", width: lw + "px", transformOrigin: right ? "0 50%" : "100% 50%" });
      tl.set(M, { opacity: 1 }, m.t).set(M, { opacity: 0 }, 0);
      tl.fromTo(c.sel(`.sn-m${m.i} .sn-dot`), { scale: 0 }, { scale: 1, duration: 0.35, ease: "back.out(3)", transformOrigin: "50% 50%" }, m.t);
      tl.fromTo(c.sel(`.sn-m${m.i} .sn-ring`), { scale: 0.4, opacity: 1 }, { scale: 2.6, opacity: 0, duration: 0.8, ease: "power3.out", immediateRender: false, transformOrigin: "50% 50%" }, m.t);
      tl.fromTo(c.sel(`.sn-m${m.i} .sn-lead`), { scaleX: 0 }, { scaleX: 1, duration: 0.3, ease: "power3.out" }, m.t + 0.05);
      tl.fromTo(c.sel(`.sn-m${m.i} .sn-tag`), { clipPath: right ? "inset(0% 100% 0% 0%)" : "inset(0% 0% 0% 100%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 0.35, ease: "power3.out" }, m.t + 0.15);
      c.sfx(m.t, "blip", { step: k + 1, dur: 0.3 }); c.sfx(m.t + 0.15, "click", { f0: 2400, gain: 0.08 });
    });
    const tL = ms.at(-1).t;
    tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-8, 5], [7, -5], [-4, 2], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, tL);
    c.sfx(tL, "impact", { gain: 0.14 }); c.sfx(tL + 0.1, "chime", { step: 3, gain: 0.09 });
    if (p.result) c.rise(".sn-result", p.resultAt ? c.at(p.resultAt) : tL + 0.8, { ease: "power4.out" });
  },
});
