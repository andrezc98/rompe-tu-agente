// Screenshots the figures served from dist/ (see render.sh). Element screenshots of #root, so the
// PNG is exactly the Cloudscape container, at 3x for the projector. Width is CSS px: narrower
// means larger text once the image fills the slide.
import { chromium } from "playwright";

const FIGS = [
  ["chaos-v1", 960, "chaos-v1.png"],
  ["chaos-v2", 960, "chaos-v2.png"],
  ["matrix", 900, "redteam-matrix.png"],
  ["capas", 992, "capas-tabla.png"],
  ["escena-pregunta", 760, "escena-pregunta.png"],
  ["escena-timeout", 1180, "escena-timeout.png"],
  ["capas-diagrama", 1000, "capas-diagrama.png"],
];
const TRANSPARENT = new Set(["capas-diagrama", "chaos-v1", "chaos-v2"]); // the slide supplies the navy
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1300, height: 900 }, deviceScaleFactor: 3 });
for (const [fig, width, out] of FIGS) {
  await page.goto(`http://127.0.0.1:4173/?fig=${fig}&w=${width}`, { waitUntil: "networkidle" });
  await page.waitForSelector("#root svg, #root table, #root [class*=chat-bubble]");
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);
  await page.locator("#root").screenshot({ path: `../assets/${out}`, omitBackground: TRANSPARENT.has(fig) });
  console.log(`wrote slides/assets/${out}`);
}
await browser.close();
