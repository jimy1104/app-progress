import { t, tr, setLang, getLang, applyStatic, LANGS, SPEECH_LOCALE, posName } from './i18n.js';
import * as store from './storage.js';
import { parseSubtitles, findActive, findLastStarted, alignSecondary, tokenize, fmtTime, normalize } from './subtitles.js';
import { Html5Player, YouTubePlayer, TtsPlayer, youtubeId, speak, isUnsupportedHost } from './player.js';
import { translate, translateLines } from './translate.js';
import { lookup } from './dictionary.js';
import { analyze, corpus, connectedSpeech, intonation, isFunctionWord, phrasalAt, expandContraction, REDUCTIONS } from './grammar.js';
import { Recorder, drawWave, scoreSpeech, similarity } from './recorder.js';
import { explainLine, askAbout } from './ai.js';
import { MODES, ROUTINE, MISTAKES, HELP, DEMO_SRT } from './content.js';
import { Game, LEVELS } from './game.js';

const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// ------------------------------------------------------------------ state
const app = {
  player: null,
  cues: [],
  session: null,          // { title, kind, url, subsText, subs2Text, untimed, trans: {lang: []} }
  secondary: null,        // aligned native-language subtitles (array of strings) if provided
  corpus: null,
  filter: null,           // { label, set:Set<number> }
  shown: -1,              // index currently displayed in the caption
};
const engine = { target: null, loopCount: 0, pausedAtEnd: null, timer: null, playOnce: null, lastT: 0, recAuto: false, guardUntil: 0, expect: 0 };
const recorder = new Recorder();
let lastRec = null; let lastRecLine = -1;
const S = () => store.settings();
const P = () => store.profile();
const native = () => P().native;
const target = () => P().target || 'en';
const speechLocale = () => SPEECH_LOCALE[target()] || 'en-US';

// ------------------------------------------------------------------ boot
function init() {
  applyLanguage();
  bindUI();
  requestAnimationFrame(tick);
  setInterval(statsTick, 1000);
  if ('speechSynthesis' in window) speechSynthesis.getVoices();
}

function applyLanguage() {
  setLang(native());
  applyStatic();
  buildProfileSwitch();
  buildModeSelect();
  buildToggles();
  $('#helpBody').innerHTML = tr(HELP);
  $('#rateSelect').value = String(S().rate || 1);
  renderSaved(); renderRoutine(); renderProgress();
  renderGameChrome();
  if (app.cues.length) { buildSubList(); showLine(app.shown, true); }
  else renderGrammarEmpty();
  updateButtons();
}

// ------------------------------------------------------------------ profiles
function buildProfileSwitch() {
  const host = $('#profileSwitch'); host.innerHTML = '';
  const st = store.getState();
  for (const p of Object.values(st.profiles)) {
    const b = document.createElement('button');
    b.className = 'profile-pill' + (p.id === st.activeProfile ? ' active' : '');
    b.innerHTML = `${esc(p.name)}<small>${esc((p.native || '').toUpperCase())}</small>`;
    b.onclick = () => { if (p.id === st.activeProfile) return; store.setActiveProfile(p.id); applyLanguage(); applySettingsToPlayer(); toast(`${p.name} · ${LANGS[p.native] || p.native}`); };
    host.appendChild(b);
  }
}

// ------------------------------------------------------------------ modes & toggles
function buildModeSelect() {
  const sel = $('#modeSelect'); sel.innerHTML = '';
  for (const k of Object.keys(MODES)) { const o = document.createElement('option'); o.value = k; o.textContent = t('m_' + k); sel.appendChild(o); }
  sel.value = S().mode || 'watch';
}
function setMode(mode) {
  Object.assign(S(), MODES[mode] || {}, { mode });
  store.persist();
  $('#modeSelect').value = mode;
  buildToggles();
  if (mode === 'translate') $('#transCard').open = true;
  if (mode === 'record') $('#recCard').open = true;
  showLine(app.shown, true);
  toast(t('m_' + mode));
}

const TOGGLES = [
  { key: 'autoPause', label: 't_autoPause' },
  { key: 'loopLine', label: 't_loop', extra: 'repeat' },
  { key: 'autoResume', label: 't_autoResume', extra: 'gap' },
  { key: 'showPrevBtn', label: 't_prevBtn' },
  { key: 'hideText', label: 't_hide' },
  { key: 'showTranslation', label: 't_trans' },
  { key: 'blurTranslation', label: 't_blur' },
  { key: 'karaoke', label: 't_karaoke' },
  { key: 'stressMap', label: 't_stress' },
  { key: 'autoRecord', label: 't_autoRec' },
  { key: 'overlayRecord', label: 't_overlayRec' },
  { key: 'offset', label: 't_offset', extra: 'offset' },
];
function buildToggles() {
  const host = $('#toggles'); host.innerHTML = '';
  const s = S();
  for (const tg of TOGGLES) {
    const chip = document.createElement('span');
    if (tg.extra === 'offset') {
      chip.className = 'chip';
      chip.innerHTML = `${t(tg.label)} <button class="stepper" data-d="-0.1">−</button><b>${(s.offset >= 0 ? '+' : '') + s.offset.toFixed(1)}s</b><button class="stepper" data-d="0.1">+</button>`;
      chip.querySelectorAll('.stepper').forEach(b => b.onclick = e => { e.stopPropagation(); s.offset = Math.round((s.offset + Number(b.dataset.d)) * 10) / 10; store.persist(); buildToggles(); });
      host.appendChild(chip); continue;
    }
    chip.className = 'chip' + (s[tg.key] ? ' on' : '');
    chip.setAttribute('role', 'switch'); chip.setAttribute('aria-checked', String(!!s[tg.key])); chip.tabIndex = 0;
    let extra = '';
    if (tg.extra === 'repeat') extra = ` <input type="number" min="0" max="20" value="${s.repeatCount}" title="0 = ∞"> ${t('t_times')}`;
    if (tg.extra === 'gap') extra = ` <span>${t('t_gap')}</span><input type="number" min="0.5" max="4" step="0.1" value="${s.gapFactor}">`;
    chip.innerHTML = `<span class="dot"></span>${t(tg.label)}${extra}`;
    const inp = chip.querySelector('input');
    if (inp) {
      inp.onclick = e => e.stopPropagation();
      inp.onchange = () => { const v = Number(inp.value); if (tg.extra === 'repeat') s.repeatCount = Math.max(0, Math.min(20, Math.round(v) || 0)); else s.gapFactor = Math.max(0.5, Math.min(4, v || 1.3)); store.persist(); };
    }
    const toggle = () => { s[tg.key] = !s[tg.key]; if (tg.key === 'overlayRecord' && s.overlayRecord) s.autoRecord = false; if (tg.key === 'autoRecord' && s.autoRecord) s.overlayRecord = false; store.persist(); buildToggles(); showLine(app.shown, true); };
    chip.onclick = toggle;
    chip.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } };
    host.appendChild(chip);
  }
  $('#btnPrev').hidden = !s.showPrevBtn;
}
function flip(key, label) { S()[key] = !S()[key]; store.persist(); buildToggles(); showLine(app.shown, true); toast(`${t(label)}: ${S()[key] ? 'ON' : 'OFF'}`); }

// ------------------------------------------------------------------ loading
function openLoad() {
  renderLibrary();
  $('#dlgLoad').showModal();
}
function srcKind() { return $('#srcSeg .seg-btn.active').dataset.v; }

async function doLoadFromDialog() {
  const kind = srcKind();
  const subsFile = $('#inSubs').files[0];
  let subsText = $('#inSubsText').value.trim();
  if (subsFile) subsText = await subsFile.text();
  const subs2File = $('#inSubs2').files[0];
  const subs2Text = subs2File ? await subs2File.text() : '';
  const videoFile = $('#inVideo').files[0];
  const url = $('#inUrl').value.trim();
  let title = $('#inTitle').value.trim();
  if (!subsText) { toast(t('needSubs')); return false; }
  if (kind === 'file' && !videoFile) { toast(t('needVideo')); return false; }
  if (kind === 'url') {
    if (!url) { toast(t('needVideo')); return false; }
    if (isUnsupportedHost(url)) { $('#urlHint').innerHTML = `<b style="color:var(--warn)">${esc(t('unsupportedSite'))}</b>`; return false; }
  }
  if (!title) title = (videoFile && videoFile.name.replace(/\.[^.]+$/, '')) || (subsFile && subsFile.name.replace(/\.[^.]+$/, '')) || url || 'Clip';
  $('#dlgLoad').close();
  await loadSession({ kind, file: videoFile, url, subsText, subs2Text, title });
  return true;
}

async function loadSession({ kind, file, url, subsText, subs2Text, title, resumeAt }) {
  const { cues, untimed } = parseSubtitles(subsText);
  if (!cues.length) { toast(t('needSubs')); return; }
  if (untimed && kind !== 'tts') { toast(t('untimed')); kind = 'tts'; }
  destroyPlayer();
  const host = $('#playerHost');
  $('#emptyState').hidden = true;
  app.cues = cues;
  const prev = store.getState().library[store.libraryKey(title)];
  app.session = { title, kind, url: kind === 'url' ? url : '', subsText, subs2Text, untimed, trans: (prev && prev.trans) || {} };
  app.secondary = subs2Text ? alignSecondary(cues, parseSubtitles(subs2Text).cues) : null;
  if (game.running) game.stop();
  app.filter = null; app.shown = -1; app.checked = {};
  Object.assign(engine, { target: null, loopCount: 0, pausedAtEnd: null, playOnce: null, lastT: 0, guardUntil: 0 });
  clearTimeout(engine.timer);
  app.corpus = corpus(cues);
  buildSubList();

  try {
    if (kind === 'file') {
      const isAudio = /^audio\//.test(file.type) || /\.(mp3|m4a|wav|ogg|aac|flac|opus)$/i.test(file.name);
      app.player = new Html5Player(host, URL.createObjectURL(file), { isAudio });
    } else if (kind === 'url') {
      const yt = youtubeId(url);
      if (yt) app.player = new YouTubePlayer(host, yt);
      else app.player = new Html5Player(host, url, { hls: /\.m3u8(\?|$)/i.test(url), isAudio: /\.(mp3|m4a|wav|ogg|aac|flac|opus)(\?|$)/i.test(url) });
    } else {
      app.player = new TtsPlayer(host, cues, speechLocale());
    }
    await app.player.ready;
  } catch (e) {
    toast(kind === 'url' ? t('badUrl') : String(e.message || e), 6000);
  }
  applySettingsToPlayer();
  store.saveSession({ title, kind, url: app.session.url, subsText: subsText.length < 400000 ? subsText : '', subs2Text: subs2Text.length < 400000 ? subs2Text : '', fileName: file ? file.name : '', lines: cues.length });
  const startIdx = resumeAt != null ? resumeAt : (prev && prev.lastIdx) || 0;
  showLine(Math.min(startIdx, cues.length - 1), true);
  if (startIdx > 0) seekToLine(startIdx, false);
  renderRoutine();
  updateButtons();
  renderGameChrome();
  toast(`${title} · ${cues.length} ${t('subsLoaded')}`);
}

