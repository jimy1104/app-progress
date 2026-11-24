// Minimal static file server for Azure App Service (Linux, Node). No dependencies.
// App Service runs `npm start` automatically and gives the port in process.env.PORT.
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const PORT = process.env.PORT || 8080;
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.ico': 'image/x-icon', '.srt': 'text/plain; charset=utf-8', '.vtt': 'text/vtt; charset=utf-8', '.ass': 'text/plain; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8', '.mp4': 'video/mp4', '.webm': 'video/webm', '.mp3': 'audio/mpeg', '.zip': 'application/zip',
};
const BLOCKED = new Set(['server.js', 'package.json', 'web.config']);

// ---------------------------------------------------------------- YouTube subtitles (best effort)
// The browser cannot read YouTube captions (CORS), so the server asks YouTube's player API for the
// caption tracks and downloads the English one (or a machine translation into ?tlang=xx).
const YT_CLIENT = { clientName: 'ANDROID', clientVersion: '20.10.38', androidSdkVersion: 34, hl: 'en', gl: 'US' };
const YT_UA = 'com.google.android.youtube/20.10.38 (Linux; U; Android 14) gzip';
const ytCache = new Map();
async function youtubeSubs(videoId, lang, tlang) {
  const key = `${videoId}|${lang}|${tlang}`;
  if (ytCache.has(key)) return ytCache.get(key);
  const r = await fetch('https://www.youtube.com/youtubei/v1/player?prettyPrint=false', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'user-agent': YT_UA, 'x-youtube-client-name': '3', 'x-youtube-client-version': YT_CLIENT.clientVersion },
    body: JSON.stringify({ context: { client: YT_CLIENT }, videoId, contentCheckOk: true, racyCheckOk: true }),
  });
  if (!r.ok) throw new Error('YouTube player API ' + r.status);
  const data = await r.json();
  const tracks = (((data.captions || {}).playerCaptionsTracklistRenderer || {}).captionTracks) || [];
  if (!tracks.length) { const e = new Error('This video has no subtitles'); e.status = 404; throw e; }
  const pick = l => tracks.find(t => t.languageCode.startsWith(l) && t.kind !== 'asr') || tracks.find(t => t.languageCode.startsWith(l));
  const want = pick(tlang || lang);
  const base = want || pick(lang) || tracks.find(t => t.kind !== 'asr') || tracks[0];
  let url = base.baseUrl.replace(/&fmt=[^&]*/, '') + '&fmt=json3';
  if (!want) url += '&tlang=' + encodeURIComponent(tlang || lang);
  const s = await fetch(url, { headers: { 'user-agent': YT_UA } });
  const text = await s.text();
  if (!s.ok || text.length < 30) throw new Error('YouTube refused the subtitle download');
  const label = (base.name && (base.name.simpleText || (base.name.runs || []).map(x => x.text).join(''))) || base.languageCode;
  const out = { text, label: label + (base.kind === 'asr' ? ' (auto)' : '') + (want ? '' : ' → ' + (tlang || lang)) };
  ytCache.set(key, out);
  if (ytCache.size > 200) ytCache.delete(ytCache.keys().next().value);
  return out;
}

http.createServer((req, res) => {
  if (req.url.startsWith('/api/yt-subs')) {
    const q = new URL(req.url, 'http://x').searchParams;
    const v = q.get('v') || ''; const lang = (q.get('lang') || 'en').slice(0, 5); const tlang = (q.get('tlang') || '').slice(0, 5);
    const send = (code, obj) => { res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(obj)); };
    if (!/^[\w-]{6,20}$/.test(v) || !/^[a-z]{2}(-[A-Za-z]{2})?$/.test(lang) || (tlang && !/^[a-z]{2}(-[A-Za-z]{2})?$/.test(tlang))) return send(400, { error: 'bad request' });
    youtubeSubs(v, lang, tlang).then(r => send(200, r)).catch(e => send(e.status || 502, { error: String(e.message || e) }));
    return;
  }
  let urlPath;
  try { urlPath = decodeURIComponent(new URL(req.url, 'http://x').pathname); } catch { res.writeHead(400); return res.end(); }
  if (urlPath.endsWith('/')) urlPath += 'index.html';
  const file = path.normalize(path.join(ROOT, urlPath));
  const rel = path.relative(ROOT, file);
  if (rel.startsWith('..') || path.isAbsolute(rel) || rel.split(path.sep).some(p => p.startsWith('.')) || BLOCKED.has(rel)) {
    res.writeHead(404); return res.end('Not found');
  }
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) { res.writeHead(404, { 'Content-Type': 'text/plain' }); return res.end('Not found'); }
    res.writeHead(200, {
      'Content-Type': TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream',
      'Content-Length': st.size,
      'Cache-Control': rel === 'index.html' ? 'no-cache' : 'public, max-age=3600',
      'Permissions-Policy': 'microphone=(self), autoplay=(self), fullscreen=(self)',
      'X-Content-Type-Options': 'nosniff',
    });
    if (req.method === 'HEAD') return res.end();
    fs.createReadStream(file).pipe(res);
  });
}).listen(PORT, () => console.log(`EnglishPro listening on ${PORT}`));
