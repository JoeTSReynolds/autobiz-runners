// A `defender` actor sits inside a honeycomb shield. Copies of the `attacker` actor fly in from off-frame, one every
// 0.6 s from the `at` word on, and each bounces off the shield with a ripple of lit cells running out from the
// hit, sparks and a small shake. `volley` (3..10, default 6) hits come in a fast run, then a slower trickle keeps
// the scene alive. With a `breach` word (at least 1.5 s after `at`) the shield fails on it: one attacker punches
// through, the cells scatter, the defender is hit and alarms. Without `breach` the shield holds. A `result` line
// lands under it. Give the defender a `name`; the attacker's copies show without one.
// Cast anything: a firewall blocking an attack (attacker asset virus, defender asset server named "Server"),
// Earth's magnetic field deflecting solar particles (attacker asset sun tint accent or asset comet, defender asset
// planet named "Earth"), antivirus on a phone (asset virus -> asset phone), a probe's shield against dust.
(() => {
  const DX = 540, DY = 900, DS = 440, SR = 370, PZ = 180, HR = 46;
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const cells = [];
  for (let r = -12; r <= 12; r++) for (let q = -8; q <= 8; q++) {
    const x = DX + (q + (r & 1 ? 0.5 : 0)) * HR * 1.732, y = DY + r * HR * 1.5;
    if (Math.hypot(x - DX, y - DY) <= SR - 26) cells.push([x, y]);
  }
  BP.define("shield", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      attacker: { type: "actor" }, defender: { type: "actor" },
      at: { type: "anchor" }, // the first hit
      volley: { type: "number", min: 3, max: 10, opt: true },
      breach: { type: "anchor", opt: true },
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      return `${p.head ? `<div class="pad d sh-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        ${ACT.html(p.defender, DS, "sh-def", DX, DY)}
        ${Array.from({ length: 15 }, () => ACT.html({ ...p.attacker, name: undefined }, PZ, "act-copy sh-p", PZ / 2, PZ / 2)).join("")}
        <i class="sh-ring" style="position:absolute;left:${DX - 60}px;top:${DY - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></i>
        <div class="sh-flash" style="position:absolute;left:${DX - 240}px;top:${DY - 240}px;width:480px;height:480px;border-radius:50%;background-color:#fff;opacity:0"></div>
        ${p.result ? `<div class="pad d sh-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, t0 = Math.max(c.at(p.at), c.start + 1.6), span = c.end - c.start, volley = p.volley || 6, tb = p.breach ? Math.max(c.at(p.breach), t0 + 1.5) : 0;
      let seed = 53; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
      const hits = []; // time, angle of each bounce
      for (let k = 0; k < 14; k++) { const t = t0 + (k < volley ? k * 0.6 : volley * 0.6 + (k - volley) * 1.0); if (t > c.end - 0.9 || (tb && t > tb - 0.9)) break; hits.push({ t, a: -Math.PI + (0.12 + rnd() * 0.76) * Math.PI }); }
      const els = [...c.qa(".sh-p")]; els.forEach((e, i) => { if (i >= hits.length + (tb ? 1 : 0)) e.remove(); });
      const cv = kit.canvas("#" + c.box.id), cx = cv.getContext("2d"), acc = c.L.colors.accent, light = p.ground === "light" ? c.L.colors.ink : c.L.colors.light;
      const rim = (a, r = SR) => [DX + Math.cos(a) * r, DY + Math.sin(a) * r], seeds = cells.map((_, i) => ((i * 7919) % 100) / 100);
      const hex = (x, y, r) => { cx.beginPath(); for (let i = 0; i < 6; i++) { const a = Math.PI / 6 + (i * Math.PI) / 3; i ? cx.lineTo(x + r * Math.cos(a), y + r * Math.sin(a)) : cx.moveTo(x + r * Math.cos(a), y + r * Math.sin(a)); } cx.closePath(); };
      const frame = (tt) => {
        cx.clearRect(0, 0, 1080, 1920);
        const born = clamp((tt - (c.start + 0.3)) / 0.9), gone = tb ? clamp((tt - tb) / 0.7) : 0;
        if (gone >= 1 || born <= 0) return;
        cells.forEach(([x, y], i) => {
          const d0 = Math.hypot(x - DX, y - DY); if (d0 / SR > born * 1.05) return;
          let glow = 0;
          for (const h of hits) { const age = tt - h.t; if (age < 0 || age > 1.2) continue; const [hx, hy] = rim(h.a), d = Math.hypot(x - hx, y - hy); glow += Math.exp(-(((d - age * 900) / 80) ** 2)) * (1 - age / 1.2) + (d < 110 ? Math.max(0, 1 - age / 0.35) : 0); }
          const fall = gone * (60 + seeds[i] * 380), ang = Math.atan2(y - DY, x - DX), a = clamp(0.16 + glow * 0.9) * (1 - gone);
          cx.globalAlpha = a; cx.fillStyle = acc; hex(x + Math.cos(ang) * fall, y + Math.sin(ang) * fall + gone * gone * 300, HR - 3 - gone * 8); cx.fill();
          cx.globalAlpha = Math.min(1, a + 0.35) * (1 - gone); cx.strokeStyle = glow > 0.3 ? light : acc; cx.lineWidth = 4; hex(x + Math.cos(ang) * fall, y + Math.sin(ang) * fall + gone * gone * 300, HR - 3 - gone * 8); cx.stroke();
        });
        cx.globalAlpha = 0.8 * (1 - gone); cx.strokeStyle = acc; cx.lineWidth = 8; cx.beginPath(); cx.arc(DX, DY, SR * born, 0, 6.283); cx.stroke();
        for (const h of hits) { const age = tt - h.t; if (age < 0 || age > 0.7) continue; const [hx, hy] = rim(h.a); cx.globalAlpha = 1 - age / 0.7; cx.fillStyle = light; // sparks off the hit
          for (let j = 0; j < 10; j++) { const an = h.a + (j / 10 - 0.5) * 2.2, r = 20 + age * (260 + (j % 3) * 90); cx.fillRect(hx + Math.cos(an) * r - 5, hy + Math.sin(an) * r + age * age * 160 - 5, 10 - age * 8, 10 - age * 8); } }
        cx.globalAlpha = 1;
      };
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 191, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".sh-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".sh-def"), { scale: 0.65, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.8, ease: "back.out(1.5)" }, c.start + 0.05);
      c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 }); c.sfx(c.start + 0.4, "riser", { dur: 0.9, gain: 0.08 });
      const px = (X) => X - PZ / 2;
      hits.forEach((h, k) => { // each attacker flies in from off-frame, bounces off the rim, spins away
        const [hx, hy] = rim(h.a, SR + PZ / 2 - 10), [sx, sy] = rim(h.a, 1250), [ex, ey] = rim(h.a, SR + 380);
        const el = els[k]; tl.set(el, { autoAlpha: 0 }, 0);
        tl.fromTo(el, { x: px(sx), y: sy - PZ / 2, autoAlpha: 1, rotation: 0, scale: 1 }, { x: px(hx), y: hy - PZ / 2, rotation: 200, duration: 0.5, ease: "power2.in", immediateRender: false }, h.t - 0.5);
        tl.to(el, { x: px(ex), y: ey - PZ / 2 + 80, rotation: 640, scale: 0.7, autoAlpha: 0, duration: 0.55, ease: "power2.out", immediateRender: false }, h.t);
        tl.fromTo(c.sel(".sh-def"), { scale: 1 }, { scale: 0.975, duration: 0.07, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, h.t);
        tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-5, 3], [4, -3], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.04 })), immediateRender: false }, h.t);
        c.sfx(h.t - 0.5, "whoosh", { dur: 0.4, f0: 600, f1: 2200, gain: 0.07 }); c.sfx(h.t, k % 2 ? "blip" : "click", { step: k % 5, dur: 0.2, gain: 0.12, f0: 1200 + (k % 4) * 200 }); c.sfx(h.t + 0.02, "impact", { dur: 0.4, gain: 0.07 });
      });
      if (tb) { // the breach: one attacker goes straight through, the shield scatters, the defender is hit
        const el = els[hits.length], a = -Math.PI / 2 + 0.5, [sx, sy] = rim(a, 1250);
        tl.set(el, { autoAlpha: 0 }, 0);
        tl.fromTo(el, { x: px(sx), y: sy - PZ / 2, autoAlpha: 1, rotation: 0, scale: 1.2 }, { x: px(DX), y: DY - PZ / 2, rotation: 260, duration: 0.55, ease: "power2.in", immediateRender: false }, tb - 0.55);
        tl.set(el, { autoAlpha: 0 }, tb);
        tl.fromTo(c.sel(".sh-ring"), { scale: 0.3, opacity: 1 }, { scale: 8, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, tb);
        tl.fromTo(c.sel(".sh-flash"), { opacity: 1, scale: 0.2 }, { opacity: 0, scale: 1.7, duration: 0.35, ease: "power2.out", immediateRender: false }, tb);
        tl.fromTo(c.sel(".sh-def"), { scale: 1 }, { scale: 1.1, duration: 0.14, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, tb);
        tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-22, 12], [18, -14], [-12, 8], [8, -4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, tb);
        const n = Math.max(2, Math.floor((c.end - tb - 0.9) / 0.5)); // the defender alarms for the rest of the scene
        tl.fromTo(c.sel(".sh-def .act-v"), { opacity: 1 }, { opacity: 0.45, duration: 0.25, yoyo: true, repeat: n, ease: "steps(1)", immediateRender: false }, tb + 0.6);
        c.particles("burst", tb - 0.05, tb + 2, { at: tb, x: DX, y: DY, spread: 3.1, g: 300, count: 170, seed: 193, color: c.L.particles.accent });
        c.sfx(tb - 0.55, "riser", { dur: 0.55, gain: 0.16 }); c.sfx(tb, "impact"); c.sfx(tb + 0.02, "scratch", { dur: 0.8, gain: 0.16 }); c.sfx(tb + 0.05, "whoosh-big", { dur: 0.7, gain: 0.16 });
      }
      tl.set(c.sel(".sh-flash"), { opacity: 0 }, 0);
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", data: "ambient", onUpdate: () => frame(c.start + o.t) }, c.start);
      // a ring pings from the defender every 2.4 s between the hits' beats
      for (let u = c.start + 1.2; u < c.end - 0.5; u += 2.4) if (!hits.some((h) => Math.abs(h.t - u) < 0.5) && !(tb && Math.abs(tb - u) < 0.6)) tl.fromTo(c.sel(".sh-ring"), { scale: 0.3, opacity: 0.4 }, { scale: 3.6, opacity: 0, duration: 1.1, ease: "power3.out", immediateRender: false }, u);
      if (p.result) c.rise(".sh-result", p.resultAt ? c.at(p.resultAt) : (tb || hits.at(-1).t) + 1.2, { ease: "power4.out" });
    },
  });
})();
