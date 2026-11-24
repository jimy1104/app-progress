// EnglishPro overlay: mounted on top of a <video> in whatever page (or iframe) holds it.
// Two modes: "Shadowing" (pause per line, repeat, prev/next) and "Listen & type" (timed blanks game).
import { parseSubtitles, findActive, findLastStarted, tokenize, fmtTime, alignSecondary, words } from './subtitles.js';
import { t, tr, setContentLang, LANGS, posName } from './i18n.js';
import { Game, LEVELS } from './game.js';
import { lookup } from './dictionary.js';
import { translate } from './translate.js';
import { analyze, connectedSpeech, intonation, expandContraction, REDUCTIONS, phrasalAt } from './grammar.js';

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const STORE = 'englishpro';

// ------------------------------------------------------------------ persistent settings (chrome.storage)
const DEFAULTS = {
  active: 'p1',
  profiles: { p1: { name: 'Person 1', native: 'es' }, p2: { name: 'Person 2', native: 'ar' } },
  autoPause: true, autoResume: false, gapFactor: 1.3, loopLine: false, repeatCount: 3,
  showSubs: true, showTrans: true, blurTrans: false, gameTrans: false, level: 'basic',
  saved: {}, best: {}, recent: [],
};
let cfg = structuredClone(DEFAULTS);
async function loadCfg() {
  try { const r = await chrome.storage.local.get(STORE); cfg = Object.assign(structuredClone(DEFAULTS), r[STORE] || {}); } catch {}
}
let saveTimer = null;
function saveCfg() { clearTimeout(saveTimer); saveTimer = setTimeout(() => { try { chrome.storage.local.set({ [STORE]: cfg }); } catch {} }, 250); }
const prof = () => cfg.profiles[cfg.active] || cfg.profiles.p1;
const native = () => prof().native || 'es';
const savedOf = () => (cfg.saved[cfg.active] = cfg.saved[cfg.active] || {});

// ------------------------------------------------------------------ mount
export async function mount(initialVideo, findVideo, candidates = []) {
  await loadCfg();
  setContentLang(native());
  const ui = new Overlay(initialVideo, findVideo);
  await ui.init();
  for (const c of candidates) ui.addCandidate(c);
  ui.afterMount();
  return ui;
}

const HOST = location.hostname;
const IS_YT = /(^|\.)youtube(-nocookie)?\.com$/.test(HOST);
const IS_NETFLIX = /(^|\.)netflix\.com$/.test(HOST);
const EN_WORDS = new Set('the you i to a and it is that what of in me my we this don\'t i\'m your for on be have not are was no do he she just know can get go with all so they there it\'s here right like'.split(' '));
function englishScore(cues) {
  let n = 0, hit = 0;
  for (const c of cues.slice(0, 120)) for (const w of words(c.text)) { n++; if (EN_WORDS.has(w)) hit++; }
  return n ? hit / n : 0;
}

class Overlay {
  constructor(video, findVideo) {
    this.video = video; this.findVideo = findVideo;
    this.cues = []; this.trans = []; this.offset = 0; this.title = '';
    this.mode = 'shadow'; this.shown = -1; this.visible = true; this.tab = 'setup';
    this.eng = { target: null, loopCount: 0, pausedAtEnd: null, timer: null, guardUntil: 0, expect: 0, lastT: 0 };
    this.popup = { word: null, pinned: false, resume: false };
    this.cands = new Map(); this.secondary = null; this.autoLoaded = false;
  }

  async init() {
    this.host = document.createElement('div');
    this.host.id = 'englishpro-root';
    this.host.style.cssText = 'position:fixed;inset:0;z-index:2147483646;pointer-events:none;';
    this.root = this.host.attachShadow({ mode: 'open' });
    const css = await fetch(chrome.runtime.getURL('lib/ui.css')).then(r => r.text());
    this.root.innerHTML = `<style>${css}</style>
      <div class="bar" part="bar">
        <span class="logo">EP</span>
        <div class="seg"><button data-mode="shadow" class="on">🗣 Shadowing</button><button data-mode="game">🎧 Listen &amp; type</button></div>
        <span class="sep"></span>
        <button class="ic" data-act="prev" title="Previous line (A)">⏮</button>
        <button class="ic" data-act="repeat" title="Repeat line (S)">↺</button>
        <button class="ic" data-act="next" title="Next line (D)">⏭</button>
        <span class="sep"></span>
        <span class="optwrap"><button class="ic wide" data-act="opts" title="Options">⚙ Options</button><span class="toggles" hidden></span></span>
        <select class="speed" title="Speed">${[0.5, 0.65, 0.75, 0.85, 1, 1.1, 1.25].map(r => `<option value="${r}" ${r === 1 ? 'selected' : ''}>${r}×</option>`).join('')}</select>
        <span class="grow"></span>
        <button class="ic" data-act="panel" title="Lines · Grammar · Saved · Setup">☰</button>
        <button class="ic" data-act="close" title="Close (Alt+E)">✕</button>
      </div>
      <div class="caption">
        <div class="hud" hidden></div>
        <div class="line" dir="auto"></div>
        <div class="timer" hidden><div class="tbar"><i></i></div><span class="secs"></span></div>
        <div class="trans" dir="auto"></div>
      </div>
      <div class="center" hidden></div>
      <aside class="side" hidden>
        <nav class="tabs"><button data-tab="lines">Lines</button><button data-tab="grammar">Grammar</button><button data-tab="saved">Saved</button><button data-tab="setup">Setup</button></nav>
        <div class="tabbody"></div>
      </aside>
      <div class="popup" hidden></div>
      <div class="floats"></div>
      <div class="toast" hidden></div>`;
    this.$ = s => this.root.querySelector(s);
    this.attach();
    this.bind();
    this.renderToggles();
    this.game = this.makeGame();
    this.$('.side').hidden = true; this.tab = 'setup';
    this.renderCaption();
    this.loop = this.loop.bind(this);
    requestAnimationFrame(this.loop);
    document.addEventListener('fullscreenchange', () => this.attach());
    document.addEventListener('webkitfullscreenchange', () => this.attach());
    // Players sometimes replace their <video>: follow it.
    setInterval(() => { if (!this.video.isConnected) { const v = this.findVideo(); if (v) this.video = v; } }, 1000);
    this.nativeCaptionsStyle = document.createElement('style');
    this.nativeCaptionsStyle.textContent = '.ytp-caption-window-container,.caption-window,.player-timedtext,.player-timedtext-text-container{display:none!important}';
  }

