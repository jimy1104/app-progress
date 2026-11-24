// Player adapters with one common interface:
//   ready (Promise), play(), pause(), seek(t), time(), duration(), paused(), setRate(r), destroy()

export class Html5Player {
  constructor(host, src, { isAudio = false, hls = false } = {}) {
    this.kind = 'html5';
    this.el = document.createElement(isAudio ? 'audio' : 'video');
    this.el.playsInline = true;
    this.el.preload = 'auto';
    this.el.controls = isAudio; // video uses our own controls; native controls would fight with auto-pause
    if (!isAudio) this.el.addEventListener('click', () => (this.paused() ? this.play() : this.pause()));
    host.appendChild(this.el);
    if (isAudio) host.classList.add('audio-only');
    this.ready = new Promise((resolve, reject) => {
      this.el.addEventListener('loadedmetadata', () => resolve(), { once: true });
      this.el.addEventListener('error', () => reject(new Error('media-error')), { once: true });
    });
    if (hls && !this.el.canPlayType('application/vnd.apple.mpegurl')) {
      this.ready = loadScript('https://cdn.jsdelivr.net/npm/hls.js@1.5.13/dist/hls.min.js').then(() => new Promise((resolve, reject) => {
        // eslint-disable-next-line no-undef
        const h = new Hls();
        this.hls = h;
        h.loadSource(src); h.attachMedia(this.el);
        // eslint-disable-next-line no-undef
        h.on(Hls.Events.MANIFEST_PARSED, () => resolve());
        // eslint-disable-next-line no-undef
        h.on(Hls.Events.ERROR, (_, d) => { if (d.fatal) reject(new Error('hls')); });
      }));
    } else {
      this.el.src = src;
    }
  }
  play() { return this.el.play().catch(() => {}); }
  pause() { this.el.pause(); }
  seek(t) { this.el.currentTime = Math.max(0, t); }
  time() { return this.el.currentTime; }
  duration() { return this.el.duration || 0; }
  paused() { return this.el.paused; }
  setRate(r) { this.el.playbackRate = r; }
  get mediaElement() { return this.el; }
  destroy() { try { this.hls && this.hls.destroy(); } catch {} this.el.pause(); this.el.removeAttribute('src'); this.el.load(); this.el.remove(); }
}

let ytApi = null;
function loadYouTubeApi() {
  if (ytApi) return ytApi;
  ytApi = new Promise(resolve => {
    if (window.YT && window.YT.Player) return resolve(window.YT);
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => { prev && prev(); resolve(window.YT); };
    loadScript('https://www.youtube.com/iframe_api');
  });
  return ytApi;
}

export function youtubeId(url) {
  try {
    const u = new URL(url);
    if (/youtu\.be$/.test(u.hostname)) return u.pathname.slice(1).split('/')[0];
    if (/youtube(-nocookie)?\.com$/.test(u.hostname.replace(/^www\.|^m\.|^music\./, ''))) {
      if (u.searchParams.get('v')) return u.searchParams.get('v');
      const m = u.pathname.match(/\/(embed|shorts|live|v)\/([\w-]{6,})/);
      if (m) return m[2];
    }
  } catch {}
  return null;
}

export class YouTubePlayer {
  constructor(host, videoId) {
    this.kind = 'youtube';
    const div = document.createElement('div');
    div.className = 'yt';
    host.appendChild(div);
    this._rate = 1;
    this.ready = loadYouTubeApi().then(YT => new Promise((resolve, reject) => {
      this.p = new YT.Player(div, {
        videoId,
        playerVars: { playsinline: 1, rel: 0, modestbranding: 1, cc_load_policy: 0, iv_load_policy: 3, origin: location.origin },
        events: { onReady: () => resolve(), onError: e => reject(new Error('yt-' + e.data)) },
      });
    }));
  }
  play() { this.p && this.p.playVideo(); }
  pause() { this.p && this.p.pauseVideo(); }
  seek(t) { this.p && this.p.seekTo(Math.max(0, t), true); }
  time() { return this.p && this.p.getCurrentTime ? this.p.getCurrentTime() : 0; }
  duration() { return this.p && this.p.getDuration ? this.p.getDuration() : 0; }
  paused() { const s = this.p && this.p.getPlayerState ? this.p.getPlayerState() : 2; return s !== 1 && s !== 3; }
  setRate(r) { this._rate = r; this.p && this.p.setPlaybackRate && this.p.setPlaybackRate(r); }
  destroy() { try { this.p && this.p.destroy(); } catch {} }
}

/**
 * No video: a virtual clock that reads each cue aloud with the browser's speech synthesis.
 * The clock advances through a cue while it is being spoken and lands on its end when speech
 * finishes, so auto-pause / loops work exactly like with a real video.
 */