function destroyPlayer() {
  if (app.player) { try { app.player.pause(); app.player.destroy(); } catch {} }
  app.player = null;
  const host = $('#playerHost');
  host.classList.remove('audio-only');
  [...host.children].forEach(c => { if (c.id !== 'emptyState') c.remove(); });
}

function applySettingsToPlayer() { if (app.player) app.player.setRate(Number(S().rate) || 1); }

function renderLibrary() {
  const lib = Object.values(store.getState().library).sort((a, b) => (b.updated || 0) - (a.updated || 0));
  const host = $('#library');
  if (!lib.length) { host.innerHTML = ''; return; }
  host.innerHTML = `<h4>${t('library')}</h4>` + lib.slice(0, 15).map(s => `
    <div class="lib-item" data-title="${esc(s.title)}">
      <span class="name" title="${esc(s.title)}">${s.kind === 'url' ? '🔗' : s.kind === 'tts' ? '🗣' : '🎬'} ${esc(s.title)}</span>
      <span class="muted small">${s.lines || ''}</span>
      <button type="button" class="btn small" data-act="open">${t('open')}</button>
      <button type="button" class="btn small" data-act="del">✕</button>
    </div>`).join('');
  host.querySelectorAll('.lib-item').forEach(row => {
    const s = store.getState().library[store.libraryKey(row.dataset.title)];
    row.querySelector('[data-act=del]').onclick = () => { store.deleteSession(s.title); renderLibrary(); };
    row.querySelector('[data-act=open]').onclick = () => {
      if (!s.subsText) { toast(t('needSubs')); return; }
      if (s.kind === 'file') {
        toast(`${t('reselect')}: ${s.fileName || ''}`, 5000);
        const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'video/*,audio/*,.mkv,.mov';
        inp.onchange = () => { if (inp.files[0]) { $('#dlgLoad').close(); loadSession({ kind: 'file', file: inp.files[0], subsText: s.subsText, subs2Text: s.subs2Text, title: s.title }); } };
        inp.click();
      } else { $('#dlgLoad').close(); loadSession({ kind: s.kind, url: s.url, subsText: s.subsText, subs2Text: s.subs2Text, title: s.title }); }
    };
  });
}

// ------------------------------------------------------------------ engine
function subTime() { return app.player ? app.player.time() - (S().offset || 0) : 0; }
function lineStartVideoTime(i) { return Math.max(0, app.cues[i].start + (S().offset || 0) - 0.05); }

function tick() {
  requestAnimationFrame(tick);
  const p = app.player; const cues = app.cues;
  if (!p || !cues.length) return;
  let tt;
  try { tt = subTime(); } catch { return; }
  const playing = !p.paused();
  // After our own seek, some players (YouTube) report the old time for a few frames: wait for it.
  if (engine.guardUntil) {
    if (Math.abs(tt - engine.expect) < 0.6 || performance.now() > engine.guardUntil) engine.guardUntil = 0;
    else return;
  }
  // Detect manual seeks (native controls, YouTube UI…).
  if (Math.abs(tt - engine.lastT) > 1.5) { engine.target = null; engine.loopCount = 0; engine.pausedAtEnd = null; }
  engine.lastT = tt;

  const active = findActive(cues, tt);
  if (playing) {
    engine.pausedAtEnd = null;
    if (engine.target == null && active >= 0) { engine.target = active; engine.loopCount = engine.loopCount || 0; }
    if (engine.target != null) {
      const cue = cues[engine.target];
      if (cue && tt >= cue.end - 0.03) onLineEnd(engine.target);
      else if (active > engine.target) { engine.target = active; engine.loopCount = 0; }
    }
  }
  const display = engine.target != null ? engine.target : (active >= 0 ? active : Math.max(0, findLastStarted(cues, tt)));
  if (display !== app.shown) showLine(display);
  updateKaraoke(tt, playing);
  const pb = $('#btnPlay'); const icon = playing ? '❚❚' : '▶';
  if (pb.textContent !== icon) pb.textContent = icon;
}

function onLineEnd(i) {
  const s = S(); const p = app.player; const cue = app.cues[i];
  if (game.active && game.running) {
    if (game.onLineEnd(i) === 'pause') { p.pause(); engine.pausedAtEnd = i; }
    else { engine.target = null; engine.loopCount = 0; }
    return;
  }
  const dur = (cue.end - cue.start) / (Number(s.rate) || 1);
  if (s.mode !== 'watch') store.bump('lines');

  if (engine.playOnce) {                        // "compare": play the line once, then the callback
    const cb = engine.playOnce; engine.playOnce = null;
    p.pause(); engine.pausedAtEnd = i; cb(); return;
  }
  if (recorder.recording && engine.recOverlay) { stopRecording(); }

  if (s.loopLine) {
    engine.loopCount++;
    if (s.repeatCount === 0 || engine.loopCount < s.repeatCount) {
      if (s.autoResume || s.autoRecord) {
        p.pause(); engine.pausedAtEnd = i;
        const gap = dur * s.gapFactor * 1000 + 300;
        if (s.autoRecord) startRecording({ auto: true, line: i });
        schedule(gap, () => { if (recorder.recording && engine.recAuto) stopRecording(); replay(i); });
      } else {
        seekToLine(i, true);
      }
      return;
    }
    engine.loopCount = 0;
  }

  if (s.autoPause) {
    p.pause();
    engine.pausedAtEnd = i;
    const gap = dur * s.gapFactor * 1000 + 300;
    if (s.autoRecord) startRecording({ auto: true, line: i });
    if (s.autoResume || s.autoRecord) {
      schedule(gap, () => {
        if (recorder.recording && engine.recAuto) stopRecording();
        if (s.autoResume) { const n = i + 1; if (n < app.cues.length) { engine.target = n; engine.loopCount = 0; seekToLine(n, true); } }
      });
    }
    return;
  }
  // Continuous playback: hand over to the next line.
  engine.target = null; engine.loopCount = 0;
}

function schedule(ms, fn) { clearTimeout(engine.timer); engine.timer = setTimeout(fn, ms); }
function clearSchedule() { clearTimeout(engine.timer); engine.timer = null; }

function seekToLine(i, play) {
  if (!app.player || !app.cues[i]) return;
  engine.target = i; engine.pausedAtEnd = null;
  const vt = lineStartVideoTime(i);
  app.player.seek(vt);
  engine.lastT = engine.expect = vt - (S().offset || 0);
  engine.guardUntil = performance.now() + 1500;
  if (play) app.player.play();
  showLine(i);
}
function replay(i) { engine.target = i; seekToLine(i, true); }

function gotoLine(i, { keepLoop = false } = {}) {
  if (!app.cues.length) return;
  i = Math.max(0, Math.min(app.cues.length - 1, i));
  clearSchedule();
  if (recorder.recording) stopRecording();
  engine.playOnce = null;
  if (!keepLoop) engine.loopCount = 0;
  seekToLine(i, true);
}
function currentIndex() { return engine.target != null ? engine.target : Math.max(0, app.shown); }
function prevLine() { gotoLine(currentIndex() - 1); }
function nextLine() { gotoLine(currentIndex() + 1); }
function repeatLine() { if (game.active && game.running) { if (game.waiting) game.replay(); else seekToLine(currentIndex(), true); return; } gotoLine(currentIndex()); }

function togglePlay() {
  const p = app.player; if (!p) { openLoad(); return; }
  if (game.active) {
    if (!game.running) { game.start(game.level, currentIndex()); return; }
    if (game.waiting) { game.replay(); return; }
  }
  clearSchedule(); engine.playOnce = null;
  if (p.paused()) {
    if (recorder.recording && engine.recAuto) stopRecording();
    if (engine.pausedAtEnd != null) {
      const n = engine.pausedAtEnd + 1; engine.pausedAtEnd = null;
      if (n < app.cues.length) { engine.loopCount = 0; seekToLine(n, true); return; }
    }
    p.play();
  } else p.pause();
}

// ------------------------------------------------------------------ caption rendering
function transFor(i) {
  if (app.secondary && app.secondary[i]) return app.secondary[i];
  const arr = app.session && app.session.trans[native()];
  return arr ? arr[i] || '' : '';
}
async function ensureTrans(i) {
  if (!app.cues[i] || transFor(i) || target() === native()) return transFor(i);
  const ses = app.session;
  ses.trans[native()] = ses.trans[native()] || [];
  try {
    const txt = await translate(app.cues[i].text, target(), native());
    ses.trans[native()][i] = txt;
    persistTrans();
    return txt;
  } catch { return ''; }
}
let transSaveTimer = null;
function persistTrans() {
  clearTimeout(transSaveTimer);
  transSaveTimer = setTimeout(() => { if (app.session) store.updateSession(app.session.title, { trans: app.session.trans }); }, 1500);
}