  // ---------------------------------------------------------------- automatic subtitles
  afterMount() {
    if (this.cues.length) return;
    this.toast('🔎 Looking for subtitles…');
    if (IS_YT) window.postMessage({ __ep: 'yt-load', lang: 'en', native: native() }, '*');
    clearTimeout(this._noSubs);
    this._noSubs = setTimeout(() => {
      if (this.cues.length) return;
      this.toast('No English subtitles yet: turn ON English subtitles (CC) in the player once — EnglishPro grabs them automatically.', 9000);
      this.openPanel('setup');
    }, IS_YT ? 5000 : 3000);
  }
  onPageEvent(ev) {
    if (ev === 'nav') { // YouTube moved to another video
      if (this.game.running) this.game.stop();
      this.cues = []; this.trans = []; this.secondary = null; this.cands.clear(); this.title = ''; this.shown = -1; this.autoLoaded = false;
      this.renderCaption(true); this.renderCenter(); this.syncNativeCaptions();
      setTimeout(() => this.afterMount(), 1500);
    }
    if (ev === 'yt-none' && !this.cues.length) { this.toast('This YouTube video has no subtitles. Load an .srt in Setup.', 8000); this.openPanel('setup'); }
  }
  addCandidate(c) {
    if (this.cands.has(c.id) && this.cands.get(c.id).text === c.text) return;
    let cues = [];
    try { cues = parseSubtitles(c.text).cues; } catch {}
    if (cues.length < 2) return;
    const lang = (c.lang || '').slice(0, 2);
    const en = lang === 'en' || (!lang && (/english|\beng?\b/i.test(c.label || '') || englishScore(cues) > 0.14));
    const cand = { ...c, cues, isEnglish: en, lang2: lang || (en ? 'en' : '') };
    this.cands.set(c.id, cand);
    // English → main subtitles (first one wins; an updated/merged version of the loaded track replaces it).
    if (en && (!this.cues.length || (this.autoLoaded && this.currentCand === c.id))) {
      this.useCandidate(cand, true);
    } else if (!en && cand.lang2 && cand.lang2 === native() && this.cues.length) {
      this.useAsTranslation(cand);
    }
    if (this.tab === 'setup' && !this.$('.side').hidden) this.renderSetup();
  }
  useCandidate(cand, auto) {
    const lang = LANGS[cand.lang2] || (cand.isEnglish ? 'English' : 'Subtitles');
    const page = (document.title || '').replace(/\s+/g, ' ').trim().slice(0, 70);
    const name = (page ? page + ' — ' : '') + (cand.label || lang);
    this.currentCand = cand.id; this.autoLoaded = !!auto;
    this.loadSubs(cand.text, name, { auto });
    // A track in the learner's language becomes the translation line.
    for (const o of this.cands.values()) if (o !== cand && o.lang2 && o.lang2 === native()) { this.useAsTranslation(o); break; }
  }
  useAsTranslation(cand) {
    if (!this.cues.length) return;
    this.secondary = alignSecondary(this.cues, cand.cues);
    this.trans = this.secondary.slice();
    this.renderCaption(true);
  }
  syncNativeCaptions() {
    const hide = this.visible && this.cues.length > 0 && (IS_YT || IS_NETFLIX);
    if (hide && !this.nativeCaptionsStyle.isConnected) document.documentElement.appendChild(this.nativeCaptionsStyle);
    if (!hide && this.nativeCaptionsStyle.isConnected) this.nativeCaptionsStyle.remove();
  }

  attach() {
    const fs = document.fullscreenElement || document.webkitFullscreenElement;
    const parent = fs && fs.tagName !== 'VIDEO' ? fs : document.documentElement;
    if (this.host.parentNode !== parent) parent.appendChild(this.host);
  }

  toggle() {
    this.visible = !this.visible;
    this.host.style.display = this.visible ? '' : 'none';
    if (!this.visible && this.game.running) this.game.stop();
    this.syncNativeCaptions();
  }

  // ---------------------------------------------------------------- events
  bind() {
    const r = this.root;
    // Keep the page's player from reacting to keys typed in our UI (space, f, m, k…).
    for (const type of ['keydown', 'keyup', 'keypress']) this.host.addEventListener(type, e => e.stopPropagation());
    r.querySelectorAll('.seg button').forEach(b => b.onclick = () => this.setMode(b.dataset.mode));
    r.querySelectorAll('[data-act]').forEach(b => b.onclick = () => this.act(b.dataset.act));
    r.querySelectorAll('.tabs button').forEach(b => b.onclick = () => this.openPanel(b.dataset.tab));
    this.$('.tabbody').addEventListener('wheel', () => { this._scrolledAt = Date.now(); }, { passive: true });
    this.$('.speed').onchange = e => { this.video.playbackRate = Number(e.target.value); };

    const line = this.$('.line');
    line.addEventListener('mouseover', e => { const w = e.target.closest('.w'); if (!w || this.popup.pinned) return; clearTimeout(this.popup.hide); clearTimeout(this.popup.showT); this.popup.showT = setTimeout(() => this.openPopup(w, false), 180); });
    line.addEventListener('mouseout', e => { if (!e.target.closest('.w')) return; clearTimeout(this.popup.showT); if (!this.popup.pinned) this.popup.hide = setTimeout(() => { if (!this.$('.popup').matches(':hover')) this.closePopup(); }, 350); });
    line.addEventListener('click', e => { const w = e.target.closest('.w'); if (w) { e.stopPropagation(); this.openPopup(w, true); } });
    const pop = this.$('.popup');
    pop.addEventListener('mouseenter', () => clearTimeout(this.popup.hide));
    pop.addEventListener('mouseleave', () => { if (!this.popup.pinned) this.popup.hide = setTimeout(() => this.closePopup(), 300); });

    // Game inputs
    line.addEventListener('input', e => {
      const el = e.target.closest('.blank-in'); if (!el) return;
      const res = this.game.type(Number(el.dataset.i), Number(el.dataset.b), el.value);
      el.classList.toggle('wrong', res === 'wrong'); el.classList.toggle('prefix', res === 'prefix');
      if (res === 'wrong') { el.classList.remove('shake'); void el.offsetWidth; el.classList.add('shake'); }
    });
    line.addEventListener('keydown', e => {
      const el = e.target.closest('.blank-in'); if (!el) return;
      if (e.key === 'Enter') { e.preventDefault(); this.gameAction('replay'); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); this.gameAction('hint'); }
      else if (e.key === 'Escape') { e.preventDefault(); this.gameAction('skip'); }
      else if (e.key === ' ' && el.value.trim()) {
        const all = [...line.querySelectorAll('.blank-in')]; const k = all.indexOf(el);
        if (all[k + 1]) { e.preventDefault(); all[k + 1].focus(); }
      }
    });

