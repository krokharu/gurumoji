/* 合成データだけで時間軸の倍率操作と表示範囲を検証する。 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(process.argv[2]);
const output = path.resolve(process.argv[3]);
const {chromium} = require(path.join(root, 'output/validation/public-analysis-cleanup-tools/node_modules/playwright'));

(async () => {
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 900}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const template = fs.readFileSync(path.join(root, 'src/gurumoji/templates/views/result.html'), 'utf8');
    const section = template.match(/<section id="speaker-timeline"[\s\S]*?<\/section>/)[0];
    const css = fs.readFileSync(path.join(root, 'src/gurumoji/static/speaker-timeline.css'), 'utf8');
    await page.setContent(`<meta charset="utf-8"><style>:root{--line:#ddd;--ink:#222;--muted:#666;--green:#247f60}body{margin:16px;font-family:sans-serif}*{box-sizing:border-box}${css}</style>${section}`);
    await page.addScriptTag({path: path.join(root, 'src/gurumoji/static/speaker-timeline.js')});
    await page.evaluate(() => {
      window.calls = [];
      window.job = {id: 'zoom-fixture', media_url: '/synthetic.wav', segments: [
        {id: 'a', speaker: 'A', start: 0, end: 100, text: '合成発話A'},
        {id: 'b', speaker: 'B', start: 400, end: 600, text: '合成発話B'},
      ]};
      window.timeline = GurumojiTimeline.create(document.querySelector('#speaker-timeline'), {
        follow: () => false, name: id => id, color: () => '#247f60',
        select: id => calls.push(['select', id]), seek: (time, play) => calls.push(['seek', time, play]),
      });
      timeline.render(job);
    });
    const disabled = id => page.locator('#timeline-' + id).isDisabled();
    const value = () => page.locator('#timeline-zoom').inputValue();
    const state = () => page.evaluate(() => {
      const vp = document.querySelector('#timeline-viewport');
      const width = parseFloat(document.querySelector('#timeline-canvas').style.getPropertyValue('--timeline-width'));
      const label = matchMedia('(max-width: 600px)').matches ? 104 : 152;
      return {width, center: (vp.scrollLeft + (vp.clientWidth - label) / 2) / width,
        scroll: vp.scrollLeft, overflow: vp.scrollWidth > vp.clientWidth + 1};
    });
    assert(await disabled('zoom-out'));
    assert(await disabled('zoom-fit'));
    assert(!(await disabled('zoom-in')));
    for (const expected of ['2', '4', '8', '16', '32']) {
      await page.locator('#timeline-zoom-in').click();
      assert.equal(await value(), expected);
    }
    assert(await disabled('zoom-in'));
    assert((await state()).overflow);
    await page.locator('#timeline-zoom').selectOption('8');
    await page.evaluate(() => {
      timeline.updateTime(12, 600);
      const vp = document.querySelector('#timeline-viewport');
      const width = parseFloat(document.querySelector('#timeline-canvas').style.getPropertyValue('--timeline-width'));
      vp.scrollLeft = width * 0.7 - (vp.clientWidth - 152) / 2;
    });
    const before = await state();
    await page.locator('#timeline-zoom-out').click();
    assert.equal(await value(), '4');
    assert(Math.abs((await state()).center - before.center) < 0.002, JSON.stringify({before, after: await state()}));
    await page.locator('#timeline-zoom').selectOption('16');
    assert(Math.abs((await state()).center - before.center) < 0.002);
    await page.locator('#timeline-zoom-fit').click();
    assert.equal(await value(), '1');
    assert.equal((await state()).scroll, 0);
    assert(!(await state()).overflow);
    await page.locator('[data-segment-id="b"]').click();
    assert.deepEqual(await page.evaluate(() => calls), [['select', 'b'], ['seek', 400, true]]);
    assert(await page.locator('[data-segment-id="b"]').getAttribute('aria-pressed') === 'true');
    await page.locator('#timeline-zoom-in').focus();
    await page.keyboard.press('Enter');
    assert.equal(await value(), '2');
    assert(await page.locator('#timeline-zoom-in').evaluate(el => document.activeElement === el));
    await page.locator('#timeline-zoom-fit').click();
    await page.locator('#speaker-timeline').screenshot({path: path.join(output, 'desktop.png')});
    for (const width of [390, 320]) {
      await page.setViewportSize({width, height: 844});
      await page.waitForTimeout(100);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert(!(await state()).overflow);
      await page.locator('#timeline-zoom-in').click();
      assert.equal(await value(), '2');
      await page.locator('#timeline-zoom-out').click();
      assert.equal(await value(), '1');
      await page.locator('#speaker-timeline').screenshot({path: path.join(output, `mobile-${width}.png`)});
    }
    await page.locator('#timeline-zoom-in').click();
    await page.evaluate(() => timeline.render({...job, id: 'other'}));
    assert.equal(await value(), '1');
    for (const segments of [[], [{id: 'zero', speaker: 'A', start: 0, end: 0, text: 'ゼロ秒'}]]) {
      await page.evaluate(segments => timeline.render({id: 'empty', segments}), segments);
      for (const id of ['zoom', 'zoom-in', 'zoom-out', 'zoom-fit']) assert(await disabled(id));
    }
    assert.deepEqual(errors, []);
    const result = {ok: true, checks: ['全体〜32倍の拡大・縮小と上下限', '倍率選択とボタンで表示中心を維持', '全体表示で横スクロールを解除', '発話選択・シーク', 'キーボードとフォーカス保持', '1440px・390px・320pxの表示', 'データ切替・空状態・0秒'], pageErrors: errors};
    fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
