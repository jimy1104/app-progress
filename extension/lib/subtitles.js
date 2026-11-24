// Subtitle parsing (SRT, WebVTT incl. YouTube auto-captions, ASS/SSA, SBV, YouTube json3, plain text)
// and tokenisation helpers.

export function parseTime(s) {
  s = String(s).trim().replace(',', '.');
  const parts = s.split(':').map(Number);
  if (parts.some(isNaN)) return NaN;
  let sec = 0;
  for (const p of parts) sec = sec * 60 + p;
  return sec;
}

export function fmtTime(sec) {
  if (!isFinite(sec)) sec = 0;
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.floor(sec % 60);
  return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(s).padStart(2, '0');
}

export function cleanText(t) {
  return String(t)
    .replace(/<\d{2}:\d{2}[:.\d]*>/g, '')          // VTT inline timestamps
    .replace(/<\/?[a-z][^>]*>/gi, '')               // HTML-ish tags (<i>, <c.color>, <font>)
    .replace(/\{[^}]*\}/g, '')                      // ASS override tags / {\an8}
    .replace(/\\[Nn]/g, ' ')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&#39;|&apos;/g, "'").replace(/&quot;/g, '"')
    .replace(/[ \t]+/g, ' ')
    .trim();
}

function parseCueBlocks(text) {
  const blocks = text.replace(/\r/g, '').split(/\n{2,}/);
  const cues = [];
  for (const block of blocks) {
    const lines = block.split('\n');
    const i = lines.findIndex(l => l.includes('-->'));
    if (i < 0) continue;
    const m = lines[i].match(/([\d:.,]+)\s*-->\s*([\d:.,]+)/);
    if (!m) continue;
    const start = parseTime(m[1]), end = parseTime(m[2]);
    const rawLines = lines.slice(i + 1).map(cleanText).filter(Boolean);
    if (!isFinite(start) || !isFinite(end)) continue;
    cues.push({ start, end, rawLines });
  }
  return cues;
}

function dedupeRolling(cues) {
  // YouTube auto-generated VTT repeats the previous line in each cue ("rolling" captions).
  const out = [];
  let prevLast = null;
  for (const c of cues) {
    let lines = c.rawLines;
    if (prevLast && lines.length > 1 && lines[0] === prevLast) lines = lines.slice(1);
    if (c.end - c.start < 0.06 && out.length) { prevLast = lines[lines.length - 1]; continue; }
    if (!lines.length) continue;
    prevLast = lines[lines.length - 1];
    out.push({ start: c.start, end: c.end, text: lines.join(' ') });
  }
  return out;
}

function parseASS(text) {
  const out = [];
  let format = null;
  for (const raw of text.replace(/\r/g, '').split('\n')) {
    const line = raw.trim();
    if (/^Format:/i.test(line) && format === null && /Start/i.test(line) && /Text/i.test(line)) {
      format = line.slice(7).split(',').map(s => s.trim().toLowerCase());
    } else if (/^Dialogue:/i.test(line)) {
      const f = format || ['layer', 'start', 'end', 'style', 'name', 'marginl', 'marginr', 'marginv', 'effect', 'text'];
      const body = line.slice(9);
      const parts = body.split(',');
      const head = parts.slice(0, f.length - 1);
      const txt = parts.slice(f.length - 1).join(',');
      const start = parseTime(head[f.indexOf('start')]);
      const end = parseTime(head[f.indexOf('end')]);
      const t = cleanText(txt);
      if (t && isFinite(start)) out.push({ start, end, text: t });
    }
  }
  return out;
}

function parseSBV(text) {
  const out = [];
  for (const block of text.replace(/\r/g, '').split(/\n{2,}/)) {
    const lines = block.split('\n');
    const m = lines[0] && lines[0].match(/^([\d:.]+),([\d:.]+)$/);
    if (!m) continue;
    const t = cleanText(lines.slice(1).join(' '));
    if (t) out.push({ start: parseTime(m[1]), end: parseTime(m[2]), text: t });
  }
  return out;
}

