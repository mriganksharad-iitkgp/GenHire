// Minimal in-memory fake of the Google Cloud Storage JSON API: just the calls
// python-backend/services/gcs_service.py makes (upload, download, delete,
// signed-URL fetch) plus a stub OAuth token endpoint.
import http from 'node:http';
import { randomUUID } from 'node:crypto';

export function startFakeGcs(port = 4443) {
  const objects = new Map();      // `${bucket}/${name}` -> { data, contentType }
  const resumable = new Map();    // id -> { bucket, name, contentType, chunks }
  const json = (res, code, body) => { res.writeHead(code, { 'content-type': 'application/json' }); res.end(JSON.stringify(body)); };
  const meta = (bucket, name, o) => ({ kind: 'storage#object', bucket, name, id: `${bucket}/${name}/1`, size: String(o.data.length), contentType: o.contentType, generation: '1' });
  const put = (bucket, name, data, contentType) => { objects.set(`${bucket}/${name}`, { data, contentType }); return meta(bucket, name, objects.get(`${bucket}/${name}`)); };

  const server = http.createServer(async (req, res) => {
    const chunks = []; for await (const c of req) chunks.push(c);
    const body = Buffer.concat(chunks);
    const url = new URL(req.url, `http://127.0.0.1:${port}`);
    const p = decodeURIComponent(url.pathname);
    res.setHeader('access-control-allow-origin', '*');
    if (req.method === 'OPTIONS') { res.writeHead(204, { 'access-control-allow-methods': '*', 'access-control-allow-headers': '*' }); return res.end(); }

    if (p === '/token') return json(res, 200, { access_token: 'fake', expires_in: 3600, token_type: 'Bearer' });

    let m;
    if ((m = p.match(/^\/upload\/storage\/v1\/b\/([^/]+)\/o$/))) {
      const bucket = m[1]; const type = url.searchParams.get('uploadType');
      if (type === 'resumable') {
        const info = body.length ? JSON.parse(body.toString()) : {};
        const name = info.name || url.searchParams.get('name');
        const id = randomUUID();
        resumable.set(id, { bucket, name, contentType: info.contentType || 'application/octet-stream', chunks: [] });
        res.writeHead(200, { location: `http://127.0.0.1:${port}/resumable/${id}` }); return res.end();
      }
      if (type === 'media') return json(res, 200, put(bucket, url.searchParams.get('name'), body, req.headers['content-type']));
      // multipart/related: JSON metadata part + media part
      const boundary = /boundary=("?)([^";]+)\1/.exec(req.headers['content-type'] || '')[2];
      const parts = body.toString('latin1').split(`--${boundary}`).slice(1, -1);
      const [metaPart, mediaPart] = parts.map(s => Buffer.from(s, 'latin1'));
      const split = b => { const i = b.indexOf('\r\n\r\n'); return [b.subarray(0, i).toString(), b.subarray(i + 4, b.length - 2)]; };
      const [, metaBody] = split(metaPart); const [mediaHead, mediaBody] = split(mediaPart);
      const info = JSON.parse(metaBody.toString());
      const ct = /content-type:\s*([^\r\n]+)/i.exec(mediaHead)?.[1] || info.contentType;
      return json(res, 200, put(bucket, info.name, mediaBody, ct));
    }
    if ((m = p.match(/^\/resumable\/(.+)$/))) {
      const s = resumable.get(m[1]); if (!s) return json(res, 404, {});
      s.chunks.push(body);
      const range = req.headers['content-range'] || '';
      const total = /\/(\d+|\*)$/.exec(range)?.[1];
      if (total && total !== '*') { resumable.delete(m[1]); return json(res, 200, put(s.bucket, s.name, Buffer.concat(s.chunks), s.contentType)); }
      res.writeHead(308, { range: `bytes=0-${Buffer.concat(s.chunks).length - 1}` }); return res.end();
    }
    if ((m = p.match(/^\/(?:download\/)?storage\/v1\/b\/([^/]+)\/o\/(.+)$/))) {
      const o = objects.get(`${m[1]}/${m[2]}`);
      if (req.method === 'DELETE') { if (!o) return json(res, 404, {}); objects.delete(`${m[1]}/${m[2]}`); res.writeHead(204); return res.end(); }
      if (!o) return json(res, 404, { error: { code: 404, message: 'Not Found' } });
      if (url.searchParams.get('alt') === 'media') { res.writeHead(200, { 'content-type': o.contentType }); return res.end(o.data); }
      return json(res, 200, meta(m[1], m[2], o));
    }
    if ((m = p.match(/^\/([^/]+)\/(.+)$/)) && req.method === 'GET') {   // signed-URL download
      const o = objects.get(`${m[1]}/${m[2]}`);
      if (!o) return json(res, 404, { error: 'not found' });
      res.writeHead(200, { 'content-type': o.contentType, 'content-length': o.data.length }); return res.end(o.data);
    }
    json(res, 404, { error: `unhandled ${req.method} ${p}` });
  });
  return new Promise(r => server.listen(port, '127.0.0.1', () => r({ server, objects, close: () => server.close() })));
}