function showLine(i, force = false) {
  const cues = app.cues;
  if (!cues.length || i < 0 || i >= cues.length) {
    $('#lineText').innerHTML = ''; $('#lineTrans').textContent = ''; $('#lineCounter').textContent = cues.length ? '' : t('noSubs');
    return;
  }
  if (i === app.shown && !force) return;
  const changed = i !== app.shown;
  app.shown = i;
  const s = S(); const cue = cues[i];
  $('#lineCounter').textContent = `${t('line')} ${i + 1} ${t('of')} ${cues.length} · ${fmtTime(cue.start)}`;
  if (game.active) {
    if (changed) game.onLineShown(i);
    renderGameLine(i);
    const lt = $('#lineTrans');
    lt.classList.toggle('off', !s.gameShowTrans || !game.running); lt.classList.remove('blur');
    lt.textContent = transFor(i);
    if (s.gameShowTrans) ensureTrans(i).then(txt => { if (app.shown === i) lt.textContent = txt || ''; });
    if (changed || force) highlightList(i);
    renderHud();
    return;
  }
  const saved = store.savedWordSet();
  const toks = tokenize(cue.text);
  let charTotal = 0; toks.forEach(k => { if (k.w) charTotal += k.t.length; });
  let acc = 0;
  $('#lineText').innerHTML = toks.map(k => {
    if (!k.w) return esc(k.t);
    const lw = k.t.toLowerCase().replace(/’/g, "'");
    const cls = ['w'];
    if (saved.has(lw)) cls.push('saved');
    if (s.stressMap) cls.push(isFunctionWord(lw) ? 'fn' : 'stress');
    acc += k.t.length;
    return `<span class="${cls.join(' ')}" data-s="${k.s}" data-f="${(acc / charTotal).toFixed(3)}">${esc(k.t)}</span>`;
  }).join('');
  $('#lineText').classList.toggle('hidden-text', !!s.hideText);
  $('#lineText').classList.remove('peek');
  const lt = $('#lineTrans');
  const transMode = s.mode === 'translate';
  lt.classList.toggle('off', !s.showTranslation || (transMode && !app.checked?.[i]));
  lt.classList.toggle('blur', !!s.blurTranslation);
  lt.textContent = transFor(i) || (s.showTranslation ? '…' : '');
  if (s.showTranslation || transMode) ensureTrans(i).then(txt => { if (app.shown === i) lt.textContent = txt || ''; const li = listItem(i); if (li && txt) li.querySelector('.tr').textContent = txt; });
  // prefetch
  for (let k = 1; k <= 2; k++) if (cues[i + k] && (s.showTranslation || transMode)) ensureTrans(i + k);
  $('#btnSaveLine').textContent = store.isSentenceSaved(cue.text) ? '★' : '☆';
  $('#btnSaveLine').classList.toggle('on', store.isSentenceSaved(cue.text));
  if (changed || force) { highlightList(i); renderGrammar(i); }
  if (changed) {
    $('#transInput').value = ''; $('#transResult').innerHTML = ''; $('#transScore').textContent = '';
    if (app.session) store.updateSession(app.session.title, { lastIdx: i });
  }
  updateButtons();
}

let karaokeCount = -1;
function updateKaraoke(tt, playing) {
  const s = S(); const i = app.shown; const cue = app.cues[i];
  if (game.active) return;
  if (!cue || !s.karaoke || s.hideText) { if (karaokeCount !== -1) { $$('#lineText .w.sung').forEach(e => e.classList.remove('sung')); karaokeCount = -1; } return; }
  const frac = (tt - cue.start) / Math.max(0.2, cue.end - cue.start);
  const spans = $$('#lineText .w');
  let n = 0;
  if (frac > 0 && (playing || frac < 1.05)) for (const sp of spans) { if (Number(sp.dataset.f) <= frac + 0.02) n++; }
  if (frac >= 1) n = spans.length;
  if (n === karaokeCount) return;
  karaokeCount = n;
  spans.forEach((sp, k) => sp.classList.toggle('sung', k < n));
}

// ------------------------------------------------------------------ subtitle list
function buildSubList() {
  const ol = $('#subList'); ol.innerHTML = '';
  const frag = document.createDocumentFragment();
  app.cues.forEach((c, i) => {
    const li = document.createElement('li');
    li.className = 'sub-item'; li.dataset.i = i;
    const q = /\?\s*$/.test(c.text) ? `<span class="tag">${t('tags_q')}</span>` : '';
    li.innerHTML = `<span class="st">${fmtTime(c.start)} <span class="tags">${q}</span></span><span class="tx" dir="auto">${esc(c.text)}</span><button class="star${store.isSentenceSaved(c.text) ? ' on' : ''}" title="${esc(t('saveSentence'))}">${store.isSentenceSaved(c.text) ? '★' : '☆'}</button><span class="tr" dir="auto">${esc(transFor(i))}</span>`;
    frag.appendChild(li);
  });
  ol.appendChild(frag);
  applyListFilter();
}
function listItem(i) { return $(`#subList .sub-item[data-i="${i}"]`); }
let userScrolledAt = 0;
function highlightList(i) {
  $$('#subList .sub-item.current').forEach(e => e.classList.remove('current'));
  const li = listItem(i); if (!li) return;
  li.classList.add('current');
  if (Date.now() - userScrolledAt > 3000 && $('[data-panel=subs]').classList.contains('active')) {
    const ol = $('#subList'); const top = li.offsetTop - ol.clientHeight / 3;
    ol.scrollTo({ top, behavior: 'smooth' });
  }
}
function applyListFilter() {
  const q = $('#subSearch').value.trim().toLowerCase();
  const f = app.filter;
  $$('#subList .sub-item').forEach(li => {
    const i = Number(li.dataset.i);
    const okF = !f || f.set.has(i);
    const okQ = !q || app.cues[i].text.toLowerCase().includes(q) || (transFor(i) || '').toLowerCase().includes(q);
    li.hidden = !(okF && okQ);
  });
  const bar = $('#subFilter');
  if (f) { bar.hidden = false; bar.innerHTML = `${t('filterOn')}: <b>${esc(f.label)}</b> (${f.set.size}) <span class="spacer"></span><button class="btn small">${t('clear')}</button>`; bar.querySelector('button').onclick = () => { app.filter = null; applyListFilter(); }; }
  else bar.hidden = true;
}
function tokenizeListItem(li) {
  if (li.dataset.tok) return;
  li.dataset.tok = '1';
  const i = Number(li.dataset.i); const saved = store.savedWordSet();
  li.querySelector('.tx').innerHTML = tokenize(app.cues[i].text).map(k => k.w ? `<span class="w${saved.has(k.t.toLowerCase()) ? ' saved' : ''}" data-s="${k.s}">${esc(k.t)}</span>` : esc(k.t)).join('');
}

async function translateAll() {
  if (!app.cues.length) return;
  const btn = $('#btnTranslateAll'); btn.disabled = true;
  try {
    const out = await translateLines(app.cues.map(c => c.text), target(), native(), (d, n) => { btn.textContent = `${Math.round(d / n * 100)}%`; });
    app.session.trans[native()] = out;
    persistTrans();
    $$('#subList .sub-item').forEach(li => { li.querySelector('.tr').textContent = out[Number(li.dataset.i)] || ''; });
    showLine(app.shown, true);
    toast(t('translated'));
  } catch { toast(t('transFail')); }
  btn.disabled = false; btn.textContent = t('translateAll');
}

// ------------------------------------------------------------------ word popup
const popup = $('#popup');
let popupState = { word: null, pinned: false, hideTimer: null, showTimer: null, resume: false, anchor: null };

function wordContext(el) {
  const li = el.closest('.sub-item');
  const idx = li ? Number(li.dataset.i) : app.shown;
  return { idx, text: app.cues[idx] ? app.cues[idx].text : '', offset: Number(el.dataset.s) };
}

function openPopup(el, pinned) {
  clearTimeout(popupState.hideTimer);
  const word = el.textContent;
  const ctx = wordContext(el);
  if (popupState.anchor) popupState.anchor.classList.remove('hl');
  popupState.anchor = el; el.classList.add('hl');
  popupState.word = word; popupState.pinned = pinned; popupState.ctx = ctx;
  // Pause while reading, like a reading assistant (resume when the popup closes).
  if (app.player && !app.player.paused() && el.closest('#lineText')) { app.player.pause(); popupState.resume = true; clearSchedule(); }
  renderPopup({ word, loading: true }, ctx);
  popup.hidden = false;
  positionPopup(el);
  lookup(word, { target: target(), native: native() }).then(res => {
    if (popupState.word !== word) return;
    renderPopup(res, ctx); positionPopup(el);
  }).catch(() => { if (popupState.word === word) renderPopup({ word, error: true }, ctx); });
}

function positionPopup(el) {
  const r = el.getBoundingClientRect(); const pr = popup.getBoundingClientRect();
  let left = Math.min(Math.max(8, r.left + r.width / 2 - pr.width / 2), innerWidth - pr.width - 8);
  let top = r.top - pr.height - 10;
  if (top < 8) top = Math.min(r.bottom + 10, innerHeight - pr.height - 8);
  popup.style.left = left + 'px'; popup.style.top = Math.max(8, top) + 'px';
}

function closePopup() {
  popup.hidden = true; popupState.word = null; popupState.pinned = false;
  if (popupState.anchor) popupState.anchor.classList.remove('hl');
  popupState.anchor = null;
  if (popupState.resume && app.player) { popupState.resume = false; app.player.play(); }
}

