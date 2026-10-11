const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createMediaPermissionHandlers } = require('../media-permissions');

const origin = 'http://localhost:32199';
function fixture(ask) {
    const contents = { getURL: () => `${origin}/index.html`, isDestroyed: () => false };
    const handlers = createMediaPermissionHandlers({ origin, webContents: contents, ask });
    const request = (details = {}) => new Promise(resolve => handlers.request(contents, 'media', resolve,
        { requestingUrl: `${origin}/index.html`, mediaTypes: ['video', 'audio'], isMainFrame: true, ...details }));
    return { contents, handlers, request };
}
test('camera and microphone require consent once per window and allow device retries', async () => {
    let asks = 0;
    const { contents, handlers, request } = fixture(async () => { asks++; return true; });
    assert.equal(handlers.check(contents, 'media', origin, { mediaType: 'video' }), false);
    assert.equal(await request(), true);
    assert.equal(handlers.check(contents, 'media', origin, { mediaType: 'video' }), true);
    assert.equal(handlers.check(contents, 'media', origin, { mediaType: 'audio' }), true);
    assert.equal(await request(), true); assert.equal(asks, 1);
});
test('declining access allows another explicit request without granting permissions', async () => {
    let allow = false;
    const { contents, handlers, request } = fixture(async () => allow);
    assert.equal(await request(), false);
    assert.equal(handlers.check(contents, 'media', origin), false);
    allow = true; assert.equal(await request(), true);
});
test('untrusted frames and unrelated permissions cannot trigger or inherit device access', async () => {
    let asks = 0;
    const { contents, handlers, request } = fixture(async () => { asks++; return true; });
    for (const requestingUrl of ['https://evil.test', `${origin}.evil.test`, 'file:///index.html']) assert.equal(await request({ requestingUrl }), false);
    assert.equal(await request({ isMainFrame: false }), false);
    assert.equal(asks, 0);
    await request();
    assert.equal(handlers.check(contents, 'notifications', origin), false);
    assert.equal(handlers.check(null, 'media', origin), false);
    assert.equal(handlers.check(contents, 'media', 'https://evil.test'), false);
});
test('simultaneous media requests share a prompt and closing or navigating the window denies the result', async () => {
    let accept; let asks = 0;
    const { contents, request } = fixture(() => { asks++; return new Promise(resolve => { accept = resolve; }); });
    const first = request(), second = request();
    await Promise.resolve(); accept(true); assert.deepEqual(await Promise.all([first, second]), [true, true]); assert.equal(asks, 1);
    const next = fixture(() => new Promise(resolve => { accept = resolve; }));
    const pending = next.request(); await Promise.resolve(); next.contents.getURL = () => 'https://evil.test'; accept(true);
    assert.equal(await pending, false);
    contents.isDestroyed = () => true; assert.equal(await request(), false);
});
test('declining simultaneous requests does not show a second popup', async () => {
    let decline; let asks = 0;
    const { request } = fixture(() => { asks++; return new Promise(resolve => { decline = resolve; }); });
    const requests = [request(), request()]; await Promise.resolve(); decline(false);
    assert.deepEqual(await Promise.all(requests), [false, false]); assert.equal(asks, 1);
});
