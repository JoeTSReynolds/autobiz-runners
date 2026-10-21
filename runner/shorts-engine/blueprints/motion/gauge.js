// A big half-circle dial with a red zone, a needle and a digital readout (`value` and `unit`), and a `subject`
// actor beside it. The needle climbs from zero, speeding up, and crosses into the red zone exactly on the `at`
// word: the zone flares, the frame shakes, a ring and a burst go off and the subject starts to alarm, then the
// needle settles on `value` (of `max`). `zone` (0.05..0.95, default 0.75) is where the red begins as a share of
// `max`; a value below the zone just ends the climb on `at` without the alarm. A `result` line lands under it.
// Cast anything: a CPU running hot (subject asset chip named "CPU", value 96, max 120, unit "C"), GPU prices
// (subject asset chip, value 2400, max 3000, unit "USD"), a heat shield on re-entry (subject asset capsule,
// value 1650, max 2000, unit "C"), a server room's load (subject asset server, value 92, max 100, unit "%").
(() => {
  const CX = 360, CY = 880, R = 300, SX = 880, SY = 760, SS = 320, TR = 250;
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const ang = (f) => Math.PI * (1 + f), pt = (f, r) => [CX + r * Math.cos(ang(f)), CY + r * Math.sin(ang(f))];
  const arc = (f0, f1, r) => { const a = pt(f0, r), b = pt(f1, r); return `M${a[0].toFixed(1)} ${a[1].toFixed(1)}A${r} ${r} 0 ${f1 - f0 > 0.5 ? 1 : 0} 1 ${b[0].toFixed(1)} ${b[1].toFixed(1)}`; };
  BP.define("gauge", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      subject: { type: "actor" },
      value: { type: "number", min: 0, max: 999999999 }, max: { type: "number", min: 1, max: 999999999 }, unit: { type: "text", max: 8, opt: true },
      zone: { type: "number", min: 0.05, max: 0.95, opt: true },
      at: { type: "anchor" }, // the needle enters the red zone
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    validate(p) { return p.value > p.max ? ["value is above max"] : []; },
    html(p) {
      const zf = p.zone ?? 0.75, dec = (String(p.value).split(".")[1] || "").length, ticks = Array.from({ length: 11 }, (_, i) => { const a = pt(i / 10, R - 62), b = pt(i / 10, R - 38); return `M${a[0].toFixed(1)} ${a[1].toFixed(1)}L${b[0].toFixed(1)} ${b[1].toFixed(1)}`; }).join("");
      return `${p.head ? `<div class="pad d ga-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        <svg style="position:absolute;left:0;top:0;overflow:visible" width="1080" height="1920">
          <path class="ga-track" d="${arc(0, 1, R)}" fill="none" stroke="var(--mid)" stroke-width="46" opacity="0"/>
          <path class="ga-zone" d="${arc(zf, 1, R)}" fill="none" stroke="var(--accent)" stroke-width="46" opacity="0"/>
          <path class="ga-ticks" d="${ticks}" fill="none" stroke="currentColor" stroke-width="6" opacity="0"/>
          <g class="ga-needle" opacity="0"><path d="M${CX - R + 36} ${CY}L${CX} ${CY - 12}L${CX} ${CY + 12}Z" fill="currentColor" transform="translate(-14 0)"/><circle cx="${CX}" cy="${CY}" r="34" fill="currentColor"/><circle cx="${CX}" cy="${CY}" r="14" fill="var(--accent)"/></g>
        </svg>
        <i class="ga-ring" style="position:absolute;left:${CX - 60}px;top:${CY - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></i>
        <i class="ga-alert" style="position:absolute;left:${SX - TR / 2 - 30}px;top:${SY - TR / 2 - 30}px;width:${TR + 60}px;height:${TR + 60}px;border-radius:50%;border:12px solid var(--accent);opacity:0"></i>
        ${ACT.html(p.subject, SS, "ga-subj", SX, SY)}
        <div class="pad d ga-val" style="left:72px;right:auto;width:576px;top:985px;font-size:170px;text-align:center;white-space:nowrap;color:var(--accent-text);z-index:2;opacity:0"><span class="ga-n">${(0).toFixed(dec)}</span>${p.unit ? `<span style="font-size:72px;margin-left:18px;color:currentColor">${p.unit}</span>` : ""}</div>
        ${p.result ? `<div class="pad d ga-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, t = Math.max(c.at(p.at), c.start + 2.2), span = c.end - c.start, zf = p.zone ?? 0.75, vf = p.value / p.max, dec = (String(p.value).split(".")[1] || "").length;
      const tr = Math.max(c.start + 0.9, t - 2.8), st = { f: 0 }, needle = c.q(".ga-needle"), nEl = c.q(".ga-n"), subj = c.q(".ga-subj .act-v"), into = vf >= zf;
      let jit = 0, hot = 0;
      const draw = () => {
        needle.setAttribute("transform", `rotate(${(180 * st.f + jit).toFixed(2)} ${CX} ${CY})`);
        nEl.textContent = (st.f * p.max).toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
      };
      draw();
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 161, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".ga-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".ga-track"), { opacity: 0 }, { opacity: 1, duration: 0.5 }, c.start + 0.1);
      tl.fromTo(c.sel(".ga-zone"), { opacity: 0 }, { opacity: 1, duration: 0.5 }, c.start + 0.3);
      tl.fromTo(c.sel(".ga-ticks"), { opacity: 0 }, { opacity: 0.8, duration: 0.5 }, c.start + 0.3);
      tl.fromTo(c.sel(".ga-needle"), { opacity: 0 }, { opacity: 1, duration: 0.4 }, c.start + 0.5);
      tl.fromTo(c.sel(".ga-subj"), { scale: 0.6, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "back.out(1.6)" }, c.start + 0.3);
      tl.fromTo(c.sel(".ga-val"), { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.5, ease: "power3.out" }, c.start + 0.6);
      c.sfx(c.start + 0.1, "whoosh", { gain: 0.08 }); c.sfx(c.start + 0.3, "pop", { step: 1 });
      // the climb: speeding into the zone on the word, then settling on the value
      if (into) {
        tl.fromTo(st, { f: 0 }, { f: zf, duration: t - tr, ease: "power2.in", onUpdate: draw, immediateRender: false }, tr);
        tl.fromTo(st, { f: zf }, { f: vf, duration: 0.9, ease: "power3.out", onUpdate: draw, immediateRender: false }, t);
      } else tl.fromTo(st, { f: 0 }, { f: vf, duration: t - tr, ease: "power2.out", onUpdate: draw, immediateRender: false }, tr);
      c.sfx(tr, "riser", { dur: t - tr, gain: 0.14 });
      for (let k = 1; k < 8; k++) c.sfx(tr + ((t - tr) * k) / 8, "click", { gain: 0.05, f0: 1400 + k * 260 });
      if (into) {
        tl.fromTo(c.sel(".ga-zone"), { attr: { "stroke-width": 46 } }, { attr: { "stroke-width": 64 }, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t);
        tl.fromTo(c.sel(".ga-ring"), { scale: 0.3, opacity: 1 }, { scale: 7, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, t);
        tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-18, 10], [16, -12], [-10, 6], [6, -3], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, t);
        tl.fromTo(c.sel(".ga-subj"), { scale: 1 }, { scale: 1.12, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t);
        // the alarm: a blinking ring round the subject and a flickering zone, for the rest of the scene
        const n = Math.max(2, Math.floor((c.end - t - 0.9) / 0.5));
        tl.fromTo(c.sel(".ga-alert"), { opacity: 1 }, { opacity: 0.15, duration: 0.25, yoyo: true, repeat: n, ease: "steps(1)", immediateRender: false }, t + 0.6);
        tl.set(c.sel(".ga-alert"), { opacity: 0 }, 0);
        c.particles("burst", t - 0.05, t + 1.8, { at: t, x: pt(zf, R)[0], y: pt(zf, R)[1], spread: 3.1, g: 300, count: 140, seed: 163, color: c.L.particles.accent });
        c.sfx(t, "impact"); c.sfx(t + 0.05, "chime", { step: 1, gain: 0.1 });
      } else { tl.fromTo(c.sel(".ga-ring"), { scale: 0.3, opacity: 1 }, { scale: 7, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, t); c.sfx(t, "chime", { step: 3, gain: 0.12 }); }
      // pings from the hub every 2.4 s keep the scene alive
      for (let u = c.start + 1.4; u < c.end - 0.5; u += 2.4) if (Math.abs(u - t) > 0.6) tl.fromTo(c.sel(".ga-ring"), { scale: 0.3, opacity: 0.6 }, { scale: 4, opacity: 0, duration: 1.1, ease: "power3.out", immediateRender: false }, u);
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", data: "ambient", onUpdate: () => {
        const u = c.start + o.t; jit = u > t + 0.9 ? Math.sin(u * 37) * (into ? 1.2 : 0.4) : 0; hot = into && u > t ? 1 : 0;
        subj.style.transform = hot ? `translate(${Math.sin(u * 47) * 5}px,${Math.cos(u * 41) * 4}px)` : `translateY(${Math.sin(u * 1.5) * 6}px)`;
        draw();
      } }, c.start);
      if (p.result) c.rise(".ga-result", p.resultAt ? c.at(p.resultAt) : t + 1.2, { ease: "power4.out" });
    },
  });
})();
