// A `traveller` flies an arc from an `origin` actor to a `destination` actor. A dashed trajectory draws itself
// ahead of it (accent where it has flown, grey where it is still to go), a big `distance` figure counts up as it
// goes (if it starts with a number, e.g. "384,400 km"; otherwise it just shows the text), and on the `at` word
// it arrives: shockwave rings, a flash, a burst and a shake. `departAt` (optional) is the word it takes off on.
// After arrival the destination keeps pinging so the frame never goes still. A `result` line lands under it.
// Cast anything: a probe flying from Earth to Phobos (traveller asset rocket or satellite, origin asset planet,
// destination asset moon, distance "56 million km"), chips shipped from Taiwan to Arizona (traveller asset chip,
// origin asset factory, destination asset building, distance "12,000 km"), a package from a warehouse to a
// customer (label "Parcel"), a rover capsule from orbit to a crater (asset capsule -> image of the crater).
(() => {
  const O = [230, 1100, 300], D = [810, 630, 340], S = [335, 975], E = [725, 775], P1 = [300, 570], TZ = 220;
  const bez = (u) => [(1 - u) ** 2 * S[0] + 2 * (1 - u) * u * P1[0] + u * u * E[0], (1 - u) ** 2 * S[1] + 2 * (1 - u) * u * P1[1] + u * u * E[1]];
  const clamp = (x) => Math.max(0, Math.min(1, x)), ease = (u) => u * u * (3 - 2 * u);
  const parse = (s) => { const m = /^(\d[\d,.]*)\s*(.*)$/.exec(s); return m ? { v: parseFloat(m[1].replace(/,/g, "")), dec: (m[1].split(".")[1] || "").length, grp: m[1].includes(","), unit: m[2] } : null; };
  BP.define("arc-travel", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      traveller: { type: "actor" }, origin: { type: "actor" }, destination: { type: "actor" },
      distance: { type: "text", max: 16 },
      at: { type: "anchor" }, // the arrival
      departAt: { type: "anchor", opt: true },
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      const d = parse(p.distance);
      return `${p.head ? `<div class="pad d at-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        ${ACT.html(p.destination, D[2], "at-dest", D[0], D[1])}${ACT.html(p.origin, O[2], "at-orig", O[0], O[1])}
        <div class="pad d at-dist" style="z-index:2;left:450px;top:1050px;font-size:130px;text-align:right;white-space:nowrap;color:var(--accent-text);opacity:0"><span class="at-n">${d ? p.distance.slice(0, p.distance.length - d.unit.length).trim() : p.distance}</span>${d && d.unit ? `<span style="font-size:64px;margin-left:16px">${d.unit}</span>` : ""}</div>
        ${ACT.html({ ...p.traveller, name: undefined }, TZ, "at-trav", 0, 0)}
        ${[D, O].map(([x, y], i) => `<div class="at-ring at-ring${i}" style="position:absolute;left:${x - 60}px;top:${y - 60}px;width:120px;height:120px;border-radius:50%;border:14px solid var(--accent);opacity:0"></div>`).join("")}
        <div class="at-flash" style="position:absolute;left:${E[0] + 40 - 150}px;top:${E[1] - 20 - 150}px;width:300px;height:300px;border-radius:50%;background-color:#fff;opacity:0"></div>
        ${p.result ? `<div class="pad d at-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, t1 = c.at(p.at), span = c.end - c.start, d = parse(p.distance);
      const fly = Math.min(3.6, Math.max(1.4, t1 - c.start - 1.4)), t0 = p.departAt ? Math.min(c.at(p.departAt), t1 - 1) : Math.max(c.start + 1.2, t1 - fly);
      const cvEl = kit.canvas("#" + c.box.id), cv = cvEl.getContext("2d"), acc = c.L.colors.accent, mid = c.L.colors.mid, light = p.ground === "light" ? c.L.colors.ink : c.L.colors.light;
      const trav = c.q(".at-trav"), tv = c.q(".at-trav .act-v"), dist = c.q(".at-dist"), nEl = c.q(".at-n");
      const fmt = d ? (v) => v.toLocaleString("en-US", { minimumFractionDigits: d.dec, maximumFractionDigits: d.dec, useGrouping: d.grp }) : null, nTxt = nEl.textContent;
      trav.style.opacity = 0; // shown by the first frame
      const pos = (t) => { const u = ease(clamp((t - t0) / (t1 - t0))); return [...bez(u), u]; };
      const frame = (t) => {
        cv.clearRect(0, 0, 1080, 1920);
        const [x, y, u] = pos(t), ahead = Math.min(1, 0.3 * clamp((t - (t0 - 1)) / 1) + u * 0.8), N = 30;
        cv.lineCap = "round"; cv.lineWidth = 8;
        for (let i = 0; i < N; i++) { // the dashed trajectory: accent behind the traveller, grey ahead of it
          const a = i / N, b = a + 0.55 / N; if (a > ahead) break;
          const q0 = bez(a), q1 = bez((a + b) / 2), q2 = bez(b);
          cv.globalAlpha = Math.min(1, (ahead - a) / 0.05) * (b < u ? 1 : 0.55); cv.strokeStyle = b < u ? acc : mid;
          cv.beginPath(); cv.moveTo(...q0); cv.quadraticCurveTo(...q1, ...q2); cv.stroke();
        }
        cv.globalAlpha = 1;
        const fl = t >= t0 && t < t1 + 0.05;
        for (let k = 1; k <= 9 && fl; k++) { const [qx, qy] = bez(ease(clamp((t - k * 0.045 - t0) / (t1 - t0)))); cv.globalAlpha = 0.5 - k * 0.05; cv.fillStyle = k % 2 ? acc : light; cv.fillRect(qx - 12 + k, qy - 12 + k, 24 - k * 2, 24 - k * 2); }
        cv.globalAlpha = 1;
        if (t > t1 + 0.9) for (let k = 0; k < 2; k++) { // the destination keeps pinging
          const age = ((t - t1 - 0.9 + k * 0.7) % 1.4) / 1.4; cv.globalAlpha = 0.6 * (1 - age); cv.strokeStyle = acc; cv.lineWidth = 6;
          cv.beginPath(); cv.arc(D[0], D[1], 185 + 50 * age, 0, 6.283); cv.stroke();
        }
        cv.globalAlpha = 1;
        const bob = t < t0 ? Math.sin(t * 5) * 6 : 0, s = t < t1 ? 0.8 + 0.2 * Math.sin(Math.PI * u) + (t < t0 ? 0 : 0.15) : Math.max(0, 1 - (t - t1) / 0.35);
        Object.assign(trav.style, { left: x - TZ / 2 + "px", top: y - TZ / 2 + bob + "px", transform: `scale(${s})`, opacity: t >= c.start + 0.5 && s > 0.02 ? 1 : 0 });
        tv.style.transform = `rotate(${(u - 0.5) * 70}deg)`;
        dist.style.opacity = t >= t0 - 0.2 ? 1 : 0;
        if (d) nEl.textContent = fmt(t >= t1 ? d.v : d.v * u); else nEl.textContent = nTxt;
      };
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 61, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".at-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      tl.fromTo(c.sel(".at-dest"), { scale: 0.6, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "back.out(1.6)" }, c.start + 0.05);
      tl.fromTo(c.sel(".at-orig"), { scale: 0.6, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: 0.7, ease: "back.out(1.6)" }, c.start + 0.25);
      tl.fromTo(c.sel(".at-dest .act-v"), { rotation: -4 }, { rotation: 4, duration: span, ease: "none", data: "ambient" }, c.start);
      c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 }); c.sfx(c.start + 0.25, "pop", { step: 1 });
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", onUpdate: () => frame(c.start + o.t) }, c.start);
      // take-off: a ring on the origin and a whoosh; the distance counts with the flight
      tl.fromTo(c.sel(".at-ring1"), { scale: 0.3, opacity: 1 }, { scale: 4, opacity: 0, duration: 0.8, ease: "power3.out", immediateRender: false }, t0);
      tl.fromTo(c.sel(".at-orig .act-v"), { scale: 1 }, { scale: 1.1, duration: 0.15, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t0);
      c.sfx(t0, "whoosh", { gain: 0.12 }); c.sfx(t0, "riser", { dur: t1 - t0, gain: 0.14 });
      for (let k = 1; k < 7; k++) c.sfx(t0 + ((t1 - t0) * k) / 7, "click", { gain: 0.05, f0: 1500 + k * 260 });
      // arrival
      tl.fromTo(c.sel(".at-ring0"), { scale: 0.3, opacity: 1 }, { scale: 6, opacity: 0, duration: 1, ease: "power3.out", immediateRender: false }, t1);
      tl.fromTo(c.sel(".at-flash"), { opacity: 1, scale: 0.2 }, { opacity: 0, scale: 1.6, duration: 0.32, ease: "power2.out", immediateRender: false }, t1);
      tl.set(c.sel(".at-flash"), { opacity: 0 }, 0);
      tl.fromTo(c.sel(".at-dest .act-v"), { scale: 1 }, { scale: 1.12, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t1);
      tl.fromTo(c.sel(".at-dist"), { scale: 1, transformOrigin: "100% 50%" }, { scale: 1.12, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, t1);
      tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-14, 8], [12, -8], [-7, 4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, t1);
      c.particles("burst", t1 - 0.05, t1 + 1.7, { at: t1, x: E[0] + 40, y: E[1] - 20, spread: 3.1, g: c.L.id === "space" ? 100 : 500, count: 150, seed: 63, color: c.L.particles.accent });
      c.sfx(t1, "impact", { gain: 0.16 }); c.sfx(t1 + 0.05, "chime", { step: 3, gain: 0.1 });
      if (p.result) {
        const r = p.resultAt ? c.at(p.resultAt) : t1 + 0.9;
        tl.to(c.sel(".at-orig .act-name"), { autoAlpha: 0, duration: 0.25 }, r - 0.45);
        c.rise(".at-result", r, { ease: "power4.out" });
      }
    },
  });
})();
