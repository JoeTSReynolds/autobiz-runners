// Horizontal bars growing on their words: a comparison ("compare"), a forecast ("forecast"), or two bars under
// a photo header ("versus", e.g. demand vs supply). Widths come from `value` (versus: value is a 0..100 score).
// A highlighted bar is accent, counts up if its text is a number, and pops. `over` sends a bar off the frame
// with a shake. A big figure of up to 6 characters is set huge and punches in; longer ones are two lines.
// In compare and forecast, every row shows its figure: put it in `text` ("80", "42.3%") and what it counts in `label`.
const BARS_GEO = { // bar y of the first row, row pitch, label offset above its bar, bar height, figure size/top, timings
  compare: { bar: 370, pitch: 340, off: 70, h: 210, fs: 170, bt: 30, t0: 0.2, gap: 0.1, head: 0.1, big: 1010, a: [1.4, "expo.out"], u: [0.7, "power4.out"] },
  forecast: { bar: 360, pitch: 260, off: 60, h: 150, fs: 110, bt: 24, t0: 0.1, gap: 0.1, head: 0.05, big: 1100, a: [1.0, "expo.out"], u: [0.5, "power4.out"] },
  versus: { bar: 960, pitch: 200, off: 0, h: 170, fs: 120, bt: 28, t0: 0, gap: 0.15, head: 0, big: 1100, a: [0.8, "expo.out"], u: [0.8, "expo.out"] },
};
const barsWidth = (p, r) => (p.layout === "versus" ? r.value / 100 : r.value / Math.max(...p.rows.map((x) => x.value))) * 936;
const barsBig = (b) => b.lines.length === 1 && b.lines[0].length <= 6;
BP.define("bars", {
  ground: "light",
  validate: (p) => (p.layout === "versus" ? [] : (p.rows || []).filter((r) => !/\d/.test(`${r.text}${r.label || ""}`))
    .map((r) => `bars row "${r.text}" shows no figure; in ${p.layout} put the number in text (e.g. "${r.value}") and what it counts in label`)),
  slots: {
    layout: { type: "enum", values: ["compare", "forecast", "versus"] },
    head: { type: "object", of: { text: { type: "text", max: 28 }, at: { type: "anchor", opt: true } } },
    rows: { type: "list", min: 2, max: 3, of: {
      text: { type: "text", max: 14 }, value: { type: "number", min: 0.0001, max: 1e12 },
      label: { type: "text", max: 24, opt: true }, at: { type: "anchor", opt: true },
      highlight: { type: "bool", opt: true }, pulseAt: { type: "anchor", opt: true }, over: { type: "anchor", opt: true },
    } },
    big: { type: "object", opt: true, of: { lines: { type: "lines", max: 10, lines: 2 }, at: { type: "anchor" }, shakeAt: { type: "anchor", opt: true } } },
    photo: { type: "object", opt: true, of: {
      image: { type: "image" }, focus: { type: "point", opt: true }, place: { type: "text", max: 24 },
      banner: { type: "text", max: 20 }, bannerAt: { type: "anchor" },
    } },
  },
  html(p) {
    const g = BARS_GEO[p.layout], ph = p.photo;
    let photo = "";
    if (ph) {
      const m = kit.cover(ph.image, 1080, 760), [fx, fy] = m.px(ph.focus || { x: 0.5, y: 0.5 });
      const x = Math.min(0, Math.max(1080 - m.iw, 540 - fx + m.ox)), y = Math.min(0, Math.max(760 - m.ih, 380 - fy + m.oy));
      photo = `<div class="b-photo" style="position:absolute;left:0;top:0;width:1080px;height:760px;background:url(assets/${ph.image}) ${x}px ${y}px/${m.iw}px ${m.ih}px no-repeat;filter:grayscale(1) contrast(1.3) brightness(0.95)"></div>
        <div class="t b-place" style="position:absolute;left:0;top:640px;background-color:var(--dark);color:var(--light);padding:22px 72px"><div class="line">${ph.place}</div></div>
        <div class="d b-banner" style="position:absolute;left:0;top:120px;font-size:120px;background-color:var(--accent);color:var(--ink);padding:22px 72px 14px"><div class="line">${ph.banner}</div></div>`;
    }
    const rows = p.rows.map((r, i) => {
      const y = g.bar + i * g.pitch, dark = !r.highlight;
      return `${r.label ? `<div class="t b-lab" style="position:absolute;left:72px;top:${y - g.off}px;font-size:44px">${r.label}</div>` : ""}
        <div class="b-bar" style="position:absolute;left:72px;top:${y}px;height:${g.h}px;width:${barsWidth(p, r)}px;transform-origin:left center;background-color:var(${dark ? "--ink" : "--accent"});${dark ? "color:var(--light)" : ""}">
          ${barsWidth(p, r) >= 320 ? `<b class="d b-fig" data-fitw="${barsWidth(p, r) - 64}" style="position:absolute;left:32px;top:${g.bt}px;font-size:${g.fs}px;white-space:nowrap">${r.text}</b>`
            : `<b class="d b-fig" data-fitw="${936 - barsWidth(p, r) - 32}" style="position:absolute;left:calc(100% + 24px);top:${g.bt}px;font-size:${g.fs}px;white-space:nowrap;color:var(--ink)">${r.text}</b>`}</div>`; // a short bar carries its figure outside
    }).join("");
    const big = p.big ? `<div class="pad d b-big" style="top:${g.big}px;font-size:${barsBig(p.big) ? 400 : 150}px">${p.big.lines.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : "";
    return `${photo}<div class="pad t b-head" style="top:${ph ? 860 : 150}px"><div class="line">${p.head.text}</div></div>${rows}${big}`;
  },
  animate(c) {
    const { tl, p } = c, g = BARS_GEO[p.layout], ph = p.photo, bars = c.qa(".b-bar"), figs = c.qa(".b-fig"), labs = c.qa(".b-lab");
    if (ph) {
      const ba = c.at(ph.bannerAt);
      c.particles("sparks", ba, c.sceneEnd, { count: 36, seed: 8, color: c.L.particles.accent });
      tl.fromTo(c.sel(".b-photo"), { scale: 1.08 }, { scale: 1, duration: c.sceneEnd - c.start, ease: "none", data: "ambient" }, c.start);
      c.rise(".b-place", c.start + 0.3);
      c.rise(".b-banner", ba, { ease: "power4.out" });
    }
    c.rise(".b-head", p.head.at ? c.at(p.head.at) : c.start + g.head);
    let t = c.start + g.t0 - g.gap, lab = 0;
    p.rows.forEach((r, i) => {
      t = r.at ? c.at(r.at) : t + g.gap; // a row without its own word follows the previous one
      const [d, ease] = r.at ? g.a : g.u;
      tl.fromTo(bars[i], { scaleX: 0 }, { scaleX: 1, duration: d, ease }, t);
      if (r.highlight && r.at && /^\D*[\d.]+\D*$/.test(r.text)) {
        const m = /^(\D*)([\d.]+)(\D*)$/.exec(r.text), dec = (m[2].split(".")[1] || "").length;
        kit.count(tl, figs[i], 0, +m[2], t, d, (v) => m[1] + v.toFixed(dec) + m[3]);
      }
      if (r.highlight && r.at) c.sfx(t, "pop", { step: 5 });
      if (r.pulseAt) tl.fromTo(bars[i], { scaleY: 1 }, { scaleY: 1.12, duration: 0.15, yoyo: true, repeat: 1 }, c.at(r.pulseAt));
      if (r.label && r.at) tl.fromTo(labs[lab], { opacity: 0 }, { opacity: 1, duration: 0.3 }, t - 0.4);
      if (r.label) lab++;
      if (r.over) { // past the right edge of the frame, with a shake
        const o = c.at(r.over);
        tl.to(bars[i], { scaleX: 1240 / barsWidth(p, r), duration: 0.6, ease: "back.out(2)" }, o);
        c.sfx(o, "whoosh", { dur: 0.4, f0: 200, f1: 900, gain: 0.18 });
        tl.fromTo(c.box, { x: 0 }, { x: 10, duration: 0.05, repeat: 5, yoyo: true, ease: "none" }, o + 0.1);
      }
    });
    if (p.big) {
      const b = p.big, at = c.at(b.at);
      if (barsBig(b)) { c.rise(".b-big", at, { duration: 0.6, ease: "power4.out" }); c.sfx(at, "pop", { step: 5 }); } else c.rise(".b-big", at, { stagger: 0.12 });
      if (b.shakeAt) tl.fromTo(c.sel(".b-big"), { x: 0 }, { x: 14, duration: 0.06, repeat: 5, yoyo: true, ease: "none" }, c.at(b.shakeAt));
    }
  },
});
