// "A rival catches up" (tech): a headline and two wafers side by side. The left one is fully lit; the right
// one fills in die by die on `rivalAt`, then hops on `bounceAt`.
BP.define("wafer-rival", {
  ground: "dark",
  slots: { head: { type: "lines", max: 14, lines: 2 }, rivalAt: { type: "anchor" }, bounceAt: { type: "anchor" } },
  html: (p) => `<div class="pad d wr-head" style="top:180px;font-size:210px">${p.head.map((l) => `<div class="line">${l}</div>`).join("")}</div>
    <svg class="pad wr-twin" style="top:660px" width="936" height="600" viewBox="0 0 936 600"></svg>`,
  animate(c) {
    const { tl, p } = c, C = c.L.colors, NS = "http://www.w3.org/2000/svg", twin = c.q(".wr-twin");
    const [a, b] = [0, 486].map((x) => {
      const s = document.createElementNS(NS, "svg");
      Object.entries({ x, y: 60, width: 450, height: 450, viewBox: "-225 -225 450 450" }).forEach(([k, v]) => s.setAttribute(k, v));
      twin.appendChild(s);
      return { svg: s, ...c.L.drawWafer(s, 220, 33, 5) };
    });
    a.dies.forEach((d) => d.setAttribute("fill", C.accent));
    c.rise(".wr-head", c.start);
    const t = c.at(p.rivalAt);
    tl.to(b.dies, { attr: { fill: C.light }, duration: 0.04, stagger: 0.02, ease: "none" }, t);
    c.sfx(t, "scratch", { dur: 1.5 });
    tl.fromTo(b.svg, { attr: { y: 60 } }, { attr: { y: 30 }, duration: 0.3, yoyo: true, repeat: 1, ease: "power2.out" }, c.at(p.bounceAt));
  },
});
