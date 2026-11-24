// Microphone recording + waveform + optional speech recognition (Chrome/Edge) for a word-match score.
import { words } from './subtitles.js';

export class Recorder {
  constructor() { this.stream = null; this.rec = null; this.recognition = null; this.recording = false; this.last = null; }

  static recognitionSupported() { return !!(window.SpeechRecognition || window.webkitSpeechRecognition); }

  async ensureStream() {
    if (this.stream && this.stream.active) return this.stream;
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    return this.stream;
  }

  release() { if (this.stream) { this.stream.getTracks().forEach(t => t.stop()); this.stream = null; } }

  async start(lang = 'en-US') {
    if (this.recording) return;
    const stream = await this.ensureStream();
    const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'].find(m => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || '';
    this.chunks = [];
    this.rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    this.rec.ondataavailable = e => { if (e.data && e.data.size) this.chunks.push(e.data); };
    this.startedAt = performance.now();
    this.rec.start();
    this.recording = true;
    this.transcript = '';
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) {
      try {
        const r = new SR();
        r.lang = lang; r.continuous = true; r.interimResults = true; r.maxAlternatives = 1;
        let finals = ''; let interim = '';
        r.onresult = e => {
          interim = '';
          for (let i = e.resultIndex; i < e.results.length; i++) {
            if (e.results[i].isFinal) finals += ' ' + e.results[i][0].transcript; else interim += ' ' + e.results[i][0].transcript;
          }
          this.transcript = (finals + ' ' + interim).trim();
        };
        r.onerror = () => {};
        r.start();
        this.recognition = r;
      } catch { this.recognition = null; }
    }
  }

  stop() {
    if (!this.recording) return Promise.resolve(this.last);
    this.recording = false;
    const duration = (performance.now() - this.startedAt) / 1000;
    const recog = this.recognition; this.recognition = null;
    const recogDone = new Promise(res => {
      if (!recog) return res();
      const timer = setTimeout(res, 1200);
      recog.onend = () => { clearTimeout(timer); res(); };
      try { recog.stop(); } catch { res(); }
    });
    const recDone = new Promise(res => { this.rec.onstop = res; this.rec.stop(); });
    return Promise.all([recDone, recogDone]).then(async () => {
      const blob = new Blob(this.chunks, { type: this.rec.mimeType || 'audio/webm' });
      if (this.last && this.last.url) URL.revokeObjectURL(this.last.url);
      const url = URL.createObjectURL(blob);
      let peaks = null; let realDuration = duration;
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const buf = await ctx.decodeAudioData(await blob.arrayBuffer());
        realDuration = buf.duration;
        peaks = computePeaks(buf.getChannelData(0), 600);
        ctx.close();
      } catch { /* some browsers can't decode webm; waveform is optional */ }
      this.last = { blob, url, duration: realDuration, peaks, transcript: this.transcript || '' };
      return this.last;
    });
  }

  play(onEnd) {
    if (!this.last) return null;
    if (this.audio) this.audio.pause();
    this.audio = new Audio(this.last.url);
    this.audio.onended = () => onEnd && onEnd();
    this.audio.play().catch(() => onEnd && onEnd());
    return this.audio;
  }
}

function computePeaks(data, n) {
  const step = Math.max(1, Math.floor(data.length / n));
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    let max = 0; const st = i * step;
    for (let j = st; j < st + step && j < data.length; j++) { const v = Math.abs(data[j]); if (v > max) max = v; }
    out[i] = max;
  }
  const top = Math.max(...out) || 1;
  return out.map(v => v / top);
}

export function drawWave(canvas, peaks, { color = '#8f83ff', progress = 0 } = {}) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const g = canvas.getContext('2d');
  g.scale(dpr, dpr);
  g.clearRect(0, 0, w, h);
  if (!peaks) {
    g.fillStyle = '#2a3142'; g.fillRect(0, h / 2 - 1, w, 2);
    return;
  }
  const bars = Math.min(peaks.length, Math.floor(w / 3));
  const per = peaks.length / bars;
  for (let i = 0; i < bars; i++) {
    let v = 0; for (let j = Math.floor(i * per); j < Math.floor((i + 1) * per); j++) v = Math.max(v, peaks[j]);
    const bh = Math.max(2, v * (h - 8));
    g.fillStyle = i / bars < progress ? '#2ec27e' : color;
    g.fillRect(i * 3, (h - bh) / 2, 2, bh);
  }
}

/** Compare expected text vs recognised speech. Returns { score, marks:[{w, ok}] }. */
export function scoreSpeech(expected, heard) {
  const ex = words(expected).map(w => w.replace(/'/g, ''));
  const hw = words(heard).map(w => w.replace(/'/g, ''));
  const n = ex.length, m = hw.length;
  const dp = Array.from({ length: n + 1 }, () => new Int16Array(m + 1));
  const same = (a, b) => a === b || (a.length > 3 && b.length > 3 && (a.startsWith(b) || b.startsWith(a))) || numEq(a, b);
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = same(ex[i], hw[j]) ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const ok = new Array(n).fill(false);
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (same(ex[i], hw[j])) { ok[i] = true; i++; j++; } else if (dp[i + 1][j] >= dp[i][j + 1]) i++; else j++;
  }
  const original = words(expected);
  return { score: n ? Math.round(ok.filter(Boolean).length / n * 100) : 0, marks: original.map((w, k) => ({ w, ok: ok[k] })) };
}
const NUM = { zero: '0', one: '1', two: '2', three: '3', four: '4', five: '5', six: '6', seven: '7', eight: '8', nine: '9', ten: '10' };
function numEq(a, b) { return NUM[a] === b || NUM[b] === a; }

/** Similarity between two translations (token overlap, Dice coefficient), 0–100. */
export function similarity(a, b) {
  const norm = s => words(s).map(w => w.normalize('NFD').replace(/[̀-ًͯ-ٟ]/g, ''));
  const A = norm(a), B = norm(b);
  if (!A.length || !B.length) return 0;
  const bag = new Map(); B.forEach(w => bag.set(w, (bag.get(w) || 0) + 1));
  let common = 0;
  for (const w of A) { const c = bag.get(w); if (c) { common++; bag.set(w, c - 1); } }
  return Math.round(2 * common / (A.length + B.length) * 100);
}
