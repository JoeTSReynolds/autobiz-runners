// Outro: "Follow" and a short promise, with an optional photo above and the lane's ambient particles.
BP.define("follow", {
  ground: (p) => p.ground || "dark",
  slots: {
    sub: { type: "text", max: 34 }, followAt: { type: "anchor" },
    image: { type: "image", opt: true },
    ground: { type: "enum", values: ["dark", "light"], opt: true },
  },
  html: (p) => `${p.image ? `<img class="fo-img" src="assets/${p.image}" style="position:absolute;left:90px;top:200px;width:900px;height:900px;object-fit:cover" />` : ""}
    <div class="pad d fo-follow" style="top:1150px;font-size:250px"><div class="line">Follow</div></div>
    <div class="pad t fo-sub" style="top:1390px"><div class="line">${p.sub}</div></div>`,
  animate(c) {
    const { tl, p } = c, t = c.at(p.followAt);
    c.particles(c.L.particles.ambient, c.start, c.end, { count: 200, seed: 4, vx: 30, vy: 0, color: c.L.id === "tech" ? c.L.particles.accent : undefined });
    if (p.image) tl.fromTo(c.sel(".fo-img"), { scale: 1.3, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.9, ease: "expo.out" }, c.start);
    c.rise(".fo-follow", t, { ease: "back.out(1.3)" });
    c.rise(".fo-sub", t + 0.1);
    c.sfx(t, "chime", { step: 0 });
  },
});
