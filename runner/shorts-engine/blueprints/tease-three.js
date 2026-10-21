// Open loop, "countdown of three": a headline and three stacked blocks. The first two fill in on their
// words; the third slams in masked ("???", glitching) and stays a mystery. Resolve it later with
// reveal-third, using the same two items. `image` (+ `focus`) sets a dimmed photo behind it that pushes in.
// shared with reveal-third.js (each file carries it, so either can be used alone)
window.T3 = window.T3 || { tops: [560, 830, 1100], h: 220 };
if (!window.t3Blocks) window.t3Blocks = (items, third) => items.map((it, i) => `<div class="t3-b t3-b${i}" style="position:absolute;left:72px;width:936px;top:${T3.tops[i]}px;height:${T3.h}px;background-color:var(--ink);color:var(--light)"><div class="pad d t3-txt" data-fitw="860" style="left:38px;right:38px;top:44px;font-size:130px;white-space:nowrap">${it}</div></div>`).join("")
  + `<div class="t3-b t3-b2" style="position:absolute;left:72px;width:936px;top:${T3.tops[2]}px;height:${T3.h}px;background-color:var(--accent);color:var(--ink)"><div class="pad d t3-mask" style="left:38px;right:38px;top:44px;font-size:130px">???</div>${third ? `<div class="pad d t3-third" data-fitw="860" style="left:38px;right:38px;top:44px;font-size:130px;white-space:nowrap;opacity:0">${third}</div>` : ""}</div>`;
BP.define("tease-three", {
  ground: (p) => p.ground || "dark",
  photo: (p) => !!p.image, // a photo sits behind the caption band
  slots: {
    image: { type: "image", opt: true }, focus: { type: "point", opt: true },
    head: { type: "lines", max: 20, lines: 2 },
    items: { type: "list", min: 2, max: 2, of: { text: { type: "text", max: 18 }, at: { type: "anchor" } } },
    mysteryAt: { type: "anchor" },
    ground: { type: "enum", values: ["dark", "light"], opt: true },
  },
  html: (p) => {
    let img = "";
    if (p.image) {
      const m = kit.cover(p.image, 1080, 1920), [fx, fy] = m.px(p.focus || { x: 0.5, y: 0.5 });
      const x = Math.min(0, Math.max(1080 - m.iw, 540 - fx + m.ox)), y = Math.min(0, Math.max(1920 - m.ih, 960 - fy + m.oy));
      img = `<img class="t3-img" src="assets/${p.image}" style="position:absolute;left:${x}px;top:${y}px;width:${m.iw}px;height:${m.ih}px;opacity:0.45;transform-origin:${fx - m.ox}px ${fy - m.oy}px" />`;
    }
    return img + `<div class="pad d t3-head" style="top:150px;font-size:120px">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>${t3Blocks(p.items.map((i) => i.text))}`;
  },
  animate(c) {
    const { tl, p } = c;
    if (p.image) tl.fromTo(c.sel(".t3-img"), { scale: 1.15 }, { scale: 1, duration: c.end - c.start, ease: "none", data: "ambient" }, c.start);
    c.rise(".t3-head", c.start + 0.1, { stagger: 0.12 });
    p.items.forEach((it, i) => {
      const t = c.at(it.at);
      tl.fromTo(c.sel(".t3-b" + i), { xPercent: -110 }, { xPercent: 0, duration: 0.55, ease: "expo.out" }, t);
      c.sfx(t, "pop", { step: i * 2 });
    });
    const m = c.at(p.mysteryAt);
    tl.fromTo(c.sel(".t3-b2"), { scale: 1.6, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.35, ease: "power4.in" }, m);
    tl.to(c.sel(".t3-b2"), { keyframes: [-26, 18, -10, 0].map((x) => ({ x, duration: 0.05, ease: "steps(1)" })) }, m + 0.35);
    c.sfx(m + 0.3, "whoosh-big", { dur: 0.4 });
    const o = { p: 0 }, node = c.q(".t3-mask"), dur = Math.max(0.5, c.end - m - 0.4);
    tl.to(o, { p: 1, duration: dur, ease: "none", onUpdate: () => { const k = Math.floor(o.p * dur * 10); node.textContent = ["???", "?#?", "%??", "??&", "?!?"][k % 5]; } }, m + 0.4);
  },
});