function parseJSON3(text) {
  const data = JSON.parse(text);
  const out = [];
  for (const ev of data.events || []) {
    if (!ev.segs) continue;
    const t = cleanText(ev.segs.map(s => s.utf8 || '').join('').replace(/\n/g, ' '));
    if (!t) continue;
    const start = (ev.tStartMs || 0) / 1000;
    out.push({ start, end: start + (ev.dDurationMs || 2000) / 1000, text: t });
  }
  return out;
}

/** TTML / DFXP (Netflix, Disney+, Prime…). Uses DOMParser (browser). */
function parseTTML(text) {
  const doc = new DOMParser().parseFromString(text, 'application/xml');
  const root = doc.documentElement;
  const attr = (el, name) => el.getAttribute(name) || el.getAttribute('ttp:' + name) || el.getAttributeNS('http://www.w3.org/ns/ttml#parameter', name);
  const tick = Number(attr(root, 'tickRate')) || 10000000;
  const fps = Number(attr(root, 'frameRate')) || 30;
  const time = v => {
    if (!v) return NaN; v = v.trim();
    let m;
    if ((m = v.match(/^([\d.]+)(h|ms|m|s|f|t)$/))) {
      const n = parseFloat(m[1]);
      return { h: n * 3600, m: n * 60, s: n, ms: n / 1000, f: n / fps, t: n / tick }[m[2]];
    }
    if ((m = v.match(/^(\d+):(\d+):(\d+)(?:\.(\d+))?(?::(\d+))?$/))) return +m[1] * 3600 + +m[2] * 60 + +m[3] + (m[4] ? Number('0.' + m[4]) : 0) + (m[5] ? +m[5] / fps : 0);
    return NaN;
  };
  const textOf = node => {
    let out = '';
    for (const c of node.childNodes) {
      if (c.nodeType === 3) out += c.nodeValue;
      else if (c.localName === 'br') out += ' ';
      else out += textOf(c);
    }
    return out;
  };
  const out = [];
  for (const p of doc.getElementsByTagName('*')) {
    if (p.localName !== 'p') continue;
    let start = time(p.getAttribute('begin')); let end = time(p.getAttribute('end'));
    if (!isFinite(end) && p.getAttribute('dur')) end = start + time(p.getAttribute('dur'));
    const t = cleanText(textOf(p));
    if (t && isFinite(start)) out.push({ start, end: isFinite(end) ? end : start + 2, text: t });
  }
  return out;
}

