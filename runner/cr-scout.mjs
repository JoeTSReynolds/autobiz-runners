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

// scripts/content-rewards-page.ts
var handled = /* @__PURE__ */ new WeakSet();
async function dismissAnnouncements(page) {
  if (handled.has(page)) return;
  handled.add(page);
  await page.addLocatorHandler(page.getByRole("button", { name: "Not now", exact: true }), (button) => button.click(), { noWaitAfter: true });
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
var TWITCH_RESERVED = /* @__PURE__ */ new Set(["videos", "directory", "downloads", "jobs", "settings", "store", "turbo", "search", "popout", "embed", "moderator", "friends", "subscriptions", "inventory", "wallet", "drops", "user", "p", "u"]);
var refUrls = (json) => (json?.data ?? json ?? {}).configuration?.referenceMaterial?.map((r) => String(r.url ?? "")) ?? [];
var hasKickSource = (json) => refUrls(json).some((u) => /^https?:\/\/(?:www\.)?kick\.com\//i.test(u));
function draftFromCampaign(json, candidate, channel) {
  const o = json?.data ?? json ?? {};
  const cfg = o.configuration ?? {}, caption = cfg.rules?.caption ?? {};
  const refs = cfg.referenceMaterial ?? [];
  const urls = refs.map((r) => String(r.url ?? ""));
  const sources = [];
  const title = String(o.name ?? "");
  const add = (s) => {
    if (s.id && !sources.some((x) => x.id === s.id)) sources.push(s);
  };
  for (const url of urls) {
    if (/(?:youtube\.com|youtu\.be)\//.test(url)) {
      add({ id: postKey(url), url, title, channel: "", duration: 0 });
      continue;
    }
    const vod = /^https?:\/\/(?:www\.|m\.)?twitch\.tv\/videos\/(\d+)/i.exec(url)?.[1];
    if (vod) {
      add({ id: vod, url, title, channel: "", duration: 0 });
      continue;
    }
    const login = /^https?:\/\/(?:www\.|m\.)?twitch\.tv\/(\w{3,25})(?:[/?#]|$)/i.exec(url)?.[1]?.toLowerCase();
    if (login && !TWITCH_RESERVED.has(login)) add({ id: login, url: `https://www.twitch.tv/${login}`, title, channel: login, duration: 0 });
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
async function joinCampaign(page, url, waitMs = 6e4) {
  try {
    await dismissAnnouncements(page);
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 3e4 });
    const submit = submitButton(page), join2 = page.getByRole("button", { name: "Join Campaign" }).first(), signIn = page.getByRole("link", { name: "Sign in" });
    await submit.or(join2).or(signIn).first().waitFor({ timeout: 3e4 });
    if (page.url().includes("/login") || await signIn.count()) return { joined: false, reason: "logged out" };
    if (await submit.count()) return { joined: true, already: true };
    await join2.click();
    let confirmed = false, clicked = Date.now();
    for (const end = Date.now() + waitMs; Date.now() < end; await page.waitForTimeout(250)) {
      if (await submit.count()) return { joined: true };
      if (!confirmed && Date.now() - clicked > 4e3 && await join2.isVisible()) {
        await join2.click();
        clicked = Date.now();
      }
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
async function fitCheck(candidates, ask, n = 5, lane = "podcast") {
  const top = candidates.slice(0, n);
  const intro = lane === "gaming" ? "Our pipeline makes YouTube Shorts and Instagram Reels from a named streamer's Twitch VODs, fully automated (no human editor): viewer-clip hotspots, a facecam-on-top and gameplay-below vertical layout, captions and a headline. For each campaign below, decide whether we can clip it. Accept Twitch VODs and channels, YouTube videos and streams, and supplied Drive footage. We post from a new page with few followers, and nobody appears or speaks on camera for us. Reject campaigns whose rules need any of: a logo or watermark kept on screen; our own voiceover or reactions; recording our own gameplay or footage; a Kick-only source (not supported yet); a specific sound or song; an existing or established account or a follower minimum; non-English content; saying or showing a link, discount code or call to action in the video. Also reject product promos and supplied ad footage (pack openings, app or store promos): the clips must be a streamer's own stream moments." : `Our pipeline makes YouTube Shorts and Instagram Reels from long-form video. For each campaign below, decide whether we can clip it well. Podcast lane: long-form talking-head video with clear speech. Reject gameplay, trailers, music videos, product demos without talking, and non-English content. We post from a new page with few followers, the clips are fully automated (no human editor), and nobody appears or speaks on camera for us. So also reject campaigns whose rules need any of: an existing or established account, or a follower minimum; the creator's face on camera, a voiceover or reactions; no automated or AI clipping; a brand logo or watermark kept on screen; a specific sound or song.`;
  const prompt = `${intro}

${top.map((c) => JSON.stringify({ id: c.id, title: c.title, categories: c.categories, description: c.description?.slice(0, 400), ...c.rules ? { rules: c.rules.slice(0, 1200) } : {} })).join("\n")}

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
function report({ retired, drafted, gamingDrafted, suggested, blocked: skipped, wouldJoin }) {
  const lines = [
    `Retired (${retired.length})`,
    ...retired.map((r) => `- ${r.id}: ${r.reason}`),
    `Joined and drafted (${drafted.length})`,
    ...drafted.map((d) => `- ${d.title} ${d.url}`),
    ...gamingDrafted ? [`Gaming joined and drafted (${gamingDrafted.length})`, ...gamingDrafted.map((d) => `- ${d.title} ${d.url}`)] : [],
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
    const gamingOn = env.SCOUT_GAMING === "1";
    const gamingFresh = fresh.filter((c) => routeChannel(c) === "gaming");
    const isPodcast = (c) => c.categories.some((n) => /podcast/i.test(n));
    const eligible = fresh.filter((c) => routeChannel(c) === "podcast" && passesMinimum(c)).sort((a, b) => Number(isPodcast(b)) - Number(isPodcast(a)));
    const mark = (id, verdict) => {
      seen[id] = { verdict, at: new Date(deps.now()).toISOString() };
    };
    const wouldJoin = [];
    const runLane = async (channel, list, max) => {
      const drafted = [], unfit = /* @__PURE__ */ new Set(), top = list.slice(0, 10);
      const details = /* @__PURE__ */ new Map();
      for (const c of top) {
        try {
          const json = await deps.fetchCampaign(c.id), r = draftFromCampaign(json, c, channel);
          details.set(c.id, json);
          c.rules = [...new Set([r.brief, r.requirements, r.checklist].filter(Boolean))].join("\n");
        } catch {
        }
      }
      const fits = top.length ? await fitCheck(top, deps.ask, 10, channel) : [];
      const judged = fits.filter((f) => f.reason !== "no valid verdict");
      if (top.length && judged.length < fits.length) notes.push(`Fit check gave no usable answer for ${fits.length - judged.length} of ${fits.length} campaigns; they will be asked again next run`);
      for (const f of judged.filter((f2) => !f2.fit)) {
        mark(f.id, "unfit");
        unfit.add(f.id);
        notes.push(`${top.find((x) => x.id === f.id).title}: not a fit (${f.reason})`);
      }
      for (const { id } of fits.filter((f) => f.fit).slice(0, max)) {
        const c = top.find((x) => x.id === id);
        if (!join_) {
          wouldJoin.push({ title: c.title, url: c.url });
          drafted.push({ id, title: c.title, url: c.url });
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
          const json = details.get(c.id) ?? await deps.fetchCampaign(c.id), record = draftFromCampaign(json, c, channel);
          if (hasKickSource(json)) notes.push(`${c.title}: Kick sources are not supported yet`);
          if (!record.sources.length) notes.push(`${c.title}: no usable source (YouTube or Twitch) in the reference materials (needs a source before it can go live)`);
          await write(join(SCOUT_OUT, "proposed", `${record.id}.json`), `${JSON.stringify(record, null, 2)}
`);
          drafted.push({ id: record.id, title: c.title, url: c.url });
        } catch (error) {
          mark(id, "failed");
          notes.push(`${c.title}: ${message(error)}`);
        }
      }
      return { drafted: join_ ? drafted : [], handled: /* @__PURE__ */ new Set([...unfit, ...drafted.map((d) => d.id)]), joinedUrls: new Set(drafted.map((d) => d.url)) };
    };
    const podcastRun = await runLane("podcast", eligible, maxJoins);
    let gamingDrafted, suggested = gamingFresh.slice(0, 5);
    if (gamingOn) {
      const maxViewsToMinimum = Number(env.SCOUT_GAMING_MAX_VIEWS ?? 1e4);
      const gamingEligible = gamingFresh.filter((c) => passesMinimum(c, { maxViewsToMinimum }));
      const run = await runLane("gaming", gamingEligible, Number(env.SCOUT_MAX_JOINS_GAMING ?? 2));
      gamingDrafted = run.drafted;
      suggested = gamingEligible.filter((c) => !run.joinedUrls.has(c.url) && !run.handled.has(c.id)).slice(0, 5);
    }
    await write(SCOUT_STATE, `${JSON.stringify(seen, null, 2)}
`);
    const text = [report({ retired, drafted: podcastRun.drafted, gamingDrafted, suggested, blocked: all.filter(blocked).length, wouldJoin: join_ ? void 0 : wouldJoin }), ...notes.length ? ["Notes", ...notes.map((n) => `- ${n}`)] : []].join("\n");
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
