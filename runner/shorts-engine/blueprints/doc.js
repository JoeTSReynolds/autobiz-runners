// A document page: a paper sheet on a dark ground with a small title and rule, grey filler text, and 2-4 real
// lines of wording placed among it. Each line is marked on its spoken word: "highlight" (an accent marker sweeps
// behind it), "redact" (a black bar wipes over it) or "reveal" (it starts blacked out and the bar wipes off).
// The camera drifts toward the line being marked. Use for leaks, reports, rulings, studies, papers and terms of
// service: any story where the exact wording on a page is the point. Keep each line short and quotable.
const DOC = { top: 170, w: 936, h: 1170, y0: 150, pitch: 64, rows: 15 };
BP.define("doc", {
  ground: "dark",
  slots: {
    title: { type: "text", max: 32 },
    lines: { type: "list", min: 2, max: 4, of: { text: { type: "text", max: 38 }, at: { type: "anchor" }, mark: { type: "enum", values: ["highlight", "redact", "reveal"] } } },
  },
  html(p) {
    let x = [...p.title].reduce((a, ch) => (a * 31 + ch.charCodeAt(0)) >>> 0, 7) || 1; // seeded: same page every render
    const r = () => (x = (x * 16807) % 2147483647) / 2147483647, k = p.lines.length;
    const split = (t) => { // a long line breaks once near its middle so each half stays big
      if (t.length <= 26) return [t];
      const m = t.length >> 1, i = [t.lastIndexOf(" ", m), t.indexOf(" ", m)].filter((n) => n > 0).sort((a, b) => Math.abs(a - m) - Math.abs(b - m))[0];
      return i > 0 ? [t.slice(0, i), t.slice(i + 1)] : [t];
    };
    const rows = p.lines.map((l) => split(l.text)), fill = DOC.rows - rows.reduce((n, s) => n + s.length, 0);
    const gap = (g) => Math.floor(fill / (k + 1)) + (g < fill % (k + 1) ? 1 : 0);
    let y = DOC.y0, out = "";
    const bars = (n) => { for (let i = 0; i < n; i++, y += DOC.pitch) out += `<i style="position:absolute;left:56px;top:${y + 22}px;width:${Math.round(8.24 * (i === n - 1 && n > 1 ? 35 + r() * 30 : 86 + r() * 14))}px;height:20px;background-color:var(--ink);opacity:0.14"></i>`; };
    rows.forEach((parts, i) => {
      bars(gap(i));
      const l = p.lines[i], hl = l.mark === "highlight";
      parts.forEach((t) => {
        out += `<div class="dl-row" style="position:absolute;left:56px;top:${y}px;height:${DOC.pitch}px"><span class="t" data-fitw="824" style="position:relative;display:inline-block;isolation:isolate;white-space:nowrap;font-size:52px;line-height:${DOC.pitch}px;color:var(--ink)"><span class="dl-tx dl-t${i}">${t}</span><i class="dl-mk dl-mk${i}" style="position:absolute;left:-12px;right:-12px;top:7px;bottom:7px;visibility:visible;z-index:${hl ? -1 : 1};background-color:var(${hl ? "--accent" : "--ink"})"></i></span></div>`;
        y += DOC.pitch;
      });
    });
    bars(gap(k));
    return `<div class="dl-cam" style="position:absolute;inset:0;transform-origin:0 0"><div class="dl-sheet" style="position:absolute;left:72px;top:${DOC.top}px;width:${DOC.w}px;height:${DOC.h}px">
      <i style="position:absolute;left:24px;top:24px;width:100%;height:100%;background-color:var(--mid)"></i>
      <div style="position:absolute;inset:0;background-color:var(--light);color:var(--ink)">
        <div class="lbl" data-fitw="824" style="position:absolute;left:56px;top:50px;font-size:40px;white-space:nowrap">${p.title}</div>
        <i style="position:absolute;left:56px;right:56px;top:112px;height:4px;background-color:var(--ink)"></i>${out}</div></div></div>`;
  },
  animate(c) {
    const { tl, p } = c, cam = c.sel(".dl-cam"), st = (P, s) => ({ scale: s, x: (1 - s) * P[0], y: (1 - s) * P[1] });
    tl.fromTo(c.sel(".dl-sheet"), { y: 140, rotation: 2, opacity: 0 }, { y: 0, rotation: 0, opacity: 1, duration: 0.6, ease: "expo.out" }, c.start);
    c.sfx(c.start, "whoosh", { gain: 0.1 });
    const marks = p.lines.map((l, i) => ({ l, i, t: c.at(l.at), P: [540, DOC.top + c.q(".dl-mk" + i).closest(".dl-row").offsetTop + 32] })).sort((a, b) => a.t - b.t);
    let from = st([540, 700], 1), t0 = c.start + 0.6;
    marks.forEach(({ l, i, t, P }, n) => {
      const reveal = l.mark === "reveal", mk = c.qa(".dl-mk" + i), to = st(P, 1.05 + 0.01 * n), end = Math.max(t0 + 0.6, t + 0.8);
      tl.fromTo(cam, from, { ...to, duration: end - t0, ease: "power1.inOut", data: "ambient", immediateRender: false }, t0);
      from = to; t0 = end;
      tl.fromTo(mk, { clipPath: reveal ? "inset(0% 0% 0% 0%)" : "inset(0% 100% 0% 0%)" }, { clipPath: reveal ? "inset(0% 0% 0% 100%)" : "inset(0% 0% 0% 0%)", duration: 0.45, ease: "power3.inOut", stagger: 0.18 }, t);
      // text is clipped away in step with a solid bar, so nothing unreadable sits under it
      if (l.mark !== "highlight") tl.fromTo(c.qa(".dl-t" + i), { clipPath: reveal ? "inset(0% 100% 0% 0%)" : "inset(0% 0% 0% 0%)" }, { clipPath: reveal ? "inset(0% 0% 0% 0%)" : "inset(0% 0% 0% 100%)", duration: reveal ? 0.55 : 0.36, ease: "power3.inOut", stagger: 0.18 }, t); // text leads a redact bar and trails a reveal bar
      if (l.mark === "highlight") { c.sfx(t, "whoosh", { dur: 0.35, f0: 700, f1: 2600, gain: 0.1 }); c.sfx(t + 0.3, "blip", { step: 2 + n }); }
      else if (l.mark === "redact") { c.sfx(t, "click", { f0: 700, gain: 0.16 }); c.sfx(t + 0.1, "whoosh", { dur: 0.3, f0: 1400, f1: 300, gain: 0.1 }); }
      else { c.sfx(t, "whoosh", { dur: 0.4, f0: 300, f1: 1800, gain: 0.1 }); c.sfx(t + 0.4, "chime", { step: 2, gain: 0.05 }); }
    });
    if (c.end - t0 > 0.5) tl.fromTo(cam, from, { ...st(marks.at(-1).P, 1.09), duration: c.end - t0, ease: "none", data: "ambient", immediateRender: false }, t0);
  },
});
