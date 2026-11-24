// Runs in the page's own JavaScript world (MAIN), in every frame, before the page's scripts.
// It watches the network requests the video player makes and keeps a copy of any subtitle
// file it downloads (WebVTT, SRT, TTML/DFXP, YouTube json3/xml). It never changes them.
// On YouTube it also asks for the English caption track directly.
(() => {
  if (window.__englishProInject) return;
  window.__englishProInject = true;

  const found = new Map();       // id -> candidate
  const segGroups = new Map();   // HLS WebVTT segments grouped by folder
  const MAX = 6e6;
  const ofetch = window.fetch;

  function kind(text) {
    if (!text || text.length < 20 || text.length > MAX) return null;
    const h = text.slice(0, 800).replace(/^﻿/, '').trimStart();
    if (/^WEBVTT/.test(h)) return 'vtt';
    if (/^\d+\s*\r?\n\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}\s*-->/.test(h)) return 'srt';
    if (h[0] === '{' && /"events"\s*:/.test(text.slice(0, 4000)) && /"segs"/.test(text)) return 'json3';
    if (/<tt[\s>]/.test(text.slice(0, 3000)) && /\bbegin=/.test(text)) return 'ttml';
    if (/<transcript[\s>]|<timedtext[\s>]/.test(text.slice(0, 2000))) return 'ytxml';
    return null;
  }

  function langOf(url, extra) {
    if (extra && extra.lang) return extra.lang;
    try {
      const u = new URL(url, location.href);
      for (const k of ['tlang', 'lang', 'language', 'lan', 'srclang']) { const v = u.searchParams.get(k); if (v) return v.toLowerCase(); }
    } catch {}
    const m = String(url).toLowerCase().match(/(?:^|[\/_.\-=?&])(english|eng|en(?:-[a-z]{2})?|spanish|spa|es(?:-[a-z]{2})?|arabic|ara|ar|french|fre|fr|german|ger|de|portuguese|por|pt(?:-[a-z]{2})?|italian|ita|it)(?=[\/_.\-&?]|$)/);
    if (!m) return '';
    const map = { english: 'en', eng: 'en', spanish: 'es', spa: 'es', arabic: 'ar', ara: 'ar', french: 'fr', fre: 'fr', german: 'de', ger: 'de', portuguese: 'pt', por: 'pt', italian: 'it', ita: 'it' };
    return map[m[1]] || m[1];
  }

  function post(c) { try { window.postMessage({ __ep: 'subs', ...c }, '*'); } catch {} }

  function add(text, url, extra = {}) {
    const k = kind(text); if (!k) return;
    url = String(url || '');
    // Small WebVTT files from the same folder are HLS segments: merge them into one track.
    if (k === 'vtt' && (text.match(/-->/g) || []).length < 40 && /\.(webvtt|vtt)(\?|$)/i.test(url) && /seg|frag|\d{2,}\.(web)?vtt/i.test(url)) {
      const dir = url.replace(/[^\/]*$/, '');
      const g = segGroups.get(dir) || { parts: new Map() };
      g.parts.set(url, text.replace(/^﻿?WEBVTT[^\n]*\n(?:[A-Z-]+[^\n]*\n)*/, ''));
      segGroups.set(dir, g);
      if (g.parts.size >= 2) {
        const merged = 'WEBVTT\n\n' + [...g.parts.values()].join('\n\n');
        const c = { id: 'seg:' + dir, url: dir, text: merged, lang: langOf(dir, extra), label: extra.label || 'Player subtitles', source: extra.source || location.hostname, format: 'vtt' };
        found.set(c.id, c); post(c);
        return;
      }
    }
    const id = extra.id || url.replace(/([?&])(expire|signature|sig|ei|pot|c|cver|xorb|xobt|xovt|cbr|cbrver|cos|cosver|cplatform|t|e|o|v)=[^&]*/g, '$1').slice(0, 400) || ('anon:' + text.length);
    const c = { id, url, text, lang: langOf(url, extra), label: extra.label || '', source: extra.source || location.hostname, format: k };
    found.set(id, c); post(c);
  }

  function interesting(url, ctype) {
    url = String(url || ''); ctype = String(ctype || '').toLowerCase();
    if (/^(video|audio|image|font)\//.test(ctype) || /mp2t|mpegurl|dash\+xml|javascript|css|html/.test(ctype)) return false;
    if (/vtt|ttml|srt|subrip|dfxp/.test(ctype)) return true;
    if (/\.(vtt|webvtt|srt|ttml|dfxp|ttml2)(\?|$)/i.test(url)) return true;
    if (/timedtext|subtitle|caption|\/subs?\//i.test(url)) return true;
    if (/xml/.test(ctype) && /nflxvideo|netflix|disney|bamgrid|primevideo|media-amazon|hulu/i.test(url)) return true;
    return false;
  }

  // fetch()
  window.fetch = async function (...args) {
    const res = await ofetch.apply(this, args);
    try {
      const url = (args[0] && args[0].url) || String(args[0]);
      if (interesting(url, res.headers.get('content-type'))) res.clone().text().then(t => add(t, url)).catch(() => {});
    } catch {}
    return res;
  };

  // XMLHttpRequest
  const oopen = XMLHttpRequest.prototype.open;
  const osend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url) { this.__epUrl = url; return oopen.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function () {
    this.addEventListener('load', () => {
      try {
        const url = this.responseURL || this.__epUrl;
        if (!interesting(url, this.getResponseHeader('content-type'))) return;
        const rt = this.responseType;
        if (rt === '' || rt === 'text') add(this.responseText, url);
        else if (rt === 'json') add(JSON.stringify(this.response), url);
        else if (rt === 'arraybuffer') add(new TextDecoder().decode(this.response), url);
        else if (rt === 'blob') this.response.text().then(t => add(t, url));
        else if (rt === 'document' && this.responseXML) add(new XMLSerializer().serializeToString(this.responseXML), url);
      } catch {}
    });
    return osend.apply(this, arguments);
  };

  // <track src="…vtt"> elements
  function scanTracks() {
    for (const tr of document.querySelectorAll('track[src]')) {
      if (tr.__epDone) continue; tr.__epDone = true;
      ofetch(tr.src).then(r => r.text()).then(t => add(t, tr.src, { lang: (tr.srclang || '').toLowerCase(), label: tr.label || '' })).catch(() => {});
    }
  }

  // ---------------- YouTube: ask for the English track directly ----------------
  const isYT = /(^|\.)youtube(-nocookie)?\.com$/.test(location.hostname);
  function ytPlayer() { return document.getElementById('movie_player') || document.querySelector('.html5-video-player'); }
  function ytTracks() {
    const p = ytPlayer();
    let r = null;
    try { r = p && p.getPlayerResponse && p.getPlayerResponse(); } catch {}
    r = r || window.ytInitialPlayerResponse;
    return { tracks: (r && r.captions && r.captions.playerCaptionsTracklistRenderer && r.captions.playerCaptionsTracklistRenderer.captionTracks) || [], vid: r && r.videoDetails && r.videoDetails.videoId };
  }
  async function ytLoad(lang = 'en', native = '') {
    const { tracks, vid } = ytTracks();
    if (!tracks.length) { window.postMessage({ __ep: 'yt-none' }, '*'); return; }
    const pick = l => tracks.find(t => t.languageCode.startsWith(l) && t.kind !== 'asr') || tracks.find(t => t.languageCode.startsWith(l));
    const want = pick(lang); const base = want || tracks.find(t => t.kind !== 'asr') || tracks[0];
    const label = t => ((t.name && (t.name.simpleText || (t.name.runs || []).map(r => r.text).join(''))) || t.languageCode) + (t.kind === 'asr' ? ' (auto-generated)' : '');
    const get = async (t, tl) => {
      const url = t.baseUrl.replace(/&fmt=[^&]*/, '') + '&fmt=json3' + (tl ? '&tlang=' + tl : '');
      const r = await ofetch(url, { credentials: 'include' });
      return [await r.text(), url];
    };
    let ok = false;
    try {
      const [txt, url] = await get(base, want ? '' : lang);
      if (kind(txt)) { add(txt, url, { id: 'yt:' + vid + ':' + lang, lang, label: 'YouTube · ' + (want ? label(want) : label(base) + ' → ' + lang), source: 'YouTube' }); ok = true; }
    } catch {}
    // Translation track in the learner's language (for dual subtitles).
    if (ok && native && native !== lang) {
      try {
        const n = pick(native);
        const [txt, url] = n ? await get(n, '') : await get(base, native);
        if (kind(txt)) add(txt, url, { id: 'yt:' + vid + ':' + native, lang: native, label: 'YouTube · ' + native, source: 'YouTube' });
      } catch {}
    }
    if (!ok) {
      // YouTube refused the direct request: switch the player's own captions on, so the player
      // downloads them (with its tokens) and the network watcher above keeps a copy.
      try {
        const p = ytPlayer();
        p.loadModule && p.loadModule('captions');
        const opt = { languageCode: base.languageCode };
        if (base.kind) opt.kind = base.kind;
        if (!want) opt.translationLanguage = { languageCode: lang };
        p.setOption && p.setOption('captions', 'track', opt);
      } catch {}
    }
  }

  // ---------------- Netflix: seeking must go through its player API ----------------
  function netflixSeek(t) {
    try {
      const vp = window.netflix.appContext.state.playerApp.getAPI().videoPlayer;
      const id = vp.getAllPlayerSessionIds()[0];
      vp.getVideoPlayerBySessionId(id).seek(Math.round(t * 1000));
      return true;
    } catch { return false; }
  }

  window.addEventListener('message', e => {
    if (e.source !== window || !e.data || typeof e.data.__ep !== 'string') return;
    const d = e.data;
    if (d.__ep === 'replay') { scanTracks(); for (const c of found.values()) post(c); }
    if (d.__ep === 'yt-load' && isYT) ytLoad(d.lang || 'en', d.native || '');
    if (d.__ep === 'seek') { if (!netflixSeek(d.t)) { const v = document.querySelector('video'); if (v) v.currentTime = d.t; } }
  });
  if (isYT) document.addEventListener('yt-navigate-finish', () => { window.postMessage({ __ep: 'nav' }, '*'); });
  document.addEventListener('DOMContentLoaded', scanTracks);
})();
