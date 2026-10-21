// A flat-shaded globe (drawn with real meridians and parallels, no continents) turns slowly. 1..4 `places`
// ({text up to 16 chars, where, at}) each get a pin that drops onto the globe on its word with a bounce, three
// ripples, a burst and a tag with the place's text. `where` is the point on the globe's visible face (x, y from 0
// to 1, top-left is 0,0; keep it inside the disc, about 0.15..0.85); the pin then rides the globe as it turns and
// hides when it goes round the back. Keep places in spoken order. A `result` line lands under the globe.
// Cast anything: data-centre locations (places "Dublin", "Oregon", "Singapore"), the Woomera landing site
// (place "Woomera" on the lower right of the face), launch sites round the world, a company's offices.
(() => {
  const GX = 540, GY = 810, R = 300, W = 0.09; // W: spin in radians per second
  const clamp = (x) => Math.max(0, Math.min(1, x));
  BP.define("pin-drop", {
    ground: (p) => p.ground || "dark",
    slots: {
      head: { type: "lines", max: 18, lines: 2, opt: true }, headAt: { type: "anchor", opt: true },
      places: { type: "list", min: 1, max: 4, of: { text: { type: "text", max: 16 }, where: { type: "point" }, at: { type: "anchor" } } },
      result: { type: "text", max: 20, opt: true }, resultAt: { type: "anchor", opt: true },
      ground: { type: "enum", values: ["dark", "light"], opt: true },
    },
    html(p) {
      return `${p.head ? `<div class="pad d pn-head" style="top:120px;font-size:112px;z-index:2">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
        ${p.places.map((s, i) => `<div class="pn-pin pn-pin${i}" style="position:absolute;left:0;top:0;width:0;height:0;visibility:hidden;z-index:1">
          <i class="pn-rip" style="position:absolute;left:-60px;top:-60px;width:120px;height:120px;border-radius:50%;border:12px solid var(--accent);opacity:0"></i>
          <div class="pn-v" style="position:absolute;left:-26px;top:-96px;width:52px;height:96px;opacity:0"><i style="position:absolute;left:0;top:0;width:52px;height:52px;border-radius:50%;background-color:var(--accent)"></i><i style="position:absolute;left:17px;top:17px;width:18px;height:18px;border-radius:50%;background-color:var(--ink)"></i><i style="position:absolute;left:10px;top:40px;border:16px solid transparent;border-top:44px solid var(--accent);border-bottom:0;box-sizing:content-box"></i></div>
          <b class="d pn-tag" style="position:absolute;left:0;top:-196px;height:76px;padding:0 24px;display:flex;align-items:center;white-space:nowrap;font-size:52px;background-color:${p.ground === "light" ? "var(--ink)" : "var(--light)"};color:${p.ground === "light" ? "var(--light)" : "var(--dark)"};opacity:0">${s.text}</b></div>`).join("")}
        ${p.result ? `<div class="pad d pn-result" style="top:1318px;z-index:2;font-size:96px;color:var(--accent-text)"><div class="line" data-layout-allow-occlusion>${p.result}</div></div>` : ""}`;
    },
    animate(c) {
      const { tl, p } = c, span = c.end - c.start, minY = p.head ? 440 : 330;
      const places = p.places.map((s, i) => ({ ...s, i, t: c.at(s.at) })).sort((a, b) => a.t - b.t);
      const ground = p.ground === "light" ? c.L.colors.light : c.L.colors.dark, disc = p.ground === "light" ? c.L.colors.ink : c.L.colors.light, mid = c.L.colors.mid;
      const cv = kit.canvas("#" + c.box.id), cx = cv.getContext("2d"), phi = (u) => W * (u - c.start);
      places.forEach((s) => { // face point -> latitude and longitude at the moment of the drop
        const nx = Math.max(-0.92, Math.min(0.92, (s.where.x - 0.5) * 2)), ny = Math.max(-0.92, Math.min(0.92, (s.where.y - 0.5) * 2)), r = Math.hypot(nx, ny), k = r > 0.92 ? 0.92 / r : 1;
        const X = nx * k, Y = ny * k, z = Math.sqrt(Math.max(0, 1 - X * X - Y * Y));
        s.lat = Math.asin(-Y); s.lon0 = Math.atan2(X, z) - phi(s.t); s.el = c.q(`.pn-pin${s.i}`); s.tag = s.el.querySelector(".pn-tag"); s.tw = s.tag.offsetWidth;
      });
      const proj = (lat, lon) => [GX + R * Math.cos(lat) * Math.sin(lon), GY - R * Math.sin(lat), Math.cos(lat) * Math.cos(lon)];
      const frame = (tt) => {
        cx.clearRect(0, 0, 1080, 1920);
        const f = phi(tt);
        cx.fillStyle = disc; cx.beginPath(); cx.arc(GX, GY, R, 0, 6.283); cx.fill();
        cx.fillStyle = mid; cx.beginPath(); cx.moveTo(GX, GY - R); cx.arc(GX, GY, R, -Math.PI / 2, Math.PI / 2); cx.ellipse(GX, GY, R * 0.6, R, 0, Math.PI / 2, -Math.PI / 2, true); cx.fill(); // the shaded side
        cx.strokeStyle = ground; cx.lineWidth = 3; cx.globalAlpha = 0.7;
        for (let m = 0; m < 12; m++) { cx.beginPath(); let on = false; for (let a = -90; a <= 90; a += 6) { const q = proj((a * Math.PI) / 180, (m * Math.PI) / 6 + f); if (q[2] > 0) { on ? cx.lineTo(q[0], q[1]) : cx.moveTo(q[0], q[1]); on = true; } else on = false; } cx.stroke(); }
        for (const lat of [-60, -30, 0, 30, 60]) { cx.beginPath(); let on = false; for (let a = -90; a <= 90; a += 6) { const q = proj((lat * Math.PI) / 180, (a * Math.PI) / 180); on ? cx.lineTo(q[0], q[1]) : cx.moveTo(q[0], q[1]); on = true; } cx.stroke(); }
        cx.globalAlpha = 1;
        places.forEach((s) => { // each pin rides the globe; behind the limb it hides
          const [x, y, z] = proj(s.lat, s.lon0 + f), show = tt >= s.t && z > 0.12;
          s.el.style.visibility = show ? "visible" : "hidden";
          if (!show) return;
          s.el.style.left = x + "px"; s.el.style.top = y + "px";
          const below = y - 200 < minY; // a tag that would hit the headline goes under the pin
          s.tag.style.top = below ? "24px" : "-196px"; s.tag.style.left = Math.max(24 - x, Math.min(1056 - x - s.tw, -s.tw / 2)) + "px";
        });
      };
      c.particles(c.L.particles.ambient, c.start, c.end, { count: 110, seed: 211, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
      if (p.head) c.rise(".pn-head", p.headAt ? c.at(p.headAt) : c.start + 0.1);
      cv.style.opacity = 0;
      tl.fromTo(cv, { opacity: 0, scale: 0.7, transformOrigin: `${GX}px ${GY}px` }, { opacity: 1, scale: 1, duration: 0.8, ease: "back.out(1.5)" }, c.start + 0.05);
      c.sfx(c.start + 0.05, "whoosh", { gain: 0.08 });
      places.forEach((s, k) => {
        tl.fromTo(c.sel(`.pn-pin${s.i} .pn-v`), { y: -420, opacity: 0 }, { y: 0, opacity: 1, duration: 0.85, ease: "bounce.out", immediateRender: false }, s.t - 0.45);
        for (let j = 0; j < 3; j++) tl.fromTo(c.sel(`.pn-pin${s.i} .pn-rip`), { scale: 0.2, opacity: 0.9 }, { scale: 3 + j * 0.4, opacity: 0, duration: 0.9, ease: "power3.out", immediateRender: false }, s.t + j * 0.3);
        tl.fromTo(c.sel(`.pn-pin${s.i} .pn-tag`), { opacity: 0, scale: 1.5 }, { opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2.4)", transformOrigin: "50% 100%", immediateRender: false }, s.t + 0.1);
        { const [bx, by] = proj(s.lat, s.lon0 + phi(s.t)); c.particles("burst", s.t - 0.05, s.t + 1.5, { at: s.t, x: bx, y: by, spread: 3.1, g: 250, count: 70, seed: 213 + k, color: c.L.particles.accent }); }
        c.sfx(s.t, "impact", { gain: 0.14 }); c.sfx(s.t + 0.05, "blip", { step: 1 + k, dur: 0.3 }); c.sfx(s.t - 0.45, "whoosh", { dur: 0.4, gain: 0.08 });
        tl.fromTo(c.box, { x: 0, y: 0 }, { keyframes: [[-6, 4], [5, -4], [0, 0]].map(([x, y]) => ({ x, y, duration: 0.05 })), immediateRender: false }, s.t);
      });
      // a ripple leaves the newest pin every 2.4 s afterwards (real beats)
      places.forEach((s, k) => { const nxt = places[k + 1] ? places[k + 1].t : c.end; for (let u = s.t + 1.6; u < nxt - 0.6 && u < c.end - 0.5; u += 2.4) tl.fromTo(c.sel(`.pn-pin${s.i} .pn-rip`), { scale: 0.2, opacity: 0.8 }, { scale: 3.4, opacity: 0, duration: 1.0, ease: "power3.out", immediateRender: false }, u); });
      if (places[0].t - c.start > 3) for (let u = c.start + 1.4; u < places[0].t - 0.6; u += 2.4) tl.fromTo(cv, { scale: 1 }, { scale: 1.015, duration: 0.3, yoyo: true, repeat: 1, ease: "power2.out", transformOrigin: `${GX}px ${GY}px`, immediateRender: false }, u);
      const o = { t: 0 };
      tl.to(o, { t: span, duration: span, ease: "none", data: "ambient", onUpdate: () => frame(c.start + o.t) }, c.start);
      if (p.result) c.rise(".pn-result", p.resultAt ? c.at(p.resultAt) : places.at(-1).t + 1.4, { ease: "power4.out" });
    },
  });
})();
