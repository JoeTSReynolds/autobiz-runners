// Waves leave a `sender` actor one after another and travel across the gap to a far `receiver` actor, which sits
// dimmed. A big `delay` timer counts up while the first wave is in flight (if it starts with a number, e.g.
// "20 min"; otherwise the text just appears) and a bar under it fills. On the `at` word the first wave lands and
// the receiver lights up: rays, a ring, a flash and a shake. Waves keep flowing afterwards. `sendAt` (optional) is
// the word the first wave leaves on. A `result` line lands under the bar.
// Cast anything: a Mars rover talking to Earth (sender asset rover named "Rover", receiver asset planet named
// "Earth", delay "20 min"), 5G latency (sender asset phone, receiver asset server, delay "10 ms"), a probe at the
// edge of the solar system (sender asset satellite, receiver asset telescope, delay "22 hours"), a trader far from
// the exchange (sender asset person -> asset building).
(() => {
  const SX = 200, SY = 790, SS = 280, RX = 880, RS = 320, R0 = 150, GAP = RX - RS / 2 - SX, PER = 0.55;
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const parse = (s) => { const m = /^(\d[\d,.]*)\s*(.*)$/.exec(s); return m ? { v: parseFloat(m[1].replace(/,/g, "")), dec: (m[1].split(".")[1] || "").length, grp: m[1].includes(","), unit: m[2], num: m[1] } : null; };
  BP.define("signal-delay", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      sender: { type: "actor" }, receiver: { type: "actor" },
      delay: { type: "text", max: 12 },
      at: { type: "anchor" }, // the first wave arrives
      sendAt: { type: "anchor", opt: true },
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      const d = parse(p.delay);
      return `${p.head ? `<div class="pad d sd-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        ${ACT.html(p.receiver, RS, "sd-recv", RX, SY)}${ACT.html(p.sender, SS, "sd-send", SX, SY)}
        <div class="pad d sd-time" style="z-index:2;top:1070px;font-size:190px;text-align:center;white-space:nowrap;color:var(--accent-text);opacity:0"><span class="sd-n">${d ? d.num : p.delay}</span>${d && d.unit ? `<span style="font-size:84px;margin-left:22px;color:currentColor">${d.unit}</span>` : ""}</div>
        <div class="sd-bar" style="position:absolute;left:72px;top:1262px;width:936px;height:14px;background-color:currentColor;opacity:0.18"></div>
        <i class="sd-fill" style="position:absolute;left:72px;top:1262px;width:936px;height:14px;background-color:var(--accent);transform:scaleX(0);transform-origin:0 50%"></i>
        <div class="sd-ring" style="position:absolute;left:${RX - 60}px;top:${SY - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></div>
        <div class="sd-flash" style="position:absolute;left:${RX - 180}px;top:${SY - 180}px;width:360px;height:360px;border-radius:50%;background-color:#fff;opacity:0"></div>
        ${p.result ? `<div class="pad d sd-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, t = Math.max(c.at(p.at), c.start + 2.2), span = c.end - c.start, d = parse(p.delay);
      const tS = Math.min(p.sendAt ? c.at(p.sendAt) : Math.max(c.start + 1.0, t - 3.0), t - 0.9), v = (GAP - R0) / (t - tS);
      const cv = kit.canvas("#" + c.box.id), cx = cv.getContext("2d"), acc = c.L.colors.accent, light = p.ground === "light" ? c.L.colors.ink : c.L.colors.light;
      const nEl = c.q(".sd-n"), fill = c.q(".sd-fill"), rv = c.q(".sd-recv .act-v"), sv = c.q(".sd-send .act-v"), nTxt = nEl.textContent;
      const fmt = d ? (x) => x.toLocaleString("en-US", { minimumFractionDigits: d.dec, maximumFractionDigits: d.dec, useGrouping: d.grp }) : null;
      tl.set(c.sel(".sd-time"), { autoAlpha: 0 }, 0);
      rv.style.opacity = 0.4; // dim until the signal lands
      const frame = (tt) => {
        cx.clearRect(0, 0, 1080, 1920);
        const pr = clamp((tt - tS) / (t - tS));
        if (tt >= tS) for (let k = 0; ; k++) { // the waves: arcs centred on the sender, clipped where they meet the receiver
          const te = tS + k * PER, r = R0 + v * (tt - te); if (r < R0) break; if (te > c.end) break;
          if (r > GAP + 20) continue;
          const a = 0.42 - (r - R0) / GAP * 0.1; cx.globalAlpha = clamp((r - R0) / 40) * (r > GAP - 30 ? (GAP + 20 - r) / 50 : 1);
          cx.strokeStyle = k % 3 === 0 ? light : acc; cx.lineWidth = k === 0 ? 16 : 11;
          cx.beginPath(); cx.arc(SX, SY, r, -a, a); cx.stroke();
        }
        cx.globalAlpha = 1;
        if (tt >= t && tt < t + 0.6) { // rays from the receiver as it lights
          const age = (tt - t) / 0.6; cx.strokeStyle = acc; cx.lineWidth = 12; cx.globalAlpha = 1 - age; cx.lineCap = "butt";
          for (let j = 0; j < 12; j++) { const an = (j / 12) * 6.283, r0 = RS / 2 + 20 + age * 70, r1 = r0 + 50 * (1 - age) + 10;
            cx.beginPath(); cx.moveTo(RX + Math.cos(an) * r0, SY + Math.sin(an) * r0); cx.lineTo(RX + Math.cos(an) * r1, SY + Math.sin(an) * r1); cx.stroke(); }
          cx.globalAlpha = 1;
        }
        if (d) nEl.textContent = fmt(tt >= t ? d.v : d.v * pr); else nEl.textContent = nTxt;
        fill.style.transform = `scaleX(${tt >= t ? 1 : pr})`;
        const em = tt >= tS ? 1 - clamp(((tt - tS) % PER) / 0.2) : 0; // the sender throbs on every wave it sends
        sv.style.transform = `scale(${1 + 0.06 * em})`;
        const lit = tt >= t, hit = lit ? clamp(1 - ((tt - t) % PER) / 0.15) : 0; // and the receiver on every wave that lands
        rv.style.opacity = lit ? 1 : 0.4; rv.style.transform = lit ? `scale(${1 + 0.04 * hit})` : "";
      };
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 121, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".sd-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".sd-send"), { scale: 0.6, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "back.out(1.6)" }, c.start + 0.05);
      tl.fromTo(c.sel(".sd-recv"), { scale: 0.6, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "back.out(1.6)" }, c.start + 0.3);
      tl.fromTo(c.sel(".sd-bar"), { scaleX: 0 }, { scaleX: 1, duration: 0.6, ease: "power3.out", transformOrigin: "0 50%" }, c.start + 0.5);
      tl.fromTo(c.sel(".sd-time"), { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: 0.6, ease: "power3.out" }, Math.max(c.start + 0.5, tS - 0.2));
      c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 }); c.sfx(c.start + 0.3, "pop", { step: 2 });
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", onUpdate: () => frame(c.start + o.t) }, c.start);
      c.sfx(tS, "whoosh", { f0: 300, f1: 2400, dur: 0.6, gain: 0.12 }); c.sfx(tS, "riser", { dur: t - tS, gain: 0.12 });
      for (let k = 0; k < Math.min(6, Math.floor((t - tS) / PER)); k++) c.sfx(tS + k * PER, "blip", { step: k % 4, dur: 0.2, gain: 0.07 });
      for (let k = 1; k < 7; k++) c.sfx(tS + ((t - tS) * k) / 7, "click", { gain: 0.05, f0: 1500 + k * 250 });
      // the landing
      tl.fromTo(c.sel(".sd-ring"), { scale: 0.3, opacity: 1 }, { scale: 6, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, t);
      tl.fromTo(c.sel(".sd-flash"), { opacity: 1, scale: 0.2 }, { opacity: 0, scale: 1.6, duration: 0.32, ease: "power2.out", immediateRender: false }, t);
      tl.set(c.sel(".sd-flash"), { opacity: 0 }, 0);
      tl.fromTo(c.sel(".sd-time"), { scale: 1, transformOrigin: "50% 50%" }, { scale: 1.1, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-14, 8], [12, -8], [-7, 4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, t);
      c.particles("burst", t - 0.05, t + 1.7, { at: t, x: RX - RS / 2, y: SY, spread: 3.1, g: c.L.id === "space" ? 100 : 500, count: 130, seed: 123, color: c.L.particles.accent });
      c.sfx(t, "impact", { gain: 0.16 }); c.sfx(t + 0.05, "chime", { step: 3, gain: 0.1 });
      if (p.result) c.rise(".sd-result", p.resultAt ? c.at(p.resultAt) : t + 0.9, { ease: "power4.out" });
    },
  });
})();
