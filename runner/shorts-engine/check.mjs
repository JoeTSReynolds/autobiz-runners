// Load a compiled Short in Chromium and run its own checks (storyboard slots, anchors, pacing, holds).
// Prints "checks ok, N sound cues" and writes sfx-cues.json, or exits 1 printing "page errors: ...".
// Usage: node check.mjs <project-dir>
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { chromium } from 'playwright'

const root = resolve(process.argv[2])
const browser = await chromium.launch()
try {
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } })
  await page.addInitScript('window.__timelines = {};')
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e.message ?? e)))
  // audio is checked by HyperFrames; sfx.wav is made after this step
  page.on('requestfailed', (r) => r.resourceType() !== 'media' && errors.push(`missing file: ${r.url()}`))
  await page.goto(pathToFileURL(`${root}/index.html`).href)
  await page.waitForTimeout(1500)
  if (errors.length) {
    console.log(`page errors: ${errors.join('; ')}`)
    process.exitCode = 1
  } else {
    const sfx = await page.evaluate('window.SFX')
    if (!sfx) {
      console.log('page errors: the page did not export window.SFX (kit.pace not called?)')
      process.exitCode = 1
    } else {
      writeFileSync(`${root}/sfx-cues.json`, JSON.stringify(sfx, null, 1))
      console.log(`checks ok, ${sfx.cues.length} sound cues`)
    }
  }
} finally {
  await browser.close()
}