/** YouTube XML formats: <transcript><text start dur> and srv3 <timedtext><p t d>. */
function parseYTXML(text) {
  const out = [];
  const dec = s => cleanText(s.replace(/<[^>]+>/g, '').replace(/&amp;#39;/g, "'").replace(/&amp;quot;/g, '"').replace(/&amp;/g, '&'));
  let m; const re1 = /<text[^>]*\bstart="([\d.]+)"[^>]*?(?:\bdur="([\d.]+)")?[^>]*>([\s\S]*?)<\/text>/g;
  while ((m = re1.exec(text))) { const t = dec(m[3]); if (t) out.push({ start: +m[1], end: +m[1] + (+m[2] || 2), text: t }); }
  const re2 = /<p[^>]*\bt="(\d+)"[^>]*?(?:\bd="(\d+)")?[^>]*>([\s\S]*?)<\/p>/g;
  while ((m = re2.exec(text))) { const t = dec(m[3]); if (t) out.push({ start: +m[1] / 1000, end: (+m[1] + (+m[2] || 2000)) / 1000, text: t }); }
  return out;
}

/** Plain text without timings: one sentence per line, with estimated durations. */
function parsePlain(text) {
  const raw = text.replace(/\r/g, '').split('\n').map(s => s.trim()).filter(Boolean);
  // Split long paragraphs into sentences.
  const sentences = [];
  for (const p of raw) {
    const parts = p.match(/[^.!?…]+(?:[.!?…]+["'”’)]?|$)/g) || [p];
    for (const s of parts) { const c = s.trim(); if (c) sentences.push(c); }
  }
  let t = 0.5;
  return sentences.map(s => {
    const dur = Math.max(1.2, s.length * 0.075);
    const cue = { start: t, end: t + dur, text: s };
    t += dur + 0.6;
    return cue;
  });
}

export function parseSubtitles(text) {
  text = String(text || '').replace(/^﻿/, '');
  const head = text.slice(0, 2000);
  let cues; let untimed = false;
  try {
    if (/^\s*\{/.test(head) && /"events"/.test(head)) cues = parseJSON3(text);
    else if (/<tt[\s>]/.test(head)) cues = parseTTML(text);
    else if (/<transcript[\s>]|<timedtext[\s>]/.test(head)) cues = parseYTXML(text);
    else if (/\[Script Info\]|\[Events\]|^Dialogue:/m.test(head)) cues = parseASS(text);
    else if (text.includes('-->')) cues = dedupeRolling(parseCueBlocks(text));
    else if (/^\d+:\d{2}:\d{2}\.\d{3},\d+:\d{2}:\d{2}\.\d{3}$/m.test(head)) cues = parseSBV(text);
    else { cues = parsePlain(text); untimed = true; }
  } catch { cues = parsePlain(text); untimed = true; }

  cues = cues.filter(c => c.text && isFinite(c.start)).sort((a, b) => a.start - b.start);
  // Merge consecutive identical cues and fix bad end times.
  const out = [];
  for (const c of cues) {
    const prev = out[out.length - 1];
    if (prev && prev.text === c.text && c.start - prev.end < 0.3) { prev.end = Math.max(prev.end, c.end); continue; }
    if (!(c.end > c.start)) c.end = c.start + Math.max(1, c.text.length * 0.06);
    out.push({ start: c.start, end: c.end, text: c.text });
  }
  out.forEach((c, i) => { c.i = i; });
  return { cues: out, untimed };
}

/** Find the cue that contains t (binary search), or -1. */
export function findActive(cues, t) {
  let lo = 0, hi = cues.length - 1, found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (cues[mid].start <= t) { found = mid; lo = mid + 1; } else hi = mid - 1;
  }
  if (found >= 0 && t < cues[found].end) return found;
  // Overlapping cues: look back a few.
  for (let k = found - 1; k >= Math.max(0, found - 3); k--) if (t >= cues[k].start && t < cues[k].end) return k;
  return -1;
}
/** Index of the last cue that started at or before t (or -1). */
export function findLastStarted(cues, t) {
  let lo = 0, hi = cues.length - 1, found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (cues[mid].start <= t) { found = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return found;
}

/** Map secondary-language cues onto primary cues by time overlap. */
export function alignSecondary(primary, secondary) {
  return primary.map(p => {
    const hits = secondary.filter(s => s.start < p.end - 0.05 && s.end > p.start + 0.05);
    if (!hits.length) return '';
    // Take cues with the biggest overlap.
    const scored = hits.map(s => ({ s, ov: Math.min(s.end, p.end) - Math.max(s.start, p.start) }));
    const best = Math.max(...scored.map(x => x.ov));
    return scored.filter(x => x.ov > best * 0.5).map(x => x.s.text).join(' ');
  });
}

const WORD_RE = /[\p{L}\p{M}\p{N}]+(?:['’][\p{L}]+)*/gu;
export function tokenize(text) {
  const out = []; let last = 0;
  for (const m of text.matchAll(WORD_RE)) {
    if (m.index > last) out.push({ t: text.slice(last, m.index), w: false, s: last });
    out.push({ t: m[0], w: true, s: m.index });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ t: text.slice(last), w: false, s: last });
  return out;
}
export function words(text) { return (String(text).match(WORD_RE) || []).map(w => w.toLowerCase().replace(/’/g, "'")); }
export function normalize(text) { return String(text).replace(/[’‘`]/g, "'").replace(/[“”]/g, '"'); }
