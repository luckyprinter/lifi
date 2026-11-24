import { chromium } from 'playwright';
import { preview } from 'vite';
import { mkdir } from 'node:fs/promises';

const widths = [320, 360, 390, 430, 768, 1024, 1366];
const output = 'artifacts';
await mkdir(output, { recursive: true });

const server = await preview({
  preview: { host: '127.0.0.1', port: 4173, strictPort: true },
});
const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
const failures = [];

try {
  for (const width of widths) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, deviceScaleFactor: 1 });
    page.on('pageerror', error => failures.push(width + 'px JavaScript error: ' + error.message));
    await page.goto('http://127.0.0.1:4173/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.academy-header');
    await page.waitForTimeout(180);

    const initial = await page.evaluate(() => ({
      innerWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
    }));
    if (initial.innerWidth !== width) failures.push(width + 'px viewport mismatch: ' + initial.innerWidth);
    if (initial.documentWidth > width + 1 || initial.bodyWidth > width + 1) {
      failures.push(width + 'px home horizontal overflow: document=' + initial.documentWidth + ', body=' + initial.bodyWidth);
    }
    if (width <= 720 && !(await page.locator('.mobile-menu').isVisible())) failures.push(width + 'px mobile menu is not visible');
    if (width > 720 && !(await page.getByRole('button', { name: 'CODE STUDIO', exact: true }).isVisible())) failures.push(width + 'px desktop navigation is not visible');
    await page.screenshot({ path: output + '/home-' + width + '.png', fullPage: true });

    if (width <= 720) await page.locator('.mobile-menu').click();
    await page.getByRole('button', { name: 'SIGNAL JOURNEY', exact: true }).click();
    await page.waitForSelector('.stage-visual');
    if (await page.locator('.stage-rail button').count() !== 8) failures.push(width + 'px signal journey does not expose all eight stages');
    await page.locator('.stage-rail button').nth(7).click();
    await page.waitForTimeout(380);
    const stageWidth = await page.locator('.journey-content').evaluate(el => el.getBoundingClientRect().width);
    if (stageWidth > width + 1) failures.push(width + 'px journey panel exceeds viewport: ' + stageWidth);
    const journeyScroll = await page.evaluate(() => document.documentElement.scrollWidth);
    if (journeyScroll > width + 1) failures.push(width + 'px journey horizontal overflow: ' + journeyScroll);
    if ([360, 390, 768, 1366].includes(width)) await page.screenshot({ path: output + '/journey-' + width + '.png', fullPage: true });
    await page.locator('.open-code-stage').click();
    await page.waitForSelector('.source-map-section');
    if (!(await page.locator('.code-lesson-head h3').innerText()).includes('Validate a complete frame')) failures.push(width + 'px journey stage did not open its matching code lesson');

    if (width <= 720) await page.locator('.mobile-menu').click();
    await page.getByRole('button', { name: 'CODE STUDIO' }).click();
    await page.waitForSelector('.source-map-section');
    await page.locator('.editor-line').nth(1).click();
    const lineExplain = await page.locator('.editor-explain p').innerText();
    if (!lineExplain.trim()) failures.push(width + 'px code line explanation is empty');
    const codeScroll = await page.evaluate(() => document.documentElement.scrollWidth);
    if (codeScroll > width + 1) failures.push(width + 'px code studio horizontal overflow: ' + codeScroll);
    if ([360, 390, 768, 1366].includes(width)) await page.screenshot({ path: output + '/code-' + width + '.png', fullPage: true });

    if (width <= 720) await page.locator('.mobile-menu').click();
    await page.getByRole('button', { name: 'LEARNING PATHS', exact: true }).click();
    await page.locator('.path-card').first().click();
    await page.waitForSelector('.focused-lesson');
    await page.getByRole('button', { name: /MARK LESSON COMPLETE/ }).click();
    const progress = await page.locator('.path-detail-hero').innerText();
    if (!progress.includes('1 OF 4')) failures.push(width + 'px lesson progress did not update');
    const pathScroll = await page.evaluate(() => document.documentElement.scrollWidth);
    if (pathScroll > width + 1) failures.push(width + 'px focused lesson horizontal overflow: ' + pathScroll);
    if ([360, 390, 768, 1366].includes(width)) await page.screenshot({ path: output + '/lesson-' + width + '.png', fullPage: true });

    await page.close();
  }
} finally {
  await browser.close();
  await new Promise(resolve => server.httpServer.close(resolve));
}

if (failures.length) {
  console.error('Responsive visual smoke test failures:');
  for (const failure of failures) console.error('- ' + failure);
  process.exitCode = 1;
} else {
  console.log('Responsive visual smoke tests passed at ' + widths.join(', ') + ' CSS pixels.');
}
