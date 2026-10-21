// Closes tease-three (hero): the same three blocks return, the first two dimmed, and the masked third
// unmasks on its word with a riser, an impact and a burst. An optional line underneath lands after.
// shared with tease-three.js (each file carries it, so either can be used alone)
window.T3 = window.T3 || { tops: [560, 830, 1100], h: 220 };
if (!window.t3Blocks) window.t3Blocks = (items, third) => items.map((it, i) => `<div class="t3-b t3-b${i}" style="position:absolute;left:72px;width:936px;top:${T3.tops[i]}px;height:${T3.h}px;background-color:var(--ink);color:var(--light)"><div class="pad d t3-txt" data-fitw="860" style="left:38px;right:38px;top:44px;font-size:130px;white-space:nowrap">${it}</div></div>`).join("")
  + `<div class="t3-b t3-b2" style="position:absolute;left:72px;width:936px;top:${T3.tops[2]}px;height:${T3.h}px;background-color:var(--accent);color:var(--ink)"><div class="pad d t3-mask" style="left:38px;right:38px;top:44px;font-size:130px">???</div>${third ? `<div class="pad d t3-third" data-fitw="860" style="left:38px;right:38px;top:44px;font-size:130px;white-space:nowrap;opacity:0">${third}</div>` : ""}</div>`;
BP.define("reveal-third", {
  ground: (p) => p.ground || "dark",
  slots: {
    head: { type: "lines", max: 20, lines: 2 },
    items: { type: "list", min: 2, max: 2, of: { text: { type: "text", max: 18 } } },
    third: { type: "text", max: 18 }, heroAt: { type: "anchor" },
    sub: { type: "object", opt: true, of: { text: { type: "text", max: 40 }, at: { type: "anchor" } } },
    ground: { type: "enum", values: ["dark", "light"], opt: true },
  },
  html: (p) => `<div class="pad d r3-head" style="top:150px;font-size:120px">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>${t3Blocks(p.items.map((i) => i.text), p.third)}
    ${p.sub ? `<div class="pad t r3-sub" style="top:1360px"><div class="line">${p.sub.text}</div></div>` : ""}`,
  animate(c) {
    const { tl, p } = c, h = c.at(p.heroAt);
    c.rise(".r3-head", c.start + 0.1, { stagger: 0.12 });
    tl.fromTo(c.qa(".t3-b"), { xPercent: -110 }, { xPercent: 0, duration: 0.5, ease: "expo.out", stagger: 0.12 }, c.start + 0.1);
    tl.to([c.q(".t3-b0"), c.q(".t3-b1")], { opacity: 0.35, duration: 0.4 }, Math.max(c.start + 0.7, h - 1.2));
    c.hero(h);
    tl.fromTo(c.sel(".t3-b2"), { scaleY: 1 }, { scaleY: 1.18, duration: 0.15, yoyo: true, repeat: 1, ease: "power2.out" }, h);
    tl.to(c.sel(".t3-mask"), { opacity: 0, duration: 0.1 }, h);
    tl.to(c.sel(".t3-third"), { opacity: 1, duration: 0.15 }, h + 0.05);
    c.particles("burst", h, h + 1.8, { at: h, x: 540, y: T3.tops[2] + T3.h / 2, count: 120, seed: 41, color: c.L.particles.accent, spread: 2.2, g: 700 });
    if (p.sub) c.rise(".r3-sub", c.at(p.sub.at));
  },
});
