import { createRequire as __autobizCreateRequire } from 'node:module'; const require = __autobizCreateRequire(import.meta.url);

// scripts/content-rewards-submit.ts
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
var CAMPAIGN = /^https:\/\/contentrewards\.com\/c\/campaigns\/[0-9a-f-]{36}$/i;
var ERROR = /can['’]t|invalid|already|\bnot\b|error|failed/i;
var ITEM_MS = 9e4;
async function submitClip(page, campaignUrl, clipUrl, shot) {
  try {
    await page.goto(campaignUrl, { waitUntil: "domcontentloaded", timeout: 3e4 });
    const open = page.getByRole("button", { name: "Submit clip", exact: true });
    const signIn = page.getByRole("link", { name: "Sign in" });
    await open.or(signIn).first().waitFor({ timeout: 3e4 });
    if (page.url().includes("/login") || await signIn.count()) return { submitted: false, reason: "logged out" };
    await open.click();
    const dialog = page.getByRole("dialog");
    const hold = dialog.getByRole("button", { name: "Hold to confirm" });
    const box = await hold.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.waitForTimeout(1600);
    await page.mouse.up();
    await dialog.locator("input[type=url]").fill(clipUrl, { timeout: 1e4 });
    await dialog.locator("input[type=checkbox]").check();
    const before = new Set((await dialog.innerText()).split("\n").map((line) => line.trim()));
    await dialog.getByRole("button", { name: "Submit clip", exact: true }).click();
    for (const end = Date.now() + 2e4; Date.now() < end; await page.waitForTimeout(250)) {
      if (!await dialog.isVisible()) return { submitted: true };
      const added = (await dialog.innerText()).split("\n").map((line) => line.trim()).filter((line) => line && !before.has(line)).join(" ");
      if (ERROR.test(added)) return { submitted: false, reason: added.replace(/\s+/g, " ").slice(0, 300) };
      if (/submitted|success/i.test(added)) return { submitted: true };
    }
    return { submitted: false, reason: "no response from the site after Submit (still open after 20 s)" };
  } catch (error) {
    return { submitted: false, reason: (error instanceof Error ? error.message : String(error)).split("\n")[0].slice(0, 300) };
  } finally {
    if (shot) await page.screenshot({ path: shot }).catch(() => void 0);
  }
}
async function submitAll(env) {
  const { CR_SESSION_FILE, CR_CAMPAIGN_URL = "", PUBLISHED, CR_RESULT_FILE, CR_SHOTS_DIR } = env;
  const items = JSON.parse(await readFile(PUBLISHED, "utf8"));
  const results = [];
  const valid = CAMPAIGN.test(CR_CAMPAIGN_URL);
  const browser = valid && items.some(({ url }) => url.startsWith("https://")) ? await chromium.launch().catch(() => void 0) : void 0;
  try {
    const context = browser && await browser.newContext({ storageState: CR_SESSION_FILE });
    if (CR_SHOTS_DIR) await mkdir(CR_SHOTS_DIR, { recursive: true });
    for (const [index, { platform, url }] of items.entries()) {
      let result;
      if (!url.startsWith("https://")) result = { submitted: false, reason: "not an https URL" };
      else if (!valid) result = { submitted: false, reason: "bad campaign URL" };
      else if (!context) result = { submitted: false, reason: "browser did not start" };
      else {
        const page = await context.newPage();
        let timer;
        result = await Promise.race([
          submitClip(page, CR_CAMPAIGN_URL, url, CR_SHOTS_DIR && join(CR_SHOTS_DIR, `${index}.png`)),
          new Promise((resolve) => {
            timer = setTimeout(() => resolve({ submitted: false, reason: "timed out" }), ITEM_MS);
          })
        ]);
        clearTimeout(timer);
        await page.close().catch(() => void 0);
      }
      results.push({ platform, url, ...result });
    }
  } finally {
    await browser?.close().catch(() => void 0);
    await writeFile(CR_RESULT_FILE, JSON.stringify(results));
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await submitAll(process.env).catch((error) => console.error(`Content Rewards submit failed: ${error instanceof Error ? error.message : error}`));
}
export {
  submitAll,
  submitClip
};