    // Shortcuts (only when not typing). Capture phase so the player doesn't eat them.
    window.addEventListener('keydown', e => {
      if (!this.visible || e.ctrlKey || e.metaKey || e.altKey) return;
      const path = e.composedPath(); const tgt = path[0];
      if (tgt && (tgt.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(tgt.tagName))) return;
      const k = e.key.toLowerCase();
      const map = { a: 'prev', d: 'next', s: 'repeat', q: 'autopause' };
      if (map[k] && this.cues.length) { e.preventDefault(); e.stopImmediatePropagation(); this.act(map[k]); }
    }, true);
    document.addEventListener('click', e => { if (!this.$('.popup').hidden && !e.composedPath().includes(this.host)) this.closePopup(); });
  }

  act(a) {
    if (a === 'close') return this.toggle();
    if (a === 'opts') { const tg = this.$('.toggles'); tg.hidden = !tg.hidden; return; }
    if (a === 'panel') { const s = this.$('.side'); s.hidden = !s.hidden; if (!s.hidden) this.openPanel(this.tab); return; }
    if (a === 'autopause') { cfg.autoPause = !cfg.autoPause; saveCfg(); this.renderToggles(); this.toast(`Pause after each line: ${cfg.autoPause ? 'ON' : 'OFF'}`); return; }
    if (!this.cues.length) { this.openPanel('setup'); this.toast('Load subtitles first.'); return; }
    if (this.game.running) { if (a === 'repeat') this.gameAction('replay'); return; }
    const cur = this.current();
    if (a === 'prev') this.goto(cur - 1);
    if (a === 'next') this.goto(cur + 1);
    if (a === 'repeat') this.goto(cur);
  }

  renderToggles() {
    const defs = [
      ['autoPause', '⏸ Pause each line'], ['loopLine', '🔁 Loop'], ['autoResume', '▶ Auto-continue'],
      ['showSubs', 'CC Subtitles'], ['showTrans', '🌐 Translation'], ['blurTrans', '◌ Blur translation'],
    ];
    const host = this.$('.toggles');
    host.innerHTML = defs.map(([k, l]) => `<button class="chip${cfg[k] ? ' on' : ''}" data-k="${k}">${l}</button>`).join('');
    host.querySelectorAll('.chip').forEach(b => b.onclick = () => { cfg[b.dataset.k] = !cfg[b.dataset.k]; saveCfg(); this.renderToggles(); this.renderCaption(true); });
    this.$('.optwrap').hidden = this.mode === 'game';
    this.root.querySelectorAll('[data-act=prev],[data-act=next]').forEach(b => { b.hidden = this.mode === 'game'; });
  }

  setMode(m) {
    if (m === this.mode) return;
    this.mode = m;
    this.root.querySelectorAll('.seg button').forEach(b => b.classList.toggle('on', b.dataset.mode === m));
    if (this.game.running) this.game.stop();
    clearTimeout(this.eng.timer);
    this.video.pause();
    this.renderToggles();
    this.renderCenter();
    this.renderCaption(true);
  }

  // ---------------------------------------------------------------- subtitles
  loadSubs(text, name, { auto = false } = {}) {
    const { cues } = parseSubtitles(text);
    if (!cues.length) { this.toast('No subtitle lines found in that file.'); return; }
    if (!auto) { this.currentCand = null; this.autoLoaded = false; }
    clearTimeout(this._noSubs);
    this.cues = cues; this.trans = new Array(cues.length).fill(''); this.secondary = null; this.title = name || 'Subtitles'; this.shown = -1;
    Object.assign(this.eng, { target: null, loopCount: 0, pausedAtEnd: null });
    const recent = (cfg.recent || []).filter(r => r.name !== this.title);
    if (text.length < 300000) recent.unshift({ name: this.title, text, offset: 0, at: Date.now() });
    cfg.recent = recent.slice(0, 6);
    const prev = (cfg.recent.find(r => r.name === this.title) || {});
    this.offset = prev.offset || 0;
    saveCfg();
    this.toast(auto ? `✅ Subtitles found automatically: ${this.title} (${cues.length} lines)` : `${cues.length} lines loaded. If they are early/late, use Sync in Setup.`);
    this.syncNativeCaptions();
    this.$('.side').hidden = true; // keep the movie visible; ☰ opens the list
    this.renderCenter();
    this.renderCaption(true);
  }
  setOffset(v) {
    this.offset = Math.round(v * 100) / 100;
    const r = (cfg.recent || []).find(x => x.name === this.title); if (r) { r.offset = this.offset; saveCfg(); }
    if (this.tab === 'setup') this.renderSetup();
    this.eng.target = null; this.renderCaption(true);
  }
  readPlayerTracks() {
    const out = [];
    for (const tt of this.video.textTracks || []) {
      try {
        if (tt.mode === 'disabled') tt.mode = 'hidden';
        const cs = tt.cues ? [...tt.cues] : [];
        if (cs.length) out.push({ label: tt.label || tt.language || 'track', cues: cs.map(c => ({ start: c.startTime, end: c.endTime, text: (c.text || '').replace(/<[^>]+>/g, '').replace(/\n/g, ' ') })) });
      } catch {}
    }
    return out;
  }

  // ---------------------------------------------------------------- engine
  subT() { return this.video.currentTime - this.offset; }
  current() { return this.eng.target != null ? this.eng.target : Math.max(0, this.shown); }
  seekToLine(i, play) {
    const c = this.cues[i]; if (!c) return;
    const e = this.eng;
    e.target = i; e.pausedAtEnd = null;
    const vt = Math.max(0, c.start + this.offset - 0.05);
    if (IS_NETFLIX) window.postMessage({ __ep: 'seek', t: vt }, '*'); // Netflix breaks if currentTime is set directly
    else this.video.currentTime = vt;
    e.expect = e.lastT = vt - this.offset; e.guardUntil = performance.now() + 1500;
    if (play) this.video.play().catch(() => {});
    this.showLine(i);
  }
  goto(i) {
    if (!this.cues.length) return;
    i = Math.max(0, Math.min(this.cues.length - 1, i));
    clearTimeout(this.eng.timer); this.eng.loopCount = 0;
    this.seekToLine(i, true);
  }

  loop() {
    requestAnimationFrame(this.loop);
    if (!this.visible || !this.cues.length) { this.place(); return; }
    const v = this.video; const e = this.eng;
    const tt = this.subT(); const playing = !v.paused && !v.ended;
    if (e.guardUntil) { if (Math.abs(tt - e.expect) < 0.6 || performance.now() > e.guardUntil) e.guardUntil = 0; else { this.place(); return; } }
    if (Math.abs(tt - e.lastT) > 1.5) { e.target = null; e.loopCount = 0; e.pausedAtEnd = null; }
    e.lastT = tt;
    const active = findActive(this.cues, tt);
    if (playing) {
      e.pausedAtEnd = null;
      if (e.target == null && active >= 0) e.target = active;
      if (e.target != null) {
        const c = this.cues[e.target];
        if (c && tt >= c.end - 0.03) this.onLineEnd(e.target);
        else if (active > e.target) { e.target = active; e.loopCount = 0; }
      }
    }
    const display = e.target != null ? e.target : (active >= 0 ? active : Math.max(0, findLastStarted(this.cues, tt)));
    if (display !== this.shown) this.showLine(display);
    this.place();
  }

  onLineEnd(i) {
    const v = this.video; const e = this.eng;
    if (this.mode === 'game') {
      if (!this.game.running) { e.target = null; return; }
      if (this.game.onLineEnd(i) === 'pause') { v.pause(); e.pausedAtEnd = i; } else { e.target = null; e.loopCount = 0; }
      return;
    }
    const c = this.cues[i]; const dur = (c.end - c.start) / (v.playbackRate || 1);
    const gap = dur * cfg.gapFactor * 1000 + 300;
    if (cfg.loopLine) {
      e.loopCount++;
      if (cfg.repeatCount === 0 || e.loopCount < cfg.repeatCount) {
        if (cfg.autoResume) { v.pause(); e.pausedAtEnd = i; e.timer = setTimeout(() => this.seekToLine(i, true), gap); }
        else this.seekToLine(i, true);
        return;
      }
      e.loopCount = 0;
    }
    if (cfg.autoPause) {
      v.pause(); e.pausedAtEnd = i;
      if (cfg.autoResume) e.timer = setTimeout(() => { if (this.cues[i + 1]) this.seekToLine(i + 1, true); }, gap);
      return;
    }
    e.target = null; e.loopCount = 0;
  }

  // Place the caption/center over the video, wherever it is on the page.
  place() {
    const vr = this.video.getBoundingClientRect();
    const cap = this.$('.caption'); const center = this.$('.center'); const side = this.$('.side');
    // When the side panel is open, use only the part of the video it doesn't cover.
    let right = vr.right;
    if (!side.hidden) { const sr = side.getBoundingClientRect(); if (sr.left < vr.right) right = Math.max(vr.left + 260, sr.left - 8); }
    const r = { left: vr.left, top: vr.top, bottom: vr.bottom, width: right - vr.left, height: vr.height };
    const w = Math.max(260, Math.min(r.width * 0.94, 1100));
    cap.style.width = w + 'px';
    cap.style.left = (r.left + r.width / 2 - w / 2) + 'px';
    const bar = this.$('.bar').getBoundingClientRect();
    side.style.top = Math.round(bar.bottom + 8) + 'px';
    const bottom = Math.max(8, innerHeight - r.bottom + Math.max(48, r.height * 0.11));
    cap.style.bottom = bottom + 'px';
    center.style.left = (r.left + r.width / 2) + 'px';
    center.style.top = (r.top + r.height * 0.42) + 'px';
    center.style.maxHeight = Math.max(200, r.height * 0.8) + 'px';
    const fl = this.$('.floats'); fl.style.left = (r.left + r.width / 2) + 'px'; fl.style.top = (r.top + r.height * 0.35) + 'px';
  }

  // ---------------------------------------------------------------- caption
  async ensureTrans(i) {
    if (this.secondary && this.secondary[i]) return (this.trans[i] = this.secondary[i]);
    if (!this.cues[i] || this.trans[i] || native() === 'en') return this.trans[i] || '';
    try { this.trans[i] = await translate(this.cues[i].text, 'en', native()); } catch {}
    return this.trans[i];
  }
  showLine(i) { this.shown = i; this.renderCaption(); this.highlightList(); if (this.tab === 'grammar' && !this.$('.side').hidden) this.renderGrammar(); if (this.mode === 'game') this.game.onLineShown(i); }

  renderCaption(force) {
    const i = this.shown; const c = this.cues[i];
    const line = this.$('.line'); const tr_ = this.$('.trans');
    if (!c) { line.innerHTML = ''; tr_.textContent = ''; return; }
    if (this.mode === 'game') {
      this.renderGameLine(i);
      tr_.hidden = !(cfg.gameTrans && this.game.running);
      if (!tr_.hidden) this.ensureTrans(i).then(x => { if (this.shown === i) tr_.textContent = x; });
      this.renderHud();
      return;
    }
    const saved = savedOf();
    line.hidden = !cfg.showSubs;
    line.innerHTML = tokenize(c.text).map(k => k.w ? `<span class="w${saved[k.t.toLowerCase()] ? ' saved' : ''}" data-s="${k.s}">${esc(k.t)}</span>` : esc(k.t)).join('');
    tr_.hidden = !cfg.showTrans; tr_.classList.toggle('blur', !!cfg.blurTrans);
    tr_.textContent = this.trans[i] || '';
    if (cfg.showTrans) this.ensureTrans(i).then(x => { if (this.shown === i) tr_.textContent = x; });
    if (cfg.showTrans) for (let k = 1; k <= 2; k++) this.ensureTrans(i + k);
  }

  // ---------------------------------------------------------------- word popup
  openPopup(el, pinned) {
    const word = el.textContent; const i = this.shown; const text = this.cues[i] ? this.cues[i].text : '';
    const offset = Number(el.dataset.s);
    this.popup.word = word; this.popup.pinned = pinned;
    if (!this.video.paused) { this.video.pause(); this.popup.resume = true; clearTimeout(this.eng.timer); }
    const pop = this.$('.popup');
    this.renderPopup({ word, loading: true }, text, offset, i);
    pop.hidden = false; this.posPopup(el);
    lookup(word, { target: 'en', native: native() }).then(res => { if (this.popup.word !== word) return; this.renderPopup(res, text, offset, i); this.posPopup(el); })
      .catch(() => { if (this.popup.word === word) this.renderPopup({ word, error: true }, text, offset, i); });
  }
  posPopup(el) {
    const pop = this.$('.popup'); const r = el.getBoundingClientRect(); const pr = pop.getBoundingClientRect();
    const left = Math.min(Math.max(8, r.left + r.width / 2 - pr.width / 2), innerWidth - pr.width - 8);
    let top = r.top - pr.height - 10; if (top < 8) top = Math.min(r.bottom + 10, innerHeight - pr.height - 8);
    pop.style.left = left + 'px'; pop.style.top = Math.max(8, top) + 'px';
  }
  closePopup() {
    this.$('.popup').hidden = true; this.popup.word = null; this.popup.pinned = false;
    if (this.popup.resume) { this.popup.resume = false; if (!(this.game.running && this.game.waiting)) this.video.play().catch(() => {}); }
  }
  renderPopup(res, text, offset, i) {
    const w = res.word; const lw = w.toLowerCase().replace(/’/g, "'");
    const isSaved = !!savedOf()[lw];
    let h = `<div class="ph"><b class="pw">${esc(w)}</b>${res.lemma && res.lemma.toLowerCase() !== lw ? `<span class="mut">→ ${esc(res.lemma)}</span>` : ''}${res.phonetic ? `<span class="mut">${esc(res.phonetic)}</span>` : ''}</div>`;
    if (/'/.test(lw) || REDUCTIONS[lw]) h += `<div class="phr">= <b>${esc(REDUCTIONS[lw] || expandContraction(lw))}</b></div>`;
    const ph = phrasalAt(text).find(p => offset >= p.s && offset < p.e);
    if (ph) h += `<div class="phr">Part of <b>${esc(ph.name)}</b> — <span dir="auto">${esc(tr({ es: ph.es, ar: ph.ar, en: ph.name }))}</span></div>`;
    if (res.loading) h += `<div class="mut">Loading…</div>`;
    else if (res.error) h += `<div class="mut">Could not translate (offline?).</div>`;
    else {
      const main = res.translation && res.translation.main;
      if (main) h += `<div class="pmain" dir="auto">${esc(main)}</div>`;
      const alts = (res.translation && res.translation.alts) || [];
      if (alts.length) h += `<div class="palts" dir="auto">${alts.slice(0, 3).map(a => `<div><span class="mut">${esc(posName(a.pos))}:</span> ${esc(a.terms.join(', '))}</div>`).join('')}</div>`;
      if (res.meanings && res.meanings.length) h += `<h5>Definition</h5>${res.meanings.slice(0, 2).map(m => `<div><i class="mut">${esc(m.pos)}</i> ${esc(m.defs[0].def)}</div>`).join('')}${res.defTr ? `<div class="mut" dir="auto">${esc(res.defTr)}</div>` : ''}`;
      if (res.examples && res.examples.length) h += `<h5>Examples</h5>${res.examples.map(e => `<div class="ex">“${esc(e.en)}”<span dir="auto">${esc(e.tr)}</span></div>`).join('')}`;
      h += `<h5>In the movie</h5><div class="ex">“${esc(text)}”<span dir="auto">${esc(this.trans[i] || '')}</span></div>`;
    }
    h += `<div class="pact"><button data-p="say">🔊 Listen</button><button data-p="save" class="${isSaved ? '' : 'pri'}">${isSaved ? '★ Saved' : '☆ Save'}</button><span class="grow"></span><button data-p="x">✕</button></div>`;
    const pop = this.$('.popup'); pop.innerHTML = h;
    pop.querySelector('[data-p=say]').onclick = () => { if (res.audio) new Audio(res.audio).play().catch(() => this.speak(w)); else this.speak(w); };
    pop.querySelector('[data-p=x]').onclick = () => this.closePopup();
    pop.querySelector('[data-p=save]').onclick = () => {
      const s = savedOf();
      if (s[lw]) delete s[lw];
      else s[lw] = { word: w, meaning: (res.translation && res.translation.main) || '', ipa: res.phonetic || '', example: res.examples && res.examples[0] ? res.examples[0].en : '', context: text, title: this.title, at: Date.now() };
      saveCfg(); this.renderPopup(res, text, offset, i); this.renderCaption(true); if (this.tab === 'saved') this.renderSaved();
    };
  }
  speak(text, rate = 0.85) {
    try {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text); u.lang = 'en-US'; u.rate = rate;
      const v = speechSynthesis.getVoices().find(x => x.lang === 'en-US'); if (v) u.voice = v;
      speechSynthesis.speak(u);
    } catch {}
  }

  // ---------------------------------------------------------------- side panel
  openPanel(tab) {
    this.tab = tab;
    this.$('.side').hidden = false;
    this.root.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
    if (tab === 'lines') this.renderLines();
    if (tab === 'grammar') this.renderGrammar();
    if (tab === 'saved') this.renderSaved();
    if (tab === 'setup') this.renderSetup();
  }
  body() { return this.$('.tabbody'); }

  renderLines() {
    const b = this.body();
    if (!this.cues.length) { b.innerHTML = '<p class="mut">No subtitles yet — open Setup.</p>'; return; }
    b.innerHTML = `<ol class="lines${this.game.running ? ' blurred' : ''}">${this.cues.map((c, i) => `<li data-i="${i}"><span class="tm">${fmtTime(c.start + this.offset)}</span>${esc(c.text)}</li>`).join('')}</ol>`;
    b.querySelector('.lines').onclick = e => { const li = e.target.closest('li'); if (!li || this.game.running) return; this.goto(Number(li.dataset.i)); };
    this.highlightList(true);
  }
  highlightList(force) {
    if (this.tab !== 'lines' || this.$('.side').hidden) return;
    const ol = this.body().querySelector('.lines'); if (!ol) return;
    ol.querySelectorAll('.cur').forEach(x => x.classList.remove('cur'));
    const li = ol.querySelector(`li[data-i="${this.shown}"]`); if (!li) return;
    li.classList.add('cur');
    if (force || !this._scrolledAt || Date.now() - this._scrolledAt > 3000) ol.parentElement.scrollTop = li.offsetTop - ol.parentElement.clientHeight / 3;
  }

  renderGrammar() {
    const b = this.body(); const c = this.cues[this.shown];
    if (!c) { b.innerHTML = '<p class="mut">Load subtitles to see the grammar of each line.</p>'; return; }
    if (this.game.running) { b.innerHTML = '<p class="mut">Hidden during the game (it would give the answers away).</p>'; return; }
    const text = c.text;
    const found = analyze(text);
    const into = intonation(text);
    let h = `<div class="gsent">${esc(text)}</div><div class="gitem">Intonation <b>${into.arrow}</b> <span dir="auto">${esc(tr(into.text))}</span></div>`;
    if (!found.length) h += '<p class="mut">No special structures detected in this line.</p>';
    for (const { rule, matches } of found) {
      const groups = new Map();
      for (const m of matches) { const k = m.detail ?? '_'; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(m); }
      for (const [detail, ms] of groups) {
        const d = rule.details && rule.details[detail];
        let frag = ms.map(m => `«${esc(text.slice(m.s, m.e).trim())}»`).join(', ');
        if (rule.id === 'phrasal') frag = ms.map(m => `<b>${esc(m.detail)}</b> — <span dir="auto">${esc(tr(m.meaning))}</span>`).join('<br>');
        if (rule.id === 'contractions') frag = ms.map(m => `<b>${esc(text.slice(m.s, m.e))}</b> = ${esc(expandContraction(text.slice(m.s, m.e)))}`).join(' · ');
        if (rule.id === 'reductions') frag = ms.map(m => `<b>${esc(text.slice(m.s, m.e))}</b> = ${esc(REDUCTIONS[text.slice(m.s, m.e).toLowerCase()] || '')}`).join(' · ');
        const ex = (d && d.examples) || rule.examples || [];
        h += `<div class="gcard lvl-${rule.level}"><h4>${esc(tr(d && d.name ? d.name : rule.name))} <span class="lvl">${rule.level}</span></h4>
          <div class="gfound">${frag}</div><code>${esc((d && d.structure) || rule.structure)}</code>
          <p dir="auto">${esc(tr(d && d.explain ? d.explain : rule.explain))}</p>
          ${ex.length ? `<ul>${ex.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
          ${rule.tip ? `<p class="tip" dir="auto">💡 ${esc(tr(rule.tip))}</p>` : ''}</div>`;
      }
    }
    const sp = connectedSpeech(text);
    if (sp.length) h += `<h5>Connected speech</h5>` + sp.map(it => `<div class="gitem">${it.from ? `${esc(it.from)} → <b>${esc(it.to)}</b>` : it.list.map(x => `<b>${esc(x)}</b>`).join(' · ')} <span class="mut" dir="auto">${esc(tr(it.label))}</span></div>`).join('');
    b.innerHTML = h;
  }

  renderSaved() {
    const b = this.body(); const items = Object.values(savedOf()).sort((x, y) => y.at - x.at);
    if (!items.length) { b.innerHTML = '<p class="mut">Hover a word in the subtitles and press ☆ Save.</p>'; return; }
    b.innerHTML = `<button class="btn" data-x="csv">Export CSV (Anki)</button>` + items.map(it => `<div class="sitem"><b>${esc(it.word)}</b> <span class="mut">${esc(it.ipa || '')}</span><div dir="auto">${esc(it.meaning)}</div><div class="mut small">🎬 ${esc(it.context || '')}</div></div>`).join('');
    b.querySelector('[data-x=csv]').onclick = () => {
      const rows = [['word', 'meaning', 'ipa', 'example', 'context']].concat(items.map(i => [i.word, i.meaning, i.ipa, i.example, i.context]));
      const csv = '﻿' + rows.map(r => r.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
      const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' })); a.download = 'englishpro-words.csv'; a.click();
    };
  }

  renderSetup() {
    const b = this.body();
    const tracks = this.readPlayerTracks();
    const langOpts = sel => Object.entries(LANGS).map(([k, v]) => `<option value="${k}" ${k === sel ? 'selected' : ''}>${v}</option>`).join('');
    b.innerHTML = `
      <h5>1 · Subtitles found on this page</h5>
      ${this.cands.size ? [...this.cands.values()].map(c => `<div class="cand${c.id === this.currentCand ? ' on' : ''}"><div><b>${esc(c.label || LANGS[c.lang2] || 'Subtitles')}</b> <span class="mut small">${esc(c.source || '')}</span> <span class="mut small">${esc(c.lang2 || '?')} · ${c.cues.length} lines${c.isEnglish ? ' · English' : ''}</span></div>
        <div class="row"><button class="btn${c.isEnglish ? ' pri' : ''}" data-cand="${esc(c.id)}">Use</button>${this.cues.length ? `<button class="btn" data-candtr="${esc(c.id)}">Use as translation</button>` : ''}</div></div>`).join('')
        : `<p class="mut small">${IS_YT ? 'Asking YouTube for its captions…' : 'None yet. Turn ON English subtitles (CC) in the video player once and they appear here automatically.'}</p>`}
      <h5>…or your own file</h5>
      <label class="drop"><input type="file" accept=".srt,.vtt,.ass,.ssa,.sbv,.txt,.json" hidden><b>Choose .srt / .vtt file</b><span class="mut">or drop it here</span></label>
      ${tracks.length ? `<div class="row">${tracks.map((tk, k) => `<button class="btn" data-track="${k}">Use player track: ${esc(tk.label)}</button>`).join('')}</div>` : ''}
      <details><summary class="mut">…or paste the subtitle text</summary><textarea rows="4" class="paste"></textarea><button class="btn" data-x="paste">Load pasted text</button></details>
      ${(cfg.recent || []).length ? `<h5>Recent</h5>${cfg.recent.map((r, k) => `<button class="btn rec" data-recent="${k}">${esc(r.name)}</button>`).join('')}` : ''}
      <h5>2 · Sync ${this.title ? `<span class="mut">(${esc(this.title)})</span>` : ''}</h5>
      <div class="row"><button class="btn" data-off="-1">−1s</button><button class="btn" data-off="-0.1">−0.1</button><b class="offv">${this.offset >= 0 ? '+' : ''}${this.offset.toFixed(2)}s</b><button class="btn" data-off="0.1">+0.1</button><button class="btn" data-off="1">+1s</button></div>
      <p class="mut small">Easiest: play until you hear a line, pause, pick that line below and press “It starts now”.</p>
      <div class="row"><select class="syncline">${this.cues.slice(0, 400).map((c, i) => `<option value="${i}" ${i === this.current() ? 'selected' : ''}>${i + 1}. ${esc(c.text.slice(0, 48))}</option>`).join('')}</select><button class="btn pri" data-x="syncnow">It starts now</button></div>
      <h5>3 · Who is studying?</h5>
      <div class="row">${Object.entries(cfg.profiles).map(([id, p]) => `<button class="btn${cfg.active === id ? ' pri' : ''}" data-prof="${id}">${esc(p.name)}</button>`).join('')}</div>
      <div class="row"><input class="pname" value="${esc(prof().name)}" placeholder="Name"><select class="pnative">${langOpts(native())}</select></div>
      <p class="mut small">Native language is only used for meanings and translations. Shortcuts: A previous · S repeat · D next · Q pause-each-line · Alt+E show/hide.</p>`;
    b.querySelectorAll('[data-cand]').forEach(btn => btn.onclick = () => { const c = this.cands.get(btn.dataset.cand); if (c) this.useCandidate(c, false); });
    b.querySelectorAll('[data-candtr]').forEach(btn => btn.onclick = () => { const c = this.cands.get(btn.dataset.candtr); if (c) { this.useAsTranslation(c); this.toast('Translation line: ' + (c.label || c.lang2)); } });
    const file = b.querySelector('input[type=file]');
    file.onchange = async () => { const f = file.files[0]; if (f) this.loadSubs(await f.text(), f.name.replace(/\.[^.]+$/, '')); };
    const drop = b.querySelector('.drop');
    drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
    drop.ondragleave = () => drop.classList.remove('over');
    drop.ondrop = async e => { e.preventDefault(); drop.classList.remove('over'); const f = e.dataTransfer.files[0]; if (f) this.loadSubs(await f.text(), f.name.replace(/\.[^.]+$/, '')); };
    b.querySelectorAll('[data-track]').forEach(btn => btn.onclick = () => {
      const tk = tracks[Number(btn.dataset.track)];
      const srt = tk.cues.map((c, i) => `${i + 1}\n${toTs(c.start)} --> ${toTs(c.end)}\n${c.text}\n`).join('\n');
      this.loadSubs(srt, tk.label);
    });
    b.querySelector('[data-x=paste]').onclick = () => { const v = b.querySelector('.paste').value.trim(); if (v) this.loadSubs(v, 'Pasted subtitles'); };
    b.querySelectorAll('[data-recent]').forEach(btn => btn.onclick = () => { const r = cfg.recent[Number(btn.dataset.recent)]; this.loadSubs(r.text, r.name); });
    b.querySelectorAll('[data-off]').forEach(btn => btn.onclick = () => this.setOffset(this.offset + Number(btn.dataset.off)));
    b.querySelector('[data-x=syncnow]').onclick = () => {
      const i = Number(b.querySelector('.syncline').value); const c = this.cues[i]; if (!c) return;
      this.setOffset(this.video.currentTime - c.start); this.toast(`Synced: line ${i + 1} starts now.`);
    };
    b.querySelectorAll('[data-prof]').forEach(btn => btn.onclick = () => { cfg.active = btn.dataset.prof; saveCfg(); setContentLang(native()); this.trans = new Array(this.cues.length).fill(''); this.renderSetup(); this.renderCaption(true); });
    b.querySelector('.pname').onchange = e => { prof().name = e.target.value.trim() || prof().name; saveCfg(); this.renderSetup(); };
    b.querySelector('.pnative').onchange = e => { prof().native = e.target.value; saveCfg(); setContentLang(native()); this.trans = new Array(this.cues.length).fill(''); this.secondary = null; this.renderCaption(true); if (IS_YT && this.cues.length) window.postMessage({ __ep: 'yt-load', lang: 'en', native: native() }, '*'); };
  }

  // ---------------------------------------------------------------- Listen & type game
  makeGame() {
    return new Game({
      cues: () => this.cues,
      seekToLine: (i, play) => { clearTimeout(this.eng.timer); this.seekToLine(i, play); },
      pause: () => this.video.pause(),
      play: () => this.video.play().catch(() => {}),
      t,
      renderLine: i => { if (this.shown === i) { this.renderGameLine(i); this.renderHud(); } else this.showLine(i); },
      renderTimer: (frac, left) => {
        const tm = this.$('.timer'); tm.hidden = false;
        const bar = tm.querySelector('i'); bar.style.width = (frac * 100).toFixed(1) + '%';
        bar.style.background = frac > 0.5 ? '#34d399' : frac > 0.25 ? '#fbbf24' : '#fb7185';
        tm.querySelector('.secs').textContent = left.toFixed(1) + 's';
        tm.classList.toggle('urgent', frac <= 0.25);
      },
      focusBlank: (i, bi) => { if (this.shown !== i || bi < 0) return; const el = this.root.querySelector(`.blank-in[data-b="${bi}"]`); if (el) el.focus({ preventScroll: true }); },
      flash: (msg, kind) => this.float(msg, 'flash ' + (kind || 'good')),
      floatPoints: txt => this.float(txt, 'pts'),
      onChange: () => { this.renderHud(); if (!this.game.running) this.renderCenter(); const ol = this.root.querySelector('.lines'); if (ol) ol.classList.toggle('blurred', this.game.running); },
      onFinish: r => this.showResults(r),
    });
  }

  renderCenter() {
    const c = this.$('.center');
    if (this.mode !== 'game' || this.game.running) { c.hidden = true; return; }
    c.hidden = false;
    if (!this.cues.length) { c.innerHTML = `<div class="card"><h2 class="grad">🎧 Listen &amp; type</h2><p>Load the movie's English subtitles first (☰ → Setup).</p><button class="btn pri" data-c="setup">Open Setup</button></div>`; c.querySelector('[data-c=setup]').onclick = () => this.openPanel('setup'); return; }
    const best = cfg.best[this.title] || {};
    c.innerHTML = `<div class="card"><h2 class="grad">🎧 Listen &amp; type</h2>
      <p class="mut">Words disappear from the subtitles. Type them while you listen. If the line ends with gaps, the movie pauses and the clock runs — be quick!</p>
      <div class="levels">${Object.entries(LEVELS).map(([k, L]) => `<button class="lv lv-${k}${cfg.level === k ? ' sel' : ''}" data-lv="${k}"><span class="e">${L.emoji}</span><b>${t('lvl_' + k)}</b><small>${t('lvlDesc_' + k)}</small>${best[k] ? `<span class="best">🏆 ${best[k]}</span>` : ''}</button>`).join('')}</div>
      <div class="row center-row"><button class="btn pri big" data-c="here">▶ Start from line ${this.current() + 1}</button><button class="btn big" data-c="begin">From the beginning</button></div>
      <p class="mut small">Enter = replay line · ↓ = hint · Esc = skip</p></div>`;
    c.querySelectorAll('[data-lv]').forEach(b => b.onclick = () => { cfg.level = b.dataset.lv; saveCfg(); this.renderCenter(); });
    c.querySelector('[data-c=here]').onclick = () => this.startGame(this.current());
    c.querySelector('[data-c=begin]').onclick = () => this.startGame(0);
  }
  startGame(from) {
    this.closePopup();
    this.$('.center').hidden = true;
    this.game.start(cfg.level, from);
    this.renderCaption(true);
  }
  gameAction(a) {
    const i = this.shown;
    if (a === 'replay') { if (this.game.waiting) this.game.replay(); else this.seekToLine(i, true); }
    if (a === 'hint') this.game.hint(i);
    if (a === 'skip') {
      if (this.game.waiting) this.game.timeUp(true);
      else { const ln = this.game.line(i); ln.blanks.forEach(b => { if (!b.done && !b.revealed) { b.revealed = true; this.game.missedWords.push(b.word); } }); this.game.combo = 0; this.renderGameLine(i); this.renderHud(); }
    }
    if (a === 'trans') { cfg.gameTrans = !cfg.gameTrans; saveCfg(); this.renderCaption(true); }
    if (a === 'quit') this.game.finish(true);
  }
  renderGameLine(i) {
    const line = this.$('.line'); line.hidden = false;
    if (!this.game.running) { line.innerHTML = ''; return; }
    const { toks, blanks } = this.game.line(i);
    const byTok = new Map(blanks.map((b, bi) => [b.tokIdx, bi]));
    const act = this.root.activeElement;
    const focused = act && act.classList && act.classList.contains('blank-in') ? Number(act.dataset.b) : -1;
    line.innerHTML = toks.map((k, ti) => {
      if (!byTok.has(ti)) return k.w ? `<span class="w" data-s="${k.s}">${esc(k.t)}</span>` : esc(k.t);
      const bi = byTok.get(ti); const b = blanks[bi];
      if (b.done) return `<span class="w ok" data-s="${k.s}">${esc(b.word)}</span>`;
      if (b.revealed) return `<span class="w miss" data-s="${k.s}">${esc(b.word)}</span>`;
      return `<input class="blank-in" data-b="${bi}" data-i="${i}" value="${esc(b.typed)}" style="width:calc(${Math.max(3, [...b.word].length)}ch + 18px)" autocomplete="off" autocapitalize="off" spellcheck="false">`;
    }).join('');
    const next = blanks.findIndex(b => !b.done && !b.revealed);
    const want = focused >= 0 && blanks[focused] && !blanks[focused].done ? focused : next;
    if (want >= 0) { const el = line.querySelector(`.blank-in[data-b="${want}"]`); if (el) { el.focus({ preventScroll: true }); el.setSelectionRange(el.value.length, el.value.length); } }
    else if (focused >= 0) { line.tabIndex = -1; line.focus({ preventScroll: true }); } // keep stray keys away from the page's player
  }
  renderHud() {
    const hud = this.$('.hud'); const g = this.game;
    hud.hidden = !(this.mode === 'game' && g.running);
    this.$('.timer').hidden = hud.hidden || !g.timer;
    if (hud.hidden) return;
    const L = LEVELS[g.level];
    const mult = Math.min(3, 1 + Math.floor(g.combo / 5) * 0.5);
    hud.innerHTML = `<span class="pill lv-${g.level}">${L.emoji} ${t('lvl_' + g.level)}</span><span class="score">${g.score}</span>
      <span class="pill${g.combo >= 5 ? ' hot' : ''}">🔥 ${g.combo}${mult > 1 ? ` ×${mult}` : ''}</span><span>${'❤️'.repeat(Math.max(0, g.lives))}${'🖤'.repeat(Math.max(0, L.lives - g.lives))}</span>
      <span class="state">${g.waiting ? '⏱ Type now!' : '🎧 Listen…'}</span>
      <span class="gbtns"><button data-g="replay" title="Enter">↺</button><button data-g="hint" title="↓">💡</button><button data-g="skip" title="Esc">⏭</button><button data-g="trans" class="${cfg.gameTrans ? 'on' : ''}" title="Translation">🌐</button><button data-g="quit" title="End game">✕</button></span>`;
    hud.querySelectorAll('[data-g]').forEach(b => b.onclick = () => this.gameAction(b.dataset.g));
  }
  showResults(r) {
    const best = (cfg.best[this.title] = cfg.best[this.title] || {});
    const isBest = r.score > (best[r.level] || 0);
    if (isBest) best[r.level] = r.score;
    saveCfg();
    const stars = r.accuracy >= 90 ? 3 : r.accuracy >= 70 ? 2 : r.accuracy >= 40 ? 1 : 0;
    const order = Object.keys(LEVELS); const nextLv = order[order.indexOf(r.level) + 1];
    const c = this.$('.center'); c.hidden = false;
    c.innerHTML = `<div class="card"><h2>${r.lives <= 0 ? '💔 Out of lives' : r.quit ? '🏁 Results' : '🎉 Clip completed!'}</h2>
      <div class="stars">${'⭐'.repeat(stars)}${'☆'.repeat(3 - stars)}</div><div class="big-score grad">${r.score}</div>
      ${isBest ? '<div class="newbest">🏆 New record!</div>' : ''}
      <div class="stats"><div><b>${r.accuracy}%</b><span>accuracy</span></div><div><b>${r.maxCombo}</b><span>best combo</span></div><div><b>${r.correct}</b><span>words</span></div></div>
      ${r.missed.length ? `<h5>Words you missed</h5><div class="missed">${r.missed.slice(0, 30).map(w => `<span>${esc(w)}</span>`).join('')}</div><button class="btn" data-r="save">☆ Save these words</button>` : ''}
      <div class="row center-row"><button class="btn" data-r="exit">Close</button><button class="btn" data-r="again">↺ Play again</button>${nextLv ? `<button class="btn pri" data-r="next">${LEVELS[nextLv].emoji} Next level</button>` : ''}</div></div>`;
    c.querySelector('[data-r=exit]').onclick = () => this.renderCenter();
    c.querySelector('[data-r=again]').onclick = () => this.startGame(this.game.startIdx || 0);
    const nx = c.querySelector('[data-r=next]'); if (nx) nx.onclick = () => { cfg.level = nextLv; saveCfg(); this.startGame(this.game.startIdx || 0); };
    const sv = c.querySelector('[data-r=save]');
    if (sv) sv.onclick = async () => {
      sv.disabled = true; const s = savedOf(); let n = 0;
      for (const w of r.missed.slice(0, 30)) {
        const k = w.toLowerCase(); if (s[k]) continue;
        let meaning = ''; try { meaning = await translate(w, 'en', native()); } catch {}
        const line = this.cues.find(cu => cu.text.includes(w));
        s[k] = { word: w, meaning, ipa: '', example: '', context: line ? line.text : '', title: this.title, at: Date.now() }; n++;
      }
      saveCfg(); sv.textContent = `✓ ${n} words saved`;
    };
    this.renderHud();
  }

  // ---------------------------------------------------------------- bits
  float(txt, cls) { const el = document.createElement('div'); el.className = 'fl ' + cls; el.textContent = txt; this.$('.floats').appendChild(el); setTimeout(() => el.remove(), 1400); }
  toast(msg, ms = 3500) { const el = this.$('.toast'); el.textContent = msg; el.hidden = false; clearTimeout(this._toast); this._toast = setTimeout(() => { el.hidden = true; }, ms); }
}

function toTs(s) {
  const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = Math.floor(s % 60), ms = Math.round((s % 1) * 1000);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
}
