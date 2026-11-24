// Free translation with two providers (Google's public endpoint, then MyMemory as fallback).
// Results are cached in memory and in localStorage.
const CACHE_KEY = 'shadowlab.tcache';
let cache = {};
try { cache = JSON.parse(localStorage.getItem(CACHE_KEY) || '{}'); } catch { cache = {}; }
let dirty = 0;
function remember(k, v) {
  cache[k] = v;
  if (++dirty % 10 === 0) flush();
}
function flush() {
  try {
    const keys = Object.keys(cache);
    if (keys.length > 4000) for (const k of keys.slice(0, keys.length - 3000)) delete cache[k];
    localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
  } catch {}
}
addEventListener('pagehide', flush);

async function fetchJSON(url, timeout = 9000) {
  const ctrl = new AbortController();
  const id = setTimeout(() => ctrl.abort(), timeout);
  try {
    const r = await fetch(url, { signal: ctrl.signal });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } finally { clearTimeout(id); }
}

function gUrl(text, from, to, dict) {
  return `https://translate.googleapis.com/translate_a/single?client=gtx&sl=${from}&tl=${to}&dt=t${dict ? '&dt=bd&dt=rm' : ''}&q=${encodeURIComponent(text)}`;
}

async function google(text, from, to) {
  const data = await fetchJSON(gUrl(text, from, to, false));
  return (data[0] || []).map(p => p[0] || '').join('');
}
async function myMemory(text, from, to) {
  const data = await fetchJSON(`https://api.mymemory.translated.net/get?q=${encodeURIComponent(text.slice(0, 480))}&langpair=${from}|${to}`);
  const t = data && data.responseData && data.responseData.translatedText;
  if (!t || /MYMEMORY WARNING|QUERY LENGTH/i.test(t)) throw new Error('mymemory');
  return t;
}

export async function translate(text, from, to) {
  text = String(text || '').trim();
  if (!text || from === to) return text;
  const k = `${from}|${to}|${text}`;
  if (cache[k]) return cache[k];
  let out;
  try { out = await google(text, from, to); } catch { out = await myMemory(text, from, to); }
  if (out) remember(k, out);
  return out;
}

/** Word lookup with alternatives grouped by part of speech (Google dictionary data). */
export async function translateWord(word, from, to) {
  const k = `w|${from}|${to}|${word.toLowerCase()}`;
  if (cache[k]) return cache[k];
  let res = { main: '', alts: [], translit: '' };
  try {
    const data = await fetchJSON(gUrl(word, from, to, true));
    res.main = (data[0] || []).filter(p => p[0]).map(p => p[0]).join('');
    const rm = (data[0] || []).find(p => !p[0] && (p[2] || p[3]));
    if (rm) res.translit = rm[3] || '';
    if (Array.isArray(data[1])) {
      res.alts = data[1].map(g => ({ pos: g[0], terms: (g[1] || []).slice(0, 6) })).filter(g => g.terms.length);
    }
  } catch {
    try { res.main = await myMemory(word, from, to); } catch { /* offline */ }
  }
  if (res.main) remember(k, res);
  return res;
}

/** Translate many lines efficiently (batched by newline). onProgress(done, total). */
export async function translateLines(lines, from, to, onProgress) {
  const out = new Array(lines.length).fill('');
  const todo = [];
  lines.forEach((l, i) => { const k = `${from}|${to}|${l.trim()}`; if (cache[k]) out[i] = cache[k]; else if (l.trim()) todo.push(i); });
  let done = lines.length - todo.length;
  onProgress && onProgress(done, lines.length);
  let batch = []; let size = 0;
  const run = async () => {
    if (!batch.length) return;
    const idx = batch; batch = []; size = 0;
    const joined = idx.map(i => lines[i].replace(/\n/g, ' ').trim()).join('\n');
    let parts = null;
    try {
      const data = await fetchJSON(gUrl(joined, from, to, false), 15000);
      const txt = (data[0] || []).map(p => p[0] || '').join('');
      parts = txt.split('\n').map(s => s.trim());
      if (parts.length !== idx.length) parts = null;
    } catch { parts = null; }
    if (!parts) {
      parts = [];
      for (const i of idx) { try { parts.push(await translate(lines[i], from, to)); } catch { parts.push(''); } }
    }
    idx.forEach((i, j) => { out[i] = parts[j] || ''; if (parts[j]) remember(`${from}|${to}|${lines[i].trim()}`, parts[j]); });
    done += idx.length;
    onProgress && onProgress(done, lines.length);
  };
  for (const i of todo) {
    const len = encodeURIComponent(lines[i]).length + 3;
    if (size + len > 4200) await run();
    batch.push(i); size += len;
  }
  await run();
  flush();
  return out;
}
