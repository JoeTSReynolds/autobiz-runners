// 2..3 `parts` actors hover apart, charging, then pull together with a magnetic snap: dashed field lines run to the
// centre, sparks and particles converge, crackling arcs jump between the parts, and on the `at` word they slam into
// one `merged` actor (shown big, with a flash ring, a burst and a shake) that keeps pulsing rings afterwards.
// Give every part a `name` (they fade as they close in) and the merged actor a `name`. A `result` line lands under.
// Note: `merged` is the actor that appears; `result` is the text line.
// Cast anything: two firms merging (parts asset building "Acme" + asset building "Globex", tint accent on one;
// merged asset building "AcmeGlobex"), two chips packaged as one (asset chip x2 -> asset chip, tint accent),
// two galaxies merging (asset galaxy x2 -> asset galaxy), three startups becoming a platform (-> asset cloud).
(() => {
  const CX = 540, CY = 800, SLOT = { 2: { s: 300, at: [[200, 800], [880, 800]] }, 3: { s: 270, at: [[230, 580], [850, 580], [540, 1070]] } };
  const clamp = (x) => Math.max(0, Math.min(1, x));
  BP.define("merge", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      parts: { type: "list", min: 2, max: 3, of: { who: { type: "actor" } } },
      merged: { type: "actor" },
      at: { type: "anchor" }, // the snap
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      const g = SLOT[p.parts.length];
      return `${p.head ? `<div class="pad d mg-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        ${ACT.html(p.merged, 540, "mg-res", CX, CY)}
        ${p.parts.map((q, i) => ACT.html(q.who, g.s, `mg-p mg-p${i}`, g.at[i][0], g.at[i][1])).join("")}
        ${[0, 1].map((i) => `<div class="mg-ring mg-ring${i}" style="position:absolute;left:${CX - 60}px;top:${CY - 60}px;width:120px;height:120px;border-radius:50%;border:${i ? 8 : 16}px solid ${i ? "#fff" : "var(--accent)"};opacity:0"></div>`).join("")}
        <div class="mg-flash" style="position:absolute;left:${CX - 200}px;top:${CY - 200}px;width:400px;height:400px;border-radius:50%;background-color:#fff;opacity:0"></div>
        ${p.result ? `<div class="pad d mg-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, t = Math.max(c.at(p.at), c.start + 2.0), span = c.end - c.start, n = p.parts.length, g = SLOT[n], tp = Math.max(c.start + 1.4, t - 1.8);
      const cv = kit.canvas("#" + c.box.id), cx = cv.getContext("2d"), acc = c.L.colors.accent, light = p.ground === "light" ? c.L.colors.ink : c.L.colors.light;
      c.box.appendChild(cv); cv.style.zIndex = 1;
      const ps = c.qa(".mg-p"), res = c.q(".mg-res .act-v"), hot = `rgb(${c.L.particles.accent})`;
      let seed = 91; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
      const sparks = Array.from({ length: 90 }, () => ({ a: rnd() * 6.283, r: 380 + rnd() * 260, off: rnd(), len: 0.5 + rnd() * 0.4 }));
      const where = (i, tt) => { // eased pull: a small backwards wind-up, then an accelerating run into the centre
        const [x, y] = g.at[i], u = clamp((tt - tp) / (t - tp)), k = u < 0.12 ? -0.06 * Math.sin((u / 0.12) * Math.PI) : u ** 2.2;
        const j = tt < tp ? 5 : 3 + 9 * u;
        return [x + (CX - x) * k + Math.sin(tt * 47 + i * 3) * j * (u > 0 || tt >= tp - 0.5 ? 1 : 0.4), y + (CY - y) * k + Math.cos(tt * 39 + i) * j * 0.6, u];
      };
      const frame = (tt) => {
        cx.clearRect(0, 0, 1080, 1920);
        const pull = tt >= tp - 0.4 && tt < t, pts = p.parts.map((_, i) => where(i, tt));
        ps.forEach((e, i) => { Object.assign(e.style, { left: pts[i][0] - g.s / 2 + "px", top: pts[i][1] - g.s / 2 + "px" }); e.firstChild.style.transform = `rotate(${(pts[i][0] < CX ? 1 : -1) * Math.sin(Math.min(1, pts[i][2] * 1.4) * 1.5) * 14}deg)`; });
        if (pull) {
          cx.lineWidth = 6; cx.strokeStyle = acc; cx.setLineDash([22, 18]); cx.lineDashOffset = -tt * 120; cx.globalAlpha = 0.55 * clamp((tt - (tp - 0.4)) / 0.4);
          pts.forEach(([x, y]) => { cx.beginPath(); cx.moveTo(x, y); cx.lineTo(CX, CY); cx.stroke(); });
          cx.setLineDash([]); cx.globalAlpha = 1;
          if (tt > tp + 0.5) { // crackling arcs jump between the parts (new shape every 1/20 s)
            const f = Math.floor(tt * 20); cx.lineWidth = 7; cx.strokeStyle = light;
            for (let i = 0; i < n; i++) { const a = pts[i], b = pts[(i + 1) % n]; if (n === 2 && i) break;
              cx.beginPath(); cx.moveTo(a[0], a[1]);
              for (let s = 1; s < 7; s++) { const h = (((f * 7 + s * 13 + i * 5) * 9301) % 233280) / 233280 - 0.5; cx.lineTo(a[0] + ((b[0] - a[0]) * s) / 7 + h * 60, a[1] + ((b[1] - a[1]) * s) / 7 + h * 60 * (s % 2 ? 1 : -1)); }
              cx.lineTo(b[0], b[1]); cx.stroke(); }
          }
          for (const s of sparks) { // dots rush in from far out and vanish at the centre
            const life = 1.1, age = ((tt - tp + s.off * life) % life) / life, r = s.r * (1 - age) ** 1.6;
            cx.globalAlpha = Math.min(1, age * 5) * (1 - age * 0.3); cx.fillStyle = s.len > 0.7 ? light : hot;
            cx.fillRect(CX + Math.cos(s.a + age * 1.2) * r - 5, CY + Math.sin(s.a + age * 1.2) * r - 5, 10 - age * 5, 10 - age * 5);
          }
          cx.globalAlpha = 1;
        }
        if (tt > t + 0.9) for (let k = 0; k < 2; k++) { // the merged actor keeps pinging
          const age = ((tt - t - 0.9 + k * 0.75) % 1.5) / 1.5; cx.globalAlpha = 0.6 * (1 - age); cx.strokeStyle = acc; cx.lineWidth = 6;
          cx.beginPath(); cx.arc(CX, CY, 290 + 140 * age, 0, 6.283); cx.stroke();
        }
        cx.globalAlpha = 1;
        res.style.transform = tt > t ? `translateY(${Math.sin(tt * 1.6) * 10}px) rotate(${Math.sin(tt * 1.1) * 2.5}deg)` : "";
      };
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 93, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".mg-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      p.parts.forEach((_, i) => {
        tl.fromTo(c.sel(`.mg-p${i}`), { scale: 0.5, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.6, ease: "back.out(1.7)" }, c.start + 0.05 + i * 0.18);
        c.sfx(c.start + 0.05 + i * 0.18, "pop", { step: i * 2 });
        tl.to(c.sel(`.mg-p${i} .act-name`), { autoAlpha: 0, duration: 0.25 }, tp + 0.1);
        tl.set(c.sel(`.mg-p${i}`), { autoAlpha: 0 }, t);
      });
      tl.set(c.sel(".mg-res"), { autoAlpha: 0 }, 0);
      tl.fromTo(c.sel(".mg-res"), { scale: 0.3, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "back.out(2.2)", immediateRender: false }, t);
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", onUpdate: () => frame(c.start + o.t) }, c.start);
      c.sfx(tp - 0.2, "riser", { dur: t - tp + 0.2, gain: 0.16 });
      for (let k = 0; k < 6; k++) c.sfx(tp + ((t - tp) * k) / 6, "click", { gain: 0.06, f0: 1400 + k * 300 });
      tl.fromTo(c.sel(".mg-ring0"), { scale: 0.4, opacity: 1 }, { scale: 8, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, t);
      tl.fromTo(c.sel(".mg-ring1"), { scale: 0.2, opacity: 1 }, { scale: 6, opacity: 0, duration: 0.6, ease: "power2.out", immediateRender: false }, t + 0.08);
      tl.fromTo(c.sel(".mg-flash"), { opacity: 1, scale: 0.3 }, { opacity: 0, scale: 1.8, duration: 0.35, ease: "power2.out", immediateRender: false }, t);
      tl.set(c.sel(".mg-flash"), { opacity: 0 }, 0);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-20, 10], [16, -12], [-10, 6], [6, -3], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, t);
      c.particles("burst", t - 0.05, t + 1.8, { at: t, x: CX, y: CY, spread: 3.1, g: 0, count: 150, seed: 95, color: c.L.particles.accent });
      c.sfx(t, "impact"); c.sfx(t + 0.05, "chime", { step: 3, gain: 0.1 });
      if (p.result) c.rise(".mg-result", p.resultAt ? c.at(p.resultAt) : t + 0.9, { ease: "power4.out" });
    },
  });
})();
