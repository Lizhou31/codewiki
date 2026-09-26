/* Optional browser regression check: build the self-wiki, then run with Node
 * and Playwright (including Chromium) installed: node tests/browser/diagrams.cjs.
 */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');

(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const site = path.resolve(__dirname, '../../codewiki/site');
    const open = async name => {
      await page.goto(pathToFileURL(path.join(site, name)).href);
      await page.waitForSelector('.diagram-controls output');
    };
    await open('architecture.html');
    const canvas = page.locator('.diagram-viewport').first();
    const wrap = page.locator('.mermaid-wrap').first();
    const svg = canvas.locator('svg');
    const view = () => svg.getAttribute('viewBox');
    const initial = await view();
    const zoomIn = wrap.getByRole('button', {name: 'Zoom in', exact: true});
    const zoomOut = wrap.getByRole('button', {name: 'Zoom out', exact: true});
    const fit = wrap.getByRole('button', {name: 'Fit diagram', exact: true});
    await zoomIn.click();
    assert.equal(await wrap.locator('output').textContent(), '125%');
    assert.notEqual(await view(), initial);
    await fit.click();
    assert.equal(await view(), initial);

    // Zoom must keep the SVG point beneath the mouse stationary.
    await canvas.scrollIntoViewIfNeeded();
    const rect = await canvas.boundingBox();
    const mouse = {x: rect.x + rect.width * 0.65, y: rect.y + rect.height * 0.4};
    const svgPoint = () => svg.evaluate((el, position) => {
      const p = el.createSVGPoint();
      p.x = position.x; p.y = position.y;
      const result = p.matrixTransform(el.getScreenCTM().inverse());
      return {x: result.x, y: result.y};
    }, mouse);
    const before = await svgPoint();
    await page.mouse.move(mouse.x, mouse.y);
    await page.mouse.wheel(0, -100);
    await page.waitForFunction(() => document.querySelector('.diagram-controls output').textContent !== '100%');
    const after = await svgPoint();
    assert.ok(Math.abs(before.x - after.x) < 0.1 && Math.abs(before.y - after.y) < 0.1);

    // Drag from a linked node without activating it; an ordinary click still works.
    await fit.click();
    const link = canvas.locator('a').first();
    const target = await link.getAttribute('href');
    const node = await link.boundingBox();
    const startURL = page.url();
    await page.mouse.move(node.x + node.width / 2, node.y + node.height / 2);
    await page.mouse.down();
    await page.mouse.move(node.x + node.width / 2 + 60, node.y + node.height / 2 + 30, {steps: 8});
    await page.mouse.up();
    assert.equal(page.url(), startURL);
    assert.notEqual(await view(), initial);
    assert.equal(await canvas.evaluate(el => el.classList.contains('is-panning')), false);
    const moved = await view();
    await wrap.getByRole('button', {name: 'Expand diagram', exact: true}).click();
    assert.equal(await view(), moved);
    assert.equal(await page.locator('dialog').first().evaluate(el => el.open), true);
    await zoomIn.click();
    const expanded = await view();
    await page.keyboard.press('Escape');
    assert.equal(await view(), expanded);
    assert.equal(await page.locator('dialog').first().evaluate(el => el.open), false);
    await fit.click();
    await link.click();
    assert.equal(page.url(), new URL(target, startURL).href);

    await open('architecture.html');
    await canvas.focus();
    await page.keyboard.press('+');
    assert.equal(await wrap.locator('output').textContent(), '125%');
    const beforeKey = await view();
    await page.keyboard.press('ArrowRight');
    assert.notEqual(await view(), beforeKey);
    await page.keyboard.press('0');
    assert.equal(await view(), initial);
    for (let i = 0; i < 15 && await zoomIn.isEnabled(); i++) await zoomIn.click();
    assert.equal(await wrap.locator('output').textContent(), '800%');
    assert.equal(await zoomIn.isEnabled(), false);
    for (let i = 0; i < 25 && await zoomOut.isEnabled(); i++) await zoomOut.click();
    assert.equal(await wrap.locator('output').textContent(), '25%');
    assert.equal(await zoomOut.isEnabled(), false);

    await page.setViewportSize({width: 390, height: 844});
    await open('architecture-ch_tw.html');
    assert.equal(await wrap.getByRole('button', {name: '放大', exact: true}).count(), 1);
    const bounds = await canvas.boundingBox();
    const svgBounds = await svg.boundingBox();
    assert.ok(bounds.width <= 390 && Math.abs(svgBounds.width - bounds.width) < 1);
    assert.ok(Math.abs(svgBounds.height - bounds.height) < 1);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await wrap.getByRole('button', {name: '展開圖表', exact: true}).click();
    const mobileView = await view();
    await wrap.getByRole('button', {name: '放大', exact: true}).click();
    assert.notEqual(await view(), mobileView);
    await page.keyboard.press('Escape');

    // Native touch input pans the same viewport.
    const touchPage = await browser.newPage({viewport: {width: 390, height: 844}, hasTouch: true, isMobile: true});
    await touchPage.goto(pathToFileURL(path.join(site, 'architecture.html')).href);
    const touchCanvas = touchPage.locator('.diagram-viewport').first();
    await touchCanvas.waitFor();
    await touchCanvas.scrollIntoViewIfNeeded();
    const touchBox = await touchCanvas.boundingBox();
    const touchSvg = touchCanvas.locator('svg');
    const touchInitial = await touchSvg.getAttribute('viewBox');
    const cdp = await touchPage.context().newCDPSession(touchPage);
    const x = touchBox.x + touchBox.width / 2, y = touchBox.y + touchBox.height / 2;
    await cdp.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [{x, y}]});
    await cdp.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: [{x: x + 50, y: y + 30}]});
    await cdp.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
    assert.notEqual(await touchSvg.getAttribute('viewBox'), touchInitial);
    assert.deepEqual(errors, []);
    console.log('Diagram browser checks passed: zoom, pointer anchoring, linked-node drag/click, dialog state, keyboard, limits, mobile layout, localization, touch.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
