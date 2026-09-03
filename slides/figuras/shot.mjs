// Screenshots the three figures served from dist/ (see render.sh). Element screenshots of #root,
// so the PNG is exactly the Cloudscape container, at 2x for the projector.
import { chromium } from "playwright";

const FIGS = [["chaos", "chaos-v1-vs-v2.png"], ["matrix", "redteam-matrix.png"], ["capas", "capas-tabla.png"]];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 992, height: 700 }, deviceScaleFactor: 2 });
for (const [fig, out] of FIGS) {
  await page.goto(`http://127.0.0.1:4173/?fig=${fig}`, { waitUntil: "networkidle" });
  await page.waitForSelector("#root svg, #root table");
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  await page.locator("#root").screenshot({ path: `../assets/${out}` });
  console.log(`wrote slides/assets/${out}`);
}
await browser.close();
