import { createRequire as __autobizCreateRequire } from 'node:module'; const require = __autobizCreateRequire(import.meta.url);

// scripts/content-rewards-scout-run.ts
import { execFile } from "node:child_process";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";
import { chromium } from "playwright";

// scripts/content-rewards-post-key.ts
function postKey(url) {
  return /(?:shorts\/|[?&]v=|youtu\.be\/)([\w-]{11})/.exec(url)?.[1] ?? /instagram\.com\/(?:reel|p)\/([\w-]+)/.exec(url)?.[1] ?? "";
}

// scripts/content-rewards-scout.ts
var GAMING = ["gaming", "streamer", "twitch", "kick", "gta", "fortnite", "roblox", "minecraft", "mobile gaming", "pc gaming"];
var PODCAST = ["personal brand", "business", "entrepreneurship", "coach & mentor", "coaching & consulting", "content creator"];
var BLOCK = ["gambling", "casino", "betting", "bet", "parlay", "poker", "prop firm", "prop trading", "funded trader", "trading", "day trading", "forex", "crypto", "memecoin", "token", "nft", "adult", "onlyfans", "politics", "political", "election", "ugc", "sound campaign"];
var BLOCK_RE = new RegExp(`(?<![a-z])(${BLOCK.join("|")})s?(?![a-z])`, "i");
var payload = (html) => [...html.matchAll(/self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)/g)].map((m) => JSON.parse(m[1])).join("");
function parseDiscoverApi(json) {
  const data = json?.data;
  if (!Array.isArray(data)) return [];
  return data.filter((o) => o && typeof o.id === "string" && o.status === "active").map((o) => ({
    id: o.id,
    title: String(o.name ?? ""),
    brand: String(o.organizationName ?? ""),
    categories: (o.categories ?? []).map((c) => String(c.name)),
    type: o.payoutType,
    platforms: o.platforms ?? [],
    requiresApplication: !!o.requiresApplication,
    availableBudget: (o.budgetCents - (o.metrics?.budgetSpentCents ?? 0)) / 100,
    budgetTotal: o.budgetCents / 100,
    creators: o.metrics?.creatorCount ?? 0,
    rate: (o.cpmMaxRateCents ?? 0) / 100,
    url: `https://contentrewards.com/c/campaigns/${o.id}`,
    description: o.description,
    terms: (o.payouts ?? []).filter((p) => p.payoutType === "cpm").map((p) => ({ platform: String(p.platform), rate: p.rateCents / 100, minPayout: p.minPayoutCents / 100, maxPayout: p.maxPayoutCents / 100 })),
    references: (o.referenceMaterials ?? []).map((r) => r.url)
  }));
}
function routeChannel(c) {
  const names = c.categories.map((n) => n.toLowerCase());
  return names.some((n) => GAMING.includes(n)) ? "gaming" : names.some((n) => n.includes("podcast") || PODCAST.includes(n)) ? "podcast" : null;
}
var blocked = (c) => {
  const m = BLOCK_RE.exec(`${c.categories.join(" | ")} | ${c.title} | ${c.brand}`);
  return m ? `blocked: ${m[1].toLowerCase()}` : null;
};
function rank(list, { minBudget = 1e3 } = {}) {
  const score = (c) => c.rate * c.availableBudget / Math.max(c.creators, 1);
  return list.filter((c) => c.type === "cpm" && !c.requiresApplication && c.platforms.includes("youtube") && c.platforms.includes("instagram") && c.availableBudget >= minBudget && routeChannel(c) && !blocked(c)).sort((a, b) => score(b) - score(a));
}
function viewsToMinimum(terms, platform) {
  const t = terms.find((x) => x.platform === platform);
  return t && t.rate > 0 ? Math.ceil(t.minPayout / t.rate * 1e3) : Infinity;
}
var passesMinimum = ({ terms }, { maxViewsToMinimum = 2e3 } = {}) => viewsToMinimum(terms, "youtube") <= maxViewsToMinimum;
var entities = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'" };
var plain = (html) => html.replace(/<[^>]*>/g, " ").replace(/&(?:amp|lt|gt|quot|#39);/g, (e) => entities[e]).replace(/[ \t]+/g, " ").replace(/ ?\n ?/g, "\n").trim();
function draftFromCampaign(json, candidate, channel) {
  const o = json?.data ?? json ?? {};
  const cfg = o.configuration ?? {}, caption = cfg.rules?.caption ?? {};
  const refs = cfg.referenceMaterial ?? [];
  const urls = refs.map((r) => String(r.url ?? ""));
  const sources = [];
  for (const url of urls.filter((u) => /(?:youtube\.com|youtu\.be)\//.test(u))) {
    const id = postKey(url);
    if (id && !sources.some((x) => x.id === id)) sources.push({ id, url, title: String(o.name ?? ""), channel: "", duration: 0 });
  }
  const rates = {};
  for (const p of cfg.payoutModel ?? []) rates[String(p.platform)] = { rate: p.rate / 100, minPayout: p.minPayout / 100, maxPayout: p.maxPayout / 100 };
  return {
    id: candidate.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || candidate.id.slice(0, 8),
    url: candidate.url,
    channel,
    active: false,
    brief: String(cfg.content?.guidelines ?? "").trim(),
    requirements: plain(String(cfg.creator?.description ?? "")),
    checklist: (cfg.rules?.reviewerOnly ?? []).join("\n"),
    featured: "",
    disclosure: ["#ad", ...caption.hashtags ?? [], ...caption.mentions ?? []].join(" "),
    rates,
    sources,
    driveLinks: urls.filter((u) => /^https:\/\/(?:drive|docs)\.google\.com\//.test(u)),
    needsSourceInfo: true
  };
}
async function audit(records, fetchPublic, { retireBelow = 100 } = {}) {
  const out = [];
  for (const { id, url } of records) {
    try {
      const html = await fetchPublic(url), s = payload(html);
      const cents = (key) => Number(new RegExp(`"${key}":(\\d+)`).exec(s)?.[1] ?? NaN);
      const available = (cents("budgetCents") - cents("budgetSpentCents")) / 100, status = /"status":"(\w+)","statusChangedAt"/.exec(s)?.[1];
      if (!Number.isFinite(available) || !status) {
        out.push({ id, url, availableBudget: null, accepting: true, retire: false, reason: "unreadable page" });
        continue;
      }
      const accepting = status === "active" && !/not accepting|campaign (?:has )?ended/i.test(html.replace(/<[^>]*>/g, " "));
      const reason = !accepting ? `not accepting (${status})` : available < retireBelow ? `budget $${available} below $${retireBelow}` : "";
      out.push({ id, url, availableBudget: available, accepting, retire: !!reason, reason });
    } catch (error) {
      out.push({ id, url, availableBudget: null, accepting: true, retire: false, reason: `fetch failed: ${error instanceof Error ? error.message : error}` });
    }
  }
  return out;
}
var submitButton = (page) => page.getByRole("button", { name: "Submit clip", exact: true });
async function joinCampaign(page, url, waitMs = 2e4) {
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 3e4 });
    const submit = submitButton(page), join2 = page.getByRole("button", { name: "Join Campaign" }).first(), signIn = page.getByRole("link", { name: "Sign in" });
    await submit.or(join2).or(signIn).first().waitFor({ timeout: 3e4 });
    if (page.url().includes("/login") || await signIn.count()) return { joined: false, reason: "logged out" };
    if (await submit.count()) return { joined: true, already: true };
    await join2.click();
    let confirmed = false;
    for (const end = Date.now() + waitMs; Date.now() < end; await page.waitForTimeout(250)) {
      if (await submit.count()) return { joined: true };
      const dialog = page.getByRole("dialog").filter({ hasNotText: /cookie/i }).first();
      const ok = dialog.getByRole("button", { name: /^(join|confirm|accept|continue)/i }).first();
      if (confirmed || !await ok.isVisible()) continue;
      for (const box of await dialog.locator("input[type=checkbox]").all()) if (!await box.isChecked()) await box.evaluate((input) => input.click());
      if (await ok.isEnabled()) {
        await ok.click();
        confirmed = true;
      }
    }
    return { joined: false, reason: `no Submit clip button ${waitMs / 1e3} s after Join` };
  } catch (error) {
    return { joined: false, reason: (error instanceof Error ? error.message : String(error)).split("\n")[0].slice(0, 300) };
  }
}
async function fitCheck(candidates, ask, n = 5) {
  const top = candidates.slice(0, n);
  const prompt = `Our pipeline makes YouTube Shorts and Instagram Reels from long-form video. For each campaign below, decide whether we can clip it well. Podcast lane: long-form talking-head video with clear speech. Reject gameplay, trailers, music videos, product demos without talking, and non-English content.

${top.map((c) => JSON.stringify({ id: c.id, title: c.title, categories: c.categories, description: c.description?.slice(0, 400) })).join("\n")}

Reply with only a JSON array: [{"id": "...", "fit": true|false, "reason": "..."}], one entry per campaign.`;
  let verdicts = [];
  try {
    const reply = await ask(prompt), from = reply.indexOf("["), to = reply.lastIndexOf("]");
    const parsed = JSON.parse(reply.slice(from, to + 1));
    if (Array.isArray(parsed)) verdicts = parsed;
  } catch {
  }
  return top.map((c) => {
    const v = verdicts.find((x) => typeof x === "object" && x !== null && x.id === c.id && typeof x.fit === "boolean");
    return v ? { id: c.id, fit: v.fit, reason: String(v.reason ?? "") } : { id: c.id, fit: false, reason: "no valid verdict" };
  });
}
function report({ retired, drafted, suggested, blocked: skipped, wouldJoin }) {
  const lines = [
    `Retired (${retired.length})`,
    ...retired.map((r) => `- ${r.id}: ${r.reason}`),
    `Joined and drafted (${drafted.length})`,
    ...drafted.map((d) => `- ${d.title} ${d.url}`),
    ...wouldJoin ? [`Would join (dry run) (${wouldJoin.length})`, ...wouldJoin.map((w) => `- ${w.title} ${w.url}`)] : [],
    `Gaming suggestions (${suggested.length}), not joined`,
    ...suggested.map((c) => `- ${c.title} ($${c.rate}/1K, $${Math.round(c.availableBudget)} left) ${c.url}`),
    `Skipped ${skipped} blocked`
  ].join("\n");
  return lines.length <= 3500 ? lines : `${lines.slice(0, 3490)}
...`;
}

// scripts/content-rewards-scout-run.ts
var DISCOVER = "https://contentrewards.com/api/campaign/campaigns/discover?collapseGroups=true&limit=50&view=summary";
var MAX_PAGES = 12;
var message = (error) => (error instanceof Error ? error.message : String(error)).split("\n")[0].slice(0, 300);
var uuidOf = (url) => /[0-9a-f-]{36}$/i.exec(url)?.[0]?.toLowerCase() ?? "";
var readJson = async (path) => JSON.parse(await readFile(path, "utf8"));
var write = async (path, text) => {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, text);
};
async function knownRecords(dir) {
  const out = [];
  for (const slug of await readdir(dir).catch(() => [])) {
    try {
      const file = await readJson(join(dir, slug, "business.json"));
      for (const { id, url } of file.business?.settings?.campaigns ?? []) if (id && url) out.push({ id, url });
    } catch {
    }
  }
  return out;
}
async function scout(env, deps) {
  const { BUSINESSES_DIR = "businesses", SCOUT_STATE = "data/scout/seen.json", SCOUT_OUT = "scout-out" } = env;
  const join_ = env.SCOUT_JOIN === "1", maxJoins = Number(env.SCOUT_MAX_JOINS ?? 2), recheckMs = Number(env.SCOUT_RECHECK_DAYS ?? 14) * 864e5;
  const site = deps.site ?? { joinCampaign };
  const notes = [];
  const page = await deps.openPage();
  try {
    const all = [];
    for (let cursor = "", n = 0; n < MAX_PAGES; n++) {
      const reply = await deps.fetchJson(cursor ? `${DISCOVER}&cursor=${encodeURIComponent(cursor)}` : DISCOVER);
      for (const c of parseDiscoverApi(reply)) if (!all.some((x) => x.id === c.id)) all.push(c);
      cursor = String(reply?.pagination?.nextCursor ?? "");
      if (!cursor) break;
    }
    if (!all.length) throw new Error("Discover API returned no campaigns. Check that contentrewards.com is up; if joins also fail, the session may have expired: run `npm run cr:connect` and update the CR_SESSION secret.");
    const records = await knownRecords(BUSINESSES_DIR);
    const retired = (await audit(records, deps.fetchPublic)).filter((a) => a.retire).map((a) => ({ id: a.id, reason: a.reason }));
    const seen = await readJson(SCOUT_STATE).catch(() => ({}));
    const known = new Set(records.map((r) => uuidOf(r.url)));
    const fresh = rank(all).filter((c) => !known.has(c.id) && !(seen[c.id] && seen[c.id].verdict !== "failed" && deps.now() - Date.parse(seen[c.id].at) < recheckMs));
    const suggested = fresh.filter((c) => routeChannel(c) === "gaming").slice(0, 5);
    const isPodcast = (c) => c.categories.some((n) => /podcast/i.test(n));
    const eligible = fresh.filter((c) => routeChannel(c) === "podcast" && passesMinimum(c)).sort((a, b) => Number(isPodcast(b)) - Number(isPodcast(a)));
    const mark = (id, verdict) => {
      seen[id] = { verdict, at: new Date(deps.now()).toISOString() };
    };
    const drafted = [], wouldJoin = [];
    const top = eligible.slice(0, 10), fits = top.length ? await fitCheck(top, deps.ask, 10) : [];
    const judged = fits.filter((f) => f.reason !== "no valid verdict");
    if (top.length && judged.length < fits.length) notes.push(`Fit check gave no usable answer for ${fits.length - judged.length} of ${fits.length} campaigns; they will be asked again next run`);
    for (const f of judged.filter((f2) => !f2.fit)) {
      mark(f.id, "unfit");
      notes.push(`${top.find((x) => x.id === f.id).title}: not a fit (${f.reason})`);
    }
    for (const { id } of fits.filter((f) => f.fit).slice(0, maxJoins)) {
      const c = top.find((x) => x.id === id);
      if (!join_) {
        wouldJoin.push({ title: c.title, url: c.url });
        continue;
      }
      try {
        const joined = await site.joinCampaign(page, c.url);
        if (!joined.joined) {
          mark(id, "failed");
          notes.push(`${c.title}: join failed (${joined.reason})`);
          continue;
        }
        mark(id, "joined");
        const record = draftFromCampaign(await deps.fetchCampaign(c.id), c, "podcast");
        if (!record.sources.length) notes.push(`${c.title}: no YouTube source in the reference materials (needs a source before it can go live)`);
        await write(join(SCOUT_OUT, "proposed", `${record.id}.json`), `${JSON.stringify(record, null, 2)}
`);
        drafted.push({ id: record.id, title: c.title, url: c.url });
      } catch (error) {
        mark(id, "failed");
        notes.push(`${c.title}: ${message(error)}`);
      }
    }
    await write(SCOUT_STATE, `${JSON.stringify(seen, null, 2)}
`);
    const text = [report({ retired, drafted, suggested, blocked: all.filter(blocked).length, wouldJoin: join_ ? void 0 : wouldJoin }), ...notes.length ? ["Notes", ...notes.map((n) => `- ${n}`)] : []].join("\n");
    await write(join(SCOUT_OUT, "report.txt"), text);
    console.log(text);
    return text;
  } catch (error) {
    await write(join(SCOUT_OUT, "report.txt"), `Campaign scout failed: ${message(error)}`).catch(() => void 0);
    throw error;
  } finally {
    await page.close().catch(() => void 0);
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const run = promisify(execFile);
  const real = {
    async openPage() {
      const browser = await chromium.launch({ executablePath: process.env.CR_CHROME || void 0 });
      const page = await (await browser.newContext({ storageState: process.env.CR_SESSION_FILE })).newPage();
      const close = page.close.bind(page);
      page.close = async (...args) => {
        await close(...args).catch(() => void 0);
        await browser.close();
      };
      return page;
    },
    fetchJson: async (url) => (await fetch(url, { signal: AbortSignal.timeout(2e4) })).json(),
    fetchPublic: async (url) => (await fetch(url, { signal: AbortSignal.timeout(2e4) })).text(),
    async fetchCampaign(id) {
      const state = await readJson(process.env.CR_SESSION_FILE ?? "");
      const cookie = (state.cookies ?? []).filter((c) => c.domain.endsWith("contentrewards.com")).map((c) => `${c.name}=${c.value}`).join("; ");
      const res = await fetch(`https://contentrewards.com/api/campaign/campaigns/${id}`, { headers: { cookie }, signal: AbortSignal.timeout(2e4) });
      if (!res.ok) throw new Error(`campaign details HTTP ${res.status}`);
      return res.json();
    },
    ask: async (prompt) => (await run("claude", ["-p", prompt, "--model", process.env.SCOUT_MODEL || "claude-haiku-5-5"], { timeout: 18e4, maxBuffer: 1e7 })).stdout,
    now: Date.now
  };
  const renewSession = async () => {
    const file = process.env.CR_SESSION_FILE;
    if (!file) return;
    const page = await real.openPage();
    try {
      await page.goto("https://contentrewards.com/c/dashboard", { waitUntil: "domcontentloaded", timeout: 6e4 });
      if (page.url().includes("/login")) throw new Error("Content Rewards session expired: run npm run cr:connect and update the CR_SESSION secret");
      await page.context().storageState({ path: file });
    } finally {
      await page.close();
    }
  };
  await renewSession().then(() => scout(process.env, real)).catch((error) => {
    console.error(`Campaign scout failed: ${message(error)}`);
    process.exitCode = 1;
  });
}
export {
  scout
};
