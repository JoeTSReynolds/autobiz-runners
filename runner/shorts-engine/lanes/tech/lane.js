window.LANE = {
  id: "tech",
  key: [130.81, 146.83, 164.81, 196.0, 220.0], // C major pentatonic: the pitch of the synth pops, blips and chimes
  music: "tech", // a recorded track from sounds/music/tech/, chosen per video
  colors: { dark: "#111111", light: "#e9e7e2", accent: "#ff4f00", tint: "#ff9f70", mid: "#77746e", ink: "#111111" },
  particles: { ambient: "sparks", dust: "233,231,226", accent: "255,79,0" },
  font: '800 100px "Archivo"', // what the driver waits for before measuring text
  fonts: ["archivo.woff2"],
};
// Lane motif: a silicon wafer drawn into `svg` (viewBox centred on 0,0). Only whole dies inside the edge ring
// count: the first 100 (each worth 1%) are returned for blueprints to light up; partial edge dies stay dim.
LANE.wafer = { disc: "#232220", die: "#3a3936", spare: "#2c2b29" };
LANE.drawWafer = (svg, r, cell, gap) => {
  const NS = "http://www.w3.org/2000/svg", W = LANE.wafer, mk = (tag, a, parent) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); parent.appendChild(e); return e; };
  const g = mk("g", {}, svg), dies = [], n = Math.ceil(r / cell) + 1;
  mk("circle", { r, fill: W.disc }, g);
  for (let y = -n; y < n; y++) for (let x = -n; x < n; x++) {
    const x0 = x * cell + gap / 2, y0 = y * cell + gap / 2, s = cell - gap;
    if (![[x0, y0], [x0 + s, y0], [x0, y0 + s], [x0 + s, y0 + s]].every(([a, b]) => Math.hypot(a, b) < r - 14)) continue;
    dies.push(mk("rect", { x: x0, y: y0, width: s, height: s, fill: W.die }, g));
  }
  if (dies.length < 100) throw new Error(`wafer r=${r} cell=${cell}: only ${dies.length} dies fit, need 100`);
  dies.slice(100).forEach((d) => d.setAttribute("fill", W.spare));
  return { g, dies: dies.slice(0, 100) };
};
