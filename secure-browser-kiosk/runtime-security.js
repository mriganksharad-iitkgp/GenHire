const path = require('path');

function resolvePublicFile(root, requestUrl) {
    try {
        // Decode before normalization so encoded traversal cannot evade checks.
        const pathname = decodeURIComponent(String(requestUrl).split('?')[0]);
        const resource = pathname === '/' ? '/index.html' : pathname;
        if (resource !== '/index.html' && !/^\/assets\/[a-zA-Z0-9_-]+\.(?:js|css|svg|png|woff2?)$/.test(resource)) return null;
        const publicRoot = path.resolve(root, 'web-app');
        const target = path.resolve(publicRoot, `.${resource}`);
        return target.startsWith(`${publicRoot}${path.sep}`) ? target : null;
    } catch { return null; }
}

function validWebUrl(value) {
    try {
        const url = new URL(value);
        return !url.username && !url.password && (url.protocol === 'https:' ||
            (url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)));
    } catch { return false; }
}

function parseInitialization(encoded) {
    if (typeof encoded !== 'string' || encoded.length > 100000) throw new Error('Invalid launch link');
    const payload = JSON.parse(Buffer.from(encoded, 'base64').toString('utf8'));
    if (!payload || typeof payload.token !== 'string' || !payload.token || !validWebUrl(payload.apiUrl)) {
        throw new Error('Launch this app from your GenHire dashboard.');
    }
    if (!validWebUrl(payload.webOrigin)) throw new Error('Invalid dashboard address');
    return payload;
}

module.exports = { resolvePublicFile, validWebUrl, parseInitialization };