export class TtsPlayer {
  constructor(host, cues, langCode) {
    this.kind = 'tts';
    this.cues = cues; this.lang = langCode || 'en-US';
    this._t = cues.length ? Math.max(0, cues[0].start - 0.2) : 0;
    this._playing = false; this._rate = 1; this._speakingIdx = -1; this._timer = null;
    this.view = document.createElement('div');
    this.view.className = 'tts-visual';
    this.view.innerHTML = '<div><div class="wave-dot">◉</div><div class="big"></div></div>';
    host.appendChild(this.view);
    this.ready = Promise.resolve();
    this._loop = this._loop.bind(this);
  }
  _voice() {
    const vs = speechSynthesis.getVoices();
    const base = this.lang.slice(0, 2);
    return vs.find(v => v.lang === this.lang && /Google|Natural|Online/i.test(v.name)) || vs.find(v => v.lang === this.lang) || vs.find(v => v.lang.startsWith(base));
  }
  _cueAt(t) { for (let i = 0; i < this.cues.length; i++) if (t < this.cues[i].end - 0.01) return i; return -1; }
  _speak(i) {
    const cue = this.cues[i]; if (!cue) return;
    speechSynthesis.cancel();
    this._speakingIdx = i; this._spokeAt = performance.now();
    this.view.querySelector('.big').textContent = '';
    const u = new SpeechSynthesisUtterance(cue.text);
    const v = this._voice(); if (v) u.voice = v;
    u.lang = this.lang; u.rate = this._rate;
    u.onend = () => {
      if (this._speakingIdx !== i || !this._playing) return;
      this._speakingIdx = -1;
      this._t = cue.end + 0.01; // land at the end of the cue
      const next = this.cues[i + 1];
      clearTimeout(this._timer);
      this._timer = setTimeout(() => { if (this._playing && next && this._t < next.start) this._t = next.start; }, 380 / this._rate);
    };
    speechSynthesis.speak(u);
  }
  _loop() {
    if (!this._playing) return;
    const i = this._cueAt(this._t);
    if (i < 0) { this._playing = false; return; }
    const cue = this.cues[i];
    if (this._t >= cue.start && this._speakingIdx !== i && this._t < cue.end) this._speak(i);
    if (this._speakingIdx === i) {
      const est = (cue.end - cue.start);
      const el = (performance.now() - this._spokeAt) / 1000 * this._rate;
      this._t = Math.min(cue.start + Math.min(el, est * 0.97), cue.end - 0.08);
    } else if (this._t < cue.start) {
      this._t = Math.min(cue.start, this._t + 1 / 60 * this._rate);
    }
    this._raf = requestAnimationFrame(this._loop);
  }
  play() {
    if (this._playing) return;
    if (this._cueAt(this._t) < 0 && this.cues.length) this._t = this.cues[0].start;
    this._playing = true; this._speakingIdx = -1; this._loop();
  }
  pause() { this._playing = false; this._speakingIdx = -1; speechSynthesis.cancel(); cancelAnimationFrame(this._raf); clearTimeout(this._timer); }
  seek(t) { const was = this._playing; this.pause(); this._t = Math.max(0, t); if (was) this.play(); }
  time() { return this._t; }
  duration() { return this.cues.length ? this.cues[this.cues.length - 1].end : 0; }
  paused() { return !this._playing; }
  setRate(r) { this._rate = r; }
  destroy() { this.pause(); this.view.remove(); }
}

export function speak(text, lang = 'en-US', rate = 0.85) {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  const vs = speechSynthesis.getVoices();
  const v = vs.find(x => x.lang === lang && /Google|Natural|Online/i.test(x.name)) || vs.find(x => x.lang === lang) || vs.find(x => x.lang.startsWith(lang.slice(0, 2)));
  if (v) u.voice = v;
  u.lang = lang; u.rate = rate;
  speechSynthesis.speak(u);
}

const scripts = {};
export function loadScript(src) {
  if (scripts[src]) return scripts[src];
  scripts[src] = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src; s.async = true; s.onload = resolve; s.onerror = () => { delete scripts[src]; reject(new Error('script ' + src)); };
    document.head.appendChild(s);
  });
  return scripts[src];
}

/** Hosts that refuse to be controlled from another site. */
export function isUnsupportedHost(url) {
  return /bilibili\.|b23\.tv|netflix\.|disneyplus\.|primevideo\.|amazon\.|hbomax\.|max\.com|crunchyroll\.|vimeo\.com\/(?!.*\.mp4)|tiktok\.|instagram\.|facebook\.|iqiyi\.|viki\.|wetv\./i.test(url);
}
