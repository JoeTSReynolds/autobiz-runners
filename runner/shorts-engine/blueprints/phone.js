// A phone (ink body, notch) showing a screenshot or photo as its screen, scrolling and pushing in slowly; on
// `noteAt` a wide notification card (app name + note, large enough to read at Shorts size) springs in from the top
// and overlaps the phone's edges. `app` is the app's name, `note` the notification text. Optional `head` (up to 2
// short lines) sits above the phone. Use for apps, platforms and consumer tech: a feature, a message, a setting,
// anything that happens on someone's phone.
const phoneGeo = (p) => { const top = p.head ? 350 : 120, h = 1430 - top, w = 620; return { top, h, w, left: (1080 - w) / 2, sw: w - 28, sh: h - 28 }; };
BP.define("phone", {
  ground: "light",
  slots: {
    image: { type: "image" }, focus: { type: "point", opt: true },
    head: { type: "lines", max: 18, lines: 2, opt: true },
    app: { type: "text", max: 18 }, note: { type: "text", max: 44 }, noteAt: { type: "anchor" },
  },
  html(p) {
    const g = phoneGeo(p), hv = Math.round(g.sh * 1.4), m = kit.cover(p.image, g.sw, hv), [fx] = m.px(p.focus || { x: 0.5, y: 0.5 });
    const x = Math.min(0, Math.max(g.sw - m.iw, g.sw / 2 - fx + m.ox));
    return `${p.head ? `<div class="pad d ph-head" style="top:100px;font-size:110px">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>` : ""}
      <div class="ph-wrap" style="position:absolute;left:${g.left}px;top:${g.top}px;width:${g.w}px;height:${g.h}px"><div class="ph" style="position:absolute;inset:0;background-color:var(--ink);border-radius:92px">
        <div style="position:absolute;inset:14px;border-radius:78px;overflow:hidden;background-color:var(--dark)">
          <div class="ph-feed" style="position:absolute;left:0;top:0;width:${g.sw}px;height:${hv}px"><img class="ph-img" src="assets/${p.image}" style="position:absolute;left:${x}px;top:${m.oy}px;width:${m.iw}px;height:${m.ih}px" /></div>
          <div style="position:absolute;left:50%;top:18px;width:150px;height:38px;margin-left:-75px;border-radius:19px;background-color:var(--ink)"></div>
        </div></div></div>
      <div class="ph-card" style="position:absolute;left:90px;width:900px;top:${g.top + 90}px;padding:30px 40px 34px;background-color:var(--light);color:var(--ink);border:8px solid var(--ink);border-left:28px solid var(--accent);box-shadow:14px 14px 0 var(--ink);transform:translateY(-900px)">
        <div style="display:flex;align-items:center;gap:16px"><i style="display:block;width:40px;height:40px;background-color:var(--accent)"></i><b class="lbl" style="font-size:40px">${p.app}</b></div>
        <div class="t ph-note" style="font-size:54px;margin-top:14px"><div class="line">${p.note}</div></div></div>`;
  },
  animate(c) {
    const { tl, p } = c, g = phoneGeo(p), hv = Math.round(g.sh * 1.4), n = c.at(p.noteAt), span = c.end - c.start;
    if (p.head) c.rise(".ph-head", c.start + 0.1, { stagger: 0.12 });
    tl.fromTo(c.sel(".ph-wrap"), { y: 320, opacity: 0 }, { y: 0, opacity: 1, duration: 0.7, ease: "expo.out" }, c.start);
    c.sfx(c.start, "whoosh", { gain: 0.1 });
    tl.fromTo(c.sel(".ph-feed"), { y: 0 }, { y: -(hv - g.sh), duration: span, ease: "none", data: "ambient" }, c.start);
    tl.fromTo(c.sel(".ph-img"), { scale: 1 }, { scale: 1.18, duration: span, ease: "none", data: "ambient" }, c.start);
    tl.fromTo(c.sel(".ph"), { rotation: -1.6 }, { rotation: 1.6, duration: span, ease: "sine.inOut", data: "ambient" }, c.start);
    tl.fromTo(c.sel(".ph-card"), { y: -900 }, { y: 0, duration: 0.95, ease: "elastic.out(1, 0.65)", immediateRender: false }, n);
    tl.fromTo(c.sel(".ph-wrap"), { scale: 1 }, { scale: 1.035, duration: 0.15, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, n + 0.12);
    c.rise(".ph-note", n + 0.3, { duration: 0.5 });
    c.sfx(n, "pop", { step: 4 }); c.sfx(n + 0.12, "blip", { step: 6, gain: 0.1 });
  },
});