function renderPopup(res, ctx) {
  const w = res.word; const lw = w.toLowerCase().replace(/’/g, "'");
  const savedNow = store.isWordSaved(w);
  let html = `<div class="p-head"><span class="p-word" dir="auto">${esc(w)}</span>`;
  if (res.lemma && res.lemma.toLowerCase() !== lw) html += `<span class="muted">→ ${esc(res.lemma)}</span>`;
  if (res.phonetic) html += `<span class="p-ipa">${esc(res.phonetic)}</span>`;
  html += `</div>`;
  // contraction / reduction quick help
  if (/'/.test(lw) || REDUCTIONS[lw]) html += `<div class="p-phr">= <b>${esc(REDUCTIONS[lw] || expandContraction(lw))}</b></div>`;
  // phrasal verb containing this word
  const ph = phrasalAt(ctx.text).find(p => ctx.offset >= p.s && ctx.offset < p.e);
  if (ph) html += `<div class="p-phr">${t('partOf')}: <b>${esc(ph.name)}</b> — <span dir="auto">${esc(tr({ es: ph.es, ar: ph.ar }))}</span></div>`;
  if (res.loading) html += `<div class="loading">${t('loading')}</div>`;
  else if (res.error) html += `<div class="loading">${t('transFail')}</div>`;
  else {
    const main = res.translation && res.translation.main;
    if (main) html += `<div class="p-main" dir="auto">${esc(main)}${res.lemmaTranslation && res.lemmaTranslation.main && res.lemmaTranslation.main !== main ? ` <span class="muted small">(${esc(res.lemma)}: ${esc(res.lemmaTranslation.main)})</span>` : ''}</div>`;
    const alts = (res.translation && res.translation.alts) || (res.lemmaTranslation && res.lemmaTranslation.alts) || [];
    if (alts.length) html += `<div class="p-alts" dir="auto">${alts.slice(0, 3).map(a => `<div><b>${esc(posName(a.pos))}:</b> ${esc(a.terms.join(', '))}</div>`).join('')}</div>`;
    if (res.meanings && res.meanings.length) {
      html += `<div class="p-sec"><h5>${t('definition')}</h5>`;
      for (const m of res.meanings.slice(0, 2)) html += `<div class="p-def"><i class="muted">${esc(m.pos)}</i> ${esc(m.defs[0].def)}</div>`;
      if (res.defTr) html += `<div class="p-def muted" dir="auto">${esc(res.defTr)}</div>`;
      html += `</div>`;
    }
    if (res.examples && res.examples.length) {
      html += `<div class="p-sec"><h5>${t('examples')}</h5>${res.examples.map(e => `<div class="p-ex">“${esc(e.en)}”<span class="tr" dir="auto">${esc(e.tr)}</span></div>`).join('')}</div>`;
    }
    if (!main && !(res.meanings && res.meanings.length)) html += `<div class="loading">${t('notFound')}</div>`;
    html += `<div class="p-sec"><h5>${t('fromVideo')}</h5><div class="p-ex">“${esc(ctx.text)}”<span class="tr" dir="auto">${esc(transFor(ctx.idx))}</span></div></div>`;
  }
  html += `<div class="p-actions">
    <button class="btn small" data-a="listen">🔊 ${t('listen')}</button>
    <button class="btn small ${savedNow ? '' : 'primary'}" data-a="save">${savedNow ? '★ ' + t('unsave') : '☆ ' + t('saveWord')}</button>
    <button class="btn small" data-a="ai">✦ IA</button>
    <span class="spacer"></span><button class="btn small" data-a="close">✕</button></div>`;
  popup.innerHTML = html;
  popup.querySelector('[data-a=listen]').onclick = () => { if (res.audio) new Audio(res.audio).play().catch(() => speak(w, speechLocale(), 0.8)); else speak(w, speechLocale(), 0.8); };
  popup.querySelector('[data-a=save]').onclick = () => {
    if (store.isWordSaved(w)) { store.removeWord(w); toast(t('removed')); }
    else {
      store.saveWord({ word: w, lemma: res.lemma || w, meaning: (res.translation && res.translation.main) || '', ipa: res.phonetic || '', example: res.examples && res.examples[0] ? res.examples[0].en : '', exampleTr: res.examples && res.examples[0] ? res.examples[0].tr : '', context: ctx.text, contextTr: transFor(ctx.idx), line: ctx.idx, title: app.session ? app.session.title : '' });
      toast(t('saved'));
    }
    renderPopup(res, ctx); refreshSavedMarks(); renderSaved(); renderProgress();
  };
  popup.querySelector('[data-a=ai]').onclick = () => { closePopup(); openAi(ctx.idx, `Explain the word/expression "${w}" as used in this line: meaning here, other common meanings, and 3 simple example sentences.`); };
  popup.querySelector('[data-a=close]').onclick = closePopup;
}

function refreshSavedMarks() {
  const saved = store.savedWordSet();
  $$('.w').forEach(sp => sp.classList.toggle('saved', saved.has(sp.textContent.toLowerCase().replace(/’/g, "'"))));
}

function bindWordEvents(root) {
  root.addEventListener('mouseover', e => {
    const el = e.target.closest('.w');
    if (!el || popupState.pinned) return;
    if (matchMedia('(hover: none)').matches) return;
    clearTimeout(popupState.showTimer); clearTimeout(popupState.hideTimer);
    popupState.showTimer = setTimeout(() => openPopup(el, false), 180);
  });
  root.addEventListener('mouseout', e => {
    const el = e.target.closest('.w'); if (!el) return;
    clearTimeout(popupState.showTimer);
    if (!popupState.pinned) popupState.hideTimer = setTimeout(() => { if (!popup.matches(':hover')) closePopup(); }, 350);
  });
  root.addEventListener('click', e => {
    const el = e.target.closest('.w'); if (!el) return;
    e.stopPropagation();
    openPopup(el, true);
  });
}

// ------------------------------------------------------------------ grammar panel
function analysisText(i) {
  const c = app.cues[i]; if (!c) return { text: '', merged: false };
  const n = app.cues[i + 1];
  if (n && !/[.!?…"”)\]]\s*$/.test(c.text) && n.start - c.end < 1.5 && /^[a-z]/.test(n.text.trim())) return { text: c.text + ' ' + n.text, merged: true };
  return { text: c.text, merged: false };
}

function renderGrammarEmpty() { $('#grammarPanel').innerHTML = `<p class="muted">${t('emptyText')}</p>`; }

function markSentence(text, ranges) {
  const norm = normalize(text);
  const marks = new Array(norm.length).fill(false);
  for (const r of ranges) for (let k = r.s; k < r.e && k < marks.length; k++) marks[k] = true;
  let out = ''; let open = false;
  for (let k = 0; k < text.length; k++) {
    if (marks[k] && !open) { out += '<mark>'; open = true; }
    if (!marks[k] && open) { out += '</mark>'; open = false; }
    out += esc(text[k]);
  }
  if (open) out += '</mark>';
  return out;
}

const exTrCache = new Map();
function renderGrammar(i) {
  const host = $('#grammarPanel');
  if (!app.cues[i]) { renderGrammarEmpty(); return; }
  const { text, merged } = analysisText(i);
  const found = analyze(text);
  const lang = getLang();
  let html = `<div class="g-section-title">${t('grammarOf')}</div><div class="g-sentence" dir="ltr">${markSentence(text, found.filter(f => !['contractions'].includes(f.rule.id)).flatMap(f => f.matches))}</div>`;
  if (merged) html += `<p class="muted small">${t('mergedNext')}</p>`;
  const into = intonation(text);
  html += `<div class="speech-item">${t('intonation')}: <b style="font-size:18px">${into.arrow}</b> <span dir="auto">${esc(tr(into.text))}</span></div>`;
  if (!found.length) html += `<p class="muted">${t('noGrammar')}</p>`;
  for (const { rule, matches } of found) {
    const fr = matches.map(m => text.slice(m.s, m.e));
    // Group by detail (e.g. which modal, which conditional type).
    const byDetail = new Map();
    matches.forEach((m, k) => { const key = m.detail ?? '_'; if (!byDetail.has(key)) byDetail.set(key, []); byDetail.get(key).push({ m, frag: fr[k] }); });
    for (const [detail, items] of byDetail) {
      const d = rule.details && rule.details[detail];
      const name = d && d.name ? tr(d.name) : tr(rule.name);
      const structure = (d && d.structure) || rule.structure;
      const explain = d && d.explain ? tr(d.explain) : tr(rule.explain);
      const examples = (d && d.examples) || rule.examples || [];
      let foundHtml = items.map(x => `«${esc(x.frag.trim())}»`).join(', ');
      if (rule.id === 'contractions') foundHtml = items.map(x => `<b>${esc(x.frag)}</b> = ${esc(expandContraction(x.frag))}`).join(' · ');
      if (rule.id === 'reductions') foundHtml = items.map(x => `<b>${esc(x.frag)}</b> = ${esc(REDUCTIONS[x.frag.toLowerCase()] || '')}`).join(' · ');
      if (rule.id === 'phrasal') foundHtml = items.map(x => `<b>${esc(x.m.detail)}</b> (${esc(x.frag)}) — <span dir="auto">${esc(tr(x.m.meaning))}</span>`).join('<br>');
      const corpusKey = rule.id === 'phrasal' ? 'pv:' + detail : rule.id;
      const cnt = app.corpus && app.corpus.get(corpusKey) ? app.corpus.get(corpusKey).lines.length : 0;
      html += `<div class="g-card lvl-${rule.level}"><h4>${esc(name)} <span class="lvl">${rule.level}</span></h4>
        <div class="found">${foundHtml}</div>
        <div class="struct">${esc(structure)}</div>
        <p dir="auto">${esc(explain)}</p>
        ${examples.length ? `<ul>${examples.map(ex => `<li><span dir="ltr">${esc(ex)}</span><span class="ex-tr" data-ex="${esc(ex)}" dir="auto">${esc(exTrCache.get(lang + '|' + ex) || '')}</span></li>`).join('')}</ul>` : ''}
        ${rule.tip ? `<p class="tip" dir="auto">💡 ${esc(tr(rule.tip))}</p>` : ''}
        ${cnt > 1 ? `<button class="btn small see-all" data-key="${esc(corpusKey)}" data-label="${esc(rule.id === 'phrasal' ? detail : name)}">${t('seeAll')} (${cnt})</button>` : ''}
      </div>`;
    }
  }
  const sp = connectedSpeech(text);
  if (sp.length) {
    html += `<div class="g-section-title">${t('connected')}</div>`;
    for (const it of sp) html += `<div class="speech-item"><span dir="auto">${esc(tr(it.label))}</span>: ${it.from ? `${esc(it.from)} → <b>${esc(it.to)}</b>` : it.list.map(x => `<b>${esc(x)}</b>`).join(' · ')}</div>`;
  }
  html += `<button class="btn primary" id="gAi">✦ ${t('aiExplain')}</button>`;
  // corpus overview
  if (app.corpus) {
    const entries = [...app.corpus.values()].filter(e => !e.phrasal).sort((a, b) => b.lines.length - a.lines.length);
    const pvs = [...app.corpus.values()].filter(e => e.phrasal).sort((a, b) => b.lines.length - a.lines.length).slice(0, 15);
    html += `<div class="g-section-title">${t('corpusTitle')}</div><p class="muted small">${t('corpusHint')}</p><div class="corpus">${entries.map(e => `<button class="chip" data-key="${esc(e.rule.id)}" data-label="${esc(tr(e.rule.name))}">${esc(tr(e.rule.name))} <b>${e.lines.length}</b></button>`).join('')}</div>`;
    if (pvs.length) html += `<div class="corpus">${pvs.map(e => `<button class="chip" data-key="pv:${esc(e.phrasal)}" data-label="${esc(e.phrasal)}">${esc(e.phrasal)} <b>${e.lines.length}</b></button>`).join('')}</div>`;
  }
  host.innerHTML = html;
  host.querySelectorAll('[data-key]').forEach(b => b.onclick = () => {
    const e = app.corpus.get(b.dataset.key); if (!e) return;
    app.filter = { label: b.dataset.label, set: new Set(e.lines) };
    switchTab('subs'); applyListFilter();
  });
  $('#gAi').onclick = () => openAi(i);
  // Translate examples into the learner's language (cached).
  const pending = [...host.querySelectorAll('.ex-tr')].filter(el => !el.textContent);
  if (pending.length && target() !== native()) {
    const list = [...new Set(pending.map(el => el.dataset.ex))];
    translateLines(list, target(), native()).then(out => {
      list.forEach((ex, k) => exTrCache.set(lang + '|' + ex, out[k]));
      host.querySelectorAll('.ex-tr').forEach(el => { const v = exTrCache.get(lang + '|' + el.dataset.ex); if (v) el.textContent = v; });
    }).catch(() => {});
  }
}

// ------------------------------------------------------------------ AI dialog
let aiLine = -1;
async function openAi(i, question) {
  aiLine = i;
  const dlg = $('#dlgAi'); const body = $('#aiBody');
  $('#aiAnswer').textContent = ''; $('#aiQuestion').value = '';
  if (!dlg.open) dlg.showModal();
  const ai = store.getState().ai;
  const line = app.cues[i] ? app.cues[i].text : '';
  if (!ai.key) {
    body.innerHTML = `<div class="g-sentence" dir="ltr">${esc(line)}</div><p>${t('aiNoKey')}</p><button type="button" class="btn primary" id="aiGoSettings">${t('settings')}</button>`;
    $('#aiGoSettings').onclick = () => { dlg.close(); openSettings(); };
    return;
  }
  if (question) { body.innerHTML = `<div class="g-sentence" dir="ltr">${esc(line)}</div>`; return ask(question); }
  body.innerHTML = `<div class="g-sentence" dir="ltr">${esc(line)}</div><p class="muted">${t('aiThinking')}</p>`;
  try {
    const r = await explainLine({ key: ai.key, model: ai.model, line, prev: app.cues[i - 1] && app.cues[i - 1].text, next: app.cues[i + 1] && app.cues[i + 1].text, native: native(), target: target() });
    if (aiLine !== i) return;
    body.innerHTML = `<div class="g-sentence" dir="ltr">${esc(line)}</div>
      <div class="g-card"><h4>${t('natural')}</h4><p dir="auto">${esc(r.natural_translation)}</p><h4>${t('literal')}</h4><p dir="auto">${esc(r.literal_translation)}</p></div>
      ${(r.grammar || []).map(g => `<div class="g-card"><h4 dir="auto">${esc(g.structure)}</h4><div class="found">«${esc(g.fragment)}»</div><p dir="auto">${esc(g.explanation)}</p><p dir="auto"><b>→</b> ${esc(g.how_to_use)}</p><ul>${(g.examples || []).map(e => `<li><span dir="ltr">${esc(e.en)}</span><span class="ex-tr" dir="auto">${esc(e.translation)}</span></li>`).join('')}</ul></div>`).join('')}
      ${(r.vocabulary || []).length ? `<div class="g-card"><h4>${t('vocab')}</h4><ul>${r.vocabulary.map(v => `<li><b dir="ltr">${esc(v.term)}</b> — <span dir="auto">${esc(v.meaning)}</span><span class="ex-tr" dir="ltr">${esc(v.example)}</span></li>`).join('')}</ul></div>` : ''}
      ${(r.pronunciation || []).length ? `<div class="g-card"><h4>${t('pronunciation')}</h4><ul>${r.pronunciation.map(p => `<li dir="auto">${esc(p)}</li>`).join('')}</ul></div>` : ''}
      ${r.usage_note ? `<div class="g-card"><h4>${t('culture')}</h4><p dir="auto">${esc(r.usage_note)}</p></div>` : ''}`;
  } catch (e) {
    body.innerHTML = `<div class="g-sentence" dir="ltr">${esc(line)}</div><p class="hint warn">${t('aiError')}: ${esc(e.message)}</p>`;
  }
}
async function ask(question) {
  const ai = store.getState().ai; const out = $('#aiAnswer');
  if (!ai.key) { out.textContent = t('aiNoKey'); return; }
  out.textContent = t('aiThinking');
  try {
    out.textContent = await askAbout({ key: ai.key, model: ai.model, line: app.cues[aiLine] ? app.cues[aiLine].text : '', question, native: native(), target: target() });
  } catch (e) { out.textContent = `${t('aiError')}: ${e.message}`; }
}

// ------------------------------------------------------------------ recording
async function startRecording({ auto = false, line = currentIndex(), overlay = false } = {}) {
  if (recorder.recording) return;
  try { await recorder.start(speechLocale()); }
  catch { toast(t('recNoMic'), 5000); return; }
  engine.recAuto = auto; engine.recOverlay = overlay; lastRecLine = line;
  $('#btnRecord').classList.add('recording');
  $('#recStats').textContent = t('recording');
  $('#scoreBox').innerHTML = '';
}
async function stopRecording() {
  if (!recorder.recording) return;
  $('#btnRecord').classList.remove('recording');
  engine.recAuto = false; engine.recOverlay = false;
  const rec = await recorder.stop();
  lastRec = rec;
  store.bump('recordings');
  const cue = app.cues[lastRecLine];
  drawWave($('#wave'), rec && rec.peaks);
  const orig = cue ? (cue.end - cue.start) / (Number(S().rate) || 1) : 0;
  $('#recStats').innerHTML = `<span>${t('origDur')}: <b>${orig.toFixed(1)}s</b></span><span>${t('yourDur')}: <b>${rec.duration.toFixed(1)}s</b></span><span>${cue ? `${t('line')} ${lastRecLine + 1}` : ''}</span>`;
  if (cue && rec.transcript) {
    const sc = scoreSpeech(cue.text, rec.transcript);
    $('#scoreBox').innerHTML = `<span class="big" style="color:${sc.score >= 80 ? 'var(--good)' : sc.score >= 50 ? 'var(--warn)' : 'var(--bad)'}">${sc.score}%</span><span class="muted small">${t('score')}</span><div dir="ltr">${sc.marks.map(m => `<span class="${m.ok ? 'ok' : 'miss'}">${esc(m.w)}</span>`).join(' ')}</div><div class="muted small" dir="ltr">${t('recognized')}: “${esc(rec.transcript)}”</div>`;
  } else if (cue && !Recorder.recognitionSupported()) {
    $('#scoreBox').innerHTML = `<span class="muted small">${t('noRecog')}</span>`;
  }
  updateButtons(); renderProgress();
}
function toggleRecord() {
  if (recorder.recording) { stopRecording(); return; }
  const s = S();
  if (s.overlayRecord && app.player) {
    const i = currentIndex();
    clearSchedule();
    startRecording({ line: i, overlay: true }).then(() => seekToLine(i, true));
  } else {
    if (app.player && !app.player.paused()) app.player.pause();
    clearSchedule();
    startRecording({ line: currentIndex() });
  }
}
function playMine() {
  if (!lastRec) return;
  const peaks = lastRec.peaks; const dur = lastRec.duration; const t0 = performance.now();
  const audio = recorder.play(() => drawWave($('#wave'), peaks));
  if (!audio) return;
  const anim = () => { if (audio.paused || audio.ended) return; drawWave($('#wave'), peaks, { progress: (performance.now() - t0) / 1000 / dur }); requestAnimationFrame(anim); };
  requestAnimationFrame(anim);
}
function compare() {
  if (!lastRec || !app.player || lastRecLine < 0) return;
  clearSchedule();
  engine.playOnce = () => setTimeout(playMine, 250);
  seekToLine(lastRecLine, true);
}

// ------------------------------------------------------------------ translation exercise
async function checkTranslation() {
  const mine = $('#transInput').value.trim();
  const i = app.shown;
  if (!mine) { toast(t('writeFirst')); return; }
  const ref = transFor(i) || await ensureTrans(i);
  const sim = similarity(mine, ref);
  app.checked = app.checked || {}; app.checked[i] = true;
  $('#transScore').textContent = `${sim}% ${t('similarity')}`;
  $('#transScore').style.color = sim >= 60 ? 'var(--good)' : sim >= 35 ? 'var(--warn)' : 'var(--bad)';
  $('#transResult').innerHTML = `<div class="cmp"><span class="lbl">${t('yourTrans')}</span><span>${esc(mine)}</span><span class="lbl">${t('refTrans')}</span><span>${esc(ref)}</span></div>`;
  $('#lineTrans').classList.remove('off'); $('#lineTrans').textContent = ref;
  store.bump('translations'); store.bump('transScoreSum', sim);
  renderProgress();
}

// ------------------------------------------------------------------ saved
let savedView = 'words';
let reviewQueue = null;
function renderSaved() {
  const host = $('#savedPanel'); const p = P();
  const words = Object.values(p.saved.words).sort((a, b) => b.added - a.added);
  const sents = p.saved.sentences;
  if (savedView === 'words') {
    if (!words.length) { host.innerHTML = `<p class="muted">${t('nothingSaved')}</p>`; return; }
    host.innerHTML = words.map(w => `<div class="saved-item"><div class="hd"><b dir="ltr">${esc(w.word)}</b>${w.ipa ? `<span class="muted small">${esc(w.ipa)}</span>` : ''}<span class="spacer"></span><button class="mini" data-say="${esc(w.word)}">🔊</button><button class="mini" data-del="${esc(w.word)}">✕</button></div>
      <div dir="auto">${esc(w.meaning)}</div>${w.example ? `<div class="ctx" dir="ltr">“${esc(w.example)}”</div>` : ''}<div class="ctx" dir="ltr">🎬 ${esc(w.context || '')}</div></div>`).join('');
    host.querySelectorAll('[data-say]').forEach(b => b.onclick = () => speak(b.dataset.say, speechLocale(), 0.8));
    host.querySelectorAll('[data-del]').forEach(b => b.onclick = () => { store.removeWord(b.dataset.del); renderSaved(); refreshSavedMarks(); });
  } else if (savedView === 'sentences') {
    if (!sents.length) { host.innerHTML = `<p class="muted">${t('nothingSaved')}</p>`; return; }
    host.innerHTML = sents.map((s, k) => `<div class="saved-item"><div class="hd"><span dir="ltr">${esc(s.text)}</span><span class="spacer"></span><button class="mini" data-say="${k}">🔊</button><button class="mini" data-del="${k}">✕</button></div><div class="ctx" dir="auto">${esc(s.trans || '')}</div>
      <div class="ctx">${esc(s.title || '')}${s.title && app.session && s.title === app.session.title ? ` · <a href="#" data-go="${s.line}">${t('jump')}</a>` : ''}</div></div>`).join('');
    host.querySelectorAll('[data-say]').forEach(b => b.onclick = () => speak(sents[Number(b.dataset.say)].text, speechLocale(), 0.85));
    host.querySelectorAll('[data-del]').forEach(b => b.onclick = () => { store.toggleSentence(sents[Number(b.dataset.del)]); renderSaved(); buildSubListStars(); });
    host.querySelectorAll('[data-go]').forEach(a => a.onclick = e => { e.preventDefault(); gotoLine(Number(a.dataset.go)); });
  } else {
    if (!words.length) { host.innerHTML = `<p class="muted">${t('nothingSaved')}</p>`; return; }
    if (!reviewQueue || !reviewQueue.length) reviewQueue = words.slice().sort((a, b) => (a.box || 0) - (b.box || 0) || Math.random() - 0.5).slice(0, 20);
    const card = reviewQueue[0];
    if (!card) { host.innerHTML = `<div class="flash"><div class="front">🎉</div><div>${t('reviewDone')}</div></div>`; return; }
    host.innerHTML = `<div class="flash"><div class="front" dir="ltr">${esc(card.word)}</div><div class="ctx muted" dir="ltr">${esc(card.context || '')}</div>
      <div class="back" hidden dir="auto"><b>${esc(card.meaning)}</b><div class="muted small" dir="ltr">${esc(card.example || '')}</div><div class="muted small" dir="auto">${esc(card.exampleTr || '')}</div></div>
      <div class="row" style="justify-content:center"><button class="btn" data-a="say">🔊</button><button class="btn primary" data-a="show">${t('show')}</button></div>
      <div class="row" style="justify-content:center" hidden data-row="grade"><button class="btn" data-a="again">${t('again')}</button><button class="btn primary" data-a="know">${t('know')}</button></div>
      <div class="muted small">${reviewQueue.length}</div></div>`;
    host.querySelector('[data-a=say]').onclick = () => speak(card.word, speechLocale(), 0.8);
    host.querySelector('[data-a=show]').onclick = () => { host.querySelector('.back').hidden = false; host.querySelector('[data-row=grade]').hidden = false; host.querySelector('[data-a=show]').hidden = true; };
    host.querySelector('[data-a=know]').onclick = () => { const w = P().saved.words[store.wordKey(card.word)]; if (w) w.box = (w.box || 0) + 1; store.persist(); reviewQueue.shift(); renderSaved(); };
    host.querySelector('[data-a=again]').onclick = () => { const w = P().saved.words[store.wordKey(card.word)]; if (w) w.box = 0; store.persist(); reviewQueue.push(reviewQueue.shift()); renderSaved(); };
  }
}
function buildSubListStars() {
  $$('#subList .sub-item').forEach(li => { const on = store.isSentenceSaved(app.cues[Number(li.dataset.i)].text); const b = li.querySelector('.star'); b.classList.toggle('on', on); b.textContent = on ? '★' : '☆'; });
  if (app.cues[app.shown]) { const on = store.isSentenceSaved(app.cues[app.shown].text); $('#btnSaveLine').textContent = on ? '★' : '☆'; $('#btnSaveLine').classList.toggle('on', on); }
}
function toggleSaveLine(i) {
  const c = app.cues[i]; if (!c) return;
  const on = store.toggleSentence({ text: c.text, trans: transFor(i), line: i, title: app.session ? app.session.title : '' });
  toast(on ? t('saved') : t('removed'));
  buildSubListStars(); renderSaved();
}
function exportCsv() {
  const p = P();
  const rows = [['word', 'meaning', 'ipa', 'example', 'example_translation', 'context', 'context_translation']];
  for (const w of Object.values(p.saved.words)) rows.push([w.word, w.meaning, w.ipa, w.example, w.exampleTr, w.context, w.contextTr]);
  for (const s of p.saved.sentences) rows.push([s.text, s.trans, '', '', '', s.title, '']);
  const csv = rows.map(r => r.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
  download(`shadowlab-${p.name}.csv`, '﻿' + csv, 'text/csv');
}
function download(name, text, type) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

// ------------------------------------------------------------------ routine & progress
function renderRoutine() {
  const host = $('#routinePanel'); const p = P();
  const key = app.session ? app.session.title : '_';
  const done = p.routine[key] || {};
  host.innerHTML = `<h3 style="margin:4px 0">${t('routineTitle')}</h3>` + ROUTINE.map((st, k) => `
    <div class="step${done[k] ? ' done' : ''}"><input type="checkbox" data-k="${k}" ${done[k] ? 'checked' : ''}><h4 dir="auto">${esc(tr(st.title))}</h4><p dir="auto">${esc(tr(st.text))}</p>
    <button class="btn small" data-mode="${st.mode}">${t('useMode')}: ${t('m_' + st.mode)}</button></div>`).join('') +
    `<button class="btn small" id="btnResetRoutine">${t('resetRoutine')}</button>
    <h3 style="margin:8px 0 0">${t('mistakesTitle')}</h3><ul class="tips">${MISTAKES.map(m => `<li dir="auto">${esc(tr(m))}</li>`).join('')}</ul>`;
  host.querySelectorAll('input[data-k]').forEach(cb => cb.onchange = () => { p.routine[key] = p.routine[key] || {}; p.routine[key][cb.dataset.k] = cb.checked; store.persist(); renderRoutine(); });
  host.querySelectorAll('[data-mode]').forEach(b => b.onclick = () => setMode(b.dataset.mode));
  $('#btnResetRoutine').onclick = () => { p.routine[key] = {}; store.persist(); renderRoutine(); };
}
function renderProgress() {
  const p = P(); const st = p.stats;
  const minutes = Math.round(Object.values(st.days).reduce((a, b) => a + b, 0) / 60);
  const avg = st.translations ? Math.round(st.transScoreSum / st.translations) + '%' : '—';
  let heat = '';
  const d = new Date(); d.setDate(d.getDate() - 27);
  for (let k = 0; k < 28; k++) {
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const v = st.days[key] || 0;
    heat += `<i class="${v > 900 ? 'l3' : v > 300 ? 'l2' : v > 30 ? 'l1' : ''}" title="${key}: ${Math.round(v / 60)} min"></i>`;
    d.setDate(d.getDate() + 1);
  }
  $('#progressPanel').innerHTML = `<h3 style="margin:4px 0">${esc(p.name)}</h3><div class="stat-grid">
    <div class="stat"><b>${store.streak()}🔥</b><span>${t('stStreak')}</span></div>
    <div class="stat"><b>${minutes}</b><span>${t('stMin')}</span></div>
    <div class="stat"><b>${st.lines}</b><span>${t('stLines')}</span></div>
    <div class="stat"><b>${st.recordings}</b><span>${t('stRec')}</span></div>
    <div class="stat"><b>${Object.keys(p.saved.words).length}</b><span>${t('stWords')}</span></div>
    <div class="stat"><b>${avg}</b><span>${t('stTrans')}</span></div></div>
    <div class="g-section-title">${t('last4w')}</div><div class="heat">${heat}</div>`;
}
let pendingSec = 0;
function statsTick() {
  if ((app.player && !app.player.paused()) || recorder.recording) {
    pendingSec++;
    if (pendingSec >= 10) { store.addPracticeSeconds(pendingSec); pendingSec = 0; if ($('[data-panel=progress]').classList.contains('active')) renderProgress(); }
  }
}
addEventListener('pagehide', () => { if (pendingSec) store.addPracticeSeconds(pendingSec); store.persist(true); recorder.release(); });

// ------------------------------------------------------------------ settings
function openSettings() {
  const st = store.getState();
  const langOpts = sel => Object.entries(LANGS).map(([k, v]) => `<option value="${k}" ${k === sel ? 'selected' : ''}>${v}</option>`).join('');
  $('#profileEditor').innerHTML = Object.values(st.profiles).map(p => `
    <div class="profile-row" data-id="${p.id}">
      <label class="field"><span>${t('profileName')}</span><input class="input" data-f="name" value="${esc(p.name)}"></label>
      <label class="field"><span>${t('nativeLang')}</span><select class="select" data-f="native">${langOpts(p.native)}</select></label>
      <label class="field"><span>${t('targetLang')}</span><select class="select" data-f="target">${langOpts(p.target)}</select></label>
    </div>`).join('');
  $('#aiKey').value = st.ai.key || '';
  $('#aiModel').value = st.ai.model || 'claude-opus-5-5';
  $('#dlgSettings').showModal();
}
function saveSettings() {
  const st = store.getState();
  $$('#profileEditor .profile-row').forEach(row => {
    const p = st.profiles[row.dataset.id];
    p.name = row.querySelector('[data-f=name]').value.trim() || p.name;
    p.native = row.querySelector('[data-f=native]').value;
    p.target = row.querySelector('[data-f=target]').value;
  });
  st.ai.key = $('#aiKey').value.trim();
  st.ai.model = $('#aiModel').value;
  store.persist(true);
  applyLanguage();
}


// ------------------------------------------------------------------ listening game ("Escucha y completa")
const game = new Game({
  cues: () => app.cues,
  seekToLine: (i, play) => { clearSchedule(); seekToLine(i, play); },
  pause: () => { if (app.player) app.player.pause(); },
  play: () => { if (app.player) app.player.play(); },
  t,
  renderLine: i => { if (app.shown === i) { renderGameLine(i); renderHud(); } else showLine(i, true); },
  renderTimer: (frac, left) => renderTimer(frac, left),
  focusBlank: (i, bi) => { if (app.shown !== i || bi < 0) return; const el = $(`#lineText .blank-in[data-b="${bi}"]`); if (el) el.focus({ preventScroll: true }); },
  flash: (msg, kind) => flash(msg, kind),
  floatPoints: txt => floatText(txt, 'pts'),
  onChange: () => { document.body.classList.toggle('game-running', game.running); renderHud(); renderGameChrome(true); },
  onFinish: r => showResults(r),
});

function setApp(name) {
  const on = name === 'game';
  if (on === game.active) return;
  game.active = on;
  if (!on && game.running) game.stop();
  document.body.classList.toggle('game-mode', on);
  $$('#appSwitch .app-btn').forEach(b => b.classList.toggle('active', b.dataset.app === name));
  clearSchedule(); engine.loopCount = 0;
  if (app.player && !app.player.paused()) app.player.pause();
  renderGameChrome();
  if (app.cues.length) showLine(app.shown, true);
}

function gameKey() { return (app.session ? app.session.title : '') + '|' + game.level; }

function renderGameChrome(light = false) {
  const active = game.active;
  const startEl = $('#gameStart'); const hud = $('#gameHud'); const bar = $('#gameBar');
  hud.hidden = !active || !game.running;
  $('#gameTimer').hidden = !active || !game.running || !game.timer;
  $('#lineText').hidden = active && !game.running;
  startEl.hidden = !active || game.running;
  if (active && !game.running && !light) {
    const best = P().game.best;
    const title = app.session ? app.session.title : '';
    startEl.innerHTML = `<h2 class="grad-text">🎧 ${t('gameTitle')}</h2><p class="muted" dir="auto">${t('gameIntro')}</p>
      <div class="levels">${Object.entries(LEVELS).map(([k, L]) => `<button class="level-card lv-${k}${game.level === k ? ' sel' : ''}" data-lv="${k}">
        <span class="lv-emoji">${L.emoji}</span><b>${t('lvl_' + k)}</b><small dir="auto">${t('lvlDesc_' + k)}</small>
        ${best[title + '|' + k] ? `<span class="lv-best">🏆 ${best[title + '|' + k]}</span>` : ''}</button>`).join('')}</div>
      ${app.cues.length ? `<div class="row wrap" style="justify-content:center"><button class="btn primary big" data-go="0">▶ ${t('startBegin')}</button>${app.shown > 0 ? `<button class="btn big" data-go="here">${t('startHere')} (${app.shown + 1})</button>` : ''}</div>`
        : `<div class="row wrap" style="justify-content:center"><button class="btn primary big" data-load>${t('load')}</button><button class="btn big" data-demo>${t('tryDemo')}</button></div>`}
      <p class="muted small">${t('gameKeys')}</p>`;
    startEl.querySelectorAll('[data-lv]').forEach(b => b.onclick = () => { game.level = b.dataset.lv; renderGameChrome(); });
    startEl.querySelectorAll('[data-go]').forEach(b => b.onclick = () => { if (!app.player) return; game.start(game.level, b.dataset.go === 'here' ? app.shown : 0); });
    const l = startEl.querySelector('[data-load]'); if (l) l.onclick = openLoad;
    const d = startEl.querySelector('[data-demo]'); if (d) d.onclick = () => $('#btnDemo').click();
  }
  if (active) {
    bar.innerHTML = game.running ? `
      <button class="btn" data-g="replay">↺ ${t('replay')}</button>
      <button class="btn" data-g="hint">💡 ${t('hint')}</button>
      <button class="btn" data-g="skip">⏭ ${t('skip')}</button>
      <button class="chip${S().gameShowTrans ? ' on' : ''}" data-g="trans"><span class="dot"></span>${t('showTrans')}</button>
      <span class="spacer"></span>
      <button class="btn danger" data-g="quit">✕ ${t('quit')}</button>` : '';
    bar.querySelectorAll('[data-g]').forEach(b => b.onclick = () => gameAction(b.dataset.g));
  }
  if (active) $('#emptyState').hidden = true;
  else $('#emptyState').hidden = !!app.player;
}

function gameAction(a) {
  const i = app.shown;
  if (a === 'replay') repeatLine();
  if (a === 'hint') game.hint(i);
  if (a === 'skip') { if (game.waiting) game.timeUp(true); else { const ln = game.line(i); ln.blanks.forEach(b => { if (!b.done && !b.revealed) { b.revealed = true; game.missedWords.push(b.word); } }); game.combo = 0; renderGameLine(i); renderHud(); } }
  if (a === 'trans') { S().gameShowTrans = !S().gameShowTrans; store.persist(); renderGameChrome(true); showLine(app.shown, true); }
  if (a === 'quit') game.finish(true);
}

function renderGameLine(i) {
  const host = $('#lineText');
  host.classList.remove('hidden-text');
  const cue = app.cues[i]; if (!cue) { host.innerHTML = ''; return; }
  if (!game.running) { host.innerHTML = ''; return; }
  const { toks, blanks } = game.line(i);
  const byTok = new Map(blanks.map((b, bi) => [b.tokIdx, bi]));
  const focused = document.activeElement && document.activeElement.classList.contains('blank-in') ? Number(document.activeElement.dataset.b) : -1;
  host.innerHTML = toks.map((k, ti) => {
    if (!byTok.has(ti)) return k.w ? `<span class="w" data-s="${k.s}">${esc(k.t)}</span>` : esc(k.t);
    const bi = byTok.get(ti); const b = blanks[bi];
    if (b.done) return `<span class="w blank ok" data-s="${k.s}">${esc(b.word)}</span>`;
    if (b.revealed) return `<span class="w blank miss" data-s="${k.s}">${esc(b.word)}</span>`;
    const w = Math.max(3, [...b.word].length);
    return `<input class="blank-in" data-b="${bi}" data-i="${i}" value="${esc(b.typed)}" style="width:calc(${w}ch + 18px)" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" dir="ltr" aria-label="blank ${bi + 1}">`;
  }).join('');
  const next = blanks.findIndex(b => !b.done && !b.revealed);
  const want = focused >= 0 && blanks[focused] && !blanks[focused].done ? focused : next;
  if (want >= 0) { const el = host.querySelector(`.blank-in[data-b="${want}"]`); if (el) { el.focus({ preventScroll: true }); const v = el.value; el.setSelectionRange(v.length, v.length); } }
}

function bindGameInputs() {
  const host = $('#lineText');
  host.addEventListener('input', e => {
    const el = e.target.closest('.blank-in'); if (!el) return;
    const res = game.type(Number(el.dataset.i), Number(el.dataset.b), el.value);
    if (res === 'prefix' || res === 'wrong' || res === '') { el.classList.toggle('wrong', res === 'wrong'); el.classList.toggle('prefix', res === 'prefix'); }
    if (res === 'wrong') { el.classList.remove('shake'); void el.offsetWidth; el.classList.add('shake'); }
  });
  host.addEventListener('keydown', e => {
    const el = e.target.closest('.blank-in'); if (!el) return;
    if (e.key === 'Enter') { e.preventDefault(); gameAction('replay'); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); gameAction('hint'); }
    else if (e.key === 'Escape') { e.preventDefault(); gameAction('skip'); }
    else if (e.key === 'Backspace' && !el.value) { const prev = el.previousElementSibling && [...host.querySelectorAll('.blank-in')].filter(x => Number(x.dataset.b) < Number(el.dataset.b)).pop(); if (prev) { e.preventDefault(); prev.focus(); } }
    else if (e.key === ' ' || e.key === 'Tab') {
      const all = [...host.querySelectorAll('.blank-in')]; const k = all.indexOf(el);
      if (all[k + 1] && e.key === ' ' && el.value.trim()) { e.preventDefault(); all[k + 1].focus(); }
    }
  });
}

function renderHud() {
  if (!game.active) return;
  const hud = $('#gameHud');
  hud.hidden = !game.running;
  $('#gameTimer').hidden = !game.running || !game.timer;
  if (!game.running) return;
  const L = LEVELS[game.level];
  const hearts = '❤️'.repeat(Math.max(0, game.lives)) + '🖤'.repeat(Math.max(0, L.lives - game.lives));
  const mult = Math.min(3, 1 + Math.floor(game.combo / 5) * 0.5);
  hud.innerHTML = `<span class="hud-pill lv-${game.level}">${L.emoji} ${t('lvl_' + game.level)}</span>
    <span class="hud-score"><small>${t('g_score')}</small><b>${game.score}</b></span>
    <span class="hud-pill combo${game.combo >= 5 ? ' hot' : ''}">🔥 ${game.combo}${mult > 1 ? ` · ×${mult}` : ''}</span>
    <span class="hud-hearts" title="${t('lives')}">${hearts}</span>
    <span class="hud-state">${game.waiting ? t('typeNow') : t('listening')}</span>`;
}

function renderTimer(frac, left) {
  const tm = $('#gameTimer'); tm.hidden = false;
  const bar = tm.querySelector('i');
  bar.style.width = (frac * 100).toFixed(1) + '%';
  bar.style.background = frac > 0.5 ? 'var(--good)' : frac > 0.25 ? 'var(--warn)' : 'var(--bad)';
  tm.querySelector('.secs').textContent = left.toFixed(1) + 's';
  tm.classList.toggle('urgent', frac <= 0.25);
}

function flash(msg, kind = 'good') { floatText(msg, 'flash ' + kind); }
function floatText(txt, cls) {
  const layer = $('#floatLayer');
  const el = document.createElement('div');
  el.className = 'float ' + cls; el.textContent = txt;
  layer.appendChild(el);
  setTimeout(() => el.remove(), 1400);
}

function showResults(r) {
  const p = P(); const key = gameKey();
  const prevBest = p.game.best[key] || 0;
  const isBest = r.score > prevBest;
  if (isBest) p.game.best[key] = r.score;
  p.game.played = (p.game.played || 0) + 1;
  store.persist();
  const stars = r.accuracy >= 90 ? 3 : r.accuracy >= 70 ? 2 : r.accuracy >= 40 ? 1 : 0;
  const order = Object.keys(LEVELS); const nextLv = order[order.indexOf(r.level) + 1];
  const host = $('#gameResults');
  host.innerHTML = `<header class="dlg-head"><h2>${r.lives <= 0 ? t('gameOverLives') : r.quit ? '🏁 ' + t('results') : t('gameDone')}</h2><button class="icon-btn" value="cancel">✕</button></header>
    <div class="res-stars">${'⭐'.repeat(stars)}${'☆'.repeat(3 - stars)}</div>
    <div class="res-score grad-text">${r.score}</div>
    ${isBest ? `<div class="res-best">${t('newBest')}</div>` : `<div class="muted" style="text-align:center">${t('best')}: ${prevBest}</div>`}
    <div class="stat-grid three">
      <div class="stat"><b>${r.accuracy}%</b><span>${t('accuracy')}</span></div>
      <div class="stat"><b>${r.maxCombo}</b><span>${t('maxCombo')}</span></div>
      <div class="stat"><b>${r.correct}</b><span>${t('words')}</span></div>
    </div>
    ${r.missed.length ? `<h3>${t('missedWords')}</h3><div class="missed">${r.missed.slice(0, 40).map(w => `<span class="tag big" dir="ltr">${esc(w)}</span>`).join('')}</div>
      <button type="button" class="btn" id="btnSaveMissed">☆ ${t('saveMissed')}</button>` : ''}
    <div class="dlg-foot"><button type="button" class="btn" data-r="exit">${t('exitGame')}</button><span class="spacer"></span>
      <button type="button" class="btn" data-r="again">↺ ${t('playAgain')}</button>
      ${nextLv ? `<button type="button" class="btn primary" data-r="next">${LEVELS[nextLv].emoji} ${t('nextLevel')}</button>` : ''}</div>`;
  const dlg = $('#dlgGame');
  host.querySelector('[data-r=exit]').onclick = () => { dlg.close(); renderGameChrome(); };
  host.querySelector('[data-r=again]').onclick = () => { dlg.close(); game.start(r.level, game.startIdx || 0); };
  const nx = host.querySelector('[data-r=next]'); if (nx) nx.onclick = () => { dlg.close(); game.start(nextLv, game.startIdx || 0); };
  const sm = host.querySelector('#btnSaveMissed');
  if (sm) sm.onclick = async () => {
    sm.disabled = true;
    let n = 0;
    for (const w of r.missed.slice(0, 40)) {
      if (store.isWordSaved(w)) continue;
      let meaning = '';
      try { meaning = await translate(w, target(), native()); } catch {}
      const line = app.cues.findIndex(c => c.text.includes(w));
      store.saveWord({ word: w, lemma: w, meaning, ipa: '', example: '', exampleTr: '', context: line >= 0 ? app.cues[line].text : '', contextTr: line >= 0 ? transFor(line) : '', line, title: app.session ? app.session.title : '' });
      n++;
    }
    sm.textContent = `✓ ${n} ${t('savedN')}`;
    renderSaved(); refreshSavedMarks(); renderProgress();
  };
  dlg.onclose = () => renderGameChrome();
  if (!dlg.open) dlg.showModal();
  renderGameChrome();
}

// ------------------------------------------------------------------ misc UI
function switchTab(name) {
  $$('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  $$('.panel').forEach(p => p.classList.toggle('active', p.dataset.panel === name));
  if (name === 'progress') renderProgress();
  if (name === 'subs' && app.shown >= 0) { userScrolledAt = 0; highlightList(app.shown); }
}
function updateButtons() {
  const has = !!app.player && app.cues.length > 0;
  ['#btnPrev', '#btnRepeat', '#btnNext'].forEach(s => { $(s).disabled = !has; });
  $('#btnPlayMine').disabled = !lastRec;
  $('#btnCompare').disabled = !lastRec || !has;
}
let toastTimer = null;
function toast(msg, ms = 2600) {
  const el = $('#toast'); el.textContent = msg; el.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.hidden = true; }, ms);
}
function toggleFullscreen() {
  const st = $('#stage');
  if (document.fullscreenElement) document.exitFullscreen(); else if (st.requestFullscreen) st.requestFullscreen().catch(() => {});
}

function bindUI() {
  $('#btnLoad').onclick = openLoad; $('#btnLoad2').onclick = openLoad;
  $('#btnDemo').onclick = () => loadSession({ kind: 'tts', subsText: DEMO_SRT, subs2Text: '', title: t('demoTitle') });
  $('#btnSettings').onclick = openSettings;
  $('#btnHelp').onclick = () => $('#dlgHelp').showModal();
  $('#btnSaveSettings').onclick = () => saveSettings();
  $('#btnDoLoad').onclick = e => { e.preventDefault(); doLoadFromDialog(); };
  $$('#srcSeg .seg-btn').forEach(b => b.onclick = () => {
    $$('#srcSeg .seg-btn').forEach(x => x.classList.toggle('active', x === b));
    $$('.src-pane').forEach(p => { p.hidden = p.dataset.src !== b.dataset.v; });
    $('#urlHint').innerHTML = t('urlHint');
  });
  $('#inUrl').addEventListener('input', () => {
    const u = $('#inUrl').value.trim();
    $('#urlHint').innerHTML = u && isUnsupportedHost(u) ? `<b style="color:var(--warn)">${esc(t('unsupportedSite'))}</b>` : t('urlHint');
  });

  $('#btnPlay').onclick = togglePlay;
  $$('#appSwitch .app-btn').forEach(b => b.onclick = () => setApp(b.dataset.app));
  bindGameInputs();
  $('#btnPrev').onclick = prevLine; $('#btnNext').onclick = nextLine; $('#btnRepeat').onclick = repeatLine;
  $('#btnRecord').onclick = toggleRecord; $('#btnPlayMine').onclick = playMine; $('#btnCompare').onclick = compare;
  $('#modeSelect').onchange = e => setMode(e.target.value);
  $('#rateSelect').onchange = e => { S().rate = Number(e.target.value); store.persist(); applySettingsToPlayer(); };
  $('#btnSpeakLine').onclick = () => { const c = app.cues[app.shown]; if (c) speak(c.text, speechLocale(), 0.8); };
  $('#btnSaveLine').onclick = () => toggleSaveLine(app.shown);
  $('#btnAiLine').onclick = () => { if (app.cues[app.shown]) openAi(app.shown); };
  $('#btnFullscreen').onclick = toggleFullscreen;
  $('#btnCheckTrans').onclick = checkTranslation;
  $('#transInput').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); checkTranslation(); } });
  $('#btnTranslateAll').onclick = translateAll;
  $('#subSearch').addEventListener('input', applyListFilter);
  $('#btnExportCsv').onclick = exportCsv;
  $('#btnAiAsk').onclick = () => { const q = $('#aiQuestion').value.trim(); if (q) ask(q); };
  $('#aiQuestion').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); $('#btnAiAsk').click(); } });
  $$('.tab').forEach(b => b.onclick = () => switchTab(b.dataset.tab));
  $$('#savedSeg .seg-btn').forEach(b => b.onclick = () => { $$('#savedSeg .seg-btn').forEach(x => x.classList.toggle('active', x === b)); savedView = b.dataset.v; reviewQueue = null; renderSaved(); });

  // subtitle list: click to jump, star to save, hover words for dictionary
  const ol = $('#subList');
  ol.addEventListener('click', e => {
    const li = e.target.closest('.sub-item'); if (!li) return;
    if (e.target.closest('.w')) return;
    const i = Number(li.dataset.i);
    if (e.target.closest('.star')) { toggleSaveLine(i); return; }
    if (game.active && game.running) return;
    gotoLine(i);
  });
  ol.addEventListener('mouseover', e => { const li = e.target.closest('.sub-item'); if (li) tokenizeListItem(li); });
  ol.addEventListener('touchstart', e => { const li = e.target.closest('.sub-item'); if (li) tokenizeListItem(li); }, { passive: true });
  ol.addEventListener('wheel', () => { userScrolledAt = Date.now(); }, { passive: true });
  ol.addEventListener('touchmove', () => { userScrolledAt = Date.now(); }, { passive: true });
  bindWordEvents($('#lineText')); bindWordEvents(ol);
  popup.addEventListener('mouseleave', () => { if (!popupState.pinned) popupState.hideTimer = setTimeout(closePopup, 300); });
  popup.addEventListener('mouseenter', () => clearTimeout(popupState.hideTimer));
  document.addEventListener('click', e => { if (!popup.hidden && !popup.contains(e.target) && !e.target.closest('.w')) closePopup(); });

  // settings: export/import/reset
  $('#btnExportData').onclick = () => download('shadowlab-backup.json', store.exportJSON(), 'application/json');
  $('#inImport').onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    try { store.importJSON(await f.text()); $('#dlgSettings').close(); applyLanguage(); toast(t('imported')); } catch { toast('JSON ✕'); }
  };
  $('#btnReset').onclick = () => { if (confirm(t('confirmReset'))) { store.resetAll(); $('#dlgSettings').close(); applyLanguage(); } };

  // keyboard shortcuts
  document.addEventListener('keydown', e => {
    if (e.target.closest('input, textarea, select, [contenteditable]') || e.ctrlKey || e.metaKey || e.altKey) return;
    if (document.querySelector('dialog[open]')) return;
    const k = e.key.toLowerCase();
    const map = {
      ' ': togglePlay, a: prevLine, arrowleft: prevLine, d: nextLine, arrowright: nextLine, s: repeatLine,
      r: toggleRecord, p: playMine, c: compare, f: toggleFullscreen,
      t: () => flip('showTranslation', 't_trans'), l: () => flip('loopLine', 't_loop'), q: () => flip('autoPause', 't_autoPause'),
      h: () => { const lt = $('#lineText'); lt.classList.add('peek'); setTimeout(() => lt.classList.remove('peek'), 2500); },
      escape: closePopup,
    };
    if (map[k]) { e.preventDefault(); map[k](); }
  });
  addEventListener('resize', () => { if (lastRec) drawWave($('#wave'), lastRec.peaks); });
  drawWave($('#wave'), null);
}

init();
