// Consent belongs to this window's bundled renderer, never an external page.
function createMediaPermissionHandlers({ origin, webContents, ask }) {
    const granted = new Set();
    let pending = null;
    const trusted = (contents, permission, url, details = {}) => {
        try {
            return contents === webContents && !contents.isDestroyed() && permission === 'media' &&
                details.isMainFrame !== false && new URL(url).origin === origin && new URL(contents.getURL()).origin === origin;
        } catch { return false; }
    };
    const typesFor = (details) => details.mediaTypes?.length ? details.mediaTypes : ['video', 'audio'];
    return {
        check(contents, permission, requestingOrigin, details = {}) {
            if (!trusted(contents, permission, requestingOrigin, details)) return false;
            return details.mediaType === 'audio' || details.mediaType === 'video' ?
                granted.has(details.mediaType) : granted.has('video') && granted.has('audio');
        },
        async request(contents, permission, callback, details = {}) {
            if (!trusted(contents, permission, details.requestingUrl, details)) return callback(false);
            const types = typesFor(details);
            if (types.some(type => !['audio', 'video'].includes(type))) return callback(false);
            try {
                if (!types.every(type => granted.has(type))) {
                    // Chromium may request camera and microphone concurrently.
                    if (!pending) {
                        pending = Promise.resolve().then(ask).then(allowed => {
                            if (allowed && trusted(contents, permission, details.requestingUrl, details)) {
                                // The dialog explicitly requests consent for both devices.
                                granted.add('video'); granted.add('audio');
                            }
                        });
                    }
                    const consent = pending;
                    try { await consent; } finally { if (pending === consent) pending = null; }
                }
                callback(trusted(contents, permission, details.requestingUrl, details) && types.every(type => granted.has(type)));
            } catch { callback(false); }
        },
    };
}
module.exports = { createMediaPermissionHandlers };
