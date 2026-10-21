// A big `container` actor fills (or drains) like a tank: an accent copy of it rises inside its own outline with a
// rippling surface line and bubbles, while a huge percentage figure counts with it. `direction` is fill (from
// empty, default) or drain (from full). The level reaches `level` (0..100) exactly on the `at` word, where the
// surface flashes, a ring and a burst go off and the figure pops. Pings keep leaving the container afterwards.
// A `result` line lands under the figure. Asset containers fill in accent; photo and label containers get an
// accent wash clipped to the same rising line.
// Cast anything: a battery charging to 80 percent (asset battery named "Battery"), a storage drive filling up
// (asset database, level 94), a budget draining (asset coin, direction drain, level 12), fuel in a tank or a 10 g
// sample jar (asset jar named "Sample"), a data centre's capacity (asset server).
(() => {
  const CX = 540, CY = 740, S = 520;
  const clamp = (x) => Math.max(0, Math.min(1, x));
  BP.define("fill", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      container: { type: "actor" }, level: { type: "number", min: 0, max: 100 },
      direction: { type: "enum", values: ["fill", "drain"], opt: true },
      at: { type: "anchor" }, // the level lands
      label: { type: "text", max: 12, opt: true },
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      const a = p.container, wash = a.asset ? ACT.html({ ...a, tint: "accent", name: undefined }, S, "fi-ov", CX, CY)
        : `<div class="fi-ov" style="position:absolute;left:${CX - S / 2}px;top:${CY - S / 2}px;width:${S}px;height:${S}px"><div style="position:absolute;inset:${a.image ? 0 : S * 0.12}px 0;background-color:${a.image ? "var(--accent)" : "var(--ink)"};opacity:${a.image ? 0.6 : 0.45};${a.image ? "border-radius:50%" : ""}"></div></div>`;
      return `${p.head ? `<div class="pad d fi-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        ${ACT.html(a, S, "fi-base", CX, CY)}${wash}
        <i class="fi-ring" style="position:absolute;left:${CX - 60}px;top:${CY - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></i>
        <div class="fi-flash" style="position:absolute;left:${CX - S / 2}px;top:${CY - 10}px;width:${S}px;height:20px;background-color:#fff;opacity:0"></div>
        <div class="pad d fi-fig" style="top:1130px;font-size:180px;text-align:center;white-space:nowrap;color:var(--accent-text);z-index:2;opacity:0"><span class="fi-n">${Math.round(p.level)}</span><span style="font-size:96px;margin-left:10px">%</span>${p.label ? `<span style="font-size:60px;margin-left:26px;color:currentColor">${p.label}</span>` : ""}</div>
        ${p.result ? `<div class="pad d fi-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, t = Math.max(c.at(p.at), c.start + 2.2), span = c.end - c.start, drain = p.direction === "drain", f1 = p.level / 100, f0 = drain ? 1 : 0;
      const tr = Math.max(c.start + 0.9, t - 2.8), st = { f: f0 }, ov = c.q(".fi-ov"), nEl = c.q(".fi-n"), cv = kit.canvas("#" + c.box.id), cx = cv.getContext("2d"), acc = c.L.colors.accent, light = p.ground === "light" ? c.L.colors.ink : c.L.colors.light;
      const x0 = CX - S / 2, y0 = CY - S / 2;
      c.box.appendChild(cv); cv.style.zIndex = 1; const nm = c.q(".fi-base .act-name"); if (nm) nm.setAttribute("data-layout-allow-occlusion", ""); // the surface line only brushes the name
      let ph = 0;
      const surf = (x) => (1 - st.f) * S + Math.sin(x * 0.045 + ph * 3) * 7 * Math.min(1, st.f * 8, (1 - st.f) * 8 + 0.3);
      const draw = () => {
        const pts = []; for (let x = 0; x <= S; x += 16) pts.push(`${x}px ${surf(x).toFixed(1)}px`);
        ov.style.clipPath = `polygon(${pts.join(",")},${S}px ${S}px,0 ${S}px)`;
        nEl.textContent = Math.round(st.f * 100);
        cx.clearRect(0, 0, 1080, 1920);
        if (ph > c.start + 0.9 && st.f > 0.02 && st.f < 0.999) { // the surface line and bubbles
          cx.strokeStyle = light; cx.lineWidth = 6; cx.globalAlpha = 0.9; cx.beginPath();
          for (let x = 0; x <= S; x += 16) { const y = surf(x); x ? cx.lineTo(x0 + x, y0 + y) : cx.moveTo(x0 + x, y0 + y); } cx.stroke();
          cx.fillStyle = light;
          for (let i = 0; i < 9; i++) { const u = (ph * 0.5 + i * 0.37) % 1, bx = x0 + 60 + ((i * 197) % 400), by = y0 + S - u * Math.max(0, st.f * S - 10); cx.globalAlpha = 0.6 * (1 - u); cx.fillRect(bx + Math.sin(u * 9 + i) * 10, by, 10 - 4 * u, 10 - 4 * u); }
          cx.globalAlpha = 1;
        }
      };
      draw();
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 181, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".fi-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".fi-base"), { scale: 0.65, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.8, ease: "back.out(1.5)" }, c.start + 0.05);
      tl.fromTo(c.sel(".fi-ov"), { scale: 0.65, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.8, ease: "back.out(1.5)" }, c.start + 0.05);
      tl.fromTo(c.sel(".fi-fig"), { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.6, ease: "power3.out" }, c.start + 0.5);
      c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 });
      tl.fromTo(st, { f: f0 }, { f: f1, duration: t - tr, ease: "power1.inOut", onUpdate: draw, immediateRender: false }, tr);
      c.sfx(tr, "riser", { dur: t - tr, gain: 0.13 });
      for (let k = 0; k < 8; k++) c.sfx(tr + ((t - tr) * k) / 8, "click", { gain: 0.05, f0: drain ? 2600 - k * 250 : 1400 + k * 250 });
      tl.fromTo(c.sel(".fi-ring"), { scale: 0.3, opacity: 1 }, { scale: 7, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, t);
      tl.fromTo(c.sel(".fi-flash"), { opacity: 1, y: (1 - f1) * S - S / 2, scaleX: 1 }, { opacity: 0, scaleX: 1.4, duration: 0.4, ease: "power2.out", immediateRender: false }, t);
      tl.set(c.sel(".fi-flash"), { opacity: 0 }, 0);
      tl.fromTo(c.sel(".fi-fig"), { scale: 1, transformOrigin: "50% 50%" }, { scale: 1.12, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t);
      tl.fromTo(c.sel(".fi-base"), { scale: 1 }, { scale: 1.06, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-12, 6], [10, -6], [-6, 3], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, t);
      c.particles("burst", t - 0.05, t + 1.8, { at: t, x: CX, y: y0 + (1 - f1) * S, spread: 1.6, dir: -Math.PI / 2, g: 500, count: 130, seed: 183, color: c.L.particles.accent });
      c.sfx(t, "impact", { gain: 0.16 }); c.sfx(t + 0.05, "chime", { step: 3, gain: 0.1 });
      for (let u = c.start + 1.2; u < c.end - 0.5; u += 2.4) if (Math.abs(u - t) > 0.7) tl.fromTo(c.sel(".fi-ring"), { scale: 0.3, opacity: 0.5 }, { scale: 4.5, opacity: 0, duration: 1.1, ease: "power3.out", immediateRender: false }, u);
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", data: "ambient", onUpdate: () => { ph = c.start + o.t; draw(); } }, c.start);
      if (p.result) c.rise(".fi-result", p.resultAt ? c.at(p.resultAt) : t + 1.2, { ease: "power4.out" });
    },
  });
})();
