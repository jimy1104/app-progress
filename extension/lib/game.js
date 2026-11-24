// "Escucha y completa": a listening game. Words disappear from the subtitles; you type them while
// the clip plays. When a line ends with blanks left, the video pauses and a countdown starts.
import { tokenize } from './subtitles.js';
import { isFunctionWord } from './grammar.js';

export const LEVELS = {
  basic: { ratio: 0, lives: 5, factor: 1.6, emoji: '🌱' },
  medium: { ratio: 0.5, lives: 4, factor: 1.2, emoji: '🔥' },
  hard: { ratio: 0.9, lives: 3, factor: 1.0, emoji: '💀' },
};

export function norm(s) {
  return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^\p{L}\p{N}]/gu, '');
}
function hash(str) { let h = 2166136261; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function shuffle(arr, r) { const a = arr.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }

/** Choose which word tokens of a line become blanks. Deterministic per line + level. */
export function chooseBlanks(text, level) {
  const toks = tokenize(text);
  const wordIdx = toks.map((k, i) => (k.w && /\p{L}/u.test(k.t) ? i : -1)).filter(i => i >= 0);
  if (!wordIdx.length) return { toks, blanks: [] };
  const r = rng(hash(text + '|' + level));
  let chosen;
  if (level === 'basic') {
    const content = wordIdx.filter(i => !isFunctionWord(toks[i].t) && norm(toks[i].t).length >= 3);
    const pool = content.length ? content : wordIdx.filter(i => norm(toks[i].t).length >= 2);
    chosen = pool.length ? [shuffle(pool, r)[0]] : [];
  } else {
    const n = level === 'medium' ? Math.max(1, Math.round(wordIdx.length * LEVELS.medium.ratio)) : Math.max(1, Math.ceil(wordIdx.length * LEVELS.hard.ratio));
    chosen = shuffle(wordIdx, r).slice(0, n);
  }
  chosen.sort((a, b) => a - b);
  return { toks, blanks: chosen.map(tokIdx => ({ tokIdx, word: toks[tokIdx].t, done: false, revealed: false, typed: '', hints: 0 })) };
}

export class Game {
  /** ctx: { cues(), seekToLine(i, play), pause(), play(), t(key), onFinish(results), onChange(), host: {line, hud, timer} } */
  constructor(ctx) {
    this.ctx = ctx;
    this.active = false;   // game app selected
    this.running = false;  // a match is in progress
    this.level = 'basic';
    this.lines = new Map();
    this._frame = this._frame.bind(this);
  }

  start(level, fromIdx = 0) {
    this.level = level;
    this.lines.clear();
    Object.assign(this, { running: true, score: 0, combo: 0, maxCombo: 0, lives: LEVELS[level].lives, correct: 0, missedWords: [], hintsUsed: 0, waiting: null, timer: null, startIdx: fromIdx, lineStartedAt: performance.now() });
    this.ctx.onChange();
    this.ctx.seekToLine(fromIdx, true);
    this.ctx.renderLine(fromIdx);
    requestAnimationFrame(this._frame);
  }

  stop() { this.running = false; this.waiting = null; this.timer = null; this.ctx.onChange(); }

  line(i) {
    if (!this.lines.has(i)) { const c = this.ctx.cues()[i]; this.lines.set(i, chooseBlanks(c ? c.text : '', this.level)); }
    return this.lines.get(i);
  }
  remaining(i) { return this.line(i).blanks.filter(b => !b.done && !b.revealed).length; }

  /** Called by the player engine when line i reaches its end. Returns 'pause' or 'continue'. */
  onLineEnd(i) {
    if (!this.running) return 'continue';
    const last = i >= this.ctx.cues().length - 1;
    if (this.remaining(i) === 0) {
      if (last) { this.finish(); return 'pause'; }
      return 'continue';
    }
    if (this.waiting && this.waiting.i === i && this.timer) { this.timer.paused = false; this.timer.last = performance.now(); return 'pause'; } // after a replay
    const limit = Math.min(45, Math.max(5, (3 + 2.2 * this.remaining(i)) * LEVELS[this.level].factor));
    this.waiting = { i };
    this.timer = { limit, left: limit, paused: false, last: performance.now() };
    this.ctx.onChange();
    this.focusNext(i);
    return 'pause';
  }

  onLineShown() { this.lineStartedAt = performance.now(); }

  replay() {
    if (!this.waiting) return;
    if (this.timer) this.timer.paused = true;
    this.ctx.seekToLine(this.waiting.i, true);
  }

  _frame(now) {
    if (!this.running) return;
    requestAnimationFrame(this._frame);
    const tm = this.timer;
    if (!tm || tm.paused) return;
    tm.left -= (now - tm.last) / 1000; tm.last = now;
    this.ctx.renderTimer(Math.max(0, tm.left) / tm.limit, Math.max(0, tm.left));
    if (tm.left <= 0) this.timeUp();
  }

  timeUp(skip = false) {
    const w = this.waiting; if (!w) return;
    const ln = this.line(w.i);
    for (const b of ln.blanks) if (!b.done && !b.revealed) { b.revealed = true; this.missedWords.push(b.word); }
    this.combo = 0;
    if (!skip) this.lives--;
    this.timer = null;
    this.ctx.flash(skip ? '⏭' : this.ctx.t('timeUp'), 'bad');
    this.ctx.renderLine(w.i);
    this.ctx.onChange();
    const i = w.i;
    setTimeout(() => {
      if (!this.running) return;
      this.waiting = null;
      if (this.lives <= 0 || i >= this.ctx.cues().length - 1) { this.finish(); return; }
      this.ctx.seekToLine(i + 1, true);
    }, skip ? 700 : 1800);
  }

  /** Called on every keystroke in a blank. Returns 'ok' | 'prefix' | 'wrong' | ''. */
  type(i, bi, value) {
    const ln = this.line(i); const b = ln.blanks[bi];
    if (!b || b.done || b.revealed || !this.running) return '';
    b.typed = value;
    const v = norm(value), target = norm(b.word);
    if (!v) return '';
    if (v === target) { this.correctWord(i, b); return 'ok'; }
    return target.startsWith(v) ? 'prefix' : 'wrong';
  }

  correctWord(i, b) {
    b.done = true;
    this.correct++; this.combo++; this.maxCombo = Math.max(this.maxCombo, this.combo);
    const mult = Math.min(3, 1 + Math.floor(this.combo / 5) * 0.5);
    let speed = 50; // typed while still listening = full bonus
    if (this.waiting && this.timer) speed = Math.round(50 * Math.max(0, this.timer.left) / this.timer.limit);
    const pts = Math.max(10, Math.round((100 + speed) * mult) - b.hints * 30);
    this.score += pts;
    this.ctx.floatPoints(`+${pts}${mult > 1 ? ` ×${mult}` : ''}`);
    if (this.combo > 0 && this.combo % 5 === 0) this.ctx.flash(`🔥 Combo ${this.combo}!`, 'good');
    this.ctx.renderLine(i);
    if (this.remaining(i) === 0) {
      if (this.waiting && this.waiting.i === i) {
        this.timer = null; this.waiting = null;
        this.ctx.flash(this.ctx.t('perfect'), 'good');
        setTimeout(() => {
          if (!this.running) return;
          if (i >= this.ctx.cues().length - 1) this.finish(); else this.ctx.seekToLine(i + 1, true);
        }, 450);
      }
    } else this.focusNext(i);
    this.ctx.onChange();
  }

  hint(i) {
    const ln = this.line(i);
    const bi = ln.blanks.findIndex(b => !b.done && !b.revealed);
    if (bi < 0) return;
    const b = ln.blanks[bi];
    const typed = norm(b.typed); const target = norm(b.word);
    let k = 0; while (k < typed.length && typed[k] === target[k]) k++;
    // Rebuild the typed prefix from the original word (keeps apostrophes/case).
    let count = 0, out = '';
    for (const ch of b.word) { if (count > k) break; out += ch; if (/[\p{L}\p{N}]/u.test(ch)) count++; }
    b.typed = out; b.hints++; this.hintsUsed++;
    this.score = Math.max(0, this.score - 25);
    if (norm(out) === target) this.correctWord(i, b);
    else { this.ctx.renderLine(i); this.focusNext(i); this.ctx.onChange(); }
  }

  focusNext(i) { this.ctx.focusBlank(i, this.line(i).blanks.findIndex(b => !b.done && !b.revealed)); }

  finish(quit = false) {
    if (!this.running) return;
    this.running = false; this.timer = null; this.waiting = null;
    this.ctx.pause();
    const total = this.correct + this.missedWords.length;
    const accuracy = total ? Math.round(this.correct / total * 100) : 0;
    this.ctx.onFinish({ quit, level: this.level, score: this.score, accuracy, maxCombo: this.maxCombo, correct: this.correct, missed: [...new Set(this.missedWords)], lives: this.lives, hints: this.hintsUsed });
    this.ctx.onChange();
  }
}
