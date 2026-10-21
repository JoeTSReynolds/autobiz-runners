// A large padlock guards a `subject` actor, set inside corner brackets. With `state: "lock"` (default) the lock
// hangs open, wobbling, and on the `at` word its shackle slams shut with a clunk: a ring, a shake, and the brackets
// snap tight round the subject. With `state: "break"` the lock sits closed and strains (cracks flash, the brackets
// rattle) and on `at` the shackle and body shatter (shards, flash, burst) and the brackets blow apart. Afterwards
// rings keep pulsing from the lock (sealed) or the subject keeps jolting (breached). A `result` line lands under it.
// Cast anything: a data breach (state break; subject asset database named "Customer data"), encryption
// (state lock; subject asset document or laptop), a sealed sample capsule (state lock; subject asset capsule named
// "Sample"), a failed shield on a probe (state break; subject asset satellite), a vault (subject asset coin).
(() => {
  const SUB = [340, 760, 460], BODY = [620, 930, 320, 250], SH = [670, 730, 220, 230], LC = [BODY[0] + BODY[2] / 2, BODY[1] + 60];
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const piece = (cls, [x, y, w, h], svg) => `<div class="act ${cls}" style="position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px"><div class="act-v" style="position:absolute;inset:0"><svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" style="display:block;overflow:visible">${svg}</svg></div></div>`;
  const BR = [[-1, -1], [1, -1], [-1, 1], [1, 1]];
  BP.define("lock", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      subject: { type: "actor" },
      state: { type: "enum", values: ["lock", "break"], opt: true },
      at: { type: "anchor" }, // the clunk or the break
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      const R = SUB[2] / 2 + 24;
      return `${p.head ? `<div class="pad d lc-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        ${ACT.html(p.subject, SUB[2], "lc-subj", SUB[0], SUB[1])}
        ${BR.map(([sx, sy], i) => `<i class="lc-br lc-br${i}" style="position:absolute;left:${SUB[0] + sx * R - (sx < 0 ? 0 : 70)}px;top:${SUB[1] + sy * R - (sy < 0 ? 0 : 70)}px;width:70px;height:70px;opacity:0;border:0 solid var(--accent);border-${sy < 0 ? "top" : "bottom"}-width:12px;border-${sx < 0 ? "left" : "right"}-width:12px"></i>`).join("")}
        ${piece("lc-shackle", SH, `<path d="M30 230V110A80 80 0 0 1 190 110V230" fill="none" stroke="var(--as)" stroke-width="40"/>`)}
        ${piece("lc-body", BODY, `<rect width="320" height="250" fill="var(--af)"/><rect x="240" width="80" height="250" fill="var(--as)"/><rect width="320" height="34" fill="var(--ah)"/><circle cx="160" cy="120" r="32" fill="var(--ab)"/><rect x="146" y="130" width="28" height="68" fill="var(--ab)"/>`)}
        <div class="lc-ring" style="position:absolute;left:${LC[0] - 60}px;top:${LC[1] - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></div>
        <div class="lc-flash" style="position:absolute;left:${LC[0] - 180}px;top:${LC[1] - 180}px;width:360px;height:360px;border-radius:50%;background-color:#fff;opacity:0"></div>
        ${p.result ? `<div class="pad d lc-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, t = Math.max(c.at(p.at), c.start + 1.6), span = c.end - c.start, brk = p.state === "break";
      const cv = kit.canvas("#" + c.box.id), cx = cv.getContext("2d"), acc = c.L.colors.accent;
      c.box.appendChild(cv); cv.style.zIndex = 1;
      const sv = c.q(".lc-shackle .act-v"), bv = c.q(".lc-body .act-v"), subj = c.q(".lc-subj .act-v");
      const open = { y: -64, rotation: -26 };
      if (!brk) tl.set(c.sel(".lc-shackle"), { ...open, transformOrigin: "30px 230px" }, 0);
      const frame = (tt) => {
        cx.clearRect(0, 0, 1080, 1920);
        const k = brk ? clamp((tt - (t - 1.5)) / 1.5) : 0, j = brk ? (tt < t ? 2 + 7 * k : 0) : 0;
        if (brk) { // the lock strains before it gives
          bv.style.transform = tt < t ? `translate(${Math.sin(tt * 57) * j}px,${Math.cos(tt * 43) * j * 0.6}px)` : "";
          sv.style.transform = tt < t ? `translate(${Math.sin(tt * 51 + 1) * j}px,${Math.cos(tt * 47) * j * 0.6}px)` : "";
        } else if (tt < t) sv.style.transform = `translate(${Math.sin(tt * 3) * 5}px,${Math.cos(tt * 4.5) * 7}px) rotate(${Math.sin(tt * 3.4) * 3}deg)`;
        else sv.style.transform = "";
        if (tt > t + 0.8) for (let q = 0; q < 2; q++) { // sealed: rings keep leaving the lock; breached: the subject keeps getting hit
          const age = ((tt - t - 0.8 + q * 0.75) % 1.5) / 1.5; cx.globalAlpha = 0.6 * (1 - age); cx.strokeStyle = acc; cx.lineWidth = 6;
          cx.beginPath(); cx.arc(brk ? SUB[0] : LC[0], brk ? SUB[1] : LC[1], (brk ? 280 : 160) + 150 * age, 0, 6.283); cx.stroke();
        }
        cx.globalAlpha = 1;
        subj.style.transform = brk && tt > t + 0.4 ? `translate(${Math.sin(tt * 3.1) * 6}px,${Math.cos(tt * 2.3) * 8}px) rotate(${Math.sin(tt * 1.9) * 2.5}deg)` : "";
      };
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 111, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".lc-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".lc-subj"), { scale: 0.6, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.8, ease: "back.out(1.5)" }, c.start + 0.05);
      tl.fromTo(c.sel(".lc-shackle"), { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.4 }, c.start + 0.3);
      tl.fromTo(c.sel(".lc-body"), { autoAlpha: 0, y: 70 }, { autoAlpha: 1, y: 0, duration: 0.6, ease: "back.out(1.7)" }, c.start + 0.3);
      c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 }); c.sfx(c.start + 0.3, "pop", { step: 1 });
      if (brk) c.qa(".lc-br").forEach((_, i) => { // the brackets frame the subject from the start, then rattle harder and harder
        tl.fromTo(c.sel(`.lc-br${i}`), { opacity: 0, scale: 1.3 }, { opacity: 1, scale: 1, duration: 0.4, ease: "back.out(2)" }, c.start + 0.5);
        const n = 12, T0 = t - 1.5; tl.fromTo(c.sel(`.lc-br${i}`), { x: 0, y: 0 }, { keyframes: Array.from({ length: n }, (_, k) => ({ x: (k % 2 ? 1 : -1) * (2 + k) * (i % 2 ? 0.8 : 1), y: (k % 3 - 1) * (1 + k * 0.6), duration: 1.5 / n, ease: "steps(1)" })), immediateRender: false }, T0);
      });
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", onUpdate: () => frame(c.start + o.t) }, c.start);
      if (brk) {
        ACT.shatter(c, ".lc-shackle", t, { ix: 0.5, iy: 0.2, sectors: 6, seed: 5, force: 620, dur: 1.4, gravity: c.L.id === "space" ? 160 : 560 });
        ACT.shatter(c, ".lc-body", t, { ix: 0.5, iy: 0.3, sectors: 8, seed: 9, force: 480, dur: 1.4, gravity: c.L.id === "space" ? 160 : 560 });
        c.qa(".lc-br").forEach((_, i) => { const [sx, sy] = BR[i]; tl.to(c.sel(`.lc-br${i}`), { x: sx * 220, y: sy * 220, opacity: 0, duration: 0.5, ease: "power3.out", immediateRender: false }, t); });
        tl.fromTo(c.sel(".lc-subj"), { scale: 1 }, { scale: 1.14, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t);
        c.sfx(t - 1.5, "riser", { dur: 1.5, gain: 0.15 }); c.sfx(t, "impact"); c.sfx(t + 0.02, "whoosh-big", { dur: 0.6, gain: 0.16 });
        c.particles("burst", t - 0.05, t + 2, { at: t, x: LC[0], y: LC[1] + 60, spread: 3.1, g: c.L.id === "space" ? 120 : 600, count: 170, seed: 113, color: c.L.particles.accent });
      } else {
        tl.fromTo(c.sel(".lc-shackle"), { ...open }, { y: 0, rotation: 0, duration: 0.18, ease: "power4.in", transformOrigin: "30px 230px", immediateRender: false }, t - 0.18);
        tl.fromTo(c.sel(".lc-body"), { y: 0 }, { keyframes: [14, -8, 5, 0].map((y) => ({ y, duration: 0.06 })), immediateRender: false }, t);
        c.qa(".lc-br").forEach((_, i) => { const [sx, sy] = BR[i]; tl.fromTo(c.sel(`.lc-br${i}`), { opacity: 0, x: sx * 160, y: sy * 160 }, { opacity: 1, x: 0, y: 0, duration: 0.3, ease: "power4.in", immediateRender: false }, t - 0.2); });
        tl.fromTo(c.sel(".lc-subj"), { scale: 1 }, { scale: 0.93, duration: 0.15, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t);
        c.sfx(t - 1.2, "riser", { dur: 1.2, gain: 0.1 }); c.sfx(t - 0.05, "click", { f0: 900, gain: 0.2 }); c.sfx(t, "impact", { gain: 0.2 }); c.sfx(t + 0.05, "chime", { step: 3, gain: 0.1 });
        c.particles("burst", t - 0.05, t + 1.4, { at: t, x: LC[0], y: LC[1] + 40, spread: 3.1, g: 300, count: 80, seed: 115, color: c.L.particles.dust });
      }
      tl.fromTo(c.sel(".lc-ring"), { scale: 0.3, opacity: 1 }, { scale: 7, opacity: 0, duration: 0.9, ease: "power3.out", immediateRender: false }, t);
      tl.fromTo(c.sel(".lc-flash"), { opacity: 1, scale: 0.2 }, { opacity: 0, scale: 1.6, duration: 0.3, ease: "power2.out", immediateRender: false }, t);
      tl.set(c.sel(".lc-flash"), { opacity: 0 }, 0);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-16, 10], [14, -10], [-8, 5], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, t);
      if (p.result) c.rise(".lc-result", p.resultAt ? c.at(p.resultAt) : t + 1.0, { ease: "power4.out" });
    },
  });
})();
